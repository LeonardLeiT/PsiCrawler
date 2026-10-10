"""Pipeline entrypoint: query, normalize, and index Catalysis-Hub systems.

The GraphQL endpoint requires a free API key. Set ``CATALYSIS_HUB_API_KEY`` (in a
local ``.env`` or the environment) before running.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.catalysishub.normalize import normalize_catalysishub_system
from sources.dft.catalysishub.download import (
    CatalysisHubConfig,
    CatalysisHubError,
    CompletionIndex,
    iter_systems,
    source_id_for,
)

SOURCE = "catalysishub"
INDEX_FIELDS = ("formula", "chemical_system", "total_energy", "spacegroup_number")


def _save_raw(raw_dir: Path, system_id: str, node: dict) -> Path:
    """Write one raw system document to ``raw/systems`` atomically."""
    target = raw_dir / "systems" / f"{system_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(node, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temporary, target)
    return target


def _run_primary(config: CatalysisHubConfig, args, logger, manifest, completion_index: CompletionIndex) -> dict:
    """Query, normalize, and index Catalysis-Hub systems."""
    structure_root = config.data_root / "structure"
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for node in iter_systems(config, max_records=args.max_records, logger=logger):
        stats["records"] += 1
        system_id = node.get("id")
        if system_id is None:
            stats["failed"] += 1
            append_manifest_item(manifest, {"status": "failed", "error": "missing system id"})
            continue
        if not args.no_resume and completion_index.is_completed(system_id):
            stats["skipped"] += 1
            continue
        try:
            raw_path = _save_raw(config.raw_dir, str(system_id), node)
            record = normalize_catalysishub_system(
                node, structure_root=structure_root, raw_path=str(raw_path), requested_id=system_id,
            )
            record["raw_path"] = str(raw_path)
            record["source_documents"] = {"graphql": config.graphql_url}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, node, columns=field_names(), index_fields=INDEX_FIELDS)
            stats["success"] += 1
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(system_id), "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", system_id)
    logger.info("[FILE] systems records=%d success=%d failed=%d skipped=%d", stats["records"],
                stats["success"], stats["failed"], stats["skipped"])
    append_manifest_item(manifest, {"table": "systems", "status": "partial" if stats["failed"] else "success", **stats})
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch query and normalize Catalysis-Hub systems.")
    parser.add_argument("--max-records", type=int, default=None, help="Index at most this many systems.")
    parser.add_argument("--data-root", default="data/dft/catalysishub")
    parser.add_argument("--api-key", default=None, help="Override CATALYSIS_HUB_API_KEY.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a Catalysis-Hub batch pipeline with a manifest."""
    args = parse_args()
    config = CatalysisHubConfig.from_environment(args.data_root)
    if args.api_key or args.page_size or args.timeout:
        config = CatalysisHubConfig(
            api_key=args.api_key or config.api_key,
            data_root=config.data_root,
            graphql_url=config.graphql_url,
            page_size=args.page_size,
            request_timeout=args.timeout,
        )
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "batch", "table": "systems", "max_records": args.max_records, "resume": not args.no_resume},
        ["catalysishub:systems"],
    )
    logger = create_logger("crawler.catalysishub.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] source=catalysishub table=systems")
    try:
        with CompletionIndex(config.database_path) as completion_index:
            stats = _run_primary(config, args, logger, manifest, completion_index)
    except CatalysisHubError as error:
        logger.error("[ERROR] %s", error)
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise SystemExit(str(error)) from error
    except Exception as error:
        logger.exception("[FATAL]")
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
