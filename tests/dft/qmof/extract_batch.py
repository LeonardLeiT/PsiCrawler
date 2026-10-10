"""Example: limited-sample download, normalize, and index of QMOF.

Run from the repository root:

    python -m tests.dft.qmof.extract_batch --max-records 5

The property table (about 22 MB) and relaxed-structures archive (about 119 MB)
are downloaded once. Set ``HF_ENDPOINT`` or ``--endpoint`` to use a mirror.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.qmof.normalize import normalize_qmof_record  # noqa: E402
from sources.dft.qmof.download import QmofConfig, iter_records  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "is_magnetic")


def main(max_records: int | None = 5, endpoint: str | None = None) -> None:
    """Stream a limited sample of QMOF into the SQLite index."""
    overrides: dict = {"data_root": Path("data/dft/qmof")}
    if endpoint:
        overrides["endpoint"] = endpoint.rstrip("/")
    config = QmofConfig(**overrides)
    structure_root = config.data_root / "structure"
    raw_path = str(config.csv_path)
    indexed = 0
    errors = 0
    for record in iter_records(config, max_records=max_records):
        try:
            normalized = normalize_qmof_record(
                record, structure_root=structure_root, raw_path=raw_path,
                requested_id=record.get("qmof_id"),
            )
            normalized["raw_path"] = raw_path
            normalized["source_documents"] = {"csv": raw_path, "structures": str(config.structures_path)}
            normalized["download_status"] = "success"
            normalized["properties_requested"] = False
            storage.save(config.database_path, normalized, record, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {normalized['source_id']} {normalized['formula']} gap={normalized['band_gap']} "
                  f"natoms={normalized['atom_count']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {record.get('qmof_id')}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample QMOF extraction.")
    parser.add_argument("--max-records", type=int, default=5)
    parser.add_argument("--endpoint", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.max_records, args.endpoint)
