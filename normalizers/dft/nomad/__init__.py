"""NOMAD Archive normalization into the DFT standard contract."""

from .normalize import enrich_archive, normalize_nomad_archive

__all__ = [
    "enrich_archive",
    "normalize_nomad_archive",
]
