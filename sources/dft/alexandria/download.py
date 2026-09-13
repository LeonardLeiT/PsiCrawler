"""Alexandria (AMD) raw download: bulk JSON.bz2 archives and OPTIMADE queries.

This module never touches the standard schema. It retrieves upstream documents
and files as completely as the Alexandria database exposes them and writes them
under ``data/dft/alexandria/raw``.

Two access paths are supported:

- Bulk archives served by the nginx directory index, for example
  ``data/pbe/2025.07.02/alexandria_00000.json.bz2``. Each archive is a single
  JSON object ``{"entries": [ComputedStructureEntry, ...]}`` that is streamed
  entry by entry so multi-hundred-megabyte files never need to fit in memory.
- The OPTIMADE REST API at ``/<prefix>/v1/structures`` for on-demand, per-record
  and filtered queries. The PBE backend can be unavailable, so callers must be
  able to fall back to the bulk archives.
"""

from __future__ import annotations

import bz2
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

BASE_URL = "https://alexandria.icams.rub.de"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_USER_AGENT = "PsiCrawler/0.1 (academic research; contact: local operator)"
READ_CHUNK_BYTES = 1 << 20

OPTIMADE_PREFIXES = {"pbe": "pbe", "pbesol": "pbesol", "scan": "scan"}


@dataclass(frozen=True)
class Dataset:
    """One Alexandria dataset and how to enumerate its files."""

    name: str
    kind: str
    format: str
    functional: str | None
    dimensionality: int | None
    directory: str | None = None
    pattern: str | None = None
    files: tuple[str, ...] = ()
    description: str = ""

    @property
    def is_primary(self) -> bool:
        """Return whether the dataset carries standard entry documents."""
        return self.kind == "primary"


DATASETS: dict[str, Dataset] = {
    "pbe-3d": Dataset(
        name="pbe-3d", kind="primary", format="entries", functional="PBE", dimensionality=3,
        directory="data/pbe/2025.07.02/", pattern=r"^alexandria_\d+\.json\.bz2$",
        description="PBE-relaxed 3D crystals, complete database 2025.07.02.",
    ),
    "pbe-2d": Dataset(
        name="pbe-2d", kind="primary", format="entries", functional="PBE", dimensionality=2,
        directory="data/pbe_2d/", pattern=r"^alexandria_2d_\d+\.json\.bz2$",
        description="PBE-relaxed 2D materials.",
    ),
    "pbe-1d": Dataset(
        name="pbe-1d", kind="primary", format="entries", functional="PBE", dimensionality=1,
        directory="data/pbe_1d/", pattern=r"^alexandria_1d_\d+\.json\.bz2$",
        description="PBE-relaxed 1D materials.",
    ),
    "pbesol": Dataset(
        name="pbesol", kind="primary", format="entries", functional="PBEsol", dimensionality=3,
        directory="data/pbesol/", pattern=r"^alexandria_ps_\d+\.json\.bz2$",
        description="PBEsol-relaxed 3D crystals.",
    ),
    "scan": Dataset(
        name="scan", kind="primary", format="entries", functional="SCAN", dimensionality=3,
        directory="data/scan/", pattern=r"^alexandria_scan_\d+\.json\.bz2$",
        description="SCAN-relaxed 3D crystals.",
    ),
    "convex-hull-pbe": Dataset(
        name="convex-hull-pbe", kind="aux", format="json", functional="PBE", dimensionality=3,
        files=("data/pbe/2025.07.02/convex_hull.json.bz2",),
        description="PBE convex hull.",
    ),
    "convex-hull-pbesol": Dataset(
        name="convex-hull-pbesol", kind="aux", format="json", functional="PBEsol", dimensionality=3,
        files=("data/pbesol/convex_hull_ps_2023.12.29.json.bz2",),
        description="PBEsol convex hull.",
    ),
    "convex-hull-scan": Dataset(
        name="convex-hull-scan", kind="aux", format="json", functional="SCAN", dimensionality=3,
        files=("data/scan/convex_hull_scan_2023.12.29.json.bz2",),
        description="SCAN convex hull.",
    ),
    "geo-opt-pbe": Dataset(
        name="geo-opt-pbe", kind="aux", format="optpath", functional="PBE", dimensionality=3,
        directory="data/geo_opt_paths/2025.07.02/pbe/", pattern=r"^pbe_\d+\.json\.bz2$",
        description="PBE geometry-optimization paths.",
    ),
    "geo-opt-pbe-2d": Dataset(
        name="geo-opt-pbe-2d", kind="aux", format="optpath", functional="PBE", dimensionality=2,
        directory="data/geo_opt_paths/2025.07.02/pbe_2d/", pattern=r".*\.json\.bz2$",
        description="PBE 2D geometry-optimization paths.",
    ),
    "geo-opt-pbe-1d": Dataset(
        name="geo-opt-pbe-1d", kind="aux", format="optpath", functional="PBE", dimensionality=1,
        directory="data/geo_opt_paths/2025.07.02/pbe_1d/", pattern=r".*\.json\.bz2$",
        description="PBE 1D geometry-optimization paths.",
    ),
    "geo-opt-pbesol": Dataset(
        name="geo-opt-pbesol", kind="aux", format="optpath", functional="PBEsol", dimensionality=3,
        directory="data/geo_opt_paths/2024.05.24/pbesol/", pattern=r".*\.json\.bz2$",
        description="PBEsol geometry-optimization paths.",
    ),
    "phonons-pbesol-3d": Dataset(
        name="phonons-pbesol-3d", kind="aux", format="phonon", functional="PBEsol", dimensionality=3,
        directory="data/pbesol_ph/3d/", pattern=r"^alexandria_ph_\d+\.json\.bz2$",
        description="PBEsol 3D phonon and electron-phonon calculations.",
    ),
    "phonons-pbesol-2d": Dataset(
        name="phonons-pbesol-2d", kind="aux", format="phonon", functional="PBEsol", dimensionality=2,
        directory="data/pbesol_ph/2d/", pattern=r"^alexandria_ph_\d+\.json\.bz2$",
        description="PBEsol 2D phonon calculations.",
    ),
    "benchmarks-wbm": Dataset(
        name="benchmarks-wbm", kind="aux", format="entries", functional="PBE", dimensionality=3,
        directory="data/pbe/benchmarks/wbm/", pattern=r"^wbm_\d+\.json\.bz2$",
        description="Wang-Botti-Marques benchmark structures.",
    ),
    "benchmarks-dimensionality": Dataset(
        name="benchmarks-dimensionality", kind="aux", format="json", functional="PBE", dimensionality=None,
        directory="data/pbe/benchmarks/dimensionality/", pattern=r".*\.bz2$",
        description="Dimensionality benchmark.",
    ),
    "benchmarks-pressure": Dataset(
        name="benchmarks-pressure", kind="aux", format="json", functional="PBE", dimensionality=None,
        directory="data/pbe/benchmarks/pressure/", pattern=r".*\.bz2$",
        description="Pressure benchmark.",
    ),
    "phonon-benchmark": Dataset(
        name="phonon-benchmark", kind="aux", format="json", functional="PBE", dimensionality=None,
        directory="data/phonon_benchmark/", pattern=r".*\.(bz2|tar\.gz|csv)$",
        description="Phonon benchmark.",
    ),
    "prototypes": Dataset(
        name="prototypes", kind="aux", format="archive", functional="PBE", dimensionality=None,
        files=("data/pbe/prototypes.tar.bz2",),
        description="PBE prototype CIF library.",
    ),
    "potcar-pbe": Dataset(
        name="potcar-pbe", kind="aux", format="file", functional="PBE", dimensionality=None,
        files=("data/pbe/potcar_pbe.dat",),
        description="POTCARs used for the PBE database.",
    ),
    "potcar-pbesol": Dataset(
        name="potcar-pbesol", kind="aux", format="file", functional="PBEsol", dimensionality=None,
        files=("data/pbesol/potcar_pbesol.dat",),
        description="POTCARs used for the PBEsol database.",
    ),
    "older-perovskites": Dataset(
        name="older-perovskites", kind="aux", format="entries", functional="PBE", dimensionality=3,
        files=("data/older/perovskites-HT-ComputedStructureEntry.json.bz2",),
        description="High-throughput perovskite dataset.",
    ),
    "older-substitutions": Dataset(
        name="older-substitutions", kind="aux", format="entries", functional="PBE", dimensionality=3,
        files=(
            "data/older/substitutions_000.json.bz2",
            "data/older/substitutions_001.json.bz2",
            "data/older/substitutions_002.json.bz2",
        ),
        description="Chemical-similarity substitution dataset.",
    ),
}

PRIMARY_DATASETS = tuple(name for name, dataset in DATASETS.items() if dataset.is_primary)


class AlexandriaError(RuntimeError):
    """Raised when an Alexandria request fails irrecoverably."""


@dataclass(frozen=True)
class AlexandriaConfig:
    """Runtime settings for one Alexandria download task."""

    data_root: Path = Path("data/dft/alexandria")
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
        raise KeyError(f"Unknown Alexandria dataset {name!r}; known: {', '.join(DATASETS)}") from error


def source_id_for(dataset: str, mat_id: str) -> str:
    """Build the namespaced stable identifier used across primary datasets."""
    return f"{dataset}:{mat_id}"


def _http_open(url: str, config: AlexandriaConfig, timeout: int | None = None):
    """Open a URL with the configured user agent and retry policy."""
    request = urllib.request.Request(url, headers={"User-Agent": config.user_agent})
    last_error: Exception | None = None
    for attempt in range(config.retry_count):
        try:
            return urllib.request.urlopen(request, timeout=timeout or config.request_timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt < config.retry_count - 1:
                time.sleep(min(config.retry_delay * (attempt + 1), 30.0))
    raise AlexandriaError(f"Failed to open {url}: {last_error}")


def http_get_bytes(url: str, config: AlexandriaConfig, timeout: int | None = None) -> bytes:
    """Fetch raw bytes from a URL."""
    with _http_open(url, config, timeout=timeout) as response:
        return response.read()


def http_get_json(url: str, config: AlexandriaConfig, timeout: int | None = None) -> Any:
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


# ---------------------------------------------------------------------------
# Remote file discovery
# ---------------------------------------------------------------------------

def list_remote_files(dataset: Dataset | str, config: AlexandriaConfig | None = None) -> list[str]:
    """Return the dataset file paths relative to the Alexandria host.

    Explicit ``files`` are returned as-is. Directory datasets are resolved by
    parsing the nginx autoindex and filtering names through the dataset pattern.
    """
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    if dataset.files:
        return list(dataset.files)
    if not dataset.directory:
        return []
    cfg = config or AlexandriaConfig()
    listing = http_get_bytes(f"{BASE_URL}/{dataset.directory}", cfg).decode("utf-8", errors="replace")
    hrefs = re.findall(r'href="([^"]+)"', listing)
    pattern = re.compile(dataset.pattern or r".*")
    selected: list[str] = []
    for href in hrefs:
        name = href.split("/")[-1]
        if not name or name.startswith("."):
            continue
        if pattern.search(name):
            selected.append(f"{dataset.directory}{name}")
    return sorted(selected)


def download_file(
    dataset: Dataset | str,
    relative_path: str,
    config: AlexandriaConfig | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Download one dataset file into ``raw/<dataset>/`` and return its path."""
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    cfg = config or AlexandriaConfig()
    target = cfg.raw_dir / dataset.name / Path(relative_path).name
    if _is_complete(target):
        return target
    url = f"{BASE_URL}/{relative_path}"
    target.parent.mkdir(parents=True, exist_ok=True)
    # A per-process unique temp name keeps concurrent downloads of the same file
    # from corrupting each other; the final ``os.replace`` stays atomic.
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
            # Another process may hold the destination open; reuse it if valid.
            if _is_complete(target):
                _quiet_unlink(temporary)
                return target
            raise
    except Exception:
        _quiet_unlink(temporary)
        raise
    if logger is not None:
        logger.info("[FILE] %s -> %s (%.1f MB)", relative_path, target, target.stat().st_size / (1024 * 1024))
    if cfg.sleep_seconds > 0:
        time.sleep(cfg.sleep_seconds)
    return target


# ---------------------------------------------------------------------------
# Streaming JSON array reader
# ---------------------------------------------------------------------------

def _iter_array_items(stream: Any, key: str = "entries", chunk_size: int = READ_CHUNK_BYTES) -> Iterator[Any]:
    """Yield the items of one top-level JSON array without loading it whole.

    The reader locates ``"<key>": [`` and then decodes one element at a time with
    :class:`json.JSONDecoder`. It only buffers enough characters to hold the
    element currently being decoded, so very large archives stay memory-safe.
    """
    decoder = json.JSONDecoder()
    buffer = ""
    pos = 0
    eof = False

    def pull_more() -> bool:
        nonlocal buffer, pos, eof
        if eof:
            return False
        if pos:
            buffer = buffer[pos:]
            pos = 0
        chunk = stream.read(chunk_size)
        if not chunk:
            eof = True
            return False
        buffer += chunk
        return True

    marker = f'"{key}"'
    while True:
        index = buffer.find(marker, pos)
        if index != -1:
            bracket = buffer.find("[", index + len(marker))
            if bracket != -1:
                pos = bracket + 1
                break
        if not pull_more():
            raise ValueError(f"top-level array {key!r} not found in JSON document")

    while True:
        while True:
            while pos < len(buffer) and buffer[pos] in " \t\r\n,":
                pos += 1
            if pos < len(buffer) or eof:
                break
            pull_more()
        if pos >= len(buffer) and eof:
            return
        if buffer[pos] == "]":
            return
        while True:
            try:
                item, end = decoder.raw_decode(buffer, pos)
            except json.JSONDecodeError:
                if not pull_more():
                    raise
                continue
            pos = end
            yield item
            break


def iter_entries(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream the ``entries`` of one downloaded Alexandria archive."""
    with bz2.open(Path(path), "rt", encoding="utf-8") as stream:
        for item in _iter_array_items(stream, "entries"):
            if isinstance(item, dict):
                yield item


def iter_dataset_entries(
    dataset: Dataset | str,
    config: AlexandriaConfig | None = None,
    *,
    max_files: int | None = None,
    max_records: int | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[dict[str, Any]]:
    """Download a primary dataset and stream its entries.

    Yields:
        dict[str, Any]: ``{"dataset", "file", "index", "raw_path", "entry"}``.
    """
    if isinstance(dataset, str):
        dataset = get_dataset(dataset)
    cfg = config or AlexandriaConfig()
    files = list_remote_files(dataset, cfg)
    if max_files is not None:
        files = files[:max_files]
    produced = 0
    for filename in files:
        local = download_file(dataset, filename, cfg, logger=logger)
        for index, entry in enumerate(iter_entries(local)):
            yield {
                "dataset": dataset.name,
                "file": Path(filename).name,
                "index": index,
                "raw_path": str(local),
                "entry": entry,
            }
            produced += 1
            if max_records is not None and produced >= max_records:
                return


# ---------------------------------------------------------------------------
# OPTIMADE queries
# ---------------------------------------------------------------------------

class OptimadeClient:
    """Query the Alexandria OPTIMADE API for on-demand records."""

    def __init__(self, config: AlexandriaConfig | None = None, prefix: str = "pbe"):
        if prefix not in OPTIMADE_PREFIXES:
            raise ValueError(f"Unknown OPTIMADE prefix {prefix!r}; known: {', '.join(OPTIMADE_PREFIXES)}")
        self.config = config or AlexandriaConfig()
        self.prefix = prefix
        self.base_url = f"{BASE_URL}/{OPTIMADE_PREFIXES[prefix]}/v1"

    def fetch_info(self, entry_type: str | None = None) -> dict[str, Any]:
        """Return the OPTIMADE ``info`` document, optionally for one entry type."""
        suffix = f"/{entry_type}" if entry_type else ""
        payload = http_get_json(f"{self.base_url}/info{suffix}", self.config)
        return payload.get("data", {})

    def fetch_structure(self, entry_id: str) -> dict[str, Any] | None:
        """Fetch one structure record by its ``agm`` identifier."""
        url = f"{self.base_url}/structures/{urllib.parse.quote(str(entry_id), safe='')}"
        payload = http_get_json(url, self.config)
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def iter_structures(
        self,
        *,
        filter_expression: str | None = None,
        response_fields: Iterable[str] | None = None,
        page_limit: int = 100,
        max_records: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate structures with offset pagination until exhausted."""
        if page_limit <= 0:
            raise ValueError("page_limit must be positive")
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
    """Flatten one OPTIMADE record into an id + attributes document."""
    attributes = record.get("attributes") or {}
    return {"id": record.get("id"), "type": record.get("type"), **attributes}


def fetch_optimade_structure(
    entry_id: str,
    config: AlexandriaConfig | None = None,
    prefix: str = "pbe",
) -> dict[str, Any] | None:
    """Fetch one OPTIMADE structure as a flat document, or ``None`` if absent."""
    record = OptimadeClient(config, prefix).fetch_structure(entry_id)
    return optimade_record_to_document(record) if record else None


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

def _load_record(db_path: str | Path, source: str, identifier: str) -> dict[str, Any] | None:
    """Read one normalized record by ``source_id`` or ``requested_id``."""
    database = Path(db_path)
    if not database.exists():
        return None
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT * FROM records WHERE source = ? AND (source_id = ? OR requested_id = ?)",
                (source, identifier, identifier),
            ).fetchone()
        except sqlite3.OperationalError:
            row = connection.execute(
                "SELECT * FROM records WHERE source = ? AND source_id = ?",
                (source, identifier),
            ).fetchone()
    return dict(row) if row is not None else None


def completed(
    db_path: str | Path,
    dataset: str,
    mat_id: str,
    *,
    source: str = "alexandria",
    schema_version: str = "3.0",
) -> bool:
    """Return whether one primary dataset entry is already indexed."""
    identifier = source_id_for(dataset, mat_id)
    row = _load_record(db_path, source, identifier)
    if not row:
        return False
    if row.get("schema_version") != schema_version:
        return False
    if row.get("download_status") not in {"success", "partial"}:
        return False
    raw_path = row.get("raw_path")
    if not raw_path or not Path(raw_path).exists():
        return False
    return True


__all__ = [
    "AlexandriaConfig",
    "AlexandriaError",
    "BASE_URL",
    "DATASETS",
    "Dataset",
    "OptimadeClient",
    "PRIMARY_DATASETS",
    "completed",
    "download_file",
    "fetch_optimade_structure",
    "get_dataset",
    "http_get_bytes",
    "http_get_json",
    "iter_dataset_entries",
    "iter_entries",
    "list_remote_files",
    "optimade_record_to_document",
    "source_id_for",
]
