"""Materials Cloud normalization: OPTIMADE records to DFT standard record.

The primary raw shape is an OPTIMADE structure record from
``https://optimade.materialscloud.org/main/<prefix>/v1``. Its attributes carry
standard OPTIMADE geometry fields plus ``_mcloud_*`` extensions (source
identifiers, total energy, magnetization, cell volume).

A secondary helper accepts an already-parsed pymatgen structure, so bulk CIF
artifacts such as ``MC3D-cifs.zip`` can reuse the same mapping when needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"

# Magnetization below this (in Bohr magneton) is treated as numerical noise.
MAGNETIC_TOLERANCE = 1e-3


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


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


def _structure_from_optimade(document: dict[str, Any]) -> Any:
    """Rebuild a pymatgen structure from OPTIMADE geometry attributes."""
    lattice = document.get("lattice_vectors")
    positions = document.get("cartesian_site_positions")
    species = document.get("species_at_sites")
    if not (lattice and positions and species):
        return None
    try:
        from pymatgen.core import Lattice, Structure

        return Structure(Lattice(lattice), list(species), positions, coords_are_cartesian=True)
    except Exception:
        return None


def _spacegroup_from_structure(structure: Any) -> tuple[int | None, str | None, str | None]:
    """Return ``(number, symbol, crystal_system)`` for a pymatgen structure.

    Uses spglib through pymatgen; returns ``(None, None, None)`` if the symmetry
    library is unavailable or the analysis fails.
    """
    if structure is None:
        return None, None, None
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        analyzer = SpacegroupAnalyzer(structure, symprec=0.1)
        number = int(analyzer.get_space_group_number())
        symbol = str(analyzer.get_space_group_symbol())
        system = getattr(analyzer.get_crystal_system(), "value", None) or str(analyzer.get_crystal_system())
        return number, symbol, str(system).replace("crystal_system.", "").lower()
    except Exception:
        return None, None, None


def _electronic_fields(band_gap: Any) -> tuple[float | None, bool | None, bool | None, str | None]:
    """Return ``(band_gap, is_metal, is_gap_direct, band_gap_type)``.

    Materials Cloud exposes a single gap value without a direct/indirect flag,
    so ``is_gap_direct`` and ``band_gap_type`` stay ``None``.
    """
    if band_gap is None:
        return None, None, None, None
    gap = float(band_gap)
    if gap <= 0:
        return gap, True, False, "metal"
    return gap, False, None, None


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

def _base_fields(dataset: str, discover_url: str | None, functional: str | None,
                 dimensionality: int | None) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "discover_url": discover_url,
        "dimensionality": dimensionality,
        "calculation_method": "DFT",
        "functional": functional,
    }


def enrich_optimade(document: dict[str, Any], dataset: str, *, discover_url: str | None = None,
                    functional: str | None = None, dimensionality: int | None = None,
                    requested_id: str | None = None, derive_symmetry: bool = True) -> dict[str, Any]:
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
    total_mag = document.get("_mcloud_total_magnetization")
    band_gap, is_metal, is_gap_direct, band_gap_type = _electronic_fields(document.get("_mcloud_band_gap"))
    sg_number, sg_symbol, crystal_system = (
        _spacegroup_from_structure(structure) if derive_symmetry else (None, None, None)
    )
    enriched: dict[str, Any] = {
        **_base_fields(dataset, discover_url, functional, dimensionality),
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": discover_url,
        "mat_id": mat_id,
        "formula": document.get("chemical_formula_descriptive"),
        "formula_reduced": document.get("chemical_formula_reduced"),
        "formula_anonymous": document.get("chemical_formula_anonymous"),
        "elements": elements,
        "chemical_system": "-".join(sorted(elements)) if elements else None,
        "atom_count": atom_count,
        "structure": None,
        "spacegroup_number": sg_number,
        "spacegroup_symbol": sg_symbol,
        "crystal_system": crystal_system,
        "total_energy": document.get("_mcloud_total_energy"),
        "band_gap": band_gap,
        "band_gap_type": band_gap_type,
        "is_metal": is_metal,
        "is_gap_direct": is_gap_direct,
        "total_magnetization": total_mag,
        "magnetic_moments": None,
        "magnetic_site_count": None,
        "is_magnetic": (abs(float(total_mag)) > MAGNETIC_TOLERANCE) if total_mag is not None else None,
        "last_updated": document.get("last_modified"),
        "api_version": "optimade-1.2.0",
        "mc3d_id": document.get("_mcloud_mc3d_id"),
        "source_db": document.get("_mcloud_source_db"),
        "source_db_id": document.get("_mcloud_source_db_id"),
        "cell_volume": document.get("_mcloud_cell_volume"),
        "absolute_magnetization": document.get("_mcloud_absolute_magnetization"),
        "ctime": document.get("_mcloud_ctime"),
    }
    enriched.update(_lattice_fields(structure))
    composition = _composition_fields(structure)
    for key, value in composition.items():
        enriched.setdefault(key, value)
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


def enrich_structure(structure: Any, dataset: str, entry_id: str, *, discover_url: str | None = None,
                     functional: str | None = None, dimensionality: int | None = None,
                     requested_id: str | None = None) -> dict[str, Any]:
    """Build an enriched document from an already-parsed pymatgen structure."""
    source_id = f"{dataset}:{entry_id}" if entry_id else None
    elements = sorted(str(element) for element in structure.composition.elements) if structure else None
    sg_number, sg_symbol, crystal_system = _spacegroup_from_structure(structure)
    enriched: dict[str, Any] = {
        **_base_fields(dataset, discover_url, functional, dimensionality),
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": discover_url,
        "mat_id": entry_id,
        "formula": structure.composition.formula if structure else None,
        "elements": elements,
        "chemical_system": "-".join(elements) if elements else None,
        "atom_count": len(structure) if structure else None,
        "structure": None,
        "spacegroup_number": sg_number,
        "spacegroup_symbol": sg_symbol,
        "crystal_system": crystal_system,
        "total_energy": None,
        "band_gap": None,
        "band_gap_type": None,
        "is_metal": None,
        "is_gap_direct": None,
        "total_magnetization": None,
        "magnetic_moments": None,
        "magnetic_site_count": None,
        "is_magnetic": None,
        "last_updated": None,
        "api_version": "materialscloud-cif",
    }
    enriched.update(_lattice_fields(structure))
    enriched.update(_composition_fields(structure))
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _apply_mapping(enriched: dict[str, Any], structure_root: str | Path | None,
                   raw_path: str | None = None) -> dict[str, Any]:
    standard = _load_yaml_cached(str(STANDARD_PATH))
    mapping = _load_yaml_cached(str(MAPPING_PATH))
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
        result["structure_path"] = _materialize_cif(
            enriched.get("source_id"), _structure_from_enriched(enriched), structure_root
        )
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


def normalize_materialscloud_optimade(
    document: dict[str, Any],
    *,
    dataset: str,
    discover_url: str | None = None,
    functional: str | None = None,
    dimensionality: int | None = None,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
    derive_symmetry: bool = True,
) -> dict[str, Any]:
    """Normalize one OPTIMADE structure record into a complete DFT standard record."""
    enriched = enrich_optimade(
        document, dataset, discover_url=discover_url, functional=functional,
        dimensionality=dimensionality, requested_id=requested_id, derive_symmetry=derive_symmetry,
    )
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


def normalize_materialscloud_structure(
    structure: Any,
    *,
    dataset: str,
    entry_id: str,
    discover_url: str | None = None,
    functional: str | None = None,
    dimensionality: int | None = None,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize an already-parsed pymatgen structure into a DFT standard record."""
    enriched = enrich_structure(
        structure, dataset, entry_id, discover_url=discover_url, functional=functional,
        dimensionality=dimensionality, requested_id=requested_id,
    )
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_optimade",
    "enrich_structure",
    "normalize_materialscloud_optimade",
    "normalize_materialscloud_structure",
]
