"""Example: index one OMat24 row by sid or integer row id.

Run from the repository root:

    python -m tests.dft.omat24.extract_single <sid_or_row_id> --subset val-rattled-1000-subsampled
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.omat24.normalize import normalize_omat24_record  # noqa: E402
from sources.dft.omat24.download import DEFAULT_SUBSET, SUBSETS, Omat24Config, read_entry  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "spacegroup_number", "energy_per_atom")


def main(record_id: str, subset: str = DEFAULT_SUBSET) -> None:
    """Read one OMat24 row and index it."""
    config = Omat24Config()
    record = read_entry(record_id, subset, config)
    if record is None:
        raise SystemExit(f"OMat24 record not found in {subset}: {record_id}")
    data = record.get("data") or {}
    sid = data.get("sid") or f"{subset}:{record.get('row_id')}"
    raw_path = record.get("db_path")
    normalized = normalize_omat24_record(
        record, structure_root=config.data_root / "structure", raw_path=raw_path, requested_id=sid,
    )
    normalized["raw_path"] = raw_path
    normalized["source_documents"] = {"subset": subset, "db": raw_path, "row_id": record.get("row_id")}
    normalized["download_status"] = "success"
    normalized["properties_requested"] = False
    storage.save(config.database_path, normalized, data, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {normalized['source_id']} {normalized['formula']} cif={normalized['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single OMat24 extraction.")
    parser.add_argument("record_id", help="OMat24 sid or integer row id.")
    parser.add_argument("--subset", choices=sorted(SUBSETS), default=DEFAULT_SUBSET)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.record_id, args.subset)
