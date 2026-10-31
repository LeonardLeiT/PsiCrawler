"""OMat24 raw download: Meta Open Materials 2024 ASE LMDB archives.

OMat24 is distributed as per-subdataset ``tar.gz`` archives that each contain an
ASE LMDB database (``data.aselmdb``). The archives are served from
``dl.fbaipublicfiles.com`` and are not gated. This module downloads and extracts
one subdataset at a time, then streams its ASE rows with the ``aselmdb`` backend
provided by ``ase-db-backends``.

This module never touches the standard schema.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import tarfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests

TRAIN_BASE = "https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/omat/train/{name}.tar.gz"
VAL_BASE = "https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241220/omat/val/{name}.tar.gz"
SALEX_BASE = "https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/{split}.tar.gz"
ONE_M_URL = "https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/251210/omat24_1M_251210.tar.gz"

SUBDATASET_NAMES = (
    "rattled-1000",
    "rattled-1000-subsampled",
    "rattled-500",
    "rattled-500-subsampled",
    "rattled-300",
    "rattled-300-subsampled",
    "aimd-from-PBE-1000-npt",
    "aimd-from-PBE-1000-nvt",
    "aimd-from-PBE-3000-npt",
    "aimd-from-PBE-3000-nvt",
    "rattled-relax",
)

SUBSETS: dict[str, dict[str, str]] = {}
for _name in SUBDATASET_NAMES:
    SUBSETS[f"val-{_name}"] = {"url": VAL_BASE.format(name=_name), "split": "val", "subset": _name}
    SUBSETS[f"train-{_name}"] = {"url": TRAIN_BASE.format(name=_name), "split": "train", "subset": _name}
SUBSETS["1m"] = {"url": ONE_M_URL, "split": "1m", "subset": "omat24_1M"}
SUBSETS["salex-train"] = {"url": SALEX_BASE.format(split="train"), "split": "salex-train", "subset": "sAlex-train"}
SUBSETS["salex-val"] = {"url": SALEX_BASE.format(split="val"), "split": "salex-val", "subset": "sAlex-val"}

DEFAULT_SUBSET = "val-rattled-1000-subsampled"
DEFAULT_TIMEOUT_SECONDS = 1200
DEFAULT_SLEEP_SECONDS = 0.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 10.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20


class Omat24Error(RuntimeError):
    """Raised when an OMat24 download or archive operation fails irrecoverably."""


@dataclass(frozen=True)
class Omat24Config:
    """Runtime settings for one OMat24 download task."""

    data_root: Path = Path("data/dft/omat24")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for archives and extracted subdatasets."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def source_id_for(subset: str, sid: Any) -> str:
    """Build the stable identifier used across the index."""
    return str(sid)


def get_subset(name: str) -> dict[str, str]:
    """Return a subdataset definition by name, or raise a helpful error."""
    try:
        return SUBSETS[name]
    except KeyError as error:
        raise KeyError(f"Unknown OMat24 subset {name!r}; known: {', '.join(sorted(SUBSETS))}") from error


def archive_path(subset: str, config: Omat24Config | None = None) -> Path:
    """Return the local archive path for one subdataset."""
    cfg = config or Omat24Config()
    return cfg.raw_dir / f"{subset}.tar.gz"


def extract_dir(subset: str, config: Omat24Config | None = None) -> Path:
    """Return the extraction directory for one subdataset."""
    cfg = config or Omat24Config()
    return cfg.raw_dir / subset


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
    subset: str,
    config: Omat24Config | None = None,
    *,
    force: bool = False,
    logger: logging.Logger | None = None,
) -> Path:
    """Download one subdataset archive into ``raw/<subset>.tar.gz``."""
    cfg = config or Omat24Config()
    definition = get_subset(subset)
    target = archive_path(subset, cfg)
    if not force and _is_complete(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    last_error: Exception | None = None
    for attempt in range(cfg.retry_count):
        try:
            with requests.get(
                definition["url"], headers={"User-Agent": cfg.user_agent},
                stream=True, timeout=cfg.request_timeout,
            ) as response:
                response.raise_for_status()
                with temporary.open("wb") as stream:
                    for chunk in response.iter_content(READ_CHUNK_BYTES):
                        if chunk:
                            stream.write(chunk)
            os.replace(temporary, target)
            break
        except Exception as error:  # noqa: BLE001 - retried below
            last_error = error
            _quiet_unlink(temporary)
            if attempt < cfg.retry_count - 1:
                time.sleep(min(cfg.retry_delay * (attempt + 1), 60.0))
    else:
        raise Omat24Error(f"Failed to download {definition['url']}: {last_error}")
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", definition["url"], target,
                    target.stat().st_size / (1024 * 1024))
    return target


def ensure_extracted(
    subset: str,
    config: Omat24Config | None = None,
    *,
    force: bool = False,
    logger: logging.Logger | None = None,
) -> Path:
    """Download (if needed) and extract one subdataset, returning its directory."""
    cfg = config or Omat24Config()
    target_dir = extract_dir(subset, cfg)
    if not force and any(target_dir.rglob("*.aselmdb")):
        return target_dir
    archive = download_archive(subset, cfg, force=force, logger=logger)
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(target_dir, filter="data")
            else:  # pragma: no cover - older Python
                tar.extractall(target_dir)
    except tarfile.TarError as error:
        raise Omat24Error(f"Failed to extract {archive}: {error}") from error
    if logger is not None:
        count = len(list(target_dir.rglob("*.aselmdb")))
        logger.info("[EXTRACT] %s -> %s (%d aselmdb files)", archive.name, target_dir, count)
    return target_dir


def _aselmdb_paths(directory: Path) -> list[Path]:
    """Return the ``.aselmdb`` files under a subdataset directory, sorted."""
    return sorted(directory.rglob("*.aselmdb"))


def iter_records(
    subset: str = DEFAULT_SUBSET,
    config: Omat24Config | None = None,
    *,
    download_missing: bool = True,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream OMat24 ASE rows for one subdataset.

    Yields:
        dict[str, Any]: ``{"subset", "db_path", "row_id", "row", "atoms", "data"}``.
    """
    cfg = config or Omat24Config()
    if download_missing:
        directory = ensure_extracted(subset, cfg, logger=logger)
    else:
        directory = extract_dir(subset, cfg)
    paths = _aselmdb_paths(directory)
    if not paths:
        raise Omat24Error(f"No .aselmdb found under {directory}")
    from ase_db_backends.aselmdb import LMDBDatabase

    produced = 0
    for db_path in paths:
        db = LMDBDatabase(db_path, readonly=True, use_lock_file=False)
        try:
            ids = list(db.ids)
            for row_id in ids:
                row = db.get(id=row_id)
                atoms = row.toatoms()
                yield {
                    "subset": subset,
                    "db_path": str(db_path),
                    "row_id": row_id,
                    "row": row,
                    "atoms": atoms,
                    "data": row.data or {},
                }
                produced += 1
                if max_records is not None and produced >= max_records:
                    return
        finally:
            db.close()


def read_entry(
    record_id: str,
    subset: str = DEFAULT_SUBSET,
    config: Omat24Config | None = None,
    *,
    download_missing: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Read one OMat24 row by its ``sid`` (or integer row id), or ``None``."""
    requested = str(record_id)
    for record in iter_records(subset, config, download_missing=download_missing, logger=logger):
        data = record.get("data") or {}
        sid = data.get("sid")
        if str(sid) == requested or str(record.get("row_id")) == requested:
            return record
    return None


class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path_value: str | Path, *, source: str = "omat24",
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

    def is_completed(self, sid: str) -> bool:
        """Return whether one OMat24 row is already indexed."""
        row = self._load(str(sid))
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
    sid: str,
    *,
    source: str = "omat24",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one OMat24 row is already indexed."""
    with CompletionIndex(db_path_value, source=source, schema_version=schema_version) as index:
        return index.is_completed(sid)


__all__ = [
    "DEFAULT_SUBSET",
    "SUBSETS",
    "CompletionIndex",
    "Omat24Config",
    "Omat24Error",
    "archive_path",
    "completed",
    "download_archive",
    "ensure_extracted",
    "extract_dir",
    "get_subset",
    "iter_records",
    "read_entry",
    "source_id_for",
]
