"""Example: index one Catalysis-Hub system.

Run from the repository root (requires ``CATALYSIS_HUB_API_KEY``):

    python -m tests.dft.catalysishub.extract_single <system_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import storage  # noqa: E402
from normalizers.dft import field_names  # noqa: E402
from normalizers.dft.catalysishub.normalize import normalize_catalysishub_system  # noqa: E402
from sources.dft.catalysishub.download import CatalysisHubConfig, read_system  # noqa: E402

INDEX_FIELDS = ("formula", "chemical_system", "total_energy", "spacegroup_number")


def main(system_id: str, api_key: str | None = None) -> None:
    """Fetch one Catalysis-Hub system and index it."""
    config = CatalysisHubConfig.from_environment()
    if api_key:
        config = CatalysisHubConfig(api_key=api_key, data_root=config.data_root)
    node = read_system(system_id, config)
    if node is None:
        raise SystemExit(f"Catalysis-Hub system not found: {system_id}")
    raw_path = config.raw_dir / "systems" / f"{system_id}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(node, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    record = normalize_catalysishub_system(
        node, structure_root=config.data_root / "structure", raw_path=str(raw_path), requested_id=system_id,
    )
    record["raw_path"] = str(raw_path)
    record["source_documents"] = {"graphql": config.graphql_url}
    record["download_status"] = "success"
    record["properties_requested"] = False
    storage.save(config.database_path, record, node, columns=field_names(), index_fields=INDEX_FIELDS)
    print(f"[OK] {record['source_id']} {record['formula']} cif={record['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single Catalysis-Hub extraction.")
    parser.add_argument("system_id", help="Catalysis-Hub system id.")
    parser.add_argument("--api-key", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.system_id, args.api_key)
