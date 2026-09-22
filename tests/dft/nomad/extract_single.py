"""Example: single NOMAD Archive entry download, normalize, and index.

Run from the repository root:

    python -m tests.dft.nomad.extract_single --0TXFv_aZUPi2bqjewWq3CTSGfc

This is a runnable example, not a unit test.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.nomad.normalize import normalize_nomad_archive  # noqa: E402
from sources.dft.nomad.download import NomadClient, NomadConfig, entry_url, save_json_atomic  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def main(entry_id: str, no_symmetry: bool = False) -> None:
    """Fetch one entry, normalize it, and insert it into the SQLite index."""
    config = NomadConfig()
    client = NomadClient(config)
    document = client.fetch_archive(entry_id)
    data = document.get("data") or {}
    upload_id = data.get("upload_id") or "unknown"
    raw_path = save_json_atomic(config.raw_dir / str(upload_id) / f"{entry_id}.json", document)
    record = normalize_nomad_archive(
        document,
        structure_root=config.data_root / "structure",
        raw_path=str(raw_path),
        requested_id=entry_id,
        derive_symmetry=not no_symmetry,
    )
    record["raw_path"] = str(raw_path)
    record["source_documents"] = {"nomad": entry_url(entry_id), "raw": str(raw_path)}
    record["download_status"] = "success"
    record["properties_requested"] = True
    storage.save(config.database_path, record, document, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {record['source_id']} {record['formula']} gap={record['band_gap']} "
          f"e={record['total_energy']} code={record['code']} raw={raw_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single NOMAD Archive entry extraction.")
    parser.add_argument("entry_id", nargs="?", help="NOMAD entry identifier.")
    parser.add_argument("--entry-id", dest="entry_id_flag", default=None,
                        help="NOMAD entry identifier as a flag; NOMAD ids often start with '--'.")
    parser.add_argument("--no-symmetry", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    entry_id = args.entry_id_flag or args.entry_id
    if not entry_id:
        raise SystemExit("An entry id is required: pass it positionally, with '--', or as --entry-id=<id>.")
    main(entry_id, args.no_symmetry)
