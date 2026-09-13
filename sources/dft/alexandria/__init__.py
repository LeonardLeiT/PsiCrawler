"""Alexandria (AMD) raw download source."""

from .download import (
    DATASETS,
    PRIMARY_DATASETS,
    AlexandriaConfig,
    AlexandriaError,
    Dataset,
    OptimadeClient,
    completed,
    download_file,
    fetch_optimade_structure,
    get_dataset,
    iter_dataset_entries,
    iter_entries,
    list_remote_files,
    optimade_record_to_document,
    source_id_for,
)

__all__ = [
    "AlexandriaConfig",
    "AlexandriaError",
    "DATASETS",
    "Dataset",
    "OptimadeClient",
    "PRIMARY_DATASETS",
    "completed",
    "download_file",
    "fetch_optimade_structure",
    "get_dataset",
    "iter_dataset_entries",
    "iter_entries",
    "list_remote_files",
    "optimade_record_to_document",
    "source_id_for",
]
