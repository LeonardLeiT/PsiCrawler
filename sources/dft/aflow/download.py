"""AFLOW raw download: metadata, files, AFLUX search, and local storage.

This module never touches the standard schema. It only retrieves upstream
documents/files and writes them under ``data/dft/aflow/raw``.
"""

from __future__ import annotations

import fnmatch
import json
import lzma
import logging
import os
import sqlite3
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AFLUX_BASE_URL = "https://aflow.org/API/aflux/"
AFLOWLIB_HTTP_BASE = "http://aflowlib.duke.edu"
DEFAULT_AURL = "aflowlib.duke.edu:AFLOWDATA/ICSD_WEB/HEX/Li3N1_ICSD_642176"
DEFAULT_PROFILE = "all"
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_USER_AGENT = "aflow-python-extractor/0.2 (academic non-commercial use)"

NON_DATA_FILES = {"index.php", "favicon.ico"}

AEL_FIELD_NAMES = (
    "ael_bulk_modulus_vrh", "ael_shear_modulus_vrh", "ael_youngs_modulus_vrh",
    "ael_poisson_ratio", "ael_debye_temperature",
)
AGL_FIELD_NAMES = ("agl_debye", "agl_thermal_conductivity_300K", "agl_thermal_expansion_300K")
MAGNETISM_FIELD_NAMES = ("spin_cell", "spin_atom", "spinD", "spinF")
BADER_FIELD_NAMES = ("bader_net_charges", "bader_atomic_volumes")
CALCULATION_FIELD_NAMES = (
    "code", "dft_type", "energy_cutoff", "kpoints_relax", "kpoints_static",
    "kpoints_bands_path", "kpoints_bands_nkpts", "calculation_time",
    "calculation_memory", "calculation_cores", "node_CPU_Model", "node_CPU_Cores",
    "node_CPU_MHz", "node_RAM_GB",
)

CATEGORIES = (
    "metadata", "structures", "electronic_structure", "figure",
    "elasticity", "thermal", "magnetism", "bader", "symmetry", "calculation",
    "optional_full_mirror",
)


@dataclass(frozen=True)
class AflowConfig:
    """Runtime settings for one AFLOW download task."""

    data_root: Path = Path("data/dft/aflow")
    request_timeout: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def raw_dir(self) -> Path:
        """Return the directory for source AFLOW files."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


@dataclass
class AflowDownloadResult:
    """Raw documents, downloaded file paths, and errors for one material."""

    identifier: str
    auid: str | None = None
    aurl: str | None = None
    compound: str | None = None
    profile: str = DEFAULT_PROFILE
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_path: str | None = None
    file_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        """Return the AFLOW stable identifier when available."""
        return self.auid or self.identifier


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def http_get_bytes(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS, user_agent: str = DEFAULT_USER_AGENT) -> bytes:
    """Fetch raw bytes from a URL."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def http_get_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Fetch and decode a JSON response."""
    return json.loads(http_get_bytes(url, timeout=timeout).decode("utf-8"))


def save_json_atomic(path: Path, data: Any) -> None:
    """Write JSON atomically so interrupted runs never leave partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def safe_filename(value: Any) -> str:
    """Return a filesystem-safe name for an AFLOW identifier."""
    text = str(value).replace(":", "_").replace("/", "_").replace("\\", "_")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def material_slug(item: dict[str, Any]) -> str:
    """Build a stable material directory name from the AFLOW index."""
    return safe_filename(item.get("auid", "unknown"))


def file_size_str(path: Path) -> str:
    """Render a human-readable file size."""
    if not path.exists():
        return "0 B"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def materialize_xz_files(paths: list[Path], errors: list[str] | None = None) -> list[Path]:
    """Decompress downloaded XZ files and remove the compressed originals."""
    materialized: list[Path] = []
    for path in paths:
        if path.suffix.lower() != ".xz":
            materialized.append(path)
            continue
        target = path.with_suffix("")
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            with lzma.open(path, "rb") as source, temporary.open("wb") as destination:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
            os.replace(temporary, target)
            path.unlink()
            materialized.append(target)
        except (OSError, lzma.LZMAError) as exc:
            if temporary.exists():
                temporary.unlink()
            if errors is not None:
                errors.append(f"Failed to decompress {path}: {exc}")
            materialized.append(path)
    return materialized


# ---------------------------------------------------------------------------
# AFLOW URL helpers
# ---------------------------------------------------------------------------

def aflux_url(query: str) -> str:
    """Build an encoded AFLUX query URL."""
    return AFLUX_BASE_URL + "?" + urllib.parse.quote(query, safe="(),*$':!._-")


def normalize_aurl_to_directory_url(identifier: str) -> str:
    """Normalize an AFLOW identifier to its material directory URL."""
    value = identifier.strip().strip('"').strip("'")
    if value.endswith("/aflowlib.json"):
        value = value[: -len("/aflowlib.json")]
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")
    if value.startswith("aflowlib.duke.edu:"):
        return f"{AFLOWLIB_HTTP_BASE}/{value.split(':', 1)[1].strip('/')}"
    if value.startswith("AFLOWDATA/"):
        return f"{AFLOWLIB_HTTP_BASE}/{value.strip('/')}"
    raise ValueError("Identifier must be an AFLOW aurl/path or a material directory URL")


def material_json_url(identifier: str) -> str:
    """Return the ``aflowlib.json`` URL for an identifier."""
    return f"{normalize_aurl_to_directory_url(identifier).rstrip('/')}/aflowlib.json"


def fetch_aflowlib_json(identifier: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Fetch one AFLOWLIB metadata document."""
    return http_get_json(material_json_url(identifier), timeout=timeout)


# ---------------------------------------------------------------------------
# AFLUX search
# ---------------------------------------------------------------------------

def quote_aflow_string(value: str) -> str:
    """Quote a string for an AFLUX filter."""
    return "'" + value.replace("'", "\\'") + "'"


def build_filter_query(
    query: str | None = None,
    species: str | None = None,
    catalog: str | None = None,
    compound_contains: str | None = None,
    egap_min: float | None = None,
    egap_max: float | None = None,
    spacegroup: int | None = None,
    ael: bool = False,
    agl: bool = False,
) -> str:
    """Build the AFLUX filter portion before field selection and paging."""
    if query:
        return query.strip().strip(",")
    filters: list[str] = []
    if species:
        for item in [value.strip() for value in species.split(",") if value.strip()]:
            filters.append(f"species({quote_aflow_string(item)})")
    if catalog:
        filters.append(f"catalog({quote_aflow_string(catalog.strip())})")
    if compound_contains:
        filters.append(f"compound(*{quote_aflow_string(compound_contains.strip())}*)")
    if egap_min is not None or egap_max is not None:
        lower = f"{egap_min}*" if egap_min is not None else "*"
        upper = f"*{egap_max}" if egap_max is not None else "*"
        if egap_min is not None and egap_max is not None:
            filters.append(f"Egap({lower},{upper})")
        elif egap_min is not None:
            filters.append(f"Egap({lower})")
        else:
            filters.append(f"Egap({upper})")
    if spacegroup is not None:
        filters.append(f"spacegroup_relax({spacegroup})")
    if ael:
        filters.append("ael_bulk_modulus_vrh(*)")
    if agl:
        filters.append("agl_debye(*)")
    if not filters:
        filters.append("Egap(1*,*2)")
    return ",".join(filters)


def make_search_query(filter_query: str, page: int, page_size: int) -> str:
    """Combine a filter, the selected AFLUX fields, and paging."""
    fields = ["aurl", "auid", "compound", "species", "catalog", "Egap", "Egap_type", "spacegroup_relax", "Pearson_symbol_relax"]
    return ",".join([filter_query, *fields, f"paging({page},{page_size})"])


def parse_total_count(result: dict[str, Any]) -> int | None:
    """Read the total match count from the AFLUX result header key."""
    if not result:
        return 0
    first_key = next(iter(result.keys()))
    if " of " not in first_key:
        return None
    try:
        return int(first_key.split(" of ", 1)[1])
    except ValueError:
        return None


def fetch_aurl_list(
    filter_query: str,
    max_materials: int,
    page_size: int = 100,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    logger: logging.Logger | None = None,
) -> list[dict[str, Any]]:
    """Fetch matching AFLUX entries that carry at least aurl/auid."""
    log = logger or logging.getLogger(__name__)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    page = 1
    total_count: int | None = None
    while len(entries) < max_materials:
        result = http_get_json(aflux_url(make_search_query(filter_query, page, page_size)), timeout=timeout)
        if total_count is None:
            total_count = parse_total_count(result)
            log.info("  AFLUX total matches: %s", total_count if total_count is not None else "unknown")
        if not result:
            break
        page_entries = list(result.values())
        if not page_entries:
            break
        for item in page_entries:
            if isinstance(item, dict) and item.get("aurl"):
                key = item.get("auid") or item.get("aurl")
                if key in seen:
                    continue
                seen.add(key)
                entries.append(item)
                if len(entries) >= max_materials:
                    break
        log.info("  Fetched page %d: %d entries, selected %d", page, len(page_entries), len(entries))
        if len(page_entries) < page_size:
            break
        if total_count is not None and page * page_size >= total_count:
            break
        page += 1
    return entries[:max_materials]


def read_aurls_file(path: str | Path) -> list[dict[str, Any]]:
    """Read one AURL per line, ignoring blanks and ``#`` comments."""
    entries: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            entries.append({"aurl": value})
    return entries


# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

def ensure_data_dirs(config: AflowConfig) -> dict[str, Path]:
    """Create the raw root and return the category directory map."""
    base = config.raw_dir
    base.mkdir(parents=True, exist_ok=True)
    dirs = {"base": base}
    for category in CATEGORIES:
        dirs[category] = base / category
    return dirs


def material_category_dir(dirs: dict[str, Path], category: str, item: dict[str, Any]) -> Path:
    """Return and create a material-local category directory."""
    path = dirs["base"] / material_slug(item) / category
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_category_jsons(item: dict[str, Any], dirs: dict[str, Path]) -> list[Path]:
    """Write small derived category JSON files from metadata fields."""
    saved: list[Path] = []
    specs = [
        ("elasticity", "ael.json", AEL_FIELD_NAMES),
        ("thermal", "agl.json", AGL_FIELD_NAMES),
        ("magnetism", "magnetism.json", MAGNETISM_FIELD_NAMES),
        ("bader", "bader.json", BADER_FIELD_NAMES),
        ("calculation", "calculation.json", CALCULATION_FIELD_NAMES),
    ]
    for category, filename, fields in specs:
        data = {name: item.get(name) for name in fields if item.get(name) is not None}
        if data:
            path = material_category_dir(dirs, category, item) / filename
            save_json_atomic(path, data)
            saved.append(path)
    return saved


def save_metadata_files(item: dict[str, Any], dirs: dict[str, Path], query_hit: dict[str, Any] | None = None) -> list[Path]:
    """Save aflowlib metadata and the source file manifest."""
    metadata_dir = material_category_dir(dirs, "metadata", item)
    saved = []
    aflowlib_path = metadata_dir / "aflowlib.json"
    save_json_atomic(aflowlib_path, item)
    saved.append(aflowlib_path)
    if query_hit:
        query_hit_path = metadata_dir / "query_hit.json"
        save_json_atomic(query_hit_path, query_hit)
        saved.append(query_hit_path)
    manifest_path = metadata_dir / "files_manifest.json"
    save_json_atomic(manifest_path, {"aurl": item.get("aurl"), "files": item.get("files", [])})
    saved.append(manifest_path)
    return saved


# ---------------------------------------------------------------------------
# File routing and profiles
# ---------------------------------------------------------------------------

def file_category(filename: str) -> tuple[str, list[str]] | None:
    """Classify an AFLOW filename into a category and optional subdirectories."""
    name = filename
    if name in {"ael.json", "ael.out"} or name.startswith("ael_"):
        return ("elasticity", [])
    if name in {"agl.json", "agl.out"} or name.startswith("agl_") or "phonon" in name.lower():
        return ("thermal", [])
    if fnmatch.fnmatch(name, "*.cif"):
        return ("structures", ["cif"])
    if name.startswith("CONTCAR") or name.startswith("POSCAR"):
        return ("structures", ["poscar"])
    if "structure_relax" in name and name.endswith(".json"):
        return ("structures", ["json"])
    if "banddos" in name and name.endswith(".png"):
        return ("figure", [])
    if name.endswith(".png") and ("dos" in name.lower() or name.startswith("bz_")):
        return ("figure", ["projected_dos"] if "_dos_" in name else [])
    if "bandsdata" in name or name.startswith("EIGENVAL") or name == "edata.bands.json" or name in {"KPOINTS.bands", "POSCAR.bands"}:
        return ("electronic_structure", ["bandstructure"])
    if "dosdata" in name or name.startswith("DOSCAR") or name == "edata.static.json":
        return ("electronic_structure", ["dos"])
    if name.startswith("aflow.") and (".group" in name or "iatoms" in name):
        return ("symmetry", [])
    if "Bader" in name or name.endswith("_abader.out"):
        return ("bader", ["jvxl"] if name.endswith(".jvxl") else [])
    if name.startswith("INCAR") or name.startswith("KPOINTS"):
        return ("calculation", ["inputs"])
    if name.startswith("OUTCAR"):
        return ("calculation", ["outputs"])
    if name.startswith(("CHGCAR", "AECCAR")):
        return ("calculation", ["charge_density"])
    return None


def profile_allows_file(filename: str, profile: str, extra_patterns: list[str] | None = None) -> bool:
    """Return whether a download profile permits a filename."""
    if extra_patterns and any(fnmatch.fnmatch(filename, pattern) for pattern in extra_patterns):
        return True
    route = file_category(filename)
    if route is None:
        return profile == "all"
    category, _ = route
    if profile == "core":
        return category == "structures"
    if profile == "plots":
        return category in {"structures", "figure"}
    if profile == "electronic":
        return category in {"structures", "figure", "electronic_structure"}
    if profile == "symmetry":
        return category in {"structures", "figure", "symmetry"}
    if profile == "bader":
        return category in {"structures", "figure", "bader"}
    if profile == "vasp_raw":
        return category in {"structures", "figure", "electronic_structure", "calculation"}
    if profile == "all":
        return True
    raise ValueError(f"Unknown profile: {profile}")


def destination_for_file(dirs: dict[str, Path], item: dict[str, Any], filename: str, profile: str) -> Path:
    """Return the local destination path for a downloaded AFLOW file."""
    route = file_category(filename)
    if route is None:
        base = material_category_dir(dirs, "optional_full_mirror", item)
    else:
        category, subdirs = route
        base = material_category_dir(dirs, category, item)
        for subdir in subdirs:
            base = base / subdir
        base.mkdir(parents=True, exist_ok=True)
    return base / filename.replace(":", "_")


def download_profile_files(
    item: dict[str, Any],
    dirs: dict[str, Path],
    profile: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_patterns: list[str] | None = None,
    errors: list[str] | None = None,
) -> list[Path]:
    """Download the files permitted by an AFLOW download profile."""
    aurl = item.get("aurl")
    files = item.get("files") or []
    if not aurl or not isinstance(files, list):
        return []
    directory_url = normalize_aurl_to_directory_url(aurl)
    saved: list[Path] = []
    for filename in files:
        if not isinstance(filename, str) or filename in NON_DATA_FILES:
            continue
        if not profile_allows_file(filename, profile, extra_patterns=extra_patterns):
            continue
        local_path = destination_for_file(dirs, item, filename, profile)
        url = f"{directory_url.rstrip('/')}/{urllib.parse.quote(filename, safe=':._-')}"
        try:
            data = None
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    data = http_get_bytes(url, timeout=timeout)
                    break
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(min(2.0 * (attempt + 1), 5.0))
            if data is None:
                raise last_error or OSError("empty response")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as stream:
                stream.write(data)
            print(f"    [FILE] {filename} -> {local_path} ({file_size_str(local_path)})")
            saved.append(local_path)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            message = f"{filename}: {exc}"
            print(f"    [WARN] Failed to download {message}")
            if errors is not None:
                errors.append(message)
    return saved


def download_one(
    identifier: str,
    config: AflowConfig | None = None,
    profile: str = DEFAULT_PROFILE,
    extra_patterns: list[str] | None = None,
    query_hit: dict[str, Any] | None = None,
    timeout: int | None = None,
) -> AflowDownloadResult:
    """Download and persist one AFLOW material exactly as returned upstream.

    Args:
        identifier (str): AFLOW AURL, path, or material directory URL.
        config (AflowConfig | None): AFLOW download configuration.
        profile (str): Download profile name.
        extra_patterns (list[str] | None): Additional filename patterns.
        query_hit (dict[str, Any] | None): Optional AFLUX query result.
        timeout (int | None): Request timeout in seconds.

    Returns:
        AflowDownloadResult: Metadata, downloaded paths, and errors.
    """
    config = config or AflowConfig()
    timeout = timeout or config.request_timeout
    result = AflowDownloadResult(identifier=identifier, profile=profile)
    dirs = ensure_data_dirs(config)
    item = fetch_aflowlib_json(identifier, timeout=timeout)
    result.metadata = item
    result.auid = item.get("auid")
    result.aurl = item.get("aurl")
    result.compound = item.get("compound")
    saved = save_metadata_files(item, dirs, query_hit=query_hit)
    result.raw_path = str(saved[0]) if saved else None
    saved += write_category_jsons(item, dirs)
    if config.sleep_seconds > 0:
        time.sleep(config.sleep_seconds)
    downloaded = download_profile_files(item, dirs, profile, timeout, extra_patterns, result.errors)
    downloaded = materialize_xz_files(downloaded, result.errors)
    result.file_paths = [str(path) for path in saved + downloaded]
    return result


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


def completed(db_path: str | Path, auid: str, *, source: str = "aflow", schema_version: str = "3.0") -> bool:
    """Return whether an AFLOW material is already fully downloaded."""
    row = _load_record(db_path, source, auid)
    if not row:
        return False
    if row.get("schema_version") != schema_version or row.get("download_status") != "success":
        return False
    raw_path = row.get("raw_path")
    return bool(raw_path) and Path(raw_path).exists()


__all__ = [
    "AflowConfig",
    "AflowDownloadResult",
    "DEFAULT_AURL",
    "DEFAULT_PROFILE",
    "aflux_url",
    "build_filter_query",
    "completed",
    "download_one",
    "fetch_aurl_list",
    "read_aurls_file",
]
