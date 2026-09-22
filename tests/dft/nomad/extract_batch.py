"""Example: limited-sample NOMAD Archive download, normalize, and index.

Run from the repository root:

    python -m tests.dft.nomad.extract_batch --scope dft --max-records 20

This is a runnable example, not a unit test. It pages ``entries/query``, fetches
each archive document, normalizes it, and indexes it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.nomad.normalize import normalize_nomad_archive  # noqa: E402
from sources.dft.nomad.download import NomadConfig, iter_archive_documents  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def main(scope: str = "dft", max_records: int | None = 20, page_size: int = 100,
         no_symmetry: bool = False) -> None:
    """Page a limited sample of the archive into the SQLite index."""
    config = NomadConfig(page_size=page_size)
    query = {"domain": "dft"} if scope == "dft" else {}
    structure_root = config.data_root / "structure"
    indexed = 0
    errors = 0
    for item in iter_archive_documents(config, query=query, page_size=page_size, max_records=max_records):
        try:
            record = normalize_nomad_archive(
                item["document"],
                structure_root=structure_root,
                raw_path=item.get("raw_path"),
                requested_id=item["entry_id"],
                derive_symmetry=not no_symmetry,
            )
            record["raw_path"] = item.get("raw_path")
            record["source_documents"] = {"nomad": item["url"], "raw": item.get("raw_path"),
                                          "entry_id": item["entry_id"], "upload_id": item["upload_id"]}
            record["download_status"] = "success"
            record["properties_requested"] = True
            storage.save(config.database_path, record, item["document"],
                         columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} "
                  f"e={record['total_energy']} code={record['code']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {item['entry_id']}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample NOMAD Archive extraction.")
    parser.add_argument("--scope", choices=("dft", "all"), default="dft")
    parser.add_argument("--max-records", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--no-symmetry", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.scope, args.max_records, args.page_size, args.no_symmetry)
