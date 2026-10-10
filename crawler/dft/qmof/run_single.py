"""Pipeline entrypoint: fetch one QMOF record from the release files."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.qmof.normalize import normalize_qmof_record
from sources.dft.qmof.download import QmofConfig, read_entry, source_id_for

SOURCE = "qmof"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "is_magnetic")


def extract_single(config: QmofConfig, qmof_id: str) -> dict:
    """Read, normalize, and index one QMOF record."""
    record = read_entry(qmof_id, config)
    if record is None:
        raise LookupError(f"QMOF record not found: {qmof_id}")
    raw_path = str(config.csv_path)
    normalized = normalize_qmof_record(
        record, structure_root=config.data_root / "structure", raw_path=raw_path, requested_id=qmof_id,
    )
    normalized["raw_path"] = raw_path
    normalized["source_documents"] = {"csv": raw_path, "structures": str(config.structures_path)}
    normalized["download_status"] = "success"
    normalized["properties_requested"] = False
    storage.save(config.database_path, normalized, record, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": qmof_id,
        "source_id": source_id_for(record.get("qmof_id") or qmof_id),
        "formula": normalized.get("formula"),
        "structure_path": normalized.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one QMOF record.")
    parser.add_argument("qmof_id", help="QMOF identifier, for example qmof-8a95c27.")
    parser.add_argument("--data-root", default="data/dft/qmof")
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    """Run one QMOF lookup and write its manifest."""
    args = parse_args()
    overrides: dict = {"data_root": Path(args.data_root), "request_timeout": args.timeout}
    if args.endpoint:
        overrides["endpoint"] = args.endpoint.rstrip("/")
    config = QmofConfig(**overrides)
    manifest = start_manifest(config.data_root / "manifests", SOURCE, {"mode": "single"}, [args.qmof_id])
    logger = create_logger("crawler.qmof.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.qmof_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.qmof_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.qmof_id)
        raise


if __name__ == "__main__":
    main()
