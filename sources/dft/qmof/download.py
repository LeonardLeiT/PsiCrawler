"""QMOF raw download: property table plus relaxed crystal structures.

QMOF (Quantum MOF Database) publishes its release as ``qmof.csv`` (properties),
``qmof.json`` (full records), and per-MOF relaxed CIFs in
``relaxed_structures.zip``. This module retrieves the CSV and the CIF archive
from Hugging Face (a community mirror carrying the official release files) and
streams one record at a time by joining a CSV row with its CIF.

The Hugging Face endpoint defaults to ``https://huggingface.co`` and can be
pointed at a mirror with the ``HF_ENDPOINT`` environment variable.
"""

from __future__ import annotations

import csv
import logging
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

DEFAULT_ENDPOINT = "https://huggingface.co"
try:  # honour HF_ENDPOINT from a local .env when python-dotenv is available
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
DEFAULT_ENDPOINT = os.environ.get("HF_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")
REPO = "vickie02736/QMOF_dataset"
CSV_FILE = "qmof_database/qmof.csv"
STRUCTURES_FILE = "qmof_database/relaxed_structures.zip"
CIF_MEMBER_TEMPLATE = "relaxed_structures/{qmof_id}.cif"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SLEEP_SECONDS = 0.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20


class QmofError(RuntimeError):
    """Raised when a QMOF request or archive operation fails irrecoverably."""


@dataclass(frozen=True)
class QmofConfig:
    """Runtime settings for one QMOF download task."""

    data_root: Path = Path("data/dft/qmof")
    endpoint: str = DEFAULT_ENDPOINT
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for source files."""
        return self.data_root / "raw"

    @property
    def csv_path(self) -> Path:
        """Return the local property-table path."""
        return self.raw_dir / "qmof.csv"

    @property
    def structures_path(self) -> Path:
        """Return the local relaxed-structures archive path."""
        return self.raw_dir / "relaxed_structures.zip"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def source_id_for(qmof_id: Any) -> str:
    """Build the stable identifier used across the index."""
    return str(qmof_id).strip()


def dataset_url(relative: str, config: QmofConfig | None = None) -> str:
    """Return the resolve URL for one QMOF release file."""
    cfg = config or QmofConfig()
    return f"{cfg.endpoint}/datasets/{REPO}/resolve/main/{relative}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_open(url: str, config: QmofConfig, timeout: int | None = None):
    """Open a URL with the configured user agent and retry policy."""
    request = urllib.request.Request(url, headers={"User-Agent": config.user_agent})
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            return urllib.request.urlopen(request, timeout=timeout or config.request_timeout)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                raise QmofError(f"HTTP {error.code} for {url}: {error.reason}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise QmofError(f"Failed to open {url}: {last_error}")


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


def download_asset(
    relative: str,
    target: Path,
    config: QmofConfig | None = None,
    *,
    force: bool = False,
    logger: logging.Logger | None = None,
) -> Path:
    """Download one release file into place, resuming when already present."""
    cfg = config or QmofConfig()
    if not force and _is_complete(target):
        return target
    url = dataset_url(relative, cfg)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    try:
        with _http_open(url, cfg) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=READ_CHUNK_BYTES)
        os.replace(temporary, target)
    except Exception:
        _quiet_unlink(temporary)
        raise
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", url, target, target.stat().st_size / (1024 * 1024))
    if cfg.sleep_seconds > 0:
        time.sleep(cfg.sleep_seconds)
    return target


def ensure_assets(config: QmofConfig | None = None, *, force: bool = False,
                  logger: logging.Logger | None = None) -> tuple[Path, Path]:
    """Download the property table and relaxed-structures archive."""
    cfg = config or QmofConfig()
    csv_path = download_asset(CSV_FILE, cfg.csv_path, cfg, force=force, logger=logger)
    zip_path = download_asset(STRUCTURES_FILE, cfg.structures_path, cfg, force=force, logger=logger)
    return csv_path, zip_path


# ---------------------------------------------------------------------------
# Entry access
# ---------------------------------------------------------------------------

def iter_csv_rows(path: str | Path) -> Iterator[dict[str, str]]:
    """Yield the property table as dictionaries keyed by dotted column name."""
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            yield row


def iter_records(
    config: QmofConfig | None = None,
    *,
    download_missing: bool = True,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream QMOF records, each joining one CSV row with its relaxed CIF.

    Yields:
        dict[str, Any]: ``{"qmof_id", "row", "cif", "index"}``.
    """
    cfg = config or QmofConfig()
    csv_path, zip_path = cfg.csv_path, cfg.structures_path
    if download_missing:
        csv_path, zip_path = ensure_assets(cfg, logger=logger)
    if not _is_complete(csv_path) or not _is_complete(zip_path):
        raise QmofError(f"QMOF assets missing: {csv_path}, {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        for index, row in enumerate(iter_csv_rows(csv_path)):
            if max_records is not None and index >= max_records:
                return
            qmof_id = row.get("qmof_id")
            if not qmof_id:
                continue
            member = CIF_MEMBER_TEMPLATE.format(qmof_id=qmof_id)
            cif = archive.read(member).decode("utf-8", errors="replace") if member in names else None
            yield {"qmof_id": qmof_id, "row": row, "cif": cif, "index": index}


def read_entry(
    qmof_id: str,
    config: QmofConfig | None = None,
    *,
    download_missing: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Read one QMOF record by identifier, or ``None`` if absent."""
    cfg = config or QmofConfig()
    requested = source_id_for(qmof_id)
    for record in iter_records(cfg, download_missing=download_missing, logger=logger):
        if source_id_for(record["qmof_id"]) == requested:
            return record
    return None


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path_value: str | Path, *, source: str = "qmof",
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

    def is_completed(self, qmof_id: str) -> bool:
        """Return whether one QMOF entry is already indexed."""
        row = self._load(source_id_for(qmof_id))
        if not row:
            return False
        return row["schema_version"] == self._schema_version and row["download_status"] in {"success", "partial"}

    def _load(self, identifier: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT schema_version, download_status FROM records "
                "WHERE source = ? AND (source_id = ? OR requested_id = ?)",
                (self._source, identifier, identifier),
            ).fetchone()
        except sqlite3.OperationalError:
            try:
                row = connection.execute(
                    "SELECT schema_version, download_status FROM records "
                    "WHERE source = ? AND source_id = ?",
                    (self._source, identifier),
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        if row is None:
            return None
        return {"schema_version": row[0], "download_status": row[1]}

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
    qmof_id: str,
    *,
    source: str = "qmof",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one QMOF entry is already indexed."""
    with CompletionIndex(db_path_value, source=source, schema_version=schema_version) as index:
        return index.is_completed(qmof_id)


__all__ = [
    "CIF_MEMBER_TEMPLATE",
    "CSV_FILE",
    "DEFAULT_ENDPOINT",
    "REPO",
    "STRUCTURES_FILE",
    "CompletionIndex",
    "QmofConfig",
    "QmofError",
    "completed",
    "dataset_url",
    "download_asset",
    "ensure_assets",
    "iter_csv_rows",
    "iter_records",
    "read_entry",
    "source_id_for",
]
