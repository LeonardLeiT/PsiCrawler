"""Materials Project normalization: raw summary document to DFT standard record."""

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
    """Read a dotted or indexed path such as ``symmetry.number`` or ``thermo.0``."""
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


def _build_mp_url(value: Any, _: dict[str, Any]) -> str | None:
    return f"https://materialsproject.org/materials/{value}/" if value else None


def _atomic_number_density(_: Any, document: dict[str, Any]) -> float | None:
    count, volume = document.get("nsites"), document.get("volume")
    if count is None or volume is None:
        return None
    if float(volume) <= 0 or float(count) <= 0:
        raise ValueError("site count and volume must be positive")
    return float(count) / float(volume)


def _youngs_modulus(_: Any, document: dict[str, Any]) -> float | None:
    """Derive Young's modulus from VRH bulk and shear moduli: E = 9KG/(3K+G)."""
    bulk = get_by_path(document, "bulk_modulus.vrh")
    shear = get_by_path(document, "shear_modulus.vrh")
    if bulk is None or shear is None:
        return None
    denominator = 3.0 * float(bulk) + float(shear)
    if denominator == 0:
        return None
    return 9.0 * float(bulk) * float(shear) / denominator


def _to_int(value: Any, _: dict[str, Any]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or float(value) != int(value):
        raise ValueError("expected an integral number")
    return int(value)


def _to_bool(value: Any, _: dict[str, Any]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y"}:
            return True
        if token in {"false", "0", "no", "n"}:
            return False
    elif isinstance(value, bool) or (isinstance(value, (int, float)) and value in (0, 1)):
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
    return None if value is None else value.strip().lower()


def _surface_energy_si(value: Any, document: dict[str, Any]) -> float | None:
    alternate = document.get("weighted_surface_energy_EV_PER_ANG2")
    converted = None if alternate is None else float(alternate) * 16.02176634
    if value is not None and converted is not None and not math.isclose(float(value), converted, rel_tol=1e-5, abs_tol=1e-6):
        raise ValueError("inconsistent surface energies in J/m^2 and eV/Angstrom^2")
    return float(value) if value is not None else converted


def _now(_: Any, __: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TRANSFORMS = {
    "requested_id": _requested_id,
    "build_mp_url": _build_mp_url,
    "atomic_number_density": _atomic_number_density,
    "youngs_modulus": _youngs_modulus,
    "to_int": _to_int,
    "to_bool": _to_bool,
    "normalize_elements": _normalize_elements,
    "count_items": _count_items,
    "normalize_formula": _normalize_formula,
    "normalize_chemical_system": _normalize_chemical_system,
    "lowercase": _lowercase,
    "surface_energy_si": _surface_energy_si,
    "now": _now,
}


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


def _materialize_structure_cif(
    document: dict[str, Any],
    structure_root: str | Path | None,
    downloaded_files: Any = None,
) -> str | None:
    """Ensure a canonical CIF exists for this record and return its path.

    The CIF is stored as ``<structure_root>/<source_id>/<source_id>.cif``. An
    already downloaded CIF is preferred, then the inline summary structure,
    then a raw POSCAR/CONTCAR. Failures return ``None`` so the record keeps a
    null ``structure_path``.
    """
    if not structure_root:
        return None
    source_id = document.get("material_id") or document.get("_requested_id")
    if not source_id:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    files = [Path(path) for path in (downloaded_files or [])]
    for path in files:
        if path.suffix.lower() == ".cif" and path.exists():
            try:
                from pymatgen.core import Structure

                if _write_cif(Structure.from_file(path), target):
                    return str(target)
            except Exception:
                pass
    inline = document.get("structure")
    if isinstance(inline, dict):
        try:
            from pymatgen.core import Structure

            if _write_cif(Structure.from_dict(inline), target):
                return str(target)
        except Exception:
            pass
    for path in files:
        if path.name.upper().startswith(("POSCAR", "CONTCAR")) and path.exists():
            try:
                from pymatgen.core import Structure

                if _write_cif(Structure.from_file(path), target):
                    return str(target)
            except Exception:
                pass
    return None


def normalize_summary(
    document: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    downloaded_files: Any = None,
    route_documents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one MP summary document into a complete DFT standard record.

    Args:
        document (dict[str, Any]): Raw MP summary document.
        structure_root (str | Path | None): Base directory for canonical CIFs.
        downloaded_files (Any): Local artifact paths for CIF materialization.
        route_documents (dict[str, Any] | None): Per-route documents keyed by
            endpoint name, exposed to mapping as ``_route.<endpoint>``.

    Returns:
        dict[str, Any]: Standard record with every contract field present.
    """
    lookup = {**document, "_route": route_documents or {}}
    standard = load_yaml(STANDARD_PATH)
    mapping = load_yaml(MAPPING_PATH)
    rules = mapping.get("mapping", {})
    result: dict[str, Any] = {}
    for name in standard.get("fields", {}):
        rule = rules.get(name) or {}
        if "value" in rule:
            value = rule["value"]
        else:
            value = get_by_path(lookup, rule.get("field"))
        if value is None and "default" in rule:
            value = rule["default"]
        if rule.get("transform"):
            value = TRANSFORMS[rule["transform"]](value, lookup)
        result[name] = value
    consumed = {
        str(rule.get("field")).split(".")[0]
        for rule in rules.values()
        if isinstance(rule, dict) and rule.get("field") and "." not in str(rule["field"])
    }
    excluded = set(mapping.get("source_extra_exclude", []))
    result["source_extra"] = {
        key: value
        for key, value in lookup.items()
        if key not in consumed and key not in excluded and not key.startswith("_")
    } or None
    result["structure_path"] = _materialize_structure_cif(lookup, structure_root, downloaded_files)
    fill_derived_pairs(result)
    return result
