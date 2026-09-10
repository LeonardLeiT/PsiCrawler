"""Filesystem and SQLite storage for Materials Project records."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .structure import write_cif
from .config import MPConfig


SEARCH_FIELDS = (
    "source", "source_id", "formula", "chemical_system", "elements", "atom_count",
    "density", "volume", "crystal_system", "spacegroup_number", "spacegroup_symbol",
    "energy_per_atom", "formation_energy_per_atom", "energy_above_hull", "is_stable",
    "band_gap", "is_metal", "is_gap_direct", "fermi_level", "bulk_modulus", "shear_modulus",
    "poisson_ratio", "total_magnetization",
)


def ensure_storage(config: MPConfig) -> None:
    """Create MP data directories and initialize the SQLite search index.

    Args:
        config (MPConfig): MP storage configuration.
    """
    for directory in (
        config.raw_dir,
        config.normalized_dir,
        config.database_path.parent,
        config.manifest_dir,
        config.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.database_path) as connection:
        fields = ", ".join(f"{field} TEXT" for field in SEARCH_FIELDS)
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS materials ({fields}, record_path TEXT, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (source_id))"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_mp_formula ON materials(formula)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_mp_chemical_system ON materials(chemical_system)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_mp_band_gap ON materials(band_gap)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_mp_energy_above_hull ON materials(energy_above_hull)")


def record_is_complete(config: MPConfig, mp_id: str, include_properties: bool = True) -> bool:
    """Return whether a requested MP record can be safely skipped.

    Args:
        config (MPConfig): MP storage configuration.
        mp_id (str): Requested MP identifier.
        include_properties (bool): Whether professional routes are required.

    Returns:
        bool: True only when the record and requested route set completed successfully.
    """
    record_path = config.normalized_dir / mp_id / "record.json"
    raw_path = config.raw_dir / mp_id / "summary.json"
    if not record_path.exists() or not raw_path.exists():
        return False
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        record.get("download_status") == "success"
        and not record.get("property_errors")
        and (not include_properties or record.get("properties_requested") is True)
    )

def save_record(config: MPConfig, raw: dict[str, Any], normalized: dict[str, Any]) -> Path:
    """Save raw and normalized JSON, then upsert the searchable index.

    Args:
        config (MPConfig): MP storage configuration.
        raw (dict[str, Any]): Original API response document.
        normalized (dict[str, Any]): Unified record from the schema engine.

    Returns:
        Path: Path to the normalized JSON record.
    """
    source_id = normalized["source_id"]
    record_id = normalized.get("requested_id") or source_id
    raw_record_dir = config.raw_dir / record_id
    normalized_record_dir = config.normalized_dir / record_id
    raw_record_dir.mkdir(parents=True, exist_ok=True)
    normalized_record_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_record_dir / "summary.json"
    normalized_path = normalized_record_dir / "record.json"
    normalized["raw_path"] = str(raw_path)
    normalized["normalized_path"] = str(normalized_path)
    structure = normalized.get("structure")
    if structure is not None:
        structure_json_path = config.raw_dir / record_id / "structure.json"
        structure_json_path.parent.mkdir(parents=True, exist_ok=True)
        structure_json_path.write_text(
            json.dumps(structure, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        structure_cif_path = write_cif(structure, config.raw_dir / record_id / "structure.cif")
        normalized["structure_json_path"] = str(structure_json_path)
        normalized["structure_path"] = str(structure_cif_path)
        normalized["structure_format"] = ["cif", "json"]
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    values = []
    for field in SEARCH_FIELDS:
        value = normalized.get(field)
        values.append(json.dumps(value, ensure_ascii=False) if field == "elements" else value)
    with sqlite3.connect(config.database_path) as connection:
        columns = ", ".join(SEARCH_FIELDS) + ", record_path"
        placeholders = ", ".join("?" for _ in range(len(SEARCH_FIELDS) + 1))
        updates = ", ".join(
            f"{field}=excluded.{field}" for field in SEARCH_FIELDS if field != "source_id"
        ) + ", record_path=excluded.record_path"
        connection.execute(
            f"INSERT INTO materials ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(source_id) DO UPDATE SET {updates}",
            values + [str(normalized_path)],
        )
    return normalized_path


def save_property(
    config: MPConfig,
    source_id: str,
    endpoint: str,
    documents: list[dict[str, Any]],
) -> Path | None:
    """Save source-specific property documents without flattening them.

    Args:
        config (MPConfig): MP storage configuration.
        source_id (str): Materials Project material identifier.
        endpoint (str): Property endpoint name.
        documents (list[dict[str, Any]]): Raw property documents.

    Returns:
        Path | None: Written file path, or ``None`` when no document exists.
    """
    if not documents:
        return None
    property_dir = config.raw_dir / source_id / "properties"
    property_dir.mkdir(parents=True, exist_ok=True)
    path = property_dir / f"{endpoint}.json"
    path.write_text(json.dumps(documents, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path











