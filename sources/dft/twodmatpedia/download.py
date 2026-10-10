"""2DMatPedia raw download: the complete database as one JSON Lines file.

2DMatPedia (Centre for Advanced 2D Materials, National University of Singapore)
publishes its whole database as a single downloadable file at
``/static/db.json.gz``. Despite the ``.gz`` suffix and the transport
``Content-Encoding: gzip``, the decoded payload is JSON Lines: one JSON object
per line, one line per material. This module downloads that file and stores it
verbatim as ``data/dft/2dmatpedia/raw/db.json`` (transport encoding removed when
present), then streams its lines entry by entry.

This module never touches the standard schema.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

BASE_URL = "http://www.2dmatpedia.org"
DB_URL = f"{BASE_URL}/static/db.json.gz"
DB_FILENAME = "db.json"
BAND_DB_URL = f"{BASE_URL}/static/2dmatpedia_band.json.tar.gz"
BAND_DB_FILENAME = "2dmatpedia_band.json.tar.gz"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20

GZIP_MAGIC = b"\x1f\x8b"


class TwoDMatPediaError(RuntimeError):
    """Raised when a 2DMatPedia request or file operation fails irrecoverably."""


@dataclass(frozen=True)
class TwoDMatPediaConfig:
    """Runtime settings for one 2DMatPedia download task."""

    data_root: Path = Path("data/dft/2dmatpedia")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for the raw database file."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def source_id_for(material_id: Any) -> str:
    """Build the stable identifier used across the index."""
    return str(material_id).strip()


def db_path(config: TwoDMatPediaConfig | None = None) -> Path:
    """Return the local path of the raw JSON Lines database file."""
    cfg = config or TwoDMatPediaConfig()
    return cfg.raw_dir / DB_FILENAME


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_open(url: str, config: TwoDMatPediaConfig, timeout: int | None = None):
    """Open a URL with the configured user agent and retry policy.

    Client errors (4xx) other than 429 are permanent and raise immediately;
    server errors and network failures are retried with a linear backoff.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": config.user_agent, "Accept-Encoding": "gzip"}
    )
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            return urllib.request.urlopen(request, timeout=timeout or config.request_timeout)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                raise TwoDMatPediaError(f"HTTP {error.code} for {url}: {error.reason}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise TwoDMatPediaError(f"Failed to open {url}: {last_error}")


def http_get_bytes(url: str, config: TwoDMatPediaConfig, timeout: int | None = None) -> bytes:
    """Fetch raw bytes from a URL, removing a gzip transport encoding if present."""
    with _http_open(url, config, timeout=timeout) as response:
        payload = response.read()
    if payload[:2] == GZIP_MAGIC:
        payload = gzip.decompress(payload)
    return payload


def _is_complete(path: Path) -> bool:
    """Return whether a local download target already holds bytes."""
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _quiet_unlink(path: Path) -> None:
    """Remove a temporary file, ignoring races and Windows sharing errors."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def download_db(
    config: TwoDMatPediaConfig | None = None,
    *,
    force: bool = False,
    logger: logging.Logger | None = None,
) -> Path:
    """Download the whole database into ``raw/db.json`` and return its path.

    An existing non-empty file is reused unless ``force`` is set, so repeated
    runs resume by skipping the multi-megabyte transfer.
    """
    cfg = config or TwoDMatPediaConfig()
    target = db_path(cfg)
    if not force and _is_complete(target):
        return target
    payload = http_get_bytes(DB_URL, cfg)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
        os.replace(temporary, target)
    except Exception:
        _quiet_unlink(temporary)
        raise
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", DB_URL, target, target.stat().st_size / (1024 * 1024))
    if cfg.sleep_seconds > 0:
        time.sleep(cfg.sleep_seconds)
    return target


def _looks_like_json(payload: bytes) -> bool:
    """Return whether the payload starts like a JSON object."""
    return payload.lstrip()[:1] == b"{"


# ---------------------------------------------------------------------------
# Entry access
# ---------------------------------------------------------------------------

def iter_entries(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream the JSON Lines entries of one downloaded 2DMatPedia database file."""
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                yield item


def iter_bulk_entries(
    config: TwoDMatPediaConfig | None = None,
    *,
    download_missing: bool = True,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Download the database when needed and stream its entries."""
    cfg = config or TwoDMatPediaConfig()
    path = db_path(cfg)
    if download_missing:
        path = download_db(cfg, logger=logger)
    if not _is_complete(path):
        raise TwoDMatPediaError(f"2DMatPedia database not found: {path}")
    for index, entry in enumerate(iter_entries(path)):
        if max_records is not None and index >= max_records:
            return
        yield entry


def read_entry(
    material_id: str,
    config: TwoDMatPediaConfig | None = None,
    *,
    download_missing: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Read one entry by material identifier, or ``None`` if absent."""
    cfg = config or TwoDMatPediaConfig()
    requested = source_id_for(material_id)
    for entry in iter_bulk_entries(cfg, download_missing=download_missing, logger=logger):
        if source_id_for(entry.get("material_id")) == requested:
            return entry
    return None


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path_value: str | Path, *, source: str = "2dmatpedia",
                 schema_version: str = "3.0"):
        self._database = Path(db_path_value)
        self._source = source
        self._schema_version = schema_version
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self._database.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._database, timeout=30.0)
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA journal_mode=WAL")
            self._connection = connection
        return self._connection

    def is_completed(self, material_id: str) -> bool:
        """Return whether one 2DMatPedia entry is already indexed."""
        row = self._load(source_id_for(material_id))
        if not row:
            return False
        if row["schema_version"] != self._schema_version:
            return False
        if row["download_status"] not in {"success", "partial"}:
            return False
        raw_path = row["raw_path"]
        return bool(raw_path) and Path(raw_path).exists()

    def _load(self, identifier: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT schema_version, download_status, raw_path FROM records "
                "WHERE source = ? AND (source_id = ? OR requested_id = ?)",
                (self._source, identifier, identifier),
            ).fetchone()
        except sqlite3.OperationalError:
            try:
                row = connection.execute(
                    "SELECT schema_version, download_status, raw_path FROM records "
                    "WHERE source = ? AND source_id = ?",
                    (self._source, identifier),
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        if row is None:
            return None
        return {"schema_version": row[0], "download_status": row[1], "raw_path": row[2]}

    def close(self) -> None:
        """Close the read connection if it was opened."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "CompletionIndex":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def completed(
    db_path_value: str | Path,
    material_id: str,
    *,
    source: str = "2dmatpedia",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one 2DMatPedia entry is already indexed."""
    with CompletionIndex(db_path_value, source=source, schema_version=schema_version) as index:
        return index.is_completed(material_id)


__all__ = [
    "BASE_URL",
    "BAND_DB_FILENAME",
    "BAND_DB_URL",
    "DB_FILENAME",
    "DB_URL",
    "CompletionIndex",
    "TwoDMatPediaConfig",
    "TwoDMatPediaError",
    "completed",
    "db_path",
    "download_db",
    "http_get_bytes",
    "iter_bulk_entries",
    "iter_entries",
    "read_entry",
    "source_id_for",
]
