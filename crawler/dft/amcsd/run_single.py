"""Pipeline entrypoint: fetch, normalize, and index one AMCSD record.

AMCSD exposes no public per-record API, so a single record is read from the
official bulk archives. The archives are downloaded on demand if they are not
already present, then the requested identifier is extracted and normalized.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.amcsd.normalize import normalize_amcsd_entry
from sources.dft.amcsd.download import (
    AmcsdConfig,
    AmcsdError,
    normalize_amcsd_id,
    read_entry,
    source_id_for,
)

SOURCE = "amcsd"
INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "crystal_system", "point_group")


def extract_single(config: AmcsdConfig, amcsd_id: str, kinds: tuple[str, ...] = ("amc", "cif", "dif")) -> dict:
    """Read, normalize, and index one AMCSD identifier from the bulk archives."""
    entry = read_entry(amcsd_id, config, kinds=kinds)
    if entry is None:
        raise LookupError(f"AMCSD record not found: {amcsd_id}")
    archive_paths = entry.get("archive_paths") or {}
    property_paths = {f"{kind}_archive": path for kind, path in archive_paths.items()}
    record = normalize_amcsd_entry(
        entry,
        structure_root=config.data_root / "structure",
        property_paths=property_paths,
        requested_id=entry["amcsd_id"],
    )
    record["raw_path"] = archive_paths.get("cif") or next(iter(archive_paths.values()), None)
    record["source_documents"] = {"members": entry.get("members"), "archives": archive_paths}
    status = "success" if record.get("structure") else "partial"
    record["download_status"] = status
    record["properties_requested"] = False
    raw = {"amcsd_id": entry["amcsd_id"], "cif": entry.get("cif"), "amc": entry.get("amc"), "dif": entry.get("dif")}
    storage.save(config.database_path, record, raw, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": amcsd_id,
        "source_id": source_id_for(entry["amcsd_id"]),
        "status": status,
        "structure_path": record.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one AMCSD record.")
    parser.add_argument("amcsd_id", help="AMCSD identifier, for example 0000130 or 130.")
    parser.add_argument("--data-root", default="data/dft/amcsd")
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    """Run one AMCSD lookup and write its manifest."""
    args = parse_args()
    config = AmcsdConfig(data_root=Path(args.data_root), request_timeout=args.timeout)
    try:
        requested = normalize_amcsd_id(args.amcsd_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    manifest = start_manifest(
        config.data_root / "manifests", SOURCE, {"mode": "single"}, [requested],
    )
    logger = create_logger("crawler.amcsd.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, requested)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": result["status"]})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except LookupError as error:
        append_manifest_item(manifest, {"source_id": requested, "status": "failed", "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[NOT FOUND] %s", requested)
        raise SystemExit(f"AMCSD record not found: {requested}") from error
    except AmcsdError as error:
        append_manifest_item(manifest, {"source_id": requested, "status": "failed", "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[ERROR] %s", error)
        raise
    except Exception as error:
        append_manifest_item(manifest, {"source_id": requested, "status": "failed", "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", requested)
        raise


if __name__ == "__main__":
    main()
