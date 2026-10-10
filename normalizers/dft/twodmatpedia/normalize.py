"""2DMatPedia normalization: raw JSON Lines entries to DFT standard record.

Each 2DMatPedia entry is one JSON object (one database line) carrying
composition, a pymatgen ``structure`` dictionary, band-structure scalars, a
thermodynamic block, and a space-group block. The normalizer maps those onto
the shared DFT contract and materializes a canonical CIF per record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs
from sources.dft.twodmatpedia.download import BASE_URL

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"

MAGNETIC_TOLERANCE = 1e-3
API_VERSION = "2dmatpedia-2019"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path such as ``spacegroup.number``."""
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
    normalized = _normalize_elements(value, _)
    return len(normalized) if normalized is not None else None


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


def _structure_from_document(document: dict[str, Any]) -> Any:
    """Parse the inline pymatgen structure of one entry."""
    payload = document.get("structure")
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_dict(payload)
    except Exception:
        return None


def _lattice_fields(structure: Any) -> dict[str, Any]:
    """Derive lattice parameters, density, and atomic density from a structure."""
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


def _materialize_cif(source_id: Any, structure: Any, structure_root: str | Path | None) -> str | None:
    """Ensure a canonical CIF exists and return its path, or ``None`` on failure."""
    if not structure_root or not source_id or structure is None:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    return str(target) if _write_cif(structure, target) else None


def _date_string(value: Any) -> str | None:
    """Read a Mongo ``$date`` dict or plain string into a string."""
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("$date", "date", "string"):
            if key in value:
                return str(value[key])
        return None
    return str(value)


def _gap_fields(band_gap: Any, is_gap_direct: Any) -> tuple[float | None, str | None]:
    """Return ``(band_gap_type,)`` classification from a gap and its directness."""
    if band_gap is None:
        return None, None
    gap = float(band_gap)
    if gap <= 0:
        return gap, None
    if is_gap_direct is None:
        return gap, None
    return gap, "direct" if is_gap_direct else "indirect"


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_entry(document: dict[str, Any], *, requested_id: str | None = None) -> dict[str, Any]:
    """Convert one raw 2DMatPedia entry into the shared enriched document."""
    structure = _structure_from_document(document)
    material_id = document.get("material_id")
    bandstructure = document.get("bandstructure") or {}
    thermo = document.get("thermo") or {}
    magnetism = document.get("magnetism") or {}
    spacegroup = document.get("spacegroup") or {}
    calc_settings = document.get("calc_settings") or {}

    elements = document.get("elements")
    if not elements and structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)
    atom_count = len(structure) if structure is not None else None

    band_gap = document.get("bandgap")
    if band_gap is None:
        band_gap = bandstructure.get("bandgap")
    is_gap_direct = bandstructure.get("is_gap_direct")
    gap_type = _gap_fields(band_gap, is_gap_direct)[1]

    total_mag = document.get("total_magnetization")
    if total_mag is None:
        total_mag = magnetism.get("total_magnetization")

    enriched: dict[str, Any] = {
        "_requested_id": requested_id,
        "source_id": material_id,
        "source_url": BASE_URL,
        "mechanism": "bulk_jsonl",
        "formula": document.get("formula_pretty"),
        "formula_anonymous": document.get("formula_anonymous"),
        "chemical_system": document.get("chemsys"),
        "elements": elements,
        "element_count": document.get("nelements") or (len(elements) if elements else None),
        "structure": None,
        "atom_count": atom_count,
        "crystal_system": spacegroup.get("crystal_system"),
        "spacegroup_number": document.get("sg_number") or spacegroup.get("number"),
        "spacegroup_symbol": document.get("sg_symbol") or spacegroup.get("symbol"),
        "point_group": spacegroup.get("point_group"),
        "calculation_method": "DFT",
        "functional": "PBE",
        "total_energy": thermo.get("energy"),
        "energy_per_atom": thermo.get("energy_per_atom") or document.get("energy_per_atom"),
        "energy_above_hull": document.get("decomposition_energy"),
        "band_gap": band_gap,
        "band_gap_type": gap_type,
        "is_metal": bandstructure.get("is_metal"),
        "is_gap_direct": is_gap_direct,
        "cbm": bandstructure.get("cbm"),
        "vbm": bandstructure.get("vbm"),
        "total_magnetization": total_mag,
        "magnetization_per_atom": None,
        "is_magnetic": (abs(float(total_mag)) > MAGNETIC_TOLERANCE) if total_mag is not None else None,
        "last_updated": _date_string(document.get("created_at")),
        "api_version": API_VERSION,
        # retained source-specific values
        "exfoliation_energy_per_atom": document.get("exfoliation_energy_per_atom"),
        "energy_vdw_per_atom": document.get("energy_vdw_per_atom"),
        "discovery_process": document.get("discovery_process"),
        "relative_id": document.get("relative_id"),
        "parent_source_id": document.get("source_id"),
        "formula_reduced_abc": document.get("formula_reduced_abc"),
        "is_hubbard": calc_settings.get("is_hubbard"),
        "hubbards": calc_settings.get("hubbards"),
        "calc_settings": calc_settings or None,
        "thermo": thermo or None,
        "bandstructure": bandstructure or None,
        "magnetism": magnetism or None,
    }
    enriched.update(_lattice_fields(structure))
    enriched.update(_composition_fields(structure))
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _structure_from_enriched(enriched: dict[str, Any]) -> Any:
    payload = enriched.get("structure")
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_dict(payload)
    except Exception:
        return None


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
            enriched.get("source_id"), _structure_from_enriched(enriched), structure_root,
        )
    if raw_path:
        result["property_paths"] = {"raw": raw_path}
    fill_derived_pairs(result)
    return result


def normalize_2dmatpedia_entry(
    document: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one 2DMatPedia entry into a complete DFT standard record."""
    enriched = enrich_entry(document, requested_id=requested_id or document.get("material_id"))
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_entry",
    "normalize_2dmatpedia_entry",
]
