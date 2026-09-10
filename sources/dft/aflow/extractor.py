"""
Single material data extractor for AFLOW.

The layout is intentionally close to the Materials Project extractor, but
adapted to AFLOW's entry model: each material has one aflowlib.json plus a
directory of downloadable files.

Usage:
    python aflow_extract_single.py
    python aflow_extract_single.py --profile plots
    python aflow_extract_single.py --profile electronic
    python aflow_extract_single.py "aflowlib.duke.edu:AFLOWDATA/ICSD_WEB/HEX/Li3N1_ICSD_642176"
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sqlite3
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .normalize import normalize_aflow
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AFLUX_BASE_URL = "https://aflow.org/API/aflux/"
AFLOWLIB_HTTP_BASE = "http://aflowlib.duke.edu"
DEFAULT_AURL = "aflowlib.duke.edu:AFLOWDATA/ICSD_WEB/HEX/Li3N1_ICSD_642176"

DEFAULT_DB_PATH = "data/dft/aflow/database/aflow.sqlite"
DEFAULT_DATA_DIR = "data/dft/aflow"
DEFAULT_STATUS_JSON = "data/dft/aflow/manifests/status.json"
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_USER_AGENT = "aflow-python-extractor/0.2 (academic non-commercial use)"
DEFAULT_PROFILE = "all"


SCALAR_FIELDS = [
    "auid", "aurl", "catalog", "data_api", "data_source", "compound", "prototype",
    "nspecies", "natoms", "natoms_orig", "density", "density_orig",
    "species", "composition", "stoichiometry", "species_pp", "species_pp_version",
    "species_pp_ZVAL", "geometry", "geometry_orig", "volume_cell", "volume_atom",
    "volume_cell_orig", "volume_atom_orig", "spacegroup_orig", "spacegroup_relax",
    "Pearson_symbol_orig", "Pearson_symbol_relax", "Bravais_lattice_orig",
    "Bravais_lattice_relax", "crystal_family", "crystal_system", "crystal_class",
    "point_group_Hermann_Mauguin", "energy_cell", "energy_atom", "enthalpy_cell",
    "enthalpy_atom", "enthalpy_formation_cell", "enthalpy_formation_atom",
    "Egap", "Egap_type", "energy_cutoff", "spin_cell", "spin_atom", "spinD",
    "pressure", "pressure_residual", "stress_tensor", "ael_bulk_modulus_vrh",
    "ael_shear_modulus_vrh", "ael_youngs_modulus_vrh", "ael_poisson_ratio",
    "ael_debye_temperature", "agl_debye", "agl_thermal_conductivity_300K",
    "agl_thermal_expansion_300K", "bader_net_charges", "bader_atomic_volumes",
    "code", "dft_type", "calculation_time", "calculation_memory",
    "calculation_cores", "aflow_version", "aflowlib_version", "aflowlib_date",
]

AEL_FIELDS = [field for field in SCALAR_FIELDS if field.startswith("ael_")]
AGL_FIELDS = [field for field in SCALAR_FIELDS if field.startswith("agl_")]
MAGNETISM_FIELDS = ["spin_cell", "spin_atom", "spinD", "spinF"]
BADER_FIELDS = ["bader_net_charges", "bader_atomic_volumes"]
CALCULATION_FIELDS = [
    "code", "dft_type", "energy_cutoff", "kpoints_relax", "kpoints_static",
    "kpoints_bands_path", "kpoints_bands_nkpts", "calculation_time",
    "calculation_memory", "calculation_cores", "node_CPU_Model", "node_CPU_Cores",
    "node_CPU_MHz", "node_RAM_GB",
]

DB_FLAG_FIELDS = [
    "has_metadata", "has_structure", "has_bandstructure", "has_dos", "has_plots",
    "has_elasticity", "has_thermal", "has_magnetism", "has_bader",
    "has_symmetry", "has_calculation_files", "has_vasp_raw",
]

# Compatibility constants used by the batch script. Profiles are preferred.
DEFAULT_FILE_PATTERNS = ["*.cif", "CONTCAR.relax*", "*_structure_relax*.json", "*banddos.png", "*dos*.png", "bz_*.png"]
ELECTRONIC_FILE_PATTERNS = ["*bandsdata.json.xz", "*dosdata.json.xz", "edata.*.json", "EIGENVAL.bands.xz", "DOSCAR.static.xz"]
["OUTCAR.static.xz", "CHGCAR.static.xz", "AECCAR0.static.xz", "AECCAR2.static.xz"]
NON_DATA_FILES = {"index.php", "favicon.ico"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AflowExtractionReport:
    auid: str | None = None
    aurl: str | None = None
    compound: str | None = None
    profile: str = DEFAULT_PROFILE
    metadata: bool = False
    database: bool = False
    status_json: bool = False
    category_flags: dict[str, bool] = field(default_factory=dict)
    files_downloaded: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def print_report(self) -> None:
        print(f"\n{'=' * 60}")
        print("  AFLOW Extraction Report")
        print(f"{'=' * 60}")
        print(f"  AUID: {self.auid or 'unknown'}")
        print(f"  Compound: {self.compound or 'unknown'}")
        print(f"  AURL: {self.aurl or 'unknown'}")
        print(f"  Profile: {self.profile}")
        print(f"  Metadata JSON: {'[OK]' if self.metadata else '[--]'}")
        for key in sorted(self.category_flags):
            print(f"  {key}: {'[OK]' if self.category_flags[key] else '[--]'}")
        print(f"  SQLite: {'[OK]' if self.database else '[--]'}")
        print(f"  Status JSON: {'[OK]' if self.status_json else '[--]'}")
        print(f"  Files downloaded: {len(self.files_downloaded)}")
        for name in self.files_downloaded:
            print(f"    - {name}")
        if self.errors:
            print(f"\n  Errors ({len(self.errors)}):")
            for err in self.errors:
                print(f"    - {err}")
        print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def http_get_bytes(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS, user_agent: str = DEFAULT_USER_AGENT) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def http_get_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    return json.loads(http_get_bytes(url, timeout=timeout).decode("utf-8"))


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def safe_filename(value: Any) -> str:
    text = str(value)
    cleaned = text.replace(":", "_").replace("/", "_").replace("\\", "_")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in cleaned)


def material_slug(item: dict[str, Any]) -> str:
    """Build a stable material directory name from the AFLOW index.

    Args:
        item (dict[str, Any]): Raw AFLOWLIB metadata document.

    Returns:
        str: Filesystem-safe AFLOW index directory name.
    """
    auid = str(item.get("auid", "unknown"))
    return safe_filename(auid)

def json_or_none(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def file_size_str(path: Path) -> str:
    if not path.exists():
        return "0 B"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


# ---------------------------------------------------------------------------
# AFLOW URL helpers
# ---------------------------------------------------------------------------

def aflux_url(query: str) -> str:
    return AFLUX_BASE_URL + "?" + urllib.parse.quote(query, safe="(),*$':!._-")


def normalize_aurl_to_directory_url(identifier: str) -> str:
    value = identifier.strip().strip('"').strip("'")
    if value.endswith("/aflowlib.json"):
        value = value[: -len("/aflowlib.json")]
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    if value.startswith("aflowlib.duke.edu:"):
        path = value.split(":", 1)[1]
        return f"{AFLOWLIB_HTTP_BASE}/{path.strip('/')}"
    if value.startswith("AFLOWDATA/"):
        return f"{AFLOWLIB_HTTP_BASE}/{value.strip('/')}"
    raise ValueError("Identifier must be an AFLOW aurl/path or a material directory/aflowlib.json URL")


def material_json_url(identifier: str) -> str:
    return f"{normalize_aurl_to_directory_url(identifier).rstrip('/')}/aflowlib.json"


def material_directory_url_from_aurl(aurl: str) -> str:
    return normalize_aurl_to_directory_url(aurl)


def fetch_aflowlib_json(identifier: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Fetch one AFLOWLIB metadata document.

    Args:
        identifier (str): AFLOW AURL, path, or material directory URL.
        timeout (int): HTTP request timeout in seconds.

    Returns:
        dict[str, Any]: Raw AFLOWLIB metadata document.
    """
    from .client import AflowClient

    return AflowClient().fetch_metadata(identifier, timeout=timeout)


# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

def ensure_data_dirs(data_dir: str) -> dict[str, Path]:
    base = Path(data_dir)
    dirs = {
        "base": base,
        "metadata": base / "metadata",
        "structures": base / "structures",
        "electronic_structure": base / "electronic_structure",
        "figure": base / "figure",
        "elasticity": base / "elasticity",
        "thermal": base / "thermal",
        "magnetism": base / "magnetism",
        "bader": base / "bader",
        "symmetry": base / "symmetry",
        "calculation": base / "calculation",
        "raw": base / "raw",
        "normalized": base / "normalized",
    }
    # Create only the root now. Category/material directories are created lazily
    # when a file or derived JSON is actually written, so empty top-level folders
    # do not imply missing data.
    base.mkdir(parents=True, exist_ok=True)
    return dirs


def material_category_dir(dirs: dict[str, Path], category: str, item: dict[str, Any]) -> Path:
    """Return a source-specific category directory for one material.

    Args:
        dirs (dict[str, Path]): AFLOW data directory mapping.
        category (str): Material-local category name.
        item (dict[str, Any]): Raw AFLOWLIB metadata document.

    Returns:
        Path: Category directory under raw/<index> or normalized/<index>.
    """
    material_id = material_slug(item)
    if category == "normalized":
        path = dirs["normalized"] / material_id
    elif category == "raw":
        path = dirs["raw"] / material_id
    else:
        path = dirs["raw"] / material_id / category
    path.mkdir(parents=True, exist_ok=True)
    return path

def write_category_jsons(item: dict[str, Any], dirs: dict[str, Path]) -> tuple[dict[str, bool], list[Path]]:
    flags = {
        "has_elasticity": False,
        "has_thermal": False,
        "has_magnetism": False,
        "has_bader": False,
        "has_calculation_files": False,
    }
    saved_paths: list[Path] = []

    category_specs = [
        ("elasticity", "ael.json", AEL_FIELDS, "has_elasticity"),
        ("thermal", "agl.json", AGL_FIELDS, "has_thermal"),
        ("magnetism", "magnetism.json", MAGNETISM_FIELDS, "has_magnetism"),
        ("bader", "bader.json", BADER_FIELDS, "has_bader"),
        ("calculation", "calculation.json", CALCULATION_FIELDS, "has_calculation_files"),
    ]

    for category, filename, fields, flag in category_specs:
        data = {field: item.get(field) for field in fields if field in item and item.get(field) is not None}
        if data:
            path = material_category_dir(dirs, category, item) / filename
            save_json_atomic(path, data)
            saved_paths.append(path)
            flags[flag] = True

    return flags, saved_paths


# ---------------------------------------------------------------------------
# File routing and profiles
# ---------------------------------------------------------------------------

def file_category(filename: str) -> tuple[str, list[str]] | None:
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
        if "_dos_" in name:
            return ("figure", ["projected_dos"])
        return ("figure", [])

    if "bandsdata" in name or name.startswith("EIGENVAL") or name == "edata.bands.json" or name in {"KPOINTS.bands", "POSCAR.bands"}:
        return ("electronic_structure", ["bandstructure"])
    if "dosdata" in name or name.startswith("DOSCAR") or name == "edata.static.json":
        return ("electronic_structure", ["dos"])

    if name.startswith("aflow.") and (".group" in name or "iatoms" in name):
        return ("symmetry", [])

    if "Bader" in name or name.endswith("_abader.out"):
        if name.endswith(".jvxl"):
            return ("bader", ["jvxl"])
        return ("bader", [])

    if name.startswith("INCAR") or name.startswith("KPOINTS"):
        return ("calculation", ["inputs"])
    if name.startswith("OUTCAR"):
        return ("calculation", ["outputs"])
    if name.startswith(("CHGCAR", "AECCAR")):
        return ("calculation", ["charge_density"])

    return None


def profile_allows_file(filename: str, profile: str, extra_patterns: list[str] | None = None) -> bool:
    if extra_patterns and any(fnmatch.fnmatch(filename, pattern) for pattern in extra_patterns):
        return True

    route = file_category(filename)
    if route is None:
        return profile == "all"

    category, subdirs = route

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
    route = file_category(filename)
    if route is None:
        base = material_category_dir(dirs, "raw", item) / "optional_full_mirror"
        base.mkdir(parents=True, exist_ok=True)
    else:
        category, subdirs = route
        base = material_category_dir(dirs, category, item)
        for subdir in subdirs:
            base = base / subdir
        base.mkdir(parents=True, exist_ok=True)
    return base / filename.replace(":", "_")


def category_flags_from_downloads(downloaded_files: list[Path]) -> dict[str, bool]:
    text_paths = [str(path).replace("\\", "/") for path in downloaded_files]
    return {
        "has_structure": any("/structures/" in path for path in text_paths),
        "has_bandstructure": any("/electronic_structure/" in path and "/bandstructure/" in path for path in text_paths),
        "has_dos": any("/electronic_structure/" in path and "/dos/" in path for path in text_paths),
        "has_elasticity": any("/elasticity/" in path for path in text_paths),
        "has_thermal": any("/thermal/" in path for path in text_paths),
        "has_plots": any("/figure/" in path for path in text_paths),
        "has_symmetry": any("/symmetry/" in path for path in text_paths),
        "has_bader": any("/bader/" in path for path in text_paths),
        "has_calculation_files": any("/calculation/" in path for path in text_paths),
        "has_vasp_raw": any(name in path for path in text_paths for name in ["OUTCAR", "CHGCAR", "AECCAR", "DOSCAR", "EIGENVAL"]),
    }


# ---------------------------------------------------------------------------
# Database and status
# ---------------------------------------------------------------------------

def init_database(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    scalar_columns = ",\n            ".join(f"{field} TEXT" for field in SCALAR_FIELDS if field != "auid")
    flag_columns = ",\n            ".join(f"{field} INTEGER DEFAULT 0" for field in DB_FLAG_FIELDS)

    cur.executescript(f"""
        CREATE TABLE IF NOT EXISTS materials (
            auid TEXT PRIMARY KEY,
            {scalar_columns},
            {flag_columns},
            download_profile TEXT,
            downloaded_files_count INTEGER DEFAULT 0,
            extracted_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS material_json (
            auid TEXT PRIMARY KEY REFERENCES materials(auid),
            aflowlib_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS downloaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auid TEXT NOT NULL,
            filename TEXT NOT NULL,
            local_path TEXT NOT NULL,
            category TEXT,
            size_bytes INTEGER,
            downloaded_at TEXT DEFAULT (datetime('now')),
            UNIQUE(auid, filename)
        );

        CREATE TABLE IF NOT EXISTS extraction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            auid TEXT,
            aurl TEXT,
            status TEXT NOT NULL,
            error_msg TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            duration_ms INTEGER
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_materials_compound ON materials(compound);
        CREATE INDEX IF NOT EXISTS idx_materials_Egap ON materials(Egap);
        CREATE INDEX IF NOT EXISTS idx_materials_spacegroup ON materials(spacegroup_relax);
        CREATE INDEX IF NOT EXISTS idx_log_status ON extraction_log(status);
    """)

    # Lightweight migration for databases created by an older version.
    cur.execute("PRAGMA table_info(materials)")
    material_columns = {row[1] for row in cur.fetchall()}
    for column in SCALAR_FIELDS:
        if column != "auid" and column not in material_columns:
            cur.execute(f"ALTER TABLE materials ADD COLUMN {column} TEXT")
    for column in DB_FLAG_FIELDS:
        if column not in material_columns:
            cur.execute(f"ALTER TABLE materials ADD COLUMN {column} INTEGER DEFAULT 0")
    if "download_profile" not in material_columns:
        cur.execute("ALTER TABLE materials ADD COLUMN download_profile TEXT")

    cur.execute("PRAGMA table_info(downloaded_files)")
    file_columns = {row[1] for row in cur.fetchall()}
    if "category" not in file_columns:
        cur.execute("ALTER TABLE downloaded_files ADD COLUMN category TEXT")

    conn.commit()
    conn.close()


def write_material_to_db(db_path: str, item: dict[str, Any], report: AflowExtractionReport, downloaded_files: list[Path]) -> None:
    auid = item.get("auid")
    if not auid:
        raise ValueError("aflowlib.json does not contain auid")

    row = {field: json_or_none(item.get(field)) for field in SCALAR_FIELDS}
    row["has_metadata"] = int(report.metadata)
    for flag in DB_FLAG_FIELDS:
        row[flag] = int(report.category_flags.get(flag, False))
    row["download_profile"] = report.profile
    row["downloaded_files_count"] = len(downloaded_files)

    columns = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    updates = ", ".join([f"{key} = excluded.{key}" for key in row if key != "auid"])

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO materials ({columns})
        VALUES ({placeholders})
        ON CONFLICT(auid) DO UPDATE SET {updates}
        """,
        list(row.values()),
    )
    cur.execute(
        """
        INSERT INTO material_json (auid, aflowlib_json)
        VALUES (?, ?)
        ON CONFLICT(auid) DO UPDATE SET aflowlib_json = excluded.aflowlib_json
        """,
        (auid, json.dumps(item, ensure_ascii=False, default=str)),
    )

    for path in downloaded_files:
        category = infer_category_from_local_path(path)
        cur.execute(
            """
            INSERT INTO downloaded_files (auid, filename, local_path, category, size_bytes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(auid, filename) DO UPDATE SET
                local_path = excluded.local_path,
                category = excluded.category,
                size_bytes = excluded.size_bytes,
                downloaded_at = datetime('now')
            """,
            (auid, path.name, str(path), category, path.stat().st_size if path.exists() else None),
        )

    conn.commit()
    conn.close()


def infer_category_from_local_path(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    for category in ["metadata", "structures", "electronic_structure", "figure", "elasticity", "thermal", "magnetism", "bader", "symmetry", "calculation", "raw"]:
        if category in parts:
            return category
    return "unknown"


def write_extraction_log(
    db_path: str,
    status: str,
    auid: str | None = None,
    aurl: str | None = None,
    error_msg: str | None = None,
    duration_ms: int | None = None,
    batch_id: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO extraction_log
            (batch_id, auid, aurl, status, error_msg, completed_at, duration_ms)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (batch_id, auid, aurl, status, error_msg, duration_ms),
    )
    conn.commit()
    conn.close()


def load_status_json(status_path: str) -> dict[str, Any]:
    path = Path(status_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def update_status_json(status_path: str, item: dict[str, Any], report: AflowExtractionReport, status: str, elapsed_ms: int) -> None:
    all_status = load_status_json(status_path)
    auid = item.get("auid", report.auid or "unknown")
    all_status[auid] = {
        "auid": auid,
        "aurl": item.get("aurl"),
        "compound": item.get("compound"),
        "species": item.get("species"),
        "catalog": item.get("catalog"),
        "Egap": item.get("Egap"),
        "Egap_type": item.get("Egap_type"),
        "spacegroup_relax": item.get("spacegroup_relax"),
        "Pearson_symbol_relax": item.get("Pearson_symbol_relax"),
        "energy_atom": item.get("energy_atom"),
        "enthalpy_formation_atom": item.get("enthalpy_formation_atom"),
        "download_profile": report.profile,
        **{flag: bool(report.category_flags.get(flag, False)) for flag in DB_FLAG_FIELDS},
        "downloaded_files": report.files_downloaded,
        "errors": report.errors,
        "status": status,
        "duration_ms": elapsed_ms,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_json_atomic(Path(status_path), all_status)
    report.status_json = True


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def save_metadata_files(item: dict[str, Any], dirs: dict[str, Path], query_hit: dict[str, Any] | None = None) -> list[Path]:
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


def download_profile_files(
    item: dict[str, Any],
    dirs: dict[str, Path],
    profile: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_patterns: list[str] | None = None,
    errors: list[str] | None = None,
) -> list[Path]:
    """Download files allowed by an AFLOW download profile.

    Args:
        item (dict[str, Any]): Raw AFLOWLIB metadata document.
        dirs (dict[str, Path]): Local category directories.
        profile (str): Download profile name.
        timeout (int): HTTP request timeout in seconds.
        extra_patterns (list[str] | None): Additional filename patterns.
        errors (list[str] | None): Mutable list receiving download errors.

    Returns:
        list[Path]: Successfully downloaded local files.
    """
    aurl = item.get("aurl")
    files = item.get("files") or []
    if not aurl or not isinstance(files, list):
        return []

    directory_url = material_directory_url_from_aurl(aurl)
    saved: list[Path] = []

    for filename in files:
        if not isinstance(filename, str):
            continue
        if filename in NON_DATA_FILES:
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
            with open(local_path, "wb") as f:
                f.write(data)
            print(f"    [FILE] {filename} -> {local_path} ({file_size_str(local_path)})")
            saved.append(local_path)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            message = f"{filename}: {exc}"
            print(f"    [WARN] Failed to download {message}")
            if errors is not None:
                errors.append(message)

    return saved


def extract_single(
    identifier: str = DEFAULT_AURL,
    db_path: str = DEFAULT_DB_PATH,
    data_dir: str = DEFAULT_DATA_DIR,
    status_path: str = DEFAULT_STATUS_JSON,
    profile: str = DEFAULT_PROFILE,
    file_patterns: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    dry_run: bool = False,
    batch_id: str | None = None,
    query_hit: dict[str, Any] | None = None,
) -> AflowExtractionReport:
    """Extract one AFLOWLIB entry and persist raw and normalized data.

    Args:
        identifier (str): AFLOW AURL, path, or material directory URL.
        db_path (str): SQLite database path.
        data_dir (str): Root directory for downloaded files.
        status_path (str): JSON status file path.
        profile (str): Download profile name.
        file_patterns (list[str] | None): Additional filename patterns.
        timeout (int): HTTP request timeout in seconds.
        sleep_seconds (float): Delay before file downloads.
        dry_run (bool): Fetch metadata without downloading files.
        batch_id (str | None): Optional batch identifier.
        query_hit (dict[str, Any] | None): Optional AFLUX query result.

    Returns:
        AflowExtractionReport: Extraction status and downloaded file summary.
    """
    report = AflowExtractionReport(profile=profile)
    start_time = time.time()

    print(f"\n{'=' * 60}")
    print("  Extracting AFLOW entry")
    print(f"  Identifier: {identifier}")
    print(f"  Profile: {profile}")
    print(f"{'=' * 60}")

    init_database(db_path)
    from .config import AflowConfig
    from .storage import AflowStorage
    storage = AflowStorage(AflowConfig(data_root=Path(data_dir), request_timeout=timeout, sleep_seconds=sleep_seconds))
    dirs = storage.dirs

    try:
        item = fetch_aflowlib_json(identifier, timeout=timeout)
        report.metadata = True
        report.auid = item.get("auid")
        report.aurl = item.get("aurl")
        report.compound = item.get("compound")
        print(f"  Compound: {report.compound}")
        print(f"  AUID: {report.auid}")
        print(f"  AURL: {report.aurl}")
        print(f"  Material folder: {material_slug(item)}")

        if dry_run:
            print("  [DRY] Metadata fetched, no files/database writes requested.")
            report.print_report()
            return report

        saved_metadata = storage.save_metadata(item, query_hit=query_hit)
        for path in saved_metadata:
            print(f"  [JSON] {path} ({file_size_str(path)})")

        category_json_flags, category_json_paths = write_category_jsons(item, dirs)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        downloaded = storage.download_files(item, profile, timeout, file_patterns, report.errors)

        downloaded_for_db = saved_metadata + category_json_paths + downloaded
        mapping_item = dict(item)
        mapping_item["_requested_id"] = item.get("auid")
        normalized = normalize_aflow(mapping_item, downloaded_for_db)
        normalized_dir = material_category_dir(dirs, "normalized", item)
        normalized_path = normalized_dir / "record.json"
        normalized["raw_path"] = str(saved_metadata[0]) if saved_metadata else None
        normalized["normalized_path"] = str(normalized_path)
        normalized["source_documents"] = {"files": [str(path) for path in downloaded_for_db]}
        normalized["download_status"] = "partial" if report.errors else "success"
        save_json_atomic(normalized_path, normalized)
        report.files_downloaded = [str(path) for path in downloaded_for_db]
        report.category_flags = category_flags_from_downloads(downloaded_for_db)
        report.category_flags.update(category_json_flags)
        report.category_flags["has_metadata"] = True

        write_material_to_db(db_path, item, report, downloaded_for_db)
        report.database = True

        elapsed_ms = int((time.time() - start_time) * 1000)
        status = "success" if not report.errors else "partial"
        update_status_json(status_path, item, report, status, elapsed_ms)
        write_extraction_log(
            db_path=db_path,
            status=status,
            auid=report.auid,
            aurl=report.aurl,
            error_msg="; ".join(report.errors) if report.errors else None,
            duration_ms=elapsed_ms,
            batch_id=batch_id,
        )

    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        report.errors.append(str(exc))
        write_extraction_log(
            db_path=db_path,
            status="error",
            auid=report.auid,
            aurl=report.aurl,
            error_msg=str(exc),
            duration_ms=elapsed_ms,
            batch_id=batch_id,
        )

    report.print_report()
    print(f"  Database: {os.path.abspath(db_path)}")
    print(f"  Data directory: {os.path.abspath(data_dir)}")
    print(f"  Status JSON: {os.path.abspath(status_path)}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract one AFLOW material entry via aflowlib.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("identifier", nargs="?", default=DEFAULT_AURL)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--status-path", default=DEFAULT_STATUS_JSON)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--profile",
        choices=["core", "plots", "electronic", "symmetry", "bader", "vasp_raw", "all"],
        default=DEFAULT_PROFILE,
        help="Download profile. Default 'plots' stores structures plus existing PNG plots.",
    )
    parser.add_argument(
        "--include-electronic",
        action="store_true",
        help="Shortcut for --profile electronic.",
    )
    parser.add_argument(
        "--include-vasp",
        action="store_true",
        help="Shortcut for --profile vasp_raw; may download large files.",
    )
    parser.add_argument(
        "--extra-patterns",
        default=None,
        help="Comma-separated additional filename glob patterns to download.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    selected_profile = cli_args.profile
    if cli_args.include_vasp:
        selected_profile = "vasp_raw"
    elif cli_args.include_electronic:
        selected_profile = "electronic"

    extras = [p.strip() for p in cli_args.extra_patterns.split(",") if p.strip()] if cli_args.extra_patterns else None

    extract_single(
        identifier=cli_args.identifier,
        db_path=cli_args.db_path,
        data_dir=cli_args.data_dir,
        status_path=cli_args.status_path,
        profile=selected_profile,
        file_patterns=extras,
        timeout=cli_args.timeout,
        sleep_seconds=cli_args.sleep,
        dry_run=cli_args.dry_run,
    )



















