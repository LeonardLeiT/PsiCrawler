"""Materials Cloud raw download: OPTIMADE queries and archive bulk files.

This module never touches the standard schema. It retrieves upstream documents
and files as completely as Materials Cloud exposes them and writes bulk files
under ``data/dft/materialscloud/raw``.

Two access paths are supported:

- The OPTIMADE REST API at ``https://optimade.materialscloud.org/main/<prefix>/v1``
  for on-demand, per-record and filtered queries. This is the primary path for
  both ``run_single`` and ``run_batch``.
- The Materials Cloud Archive (InvenioRDM) file API at
  ``https://archive.materialscloud.org/api/records/<uuid>/files`` for bulk
  artifacts such as ``MC3D-structures.aiida`` and ``structure_2d.json``.

The ``mc3d``/``mc2d`` OPTIMADE servers report the total entry count in
``meta.data_returned`` instead of the page size, so pagination must rely on
``meta.data_available`` and the actual number of returned records. The edge also
rejects oversized pages (``page_limit`` above :data:`MAX_PAGE_LIMIT`) with HTTP
403, so page sizes are bounded to the accepted range.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

OPTIMADE_HOST = "https://optimade.materialscloud.org"
ARCHIVE_HOST = "https://archive.materialscloud.org"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20
API_VERSION = "1.2.0"

# The Materials Cloud OPTIMADE edge rejects oversized pages with HTTP 403.
# 500 is the largest page size known to be accepted; keep requests well below.
MAX_PAGE_LIMIT = 500


@dataclass(frozen=True)
class Dataset:
    """One Materials Cloud child database and how to enumerate its records."""

    name: str
    prefix: str
    display: str
    functional: str | None
    dimensionality: int | None
    discover_url: str
    record_uuid: str | None = None
    bulk_files: tuple[str, ...] = ()
    description: str = ""

    @property
    def optimade_base_url(self) -> str:
        """Return the child-database OPTIMADE root, including ``/v1``."""
        return f"{OPTIMADE_HOST}/main/{self.prefix}/v1"

    @property
    def is_primary(self) -> bool:
        """Return whether the dataset carries standard structure records."""
        return True


# Bulk files intentionally exclude the 12 GB ``MC3D-provenance.aiida`` and the
# 8.4 GB ``MC2D_export_*.aiida``; callers can still fetch them by explicit key.
DATASETS: dict[str, Dataset] = {
    "mc3d-pbe-v1": Dataset(
        name="mc3d-pbe-v1",
        prefix="mc3d-pbe-v1",
        display="MC3D (PBE-v1)",
        functional="PBE",
        dimensionality=3,
        discover_url="https://www.materialscloud.org/discover/mc3d",
        record_uuid="eqzc6-e2579",
        bulk_files=("MC3D-structures.aiida", "MC3D-cifs.zip"),
        description="Curated 3D crystals from MPDS/COD/ICSD relaxed with PBE (snapshot v1).",
    ),
    "mc3d-pbesol-v1": Dataset(
        name="mc3d-pbesol-v1",
        prefix="mc3d-pbesol-v1",
        display="MC3D (PBEsol-v1)",
        functional="PBEsol",
        dimensionality=3,
        discover_url="https://www.materialscloud.org/discover/mc3d",
        record_uuid="eqzc6-e2579",
        bulk_files=("MC3D-structures.aiida", "MC3D-cifs.zip"),
        description="Curated 3D crystals from MPDS/COD/ICSD relaxed with PBEsol (snapshot v1).",
    ),
    "mc3d-pbesol-v2": Dataset(
        name="mc3d-pbesol-v2",
        prefix="mc3d-pbesol-v2",
        display="MC3D (PBEsol-v2)",
        functional="PBEsol",
        dimensionality=3,
        discover_url="https://www.materialscloud.org/discover/mc3d",
        record_uuid="eqzc6-e2579",
        bulk_files=("MC3D-structures.aiida", "MC3D-cifs.zip"),
        description="Curated 3D crystals from MPDS/COD/ICSD relaxed with PBEsol (snapshot v2, latest).",
    ),
    "mc2d": Dataset(
        name="mc2d",
        prefix="mc2d",
        display="MC2D",
        functional="PBE",
        dimensionality=2,
        discover_url="https://www.materialscloud.org/discover/mc2d",
        record_uuid="17gf6-84915",
        bulk_files=(
            "structure_2d.json",
            "optimized_2d_structures.zip",
            "as_extracted_2d_structures.zip",
        ),
        description="Two-dimensional materials from computational exfoliation of 3D compounds.",
    ),
}

PRIMARY_DATASETS = tuple(DATASETS)


class MaterialsCloudError(RuntimeError):
    """Raised when a Materials Cloud request fails irrecoverably."""


@dataclass(frozen=True)
class MaterialsCloudConfig:
    """Runtime settings for one Materials Cloud download task."""

    data_root: Path = Path("data/dft/materialscloud")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for source archives and files."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def get_dataset(name: str) -> Dataset:
    """Return a dataset by name, or raise a helpful error."""
    try:
        return DATASETS[name]
    except KeyError as error:
        raise KeyError(
            f"Unknown Materials Cloud dataset {name!r}; known: {', '.join(DATASETS)}"
        ) from error


def source_id_for(dataset: str, entry_id: str) -> str:
    """Build the namespaced stable identifier used across child databases."""
    return f"{dataset}:{entry_id}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_open(url: str, config: MaterialsCloudConfig, timeout: int | None = None):
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
                raise MaterialsCloudError(f"HTTP {error.code} for {url}: {error.reason}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise MaterialsCloudError(f"Failed to open {url}: {last_error}")


def http_get_bytes(url: str, config: MaterialsCloudConfig, timeout: int | None = None) -> bytes:
    """Fetch raw bytes from a URL."""
    with _http_open(url, config, timeout=timeout) as response:
        return response.read()


def http_get_json(url: str, config: MaterialsCloudConfig, timeout: int | None = None) -> Any:
    """Fetch and decode a JSON response."""
    return json.loads(http_get_bytes(url, config, timeout=timeout).decode("utf-8"))


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


def save_json_atomic(path: str | Path, payload: Any) -> Path:
    """Write a JSON document through a temporary file and rename it into place."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        os.replace(temporary, target)
    except Exception:
        _quiet_unlink(temporary)
        raise
    return target


def _stream_download(url: str, target: Path, config: MaterialsCloudConfig,
                     logger: logging.Logger | None, label: str) -> Path:
    """Stream one URL into ``target`` through a per-process temp file."""
    if _is_complete(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    try:
        with _http_open(url, config) as response, temporary.open("wb") as stream:
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
        logger.info("[FILE] %s -> %s (%.1f MB)", label, target, target.stat().st_size / (1024 * 1024))
    if config.sleep_seconds > 0:
        time.sleep(config.sleep_seconds)
    return target


# ---------------------------------------------------------------------------
# Archive bulk files (InvenioRDM)
# ---------------------------------------------------------------------------

def list_bulk_files(
    dataset: Dataset | str,
    config: MaterialsCloudConfig | None = None,
    *,
    include_all: bool = False,
) -> list[dict[str, Any]]:
    """Return downloadable bulk files for a child database.

    Only the curated small artifacts are returned unless ``include_all`` is set,
    in which case the multi-gigabyte provenance archives are listed as well.
    Each item is ``{"key", "size", "url"}``.
    """
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    if not dataset.record_uuid:
        return []
    cfg = config or MaterialsCloudConfig()
    payload = http_get_json(f"{ARCHIVE_HOST}/api/records/{dataset.record_uuid}/files", cfg)
    selected: list[dict[str, Any]] = []
    wanted = None if include_all else set(dataset.bulk_files)
    for entry in payload.get("entries") or []:
        key = entry.get("key")
        content = (entry.get("links") or {}).get("content")
        if not key or not content:
            continue
        if wanted is not None and key not in wanted:
            continue
        selected.append({"key": key, "size": entry.get("size"), "url": content})
    return selected


def download_bulk_file(
    dataset: Dataset | str,
    key: str,
    config: MaterialsCloudConfig | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Download one archive bulk file into ``raw/<dataset>/`` and return its path."""
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    cfg = config or MaterialsCloudConfig()
    target = cfg.raw_dir / dataset.name / key
    if _is_complete(target):
        return target
    match = next(
        (item for item in list_bulk_files(dataset, cfg, include_all=True) if item["key"] == key),
        None,
    )
    if match is None:
        raise MaterialsCloudError(
            f"Bulk file {key!r} not found for {dataset.name!r} "
            f"(record {dataset.record_uuid}); use list_bulk_files(include_all=True) to inspect."
        )
    return _stream_download(match["url"], target, cfg, logger, f"{dataset.name}/{key}")


# ---------------------------------------------------------------------------
# OPTIMADE queries
# ---------------------------------------------------------------------------

class OptimadeClient:
    """Query one Materials Cloud OPTIMADE child database."""

    def __init__(self, config: MaterialsCloudConfig | None = None, dataset: Dataset | str = "mc3d-pbesol-v2"):
        self.config = config or MaterialsCloudConfig()
        self.dataset = get_dataset(dataset) if isinstance(dataset, str) else dataset
        self.base_url = self.dataset.optimade_base_url

    def fetch_info(self, entry_type: str | None = None) -> dict[str, Any]:
        """Return the OPTIMADE ``info`` document, optionally for one entry type."""
        suffix = f"/{entry_type}" if entry_type else ""
        payload = http_get_json(f"{self.base_url}/info{suffix}", self.config)
        return payload.get("data", {})

    def fetch_structure(self, entry_id: str) -> dict[str, Any] | None:
        """Fetch one structure record by its identifier."""
        url = f"{self.base_url}/structures/{urllib.parse.quote(str(entry_id), safe='')}"
        payload = http_get_json(url, self.config)
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def count(self, filter_expression: str | None = None) -> int | None:
        """Return the number of entries matching a filter, or ``None`` if unknown."""
        params: dict[str, Any] = {"page_limit": 1}
        if filter_expression:
            params["filter"] = filter_expression
        payload = http_get_json(f"{self.base_url}/structures?{urllib.parse.urlencode(params)}", self.config)
        total = (payload.get("meta") or {}).get("data_available")
        return int(total) if total is not None else None

    def iter_structures(
        self,
        *,
        filter_expression: str | None = None,
        response_fields: Iterable[str] | None = None,
        page_limit: int = 100,
        max_records: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate structures with offset pagination until exhausted.

        ``meta.data_returned`` is deliberately ignored because the Materials
        Cloud servers report the total there instead of the page length.
        """
        if page_limit <= 0:
            raise ValueError("page_limit must be positive")
        if page_limit > MAX_PAGE_LIMIT:
            raise ValueError(
                f"page_limit {page_limit} exceeds the Materials Cloud OPTIMADE cap of "
                f"{MAX_PAGE_LIMIT}; larger pages are rejected with HTTP 403"
            )
        offset = 0
        produced = 0
        while True:
            params: dict[str, Any] = {"page_limit": page_limit, "page_offset": offset}
            if filter_expression:
                params["filter"] = filter_expression
            if response_fields:
                params["response_fields"] = ",".join(response_fields)
            url = f"{self.base_url}/structures?{urllib.parse.urlencode(params)}"
            payload = http_get_json(url, self.config)
            data = payload.get("data") or []
            if not data:
                return
            for record in data:
                if isinstance(record, dict):
                    yield record
                    produced += 1
                    if max_records is not None and produced >= max_records:
                        return
            total = (payload.get("meta") or {}).get("data_available")
            offset += len(data)
            if len(data) < page_limit or (total is not None and offset >= int(total)):
                return
            if self.config.sleep_seconds > 0:
                time.sleep(self.config.sleep_seconds)


def optimade_record_to_document(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten one OPTIMADE record into an id + attributes document.

    Attributes are preserved verbatim, including the ``_mcloud_*`` extension
    keys that carry source identifiers, energies and magnetizations.
    """
    attributes = record.get("attributes") or {}
    return {"id": record.get("id"), "type": record.get("type"), **attributes}


def structure_url(dataset: Dataset | str, entry_id: str) -> str:
    """Return the canonical OPTIMADE structure URL for one entry."""
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    return f"{dataset.optimade_base_url}/structures/{urllib.parse.quote(str(entry_id), safe='')}"


def iter_dataset_structures(
    dataset: Dataset | str,
    config: MaterialsCloudConfig | None = None,
    *,
    filter_expression: str | None = None,
    response_fields: Iterable[str] | None = None,
    page_limit: int = 100,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate a child database's structures through OPTIMADE.

    Yields:
        dict[str, Any]: ``{"dataset", "index", "document", "url"}``.
    """
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    cfg = config or MaterialsCloudConfig()
    client = OptimadeClient(cfg, dataset)
    if logger is not None:
        logger.info("[START] %s %s", dataset.name, client.base_url)
    for index, record in enumerate(
        client.iter_structures(
            filter_expression=filter_expression,
            response_fields=response_fields,
            page_limit=page_limit,
            max_records=max_records,
        )
    ):
        yield {
            "dataset": dataset.name,
            "index": index,
            "document": optimade_record_to_document(record),
            "url": f"{client.base_url}/structures/{record.get('id')}",
        }


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run.

    Unlike bulk-archive sources, Materials Cloud records are queried directly,
    so completeness is decided from the indexed record alone: a matching
    ``schema_version`` and a ``success`` or ``partial`` status is enough.
    """

    def __init__(self, db_path: str | Path, *, source: str = "materialscloud",
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

    def is_completed(self, dataset: str, entry_id: str) -> bool:
        """Return whether one child-database entry is already indexed."""
        row = self._load(source_id_for(dataset, entry_id))
        if not row:
            return False
        return (
            row["schema_version"] == self._schema_version
            and row["download_status"] in {"success", "partial"}
        )

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
    db_path: str | Path,
    dataset: str,
    entry_id: str,
    *,
    source: str = "materialscloud",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one child-database entry is already indexed."""
    with CompletionIndex(db_path, source=source, schema_version=schema_version) as index:
        return index.is_completed(dataset, entry_id)


__all__ = [
    "API_VERSION",
    "ARCHIVE_HOST",
    "CompletionIndex",
    "DATASETS",
    "Dataset",
    "MaterialsCloudConfig",
    "MaterialsCloudError",
    "MAX_PAGE_LIMIT",
    "OPTIMADE_HOST",
    "OptimadeClient",
    "PRIMARY_DATASETS",
    "completed",
    "download_bulk_file",
    "get_dataset",
    "http_get_bytes",
    "http_get_json",
    "iter_dataset_structures",
    "list_bulk_files",
    "optimade_record_to_document",
    "save_json_atomic",
    "source_id_for",
    "structure_url",
]
