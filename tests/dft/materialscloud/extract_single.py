"""Example: fetch, normalize, and index one Materials Cloud OPTIMADE record.

Run from the repository root:

    python -m tests.dft.materialscloud.extract_single <id> --dataset mc3d-pbesol-v2

This is a runnable example, not a unit test.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from crawler.dft.materialscloud.run_single import extract_single  # noqa: E402
from sources.dft.materialscloud.download import DATASETS, MaterialsCloudConfig  # noqa: E402


def main(entry_id: str, dataset_name: str) -> None:
    """Fetch one OPTIMADE record and index its normalized standard record."""
    config = MaterialsCloudConfig()
    result = extract_single(config, dataset_name, entry_id)
    print(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch one Materials Cloud record.")
    parser.add_argument("entry_id")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="mc3d-pbesol-v2")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.entry_id, args.dataset)
