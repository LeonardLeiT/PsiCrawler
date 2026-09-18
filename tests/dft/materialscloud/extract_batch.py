"""Example: limited-sample download, normalize, and index of a Materials Cloud dataset.

Run from the repository root:

    python -m tests.dft.materialscloud.extract_batch --dataset mc2d --max-records 50

This is a runnable example, not a unit test. It pages the OPTIMADE API, normalizes
each record, and indexes it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.materialscloud.normalize import normalize_materialscloud_optimade  # noqa: E402
from sources.dft.materialscloud.download import (  # noqa: E402
    DATASETS,
    MaterialsCloudConfig,
    get_dataset,
    iter_dataset_structures,
)

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def main(dataset_name: str = "mc2d", max_records: int | None = 50, page_limit: int = 100) -> None:
    """Page a limited sample of one dataset into the SQLite index."""
    config = MaterialsCloudConfig()
    dataset = get_dataset(dataset_name)
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for item in iter_dataset_structures(dataset, config, page_limit=page_limit, max_records=max_records):
        try:
            record = normalize_materialscloud_optimade(
                item["document"],
                dataset=dataset.name,
                discover_url=dataset.discover_url,
                functional=dataset.functional,
                dimensionality=dataset.dimensionality,
                structure_root=structure_root,
                requested_id=item["document"].get("id"),
            )
            record["raw_path"] = None
            record["source_documents"] = {"optimade": item["url"], "dataset": dataset.name}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, item["document"],
                         columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} "
                  f"e={record['total_energy']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {item['document'].get('id')}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample Materials Cloud dataset extraction.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="mc2d")
    parser.add_argument("--max-records", type=int, default=50)
    parser.add_argument("--page-limit", type=int, default=100)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.dataset, args.max_records, args.page_limit)
