"""Example: limited-sample download, normalize, and index of AMCSD records.

Run from the repository root:

    python -m tests.dft.amcsd.extract_batch --max-records 5

This is a runnable example, not a unit test. It downloads the official CIF, AMC
and DIF archives if needed, streams entries aligned by AMCSD identifier,
normalizes each record as an experimental structure, and indexes it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.amcsd.normalize import normalize_amcsd_entry  # noqa: E402
from sources.dft.amcsd.download import AmcsdConfig, iter_archive_entries, source_id_for  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "crystal_system", "point_group")


def main(max_records: int | None = 5) -> None:
    """Stream a limited sample of AMCSD entries into the SQLite index."""
    config = AmcsdConfig()
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for entry in iter_archive_entries(config, max_records=max_records):
        archive_paths = entry.get("archive_paths") or {}
        property_paths = {f"{kind}_archive": path for kind, path in archive_paths.items()}
        try:
            record = normalize_amcsd_entry(entry, structure_root=structure_root, property_paths=property_paths)
            record["raw_path"] = archive_paths.get("cif") or next(iter(archive_paths.values()), None)
            record["source_documents"] = {"members": entry.get("members"), "archives": archive_paths}
            status = "success" if record.get("structure") else "partial"
            record["download_status"] = status
            record["properties_requested"] = False
            raw = {
                "amcsd_id": entry["amcsd_id"], "cif": entry.get("cif"),
                "amc": entry.get("amc"), "dif": entry.get("dif"),
            }
            storage.save(config.database_path, record, raw, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            extra = record.get("source_extra") or {}
            print(
                f"[{status}] {record['source_id']} {extra.get('mineral_name')} "
                f"{record.get('formula')} sg={record.get('spacegroup_number')} "
                f"system={record.get('crystal_system')}"
            )
        except Exception as error:
            errors += 1
            print(f"[FAIL] {source_id_for(entry.get('amcsd_id'))}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample AMCSD extraction.")
    parser.add_argument("--max-records", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.max_records)
