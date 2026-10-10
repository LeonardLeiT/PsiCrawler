"""Example: download and index one 2DMatPedia material.

Run from the repository root:

    python -m tests.dft.twodmatpedia.extract_single 2dm-1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.twodmatpedia.normalize import normalize_2dmatpedia_entry  # noqa: E402
from sources.dft.twodmatpedia.download import TwoDMatPediaConfig, db_path, read_entry  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "energy_above_hull", "spacegroup_number")


def main(material_id: str) -> None:
    """Read one 2DMatPedia record and index it."""
    config = TwoDMatPediaConfig()
    entry = read_entry(material_id, config)
    if entry is None:
        raise SystemExit(f"2DMatPedia record not found: {material_id}")
    local = db_path(config)
    record = normalize_2dmatpedia_entry(
        entry, structure_root=config.data_root / "structure", raw_path=str(local),
        requested_id=material_id,
    )
    record["raw_path"] = str(local)
    record["source_documents"] = {"file": local.name}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {record['source_id']} {record['formula']} cif={record['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single 2DMatPedia extraction.")
    parser.add_argument("material_id", help="2DMatPedia identifier, for example 2dm-1.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.material_id)
