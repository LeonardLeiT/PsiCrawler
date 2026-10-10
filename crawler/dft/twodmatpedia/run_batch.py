"""Pipeline entrypoint: batch download, normalize, and index 2DMatPedia.

The whole database is a single JSON Lines file, so the run downloads it once,
streams its lines, normalizes each record into DFT schema ``3.0``, and indexes
it in SQLite. ``--download-only`` keeps the raw file without normalizing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.twodmatpedia.normalize import normalize_2dmatpedia_entry
from sources.dft.twodmatpedia.download import (
    CompletionIndex,
    TwoDMatPediaConfig,
    db_path,
    download_db,
    iter_entries,
    source_id_for,
)

SOURCE = "2dmatpedia"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def _run_primary(config: TwoDMatPediaConfig, args, logger, manifest,
                 completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index the 2DMatPedia database."""
    local = download_db(config, force=args.force_download, logger=logger)
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for index, entry in enumerate(iter_entries(local)):
        if args.max_records is not None and stats["records"] >= args.max_records:
            break
        stats["records"] += 1
        material_id = entry.get("material_id")
        if material_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {"index": index, "status": "failed", "error": "missing material_id"})
            continue
        if not args.no_resume and completion_index.is_completed(material_id):
            stats["skipped"] += 1
            continue
        try:
            record = normalize_2dmatpedia_entry(
                entry,
                structure_root=structure_root,
                raw_path=str(local),
                requested_id=material_id,
            )
            record["raw_path"] = str(local)
            record["source_documents"] = {"file": local.name, "entry_index": index}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(material_id), "index": index,
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", material_id)
    logger.info("[FILE] %s records=%d success=%d failed=%d skipped=%d", local.name, stats["records"],
                stats["success"], stats["failed"], stats["skipped"])
    append_manifest_item(manifest, {
        "file": local.name,
        "status": "partial" if stats["failed"] else "success",
        **stats,
    })
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize 2DMatPedia.")
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many entries.")
    parser.add_argument("--data-root", default="data/dft/2dmatpedia")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--download-only", action="store_true", help="Preserve the raw file without normalizing.")
    parser.add_argument("--force-download", action="store_true", help="Re-download the database file.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a 2DMatPedia batch pipeline with a manifest."""
    args = parse_args()
    config = TwoDMatPediaConfig(
        data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep,
    )
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "max_records": args.max_records,
         "download_only": args.download_only, "resume": not args.no_resume},
        ["2dmatpedia"],
    )
    logger = create_logger("crawler.2dmatpedia.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] source=2dmatpedia download_only=%s", args.download_only)
    try:
        if args.download_only:
            local = download_db(config, force=args.force_download, logger=logger)
            stats = {"file": str(local), "records": 0, "success": 0, "failed": 0, "skipped": 0}
        else:
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
