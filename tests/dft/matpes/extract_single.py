"""Example: index one MatPES material by scanning the remote file.

Run from the repository root:

    python -m tests.dft.matpes.extract_single matpes-20240214_999485_2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.matpes.normalize import normalize_matpes_entry  # noqa: E402
from sources.dft.matpes.download import DEFAULT_FUNCTION, MatPesConfig, dataset_url, read_entry  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "formation_energy_per_atom", "spacegroup_number")


def main(matpes_id: str, function: str = DEFAULT_FUNCTION, endpoint: str | None = None, max_scan: int | None = None) -> None:
    """Read one MatPES record and index it."""
    overrides = {"data_root": Path("data/dft/matpes")}
    if endpoint:
        overrides["endpoint"] = endpoint.rstrip("/")
    config = MatPesConfig(**overrides)
    entry = read_entry(matpes_id, function, config, max_scan=max_scan)
    if entry is None:
        raise SystemExit(f"MatPES record not found: {matpes_id}")
    url = dataset_url(function, config)
    record = normalize_matpes_entry(
        entry, structure_root=config.data_root / "structure", raw_path=url, requested_id=matpes_id,
    )
    record["raw_path"] = url
    record["source_documents"] = {"dataset": function, "url": url}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {record['source_id']} {record['formula']} cif={record['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single MatPES extraction.")
    parser.add_argument("matpes_id", help="MatPES identifier, for example matpes-20240214_999485_2.")
    parser.add_argument("--function", default=DEFAULT_FUNCTION, choices=["r2scan", "pbe"])
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--max-scan", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.matpes_id, args.function, args.endpoint, args.max_scan)
