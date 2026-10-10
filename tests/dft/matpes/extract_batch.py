"""Example: limited-sample stream, normalize, and index of MatPES.

Run from the repository root:

    python -m tests.dft.matpes.extract_batch --function r2scan --max-records 5

The full MatPES files are multi-gigabyte; a limited run transfers only the
consumed lines. Set ``HF_ENDPOINT`` or ``--endpoint`` to use a mirror.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.matpes.normalize import normalize_matpes_entry  # noqa: E402
from sources.dft.matpes.download import DEFAULT_FUNCTION, MatPesConfig, dataset_url, iter_entries  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "formation_energy_per_atom", "spacegroup_number")


def main(function: str = DEFAULT_FUNCTION, max_records: int | None = 5, endpoint: str | None = None) -> None:
    """Stream a limited sample of MatPES into the SQLite index."""
    overrides = {"data_root": Path("data/dft/matpes")}
    if endpoint:
        overrides["endpoint"] = endpoint.rstrip("/")
    config = MatPesConfig(**overrides)
    url = dataset_url(function, config)
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for index, entry in enumerate(iter_entries(function, config, max_records=max_records)):
        try:
            record = normalize_matpes_entry(
                entry, structure_root=structure_root, raw_path=url,
                requested_id=entry.get("matpes_id"),
            )
            record["raw_path"] = url
            record["source_documents"] = {"dataset": function, "url": url, "entry_index": index}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, entry, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} "
                  f"e/atom={record['energy_per_atom']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {entry.get('matpes_id')}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample MatPES extraction.")
    parser.add_argument("--function", default=DEFAULT_FUNCTION, choices=["r2scan", "pbe"])
    parser.add_argument("--max-records", type=int, default=5)
    parser.add_argument("--endpoint", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.function, args.max_records, args.endpoint)
