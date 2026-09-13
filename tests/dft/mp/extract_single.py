"""Example: completely download, normalize, and index one Materials Project record.

Run from the repository root:

    python -m tests.dft.mp.extract_single mp-149

This is a runnable example, not a unit test. It downloads every REST route,
full pymatgen objects, the NoMaD raw VASP archives, and charge density, then
normalizes and indexes the record.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.mp.normalize import normalize_summary  # noqa: E402
from sources.dft.mp.download import MPArtifactsClient, MPClient, MPConfig, download_one  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "is_stable")


def main(mp_id: str = "mp-149", include_properties: bool = True) -> None:
    """Download one material, normalize it, and write it to the index."""
    config = MPConfig.from_environment()
    artifacts = MPArtifactsClient(config)
    result = download_one(MPClient(config), config, mp_id, include_properties, artifacts_client=artifacts)
    record = normalize_summary({**result.summary, "_requested_id": result.source_id})
    record["raw_path"] = str(result.raw_path)
    record["property_paths"] = result.property_paths or None
    record["property_errors"] = result.property_errors or {}
    record["source_documents"] = {"properties": result.property_paths, "files": result.file_paths, "nomad": result.raw_archive_paths}
    record["download_status"] = result.status
    record["properties_requested"] = include_properties
    storage.save(config.database_path, record, result.summary, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"{result.source_id}: routes={len(result.property_paths)} files={len(result.file_paths)} "
          f"nomad={len(result.raw_archive_paths)} status={result.status} raw={result.raw_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mp-149")
