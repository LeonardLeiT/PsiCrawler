"""Materials Project structure conversion helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pymatgen.core import Structure
from pymatgen.io.cif import CifWriter


def write_cif(structure: dict[str, Any], path: str | Path) -> Path:
    """Convert an MP structure dictionary to CIF and write it to disk.

    Args:
        structure (dict[str, Any]): Structure document returned by MP.
        path (str | Path): Destination CIF path.

    Returns:
        Path: Written CIF path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cif_text = str(CifWriter(Structure.from_dict(structure)))
    destination.write_text(cif_text, encoding="utf-8")
    return destination

