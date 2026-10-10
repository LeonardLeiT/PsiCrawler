"""Catalysis-Hub raw download: GraphQL queries over surface-reaction data.

Catalysis-Hub (SUNCAT Center, SLAC/Stanford) exposes an ASE-based database of
DFT surface calculations through a GraphQL endpoint. The ``systems`` table holds
atomic structures (slabs and adsorbates) with total energies and metadata; the
``reactions`` table holds reaction energies that reference those systems.

The endpoint requires a free API key, passed in the ``X-API-Key`` header. Supply
it through the ``CATALYSIS_HUB_API_KEY`` environment variable (or a local
``.env``), following the same pattern as the Materials Project key.

This module never touches the standard schema.
"""

from __future__ import annotations

import base64
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests

GRAPHQL_URL = "https://api-catalysis-hub.slac.stanford.edu/graphql"
DEFAULT_DATA_ROOT = Path("data/dft/catalysishub")
DEFAULT_PAGE_SIZE = 50
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"

# Fields requested for each system record. ``Cifdata`` carries the structure.
SYSTEM_FIELDS = (
    "id",
    "uniqueId",
    "energy",
    "natoms",
    "volume",
    "Formula",
    "Cifdata",
    "DftCode",
    "DftFunctional",
    "Substrate",
    "Facet",
    "Adsorbate",
    "ctime",
    "mtime",
)


class CatalysisHubError(RuntimeError):
    """Raised when a Catalysis-Hub request fails irrecoverably."""


@dataclass(frozen=True)
class CatalysisHubConfig:
    """Runtime settings for one Catalysis-Hub download task."""

    api_key: str = ""
    data_root: Path = DEFAULT_DATA_ROOT
    graphql_url: str = GRAPHQL_URL
    page_size: int = DEFAULT_PAGE_SIZE
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_environment(cls, data_root: str | Path = DEFAULT_DATA_ROOT) -> "CatalysisHubConfig":
        """Build configuration from environment variables or a local ``.env`` file."""
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        api_key = os.getenv("CATALYSIS_HUB_API_KEY", "")
        if not api_key or api_key.startswith("replace_with_"):
            api_key = ""
        return cls(api_key=api_key, data_root=Path(os.getenv("CATALYSIS_HUB_DATA_ROOT", str(data_root))))

    @property
    def raw_dir(self) -> Path:
        """Return the directory for raw GraphQL responses."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


def source_id_for(system_id: Any) -> str:
    """Build the stable identifier used across the index."""
    return str(system_id).strip()


# ---------------------------------------------------------------------------
# GraphQL client
# ---------------------------------------------------------------------------

def gql(query: str, config: CatalysisHubConfig, *, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query and return the ``data`` object.

    Raises:
        CatalysisHubError: on a missing key, a GraphQL error, or a transport
            failure after retries.
    """
    if not config.api_key:
        raise CatalysisHubError(
            "CATALYSIS_HUB_API_KEY is required; copy .env.example to .env and set a key "
            "obtained from https://api-catalysis-hub.slac.stanford.edu/auth/login"
        )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": config.api_key,
        "User-Agent": config.user_agent,
    }
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            response = requests.post(
                config.graphql_url,
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=config.request_timeout,
            )
        except requests.RequestException as error:
            last_error = error
            if attempt < config.retry_count - 1:
                time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
            continue
        if response.status_code == 401:
            raise CatalysisHubError(f"Catalysis-Hub rejected the API key (HTTP 401): {response.text}")
        if 400 <= response.status_code < 500 and response.status_code != 429:
            raise CatalysisHubError(f"HTTP {response.status_code} for GraphQL: {response.text}")
        if response.status_code >= 500 or response.status_code == 429:
            last_error = CatalysisHubError(f"HTTP {response.status_code} for GraphQL")
            if attempt < config.retry_count - 1:
                time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
            continue
        document = response.json()
        break
    else:
        raise CatalysisHubError(f"Failed GraphQL request: {last_error}")
    if document.get("errors"):
        raise CatalysisHubError(f"GraphQL errors: {document['errors']}")
    return document.get("data") or {}


def _connection_query(table: str, fields: tuple[str, ...]) -> str:
    """Build a cursor-paginated connection query for one table."""
    selection = " ".join(fields)
    return (
        f"query($first: Int!, $after: String) {{ {table}(first: $first, after: $after) {{ "
        f"pageInfo {{ hasNextPage endCursor }} edges {{ node {{ {selection} }} }} }} }}"
    )


def iter_systems(
    config: CatalysisHubConfig,
    *,
    fields: tuple[str, ...] = SYSTEM_FIELDS,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate Catalysis-Hub ``systems`` with cursor pagination."""
    query = _connection_query("systems", fields)
    cursor: str | None = None
    produced = 0
    while True:
        data = gql(query, config, variables={"first": config.page_size, "after": cursor})
        connection = data.get("systems") or {}
        edges = connection.get("edges") or []
        if not edges:
            return
        for edge in edges:
            node = edge.get("node")
            if isinstance(node, dict):
                yield node
                produced += 1
                if max_records is not None and produced >= max_records:
                    return
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return
        cursor = page_info.get("endCursor")
        if not cursor:
            return
        if config.sleep_seconds > 0:
            time.sleep(config.sleep_seconds)


def _numeric_system_id(value: Any) -> int:
    """Resolve a numeric ``systems.id`` from a plain integer or a global Relay id.

    The GraphQL ``systems(id:)`` filter takes an ``Int``; the node ``id`` field is
    a base64 global id that decodes to ``System:<n>``.
    """
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        decoded = base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", errors="replace")
    except Exception:
        decoded = ""
    tail = decoded.rsplit(":", 1)[-1] if ":" in decoded else ""
    if tail.isdigit():
        return int(tail)
    raise CatalysisHubError(f"Cannot resolve a numeric system id from {value!r}")


def read_system(
    system_id: str,
    config: CatalysisHubConfig,
    *,
    fields: tuple[str, ...] = SYSTEM_FIELDS,
) -> dict[str, Any] | None:
    """Fetch one ``systems`` record by its numeric or global id."""
    numeric = _numeric_system_id(system_id)
    selection = " ".join(fields)
    query = f"query($id: Int!) {{ systems(id: $id) {{ edges {{ node {{ {selection} }} }} }} }}"
    data = gql(query, config, variables={"id": numeric})
    edges = (data.get("systems") or {}).get("edges") or []
    for edge in edges:
        node = edge.get("node")
        if isinstance(node, dict):
            return node
    return None


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class CompletionIndex:
    """Reusable read handle for resume checks during one crawler run."""

    def __init__(self, db_path_value: str | Path, *, source: str = "catalysishub",
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

    def is_completed(self, system_id: str) -> bool:
        """Return whether one Catalysis-Hub system is already indexed."""
        row = self._load(source_id_for(system_id))
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
    system_id: str,
    *,
    source: str = "catalysishub",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one Catalysis-Hub system is already indexed."""
    with CompletionIndex(db_path_value, source=source, schema_version=schema_version) as index:
        return index.is_completed(system_id)


__all__ = [
    "GRAPHQL_URL",
    "SYSTEM_FIELDS",
    "CatalysisHubConfig",
    "CatalysisHubError",
    "CompletionIndex",
    "completed",
    "gql",
    "iter_systems",
    "read_system",
    "source_id_for",
]
