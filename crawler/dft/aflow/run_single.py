"""Pipeline entrypoint: download, normalize, and index one AFLOW record."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.aflow.normalize import normalize_aflow
from sources.dft.aflow.download import DEFAULT_AURL, DEFAULT_PROFILE, AflowConfig, completed, download_one

SOURCE = "aflow"
SCHEMA_VERSION = "3.0"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number")


def extract_single(config: AflowConfig, identifier: str, profile: str = DEFAULT_PROFILE,
                   extra_patterns: list[str] | None = None) -> dict:
    """Run the full pipeline for one AFLOW material and return a status summary."""
    result = download_one(identifier, config, profile, extra_patterns)
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
    return {
        "source_id": result.source_id,
        "raw_path": result.raw_path,
        "files": len(result.file_paths),
        "errors": result.errors,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Download and normalize one AFLOW material entry.")
    parser.add_argument("identifier", nargs="?", default=DEFAULT_AURL)
    parser.add_argument("--data-root", default="data/dft/aflow")
    parser.add_argument("--profile", choices=["core", "plots", "electronic", "symmetry", "bader", "vasp_raw", "all"], default=DEFAULT_PROFILE)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--extra-patterns", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run one AFLOW pipeline and write its manifest."""
    args = parse_args()
    config = AflowConfig(data_root=Path(args.data_root), request_timeout=args.timeout, sleep_seconds=args.sleep)
    patterns = [item.strip() for item in args.extra_patterns.split(",") if item.strip()] if args.extra_patterns else None
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single", "identifier": args.identifier, "profile": args.profile},
        [args.identifier],
    )
    logger = create_logger("crawler.aflow.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        if not args.force and completed(config.database_path, args.identifier):
            logger.info("[SKIP] %s already downloaded", args.identifier)
            append_manifest_item(manifest, {"source_id": args.identifier, "status": "skipped", "attempts": 0})
            finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 0, "skipped": 1})
            return
        result = extract_single(config, args.identifier, args.profile, patterns)
        status = "partial" if result["errors"] else "success"
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": status, "attempts": 1, "files": result["files"], "errors": result["errors"]})
        finish_manifest(manifest, {"requested": 1, "success": int(status == "success"), "partial": int(status == "partial"), "failed": 0, "skipped": 0})
        print(result)
    except Exception as error:
        logger.exception("[ERROR] %s", args.identifier)
        append_manifest_item(manifest, {"source_id": args.identifier, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 1, "skipped": 0})
        raise


if __name__ == "__main__":
    main()
