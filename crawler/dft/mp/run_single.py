"""Pipeline entrypoint: download, normalize, and index one Materials Project record."""

from __future__ import annotations

import argparse

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.mp.normalize import normalize_summary
from sources.dft.mp.download import (
    DEFAULT_BS_PATH_TYPES,
    PROPERTY_DOWNLOAD_VERSION,
    MPArtifactsClient,
    MPClient,
    MPConfig,
    completed,
    download_one,
    normalize_mp_id,
    requested_categories,
)

SOURCE = "mp"
SCHEMA_VERSION = "3.0"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "is_stable")


def extract_single(
    config: MPConfig,
    mp_id: int | str,
    include_properties: bool = True,
    *,
    include_files: bool = True,
    include_charge_density: bool = True,
    include_raw_vasp: bool = True,
    bs_path_types: tuple[str, ...] = DEFAULT_BS_PATH_TYPES,
    include_bs_projections: bool = True,
) -> dict:
    """Run the full download/normalize/index pipeline for one material."""
    client = MPClient(config)
    artifacts = MPArtifactsClient(config) if (include_files or include_raw_vasp) else None
    result = download_one(
        client,
        config,
        mp_id,
        include_properties,
        include_files=include_files,
        include_charge_density=include_charge_density,
        include_raw_vasp=include_raw_vasp,
        bs_path_types=bs_path_types,
        include_bs_projections=include_bs_projections,
        artifacts_client=artifacts,
    )
    record = normalize_summary(
        {**result.summary, "_requested_id": result.source_id},
        structure_root=config.data_root / "structure",
        downloaded_files=list(result.file_paths.values()),
        route_documents=result.documents,
    )
    record["raw_path"] = str(result.raw_path)
    record["property_paths"] = result.property_paths or None
    record["elastic_tensor_path"] = result.property_paths.get("elasticity")
    record["property_errors"] = result.property_errors or {}
    record["source_documents"] = {
        "properties": result.property_paths,
        "files": result.file_paths,
        "nomad": result.raw_archive_paths,
        "property_download_version": PROPERTY_DOWNLOAD_VERSION,
        "download_categories": sorted(result.categories),
        "bs_path_types": list(bs_path_types),
    }
    record["download_status"] = result.status
    record["properties_requested"] = include_properties
    storage.save(config.database_path, record, result.summary, columns=field_names(), index_fields=INDEX_FIELDS)
    return {
        "requested_id": result.requested_id,
        "source_id": result.source_id,
        "raw_path": str(result.raw_path),
        "properties": result.properties,
        "property_errors": result.property_errors,
        "files": len(result.file_paths),
        "file_errors": result.file_errors,
        "nomad_archives": len(result.raw_archive_paths),
        "raw_errors": result.raw_errors,
        "download_status": result.status,
        "categories": sorted(result.categories),
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Download and normalize one Materials Project record.")
    parser.add_argument("mp_id", help="Material ID, for example mp-149 or 149.")
    parser.add_argument("--data-root", default="data/dft/mp", help="MP data directory.")
    parser.add_argument("--no-properties", action="store_true", help="Skip per-material REST routes.")
    parser.add_argument("--no-files", action="store_true", help="Skip full pymatgen objects.")
    parser.add_argument("--no-charge-density", action="store_true", help="Skip the CHGCAR artifact.")
    parser.add_argument("--no-raw-vasp", action="store_true", help="Skip the NoMaD raw VASP archives.")
    parser.add_argument("--bs-path-types", default=",".join(DEFAULT_BS_PATH_TYPES),
                        help="Comma-separated band-structure path conventions.")
    parser.add_argument("--no-bandstructure-projections", action="store_true",
                        help="Skip the atom/orbital-projected band structures.")
    parser.add_argument("--force", action="store_true", help="Redownload an already indexed record.")
    return parser.parse_args()


def main() -> None:
    """Run one resumable MP pipeline and write its manifest."""
    args = parse_args()
    config = MPConfig.from_environment(args.data_root)
    include_properties = not args.no_properties
    include_files = not args.no_files
    include_charge_density = not args.no_charge_density
    include_raw_vasp = not args.no_raw_vasp
    include_bs_projections = not args.no_bandstructure_projections
    bs_path_types = tuple(item.strip() for item in args.bs_path_types.split(",") if item.strip())
    categories = requested_categories(
        include_properties=include_properties,
        include_files=include_files,
        include_charge_density=include_charge_density,
        include_raw_vasp=include_raw_vasp,
        include_bs_projections=include_bs_projections,
    )
    material_id = normalize_mp_id(args.mp_id)
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"mode": "single", "properties": include_properties, "files": include_files,
         "charge_density": include_charge_density, "raw_vasp": include_raw_vasp,
         "bs_projections": include_bs_projections, "force": args.force},
        [material_id],
    )
    logger = create_logger("crawler.mp.single", config.data_root / "logs", run_id=manifest["run_id"])
    try:
        if not args.force and completed(config.database_path, material_id, categories=categories, bs_path_types=bs_path_types):
            logger.info("[SKIP] %s already downloaded", material_id)
            append_manifest_item(manifest, {"source_id": material_id, "status": "skipped", "attempts": 0})
            finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 0, "skipped": 1})
            return
        logger.info("[START] %s", material_id)
        result = extract_single(
            config, material_id, include_properties,
            include_files=include_files,
            include_charge_density=include_charge_density,
            include_raw_vasp=include_raw_vasp,
            bs_path_types=bs_path_types,
            include_bs_projections=include_bs_projections,
        )
        status = result["download_status"]
        append_manifest_item(manifest, {"source_id": material_id, "status": status, "attempts": 1, **result})
        logger.info("[%s] %s files=%d nomad=%d", status.upper(), material_id, result["files"], result["nomad_archives"])
        finish_manifest(manifest, {"requested": 1, "success": int(status == "success"), "partial": int(status == "partial"), "failed": 0, "skipped": 0})
        print(result)
    except Exception as error:
        logger.exception("[ERROR] %s", material_id)
        append_manifest_item(manifest, {"source_id": material_id, "status": "failed", "attempts": 1, "error": str(error)})
        finish_manifest(manifest, {"requested": 1, "success": 0, "partial": 0, "failed": 1, "skipped": 0})
        raise


if __name__ == "__main__":
    main()
