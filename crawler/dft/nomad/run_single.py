"""Pipeline entrypoint: fetch one NOMAD Archive entry.

The identifier is the NOMAD ``entry_id``. The processed archive document is
preserved under ``raw/<upload_id>/<entry_id>.json`` and the normalized standard
record is indexed in SQLite.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.nomad.normalize import normalize_nomad_archive
from sources.dft.nomad.download import (
    NomadClient,
    NomadConfig,
    NomadError,
    default_data_root,
    entry_url,
    save_json_atomic,
    source_id_for,
)

SOURCE = "nomad"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def extract_single(config: NomadConfig, entry_id: str, *, derive_symmetry: bool = True) -> dict:
    """Fetch, normalize, and index one NOMAD archive entry."""
    client = NomadClient(config)
    document = client.fetch_archive(entry_id)
    data = document.get("data") or {}
    upload_id = data.get("upload_id") or "unknown"
    raw_path = save_json_atomic(config.raw_dir / str(upload_id) / f"{entry_id}.json", document)
    standard = normalize_nomad_archive(
        document,
        structure_root=config.data_root / "structure",
        raw_path=str(raw_path),
        requested_id=entry_id,
        derive_symmetry=derive_symmetry,
    )
    standard["raw_path"] = str(raw_path)
    standard["source_documents"] = {
        "nomad": entry_url(entry_id),
        "raw": str(raw_path),
        "entry_id": entry_id,
        "upload_id": upload_id,
    }
    standard["download_status"] = "success"
    standard["properties_requested"] = True
    storage.save(config.database_path, standard, document, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": entry_id,
        "source_id": source_id_for(entry_id),
        "structure_path": standard.get("structure_path"),
        "raw_path": str(raw_path),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one NOMAD Archive entry.")
    parser.add_argument("entry_id", nargs="?", help="NOMAD entry identifier.")
    parser.add_argument("--entry-id", dest="entry_id_flag", default=None,
                        help="NOMAD entry identifier as a flag; NOMAD ids often start with '--'.")
    parser.add_argument("--data-root", default=None,
                        help="Output directory; defaults to NOMAD_DATA_ROOT or data/dft/nomad.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-symmetry", action="store_true",
                        help="Skip spglib space-group derivation for speed.")
    return parser.parse_args()


def main() -> None:
    """Run one NOMAD lookup and write its manifest."""
    args = parse_args()
    entry_id = args.entry_id_flag or args.entry_id
    if not entry_id:
        raise SystemExit("An entry id is required: pass it positionally, with '--', or as --entry-id=<id>.")
    args.entry_id = entry_id
    data_root = Path(args.data_root) if args.data_root else default_data_root()
    config = NomadConfig(data_root=data_root, request_timeout=args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single"},
        [args.entry_id],
    )
    logger = create_logger("crawler.nomad.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.entry_id, derive_symmetry=not args.no_symmetry)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except NomadError as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[ERROR] NOMAD request failed: %s", error)
        raise SystemExit(
            "NOMAD request failed. Use 'python -m crawler.dft.nomad.run_batch --max-records 100' "
            "to page the archive instead."
        ) from error
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.entry_id)
        raise


if __name__ == "__main__":
    main()
