"""Pipeline entrypoint: fetch one OMat24 row from a subdataset.

OMat24 has no per-record API, so a single structure is located by streaming the
selected subdataset until ``sid`` (or the integer row id) matches.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.omat24.normalize import normalize_omat24_record
from sources.dft.omat24.download import DEFAULT_SUBSET, SUBSETS, Omat24Config, read_entry

SOURCE = "omat24"
INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "energy_per_atom")


def extract_single(config: Omat24Config, subset: str, record_id: str) -> dict:
    """Read, normalize, and index one OMat24 row."""
    record = read_entry(record_id, subset, config)
    if record is None:
        raise LookupError(f"OMat24 record not found in {subset}: {record_id}")
    data = record.get("data") or {}
    sid = data.get("sid") or f"{subset}:{record.get('row_id')}"
    raw_path = record.get("db_path")
    normalized = normalize_omat24_record(
        record, structure_root=config.data_root / "structure", raw_path=raw_path, requested_id=sid,
    )
    normalized["raw_path"] = raw_path
    normalized["source_documents"] = {"subset": subset, "db": raw_path, "row_id": record.get("row_id")}
    normalized["download_status"] = "success"
    normalized["properties_requested"] = False
    storage.save(config.database_path, normalized, data, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": record_id,
        "source_id": normalized.get("source_id"),
        "formula": normalized.get("formula"),
        "structure_path": normalized.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one OMat24 row.")
    parser.add_argument("record_id", help="OMat24 sid or integer row id.")
    parser.add_argument("--subset", choices=sorted(SUBSETS), default=DEFAULT_SUBSET)
    parser.add_argument("--data-root", default="data/dft/omat24")
    parser.add_argument("--timeout", type=int, default=1200)
    return parser.parse_args()


def main() -> None:
    """Run one OMat24 lookup and write its manifest."""
    args = parse_args()
    config = Omat24Config(data_root=Path(args.data_root), request_timeout=args.timeout)
    manifest = start_manifest(config.data_root / "manifests", SOURCE,
                              {"mode": "single", "subset": args.subset}, [args.record_id])
    logger = create_logger("crawler.omat24.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.subset, args.record_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.record_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.record_id)
        raise


if __name__ == "__main__":
    main()
