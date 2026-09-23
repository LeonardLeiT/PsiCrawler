"""AMCSD raw download: bulk CIF, AMC and DIF archives.

The American Mineralogist Crystal Structure Database (AMCSD) is served by the
RRUFF project as three Apache directory-index ZIP archives:

- ``cif.zip``: minimal CIF records (unit cell, symmetry, atomic coordinates).
- ``amc.zip``: the native AMCSD text format with the richest metadata
  (mineral name, authors, journal, locality, experimental conditions).
- ``dif.zip``: tabular diffraction records.

This module never touches the standard schema. It downloads the archives under
``data/dft/amcsd/raw`` and streams their members entry by entry. Members are
aligned across archives by the trailing AMCSD identifier in their filename
(``Actinolite__0001982.cif``). The CIF archive is the superset (some records
have a CIF but no AMC/DIF), so the identifier iteration is driven by the union
of the requested archives' identifiers.
"""

from __future__ import annotations

import logging
import os
import re
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

BASE_URL = "https://www.rruff.net"
ARCHIVE_DIR = "AMS/zipped_files"
ARCHIVES: dict[str, str] = {"amc": "amc.zip", "cif": "cif.zip", "dif": "dif.zip"}
PRIMARY_ARCHIVE = "cif"
DEFAULT_KINDS = ("amc", "cif", "dif")
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20

ID_PATTERN = re.compile(r"__(?P<id>\d+)\.(?:cif|amc|dif)$", re.IGNORECASE)


class AmcsdError(RuntimeError):
    """Raised when an AMCSD request or archive operation fails irrecoverably."""


@dataclass(frozen=True)
class AmcsdConfig:
    """Runtime settings for one AMCSD download task."""

    data_root: Path = Path("data/dft/amcsd")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for source archives."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def normalize_amcsd_id(value: Any) -> str:
    """Return a zero-padded seven-digit AMCSD identifier."""
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"AMCSD identifier must be digits, got {value!r}")
    return text.zfill(7)


def source_id_for(amcsd_id: Any) -> str:
    """Build the stable identifier used across the index."""
    return normalize_amcsd_id(amcsd_id)


def archive_url(kind: str) -> str:
    """Return the download URL for one archive kind."""
    try:
        filename = ARCHIVES[kind]
    except KeyError as error:
        raise KeyError(f"Unknown AMCSD archive {kind!r}; known: {', '.join(ARCHIVES)}") from error
    return f"{BASE_URL}/{ARCHIVE_DIR}/{filename}"


def archive_path(kind: str, config: AmcsdConfig | None = None) -> Path:
    """Return the local path of one archive under ``raw/<kind>/``."""
    try:
        filename = ARCHIVES[kind]
    except KeyError as error:
        raise KeyError(f"Unknown AMCSD archive {kind!r}; known: {', '.join(ARCHIVES)}") from error
    cfg = config or AmcsdConfig()
    return cfg.raw_dir / kind / filename


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_open(url: str, config: AmcsdConfig, timeout: int | None = None):
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
                raise AmcsdError(f"HTTP {error.code} for {url}: {error.reason}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise AmcsdError(f"Failed to open {url}: {last_error}")


def http_get_bytes(url: str, config: AmcsdConfig, timeout: int | None = None) -> bytes:
    """Fetch raw bytes from a URL."""
    with _http_open(url, config, timeout=timeout) as response:
        return response.read()


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


def download_archive(
    kind: str,
    config: AmcsdConfig | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Download one ZIP archive into ``raw/<kind>/`` and return its path.

    An existing non-empty file is reused, so repeated runs resume by skipping
    the multi-megabyte transfer.
    """
    cfg = config or AmcsdConfig()
    target = archive_path(kind, cfg)
    if _is_complete(target):
        return target
    url = archive_url(kind)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    try:
        with _http_open(url, cfg) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=READ_CHUNK_BYTES)
        if _is_complete(target):
            _quiet_unlink(temporary)
            return target
        try:
            os.replace(temporary, target)
        except OSError:
            if _is_complete(target):
                _quiet_unlink(temporary)
                return target
            raise
    except Exception:
        _quiet_unlink(temporary)
        raise
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", url, target, target.stat().st_size / (1024 * 1024))
    if cfg.sleep_seconds > 0:
        time.sleep(cfg.sleep_seconds)
    return target


def ensure_archives(
    config: AmcsdConfig | None = None,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    logger: logging.Logger | None = None,
) -> dict[str, Path]:
    """Download every missing requested archive and return their paths."""
    cfg = config or AmcsdConfig()
    return {kind: download_archive(kind, cfg, logger=logger) for kind in kinds}


# ---------------------------------------------------------------------------
# Archive member access
# ---------------------------------------------------------------------------

def _name_from_member(member: str) -> str | None:
    """Return the mineral/compound name encoded in an archive member name."""
    base = Path(member).name
    name = base.split("__", 1)[0].strip()
    return name or None


def _member_priority(member: str) -> int:
    """Rank competing members for one identifier.

    Some identifiers carry both a minimal CIF and an ``__original__`` CIF; the
    minimal record is preferred because it is the standardized structure used by
    the database, and the original stays available inside the raw archive.
    """
    return 1 if "__original__" in member.lower() else 0


class AmcsdArchives:
    """Open the requested ZIP archives and read aligned records."""

    def __init__(self, config: AmcsdConfig, kinds: tuple[str, ...]):
        self.config = config
        self.kinds = tuple(kind for kind in kinds if kind in ARCHIVES)
        if not self.kinds:
            raise AmcsdError(f"No known AMCSD archives requested; known: {', '.join(ARCHIVES)}")
        self._zips: dict[str, zipfile.ZipFile] = {}
        self._maps: dict[str, dict[str, str]] = {}

    def __enter__(self) -> "AmcsdArchives":
        try:
            for kind in self.kinds:
                path = archive_path(kind, self.config)
                if not _is_complete(path):
                    raise AmcsdError(f"AMCSD archive {kind} is missing: {path}")
                try:
                    handle = zipfile.ZipFile(path)
                except zipfile.BadZipFile as error:
                    raise AmcsdError(f"AMCSD archive {kind} is not a valid ZIP: {path}") from error
                self._zips[kind] = handle
                mapping: dict[str, str] = {}
                for name in handle.namelist():
                    match = ID_PATTERN.search(name)
                    if not match:
                        continue
                    key = match.group("id")
                    current = mapping.get(key)
                    if current is None or _member_priority(name) < _member_priority(current):
                        mapping[key] = name
                self._maps[kind] = mapping
        except Exception:
            self.__exit__()
            raise
        return self

    def __exit__(self, *_: Any) -> None:
        for handle in self._zips.values():
            handle.close()
        self._zips = {}
        self._maps = {}

    def ids(self) -> list[str]:
        """Return the sorted union of identifiers across the open archives."""
        union: set[str] = set()
        for mapping in self._maps.values():
            union.update(mapping)
        return sorted(union)

    def has(self, amcsd_id: str) -> bool:
        """Return whether any open archive contains the identifier."""
        key = normalize_amcsd_id(amcsd_id)
        return any(key in mapping for mapping in self._maps.values())

    def read_entry(self, amcsd_id: str) -> dict[str, Any]:
        """Read every available member for one identifier into an entry dict."""
        key = normalize_amcsd_id(amcsd_id)
        members = {kind: self._maps[kind].get(key) for kind in self.kinds}
        members = {kind: member for kind, member in members.items() if member}
        if not members:
            raise LookupError(f"AMCSD identifier not found in open archives: {key}")
        texts: dict[str, str | None] = {}
        for kind in ("amc", "cif", "dif"):
            member = members.get(kind)
            texts[kind] = (
                self._zips[kind].read(member).decode("utf-8", errors="replace") if member else None
            )
        primary = members.get(PRIMARY_ARCHIVE) or next(iter(members.values()))
        return {
            "amcsd_id": key,
            "name": _name_from_member(primary),
            "members": members,
            "amc": texts.get("amc"),
            "cif": texts.get("cif"),
            "dif": texts.get("dif"),
            "archive_paths": {kind: str(archive_path(kind, self.config)) for kind in self.kinds},
        }


def iter_archive_entries(
    config: AmcsdConfig | None = None,
    *,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    download_missing: bool = True,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream aligned AMCSD entries from the requested archives.

    Yields:
        dict[str, Any]: ``{"amcsd_id", "name", "members", "amc", "cif", "dif",
        "archive_paths"}``.
    """
    cfg = config or AmcsdConfig()
    selected = tuple(kind for kind in kinds if kind in ARCHIVES)
    if download_missing:
        ensure_archives(cfg, selected, logger=logger)
    with AmcsdArchives(cfg, selected) as archives:
        for index, amcsd_id in enumerate(archives.ids()):
            if max_records is not None and index >= max_records:
                return
            yield archives.read_entry(amcsd_id)


def read_entry(
    amcsd_id: str,
    config: AmcsdConfig | None = None,
    *,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    download_missing: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Read one AMCSD entry by identifier, or ``None`` if absent."""
    cfg = config or AmcsdConfig()
    selected = tuple(kind for kind in kinds if kind in ARCHIVES)
    if download_missing:
        ensure_archives(cfg, selected, logger=logger)
    with AmcsdArchives(cfg, selected) as archives:
        if not archives.has(amcsd_id):
            return None
        return archives.read_entry(amcsd_id)


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path: str | Path, *, source: str = "amcsd",
                 schema_version: str = "3.0"):
        self._database = Path(db_path)
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

    def is_completed(self, amcsd_id: str) -> bool:
        """Return whether one AMCSD entry is already indexed."""
        identifier = source_id_for(amcsd_id)
        row = self._load(identifier)
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
    db_path: str | Path,
    amcsd_id: str,
    *,
    source: str = "amcsd",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one AMCSD entry is already indexed."""
    with CompletionIndex(db_path, source=source, schema_version=schema_version) as index:
        return index.is_completed(amcsd_id)


__all__ = [
    "ARCHIVES",
    "ARCHIVE_DIR",
    "AmcsdArchives",
    "AmcsdConfig",
    "AmcsdError",
    "BASE_URL",
    "CompletionIndex",
    "DEFAULT_KINDS",
    "PRIMARY_ARCHIVE",
    "archive_path",
    "archive_url",
    "completed",
    "download_archive",
    "ensure_archives",
    "http_get_bytes",
    "iter_archive_entries",
    "normalize_amcsd_id",
    "read_entry",
    "source_id_for",
]
