"""AFLOW-specific enrichment and schema normalization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from core.schema import normalize_by_schema

SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "schemas" / "dft"
STANDARD_SCHEMA = SCHEMA_ROOT / "standard.yaml"
AFLOW_MAPPING = SCHEMA_ROOT / "aflow.yaml"


def _first_path(paths: list[Path], patterns: tuple[str, ...]) -> Path | None:
    """Return the first downloaded path matching one of the filename patterns."""
    for path in paths:
        name = path.name.lower()
        if any(pattern in name for pattern in patterns):
            return path
    return None


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a small AFLOW property JSON file, including .xz files."""
    import json
    import lzma

    try:
        raw = path.read_bytes()
        if path.suffix.lower() == ".xz":
            raw = lzma.decompress(raw)
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, lzma.LZMAError, UnicodeDecodeError):
        return None


def _parse_structure(paths: list[Path]) -> Any:
    """Read the first local CIF structure when pymatgen is available."""
    cif = next((path for path in paths if path.suffix.lower() == ".cif" and path.exists()), None)
    if cif is None:
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_file(cif)
    except Exception:
        return None


def _formula_parts(document: dict[str, Any], structure: Any) -> tuple[str | None, list[str] | None, dict[str, float] | None]:
    if structure is not None:
        composition = structure.composition
        return composition.reduced_formula, sorted(str(element) for element in composition.elements), composition.get_el_amt_dict()
    species = document.get("species")
    amounts = document.get("composition")
    if isinstance(species, list) and isinstance(amounts, list) and len(species) == len(amounts):
        composition = {str(element): amount for element, amount in zip(species, amounts)}
        formula = "".join(f"{element}{amount:g}" for element, amount in composition.items())
        return formula, sorted(str(element) for element in species), composition
    return None, None, None



def _parse_vasp_inputs(paths: list[Path]) -> dict[str, Any]:
    """Extract common calculation settings from downloaded VASP input files."""
    result: dict[str, Any] = {}
    incar = next((path for path in paths if path.name.upper().startswith("INCAR") and path.exists()), None)
    if incar is None:
        return result
    try:
        text = incar.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return result
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("!", 1)[0].split("#", 1)[0]
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().upper()] = value.strip()
    if "ENCUT" in values:
        try:
            result["energy_cutoff"] = float(values["ENCUT"])
        except ValueError:
            pass
    if "ISMEAR" in values:
        result["smearing"] = values["ISMEAR"]
    result["spin_orbit_coupling"] = values.get("LSORBIT", "").upper() in {"T", ".TRUE.", "TRUE"}
    result["hubbard_u"] = values.get("LDAU", "").upper() in {"T", ".TRUE.", "TRUE"}
    if "LDAUU" in values:
        try:
            result["u_values"] = [float(value) for value in values["LDAUU"].replace(",", " ").split()]
        except ValueError:
            pass
    if values.get("NSW", "0").strip() not in {"0", "0.0"} or "CONTCAR" in " ".join(path.name for path in paths):
        result["relaxation_status"] = "relaxed"
    result["basis_set"] = "plane-wave"
    return result

def enrich_aflow_document(document: dict[str, Any], downloaded_files: Iterable[str | Path] | None = None) -> dict[str, Any]:
    """Derive standard DFT values from AFLOW metadata and local files.

    Args:
        document (dict[str, Any]): Raw AFLOWLIB metadata document.
        downloaded_files (Iterable[str | Path] | None): Local files saved for the material.

    Returns:
        dict[str, Any]: Enriched AFLOW document ready for schema normalization.
    """
    enriched = dict(document)
    paths = [Path(path) for path in (downloaded_files or [])]
    structure = _parse_structure(paths)
    formula_reduced, elements, composition = _formula_parts(enriched, structure)
    geometry = enriched.get("geometry") or []
    if structure is not None:
        lattice = structure.lattice
        enriched["structure"] = structure.as_dict()
        enriched["lattice_matrix"] = lattice.matrix.tolist()
        enriched["lattice_a"] = lattice.a
        enriched["lattice_b"] = lattice.b
        enriched["lattice_c"] = lattice.c
        enriched["angle_alpha"] = lattice.alpha
        enriched["angle_beta"] = lattice.beta
        enriched["angle_gamma"] = lattice.gamma
        try:
            enriched["spacegroup_symbol"] = structure.get_space_group_info()[0]
        except Exception:
            pass
    elif isinstance(geometry, list) and len(geometry) >= 6:
        try:
            from pymatgen.core import Lattice

            lattice = Lattice.from_parameters(*[float(value) for value in geometry[:6]])
            enriched["lattice_matrix"] = lattice.matrix.tolist()
            enriched["lattice_a"], enriched["lattice_b"], enriched["lattice_c"] = lattice.a, lattice.b, lattice.c
            enriched["angle_alpha"], enriched["angle_beta"], enriched["angle_gamma"] = lattice.alpha, lattice.beta, lattice.gamma
        except Exception:
            pass
    enriched["formula_reduced"] = formula_reduced
    enriched["elements"] = elements
    enriched["composition_standard"] = composition
    enriched["element_count"] = len(elements) if elements else enriched.get("nspecies")
    enriched["chemical_system"] = "-".join(elements) if elements else None
    enriched["spacegroup_number"] = enriched.get("spacegroup_relax")
    enriched["point_group"] = enriched.get("point_group_Hermann_Mauguin")
    enriched["calculation_method"] = enriched.get("code")
    enriched["calculation_type"] = enriched.get("dft_type")
    enriched["code_version"] = enriched.get("code")
    dft_type = enriched.get("dft_type")
    functional_text = ", ".join(str(value) for value in dft_type) if isinstance(dft_type, list) else dft_type
    enriched["functional"] = functional_text
    enriched["exchange_correlation"] = functional_text
    enriched["kpoint_mesh"] = enriched.get("kpoints_static") or enriched.get("kpoints_relax")
    enriched["spin_polarized"] = enriched.get("spin_cell") is not None or enriched.get("spinD") is not None
    enriched["is_metal"] = bool(enriched.get("Egap") is not None and float(enriched["Egap"]) <= 0)
    gap_type = str(enriched.get("Egap_type") or "").lower()
    enriched["is_gap_direct"] = bool(gap_type) if "direct" in gap_type else None
    enriched["total_magnetization"] = enriched.get("spin_cell")
    enriched["magnetization_per_atom"] = enriched.get("spin_atom")
    spin_sites = enriched.get("spinD")
    enriched["magnetic_moments"] = spin_sites
    if isinstance(spin_sites, list):
        enriched["magnetic_site_count"] = sum(1 for value in spin_sites if value is not None and abs(float(value)) > 1e-8)
    enriched["bulk_modulus_vrh"] = enriched.get("ael_bulk_modulus_vrh")
    enriched["shear_modulus_vrh"] = enriched.get("ael_shear_modulus_vrh")
    enriched["youngs_modulus"] = enriched.get("ael_youngs_modulus_vrh")
    enriched["debye_temperature"] = enriched.get("ael_debye_temperature") or enriched.get("agl_debye")
    enriched["formation_energy_per_atom"] = enriched.get("enthalpy_formation_atom")
    enriched["volume"] = enriched.get("volume_cell")
    enriched.update(_parse_vasp_inputs(paths))
    enriched["formula_anonymous"] = structure.composition.anonymized_formula if structure is not None else None
    enriched["composition_reduced"] = composition
    enriched["nelements"] = len(elements) if elements else None
    enriched["is_magnetic"] = bool(enriched.get("spin_cell") not in (None, 0) or any(float(value) != 0 for value in (spin_sites or []))) if isinstance(spin_sites, list) else bool(enriched.get("spin_cell"))
    enriched["last_updated"] = enriched.get("aflowlib_date")
    enriched["updated_at"] = enriched.get("aflowlib_date")
    # Property files are source data too: expose their paths and merge small JSON summaries.
    ael_path = _first_path(paths, ("ael.json", "elastic", "elasticity"))
    agl_path = _first_path(paths, ("agl.json", "phonon", "thermal"))
    dielectric_path = _first_path(paths, ("dielectric", "epsilon", "born"))
    enriched["elastic_tensor_path"] = str(ael_path) if ael_path else None
    enriched["phonon_band_structure_path"] = str(agl_path) if agl_path else None
    enriched["phonon_dos_path"] = str(agl_path) if agl_path else None
    enriched["has_elasticity"] = bool(ael_path or enriched.get("ael_bulk_modulus_vrh") is not None)
    enriched["has_phonon"] = bool(agl_path)
    enriched["has_dielectric"] = bool(dielectric_path)
    for property_path in (ael_path, agl_path):
        if property_path:
            property_data = _load_json(property_path)
            if property_data:
                for key, value in property_data.items():
                    if key not in enriched or enriched.get(key) is None:
                        enriched[key] = value

    enriched["downloaded_file_paths"] = {path.name: str(path) for path in paths}
    structure_path = _first_path(paths, (".cif", "structure_relax"))
    structure_json = _first_path(paths, ("structure_relax",))
    band_path = _first_path(paths, ("bandsdata", "eigenval", "edata.bands"))
    dos_path = _first_path(paths, ("dosdata", "doscar", "edata.static"))
    enriched["structure_path"] = str(structure_path) if structure_path else None
    enriched["structure_json_path"] = str(structure_json) if structure_json else None
    enriched["structure_format"] = ["cif"] if structure_path else None
    enriched["band_structure_path"] = str(band_path) if band_path else None
    enriched["dos_path"] = str(dos_path) if dos_path else None
    enriched["has_structure"] = structure_path is not None or enriched.get("geometry") is not None
    enriched["has_band_structure"] = band_path is not None
    enriched["has_dos"] = dos_path is not None
    return enriched


def normalize_aflow(document: dict[str, Any], downloaded_files: Iterable[str | Path] | None = None) -> dict[str, Any]:
    """Map enriched AFLOWLIB data into the unified DFT schema.

    Args:
        document (dict[str, Any]): Raw AFLOWLIB metadata document.
        downloaded_files (Iterable[str | Path] | None): Local material files.

    Returns:
        dict[str, Any]: Unified DFT record with derived values filled when available.
    """
    enriched = enrich_aflow_document(document, downloaded_files)
    return normalize_by_schema(enriched, STANDARD_SCHEMA, AFLOW_MAPPING)




