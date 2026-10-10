"""Example: index one QMOF material.

Run from the repository root:

    python -m tests.dft.qmof.extract_single qmof-8a95c27
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.qmof.normalize import normalize_qmof_record  # noqa: E402
from sources.dft.qmof.download import QmofConfig, read_entry  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "is_magnetic")


def main(qmof_id: str, endpoint: str | None = None) -> None:
    """Read one QMOF record and index it."""
    overrides: dict = {"data_root": Path("data/dft/qmof")}
    if endpoint:
        overrides["endpoint"] = endpoint.rstrip("/")
    config = QmofConfig(**overrides)
    record = read_entry(qmof_id, config)
    if record is None:
        raise SystemExit(f"QMOF record not found: {qmof_id}")
    raw_path = str(config.csv_path)
    normalized = normalize_qmof_record(
        record, structure_root=config.data_root / "structure", raw_path=raw_path, requested_id=qmof_id,
    )
    normalized["raw_path"] = raw_path
    normalized["source_documents"] = {"csv": raw_path, "structures": str(config.structures_path)}
    normalized["download_status"] = "success"
    normalized["properties_requested"] = False
    storage.save(config.database_path, normalized, record, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {normalized['source_id']} {normalized['formula']} cif={normalized['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single QMOF extraction.")
    parser.add_argument("qmof_id", help="QMOF identifier, for example qmof-8a95c27.")
    parser.add_argument("--endpoint", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.qmof_id, args.endpoint)
