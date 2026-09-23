"""AMCSD normalization: raw CIF/AMC text to DFT standard record.

AMCSD records are experimental single-crystal structures. The minimal CIF is the
authoritative source for the cell, symmetry and atomic coordinates, while the
native AMC text supplies the richest metadata (mineral name, authors, journal,
locality) and experimental conditions such as temperature or pressure.

The standard DFT contract is reused unchanged. Fields that describe a
calculation (functional, energies, band gap, magnetism, elastic and phonon
properties) stay ``null``, ``calculation_method`` is ``experimental``,
``theoretical`` is ``false``, and the reserved ``temperature``/``pressure``
columns are never populated: experimental conditions are kept in
``source_extra`` together with the citation and provenance text.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"

RECORD_URL_TEMPLATE = "https://www.rruff.net/odr/amcsd/{amcsd_id}"
AMCSD_CITATION = (
    "Downs, R.T. and Hall-Wallace, M. (2003) The American Mineralogist "
    "Crystal Structure Database. American Mineralogist 88, 247-250"
)
API_VERSION = "amcsd-bulk-2026.06.29"

CELL_LINE = re.compile(
    r"^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+"
    r"(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(\S+)\s*$"
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


def get_by_path(document: dict[str, Any], field_path: str | None) -> Any:
    """Read a dotted or indexed path such as ``structure.lattice.a``."""
    if not field_path:
        return None
    value: Any = document
    for part in field_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            return None
        if value is None:
            return None
    return value


def _requested_id(_: Any, document: dict[str, Any]) -> str | None:
    return document.get("_requested_id")


def _to_int(value: Any, _: dict[str, Any]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or float(value) != int(value):
        raise ValueError("expected an integral number")
    return int(value)


def _to_bool(value: Any, _: dict[str, Any]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "y"}:
            return True
        if token in {"false", "0", "no", "n"}:
            return False
    elif isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ValueError("expected an explicit boolean value")


def _normalize_elements(value: Any, _: dict[str, Any]) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("elements must be a list of element symbols")
    return sorted(set(value))


def _count_items(value: Any, _: dict[str, Any]) -> int | None:
    return len(_normalize_elements(value, _)) if value is not None else None


def _normalize_formula(value: Any, _: dict[str, Any]) -> str | None:
    return str(value).strip() if value is not None else None


def _normalize_chemical_system(value: Any, _: dict[str, Any]) -> str | None:
    if not value:
        return None
    return "-".join(sorted(str(value).replace("_", "-").split("-")))


def _lowercase(value: Any, _: dict[str, Any]) -> str | None:
    return None if value is None else str(value).strip().lower()


def _now(_: Any, __: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


TRANSFORMS = {
    "requested_id": _requested_id,
    "to_int": _to_int,
    "to_bool": _to_bool,
    "normalize_elements": _normalize_elements,
    "count_items": _count_items,
    "normalize_formula": _normalize_formula,
    "normalize_chemical_system": _normalize_chemical_system,
    "lowercase": _lowercase,
    "now": _now,
}


# ---------------------------------------------------------------------------
# Structure helpers
# ---------------------------------------------------------------------------

def _safe_name(value: Any) -> str:
    """Return a filesystem-safe name for a material identifier."""
    text = str(value).replace(":", "_").replace("/", "_").replace("\\", "_")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def _write_cif(structure: Any, target: Path) -> bool:
    """Write one pymatgen structure to a CIF file, creating parents as needed."""
    try:
        from pymatgen.io.cif import CifWriter

        target.parent.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            CifWriter(structure).write_file(target)
        return True
    except Exception:
        return False


def _first_block(data: dict[str, Any]) -> dict[str, Any]:
    """Return the first CIF data block, or an empty mapping."""
    for value in data.values():
        if isinstance(value, dict):
            return value
    return {}


def _parse_cif(text: str | None) -> tuple[Any, dict[str, Any]]:
    """Parse a minimal AMCSD CIF into ``(structure, metadata_block)``.

    Relaxed parsing (``check_occu=False``) accepts the partial occupancies and
    mixed site labels common in mineral structures. Malformed records yield
    ``structure=None`` so their metadata can still be indexed as ``partial``.
    """
    if not text:
        return None, {}
    try:
        from pymatgen.io.cif import CifParser
    except Exception:
        return None, {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            parser = CifParser.from_str(text)
            block = _first_block(parser.as_dict())
        except Exception:
            return None, {}
        structure = None
        for kwargs in (
            {"primitive": False, "check_occu": False, "on_error": "ignore"},
            {"primitive": False},
        ):
            try:
                structures = parser.parse_structures(**kwargs)
                if structures:
                    structure = structures[0]
                    break
            except Exception:
                continue
    return structure, block


def parse_amc(text: str | None) -> dict[str, Any]:
    """Best-effort parse of the AMCSD native AMC text format.

    The format has no formal grammar: a header (name, authors, journal, title),
    free metadata lines, a ``_database_code_amcsd`` marker, a cell/symmetry
    line, and an atom table. Only the metadata is read here; geometry comes from
    the CIF.
    """
    meta: dict[str, Any] = {}
    if not text:
        return meta
    lines = [line.rstrip() for line in text.splitlines()]
    nonempty = [(index, line) for index, line in enumerate(lines) if line.strip()]
    if nonempty:
        meta["mineral_name"] = nonempty[0][1].strip()
    if len(nonempty) > 1:
        meta["authors"] = nonempty[1][1].strip()
    if len(nonempty) > 2:
        meta["journal"] = nonempty[2][1].strip()

    database_index: int | None = None
    for index, line in enumerate(lines):
        if "_database_code_amcsd" in line:
            database_index = index
            code = line.split("_database_code_amcsd", 1)[1].strip()
            if code:
                meta["amc_database_code"] = code
            break

    title_start = nonempty[2][0] + 1 if len(nonempty) > 2 else 0
    title_end = database_index if database_index is not None else len(lines)
    title_parts: list[str] = []
    for index in range(title_start, title_end):
        stripped = lines[index].strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if (
            stripped.startswith("Locality:")
            or re.match(r"^[TP]\s*=", stripped)
            or CELL_LINE.match(stripped)
        ):
            break
        title_parts.append(stripped)
    if title_parts:
        meta["title"] = " ".join(title_parts)

    if database_index is not None:
        for index in range(database_index + 1, len(lines)):
            match = CELL_LINE.match(lines[index])
            if match:
                meta["amc_cell"] = {
                    "a": match.group(1), "b": match.group(2), "c": match.group(3),
                    "alpha": match.group(4), "beta": match.group(5), "gamma": match.group(6),
                    "spacegroup": match.group(7),
                }
                break

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        match = re.match(r"^T\s*=\s*(.+)$", stripped)
        if match:
            meta.setdefault("temperature", match.group(1).strip())
        match = re.match(r"^P\s*=\s*(.+)$", stripped)
        if match:
            meta.setdefault("pressure", match.group(1).strip())
        if lowered.startswith("locality:"):
            meta.setdefault("locality", stripped.split(":", 1)[1].strip())
        if lowered.startswith("temperature"):
            meta.setdefault("temperature", stripped.split(":", 1)[-1].strip())
        if lowered.startswith("pressure"):
            meta.setdefault("pressure", stripped.split(":", 1)[-1].strip())
        if "radiation" in lowered:
            meta.setdefault("radiation_source", stripped)
        if "wavelength" in lowered:
            meta.setdefault("wavelength", stripped)
    return meta


def _meta_from_cif(block: dict[str, Any]) -> dict[str, Any]:
    """Extract citation and provenance strings from a CIF data block."""
    if not block:
        return {}
    authors = block.get("_publ_author_name")
    if isinstance(authors, str):
        authors = [authors]
    meta: dict[str, Any] = {}
    if authors:
        meta["cif_authors"] = [str(item) for item in authors]
    title = block.get("_publ_section_title")
    if isinstance(title, str) and title.strip():
        meta["cif_title"] = " ".join(title.split())
    journal = block.get("_journal_name_full")
    if isinstance(journal, str) and journal.strip():
        meta["cif_journal"] = journal.strip()
    for source_key, target_key in (
        ("_journal_volume", "cif_journal_volume"),
        ("_journal_year", "cif_journal_year"),
        ("_journal_page_first", "cif_journal_page_first"),
        ("_journal_page_last", "cif_journal_page_last"),
        ("_chemical_formula_sum", "cif_chemical_formula_sum"),
        ("_cell_volume", "cif_cell_volume"),
        ("_exptl_crystal_density_diffrn", "cif_density"),
        ("_chemical_compound_source", "cif_compound_source"),
        ("_chemical_name_mineral", "cif_mineral_name"),
        ("_symmetry_space_group_name_H-M", "cif_space_group_name"),
        ("_database_code_amcsd", "cif_database_code"),
    ):
        value = block.get(source_key)
        if value is not None and str(value).strip() != "":
            meta[target_key] = value
    return meta


def _symmetry(block: dict[str, Any], structure: Any) -> tuple[int | None, str | None, str | None, str | None]:
    """Return ``(number, symbol, crystal_system, point_group)``.

    The declared CIF Hermann-Mauguin symbol is preferred because it preserves
    the experimental symmetry. Only when it is missing or unrecognized is the
    symmetry re-derived from the parsed structure with spglib.
    """
    symbol_text = block.get("_symmetry_space_group_name_H-M") if block else None
    if isinstance(symbol_text, str) and symbol_text.strip():
        try:
            from pymatgen.symmetry.groups import SpaceGroup

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                group = SpaceGroup(symbol_text)
            system = getattr(group.crystal_system, "value", None) or str(group.crystal_system)
            return (
                int(group.int_number),
                str(group.symbol),
                str(system).replace("crystal_system.", "").lower(),
                str(group.point_group),
            )
        except Exception:
            pass
    if structure is not None:
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                analyzer = SpacegroupAnalyzer(structure, symprec=0.1)
                number = int(analyzer.get_space_group_number())
                symbol = str(analyzer.get_space_group_symbol())
                system = getattr(analyzer.get_crystal_system(), "value", None) or str(analyzer.get_crystal_system())
                try:
                    point_group = str(analyzer.get_point_group_symbol())
                except Exception:
                    point_group = None
            return number, symbol, str(system).replace("crystal_system.", "").lower(), point_group
        except Exception:
            pass
    return None, None, None, None


def _composition_fields(structure: Any) -> dict[str, Any]:
    """Derive reduced formula, anonymous formula, and reduced composition."""
    if structure is None:
        return {}
    try:
        composition = structure.composition
        return {
            "formula_reduced": composition.reduced_formula,
            "formula_anonymous": composition.anonymized_formula,
            "composition_reduced": composition.reduced_composition.get_el_amt_dict(),
        }
    except Exception:
        return {}


def _lattice_fields(structure: Any) -> dict[str, Any]:
    """Derive lattice parameters and density from a pymatgen structure."""
    if structure is None:
        return {}
    lattice = structure.lattice
    fields: dict[str, Any] = {
        "lattice_a": lattice.a,
        "lattice_b": lattice.b,
        "lattice_c": lattice.c,
        "angle_alpha": lattice.alpha,
        "angle_beta": lattice.beta,
        "angle_gamma": lattice.gamma,
        "volume": lattice.volume,
    }
    try:
        density = float(structure.density)
        if density > 0:
            fields["density"] = density
    except Exception:
        pass
    try:
        if lattice.volume:
            fields["density_atomic"] = len(structure) / lattice.volume
    except Exception:
        pass
    return fields


def _materialize_cif(
    source_id: Any,
    structure: Any,
    structure_root: str | Path | None,
    cif_text: str | None = None,
) -> str | None:
    """Ensure the structure CIF artifact exists and return its path.

    The original AMCSD minimal CIF is written verbatim when available because it
    is faithful to the published record and avoids lossy re-serialization. Only
    when no source CIF text is available is the parsed structure re-written with
    pymatgen.
    """
    if not structure_root or not source_id:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if cif_text:
        try:
            target.write_text(cif_text, encoding="utf-8")
            return str(target)
        except Exception:
            pass
    if structure is None:
        return None
    return str(target) if _write_cif(structure, target) else None


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_amcsd(entry: dict[str, Any], *, requested_id: str | None = None) -> dict[str, Any]:
    """Convert one raw AMCSD entry into the shared enriched document."""
    amcsd_id = entry.get("amcsd_id")
    source_id = str(amcsd_id).zfill(7) if amcsd_id else None
    structure, block = _parse_cif(entry.get("cif"))
    amc_meta = parse_amc(entry.get("amc"))
    cif_meta = _meta_from_cif(block)

    elements = (
        sorted(str(element) for element in structure.composition.elements)
        if structure is not None else None
    )
    atom_count = len(structure) if structure is not None else None
    formula = cif_meta.get("cif_chemical_formula_sum")
    if not formula and structure is not None:
        formula = structure.composition.formula
    number, symbol, system, point_group = _symmetry(block, structure)

    authors = amc_meta.get("authors")
    if not authors and cif_meta.get("cif_authors"):
        authors = ", ".join(cif_meta["cif_authors"])
    title = amc_meta.get("title") or cif_meta.get("cif_title")
    journal = amc_meta.get("journal") or cif_meta.get("cif_journal")
    citation_parts = [
        f"{authors}." if authors else None,
        f"{title}." if title else None,
        journal if journal else None,
    ]
    dataset_citation = " ".join(part for part in citation_parts if part) or None

    enriched: dict[str, Any] = {
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": RECORD_URL_TEMPLATE.format(amcsd_id=source_id) if source_id else None,
        "amcsd_id": source_id,
        "mineral_name": amc_meta.get("mineral_name") or cif_meta.get("cif_mineral_name"),
        "formula": formula,
        "elements": elements,
        "chemical_system": "-".join(elements) if elements else None,
        "atom_count": atom_count,
        "structure": None,
        "spacegroup_number": number,
        "spacegroup_symbol": symbol,
        "crystal_system": system,
        "point_group": point_group,
        "calculation_method": "experimental",
        "theoretical": False,
        "functional": None,
        "api_version": API_VERSION,
        "amcsd_citation": AMCSD_CITATION,
        "dataset_citation": dataset_citation,
        "_cif_text": entry.get("cif"),
        "_structure_obj": structure,
    }
    enriched.update(amc_meta)
    for key, value in cif_meta.items():
        enriched.setdefault(key, value)
    enriched.update(_lattice_fields(structure))
    composition = _composition_fields(structure)
    for key, value in composition.items():
        enriched.setdefault(key, value)
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _apply_mapping(enriched: dict[str, Any], structure_root: str | Path | None,
                   property_paths: dict[str, str] | None = None) -> dict[str, Any]:
    standard = _load_yaml_cached(str(STANDARD_PATH))
    mapping = _load_yaml_cached(str(MAPPING_PATH))
    rules = mapping.get("mapping", {})
    result: dict[str, Any] = {}
    for name in standard.get("fields", {}):
        rule = rules.get(name) or {}
        if "value" in rule:
            value = rule["value"]
        else:
            value = get_by_path(enriched, rule.get("field"))
        if value is None and "default" in rule:
            value = rule["default"]
        if rule.get("transform"):
            value = TRANSFORMS[rule["transform"]](value, enriched)
        result[name] = value
    consumed = {
        str(rule.get("field")).split(".")[0]
        for rule in rules.values()
        if isinstance(rule, dict) and rule.get("field") and "." not in str(rule["field"])
    }
    excluded = set(mapping.get("source_extra_exclude", []))
    result["source_extra"] = {
        key: value
        for key, value in enriched.items()
        if key not in consumed and key not in excluded and not key.startswith("_") and key != "structure"
    } or None
    cif_text = enriched.get("_cif_text")
    if structure_root and (enriched.get("structure") is not None or cif_text):
        result["structure_path"] = _materialize_cif(
            enriched.get("source_id"), enriched.get("_structure_obj"), structure_root, cif_text,
        )
    if property_paths:
        result["property_paths"] = dict(property_paths)
    fill_derived_pairs(result)
    return result


def normalize_amcsd_entry(
    entry: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    property_paths: dict[str, str] | None = None,
    requested_id: str | None = None,
) -> dict[str, Any]:
    """Normalize one raw AMCSD entry into a complete DFT standard record."""
    enriched = enrich_amcsd(entry, requested_id=requested_id)
    return _apply_mapping(enriched, structure_root, property_paths=property_paths)


__all__ = [
    "AMCSD_CITATION",
    "API_VERSION",
    "enrich_amcsd",
    "normalize_amcsd_entry",
    "parse_amc",
]
