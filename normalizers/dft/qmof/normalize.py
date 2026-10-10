"""QMOF normalization: joined property row and relaxed CIF to DFT record.

Each QMOF record couples one ``qmof.csv`` property row with the relaxed
structure CIF archived per ``qmof_id``. The normalizer parses the CIF with
pymatgen, reads the DFT properties from the row, maps everything onto the shared
DFT contract, and materializes a canonical CIF per record.
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

MAGNETIC_TOLERANCE = 1e-3
API_VERSION = "qmof-release"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path such as ``info.symmetry.spacegroup``."""
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
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if float(value) != int(float(value)):
        raise ValueError("expected an integral number")
    return int(float(value))


def _to_bool(value: Any, _: dict[str, Any]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y"}:
            return True
        if token in {"false", "0", "no", "n", ""}:
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
# Value and structure helpers
# ---------------------------------------------------------------------------

def _num(value: Any) -> float | None:
    """Convert a CSV string to a float, returning ``None`` for blanks."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if text == "" or text.lower() in {"none", "nan", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    return None


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


def _structure_from_cif(cif: Any) -> Any:
    """Parse a CIF string into a pymatgen structure."""
    if not cif:
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_str(cif, fmt="cif")
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


def _gap_type(band_gap: Any, is_gap_direct: Any) -> str | None:
    """Return a coarse gap classification from the gap value and directness."""
    if band_gap is None:
        return None
    if float(band_gap) <= 0:
        return None
    if is_gap_direct is None:
        return None
    return "direct" if is_gap_direct else "indirect"


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_record(record: dict[str, Any], *, requested_id: str | None = None) -> dict[str, Any]:
    """Convert one joined QMOF record into the shared enriched document."""
    row = record.get("row") or {}
    structure = _structure_from_cif(record.get("cif"))
    qmof_id = record.get("qmof_id")

    elements = None
    if structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)
    atom_count = _int(row.get("info.natoms"))
    if atom_count is None and structure is not None:
        atom_count = len(structure)

    band_gap = _num(row.get("outputs.pbe.bandgap"))
    is_gap_direct = _bool(row.get("outputs.pbe.directgap"))
    total_mag = _num(row.get("outputs.pbe.net_magmom"))
    spacegroup_number = _int(row.get("info.symmetry.spacegroup_number"))

    enriched: dict[str, Any] = {
        "_requested_id": requested_id,
        "source_id": qmof_id,
        "source_url": "https://materialsproject.org/mofs",
        "mechanism": "hf_csv_zip",
        "name": row.get("name"),
        "formula": row.get("info.formula"),
        "formula_reduced": row.get("info.formula_reduced"),
        "chemical_system": "-".join(elements) if elements else None,
        "elements": elements,
        "element_count": len(elements) if elements else None,
        "structure": None,
        "atom_count": atom_count,
        "crystal_system": row.get("info.symmetry.spacegroup_crystal"),
        "spacegroup_number": spacegroup_number,
        "spacegroup_symbol": row.get("info.symmetry.spacegroup"),
        "point_group": row.get("info.symmetry.pointgroup"),
        "calculation_method": "DFT",
        "functional": row.get("inputs.pbe.theory"),
        "energy_cutoff": _num(row.get("inputs.pbe.encut")),
        "total_energy": _num(row.get("outputs.pbe.energy_total")),
        "energy_per_atom": None,
        "band_gap": band_gap,
        "band_gap_type": _gap_type(band_gap, is_gap_direct),
        "is_metal": None if band_gap is None else band_gap <= 0,
        "is_gap_direct": is_gap_direct,
        "cbm": _num(row.get("outputs.pbe.cbm")),
        "vbm": _num(row.get("outputs.pbe.vbm")),
        "total_magnetization": total_mag,
        "magnetization_per_atom": None,
        "is_magnetic": (abs(total_mag) > MAGNETIC_TOLERANCE) if total_mag is not None else None,
        "api_version": API_VERSION,
        # retained source-specific values
        "info_source": row.get("info.source"),
        "doi": row.get("info.doi"),
        "synthesized": _bool(row.get("info.synthesized")),
        "pld": _num(row.get("info.pld")),
        "lcd": _num(row.get("info.lcd")),
        "mofid": {
            "mofid": row.get("info.mofid.mofid"),
            "mofkey": row.get("info.mofid.mofkey"),
            "topology": row.get("info.mofid.topology"),
            "smiles": row.get("info.mofid.smiles"),
        },
        "energy_vdw": _num(row.get("outputs.pbe.energy_vdw")),
        "energy_elec": _num(row.get("outputs.pbe.energy_elec")),
        "hse06_bandgap": _num(row.get("outputs.hse06.bandgap")),
        "hle17_bandgap": _num(row.get("outputs.hle17.bandgap")),
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


def normalize_qmof_record(
    record: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one joined QMOF record into a complete DFT standard record."""
    enriched = enrich_record(record, requested_id=requested_id or record.get("qmof_id"))
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_record",
    "normalize_qmof_record",
]
