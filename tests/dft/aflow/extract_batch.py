"""Example: batch download, normalize, and index AFLOW records.

Run from the repository root:

    python -m tests.dft.aflow.extract_batch --species Li --max 5

This is a runnable example, not a unit test.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.aflow.normalize import normalize_aflow  # noqa: E402
from sources.dft.aflow.download import AflowConfig, build_filter_query, download_one, fetch_aurl_list  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number")


def main(species: str = "Li", maximum: int = 5) -> None:
    """Query AFLUX and index the first matching materials."""
    config = AflowConfig()
    filter_query = build_filter_query(species=species)
    for entry in fetch_aurl_list(filter_query, maximum):
        identifier = entry.get("aurl")
        if not identifier:
            continue
        try:
            result = download_one(identifier, config, "core", query_hit=entry)
            record = normalize_aflow({**result.metadata, "_requested_id": result.source_id}, result.file_paths)
            record["raw_path"] = result.raw_path
            record["source_documents"] = {"files": result.file_paths}
            record["download_status"] = "partial" if result.errors else "success"
            record["properties_requested"] = True
            record["property_errors"] = {str(index): error for index, error in enumerate(result.errors)}
            storage.save(config.database_path, record, result.metadata, columns=field_names(), index_fields=INDEX_FIELDS)
            print(f"[OK] {result.source_id}")
        except Exception as error:
            print(f"[FAIL] {identifier}: {error}")


if __name__ == "__main__":
    main()
