"""Pipeline entrypoint: batch download, normalize, and index AFLOW records."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.aflow.normalize import normalize_aflow
from sources.dft.aflow.download import (
    DEFAULT_PROFILE,
    AflowConfig,
    build_filter_query,
    completed,
    download_one,
    fetch_aurl_list,
    read_aurls_file,
)

SOURCE = "aflow"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number")


def _extract(config: AflowConfig, identifier: str, profile: str, extra_patterns: list[str] | None,
             query_hit: dict | None = None) -> dict:
    """Download, normalize, and index one material."""
    result = download_one(identifier, config, profile, extra_patterns, query_hit=query_hit)
    record = normalize_aflow(
        {**result.metadata, "_requested_id": result.source_id},
        result.file_paths,
        structure_root=config.data_root / "structure",
    )
    record["raw_path"] = result.raw_path
    record["source_documents"] = {"files": result.file_paths}
    record["download_status"] = "partial" if result.errors else "success"
    record["properties_requested"] = True
    record["property_errors"] = {str(index): error for index, error in enumerate(result.errors)}
    storage.save(config.database_path, record, result.metadata, columns=field_names(), index_fields=INDEX_FIELDS)
    return {"source_id": result.source_id, "raw_path": result.raw_path, "files": len(result.file_paths), "errors": result.errors}


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize AFLOW material entries.")
    parser.add_argument("--query", help="Raw AFLUX filter expression.")
    parser.add_argument("--species", help="Comma-separated species filter.")
    parser.add_argument("--catalog", help="Source catalog filter, such as ICSD.")
    parser.add_argument("--compound-contains", help="Substring filter on the compound name.")
    parser.add_argument("--egap-min", type=float)
    parser.add_argument("--egap-max", type=float)
    parser.add_argument("--spacegroup", type=int)
    parser.add_argument("--ael", action="store_true", help="Require an AEL bulk modulus.")
    parser.add_argument("--agl", action="store_true", help="Require an AGL Debye temperature.")
    parser.add_argument("--aurls-file", help="Read one AURL per line instead of querying AFLUX.")
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--profile", choices=["core", "plots", "electronic", "symmetry", "bader", "vasp_raw", "all"], default=DEFAULT_PROFILE)
    parser.add_argument("--extra-patterns", default=None)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--data-root", default="data/dft/aflow")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a resumable AFLOW batch pipeline with a manifest."""
    args = parse_args()
    config = AflowConfig(data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep)
    patterns = [item.strip() for item in args.extra_patterns.split(",") if item.strip()] if args.extra_patterns else None
    if args.aurls_file:
        entries = read_aurls_file(args.aurls_file)
    else:
        filter_query = build_filter_query(
            query=args.query, species=args.species, catalog=args.catalog,
            compound_contains=args.compound_contains, egap_min=args.egap_min,
            egap_max=args.egap_max, spacegroup=args.spacegroup, ael=args.ael, agl=args.agl,
        )
        entries = fetch_aurl_list(filter_query, args.max, args.page_size, args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "profile": args.profile, "max": args.max, "resume": not args.no_resume},
        [str(entry.get("auid") or entry.get("aurl") or "unknown") for entry in entries],
    )
    logger = create_logger("crawler.aflow.batch", config.data_root / "logs", run_id=manifest["run_id"])
    stats = {"total": len(entries), "success": 0, "partial": 0, "failed": 0, "skipped": 0}
    for index, entry in enumerate(entries, start=1):
        identifier = entry.get("aurl")
        if not identifier:
            stats["failed"] += 1
            logger.error("[%d/%d] missing aurl", index, len(entries))
            continue
        auid = entry.get("auid")
        if auid and not args.no_resume and completed(config.database_path, auid):
            stats["skipped"] += 1
            append_manifest_item(manifest, {"source_id": auid, "status": "skipped", "attempts": 0})
            logger.info("[SKIP] %s", auid)
            continue
        try:
            result = _extract(config, identifier, args.profile, patterns, entry)
            status = "partial" if result["errors"] else "success"
            stats[status] += 1
            append_manifest_item(manifest, {"source_id": result["source_id"], "status": status, "attempts": 1, "files": result["files"], "errors": result["errors"]})
            logger.info("[OK] %s files=%d", result["source_id"], result["files"])
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {"source_id": auid or identifier, "status": "failed", "attempts": 1, "error": str(error)})
            logger.exception("[ERROR] %s", identifier)
        if index < len(entries) and args.sleep > 0:
            time.sleep(args.sleep)
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
