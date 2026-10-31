"""OMat24 raw download source."""

from .download import (
    DEFAULT_SUBSET,
    SUBSETS,
    CompletionIndex,
    Omat24Config,
    Omat24Error,
    archive_path,
    completed,
    download_archive,
    ensure_extracted,
    extract_dir,
    get_subset,
    iter_records,
    read_entry,
    source_id_for,
)

__all__ = [
    "DEFAULT_SUBSET",
    "SUBSETS",
    "CompletionIndex",
    "Omat24Config",
    "Omat24Error",
    "archive_path",
    "completed",
    "download_archive",
    "ensure_extracted",
    "extract_dir",
    "get_subset",
    "iter_records",
    "read_entry",
    "source_id_for",
]
