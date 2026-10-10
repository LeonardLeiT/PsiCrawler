"""Pipeline entrypoint: stream, normalize, and index MatPES.

MatPES entries are streamed from the remote JSON Lines file on Hugging Face, so
a limited run transfers only the lines it consumes. ``--function`` selects the
PBE or r2SCAN release.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.matpes.normalize import normalize_matpes_entry
from sources.dft.matpes.download import (
    DEFAULT_FUNCTION,
    FUNCTIONS,
    CompletionIndex,
    MatPesConfig,
    dataset_url,
    iter_entries,
    source_id_for,
)

SOURCE = "matpes"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "formation_energy_per_atom", "spacegroup_number")


def _run_primary(config: MatPesConfig, args, logger, manifest, completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index one MatPES functional file."""
    url = dataset_url(args.function, config)
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for index, entry in enumerate(iter_entries(args.function, config, logger=logger)):
        if args.max_records is not None and stats["records"] >= args.max_records:
            break
        stats["records"] += 1
        matpes_id = entry.get("matpes_id")
        if matpes_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {"index": index, "status": "failed", "error": "missing matpes_id"})
            continue
        if not args.no_resume and completion_index.is_completed(matpes_id):
            stats["skipped"] += 1
            continue
        try:
            record = normalize_matpes_entry(
                entry, structure_root=structure_root, raw_path=url, requested_id=matpes_id,
            )
            record["raw_path"] = url
            record["source_documents"] = {"dataset": args.function, "url": url, "entry_index": index}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(matpes_id), "index": index,
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", matpes_id)
    logger.info("[FILE] %s records=%d success=%d failed=%d skipped=%d", args.function, stats["records"],
                stats["success"], stats["failed"], stats["skipped"])
    append_manifest_item(manifest, {"file": args.function, "status": "partial" if stats["failed"] else "success", **stats})
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch stream and normalize MatPES.")
    parser.add_argument("--function", choices=sorted(FUNCTIONS), default=DEFAULT_FUNCTION)
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many entries.")
    parser.add_argument("--data-root", default="data/dft/matpes")
    parser.add_argument("--endpoint", default=None, help="Hugging Face endpoint (mirror) override.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a MatPES batch pipeline with a manifest."""
    args = parse_args()
    config = MatPesConfig(data_root=Path(args.data_root), request_timeout=args.timeout)
    if args.endpoint:
        config = MatPesConfig(
            data_root=Path(args.data_root), endpoint=args.endpoint.rstrip("/"), request_timeout=args.timeout,
        )
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "function": args.function, "max_records": args.max_records,
         "endpoint": config.endpoint, "resume": not args.no_resume},
        [f"matpes:{args.function}"],
    )
    logger = create_logger("crawler.matpes.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] source=matpes function=%s endpoint=%s", args.function, config.endpoint)
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
