"""OMat24 normalization: ASE LMDB rows to DFT standard record.

Each OMat24 row is an ASE ``Atoms`` object with a total energy (eV), forces
(eV/Angstrom) and stress (eV/Angstrom^3), plus metadata in ``row.data``. The
normalizer converts the atoms to a pymatgen structure, maps the structure,
energy and metadata onto the shared DFT contract, and materializes a canonical
CIF per record.

OMat24 energies use Meta's PBE/PBE+U reference scheme and are **not** directly
comparable to Materials Project energies (different pseudopotentials and
corrections).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"

SOURCE_URL = "https://huggingface.co/datasets/facebook/OMAT24"
SPG_PATTERN = re.compile(r"_spg(\d{1,3})_")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


@lru_cache(maxsize=256)
def _spacegroup_info(number: int) -> tuple[str | None, str | None, str | None]:
    """Return ``(symbol, crystal_system, point_group)`` for a space-group number."""
    try:
        from pymatgen.symmetry.groups import SpaceGroup

        group = SpaceGroup.from_int_number(int(number))
        system = getattr(group.crystal_system, "value", None) or str(group.crystal_system)
        system = str(system).replace("crystal_system.", "").lower()
        return group.symbol, system, str(group.point_group)
    except Exception:
        return None, None, None


def _spacegroup_from_sid(sid: Any) -> int | None:
    """Extract the space-group number embedded in an OMat24 ``sid``."""
    if not sid:
        return None
    match = SPG_PATTERN.search(str(sid))
    return int(match.group(1)) if match else None


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path."""
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
    if isinstance(value, bool) or float(value) != int(float(value)):
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


def _structure_from_atoms(atoms: Any) -> Any:
    """Convert an ASE ``Atoms`` object into a pymatgen structure."""
    if atoms is None:
        return None
    try:
        from pymatgen.io.ase import AseAtomsAdaptor

        return AseAtomsAdaptor.get_structure(atoms)
    except Exception:
        return None


def _to_list(value: Any) -> Any:
    """Convert numpy arrays into nested plain lists for JSON storage."""
    if value is None:
        return None
    try:
        return value.tolist()
    except AttributeError:
        return value


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


def _api_version(subset: str) -> str:
    """Return a release tag for the subdataset split."""
    if subset.startswith("val"):
        return "omat24-241220"
    if subset.startswith("train"):
        return "omat24-241018"
    if subset == "1m":
        return "omat24-251210"
    if subset.startswith("salex"):
        return "omat24-241018"
    return "omat24"


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_record(record: dict[str, Any], *, requested_id: str | None = None) -> dict[str, Any]:
    """Convert one OMat24 ASE row into the shared enriched document."""
    row = record.get("row")
    data = record.get("data") or {}
    atoms = record.get("atoms")
    subset = record.get("subset") or ""
    structure = _structure_from_atoms(atoms)

    elements = None
    if structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)
    atom_count = len(atoms) if atoms is not None else (len(structure) if structure is not None else None)

    sid = data.get("sid") or f"{subset}:{record.get('row_id')}"
    sg_number = _spacegroup_from_sid(sid)
    sg_symbol = sg_system = sg_point = None
    if sg_number:
        sg_symbol, sg_system, sg_point = _spacegroup_info(sg_number)

    energy = getattr(row, "energy", None) if row is not None else None
    forces = _to_list(getattr(row, "forces", None)) if row is not None else None
    stress = _to_list(getattr(row, "stress", None)) if row is not None else None

    enriched: dict[str, Any] = {
        "_requested_id": requested_id,
        "source_id": sid,
        "source_url": SOURCE_URL,
        "mechanism": "ase_lmdb",
        "formula": atoms.get_chemical_formula() if atoms is not None else None,
        "chemical_system": "-".join(elements) if elements else None,
        "elements": elements,
        "element_count": len(elements) if elements else None,
        "structure": None,
        "atom_count": atom_count,
        "crystal_system": sg_system,
        "spacegroup_number": sg_number,
        "spacegroup_symbol": sg_symbol,
        "point_group": sg_point,
        "calculation_method": "DFT",
        "functional": "PBE/PBE+U",
        "total_energy": energy,
        "energy_per_atom": None,
        "api_version": _api_version(subset),
        # retained source-specific values
        "subset": subset,
        "row_id": record.get("row_id"),
        "forces": forces,
        "stress": stress,
        "sid": data.get("sid"),
        "calc_id": data.get("calc_id"),
        "task_type": data.get("task_type"),
        "composition_reduced": data.get("composition_reduced"),
        "prototype_label": data.get("prototype_label"),
        "prototype_error": data.get("prototype_error"),
        "energy_corrected_mp2020": data.get("energy_corrected_mp2020"),
        "energy_correction_uncertainty_mp2020": data.get("energy_correction_uncertainty_mp2020"),
        "energy_adjustments_mp2020": data.get("energy_adjustments_mp2020"),
        "correction_warnings": data.get("correction_warnings"),
        "parent_id": data.get("parent_id"),
        "parent_prototype_label": data.get("parent_prototype_label"),
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


def normalize_omat24_record(
    record: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one OMat24 ASE row into a complete DFT standard record."""
    enriched = enrich_record(record, requested_id=requested_id or (record.get("data") or {}).get("sid"))
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_record",
    "normalize_omat24_record",
]
