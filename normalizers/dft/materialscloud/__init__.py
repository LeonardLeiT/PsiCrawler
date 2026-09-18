"""Materials Cloud normalization into the DFT standard contract."""

from .normalize import (
    enrich_optimade,
    enrich_structure,
    normalize_materialscloud_optimade,
    normalize_materialscloud_structure,
)

__all__ = [
    "enrich_optimade",
    "enrich_structure",
    "normalize_materialscloud_optimade",
    "normalize_materialscloud_structure",
]
