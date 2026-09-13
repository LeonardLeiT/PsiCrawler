"""Pipeline entrypoint: batch download, normalize, and index Alexandria records.

Primary datasets are streamed entry by entry from the bulk ``.json.bz2``
archives. Auxiliary datasets are preserved raw with ``--download-only``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.alexandria.normalize import normalize_alexandria_entry
from sources.dft.alexandria.download import (
    BASE_URL,
    DATASETS,
    AlexandriaConfig,
    completed,
    download_file,
    get_dataset,
    iter_dataset_entries,
    list_remote_files,
    source_id_for,
)

SOURCE = "alexandria"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def _dataset_url(dataset) -> str | None:
    """Return the upstream download directory for a dataset, when known."""
    return f"{BASE_URL}/{dataset.directory}" if dataset.directory else None


def _run_download_only(config: AlexandriaConfig, dataset, logger, manifest, max_files: int | None) -> dict:
    """Download an auxiliary dataset without normalizing it."""
    files = list_remote_files(dataset, config)
    if max_files is not None:
        files = files[:max_files]
    stats = {"files": len(files), "downloaded": 0, "failed": 0}
    for index, filename in enumerate(files, start=1):
        try:
            path = download_file(dataset, filename, config, logger=logger)
            stats["downloaded"] += 1
            append_manifest_item(manifest, {"file": Path(filename).name, "status": "success", "path": str(path)})
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {"file": Path(filename).name, "status": "failed", "error": str(error)})
            logger.exception("[ERROR] %s (%d/%d)", filename, index, len(files))
    return stats


def _run_primary(config: AlexandriaConfig, dataset, args, logger, manifest) -> dict:
    """Stream, normalize, and index a primary entry dataset."""
    dataset_url = _dataset_url(dataset)
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0, "files": 0}
    current_file: str | None = None
    file_records = 0
    file_success = 0
    file_failed = 0

    def flush_file() -> None:
        nonlocal file_records, file_success, file_failed
        if current_file is not None:
            logger.info("[FILE] %s records=%d success=%d failed=%d", current_file, file_records, file_success, file_failed)
            append_manifest_item(manifest, {
                "file": current_file, "status": "partial" if file_failed else "success",
                "records": file_records, "success": file_success, "failed": file_failed,
            })
        file_records = file_success = file_failed = 0

    for item in iter_dataset_entries(
        dataset, config, max_files=args.max_files, max_records=args.max_records, logger=logger,
    ):
        filename = item["file"]
        if filename != current_file:
            flush_file()
            current_file = filename
            stats["files"] += 1
        stats["records"] += 1
        file_records += 1
        entry = item["entry"]
        data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
        mat_id = data.get("mat_id")
        if mat_id is None:
            stats["failed"] += 1
            file_failed += 1
            append_manifest_item(manifest, {"file": filename, "index": item["index"], "status": "failed", "error": "missing mat_id"})
            continue
        if not args.no_resume and completed(config.database_path, dataset.name, mat_id):
            stats["skipped"] += 1
            continue
        try:
            record = normalize_alexandria_entry(
                entry,
                dataset=dataset.name,
                dataset_url=dataset_url,
                functional=dataset.functional,
                dimensionality=dataset.dimensionality,
                structure_root=structure_root,
                raw_path=item["raw_path"],
            )
            record["raw_path"] = item["raw_path"]
            record["source_documents"] = {"dataset": dataset.name, "file": filename, "entry_index": item["index"]}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
            file_success += 1
        except Exception as error:
            stats["failed"] += 1
            file_failed += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(dataset.name, mat_id), "file": filename,
                "index": item["index"], "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s: %s", mat_id, filename)
    flush_file()
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize Alexandria datasets.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="pbe-3d")
    parser.add_argument("--max-files", type=int, default=None, help="Process at most this many dataset files.")
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many entries.")
    parser.add_argument("--data-root", default="data/dft/alexandria")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--download-only", action="store_true", help="Preserve raw files without normalizing.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run an Alexandria batch pipeline with a manifest."""
    args = parse_args()
    config = AlexandriaConfig(
        data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep,
    )
    dataset = get_dataset(args.dataset)
    if not args.download_only and not dataset.is_primary:
        raise SystemExit(f"Dataset {dataset.name!r} is auxiliary; re-run with --download-only.")
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "dataset": dataset.name, "max_files": args.max_files,
         "max_records": args.max_records, "download_only": args.download_only, "resume": not args.no_resume},
        [f"dataset:{dataset.name}"],
    )
    logger = create_logger("crawler.alexandria.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] dataset=%s primary=%s", dataset.name, dataset.is_primary)
    if args.download_only or not dataset.is_primary:
        stats = _run_download_only(config, dataset, logger, manifest, args.max_files)
    else:
        stats = _run_primary(config, dataset, args, logger, manifest)
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
