"""Write-only SQLite index for normalized standard records.

This module only saves records. Callers pass the standard column list together
with any index fields; reading and completeness decisions live in each source.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

INDEXED_AT = "indexed_at"
_INIT_LOCK = threading.Lock()
_INITIALIZED: set[str] = set()


def save(
    db_path: str | Path,
    record: dict[str, Any],
    raw: Any,
    *,
    columns: Iterable[str] | None = None,
    index_fields: Iterable[str] = (),
) -> None:
    """Ensure the shared table exists, then insert or replace one record.

    Args:
        db_path (str | Path): SQLite database path.
        record (dict[str, Any]): Complete normalized record.
        raw (Any): Raw source document used for the content hash.
        columns (Iterable[str] | None): Standard columns to create; defaults to
            the record keys.
        index_fields (Iterable[str]): Columns that receive a search index.
    """
    if "source" not in record or "source_id" not in record:
        raise ValueError("record must contain source and source_id")
    database = Path(db_path)
    _initialize(database, list(columns) if columns is not None else list(record), tuple(index_fields))
    payload = dict(record)
    payload["content_hash"] = _content_hash(raw)
    payload[INDEXED_AT] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect(database)) as connection, connection:
        table_columns = [row[1] for row in connection.execute("PRAGMA table_info(records)")]
        stored = [name for name in table_columns if name in payload]
        values = [_serialize(payload[name]) for name in stored]
        placeholders = ", ".join("?" for _ in stored)
        updates = ", ".join(f'"{name}"=excluded."{name}"' for name in stored if name not in ("source", "source_id"))
        columns_sql = ", ".join(f'"{name}"' for name in stored)
        statement = (
            f'INSERT INTO records ({columns_sql}) VALUES ({placeholders}) '
            f'ON CONFLICT(source, source_id) DO UPDATE SET {updates}'
        )
        _execute_with_retry(connection, statement, values)


def _initialize(database: Path, columns: list[str], index_fields: tuple[str, ...]) -> None:
    """Create or evolve the table once per process and database path."""
    key = str(database.resolve())
    with _INIT_LOCK:
        if key in _INITIALIZED:
            return
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(_connect(database)) as connection, connection:
            connection.execute(
                'CREATE TABLE IF NOT EXISTS records ('
                '"source" TEXT NOT NULL, "source_id" TEXT NOT NULL, '
                f'"{INDEXED_AT}" TEXT, PRIMARY KEY (source, source_id))'
            )
            existing = {row[1] for row in connection.execute("PRAGMA table_info(records)")}
            for name in ("source", "source_id", *columns, INDEXED_AT):
                if name not in existing:
                    try:
                        connection.execute(f'ALTER TABLE records ADD COLUMN "{name}" TEXT')
                    except sqlite3.OperationalError as error:
                        # A concurrent process may have added the same column first.
                        if "duplicate column name" not in str(error).lower():
                            raise
            for name in index_fields:
                if name in columns or name in existing:
                    connection.execute(f'CREATE INDEX IF NOT EXISTS "idx_records_{name}" ON records("{name}")')
        _INITIALIZED.add(key)


def _connect(database: Path) -> sqlite3.Connection:
    """Open a connection configured for concurrent writers."""
    connection = sqlite3.connect(database, timeout=30.0)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def _execute_with_retry(connection: sqlite3.Connection, statement: str, values: list[Any], attempts: int = 5) -> None:
    """Retry a write that lost a SQLite lock race."""
    for attempt in range(attempts):
        try:
            connection.execute(statement, values)
            return
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).lower() or attempt == attempts - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def _content_hash(raw: Any) -> str:
    """Return the canonical SHA-256 of a raw source document.

    Non-finite floats are permitted because upstream archives legitimately
    contain ``NaN`` (for example relaxed forces); rejecting them would silently
    drop otherwise valid records.
    """
    payload = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _serialize(value: Any) -> Any:
    """Store scalars as-is and JSON-encode structured values."""
    if value is None or isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, ensure_ascii=False)
