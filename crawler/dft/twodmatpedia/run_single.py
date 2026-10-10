"""Pipeline entrypoint: fetch one 2DMatPedia record from the bulk database.

2DMatPedia exposes no per-record API, so a single material is read from the
already-downloaded JSON Lines file (downloading it on first use).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.twodmatpedia.normalize import normalize_2dmatpedia_entry
from sources.dft.twodmatpedia.download import (
    TwoDMatPediaConfig,
    db_path,
    read_entry,
    source_id_for,
)

SOURCE = "2dmatpedia"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def extract_single(config: TwoDMatPediaConfig, material_id: str) -> dict:
    """Read, normalize, and index one 2DMatPedia record."""
    entry = read_entry(material_id, config)
    if entry is None:
        raise LookupError(f"2DMatPedia record not found: {material_id}")
    local = db_path(config)
    record = normalize_2dmatpedia_entry(
        entry,
        structure_root=config.data_root / "structure",
        raw_path=str(local),
        requested_id=material_id,
    )
    record["raw_path"] = str(local)
    record["source_documents"] = {"file": local.name}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": material_id,
        "source_id": source_id_for(entry.get("material_id") or material_id),
        "formula": record.get("formula"),
        "structure_path": record.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one 2DMatPedia record.")
    parser.add_argument("material_id", help="2DMatPedia identifier, for example 2dm-1.")
    parser.add_argument("--data-root", default="data/dft/2dmatpedia")
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    """Run one 2DMatPedia lookup and write its manifest."""
    args = parse_args()
    config = TwoDMatPediaConfig(data_root=Path(args.data_root), request_timeout=args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single"},
        [args.material_id],
    )
    logger = create_logger("crawler.2dmatpedia.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.material_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.material_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.material_id)
        raise


if __name__ == "__main__":
    main()
