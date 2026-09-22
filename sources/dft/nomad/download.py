"""NOMAD Archive raw download through the public native API.

This module never touches the standard schema. It enumerates public entries,
fetches their processed archive documents, preserves them verbatim under
``data/dft/nomad/raw``, and reports progress.

Access paths:

- ``POST {API_HOST}/entries/query`` enumerates public entries with
  ``page_after_value`` pagination. This is the primary listing used for both
  ``run_single`` and ``run_batch``.
- ``POST {API_HOST}/entries/{entry_id}/archive/query`` returns one processed
  archive document. The requested ``required`` tree is deliberately bounded so
  each payload stays small while still carrying identity, composition,
  structure (``metadata.optimade`` for periodic systems plus the resolved
  ``run.system`` fallback), method settings (``run.method``, including the
  k-point mesh), and the final calculation energy.
- ``POST {API_HOST}/entries/archive/download/query`` streams a zip with one
  ``<entry-id>.json`` per entry for bulk ingestion.

NOMAD stores quantities in SI base units, so the archive energy is in Joule and
lengths are in metre. Length conversion happens here only when the ``optimade``
structure is absent; all other conversions live in the normalizer.

Public data requires no authentication. Set ``NOMAD_API_TOKEN`` only for
non-public resources or to raise the anonymous rate limits.
"""

from __future__ import annotations

import io
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
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

API_HOST = "https://nomad-lab.eu/prod/v1/api/v1"
ENTRIES_QUERY_URL = f"{API_HOST}/entries/query"
ARCHIVE_DOWNLOAD_QUERY_URL = f"{API_HOST}/entries/archive/download/query"
GUI_ENTRY_URL = "https://nomad-lab.eu/prod/v1/gui/search/entries/entry/id/{entry_id}"

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_SLEEP_SECONDS = 0.2
DEFAULT_RETRY_COUNT = 4
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20
API_VERSION = "nomad-v1"

# The archive subtree requested for every entry. ``metadata.optimade`` carries
# the structure in Angstrom for periodic systems; ``run.system.atoms`` and the
# selected ``run.method`` branches are requested as well so the raw document
# keeps the resolved geometry (the fallback for entries without an OPTIMADE
# structure) plus the k-point mesh, and basis-set settings. Only the needed
# sub-branches are listed because ``"*"`` would also pull the bulk code-specific
# dumps (VASP ``x_vasp_incar_*``) and symmetry/descriptor duplicates.
ARCHIVE_REQUIRED: dict[str, Any] = {
    "metadata": {
        "entry_id": "*",
        "upload_id": "*",
        "mainfile": "*",
        "license": "*",
        "external_db": "*",
        "origin": "*",
        "parser_name": "*",
        "published": "*",
        "entry_type": "*",
        "domain": "*",
        "upload_name": "*",
        "datasets": "*",
        "references": "*",
        "upload_create_time": "*",
        "optimade": "*",
    },
    "results": {
        "material": "*",
        "method": "*",
        "properties": "*",
    },
    "run": {
        "program": "*",
        "system": {
            "atoms": {
                "labels": "*",
                "positions": "*",
                "lattice_vectors": "*",
                "periodic": "*",
                "species": "*",
            },
        },
        "method": {
            "k_mesh": {
                "grid": "*",
                "dimensionality": "*",
                "sampling_method": "*",
                "n_points": "*",
            },
            "electrons_representation": {
                "type": "*",
                "native_tier": "*",
                "basis_set": {
                    "type": "*",
                    "scope": "*",
                    "cutoff": "*",
                    "frozen_core": "*",
                },
            },
            "basis_set": {
                "type": "*",
                "scope": "*",
                "cutoff": "*",
                "frozen_core": "*",
            },
            "scf": {"threshold_energy_change": "*"},
            "dft": "*",
        },
        "calculation[-1]": {"energy": "*"},
    },
    "workflow": {
        "calculation_result_ref": {"energy": "*"},
    },
}


class NomadError(RuntimeError):
    """Raised when a NOMAD request fails irrecoverably."""


@dataclass(frozen=True)
class NomadConfig:
    """Runtime settings for one NOMAD download task."""

    data_root: Path = Path("data/dft/nomad")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT
    token: str | None = None
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def raw_dir(self) -> Path:
        """Return the directory for per-entry archive documents."""
        return self.data_root / "raw"

    @property
    def bulk_dir(self) -> Path:
        """Return the directory for bulk zip archives."""
        return self.data_root / "raw" / "_bulk"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def load_environment() -> None:
    """Load a local ``.env`` when ``python-dotenv`` is available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def token_from_env() -> str | None:
    """Return ``NOMAD_API_TOKEN`` when it is configured and non-empty."""
    load_environment()
    value = os.environ.get("NOMAD_API_TOKEN", "").strip()
    return value or None


def default_data_root() -> Path:
    """Return ``NOMAD_DATA_ROOT`` or the standard output directory."""
    load_environment()
    return Path(os.getenv("NOMAD_DATA_ROOT", "data/dft/nomad"))


def source_id_for(entry_id: str) -> str:
    """Build the namespaced stable identifier used across NOMAD entries."""
    return f"nomad:{entry_id}"


def entry_url(entry_id: str) -> str:
    """Return the canonical GUI page for one entry."""
    return GUI_ENTRY_URL.format(entry_id=urllib.parse.quote(str(entry_id), safe=""))


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers(config: NomadConfig, *, content_type: str | None = None) -> dict[str, str]:
    """Build request headers, including an optional bearer token."""
    headers = {"User-Agent": config.user_agent, "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    return headers


def _open_with_retry(request: urllib.request.Request, config: NomadConfig,
                     timeout: int | None = None):
    """Open a request with retries on throttling and transient server errors.

    Client errors other than 429 are permanent and raise immediately. NOMAD
    returns HTTP 503 when rate limits are hit, so those are retried with a
    linear backoff.
    """
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            return urllib.request.urlopen(request, timeout=timeout or config.request_timeout)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                body = ""
                try:
                    body = error.read().decode("utf-8", "replace")[:400]
                except Exception:  # pragma: no cover - best-effort diagnostics
                    body = ""
                raise NomadError(f"HTTP {error.code} for {request.full_url}: {error.reason} {body}".strip()) from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
        if attempt < config.retry_count - 1:
            time.sleep(min(config.retry_delay * (attempt + 1), 60.0))
    raise NomadError(f"Failed to open {request.full_url}: {last_error}")


def http_post_json(url: str, payload: dict[str, Any], config: NomadConfig,
                   timeout: int | None = None) -> Any:
    """POST a JSON document and decode the JSON response."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=_headers(config, content_type="application/json"))
    with _open_with_retry(request, config, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_json(url: str, config: NomadConfig, timeout: int | None = None) -> Any:
    """GET a JSON document."""
    request = urllib.request.Request(url, headers=_headers(config))
    with _open_with_retry(request, config, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def _stream_post_to_file(url: str, payload: dict[str, Any], target: Path,
                         config: NomadConfig, logger: logging.Logger | None,
                         label: str) -> Path:
    """Stream a POST response body into ``target`` through a temp file."""
    if _is_complete(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.part")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=_headers(config, content_type="application/json"))
    try:
        with _open_with_retry(request, config) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=READ_CHUNK_BYTES)
        os.replace(temporary, target)
    except Exception:
        _quiet_unlink(temporary)
        raise
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", label, target, target.stat().st_size / (1024 * 1024))
    return target


# ---------------------------------------------------------------------------
# Native API client
# ---------------------------------------------------------------------------

class NomadClient:
    """Query the NOMAD native API for public entries and archive documents."""

    def __init__(self, config: NomadConfig | None = None):
        self.config = config or NomadConfig()

    def count(self, query: dict[str, Any] | None = None, *, owner: str = "public") -> int | None:
        """Return the number of entries matching ``query``."""
        payload = {
            "owner": owner,
            "query": query or {},
            "pagination": {"page_size": 1},
        }
        response = http_post_json(ENTRIES_QUERY_URL, payload, self.config)
        total = (response.get("pagination") or {}).get("total")
        return int(total) if total is not None else None

    def iter_entries(
        self,
        query: dict[str, Any] | None = None,
        *,
        owner: str = "public",
        page_size: int | None = None,
        max_records: int | None = None,
        after: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate entry metadata with ``page_after_value`` pagination."""
        size = page_size or self.config.page_size
        if not 1 <= size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        produced = 0
        cursor = after
        while True:
            pagination: dict[str, Any] = {"page_size": size, "order_by": "entry_id", "order": "asc"}
            if cursor:
                pagination["page_after_value"] = cursor
            payload = {"owner": owner, "query": query or {}, "pagination": pagination}
            response = http_post_json(ENTRIES_QUERY_URL, payload, self.config)
            data = response.get("data") or []
            if not data:
                return
            for item in data:
                if isinstance(item, dict):
                    yield item
                    produced += 1
                    if max_records is not None and produced >= max_records:
                        return
            cursor = (response.get("pagination") or {}).get("next_page_after_value")
            if not cursor or len(data) < size:
                return
            if self.config.sleep_seconds > 0:
                time.sleep(self.config.sleep_seconds)

    def fetch_archive(self, entry_id: str, *, required: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch one processed archive document by entry identifier."""
        safe = urllib.parse.quote(str(entry_id), safe="")
        url = f"{API_HOST}/entries/{safe}/archive/query"
        payload = {"required": required or ARCHIVE_REQUIRED}
        document = http_post_json(url, payload, self.config)
        if not isinstance(document, dict):
            raise NomadError(f"Unexpected archive response for {entry_id}")
        return document

    def download_archive_bulk(self, query: dict[str, Any] | None, target: str | Path,
                              *, owner: str = "public",
                              logger: logging.Logger | None = None) -> Path:
        """Stream a zip of per-entry archive documents for a query.

        The zip contains ``<upload-id>/<entry-id>.json`` members and a
        ``manifest.json``; each member is an object with ``entry_id``,
        ``parser_name`` and ``archive`` at the top level.
        """
        payload = {
            "owner": owner,
            "query": query or {},
            "required": ARCHIVE_REQUIRED,
        }
        return _stream_post_to_file(
            ARCHIVE_DOWNLOAD_QUERY_URL, payload, Path(target), self.config, logger,
            f"bulk:{json.dumps(query or {}, ensure_ascii=False)}",
        )


# ---------------------------------------------------------------------------
# Document iteration
# ---------------------------------------------------------------------------

def iter_archive_documents(
    config: NomadConfig | None = None,
    *,
    query: dict[str, Any] | None = None,
    owner: str = "public",
    page_size: int | None = None,
    max_records: int | None = None,
    after: str | None = None,
    persist_raw: bool = True,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate archive documents with per-entry raw persistence.

    Yields:
        dict[str, Any]: ``{"entry_id", "upload_id", "document", "url", "raw_path"}``.
    """
    cfg = config or NomadConfig()
    client = NomadClient(cfg)
    if logger is not None:
        logger.info("[START] nomad entries query=%s", json.dumps(query or {}, ensure_ascii=False))
    for meta in client.iter_entries(
        query, owner=owner, page_size=page_size, max_records=max_records, after=after,
    ):
        entry_id = meta.get("entry_id")
        if not entry_id:
            continue
        document = client.fetch_archive(entry_id)
        data = document.get("data") or {}
        upload_id = data.get("upload_id") or meta.get("upload_id") or "unknown"
        raw_path: str | None = None
        if persist_raw:
            raw_path = str(save_json_atomic(cfg.raw_dir / str(upload_id) / f"{entry_id}.json", document))
        if cfg.sleep_seconds > 0:
            time.sleep(cfg.sleep_seconds)
        yield {
            "entry_id": entry_id,
            "upload_id": upload_id,
            "document": document,
            "url": entry_url(entry_id),
            "raw_path": raw_path,
        }


def iter_bulk_zip_documents(zip_path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield one archive document per ``<entry-id>.json`` member of a zip.

    Yields:
        dict[str, Any]: ``{"entry_id", "upload_id", "document", "url"}``.
    """
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".json") or Path(name).name == "manifest.json":
                continue
            fallback_id = Path(name).stem
            with archive.open(name) as stream:
                payload = json.loads(stream.read().decode("utf-8"))
            if not isinstance(payload, dict):
                continue
            entry_id = payload.get("entry_id") or fallback_id
            raw_archive = payload.get("archive")
            if not isinstance(raw_archive, dict):
                # Already in the ``{"data": {"archive": ...}}`` shape.
                data = payload.get("data") or {}
                raw_archive = data.get("archive") or {}
                parser_name = data.get("parser_name")
            else:
                parser_name = payload.get("parser_name")
            upload_id = ((raw_archive.get("metadata") or {}).get("upload_id")
                         or payload.get("upload_id") or "unknown")
            document = {
                "entry_id": entry_id,
                "data": {
                    "entry_id": entry_id,
                    "upload_id": upload_id,
                    "parser_name": parser_name,
                    "archive": raw_archive,
                },
            }
            yield {
                "entry_id": entry_id,
                "upload_id": upload_id,
                "document": document,
                "url": entry_url(entry_id),
            }


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path: str | Path, *, source: str = "nomad",
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

    def is_completed(self, entry_id: str) -> bool:
        """Return whether one entry is already indexed for this schema version."""
        row = self._load(source_id_for(entry_id))
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
    entry_id: str,
    *,
    source: str = "nomad",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one NOMAD entry is already indexed."""
    with CompletionIndex(db_path, source=source, schema_version=schema_version) as index:
        return index.is_completed(entry_id)


__all__ = [
    "API_HOST",
    "API_VERSION",
    "ARCHIVE_DOWNLOAD_QUERY_URL",
    "ARCHIVE_REQUIRED",
    "CompletionIndex",
    "ENTRIES_QUERY_URL",
    "GUI_ENTRY_URL",
    "MAX_PAGE_SIZE",
    "NomadClient",
    "NomadConfig",
    "NomadError",
    "completed",
    "default_data_root",
    "entry_url",
    "http_get_json",
    "http_post_json",
    "iter_archive_documents",
    "iter_bulk_zip_documents",
    "load_environment",
    "save_json_atomic",
    "source_id_for",
    "token_from_env",
]
