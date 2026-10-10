"""Example: limited-sample download, normalize, and index of 2DMatPedia.

Run from the repository root:

    python -m tests.dft.twodmatpedia.extract_batch --max-records 5

This is a runnable example, not a unit test.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.twodmatpedia.normalize import normalize_2dmatpedia_entry  # noqa: E402
from sources.dft.twodmatpedia.download import TwoDMatPediaConfig, download_db, iter_entries  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def main(max_records: int | None = 5) -> None:
    """Stream a limited sample of 2DMatPedia into the SQLite index."""
    config = TwoDMatPediaConfig()
    local = download_db(config)
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for index, entry in enumerate(iter_entries(local)):
        if max_records is not None and index >= max_records:
            break
        try:
            record = normalize_2dmatpedia_entry(
                entry, structure_root=structure_root, raw_path=str(local),
                requested_id=entry.get("material_id"),
            )
            record["raw_path"] = str(local)
            record["source_documents"] = {"file": local.name, "entry_index": index}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} "
                  f"ehull={record['energy_above_hull']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {entry.get('material_id')}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample 2DMatPedia extraction.")
    parser.add_argument("--max-records", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.max_records)
