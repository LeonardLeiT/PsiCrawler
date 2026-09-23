"""Pipeline entrypoint: batch download, normalize, and index AMCSD records.

The three AMCSD ZIP archives (CIF, AMC, DIF) are downloaded from the official
RRUFF directory index and preserved verbatim under ``data/dft/amcsd/raw``.
Entries are streamed from the archives, aligned by AMCSD identifier, normalized
into DFT schema ``3.0`` (as experimental structures), and indexed in SQLite.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.amcsd.normalize import normalize_amcsd_entry
from sources.dft.amcsd.download import (
    ARCHIVES,
    AmcsdConfig,
    CompletionIndex,
    ensure_archives,
    iter_archive_entries,
    source_id_for,
)

SOURCE = "amcsd"
INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "crystal_system", "point_group")


def _parse_kinds(value: str) -> tuple[str, ...]:
    """Parse a comma-separated archive list into known archive kinds."""
    kinds = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    unknown = [kind for kind in kinds if kind not in ARCHIVES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown archives {unknown}; known: {', '.join(ARCHIVES)}")
    if not kinds:
        raise argparse.ArgumentTypeError("at least one archive must be requested")
    return kinds


def _property_paths(entry: dict) -> dict[str, str]:
    """Return the archive path map stored on every record."""
    paths = entry.get("archive_paths") or {}
    return {f"{kind}_archive": path for kind, path in paths.items()}


def _run_download_only(config: AmcsdConfig, kinds: tuple[str, ...], logger, manifest) -> dict:
    """Download the requested archives without normalizing them."""
    paths = ensure_archives(config, kinds, logger=logger)
    for kind, path in paths.items():
        append_manifest_item(manifest, {"file": f"{kind}.zip", "status": "success", "path": str(path)})
    return {"files": len(paths), "downloaded": len(paths), "failed": 0}


def _run_primary(config: AmcsdConfig, kinds: tuple[str, ...], args, logger, manifest,
                 completion_index: CompletionIndex) -> dict:
    """Stream, normalize, and index the requested AMCSD archives."""
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "partial": 0, "failed": 0, "skipped": 0}
    reached_limit = False
    for entry in iter_archive_entries(
        config, kinds=kinds, max_records=args.max_records, logger=logger,
    ):
        stats["records"] += 1
        amcsd_id = entry.get("amcsd_id")
        if amcsd_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {"status": "failed", "error": "missing amcsd_id"})
            continue
        if not args.no_resume and completion_index.is_completed(amcsd_id):
            stats["skipped"] += 1
            continue
        archive_paths = entry.get("archive_paths") or {}
        primary_raw = archive_paths.get("cif") or next(iter(archive_paths.values()), None)
        try:
            record = normalize_amcsd_entry(
                entry,
                structure_root=structure_root,
                property_paths=_property_paths(entry),
            )
            record["raw_path"] = primary_raw
            record["source_documents"] = {
                "members": entry.get("members"),
                "archives": archive_paths,
            }
            status = "success" if record.get("structure") else "partial"
            record["download_status"] = status
            record["properties_requested"] = False
            raw = {
                "amcsd_id": amcsd_id,
                "cif": entry.get("cif"),
                "amc": entry.get("amc"),
                "dif": entry.get("dif"),
            }
            storage.save(config.database_path, record, raw, columns=field_names(), index_fields=INDEX_FIELDS)
            stats[status] += 1
            if status == "partial":
                append_manifest_item(manifest, {
                    "source_id": source_id_for(amcsd_id), "status": "partial",
                    "error": "structure not parsed from CIF",
                })
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(amcsd_id), "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", amcsd_id)
        if args.max_records is not None and stats["records"] >= args.max_records:
            reached_limit = True
            break
    if reached_limit:
        logger.info("[LIMIT] stopped after %d records", stats["records"])
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize the AMCSD archives.")
    parser.add_argument("--data-root", default="data/dft/amcsd")
    parser.add_argument("--archives", type=_parse_kinds, default=("amc", "cif", "dif"),
                        help="Comma-separated archives to process (amc,cif,dif).")
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many entries.")
    parser.add_argument("--download-only", action="store_true", help="Preserve raw archives without normalizing.")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    """Run an AMCSD batch pipeline with a manifest."""
    args = parse_args()
    config = AmcsdConfig(
        data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep,
    )
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "archives": list(args.archives), "max_records": args.max_records,
         "download_only": args.download_only, "resume": not args.no_resume},
        [f"archive:{kind}" for kind in args.archives],
    )
    logger = create_logger("crawler.amcsd.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] archives=%s", ",".join(args.archives))
    try:
        if args.download_only:
            stats = _run_download_only(config, args.archives, logger, manifest)
        else:
            with CompletionIndex(config.database_path) as completion_index:
                stats = _run_primary(config, args.archives, args, logger, manifest, completion_index)
    except Exception as error:
        logger.exception("[FATAL]")
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
