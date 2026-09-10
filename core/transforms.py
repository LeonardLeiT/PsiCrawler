"""Named, safe transforms used by schema mappings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalize_chemical_system(value: Any, _: dict[str, Any]) -> str | None:
    """Sort chemical-system elements into a stable representation."""
    if not value:
        return None
    return "-".join(sorted(str(value).replace("_", "-").split("-")))


def normalize_elements(value: Any, _: dict[str, Any]) -> list[str] | None:
    """Return sorted unique element symbols."""
    if value is None:
        return None
    return sorted({str(item) for item in value})


def normalize_formula(value: Any, _: dict[str, Any]) -> str | None:
    """Normalize a formula without changing its chemical meaning."""
    return str(value).strip() if value is not None else None


def to_int(value: Any, _: dict[str, Any]) -> int | None:
    """Convert a source value to an integer or return null."""
    return int(value) if value is not None else None


def count_items(value: Any, _: dict[str, Any]) -> int | None:
    """Count items in a source list or return null."""
    return len(value) if value is not None else None


def to_bool(value: Any, _: dict[str, Any]) -> bool | None:
    """Convert common source values to a boolean or return null."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def composition_from_structure(_: Any, document: dict[str, Any]) -> dict[str, float] | None:
    """Build an elemental composition from a serialized structure."""
    counts: dict[str, float] = {}
    for site in (document.get("structure") or {}).get("sites", []):
        for species in site.get("species", []):
            element = species.get("element")
            if element:
                counts[element] = counts.get(element, 0.0) + float(species.get("occu", 1.0))
    return counts or None


def requested_id(_: Any, document: dict[str, Any]) -> str | None:
    """Return the identifier used by the crawler query when available."""
    return document.get("_requested_id")


def build_mp_url(value: Any, _: dict[str, Any]) -> str | None:
    """Build the public Materials Project URL for a material ID."""
    return f"https://materialsproject.org/materials/{value}/" if value else None


def now(_: Any, __: dict[str, Any]) -> str:
    """Return the current UTC retrieval timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TRANSFORMS = {
    "normalize_chemical_system": normalize_chemical_system,
    "normalize_elements": normalize_elements,
    "normalize_formula": normalize_formula,
    "to_int": to_int,
    "count_items": count_items,
    "to_bool": to_bool,
    "composition_from_structure": composition_from_structure,
    "requested_id": requested_id,
    "build_mp_url": build_mp_url,
    "now": now,
}


def apply_transform(name: str, value: Any, document: dict[str, Any]) -> Any:
    """Apply a registered schema transform.

    Args:
        name (str): Registered transform name.
        value (Any): Extracted source value.
        document (dict[str, Any]): Complete source document.

    Returns:
        Any: Transformed value.

    Raises:
        KeyError: If the transform is not registered.
    """
    return TRANSFORMS[name](value, document)
