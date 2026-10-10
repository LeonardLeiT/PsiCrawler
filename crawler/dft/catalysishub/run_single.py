"""Pipeline entrypoint: fetch one Catalysis-Hub system by id.

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
    read_system,
    source_id_for,
)

SOURCE = "catalysishub"
INDEX_FIELDS = ("formula", "chemical_system", "total_energy", "spacegroup_number")


def extract_single(config: CatalysisHubConfig, system_id: str) -> dict:
    """Fetch, normalize, and index one Catalysis-Hub system."""
    node = read_system(system_id, config)
    if node is None:
        raise LookupError(f"Catalysis-Hub system not found: {system_id}")
    target = config.raw_dir / "systems" / f"{system_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(node, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    record = normalize_catalysishub_system(
        node, structure_root=config.data_root / "structure", raw_path=str(target), requested_id=system_id,
    )
    record["raw_path"] = str(target)
    record["source_documents"] = {"graphql": config.graphql_url}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, node, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": system_id,
        "source_id": source_id_for(node.get("id") or system_id),
        "formula": record.get("formula"),
        "structure_path": record.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one Catalysis-Hub system.")
    parser.add_argument("system_id", help="Catalysis-Hub system id.")
    parser.add_argument("--data-root", default="data/dft/catalysishub")
    parser.add_argument("--api-key", default=None, help="Override CATALYSIS_HUB_API_KEY.")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    """Run one Catalysis-Hub lookup and write its manifest."""
    args = parse_args()
    config = CatalysisHubConfig.from_environment(args.data_root)
    if args.api_key or args.timeout:
        config = CatalysisHubConfig(
            api_key=args.api_key or config.api_key,
            data_root=config.data_root,
            graphql_url=config.graphql_url,
            request_timeout=args.timeout,
        )
    manifest = start_manifest(config.data_root / "manifests", SOURCE, {"mode": "single"}, [args.system_id])
    logger = create_logger("crawler.catalysishub.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.system_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except CatalysisHubError as error:
        append_manifest_item(manifest, {"source_id": args.system_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[ERROR] %s", error)
        raise SystemExit(str(error)) from error
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.system_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.system_id)
        raise


if __name__ == "__main__":
    main()
