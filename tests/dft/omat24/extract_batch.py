"""Example: limited-sample download, normalize, and index of OMat24.

Run from the repository root:

    python -m tests.dft.omat24.extract_batch --subset val-rattled-1000-subsampled --max-records 5

The validation subsets are the smallest; ``val-rattled-1000-subsampled`` is about
80 MB and 39,785 rows. The ``1m`` subset is about 2.3 GB.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.omat24.normalize import normalize_omat24_record  # noqa: E402
from sources.dft.omat24.download import DEFAULT_SUBSET, SUBSETS, Omat24Config, iter_records  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "energy_per_atom")


def main(subset: str = DEFAULT_SUBSET, max_records: int | None = 5) -> None:
    """Stream a limited sample of an OMat24 subset into the SQLite index."""
    config = Omat24Config()
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for record in iter_records(subset, config, max_records=max_records):
        data = record.get("data") or {}
        sid = data.get("sid") or f"{subset}:{record.get('row_id')}"
        try:
            raw_path = record.get("db_path")
            normalized = normalize_omat24_record(
                record, structure_root=structure_root, raw_path=raw_path, requested_id=sid,
            )
            normalized["raw_path"] = raw_path
            normalized["source_documents"] = {"subset": subset, "db": raw_path, "row_id": record.get("row_id")}
            normalized["download_status"] = "success"
            normalized["properties_requested"] = False
            storage.save(config.database_path, normalized, data, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {normalized['source_id']} {normalized['formula']} "
                  f"e/atom={normalized['energy_per_atom']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {sid}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample OMat24 extraction.")
    parser.add_argument("--subset", choices=sorted(SUBSETS), default=DEFAULT_SUBSET)
    parser.add_argument("--max-records", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.subset, args.max_records)
