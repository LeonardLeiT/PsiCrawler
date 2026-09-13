"""arXiv paper normalization placeholder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

STANDARD_PATH = Path(__file__).resolve().parent / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"


def normalize_record(document: dict[str, Any]) -> dict[str, Any]:
    """Convert one arXiv raw document into the paper standard record."""
    raise NotImplementedError("arXiv normalization is not implemented yet")
