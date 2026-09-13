"""Example: download, normalize, and index one AFLOW record.

Run from the repository root:

    python -m tests.dft.aflow.extract_single

This is a runnable example, not a unit test.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.aflow.normalize import normalize_aflow  # noqa: E402
from sources.dft.aflow.download import DEFAULT_AURL, AflowConfig, download_one  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number")


def main(identifier: str = DEFAULT_AURL, profile: str = "all") -> None:
    """Download one material, normalize it, and write it to the index."""
    config = AflowConfig()
    result = download_one(identifier, config, profile)
    record = normalize_aflow({**result.metadata, "_requested_id": result.source_id}, result.file_paths)
    record["raw_path"] = result.raw_path
    record["source_documents"] = {"files": result.file_paths}
    record["download_status"] = "partial" if result.errors else "success"
    record["properties_requested"] = True
    record["property_errors"] = {str(index): error for index, error in enumerate(result.errors)}
    storage.save(config.database_path, record, result.metadata, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"{result.source_id} -> raw={result.raw_path} files={len(result.file_paths)} db={config.database_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AURL)
