"""Shared, source-agnostic utilities used by all crawlers."""

from .logging import create_logger, new_run_id
from .storage import save

__all__ = [
    "create_logger",
    "new_run_id",
    "save",
]
