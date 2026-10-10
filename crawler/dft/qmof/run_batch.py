"""Pipeline entrypoint: download, normalize, and index QMOF.

The property table and relaxed-structure archive are downloaded once, then each
CSV row is joined with its CIF, normalized into DFT schema ``3.0``, and indexed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.qmof.normalize import normalize_qmof_record
from sources.dft.qmof.download import (
    CompletionIndex,
    QmofConfig,
    ensure_assets,
    iter_records,
    source_id_for,
)

SOURCE = "qmof"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "is_magnetic")


def _run_primary(config: QmofConfig, args, logger, manifest, completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index the QMOF release."""
    if args.download_only:
        csv_path, zip_path = ensure_assets(config, force=args.force_download, logger=logger)
        return {"file": str(csv_path), "structures": str(zip_path), "records": 0, "success": 0,
                "failed": 0, "skipped": 0}
    structure_root = config.data_root / "structure"
    raw_path = str(config.csv_path)
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for record in iter_records(config, download_missing=True, logger=logger):
        if args.max_records is not None and stats["records"] >= args.max_records:
            break
        stats["records"] += 1
        qmof_id = record.get("qmof_id")
        if qmof_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {"index": record.get("index"), "status": "failed", "error": "missing qmof_id"})
            continue
        if not args.no_resume and completion_index.is_completed(qmof_id):
            stats["skipped"] += 1
            continue
        try:
            normalized = normalize_qmof_record(
                record, structure_root=structure_root, raw_path=raw_path, requested_id=qmof_id,
            )
            normalized["raw_path"] = raw_path
            normalized["source_documents"] = {
                "csv": raw_path, "structures": str(config.structures_path), "row": record.get("index"),
            }
            normalized["download_status"] = "success"
            normalized["properties_requested"] = False
            storage.save(config.database_path, normalized, record, columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(qmof_id), "index": record.get("index"),
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", qmof_id)
    logger.info("[FILE] qmof.csv records=%d success=%d failed=%d skipped=%d", stats["records"],
                stats["success"], stats["failed"], stats["skipped"])
    append_manifest_item(manifest, {"file": "qmof.csv", "status": "partial" if stats["failed"] else "success", **stats})
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize QMOF.")
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many entries.")
    parser.add_argument("--data-root", default="data/dft/qmof")
    parser.add_argument("--endpoint", default=None, help="Hugging Face endpoint (mirror) override.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--download-only", action="store_true", help="Download assets without normalizing.")
    parser.add_argument("--force-download", action="store_true", help="Re-download the assets.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a QMOF batch pipeline with a manifest."""
    args = parse_args()
    overrides: dict = {"data_root": Path(args.data_root), "request_timeout": args.timeout}
    if args.endpoint:
        overrides["endpoint"] = args.endpoint.rstrip("/")
    config = QmofConfig(**overrides)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "max_records": args.max_records, "endpoint": config.endpoint,
         "download_only": args.download_only, "resume": not args.no_resume},
        ["qmof"],
    )
    logger = create_logger("crawler.qmof.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] source=qmof endpoint=%s download_only=%s", config.endpoint, args.download_only)
    try:
        with CompletionIndex(config.database_path) as completion_index:
            stats = _run_primary(config, args, logger, manifest, completion_index)
    except Exception as error:
        logger.exception("[FATAL]")
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
