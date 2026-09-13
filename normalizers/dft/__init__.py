"""DFT standard contract and per-source normalization."""

from pathlib import Path

import yaml

STANDARD_PATH = Path(__file__).resolve().parent / "standard.yaml"


def load_standard() -> dict:
    """Load the shared DFT standard contract."""
    with STANDARD_PATH.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def field_names() -> list[str]:
    """Return the ordered standard field names."""
    return list(load_standard().get("fields", {}))


PER_ATOM_PAIRS = (
    ("total_energy", "energy_per_atom"),
    ("formation_energy", "formation_energy_per_atom"),
    ("total_magnetization", "magnetization_per_atom"),
)


def fill_derived_pairs(record: dict) -> dict:
    """Fill missing total/per-atom partners from the available side.

    Uses ``atom_count`` as the divisor. A field that already carries a value is
    left untouched; a missing or non-positive ``atom_count`` disables filling.
    """
    count = record.get("atom_count")
    if not isinstance(count, (int, float)) or isinstance(count, bool) or count <= 0:
        return record
    for total_key, per_key in PER_ATOM_PAIRS:
        total = record.get(total_key)
        per = record.get(per_key)
        if total is None and per is not None:
            record[total_key] = float(per) * float(count)
        elif per is None and total is not None:
            record[per_key] = float(total) / float(count)
    return record


__all__ = ["STANDARD_PATH", "fill_derived_pairs", "field_names", "load_standard"]
