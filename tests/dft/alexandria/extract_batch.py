"""Example: limited-sample download, normalize, and index of an Alexandria dataset.

Run from the repository root:

    python -m tests.dft.alexandria.extract_batch --dataset pbe-3d --max-files 1 --max-records 100

This is a runnable example, not a unit test. It streams the bulk archive entry
by entry, normalizes each record, and indexes it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.alexandria.normalize import normalize_alexandria_entry  # noqa: E402
from sources.dft.alexandria.download import (  # noqa: E402
    BASE_URL,
    AlexandriaConfig,
    get_dataset,
    iter_dataset_entries,
)

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def main(dataset_name: str = "pbe-3d", max_files: int | None = 1, max_records: int | None = 100) -> None:
    """Stream a limited sample of one dataset into the SQLite index."""
    config = AlexandriaConfig()
    dataset = get_dataset(dataset_name)
    if not dataset.is_primary:
        raise SystemExit(f"{dataset_name!r} is auxiliary; use the crawler with --download-only.")
    dataset_url = f"{BASE_URL}/{dataset.directory}" if dataset.directory else None
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for item in iter_dataset_entries(dataset, config, max_files=max_files, max_records=max_records):
        entry = item["entry"]
        try:
            record = normalize_alexandria_entry(
                entry,
                dataset=dataset.name,
                dataset_url=dataset_url,
                functional=dataset.functional,
                dimensionality=dataset.dimensionality,
                structure_root=structure_root,
                raw_path=item["raw_path"],
            )
            record["raw_path"] = item["raw_path"]
            record["source_documents"] = {"dataset": dataset.name, "file": item["file"], "entry_index": item["index"]}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} ehull={record['energy_above_hull']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {item['file']}#{item['index']}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample Alexandria dataset extraction.")
    parser.add_argument("--dataset", default="pbe-3d")
    parser.add_argument("--max-files", type=int, default=1)
    parser.add_argument("--max-records", type=int, default=100)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.dataset, args.max_files, args.max_records)
