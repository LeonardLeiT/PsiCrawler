"""Example: limited-sample query, normalize, and index of Catalysis-Hub systems.

Run from the repository root (requires ``CATALYSIS_HUB_API_KEY``):

    python -m tests.dft.catalysishub.extract_batch --max-records 5

Obtain a free key at https://api-catalysis-hub.slac.stanford.edu/auth/login
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.catalysishub.normalize import normalize_catalysishub_system  # noqa: E402
from sources.dft.catalysishub.download import CatalysisHubConfig, iter_systems  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "total_energy", "spacegroup_number")


def main(max_records: int | None = 5, api_key: str | None = None) -> None:
    """Query a limited sample of Catalysis-Hub systems into the SQLite index."""
    config = CatalysisHubConfig.from_environment()
    if api_key:
        config = CatalysisHubConfig(api_key=api_key, data_root=config.data_root)
    structure_root = config.data_root / "structure"
    raw_dir = config.raw_dir / "systems"
    raw_dir.mkdir(parents=True, exist_ok=True)
    indexed = 0
    errors = 0
    for node in iter_systems(config, max_records=max_records):
        system_id = node.get("id")
        try:
            raw_path = raw_dir / f"{system_id}.json"
            raw_path.write_text(json.dumps(node, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            record = normalize_catalysishub_system(
                node, structure_root=structure_root, raw_path=str(raw_path), requested_id=system_id,
            )
            record["raw_path"] = str(raw_path)
            record["source_documents"] = {"graphql": config.graphql_url}
            record["download_status"] = "success"
            record["properties_requested"] = False
            storage.save(config.database_path, record, node, columns=field_names(), index_fields=INDEX_FIELDS)
            indexed += 1
            print(f"[OK] {record['source_id']} {record['formula']} e={record['total_energy']}")
        except Exception as error:
            errors += 1
            print(f"[FAIL] {system_id}: {error}")
    print(f"indexed={indexed} errors={errors} db={config.database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limited-sample Catalysis-Hub extraction.")
    parser.add_argument("--max-records", type=int, default=5)
    parser.add_argument("--api-key", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.max_records, args.api_key)
