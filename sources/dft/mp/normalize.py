"""Schema-driven normalization for Materials Project records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.schema import normalize_by_schema


SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "schemas" / "dft"
STANDARD_SCHEMA = SCHEMA_ROOT / "standard.yaml"
MP_MAPPING = SCHEMA_ROOT / "mp.yaml"


def normalize_summary(document: dict[str, Any]) -> dict[str, Any]:
    """Convert one MP summary document using the executable MP mapping.

    Args:
        document (dict[str, Any]): Raw MP summary document.

    Returns:
        dict[str, Any]: Complete DFT record with unavailable fields set to null.
    """
    return normalize_by_schema(document, STANDARD_SCHEMA, MP_MAPPING)
