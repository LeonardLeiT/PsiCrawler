"""Pipeline entrypoint: batch download, normalize, and index Materials Cloud.

Primary records are streamed from the Materials Cloud OPTIMADE API child by
child. The curated archive bulk archives can also be preserved verbatim with
``--download-bulk`` (the multi-gigabyte provenance archives are excluded).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.materialscloud.normalize import normalize_materialscloud_optimade
from sources.dft.materialscloud.download import (
    DATASETS,
    MAX_PAGE_LIMIT,
    CompletionIndex,
    MaterialsCloudConfig,
    download_bulk_file,
    get_dataset,
    iter_dataset_structures,
    list_bulk_files,
    source_id_for,
)

SOURCE = "materialscloud"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def parse_page_limit(value: str) -> int:
    """Parse and bound the OPTIMADE page size to the provider's accepted range."""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("page limit must be an integer") from error
    if not 1 <= number <= MAX_PAGE_LIMIT:
        raise argparse.ArgumentTypeError(
            f"page limit must be between 1 and {MAX_PAGE_LIMIT} "
            "(larger pages are rejected with HTTP 403)"
        )
    return number


def parse_datasets(value: str) -> list[str]:
    """Parse a comma-separated dataset list and validate each name."""
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise argparse.ArgumentTypeError("at least one dataset name is required")
    unknown = [name for name in names if name not in DATASETS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown dataset(s): {', '.join(unknown)}; known: {', '.join(DATASETS)}"
        )
    return names


def _run_bulk(config: MaterialsCloudConfig, dataset, logger, manifest) -> dict:
    """Preserve the curated bulk archives of one dataset without normalizing."""
    files = list_bulk_files(dataset, config)
    if not files:
        logger.warning("[EMPTY] no bulk files found for dataset %s", dataset.name)
    stats = {"files": len(files), "downloaded": 0, "failed": 0}
    for item in files:
        try:
            path = download_bulk_file(dataset, item["key"], config, logger=logger)
            stats["downloaded"] += 1
            append_manifest_item(manifest, {
                "dataset": dataset.name, "file": item["key"], "status": "success", "path": str(path),
            })
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "dataset": dataset.name, "file": item["key"], "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s/%s", dataset.name, item["key"])
    return stats


def _run_primary(config: MaterialsCloudConfig, dataset, args, logger, manifest,
                 completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index one dataset through OPTIMADE."""
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for item in iter_dataset_structures(
        dataset,
        config,
        filter_expression=args.filter,
        page_limit=args.page_limit,
        max_records=args.max_records,
        logger=logger,
    ):
        stats["records"] += 1
        entry_id = item["document"].get("id")
        if entry_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "dataset": dataset.name, "index": item["index"], "status": "failed", "error": "missing id",
            })
            continue
        if not args.no_resume and completion_index.is_completed(dataset.name, entry_id):
            stats["skipped"] += 1
            continue
        try:
            record = normalize_materialscloud_optimade(
                item["document"],
                dataset=dataset.name,
                discover_url=dataset.discover_url,
                functional=dataset.functional,
                dimensionality=dataset.dimensionality,
                structure_root=structure_root,
                requested_id=entry_id,
                derive_symmetry=not args.no_symmetry,
            )
            record["raw_path"] = None
            record["source_documents"] = {"optimade": item["url"], "dataset": dataset.name}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, item["document"],
                         columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
            if args.progress and stats["success"] % args.progress == 0:
                logger.info("[PROGRESS] %s success=%d", dataset.name, stats["success"])
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(dataset.name, entry_id), "dataset": dataset.name,
                "index": item["index"], "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s: %s", entry_id, dataset.name)
    logger.info("[DATASET] %s %s", dataset.name, stats)
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize Materials Cloud datasets.")
    parser.add_argument("--dataset", type=parse_datasets, default=list(DATASETS),
                        help="Comma-separated dataset names; defaults to all four.")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Index at most this many records per dataset.")
    parser.add_argument("--page-limit", type=parse_page_limit, default=100,
                        help=f"OPTIMADE page size, 1-{MAX_PAGE_LIMIT} (default 100).")
    parser.add_argument("--filter", default=None, help="OPTIMADE filter expression.")
    parser.add_argument("--data-root", default="data/dft/materialscloud")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--progress", type=int, default=1000,
                        help="Log a progress line every N saved records (0 disables).")
    parser.add_argument("--no-symmetry", action="store_true",
                        help="Skip spglib space-group derivation for speed.")
    parser.add_argument("--download-bulk", action="store_true",
                        help="Preserve curated archive bulk files instead of normalizing.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a Materials Cloud batch pipeline with a manifest."""
    args = parse_args()
    config = MaterialsCloudConfig(
        data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep,
    )
    datasets = [get_dataset(name) for name in args.dataset]
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "bulk" if args.download_bulk else "batch", "datasets": [d.name for d in datasets],
         "max_records": args.max_records, "page_limit": args.page_limit, "filter": args.filter,
         "download_bulk": args.download_bulk, "resume": not args.no_resume,
         "derive_symmetry": not args.no_symmetry},
        [f"dataset:{d.name}" for d in datasets],
    )
    logger = create_logger("crawler.materialscloud.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] datasets=%s mode=%s", ",".join(d.name for d in datasets),
                "bulk" if args.download_bulk else "batch")
    try:
        if args.download_bulk:
            stats = {"datasets": {}}
            for dataset in datasets:
                stats["datasets"][dataset.name] = _run_bulk(config, dataset, logger, manifest)
        else:
            stats = {"datasets": {}}
            with CompletionIndex(config.database_path) as completion_index:
                for dataset in datasets:
                    stats["datasets"][dataset.name] = _run_primary(
                        config, dataset, args, logger, manifest, completion_index,
                    )
    except Exception as error:
        logger.exception("[FATAL] datasets=%s", ",".join(d.name for d in datasets))
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
