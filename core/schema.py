"""Schema-driven record normalization shared by all sources."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .transforms import apply_transform


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping file.

    Args:
        path (str | Path): YAML file path.

    Returns:
        dict[str, Any]: Parsed YAML document.
    """
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed field path from a nested document.

    Args:
        document (dict[str, Any]): Source document.
        field_path (str | None): Path such as ``symmetry.number``.

    Returns:
        Any: Field value, or ``None`` when the path is absent.
    """
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


def normalize_by_schema(
    document: dict[str, Any],
    standard_path: str | Path,
    mapping_path: str | Path,
) -> dict[str, Any]:
    """Create a complete normalized record from a source mapping.

    Args:
        document (dict[str, Any]): Raw source document.
        standard_path (str | Path): Unified DFT schema path.
        mapping_path (str | Path): Source-specific mapping path.

    Returns:
        dict[str, Any]: Record containing every standard field, with missing
            values represented by ``None``.
    """
    standard = load_yaml(standard_path)
    mapping = load_yaml(mapping_path)
    result: dict[str, Any] = {}
    rules = mapping.get("mapping", {})
    for field_name in standard.get("fields", {}):
        rule = rules.get(field_name, {}) or {}
        if "value" in rule:
            value = rule["value"]
        else:
            value = get_by_path(document, rule.get("field"))
        if value is None and "default" in rule:
            value = rule["default"]
        if rule.get("transform"):
            value = apply_transform(rule["transform"], value, document)
        result[field_name] = value
    consumed_fields = {
        str(rule.get("field")).split(".")[0]
        for rule in rules.values()
        if isinstance(rule, dict) and rule.get("field")
    }
    excluded_extra = set(mapping.get("source_extra_exclude", []))
    source_extra = {
        key: value
        for key, value in document.items()
        if key not in consumed_fields
        and key not in excluded_extra
        and not key.startswith("_")
    }
    result["source_extra"] = source_extra or None
    return result


