"""Command-line entrypoint for one Materials Project material."""
from __future__ import annotations

import argparse

from core.logging import create_logger, new_run_id
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from sources.dft.mp import MPClient, MPConfig, extract_one
from sources.dft.mp.storage import ensure_storage, record_is_complete


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Extract one Materials Project record.")
    parser.add_argument("mp_id", help="Material ID, for example mp-149 or 149.")
    parser.add_argument("--data-root", default="data/dft/mp", help="MP data directory.")
    parser.add_argument("--no-properties", action="store_true", help="Skip extra property endpoints.")
    parser.add_argument("--force", action="store_true", help="Redownload an already complete record.")
    return parser.parse_args()


def main() -> None:
    """Run one resumable MP extraction and write its manifest."""
    args = parse_args()
    config = MPConfig.from_environment(args.data_root)
    ensure_storage(config)
    material_id = args.mp_id if str(args.mp_id).startswith("mp-") else f"mp-{args.mp_id}"
    include_properties = not args.no_properties
    manifest = start_manifest(
        config.manifest_dir,
        "mp",
        {"mode": "single", "include_properties": include_properties, "force": args.force},
        [material_id],
    )
    logger = create_logger("crawler.mp.single", config.logs_dir, run_id=manifest["run_id"])
    try:
        if not args.force and record_is_complete(config, material_id, include_properties):
            logger.info("[SKIP] %s already complete", material_id)
            append_manifest_item(manifest, {"source_id": material_id, "status": "skipped", "attempts": 0})
            finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 0, "skipped": 1})
            return
        logger.info("[START] %s", material_id)
        result = extract_one(MPClient(config), material_id, config, include_properties)
        append_manifest_item(manifest, {"source_id": material_id, "status": "success" if not result["property_errors"] else "partial", "attempts": 1, **result})
        logger.info("[OK] %s", material_id)
        finish_manifest(manifest, {"requested": 1, "success": int(not result["property_errors"]), "partial": int(bool(result["property_errors"])), "failed": 0, "skipped": 0})
        print(result)
    except Exception as error:
        logger.exception("[ERROR] %s", material_id)
        append_manifest_item(manifest, {"source_id": material_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 1, "skipped": 0})
        raise


if __name__ == "__main__":
    main()
