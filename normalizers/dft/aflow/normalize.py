"""AFLOW normalization: raw metadata plus local files to DFT standard record."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from normalizers.dft import fill_derived_pairs

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path such as ``ael_bulk_modulus_vrh``."""
    if not field_path:
        return None
    value: Any = document
    for part in field_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            return None
        if value is None:
            return None
    return value


def _requested_id(_: Any, document: dict[str, Any]) -> str | None:
    return document.get("_requested_id")


def _lowercase(value: Any, _: dict[str, Any]) -> str | None:
    return None if value is None else str(value).strip().lower()


def _kbar_to_gpa(value: Any, _: dict[str, Any]) -> float | None:
    return None if value is None else float(value) * 0.1


def _now(_: Any, __: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TRANSFORMS = {
    "requested_id": _requested_id,
    "lowercase": _lowercase,
    "kbar_to_gpa": _kbar_to_gpa,
    "now": _now,
}


def _first_path(paths: list[Path], patterns: tuple[str, ...]) -> Path | None:
    """Return the first downloaded path matching one of the filename patterns."""
    for path in paths:
        name = path.name.lower()
        if any(pattern in name for pattern in patterns):
            return path
    return None


def _compact_electronic_summary(document: dict[str, Any] | None, kind: str) -> dict[str, Any] | None:
    """Create a small summary from an AFLOW band or DOS JSON document."""
    if not document:
        return None
    keys = ("name", "Emin", "Emax", "Efermi", "n_kpoints", "n_bands", "title")
    summary = {key: document[key] for key in keys if key in document}
    if "DOS_grid" in document and isinstance(document["DOS_grid"], list):
        summary["energy_grid_points"] = len(document["DOS_grid"])
    if kind == "bandstructure" and isinstance(document.get("bands_data"), list):
        summary["bands_data_points"] = len(document["bands_data"])
    return summary or None


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


def _safe_name(value: Any) -> str:
    """Return a filesystem-safe name for an AFLOW identifier."""
    text = str(value).replace(":", "_").replace("/", "_").replace("\\", "_")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def _write_cif(structure: Any, target: Path) -> bool:
    """Write one pymatgen structure to a CIF file, creating parents as needed."""
    try:
        from pymatgen.io.cif import CifWriter

        target.parent.mkdir(parents=True, exist_ok=True)
        CifWriter(structure).write_file(target)
        return True
    except Exception:
        return False


def _structure_from_json(payload: Any) -> Any:
    """Parse a pymatgen structure dict or an AFLOW structure JSON document."""
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        if "@module" in payload or "sites" in payload:
            return Structure.from_dict(payload)
    except Exception:
        pass
    try:
        from pymatgen.core import Lattice, Structure

        scale = float(payload.get("scale", 1.0) or 1.0)
        lattice = [[float(c) * scale for c in row] for row in payload["lattice"]]
        atoms = payload.get("atoms") or []
        species = [atom.get("name") for atom in atoms]
        coords = [atom.get("position") for atom in atoms]
        if not species or not coords:
            return None
        direct = str(payload.get("coordinates_type", "direct")).lower().startswith("d")
        occupancies = [float(atom.get("occupancy", 1.0)) for atom in atoms]
        if any(abs(value - 1.0) > 1e-8 for value in occupancies):
            return Structure(
                Lattice(lattice), species, coords,
                coords_are_cartesian=not direct,
                site_properties={"occupancy": occupancies},
            )
        return Structure(Lattice(lattice), species, coords, coords_are_cartesian=not direct)
    except Exception:
        return None


def _structure_from_path(path: Path) -> Any:
    """Parse a CIF, POSCAR/CONTCAR, or structure JSON file into pymatgen."""
    try:
        if path.suffix.lower() == ".json":
            return _structure_from_json(_load_json(path))
        from pymatgen.core import Structure

        return Structure.from_file(path)
    except Exception:
        return None


def _materialize_cif(
    document: dict[str, Any],
    structure: Any,
    paths: list[Path],
    structure_root: str | Path | None,
) -> str | None:
    """Ensure a canonical CIF exists for this AFLOW record and return its path.

    The CIF is stored as ``<structure_root>/<source_id>/<source_id>.cif``. An
    already parsed structure is written first; otherwise raw CIF,
    ``structure_relax*`` JSON, or POSCAR/CONTCAR files are converted. Failures
    return ``None`` so the record keeps a null ``structure_path``.
    """
    if not structure_root:
        return None
    source_id = document.get("auid") or document.get("_requested_id")
    if not source_id:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    if structure is not None and _write_cif(structure, target):
        return str(target)
    for path in paths:
        name = path.name.upper()
        if name.startswith(("POSCAR", "CONTCAR")) or "structure_relax" in path.name.lower():
            candidate = _structure_from_path(path)
            if candidate is not None and _write_cif(candidate, target):
                return str(target)
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
    return result


def enrich_aflow_document(
    document: dict[str, Any],
    downloaded_files: Iterable[str | Path] | None = None,
    structure_root: str | Path | None = None,
) -> dict[str, Any]:
    """Derive standard DFT values from AFLOW metadata and local files.

    Args:
        document (dict[str, Any]): Raw AFLOWLIB metadata document.
        downloaded_files (Iterable[str | Path] | None): Local files saved for the material.
        structure_root (str | Path | None): Base directory for canonical CIFs.

    Returns:
        dict[str, Any]: Enriched document ready for standard normalization.
    """
    enriched = dict(document)
    paths = [Path(path) for path in (downloaded_files or [])]
    structure = _parse_structure(paths)
    formula_reduced, elements, composition = _formula_parts(enriched, structure)
    geometry = enriched.get("geometry") or []
    if structure is not None:
        lattice = structure.lattice
        enriched["structure"] = structure.as_dict()
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
            enriched["lattice_a"], enriched["lattice_b"], enriched["lattice_c"] = lattice.a, lattice.b, lattice.c
            enriched["angle_alpha"], enriched["angle_beta"], enriched["angle_gamma"] = lattice.alpha, lattice.beta, lattice.gamma
        except Exception:
            pass
    enriched["formula_reduced"] = formula_reduced
    enriched["elements"] = elements
    enriched["composition_standard"] = composition
    enriched["element_count"] = len(elements) if elements else enriched.get("nspecies")
    enriched["possible_species"] = enriched.get("species")
    if enriched.get("volume_cell") and enriched.get("natoms"):
        enriched["density_atomic"] = float(enriched["natoms"]) / float(enriched["volume_cell"])
    enriched["chemical_system"] = "-".join(elements) if elements else None
    enriched["spacegroup_number"] = enriched.get("spacegroup_relax")
    enriched["point_group"] = enriched.get("point_group_Hermann_Mauguin")
    enriched["calculation_method"] = "DFT"
    raw_code = enriched.get("code")
    if isinstance(raw_code, str) and "." in raw_code:
        enriched["code"], enriched["code_version"] = raw_code.split(".", 1)
    else:
        enriched["code"], enriched["code_version"] = raw_code, None
    dft_type = enriched.get("dft_type")
    functional_text = ", ".join(str(value) for value in dft_type) if isinstance(dft_type, list) else dft_type
    enriched["functional"] = functional_text
    enriched["kpoint_mesh"] = enriched.get("kpoints_static") or enriched.get("kpoints_relax")
    enriched["is_metal"] = float(enriched["Egap"]) <= 0 if enriched.get("Egap") is not None else None
    gap_type = str(enriched.get("Egap_type") or "").lower()
    enriched["is_gap_direct"] = None if not gap_type else gap_type == "direct" or gap_type.endswith("-direct")
    enriched["fermi_level"] = enriched.get("Efermi")
    enriched["formation_energy"] = enriched.get("enthalpy_formation_cell")
    enriched["total_magnetization"] = enriched.get("spin_cell")
    enriched["magnetization_per_atom"] = enriched.get("spin_atom")
    spin_sites = enriched.get("spinD")
    enriched["magnetic_moments"] = spin_sites
    if isinstance(spin_sites, list):
        enriched["magnetic_site_count"] = sum(1 for value in spin_sites if value is not None and abs(float(value)) > 1e-8)
    enriched["youngs_modulus"] = enriched.get("ael_youngs_modulus_vrh")
    enriched["debye_temperature"] = enriched.get("ael_debye_temperature") or enriched.get("agl_debye")
    enriched["formation_energy_per_atom"] = enriched.get("enthalpy_formation_atom")
    enriched["volume"] = enriched.get("volume_cell")
    enriched.update(_parse_vasp_inputs(paths))
    enriched["formula_anonymous"] = structure.composition.anonymized_formula if structure is not None else None
    enriched["composition_reduced"] = None
    if composition:
        from pymatgen.core import Composition

        reduced = Composition(composition).reduced_composition
        enriched["composition_reduced"] = reduced.get_el_amt_dict()
        enriched["formula_reduced"] = reduced.reduced_formula
    enriched["is_magnetic"] = bool(enriched.get("spin_cell") not in (None, 0) or any(float(value) != 0 for value in (spin_sites or []))) if isinstance(spin_sites, list) else bool(enriched.get("spin_cell"))
    source_dates = enriched.get("aflowlib_date")
    last_date = source_dates[-1] if isinstance(source_dates, list) and source_dates else source_dates
    if last_date == []:
        last_date = None
    enriched["last_updated"] = last_date
    enriched["updated_at"] = last_date
    ael_path = _first_path(paths, ("ael.json",))
    agl_path = _first_path(paths, ("agl.json",))
    dielectric_path = _first_path(paths, ("dielectric", "epsilon", "born"))
    enriched["elastic_tensor_path"] = str(ael_path) if ael_path else None
    enriched["phonon_band_structure_path"] = None
    enriched["phonon_dos_path"] = None
    for property_path in (ael_path, agl_path):
        if property_path:
            property_data = _load_json(property_path)
            if property_data:
                for key, value in property_data.items():
                    if key not in enriched or enriched.get(key) is None:
                        enriched[key] = value
    enriched["downloaded_file_paths"] = [str(path) for path in paths]
    enriched["structure_path"] = _materialize_cif(enriched, structure, paths, structure_root)
    band_path = _first_path(paths, ("bandsdata", "eigenval", "edata.bands"))
    dos_path = _first_path(paths, ("dosdata", "doscar", "edata.static"))
    band_json_path = next((path for path in paths if "bandsdata.json" in path.name.lower()), None)
    dos_json_path = next((path for path in paths if "dosdata.json" in path.name.lower()), None)
    band_document = _load_json(band_json_path) if band_json_path else None
    dos_document = _load_json(dos_json_path) if dos_json_path else None
    enriched["bandstructure_summary"] = _compact_electronic_summary(band_document, "bandstructure")
    enriched["dos_summary"] = _compact_electronic_summary(dos_document, "dos")
    if enriched.get("fermi_level") is None:
        enriched["fermi_level"] = (band_document or {}).get("Efermi") or (dos_document or {}).get("Efermi")
    enriched["band_structure_path"] = str(band_path) if band_path else None
    enriched["dos_path"] = str(dos_path) if dos_path else None
    property_paths = {}
    for name, path in {
        "elasticity": ael_path,
        "thermal": agl_path,
        "dielectric": dielectric_path,
        "band_structure": band_path,
        "dos": dos_path,
    }.items():
        if path:
            property_paths[name] = str(path)
    enriched["property_paths"] = property_paths or None
    # Derive these after property JSON enrichment, not before it.
    enriched["bulk_modulus_vrh"] = enriched.get("ael_bulk_modulus_vrh")
    enriched["shear_modulus_vrh"] = enriched.get("ael_shear_modulus_vrh")
    enriched["debye_temperature"] = enriched.get("ael_debye_temperature")
    if enriched["debye_temperature"] is None:
        enriched["debye_temperature"] = enriched.get("agl_debye")
    return enriched


def normalize_aflow(
    document: dict[str, Any],
    downloaded_files: Iterable[str | Path] | None = None,
    structure_root: str | Path | None = None,
) -> dict[str, Any]:
    """Map enriched AFLOWLIB data into the unified DFT schema.

    Args:
        document (dict[str, Any]): Raw AFLOWLIB metadata document.
        downloaded_files (Iterable[str | Path] | None): Local material files.
        structure_root (str | Path | None): Base directory for canonical CIFs.

    Returns:
        dict[str, Any]: Standard record with every contract field present.
    """
    enriched = enrich_aflow_document(document, downloaded_files, structure_root)
    standard = load_yaml(STANDARD_PATH)
    mapping = load_yaml(MAPPING_PATH)
    rules = mapping.get("mapping", {})
    result: dict[str, Any] = {}
    for name in standard.get("fields", {}):
        rule = rules.get(name) or {}
        if "value" in rule:
            value = rule["value"]
        else:
            value = get_by_path(enriched, rule.get("field"))
        if value is None and "default" in rule:
            value = rule["default"]
        if rule.get("transform"):
            value = TRANSFORMS[rule["transform"]](value, enriched)
        result[name] = value
    consumed = {
        str(rule.get("field")).split(".")[0]
        for rule in rules.values()
        if isinstance(rule, dict) and rule.get("field") and "." not in str(rule["field"])
    }
    excluded = set(mapping.get("source_extra_exclude", []))
    result["source_extra"] = {
        key: value
        for key, value in enriched.items()
        if key not in consumed and key not in excluded and not key.startswith("_")
    } or None
    fill_derived_pairs(result)
    return result


__all__ = ["normalize_aflow", "enrich_aflow_document", "_parse_vasp_inputs"]
