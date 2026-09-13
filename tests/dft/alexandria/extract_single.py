"""Example: fetch, normalize, and index one Alexandria record through OPTIMADE.

Run from the repository root:

    python -m tests.dft.alexandria.extract_single agm001010489 --dataset pbesol

This is a runnable example, not a unit test. The PBE OPTIMADE backend can be
unavailable; use the PBEsol endpoint or the bulk dataset instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from crawler.dft.alexandria.run_single import extract_single  # noqa: E402
from sources.dft.alexandria.download import AlexandriaConfig  # noqa: E402


def main(entry_id: str = "agm001010489", dataset: str = "pbesol") -> None:
    """Fetch one OPTIMADE record and index it."""
    config = AlexandriaConfig()
    result = extract_single(config, dataset, entry_id)
    print(f"[OK] {result['source_id']} dataset={result['dataset']} structure_path={result['structure_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single Alexandria OPTIMADE extraction.")
    parser.add_argument("entry_id", nargs="?", default="agm001010489")
    parser.add_argument("--dataset", default="pbesol", choices=["pbe-3d", "pbesol", "scan"])
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.entry_id, args.dataset)
