"""Pipeline entrypoint: batch download, normalize, and index Materials Project records."""

from __future__ import annotations

import argparse
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.mp.normalize import normalize_summary
from sources.dft.mp.download import (
    DEFAULT_BS_PATH_TYPES,
    PROPERTY_DOWNLOAD_VERSION,
    MPArtifactsClient,
    MPClient,
    MPConfig,
    completed,
    download_one,
    normalize_mp_id,
    requested_categories,
)

SOURCE = "mp"
SCHEMA_VERSION = "3.0"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "is_stable")

_THREAD_STATE = threading.local()


def _clients(config: MPConfig, need_artifacts: bool) -> tuple[MPClient, MPArtifactsClient | None]:
    """Return per-thread clients so parallel workers reuse expensive objects."""
    state = _THREAD_STATE
    if not hasattr(state, "client"):
        state.client = MPClient(config)
    if need_artifacts and not hasattr(state, "artifacts"):
        state.artifacts = MPArtifactsClient(config)
    return state.client, getattr(state, "artifacts", None)


def _extract(
    config: MPConfig,
    mp_id: str,
    *,
    include_properties: bool,
    include_files: bool,
    include_charge_density: bool,
    include_raw_vasp: bool,
    bs_path_types: tuple[str, ...],
    include_bs_projections: bool,
) -> dict:
    """Download, normalize, and index one material."""
    client, artifacts = _clients(config, include_files or include_raw_vasp)
    result = download_one(
        client,
        config,
        mp_id,
        include_properties,
        include_files=include_files,
        include_charge_density=include_charge_density,
        include_raw_vasp=include_raw_vasp,
        bs_path_types=bs_path_types,
        include_bs_projections=include_bs_projections,
        artifacts_client=artifacts,
    )
    record = normalize_summary(
        {**result.summary, "_requested_id": result.source_id},
        structure_root=config.data_root / "structure",
        downloaded_files=list(result.file_paths.values()),
        route_documents=result.documents,
    )
    record["raw_path"] = str(result.raw_path)
    record["property_paths"] = result.property_paths or None
    record["elastic_tensor_path"] = result.property_paths.get("elasticity")
    record["property_errors"] = result.property_errors or {}
    record["source_documents"] = {
        "properties": result.property_paths,
        "files": result.file_paths,
        "nomad": result.raw_archive_paths,
        "property_download_version": PROPERTY_DOWNLOAD_VERSION,
        "download_categories": sorted(result.categories),
        "bs_path_types": list(bs_path_types),
    }
    record["download_status"] = result.status
    record["properties_requested"] = include_properties
    storage.save(config.database_path, record, result.summary, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": result.requested_id,
        "source_id": result.source_id,
        "raw_path": str(result.raw_path),
        "properties": result.properties,
        "property_errors": result.property_errors,
        "files": len(result.file_paths),
        "file_errors": result.file_errors,
        "nomad_archives": len(result.raw_archive_paths),
        "raw_errors": result.raw_errors,
        "download_status": result.status,
        "categories": sorted(result.categories),
    }


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize Materials Project records.")
    parser.add_argument("--mp-ids", help="Comma-separated IDs; omit to query the MP summary endpoint.")
    parser.add_argument("--chemsys", help="Chemical system filter, such as Si-O.")
    parser.add_argument("--elements", help="Comma-separated required elements.")
    parser.add_argument("--stable", action="store_true", help="Only retrieve stable materials.")
    parser.add_argument("--max", type=int, default=None, dest="max_materials")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds between dispatches.")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--data-root", default="data/dft/mp")
    parser.add_argument("--no-properties", action="store_true")
    parser.add_argument("--no-files", action="store_true")
    parser.add_argument("--no-charge-density", action="store_true")
    parser.add_argument("--no-raw-vasp", action="store_true")
    parser.add_argument("--bs-path-types", default=",".join(DEFAULT_BS_PATH_TYPES))
    parser.add_argument("--no-bandstructure-projections", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a resumable MP batch pipeline with a manifest."""
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.workers > 1:
        os.environ.setdefault("TQDM_DISABLE", "1")
    config = MPConfig.from_environment(args.data_root)
    client = MPClient(config)
    include_properties = not args.no_properties
    include_files = not args.no_files
    include_charge_density = not args.no_charge_density
    include_raw_vasp = not args.no_raw_vasp
    include_bs_projections = not args.no_bandstructure_projections
    bs_path_types = tuple(item.strip() for item in args.bs_path_types.split(",") if item.strip())
    categories = requested_categories(
        include_properties=include_properties,
        include_files=include_files,
        include_charge_density=include_charge_density,
        include_raw_vasp=include_raw_vasp,
        include_bs_projections=include_bs_projections,
    )
    if args.mp_ids:
        mp_ids = [item.strip() for item in args.mp_ids.split(",") if item.strip()]
    else:
        elements = [item.strip() for item in args.elements.split(",")] if args.elements else None
        mp_ids = client.fetch_ids(chemsys=args.chemsys, elements=elements,
                                  is_stable=True if args.stable else None, max_materials=args.max_materials)
    mp_ids = [normalize_mp_id(item) for item in mp_ids]
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "properties": include_properties, "files": include_files,
         "charge_density": include_charge_density, "raw_vasp": include_raw_vasp,
         "bs_projections": include_bs_projections,
         "workers": args.workers, "force": args.force, "chemsys": args.chemsys,
         "elements": args.elements, "stable": args.stable, "max_materials": args.max_materials},
        mp_ids,
    )
    logger = create_logger("crawler.mp.batch", config.data_root / "logs", run_id=manifest["run_id"])
    pending: list[str] = []
    skipped = 0
    for mp_id in mp_ids:
        if not args.force and completed(config.database_path, mp_id, categories=categories, bs_path_types=bs_path_types):
            logger.info("[SKIP] %s already downloaded", mp_id)
            append_manifest_item(manifest, {"source_id": mp_id, "status": "skipped", "attempts": 0})
            skipped += 1
        else:
            pending.append(mp_id)
    logger.info("run_id=%s requested=%d pending=%d skipped=%d workers=%d",
                manifest["run_id"], len(mp_ids), len(pending), skipped, args.workers)

    def download_one_item(mp_id: str) -> tuple[str, bool, dict[str, Any] | None, str | None]:
        logger.info("[START] %s", mp_id)
        try:
            result = _extract(
                config, mp_id,
                include_properties=include_properties,
                include_files=include_files,
                include_charge_density=include_charge_density,
                include_raw_vasp=include_raw_vasp,
                bs_path_types=bs_path_types,
                include_bs_projections=include_bs_projections,
            )
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
        status = (result or {}).get("download_status", "success")
        partial += int(status == "partial")
        succeeded += int(status == "success")
        append_manifest_item(manifest, {"source_id": mp_id, "status": status, "attempts": 1, **(result or {})})
        logger.info("[%s] %s", status.upper(), mp_id)

    if args.workers == 1:
        for index, mp_id in enumerate(pending):
            handle(download_one_item(mp_id))
            if index + 1 < len(pending):
                time.sleep(args.sleep)
    else:
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="mp-crawler") as pool:
            futures = []
            for index, mp_id in enumerate(pending):
                futures.append(pool.submit(download_one_item, mp_id))
                if index + 1 < len(pending) and args.sleep > 0:
                    time.sleep(args.sleep)
            for future in as_completed(futures):
                handle(future.result())
    summary = {"requested": len(mp_ids), "success": succeeded, "partial": partial, "failed": failed, "skipped": skipped, "workers": args.workers}
    finish_manifest(manifest, summary)
    logger.info("completed run_id=%s %s", manifest["run_id"], summary)


if __name__ == "__main__":
    main()
