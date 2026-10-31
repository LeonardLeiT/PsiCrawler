"""Pipeline entrypoint: batch download, normalize, and index OMat24.

One subdataset is downloaded and extracted at a time, then its ASE LMDB rows are
streamed, normalized into DFT schema ``3.0``, and indexed in SQLite.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.omat24.normalize import normalize_omat24_record
from sources.dft.omat24.download import (
    DEFAULT_SUBSET,
    SUBSETS,
    CompletionIndex,
    Omat24Config,
    ensure_extracted,
    iter_records,
)

SOURCE = "omat24"
INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "energy_per_atom")


def _run_primary(config: Omat24Config, args, logger, manifest, completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index one OMat24 subdataset."""
    if args.download_only:
        directory = ensure_extracted(args.subset, config, force=args.force_download, logger=logger)
        return {"subset": args.subset, "extracted": str(directory), "records": 0,
                "success": 0, "failed": 0, "skipped": 0}
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for record in iter_records(args.subset, config, logger=logger):
        if args.max_records is not None and stats["records"] >= args.max_records:
            break
        stats["records"] += 1
        data = record.get("data") or {}
        sid = data.get("sid") or f"{args.subset}:{record.get('row_id')}"
        if not args.no_resume and completion_index.is_completed(sid):
            stats["skipped"] += 1
            continue
        try:
            raw_path = record.get("db_path")
            normalized = normalize_omat24_record(
                record, structure_root=structure_root, raw_path=raw_path, requested_id=sid,
            )
            normalized["raw_path"] = raw_path
            normalized["source_documents"] = {
                "subset": args.subset, "db": record.get("db_path"), "row_id": record.get("row_id"),
            }
            normalized["download_status"] = "success"
            normalized["properties_requested"] = False
            storage.save(config.database_path, normalized, record.get("data"), columns=field_names(),
                         index_fields=INDEX_FIELDS)
            stats["success"] += 1
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": sid, "row_id": record.get("row_id"), "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", sid)
    logger.info("[SUBSET] %s records=%d success=%d failed=%d skipped=%d", args.subset, stats["records"],
                stats["success"], stats["failed"], stats["skipped"])
    append_manifest_item(manifest, {"subset": args.subset,
                                    "status": "partial" if stats["failed"] else "success", **stats})
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize OMat24.")
    parser.add_argument("--subset", choices=sorted(SUBSETS), default=DEFAULT_SUBSET)
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many rows.")
    parser.add_argument("--data-root", default="data/dft/omat24")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--download-only", action="store_true", help="Download and extract without normalizing.")
    parser.add_argument("--force-download", action="store_true", help="Re-download the archive.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run an OMat24 batch pipeline with a manifest."""
    args = parse_args()
    config = Omat24Config(data_root=Path(args.data_root), request_timeout=args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "subset": args.subset, "max_records": args.max_records,
         "download_only": args.download_only, "resume": not args.no_resume},
        [f"omat24:{args.subset}"],
    )
    logger = create_logger("crawler.omat24.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] source=omat24 subset=%s download_only=%s", args.subset, args.download_only)
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
