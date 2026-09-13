"""Materials Project raw download: configuration, REST client, and file storage.

This module never touches the standard schema. It retrieves upstream documents
and files as completely as the Materials Project API allows and writes them
under ``data/dft/mp/raw``:

- ``summary.json`` plus every per-material REST route (all fields).
- ``files/`` with full pymatgen objects (structure, band structure, DOS,
  phonon band structure/DOS, Wulff shape, entries, references, charge density).
- ``nomad/`` with the raw VASP archives that MP mirrors through NoMaD.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import zipfile
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from monty.json import MontyEncoder, jsanitize
from pymatgen.io.cif import CifWriter

try:  # emmet-core moved BSPathType in 0.87.
    from emmet.core.band_theory import BSPathType
except ImportError:  # pragma: no cover - older emmet-core
    from emmet.core.electronic_structure import BSPathType

BASE_URL = "https://api.materialsproject.org"
PROPERTY_DOWNLOAD_VERSION = 4
CATEGORIES: tuple[str, ...] = ("properties", "files", "charge_density", "raw_vasp", "bandstructure_projections")
DEFAULT_BS_PATH_TYPES: tuple[str, ...] = ("setyawan_curtarolo", "hinuma", "latimer_munro")

# Every Materials Project route that can be filtered down to one material
# (directly, or through its tasks/formula/phonon/film identifiers).
PROPERTY_ENDPOINTS: tuple[dict[str, Any], ...] = (
    {"name": "absorption", "path": "absorption"},
    {"name": "alloys", "path": "alloys"},
    {"name": "bonds", "path": "bonds"},
    {"name": "chemenv", "path": "chemenv"},
    {"name": "core", "path": "core"},
    {"name": "dielectric", "path": "dielectric"},
    {"name": "elasticity", "path": "elasticity"},
    {"name": "electronic_structure", "path": "electronic_structure"},
    {"name": "eos", "path": "eos", "query_field": "task_ids"},
    {"name": "grain_boundaries", "path": "grain_boundaries"},
    {"name": "insertion_electrodes", "path": "insertion_electrodes", "query_field": "formula", "context_field": "formula_pretty"},
    {"name": "magnetism", "path": "magnetism"},
    {"name": "oxidation_states", "path": "oxidation_states"},
    {"name": "phonon", "path": "phonon", "query_field": "identifiers", "context_field": "phonon_IDs"},
    {"name": "piezoelectric", "path": "piezoelectric"},
    {"name": "provenance", "path": "provenance"},
    {"name": "robocrys", "path": "robocrys"},
    {"name": "similarity", "path": "similarity"},
    {"name": "substrates", "path": "substrates", "query_field": "film_id"},
    {"name": "surface_properties", "path": "surface_properties"},
    {"name": "synthesis", "path": "synthesis", "query_field": "target_formula", "context_field": "formula_pretty", "supports_all_fields": False},
    {"name": "tasks", "path": "tasks", "query_field": "task_ids"},
    {"name": "tasks_entries", "path": "tasks/entries", "query_field": "task_ids", "supports_all_fields": False},
    {"name": "thermo", "path": "thermo"},
    {"name": "xas", "path": "xas", "query_field": "task_ids"},
)


@dataclass(frozen=True)
class MPConfig:
    """Runtime settings for one Materials Project download task."""

    api_key: str
    data_root: Path = Path("data/dft/mp")
    request_timeout: float = 30.0
    nomad_timeout: float = 600.0
    retry_count: int = 3
    retry_delay: float = 10.0

    @classmethod
    def from_environment(cls, data_root: str | Path = "data/dft/mp") -> "MPConfig":
        """Build configuration from environment variables or a local ``.env`` file."""
        load_dotenv()
        api_key = os.getenv("MP_API_KEY")
        if not api_key or api_key.startswith("replace_with_"):
            raise RuntimeError("MP_API_KEY is required; copy .env.example to .env and set your API key.")
        return cls(api_key=api_key, data_root=Path(os.getenv("MP_DATA_ROOT", str(data_root))))

    @property
    def raw_dir(self) -> Path:
        """Return the directory for untouched API responses."""
        return self.data_root / "raw"

    @property
    def database_path(self) -> Path:
        """Return the shared SQLite index path."""
        return self.data_root / "index.sqlite"


@dataclass
class DownloadResult:
    """Raw documents and local paths produced by one download."""

    requested_id: str
    source_id: str
    raw_path: Path
    summary: dict[str, Any]
    property_paths: dict[str, str] = field(default_factory=dict)
    properties: dict[str, int] = field(default_factory=dict)
    property_errors: dict[str, str] = field(default_factory=dict)
    documents: dict[str, list[Any]] = field(default_factory=dict)
    file_paths: dict[str, str] = field(default_factory=dict)
    file_errors: dict[str, str] = field(default_factory=dict)
    raw_archive_paths: list[str] = field(default_factory=list)
    raw_errors: list[str] = field(default_factory=list)
    categories: set[str] = field(default_factory=set)

    @property
    def status(self) -> str:
        """Return ``partial`` when any route, file, or raw archive failed."""
        return "partial" if (self.property_errors or self.file_errors or self.raw_errors) else "success"


def normalize_mp_id(mp_id: int | str) -> str:
    """Normalize an integer or string to the ``mp-XXXXX`` format."""
    value = str(mp_id).strip()
    if value.lower().startswith("mp-"):
        return f"mp-{value[3:]}"
    if value.isdigit():
        return f"mp-{value}"
    return value


class MPClient:
    """Access Materials Project summary and detail endpoints over REST."""

    def __init__(self, config: MPConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": config.api_key})

    def fetch_ids(self, *, chemsys: str | None = None, elements: list[str] | None = None,
                  is_stable: bool | None = None, max_materials: int | None = None,
                  page_size: int = 1000) -> list[str]:
        """Fetch material IDs with optional filters."""
        params: dict[str, Any] = {"_fields": "material_id", "_limit": page_size, "_skip": 0}
        if chemsys:
            params["chemsys"] = chemsys
        if elements:
            params["elements"] = ",".join(elements)
        if is_stable is not None:
            params["is_stable"] = str(is_stable).lower()
        material_ids: list[str] = []
        while max_materials is None or len(material_ids) < max_materials:
            response = self.session.get(f"{BASE_URL}/materials/summary/", params=params,
                                        timeout=self.config.request_timeout)
            response.raise_for_status()
            docs = response.json().get("data", [])
            if not docs:
                break
            material_ids.extend(normalize_mp_id(doc["material_id"]) for doc in docs if doc.get("material_id"))
            if len(docs) < page_size:
                break
            params["_skip"] += page_size
        return material_ids[:max_materials] if max_materials else material_ids

    def fetch_summary(self, mp_id: int | str) -> dict[str, Any] | None:
        """Fetch one material summary document with every field."""
        response = self.session.get(f"{BASE_URL}/materials/summary/",
                                    params={"material_ids": normalize_mp_id(mp_id), "_all_fields": "true"},
                                    timeout=self.config.request_timeout)
        response.raise_for_status()
        docs = response.json().get("data", [])
        return docs[0] if docs else None

    def fetch_property(self, route: dict[str, Any], mp_id: int | str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch one source-specific property endpoint with strict pagination."""
        query_field = route.get("query_field", "material_ids")
        query_value: Any = normalize_mp_id(mp_id)
        if route.get("context_field"):
            query_value = (context or {}).get(route["context_field"])
        if query_field == "task_ids":
            query_value = (context or {}).get("task_ids", [])
        if query_field == "identifiers":
            phonon_ids = (context or {}).get("phonon_IDs") or {}
            query_value = [identifier for values in phonon_ids.values() for identifier in (values or [])]
        if isinstance(query_value, (list, tuple)):
            query_value = ",".join(dict.fromkeys(str(value) for value in query_value if value is not None and str(value).strip()))
        if query_value is None or not str(query_value).strip():
            return []
        params: dict[str, Any] = {query_field: query_value, "_limit": 100, "_skip": 0}
        if route.get("supports_all_fields", True):
            params["_all_fields"] = "true"
        documents: list[dict[str, Any]] = []
        expected_total: int | None = None
        seen_pages: set[str] = set()
        seen_tokens: set[str] = set()
        while True:
            response = self.session.get(f"{BASE_URL}/materials/{route['path']}/", params=dict(params),
                                        timeout=self.config.request_timeout)
            response.raise_for_status()
            payload = response.json()
            page = payload.get("data")
            if not isinstance(page, list) or any(not isinstance(doc, dict) or not doc for doc in page):
                raise ValueError(f"{route['name']}: malformed or empty property documents")
            meta = payload.get("meta") or {}
            total = meta.get("total_doc")
            if total is not None:
                if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                    raise ValueError(f"{route['name']}: invalid total_doc")
                if expected_total is not None and total != expected_total:
                    raise ValueError(f"{route['name']}: total_doc changed during pagination")
                expected_total = total
            if not page:
                if expected_total is not None and len(documents) != expected_total:
                    raise ValueError(f"{route['name']}: incomplete download ({len(documents)}/{expected_total})")
                return documents
            content = [{k: v for k, v in doc.items() if k not in {"meta", "meta_pagination_token"}} for doc in page]
            fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            if fingerprint in seen_pages:
                raise ValueError(f"{route['name']}: repeated page; pagination made no progress")
            seen_pages.add(fingerprint)
            documents.extend(page)
            if expected_total is not None:
                if len(documents) > expected_total:
                    raise ValueError(f"{route['name']}: downloaded more documents than total_doc")
                if len(documents) == expected_total:
                    return documents
            elif len(page) < params["_limit"]:
                return documents
            token = meta.get("pagination_token")
            if token:
                if token in seen_tokens:
                    raise ValueError(f"{route['name']}: repeated pagination token")
                seen_tokens.add(token)
                params.pop("_skip", None)
                params["_pagination_token"] = token
            else:
                if "_pagination_token" in params:
                    raise ValueError(f"{route['name']}: pagination token missing before completion")
                params["_skip"] = len(documents)


class MPArtifactsClient:
    """Download full pymatgen objects and NoMaD raw archives through ``mp-api``."""

    def __init__(self, config: MPConfig):
        from mp_api.client import MPRester

        self.config = config
        self.rester = MPRester(api_key=config.api_key)

    def fetch_files(
        self,
        material_id: str,
        files_dir: str | Path,
        *,
        summary: dict[str, Any] | None = None,
        include_charge_density: bool = True,
        bs_path_types: tuple[str, ...] = DEFAULT_BS_PATH_TYPES,
        include_bs_projections: bool = True,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Download every full object MP exposes for one material.

        The ``summary`` document is used to skip optional objects the material
        does not have, because ``mp-api`` raises instead of returning ``None``
        for some absent resources (for example a missing phonon calculation).
        """
        directory = Path(files_dir)
        directory.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        errors: dict[str, str] = {}

        def load(name: str, factory):
            try:
                return factory()
            except Exception as error:  # Individual objects may be missing.
                errors[name] = str(error)
                return None

        bandstructure_available = summary is None or bool(summary.get("bandstructure"))
        dos_available = summary is None or bool(summary.get("dos"))
        phonon_ids = (summary or {}).get("phonon_IDs") or {}
        phonon_available = summary is None or any(phonon_ids.values())
        surface_available = summary is None or any(
            summary.get(key) is not None
            for key in ("weighted_surface_energy", "weighted_surface_energy_EV_PER_ANG2", "surface_anisotropy", "shape_factor")
        )

        structure = load("structure", lambda: self.rester.get_structure_by_material_id(material_id))
        if structure is not None:
            try:
                cif_path = directory / "structure.cif"
                CifWriter(structure).write_file(cif_path)
                paths["structure_cif"] = str(cif_path)
                json_path = directory / "structure.json"
                _write_monty_json(json_path, _as_jsonable(structure))
                paths["structure_json"] = str(json_path)
            except Exception as error:
                errors["structure"] = str(error)

        for path_type in bs_path_types if bandstructure_available else ():
            name = f"bandstructure_{path_type}"
            bandstructure = load(name, lambda pt=path_type: self.rester.get_bandstructure_by_material_id(
                material_id, path_type=BSPathType(pt)))
            if bandstructure is not None:
                try:
                    path = directory / f"{name}.json"
                    _write_monty_json(path, _as_jsonable(bandstructure))
                    paths[name] = str(path)
                except Exception as error:
                    errors[name] = str(error)

        if include_bs_projections:
            for path_type in bs_path_types if bandstructure_available else ():
                name = f"bandstructure_{path_type}_projections"
                projections = load(name, lambda pt=path_type: self.rester.get_bandstructure_by_material_id(
                    material_id, path_type=BSPathType(pt), load_projections=True))
                if projections is not None:
                    try:
                        path = directory / f"{name}.json"
                        _write_monty_json(path, _as_jsonable(projections))
                        paths[name] = str(path)
                    except Exception as error:
                        errors[name] = str(error)

        dos = load("dos", lambda: self.rester.get_dos_by_material_id(material_id)) if dos_available else None
        if dos is not None:
            try:
                path = directory / "dos.json"
                _write_monty_json(path, _as_jsonable(dos))
                paths["dos"] = str(path)
            except Exception as error:
                errors["dos"] = str(error)

        for name, factory in (
            ("phonon_bandstructure", lambda: self.rester.get_phonon_bandstructure_by_material_id(material_id)),
            ("phonon_dos", lambda: self.rester.get_phonon_dos_by_material_id(material_id)),
        ) if phonon_available else ():
            obj = load(name, factory)
            if obj is not None:
                try:
                    path = directory / f"{name}.json"
                    _write_monty_json(path, _as_jsonable(obj))
                    paths[name] = str(path)
                except Exception as error:
                    errors[name] = str(error)

        wulff = load("wulff_shape", lambda: self.rester.get_wulff_shape(material_id)) if surface_available else None
        if wulff is not None:
            try:
                payload = {
                    "volume": wulff.volume,
                    "area_fraction_dict": {str(key): value for key, value in wulff.area_fraction_dict.items()},
                    "miller_area_dict": {str(key): value for key, value in wulff.miller_area_dict.items()},
                    "miller_energy_dict": {str(key): value for key, value in wulff.miller_energy_dict.items()},
                }
                path = directory / "wulff_shape.json"
                _write_json(path, payload)
                paths["wulff_shape"] = str(path)
            except Exception as error:
                errors["wulff_shape"] = str(error)

        entries = load("entries", lambda: self.rester.get_entries([material_id]))
        if entries:
            try:
                path = directory / "entries.json"
                _write_monty_json(path, _as_jsonable(entries))
                paths["entries"] = str(path)
            except Exception as error:
                errors["entries"] = str(error)

        references = load("references", lambda: self.rester.get_material_id_references(material_id))
        if references:
            try:
                path = directory / "references.json"
                _write_json(path, references)
                paths["references"] = str(path)
            except Exception as error:
                errors["references"] = str(error)

        if include_charge_density:
            charge = load("charge_density", lambda: self.rester.get_charge_density_from_material_id(material_id))
            if charge is not None:
                try:
                    charge_dir = directory / "charge_density"
                    charge_dir.mkdir(parents=True, exist_ok=True)
                    charge_path = charge_dir / "CHGCAR"
                    charge.write_file(charge_path)
                    paths["charge_density"] = str(charge_path)
                except Exception as error:
                    errors["charge_density"] = str(error)

        return paths, errors

    def fetch_nomad(
        self,
        material_id: str,
        nomad_dir: str | Path,
        *,
        timeout: float | None = None,
    ) -> tuple[list[str], list[str]]:
        """Download and extract the raw VASP archives MP mirrors through NoMaD."""
        directory = Path(nomad_dir)
        directory.mkdir(parents=True, exist_ok=True)
        archives: list[str] = []
        errors: list[str] = []
        try:
            meta, urls = self.rester.get_download_info([material_id])
        except Exception as error:
            errors.append(f"get_download_info: {error}")
            return archives, errors
        _write_json(directory / "download_info.json", meta)
        for index, url in enumerate(urls):
            try:
                archive_dir = directory / f"archive_{index:03d}"
                archive_dir.mkdir(parents=True, exist_ok=True)
                zip_path = directory / f"archive_{index:03d}.zip"
                with requests.get(url, timeout=timeout or self.config.nomad_timeout, stream=True) as response:
                    response.raise_for_status()
                    with zip_path.open("wb") as stream:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                stream.write(chunk)
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(archive_dir)
                archives.append(str(archive_dir))
            except Exception as error:
                errors.append(f"archive {index}: {error}")
        return archives, errors


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    _atomic_write(path, text)


def _atomic_write(path: Path, text: str) -> None:
    """Write text through a temporary file so interrupted runs never truncate."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _as_jsonable(obj: Any) -> Any:
    """Convert pymatgen/pydantic objects into JSON-safe structures."""
    if isinstance(obj, (list, tuple)):
        return [_as_jsonable(item) for item in obj]
    payload: Any
    if hasattr(obj, "as_dict"):
        try:
            payload = obj.as_dict()
        except Exception:  # Some entries carry non-string keys inside ``data``.
            payload = getattr(obj, "__dict__", None) or str(obj)
    elif hasattr(obj, "model_dump"):
        payload = obj.model_dump()
    else:
        payload = obj
    return _stringify_keys(jsanitize(payload, strict=True, allow_bson=False))


def _stringify_keys(obj: Any) -> Any:
    """Recursively coerce mapping keys to strings for JSON output."""
    if isinstance(obj, dict):
        return {str(key): _stringify_keys(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_stringify_keys(item) for item in obj]
    return obj


def _write_monty_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(payload, cls=MontyEncoder, ensure_ascii=False, indent=2))


def requested_categories(
    *,
    include_properties: bool = True,
    include_files: bool = True,
    include_charge_density: bool = True,
    include_raw_vasp: bool = True,
    include_bs_projections: bool = True,
) -> set[str]:
    """Return the download categories selected by the caller."""
    categories: set[str] = set()
    if include_properties:
        categories.add("properties")
    if include_files:
        categories.add("files")
        if include_charge_density:
            categories.add("charge_density")
        if include_bs_projections:
            categories.add("bandstructure_projections")
    if include_raw_vasp:
        categories.add("raw_vasp")
    return categories


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
    requested_id: int | str,
    *,
    categories: set[str] | None = None,
    bs_path_types: tuple[str, ...] = DEFAULT_BS_PATH_TYPES,
    source: str = "mp",
    schema_version: str = "3.0",
) -> bool:
    """Return whether the requested material is already fully downloaded.

    Matching accepts either the stored ``source_id`` (the canonical AlphaID) or
    the ``requested_id`` so legacy numeric IDs resume correctly.
    """
    row = _load_record(db_path, source, normalize_mp_id(requested_id))
    if not row:
        return False
    if row.get("schema_version") != schema_version or row.get("download_status") != "success":
        return False
    documents = row.get("source_documents")
    if isinstance(documents, str):
        try:
            documents = json.loads(documents)
        except ValueError:
            documents = {}
    documents = documents or {}
    if documents.get("property_download_version") != PROPERTY_DOWNLOAD_VERSION:
        return False
    required = categories if categories is not None else set(CATEGORIES)
    if not required <= set(documents.get("download_categories") or []):
        return False
    if ({"files", "bandstructure_projections"} & required) and tuple(documents.get("bs_path_types") or ()) != tuple(bs_path_types):
        return False
    raw_path = row.get("raw_path")
    if not raw_path or not Path(raw_path).exists():
        return False
    base = Path(raw_path).parent
    sentinels: dict[str, Path] = {
        "properties": base / "properties",
        "files": base / "files",
        "charge_density": base / "files" / "charge_density" / "CHGCAR",
        "raw_vasp": base / "nomad",
    }
    for category in required:
        if category == "bandstructure_projections":
            if not any((base / "files").glob("*_projections.json")):
                return False
            continue
        target = sentinels.get(category)
        if target is not None and not target.exists():
            return False
    return True


def download_one(
    client: MPClient,
    config: MPConfig,
    mp_id: int | str,
    include_properties: bool = True,
    *,
    include_files: bool = True,
    include_charge_density: bool = True,
    include_raw_vasp: bool = True,
    bs_path_types: tuple[str, ...] = DEFAULT_BS_PATH_TYPES,
    include_bs_projections: bool = True,
    artifacts_client: MPArtifactsClient | None = None,
) -> DownloadResult:
    """Download one MP material as completely as the API allows.

    Args:
        client (MPClient): Configured MP REST client.
        config (MPConfig): MP download configuration.
        mp_id (int | str): Material identifier.
        include_properties (bool): Fetch every per-material REST route.
        include_files (bool): Fetch full pymatgen objects.
        include_charge_density (bool): Include the CHGCAR artifact (large).
        include_raw_vasp (bool): Fetch the NoMaD raw VASP archives (large).
        bs_path_types (tuple[str, ...]): Band-structure path conventions.
        artifacts_client (MPArtifactsClient | None): Reusable artifacts client.

    Returns:
        DownloadResult: Raw documents, file paths, and per-item errors.
    """
    material_id = normalize_mp_id(mp_id)
    summary = client.fetch_summary(material_id)
    if summary is None:
        raise LookupError(f"Materials Project record not found: {material_id}")
    raw_dir = config.raw_dir / material_id
    raw_path = raw_dir / "summary.json"
    _write_json(raw_path, summary)
    result = DownloadResult(requested_id=material_id, source_id=material_id, raw_path=raw_path, summary=summary)
    result.categories |= requested_categories(
        include_properties=include_properties,
        include_files=include_files,
        include_charge_density=include_charge_density,
        include_raw_vasp=include_raw_vasp,
        include_bs_projections=include_bs_projections,
    )

    if include_properties:
        for route in PROPERTY_ENDPOINTS:
            endpoint = route["name"]
            try:
                documents = client.fetch_property(route, material_id, summary)
                result.properties[endpoint] = len(documents)
                result.documents[endpoint] = documents
                if documents:
                    property_path = raw_dir / "properties" / f"{endpoint}.json"
                    _write_json(property_path, documents)
                    result.property_paths[endpoint] = str(property_path)
            except Exception as error:  # Keep going; individual routes may fail independently.
                result.properties[endpoint] = 0
                result.property_errors[endpoint] = str(error)

    if include_files or include_raw_vasp:
        artifacts = artifacts_client or MPArtifactsClient(config)
        if include_files:
            file_paths, file_errors = artifacts.fetch_files(
                material_id,
                raw_dir / "files",
                summary=summary,
                include_charge_density=include_charge_density,
                bs_path_types=bs_path_types,
                include_bs_projections=include_bs_projections,
            )
            result.file_paths.update(file_paths)
            result.file_errors.update(file_errors)
        if include_raw_vasp:
            archives, raw_errors = artifacts.fetch_nomad(material_id, raw_dir / "nomad", timeout=config.nomad_timeout)
            result.raw_archive_paths.extend(archives)
            result.raw_errors.extend(raw_errors)

    return result


__all__ = [
    "CATEGORIES",
    "DEFAULT_BS_PATH_TYPES",
    "DownloadResult",
    "MPArtifactsClient",
    "MPClient",
    "MPConfig",
    "PROPERTY_DOWNLOAD_VERSION",
    "PROPERTY_ENDPOINTS",
    "completed",
    "download_one",
    "normalize_mp_id",
    "requested_categories",
]
