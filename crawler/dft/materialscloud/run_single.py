"""Pipeline entrypoint: fetch one Materials Cloud record through OPTIMADE.

The identifier is the OPTIMADE structure id of the selected child database. The
raw record is preserved under ``raw/<dataset>/optimade/<id>.json`` and the
normalized standard record is indexed in SQLite.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.materialscloud.normalize import normalize_materialscloud_optimade
from sources.dft.materialscloud.download import (
    DATASETS,
    MaterialsCloudConfig,
    MaterialsCloudError,
    OptimadeClient,
    get_dataset,
    optimade_record_to_document,
    save_json_atomic,
    source_id_for,
)

SOURCE = "materialscloud"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def extract_single(config: MaterialsCloudConfig, dataset_name: str, entry_id: str) -> dict:
    """Fetch, normalize, and index one OPTIMADE structure."""
    dataset = get_dataset(dataset_name)
    client = OptimadeClient(config, dataset)
    record = client.fetch_structure(entry_id)
    if record is None:
        raise LookupError(f"Materials Cloud record not found: {entry_id} in {dataset_name}")
    document = optimade_record_to_document(record)
    raw_path = save_json_atomic(
        config.raw_dir / dataset.name / "optimade" / f"{Path(entry_id).name}.json", record,
    )
    standard = normalize_materialscloud_optimade(
        document,
        dataset=dataset.name,
        discover_url=dataset.discover_url,
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
    parser = argparse.ArgumentParser(description="Fetch and normalize one Materials Cloud OPTIMADE record.")
    parser.add_argument("entry_id", help="OPTIMADE structure id of the selected dataset.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="mc3d-pbesol-v2")
    parser.add_argument("--data-root", default="data/dft/materialscloud")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    """Run one OPTIMADE lookup and write its manifest."""
    args = parse_args()
    config = MaterialsCloudConfig(data_root=Path(args.data_root), request_timeout=args.timeout)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single", "dataset": args.dataset},
        [args.entry_id],
    )
    logger = create_logger("crawler.materialscloud.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        result = extract_single(config, args.dataset, args.entry_id)
        append_manifest_item(manifest, {"source_id": result["source_id"], "status": "success", "attempts": 1})
        finish_manifest(manifest, {"requested": 1, "success": 1, "failed": 0})
        logger.info("[OK] %s", result["source_id"])
        print(result)
    except MaterialsCloudError as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.error("[ERROR] OPTIMADE request failed: %s", error)
        raise SystemExit(
            "OPTIMADE request failed. Use "
            "'python -m crawler.dft.materialscloud.run_batch --dataset "
            f"{args.dataset}' to page the dataset instead."
        ) from error
    except Exception as error:
        append_manifest_item(manifest, {"source_id": args.entry_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "failed": 1})
        logger.exception("[ERROR] %s", args.entry_id)
        raise


if __name__ == "__main__":
    main()
