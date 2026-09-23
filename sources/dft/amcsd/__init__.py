"""AMCSD raw download source."""

from .download import (
    ARCHIVES,
    AmcsdArchives,
    AmcsdConfig,
    AmcsdError,
    CompletionIndex,
    archive_path,
    archive_url,
    completed,
    download_archive,
    ensure_archives,
    iter_archive_entries,
    normalize_amcsd_id,
    read_entry,
    source_id_for,
)

__all__ = [
    "ARCHIVES",
    "AmcsdArchives",
    "AmcsdConfig",
    "AmcsdError",
    "CompletionIndex",
    "archive_path",
    "archive_url",
    "completed",
    "download_archive",
    "ensure_archives",
    "iter_archive_entries",
    "normalize_amcsd_id",
    "read_entry",
    "source_id_for",
]
