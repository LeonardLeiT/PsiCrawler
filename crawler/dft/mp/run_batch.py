"""Command-line entrypoint for batch Materials Project extraction."""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from sources.dft.mp import MPClient, MPConfig, extract_one
from sources.dft.mp.storage import ensure_storage, record_is_complete


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments.

    Returns:
        argparse.Namespace: Parsed crawler arguments.
    """
    parser = argparse.ArgumentParser(description="Batch extract Materials Project records.")
    parser.add_argument("--mp-ids", help="Comma-separated IDs; omit to query the MP summary endpoint.")
    parser.add_argument("--chemsys", help="Chemical system filter, such as Si-O.")
    parser.add_argument("--elements", help="Comma-separated required elements.")
    parser.add_argument("--stable", action="store_true", help="Only retrieve stable materials.")
    parser.add_argument("--max", type=int, default=None, dest="max_materials")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--data-root", default="data/dft/mp")
    parser.add_argument("--no-properties", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a resumable MP batch extraction with a manifest."""
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    config = MPConfig.from_environment(args.data_root)
    ensure_storage(config)
    client = MPClient(config)
    if args.mp_ids:
        mp_ids = [item.strip() for item in args.mp_ids.split(",") if item.strip()]
    else:
        elements = [item.strip() for item in args.elements.split(",")] if args.elements else None
        mp_ids = client.fetch_ids(chemsys=args.chemsys, elements=elements, is_stable=True if args.stable else None, max_materials=args.max_materials)
    mp_ids = [item if str(item).startswith("mp-") else f"mp-{item}" for item in mp_ids]
    include_properties = not args.no_properties
    manifest = start_manifest(
        config.manifest_dir,
        "mp",
        {"mode": "batch", "include_properties": include_properties, "workers": args.workers, "force": args.force, "chemsys": args.chemsys, "elements": args.elements, "stable": args.stable, "max_materials": args.max_materials},
        mp_ids,
    )
    logger = create_logger("crawler.mp.batch", config.logs_dir, run_id=manifest["run_id"])
    pending: list[str] = []
    skipped = 0
    for mp_id in mp_ids:
        if not args.force and record_is_complete(config, mp_id, include_properties):
            logger.info("[SKIP] %s already complete", mp_id)
            append_manifest_item(manifest, {"source_id": mp_id, "status": "skipped", "attempts": 0})
            skipped += 1
        else:
            pending.append(mp_id)
    logger.info("run_id=%s requested=%d pending=%d skipped=%d workers=%d", manifest["run_id"], len(mp_ids), len(pending), skipped, args.workers)

    def download_one(mp_id: str) -> tuple[str, bool, dict[str, Any] | None, str | None]:
        logger.info("[START] %s", mp_id)
        try:
            result = extract_one(MPClient(config), mp_id, config, include_properties)
            return mp_id, True, result, None
        except Exception as error:
            logger.exception("[ERROR] %s", mp_id)
            return mp_id, False, None, str(error)

    succeeded = partial = failed = 0
    def handle(result_tuple: tuple[str, bool, dict[str, Any] | None, str | None]) -> None:
        nonlocal succeeded, partial, failed
        mp_id, ok, result, error = result_tuple
        if not ok:
            failed += 1
            append_manifest_item(manifest, {"source_id": mp_id, "status": "failed", "attempts": 1, "error": error})
            return
        has_errors = bool(result and result.get("property_errors"))
        partial += int(has_errors)
        succeeded += int(not has_errors)
        append_manifest_item(manifest, {"source_id": mp_id, "status": "partial" if has_errors else "success", "attempts": 1, **(result or {})})
        logger.info("[OK] %s", mp_id)

    if args.workers == 1:
        for index, mp_id in enumerate(pending):
            handle(download_one(mp_id))
            if index + 1 < len(pending):
                time.sleep(args.sleep)
    else:
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="mp-crawler") as pool:
            for future in as_completed([pool.submit(download_one, mp_id) for mp_id in pending]):
                handle(future.result())
    summary = {"requested": len(mp_ids), "success": succeeded, "partial": partial, "failed": failed, "skipped": skipped, "workers": args.workers}
    finish_manifest(manifest, summary)
    logger.info("completed run_id=%s %s", manifest["run_id"], summary)


if __name__ == "__main__":
    main()
