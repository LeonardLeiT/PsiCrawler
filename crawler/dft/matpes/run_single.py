"""Pipeline entrypoint: fetch one MatPES record by scanning the remote file.

MatPES has no per-record API, so a single material is located by streaming the
selected functional file until the identifier matches. Use ``--max-scan`` to
bound the search on very large files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.matpes.normalize import normalize_matpes_entry
from sources.dft.matpes.download import (
    DEFAULT_FUNCTION,
    FUNCTIONS,
    MatPesConfig,
    dataset_url,
    read_entry,
    source_id_for,
)

SOURCE = "matpes"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "formation_energy_per_atom", "spacegroup_number")


def extract_single(config: MatPesConfig, function: str, matpes_id: str, max_scan: int | None) -> dict:
    """Stream, normalize, and index one MatPES record."""
    entry = read_entry(matpes_id, function, config, max_scan=max_scan)
    if entry is None:
        raise LookupError(f"MatPES record not found: {matpes_id}")
    url = dataset_url(function, config)
    record = normalize_matpes_entry(
        entry, structure_root=config.data_root / "structure", raw_path=url, requested_id=matpes_id,
    )
    record["raw_path"] = url
    record["source_documents"] = {"dataset": function, "url": url}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": matpes_id,
        "source_id": source_id_for(entry.get("matpes_id") or matpes_id),
        "formula": record.get("formula"),
        "structure_path": record.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one MatPES record.")
    parser.add_argument("matpes_id", help="MatPES identifier, for example matpes-20240214_999485_2.")
    parser.add_argument("--function", choices=sorted(FUNCTIONS), default=DEFAULT_FUNCTION)
    parser.add_argument("--data-root", default="data/dft/matpes")
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--max-scan", type=int, default=None, help="Stop after scanning this many lines.")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    """Run one MatPES lookup and write its manifest."""
    args = parse_args()
    overrides = {"data_root": Path(args.data_root), "request_timeout": args.timeout}
    if args.endpoint:
        overrides["endpoint"] = args.endpoint.rstrip("/")
    config = MatPesConfig(**overrides)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single", "function": args.function},
        [args.matpes_id],
    )
    logger = create_logger("crawler.matpes.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.function, args.matpes_id, args.max_scan)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.matpes_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.matpes_id)
        raise


if __name__ == "__main__":
    main()
