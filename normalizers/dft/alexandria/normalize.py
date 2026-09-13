"""Alexandria (AMD) normalization: raw entries to DFT standard record.

Two raw shapes are supported and converge on the same standard record:

- Bulk archives yield pymatgen ``ComputedStructureEntry`` dictionaries with a
  ``data`` block and an inline ``structure``.
- The OPTIMADE API yields records whose attributes include standard OPTIMADE
  fields plus ``_alexandria_*`` extension properties.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path such as ``structure.lattice.a``."""
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


def _to_int(value: Any, _: dict[str, Any]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or float(value) != int(value):
        raise ValueError("expected an integral number")
    return int(value)


def _to_bool(value: Any, _: dict[str, Any]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y"}:
            return True
        if token in {"false", "0", "no", "n"}:
            return False
    elif isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ValueError("expected an explicit boolean value")


def _normalize_elements(value: Any, _: dict[str, Any]) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("elements must be a list of element symbols")
    return sorted(set(value))


def _count_items(value: Any, _: dict[str, Any]) -> int | None:
    return len(_normalize_elements(value, _)) if value is not None else None


def _normalize_formula(value: Any, _: dict[str, Any]) -> str | None:
    return str(value).strip() if value is not None else None


def _normalize_chemical_system(value: Any, _: dict[str, Any]) -> str | None:
    if not value:
        return None
    return "-".join(sorted(str(value).replace("_", "-").split("-")))


def _lowercase(value: Any, _: dict[str, Any]) -> str | None:
    return None if value is None else str(value).strip().lower()


def _parse_decomposition(value: Any, _: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Convert an Alexandria decomposition string into standard products."""
    if value is None:
        return None
    if isinstance(value, list):
        parts = [str(item) for item in value]
    else:
        parts = [part for part in str(value).split() if part]
    if not parts:
        return None
    return [{"material_id": None, "formula": part, "amount": None} for part in parts]


def _now(_: Any, __: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TRANSFORMS = {
    "requested_id": _requested_id,
    "to_int": _to_int,
    "to_bool": _to_bool,
    "normalize_elements": _normalize_elements,
    "count_items": _count_items,
    "normalize_formula": _normalize_formula,
    "normalize_chemical_system": _normalize_chemical_system,
    "lowercase": _lowercase,
    "parse_decomposition": _parse_decomposition,
    "now": _now,
}


# ---------------------------------------------------------------------------
# Structure helpers
# ---------------------------------------------------------------------------

def _safe_name(value: Any) -> str:
    """Return a filesystem-safe name for a material identifier."""
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


def _structure_from_entry(entry: dict[str, Any]) -> Any:
    """Parse the inline pymatgen structure of a bulk entry."""
    payload = entry.get("structure")
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_dict(payload)
    except Exception:
        return None


def _apply_site_properties(structure: Any, magmoms: Any, charges: Any, forces: Any) -> None:
    """Attach site-resolved magmom/charge/forces when lengths are consistent."""
    try:
        count = len(structure)
    except TypeError:
        return
    for name, values in (("magmom", magmoms), ("charge", charges), ("forces", forces)):
        if isinstance(values, list) and len(values) == count:
            try:
                structure.add_site_property(name, values)
            except Exception:
                pass


def _structure_from_optimade(document: dict[str, Any]) -> Any:
    """Rebuild a pymatgen structure from OPTIMADE geometry attributes."""
    lattice = document.get("lattice_vectors")
    positions = document.get("cartesian_site_positions")
    species = document.get("species_at_sites")
    if not (lattice and positions and species):
        return None
    try:
        from pymatgen.core import Lattice, Structure

        structure = Structure(
            Lattice(lattice), list(species), positions, coords_are_cartesian=True,
        )
    except Exception:
        return None
    _apply_site_properties(
        structure,
        document.get("_alexandria_magnetic_moments"),
        document.get("_alexandria_charges"),
        document.get("_alexandria_forces"),
    )
    return structure


def _spacegroup_info(number: Any) -> tuple[str | None, str | None]:
    """Return ``(crystal_system, symbol)`` for an international space-group number."""
    if number is None:
        return None, None
    try:
        from pymatgen.symmetry.groups import SpaceGroup

        group = SpaceGroup.from_int_number(int(number))
        system = getattr(group.crystal_system, "value", None) or str(group.crystal_system)
        return str(system).replace("crystal_system.", "").lower(), group.symbol
    except Exception:
        return None, None


def _gap_fields(band_gap: Any, direct_gap: Any) -> tuple[float | None, bool | None, bool | None, str | None]:
    """Return ``(band_gap, is_metal, is_gap_direct, band_gap_type)``."""
    if band_gap is None:
        return None, None, None, None
    gap = float(band_gap)
    if gap <= 0:
        return gap, True, False, None
    is_direct = direct_gap is not None and math.isclose(float(direct_gap), gap, rel_tol=1e-6, abs_tol=1e-6)
    return gap, False, is_direct, "direct" if is_direct else "indirect"


def _count_magnetic_sites(moments: Any) -> int | None:
    if not isinstance(moments, list):
        return None
    return sum(1 for value in moments if value is not None and abs(float(value)) > 1e-8)


def _composition_fields(structure: Any) -> dict[str, Any]:
    """Derive reduced formula, anonymous formula, and reduced composition."""
    if structure is None:
        return {}
    try:
        composition = structure.composition
        return {
            "formula_reduced": composition.reduced_formula,
            "formula_anonymous": composition.anonymized_formula,
            "composition_reduced": composition.reduced_composition.get_el_amt_dict(),
        }
    except Exception:
        return {}


def _lattice_fields(structure: Any) -> dict[str, Any]:
    """Derive lattice parameters and density from a pymatgen structure."""
    if structure is None:
        return {}
    lattice = structure.lattice
    fields: dict[str, Any] = {
        "lattice_a": lattice.a,
        "lattice_b": lattice.b,
        "lattice_c": lattice.c,
        "angle_alpha": lattice.alpha,
        "angle_beta": lattice.beta,
        "angle_gamma": lattice.gamma,
        "volume": lattice.volume,
    }
    try:
        fields["density"] = structure.density
    except Exception:
        pass
    try:
        if lattice.volume:
            fields["density_atomic"] = len(structure) / lattice.volume
    except Exception:
        pass
    return fields


def _materialize_cif(source_id: Any, structure: Any, structure_root: str | Path | None) -> str | None:
    """Ensure a canonical CIF exists and return its path, or ``None`` on failure."""
    if not structure_root or not source_id or structure is None:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    return str(target) if _write_cif(structure, target) else None


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def _base_fields(dataset: str, dataset_url: str | None, functional: str | None,
                 dimensionality: int | None) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "dataset_url": dataset_url,
        "dimensionality": dimensionality,
        "calculation_method": "DFT",
        "functional": functional,
        "api_version": None,
    }


def enrich_entry(document: dict[str, Any], dataset: str, *, dataset_url: str | None = None,
                 functional: str | None = None, dimensionality: int | None = None,
                 requested_id: str | None = None) -> dict[str, Any]:
    """Convert one bulk pymatgen entry into the shared enriched document."""
    entry = document
    data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
    structure = _structure_from_entry(entry)
    mat_id = data.get("mat_id") or entry.get("entry_id") or requested_id
    source_id = f"{dataset}:{mat_id}" if mat_id else None
    elements = data.get("elements")
    if not elements and structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)
    atom_count = data.get("nsites")
    if atom_count is None and structure is not None:
        atom_count = len(structure)
    total_energy = data.get("energy_total")
    if total_energy is None:
        total_energy = entry.get("energy")
    e_form = data.get("e_form")
    total_mag = data.get("total_mag")
    magmom = None
    if structure is not None:
        try:
            magmom = [site.properties.get("magmom") for site in structure]
        except Exception:
            magmom = None
    band_gap, is_metal, is_gap_direct, band_gap_type = _gap_fields(data.get("band_gap_ind"), data.get("band_gap_dir"))
    sg_number = data.get("spg")
    crystal_system, symbol = _spacegroup_info(sg_number)
    enriched: dict[str, Any] = {
        **_base_fields(dataset, dataset_url, functional, dimensionality),
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": dataset_url,
        "mat_id": mat_id,
        "formula": data.get("formula"),
        "elements": elements,
        "chemical_system": "-".join(sorted(elements)) if elements else None,
        "atom_count": atom_count,
        "structure": None,
        "spacegroup_number": sg_number,
        "spacegroup_symbol": symbol,
        "crystal_system": crystal_system,
        "total_energy": total_energy,
        "formation_energy_per_atom": e_form,
        "formation_energy": float(e_form) * float(atom_count) if e_form is not None and atom_count else None,
        "energy_above_hull": data.get("e_above_hull"),
        "band_gap": band_gap,
        "band_gap_type": band_gap_type,
        "is_metal": is_metal,
        "is_gap_direct": is_gap_direct,
        "total_magnetization": total_mag,
        "magnetic_moments": magmom,
        "magnetic_site_count": _count_magnetic_sites(magmom),
        "is_magnetic": (abs(float(total_mag)) > 1e-8) if total_mag is not None else None,
        "decomposes_to": data.get("decomposition"),
        "dos_ef": data.get("dos_ef"),
        "energy_corrected": data.get("energy_corrected"),
        "phase_separation_energy": data.get("e_phase_separation"),
        "prototype_id": data.get("prototype_id"),
        "location": data.get("location"),
        "run_timestamp": _timestamp_string(data.get("run_timestamp")),
        "last_updated": _timestamp_string(data.get("run_timestamp")),
        "api_version": f"alexandria-bulk:{dataset}",
    }
    enriched.update(_lattice_fields(structure))
    enriched.update(_composition_fields(structure))
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


def enrich_optimade(document: dict[str, Any], dataset: str, *, functional: str | None = None,
                    dimensionality: int | None = None, requested_id: str | None = None) -> dict[str, Any]:
    """Convert one OPTIMADE structure record into the shared enriched document."""
    structure = _structure_from_optimade(document)
    mat_id = document.get("id")
    source_id = f"{dataset}:{mat_id}" if mat_id else None
    elements = document.get("elements")
    if not elements and structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)
    atom_count = document.get("nsites")
    if atom_count is None and structure is not None:
        atom_count = len(structure)
    total_mag = document.get("_alexandria_magnetization")
    magmom = document.get("_alexandria_magnetic_moments")
    band_gap, is_metal, is_gap_direct, band_gap_type = _gap_fields(
        document.get("_alexandria_band_gap"), document.get("_alexandria_band_gap_direct"),
    )
    e_form = document.get("_alexandria_formation_energy_per_atom")
    sg_number = document.get("_alexandria_space_group")
    crystal_system, symbol = _spacegroup_info(sg_number)
    enriched: dict[str, Any] = {
        **_base_fields(dataset, None, functional, dimensionality),
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": None,
        "mat_id": mat_id,
        "formula": document.get("chemical_formula_descriptive"),
        "formula_reduced": document.get("chemical_formula_reduced"),
        "formula_anonymous": document.get("chemical_formula_anonymous"),
        "elements": elements,
        "chemical_system": "-".join(sorted(elements)) if elements else None,
        "atom_count": atom_count,
        "structure": None,
        "spacegroup_number": sg_number,
        "spacegroup_symbol": symbol,
        "crystal_system": crystal_system,
        "total_energy": document.get("_alexandria_energy"),
        "formation_energy_per_atom": e_form,
        "formation_energy": float(e_form) * float(atom_count) if e_form is not None and atom_count else None,
        "energy_above_hull": document.get("_alexandria_hull_distance"),
        "band_gap": band_gap,
        "band_gap_type": band_gap_type,
        "is_metal": is_metal,
        "is_gap_direct": is_gap_direct,
        "total_magnetization": total_mag,
        "magnetic_moments": magmom,
        "magnetic_site_count": _count_magnetic_sites(magmom),
        "is_magnetic": (abs(float(total_mag)) > 1e-8) if total_mag is not None else None,
        "decomposes_to": document.get("_alexandria_decomposition"),
        "dos_ef": document.get("_alexandria_dos_ef"),
        "energy_corrected": document.get("_alexandria_energy_corrected"),
        "phase_separation_energy": document.get("_alexandria_phase_separation_energy"),
        "stress": document.get("_alexandria_stress_tensor"),
        "functional": document.get("_alexandria_xc_functional") or functional,
        "last_updated": document.get("last_modified"),
        "api_version": "optimade-1.1.0",
    }
    enriched.update(_lattice_fields(structure))
    composition = _composition_fields(structure)
    for key, value in composition.items():
        enriched.setdefault(key, value)
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


def _timestamp_string(value: Any) -> str | None:
    """Read a pymatgen datetime dict or plain string into an ISO-ish string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("string")
    return str(value)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _apply_mapping(enriched: dict[str, Any], structure_root: str | Path | None,
                   raw_path: str | None = None) -> dict[str, Any]:
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
        if key not in consumed and key not in excluded and not key.startswith("_") and key != "structure"
    } or None
    if structure_root and enriched.get("structure") is not None:
        result["structure_path"] = _materialize_cif(enriched.get("source_id"), _structure_from_enriched(enriched), structure_root)
    if raw_path:
        result["property_paths"] = {"raw": raw_path}
    fill_derived_pairs(result)
    return result


def _structure_from_enriched(enriched: dict[str, Any]) -> Any:
    payload = enriched.get("structure")
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_dict(payload)
    except Exception:
        return None


def normalize_alexandria_entry(
    entry: dict[str, Any],
    *,
    dataset: str,
    dataset_url: str | None = None,
    functional: str | None = None,
    dimensionality: int | None = None,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one bulk pymatgen entry into a complete DFT standard record."""
    enriched = enrich_entry(
        entry, dataset, dataset_url=dataset_url, functional=functional,
        dimensionality=dimensionality, requested_id=requested_id,
    )
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


def normalize_alexandria_optimade(
    document: dict[str, Any],
    *,
    dataset: str = "pbesol",
    functional: str | None = None,
    dimensionality: int | None = None,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one OPTIMADE structure record into a complete DFT standard record."""
    enriched = enrich_optimade(
        document, dataset, functional=functional, dimensionality=dimensionality,
        requested_id=requested_id,
    )
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_entry",
    "enrich_optimade",
    "normalize_alexandria_entry",
    "normalize_alexandria_optimade",
]
