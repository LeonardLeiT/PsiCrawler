"""Single-record AFLOW crawler entrypoint."""
from __future__ import annotations

import argparse
from pathlib import Path

from core.manifest import append_manifest_item, finish_manifest, start_manifest
from sources.dft.aflow.extractor import (
    DEFAULT_AURL,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_PROFILE,
    DEFAULT_STATUS_JSON,
    DEFAULT_TIMEOUT_SECONDS,
    extract_single,
)


def parse_args() -> argparse.Namespace:
    """Parse AFLOW single-record arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Extract one AFLOW material entry.")
    parser.add_argument("identifier", nargs="?", default=DEFAULT_AURL)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--status-path", default=DEFAULT_STATUS_JSON)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--profile", choices=["core", "plots", "electronic", "symmetry", "bader", "vasp_raw", "all"], default=DEFAULT_PROFILE)
    parser.add_argument("--include-electronic", action="store_true")
    parser.add_argument("--include-vasp", action="store_true")
    parser.add_argument("--extra-patterns", default=None)
    return parser.parse_args()


def main() -> None:
    """Run one AFLOW extraction and write its manifest."""
    args = parse_args()
    profile = "vasp_raw" if args.include_vasp else "electronic" if args.include_electronic else args.profile
    patterns = [p.strip() for p in args.extra_patterns.split(",") if p.strip()] if args.extra_patterns else None
    manifest = start_manifest(
        Path(args.status_path).parent,
        "aflow",
        {"mode": "single", "identifier": args.identifier, "profile": profile, "dry_run": args.dry_run},
        [args.identifier],
    )
    report = extract_single(
        identifier=args.identifier,
        db_path=args.db_path,
        data_dir=args.data_dir,
        status_path=args.status_path,
        profile=profile,
        file_patterns=patterns,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
        dry_run=args.dry_run,
    )
    status = "success" if report.metadata and not report.errors else "partial" if report.metadata else "failed"
    append_manifest_item(manifest, {"source_id": report.auid or args.identifier, "status": status, "attempts": 1, "errors": report.errors, "files_downloaded": len(report.files_downloaded)})
    finish_manifest(manifest, {"requested": 1, "success": int(status == "success"), "partial": int(status == "partial"), "failed": int(status == "failed"), "skipped": 0})


if __name__ == "__main__":
    main()
