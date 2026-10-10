"""MatPES raw download: potential-energy-surface entries as JSON Lines.

MatPES (Materials Potential Energy Surface; Materialyze.AI and the Materials
Project) publishes its dataset as JSON Lines files on Hugging Face. Each line is
one static DFT calculation with an inline pymatgen ``structure``, total energy,
forces, stress, band gap, and magnetic moments. The PBE and r2SCAN functional
files are provided separately.

The files are multi-gigabyte, so entries are streamed over HTTP line by line and
never loaded whole. The Hugging Face endpoint defaults to ``https://huggingface.co``
and can be pointed at a mirror with the ``HF_ENDPOINT`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request
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
REPO = "materialyze/matpes"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_SLEEP_SECONDS = 0.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20

FUNCTIONS: dict[str, str] = {
    "r2scan": "MatPES-R2SCAN-2025.2.jsonl",
    "pbe": "MatPES-PBE-2025.2.jsonl",
}
DEFAULT_FUNCTION = "r2scan"


class MatPesError(RuntimeError):
    """Raised when a MatPES request fails irrecoverably."""


@dataclass(frozen=True)
class MatPesConfig:
    """Runtime settings for one MatPES download task."""

    data_root: Path = Path("data/dft/matpes")
    endpoint: str = DEFAULT_ENDPOINT
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for downloaded files."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def source_id_for(matpes_id: Any) -> str:
    """Build the stable identifier used across the index."""
    return str(matpes_id).strip()


def dataset_url(function: str, config: MatPesConfig | None = None) -> str:
    """Return the resolve URL for one MatPES functional file."""
    cfg = config or MatPesConfig()
    try:
        filename = FUNCTIONS[function]
    except KeyError as error:
        raise KeyError(f"Unknown MatPES function {function!r}; known: {', '.join(FUNCTIONS)}") from error
    return f"{cfg.endpoint}/datasets/{REPO}/resolve/main/{filename}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_open(url: str, config: MatPesConfig, timeout: int | None = None):
    """Open a URL with the configured user agent and retry policy.

    Client errors (4xx) other than 429 are permanent and raise immediately;
    server errors and network failures are retried with a linear backoff.
    """
    request = urllib.request.Request(url, headers={"User-Agent": config.user_agent})
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            return urllib.request.urlopen(request, timeout=timeout or config.request_timeout)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                raise MatPesError(f"HTTP {error.code} for {url}: {error.reason}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise MatPesError(f"Failed to open {url}: {last_error}")


def http_get_bytes(url: str, config: MatPesConfig, timeout: int | None = None) -> bytes:
    """Fetch raw bytes from a URL."""
    with _http_open(url, config, timeout=timeout) as response:
        return response.read()


# ---------------------------------------------------------------------------
# Streaming entry access
# ---------------------------------------------------------------------------

def iter_entries(
    function: str = DEFAULT_FUNCTION,
    config: MatPesConfig | None = None,
    *,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream MatPES entries line by line from the remote JSON Lines file.

    A short-lived response is used so that a limited sample transfers only the
    lines it consumes.
    """
    cfg = config or MatPesConfig()
    url = dataset_url(function, cfg)
    if logger is not None:
        logger.info("[STREAM] %s", url)
    with _http_open(url, cfg) as response:
        produced = 0
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            yield entry
            produced += 1
            if max_records is not None and produced >= max_records:
                return


def read_entry(
    matpes_id: str,
    function: str = DEFAULT_FUNCTION,
    config: MatPesConfig | None = None,
    *,
    max_scan: int | None = None,
) -> dict[str, Any] | None:
    """Scan the remote file for one MatPES entry by identifier."""
    requested = source_id_for(matpes_id)
    for index, entry in enumerate(iter_entries(function, config)):
        if source_id_for(entry.get("matpes_id")) == requested:
            return entry
        if max_scan is not None and index + 1 >= max_scan:
            return None
    return None


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run.

    MatPES raw records are referenced by URL, so completion depends only on the
    index row (schema version and download status) rather than a local file.
    """

    def __init__(self, db_path_value: str | Path, *, source: str = "matpes",
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

    def is_completed(self, matpes_id: str) -> bool:
        """Return whether one MatPES entry is already indexed."""
        row = self._load(source_id_for(matpes_id))
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
    matpes_id: str,
    *,
    source: str = "matpes",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one MatPES entry is already indexed."""
    with CompletionIndex(db_path_value, source=source, schema_version=schema_version) as index:
        return index.is_completed(matpes_id)


__all__ = [
    "DEFAULT_ENDPOINT",
    "DEFAULT_FUNCTION",
    "FUNCTIONS",
    "REPO",
    "CompletionIndex",
    "MatPesConfig",
    "MatPesError",
    "completed",
    "dataset_url",
    "http_get_bytes",
    "iter_entries",
    "read_entry",
    "source_id_for",
]
