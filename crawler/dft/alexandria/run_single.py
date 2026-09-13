"""Pipeline entrypoint: fetch one Alexandria record through OPTIMADE.

The bulk archives are the complete source, but a single material is fastest to
retrieve through the OPTIMADE API. If the PBE backend is unavailable, the caller
must fall back to ``run_batch`` on the bulk ``pbe-3d`` dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.alexandria.normalize import normalize_alexandria_optimade
from sources.dft.alexandria.download import (
    AlexandriaConfig,
    AlexandriaError,
    OptimadeClient,
    get_dataset,
    optimade_record_to_document,
    save_json_atomic,
    source_id_for,
)

SOURCE = "alexandria"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")
OPTIMADE_PREFIXES = {"pbe-3d": "pbe", "pbesol": "pbesol", "scan": "scan"}


def extract_single(config: AlexandriaConfig, dataset_name: str, entry_id: str) -> dict:
    """Fetch, normalize, and index one OPTIMADE structure."""
    dataset = get_dataset(dataset_name)
    prefix = OPTIMADE_PREFIXES[dataset_name]
    client = OptimadeClient(config, prefix)
    record = client.fetch_structure(entry_id)
    if record is None:
        raise LookupError(f"Alexandria record not found: {entry_id}")
    document = optimade_record_to_document(record)
    raw_path = save_json_atomic(
        config.raw_dir / "optimade" / dataset.name / f"{Path(entry_id).name}.json", record,
    )
    standard = normalize_alexandria_optimade(
        document,
        dataset=dataset.name,
        functional=dataset.functional,
        dimensionality=dataset.dimensionality,
        structure_root=config.data_root / "structure",
        raw_path=str(raw_path),
        requested_id=entry_id,
    )
    standard["raw_path"] = str(raw_path)
    standard["source_documents"] = {
        "optimade": f"{client.base_url}/structures/{entry_id}",
        "raw": str(raw_path),
    }
    standard["download_status"] = "success"
    standard["properties_requested"] = False
    storage.save(config.database_path, standard, document, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": entry_id,
        "source_id": source_id_for(dataset.name, document.get("id") or entry_id),
        "dataset": dataset.name,
        "structure_path": standard.get("structure_path"),
    }


def parse_args() -> argparse.Namespace:
    """Parse single-record crawler arguments."""
    parser = argparse.ArgumentParser(description="Fetch and normalize one Alexandria OPTIMADE record.")
    parser.add_argument("entry_id", help="Alexandria identifier, for example agm001010489.")
    parser.add_argument("--dataset", choices=sorted(OPTIMADE_PREFIXES), default="pbesol")
    parser.add_argument("--data-root", default="data/dft/alexandria")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    """Run one OPTIMADE lookup and write its manifest."""
    args = parse_args()
    config = AlexandriaConfig(data_root=Path(args.data_root), request_timeout=args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single", "dataset": args.dataset},
        [args.entry_id],
    )
    logger = create_logger("crawler.alexandria.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.dataset, args.entry_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except AlexandriaError as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[ERROR] OPTIMADE request failed: %s", error)
        raise SystemExit(
            "OPTIMADE request failed. The PBE backend can be unavailable; use "
            "'python -m crawler.dft.alexandria.run_batch --dataset pbe-3d' instead."
        ) from error
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.entry_id)
        raise


if __name__ == "__main__":
    main()
