"""Example: fetch, normalize, and index one AMCSD record.

Run from the repository root:

    python -m tests.dft.amcsd.extract_single 0000130

This is a runnable example, not a unit test. AMCSD has no public per-record API,
so the record is extracted from the official bulk archives, which are downloaded
on demand if they are not already present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from crawler.dft.amcsd.run_single import extract_single  # noqa: E402
from sources.dft.amcsd.download import AmcsdConfig, normalize_amcsd_id  # noqa: E402


def main(amcsd_id: str = "0000130") -> None:
    """Fetch one AMCSD record and index it."""
    config = AmcsdConfig()
    result = extract_single(config, normalize_amcsd_id(amcsd_id))
    print(
        f"[{result['status']}] {result['source_id']} "
        f"structure_path={result['structure_path']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single AMCSD extraction.")
    parser.add_argument("amcsd_id", nargs="?", default="0000130")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.amcsd_id)
