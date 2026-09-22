"""NOMAD Archive normalization: processed archive documents to DFT standard.

The primary raw shape is the response of
``POST https://nomad-lab.eu/prod/v1/api/v1/entries/{entry_id}/archive/query``:

```
{"entry_id": ..., "required": {...},
 "data": {"entry_id", "upload_id", "parser_name",
          "archive": {"metadata": {...}, "results": {...},
                      "run": [...], "workflow": [...]}}}
```

The structure is taken from ``metadata.optimade`` because NOMAD already stores
it in Angstrom with explicit site positions. Every other archive quantity is in
SI base units, so energies (Joule) are converted to eV and the plane-wave cutoff
to eV; lengths from ``run.system`` are converted from metre to Angstrom only
when the ``optimade`` structure is missing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from normalizers.dft import fill_derived_pairs
from sources.dft.nomad.download import API_VERSION

STANDARD_PATH = Path(__file__).resolve().parents[1] / "standard.yaml"
MAPPING_PATH = Path(__file__).resolve().parent / "mapping.yaml"

# NOMAD stores energies in Joule and lengths in metre.
JOULE_TO_EV = 1.0 / 1.602176634e-19
METRE_TO_ANGSTROM = 1.0e10
# Magnetization below this (in Bohr magneton) is treated as numerical noise.
MAGNETIC_TOLERANCE = 1e-3


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML schema or mapping document."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict[str, Any]:
    """Load and cache a YAML document for the lifetime of the process."""
    return load_yaml(path)


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def _requested_id(_: Any, enriched: dict[str, Any]) -> str | None:
    return enriched.get("_requested_id")


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
# Archive document accessors
# ---------------------------------------------------------------------------

def _dig(payload: Any, *keys: str) -> Any:
    """Read a nested mapping, returning ``None`` when any link is missing."""
    value = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _archive(document: dict[str, Any]) -> dict[str, Any]:
    archive = _dig(document, "data", "archive")
    return archive if isinstance(archive, dict) else {}


def _last_calculation(archive: dict[str, Any]) -> dict[str, Any] | None:
    runs = archive.get("run")
    if not isinstance(runs, list) or not runs:
        return None
    calculations = runs[-1].get("calculation") if isinstance(runs[-1], dict) else None
    if not isinstance(calculations, list) or not calculations:
        return None
    return calculations[-1] if isinstance(calculations[-1], dict) else None


def _last_of(value: Any) -> dict[str, Any] | None:
    """Return the last dict of a list, or the mapping itself when given one."""
    if isinstance(value, list):
        return value[-1] if value and isinstance(value[-1], dict) else None
    return value if isinstance(value, dict) else None


def _run_method(archive: dict[str, Any]) -> dict[str, Any]:
    """Return the last ``run.method`` mapping, or an empty mapping."""
    runs = archive.get("run")
    if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
        return {}
    return _last_of(runs[-1].get("method")) or {}


def _energy_value(archive: dict[str, Any], key: str = "total") -> float | None:
    """Return a final-calculation energy in eV, falling back to the workflow."""
    calculation = _last_calculation(archive)
    value = _dig(calculation, "energy", key, "value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) * JOULE_TO_EV
    workflow = archive.get("workflow")
    if isinstance(workflow, list) and workflow and isinstance(workflow[-1], dict):
        value = _dig(workflow[-1], "calculation_result_ref", "energy", key, "value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) * JOULE_TO_EV
    return None


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
        CifWriter(structure).write_file(target)
        return True
    except Exception:
        return False


def _structure_from_optimade(optimade: dict[str, Any]) -> Any:
    """Rebuild a pymatgen structure from NOMAD's ``metadata.optimade`` block."""
    lattice = optimade.get("lattice_vectors")
    positions = optimade.get("cartesian_site_positions")
    species = optimade.get("species_at_sites")
    if not (lattice and positions and species):
        return None
    try:
        from pymatgen.core import Lattice, Structure

        return Structure(Lattice(lattice), list(species), positions, coords_are_cartesian=True)
    except Exception:
        return None


def _structure_from_run(archive: dict[str, Any]) -> Any:
    """Rebuild a structure from a resolved ``run.system`` branch, in metres.

    ``run.system`` is a list of resolved systems; the last one matches the last
    calculation. Non-periodic systems have no lattice and return ``None`` so a
    molecular entry never produces a spurious crystal CIF.
    """
    runs = archive.get("run")
    if not isinstance(runs, list) or not runs or not isinstance(runs[-1], dict):
        return None
    system = _last_of(runs[-1].get("system"))
    atoms = system.get("atoms") if isinstance(system, dict) else None
    if not isinstance(atoms, dict):
        return None
    lattice = atoms.get("lattice_vectors")
    positions = atoms.get("positions")
    labels = atoms.get("labels")
    periodic = atoms.get("periodic")
    if periodic is not None and not any(bool(flag) for flag in periodic):
        return None
    if not (lattice and positions and labels):
        return None
    try:
        from pymatgen.core import Lattice, Structure

        scaled_lattice = [[float(x) * METRE_TO_ANGSTROM for x in row] for row in lattice]
        scaled_positions = [[float(x) * METRE_TO_ANGSTROM for x in row] for row in positions]
        return Structure(Lattice(scaled_lattice), list(labels), scaled_positions, coords_are_cartesian=True)
    except Exception:
        return None


def _kpoint_mesh(archive: dict[str, Any]) -> list[int] | None:
    """Return the regular k-point grid from ``run.method.k_mesh`` when present."""
    method = _run_method(archive)
    grid = _dig(method, "k_mesh", "grid")
    if not isinstance(grid, list) or len(grid) != 3:
        return None
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in grid):
        return None
    return [int(value) for value in grid]


def _spacegroup_from_structure(structure: Any) -> tuple[int | None, str | None, str | None]:
    """Return ``(number, symbol, crystal_system)`` using spglib through pymatgen."""
    if structure is None:
        return None, None, None
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        analyzer = SpacegroupAnalyzer(structure, symprec=0.1)
        number = int(analyzer.get_space_group_number())
        symbol = str(analyzer.get_space_group_symbol())
        system = getattr(analyzer.get_crystal_system(), "value", None) or str(analyzer.get_crystal_system())
        return number, symbol, str(system).replace("crystal_system.", "").lower()
    except Exception:
        return None, None, None


def _lattice_fields(structure: Any) -> dict[str, Any]:
    """Derive lattice parameters, density and atomic density from a structure."""
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
        fields["density"] = structure.density
    except Exception:
        pass
    try:
        if lattice.volume:
            fields["density_atomic"] = len(structure) / lattice.volume
    except Exception:
        pass
    return fields


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


def _materialize_cif(source_id: Any, structure: Any, structure_root: str | Path | None) -> str | None:
    """Ensure a canonical CIF exists and return its path, or ``None`` on failure."""
    if not structure_root or not source_id or structure is None:
        return None
    material_id = _safe_name(source_id)
    target = Path(structure_root) / material_id / f"{material_id}.cif"
    if target.exists():
        return str(target)
    return str(target) if _write_cif(structure, target) else None


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def _band_gap_ev(electronic: dict[str, Any]) -> tuple[float | None, bool | None, str | None, float | None, float | None]:
    """Return ``(band_gap, is_metal, band_gap_type, cbm, vbm)`` in eV.

    NOMAD may expose ``band_gap`` as a scalar mapping or as a list of
    spin/index-resolved entries; the smallest non-negative value is taken as the
    fundamental gap.
    """
    if not isinstance(electronic, dict):
        return None, None, None, None, None
    raw = electronic.get("band_gap")
    entries: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        entries = [raw]
    elif isinstance(raw, list):
        entries = [item for item in raw if isinstance(item, dict)]
    numeric = [float(item["value"]) for item in entries if isinstance(item.get("value"), (int, float))
               and not isinstance(item.get("value"), bool)]
    gap: float | None = None
    if numeric:
        non_negative = [value for value in numeric if value >= 0]
        gap = (min(non_negative) if non_negative else min(numeric)) * JOULE_TO_EV
    highest = [float(item["energy_highest_occupied"]) for item in entries
               if isinstance(item.get("energy_highest_occupied"), (int, float))]
    lowest = [float(item["energy_lowest_unoccupied"]) for item in entries
              if isinstance(item.get("energy_lowest_unoccupied"), (int, float))]
    vbm = max(highest) * JOULE_TO_EV if highest else None
    cbm = min(lowest) * JOULE_TO_EV if lowest else None
    if gap is None:
        return None, None, None, cbm, vbm
    if gap <= 0:
        return gap, True, "metal", cbm, vbm
    return gap, False, None, cbm, vbm


def _functional(simulation: dict[str, Any]) -> str | None:
    """Return a readable exchange-correlation functional name."""
    if not isinstance(simulation, dict):
        return None
    dft = simulation.get("dft") or {}
    names = dft.get("xc_functional_names")
    if isinstance(names, list) and names:
        return "+".join(str(name) for name in names)
    return dft.get("xc_functional_type") or dft.get("jacobs_ladder")


def enrich_archive(document: dict[str, Any], *, requested_id: str | None = None,
                   derive_symmetry: bool = True) -> dict[str, Any]:
    """Convert one NOMAD archive document into the shared enriched document."""
    archive = _archive(document)
    metadata = archive.get("metadata") or {}
    results = archive.get("results") or {}
    material = results.get("material") or {}
    properties = results.get("properties") or {}
    simulation = _dig(results, "method", "simulation") or {}
    optimade = metadata.get("optimade") or {}

    entry_id = document.get("entry_id") or _dig(document, "data", "entry_id")
    source_id = f"nomad:{entry_id}" if entry_id else None

    structure = _structure_from_optimade(optimade)
    if structure is None:
        structure = _structure_from_run(archive)

    elements = material.get("elements") or optimade.get("elements")
    if not elements and structure is not None:
        elements = sorted(str(element) for element in structure.composition.elements)

    atom_count = optimade.get("nsites")
    if atom_count is None:
        atom_count = _dig(properties, "structures", "structure_primitive", "n_sites")
    if atom_count is None and structure is not None:
        atom_count = len(structure)

    symmetry = material.get("symmetry") or {}
    spacegroup_number = symmetry.get("space_group_number")
    spacegroup_symbol = symmetry.get("space_group_symbol")
    crystal_system = symmetry.get("crystal_system")
    point_group = symmetry.get("point_group")
    if derive_symmetry and (spacegroup_number is None or crystal_system is None):
        derived_number, derived_symbol, derived_system = _spacegroup_from_structure(structure)
        spacegroup_number = spacegroup_number if spacegroup_number is not None else derived_number
        spacegroup_symbol = spacegroup_symbol or derived_symbol
        crystal_system = crystal_system or derived_system

    band_gap, is_metal, band_gap_type, cbm, vbm = _band_gap_ev(
        properties.get("electronic") if isinstance(properties.get("electronic"), dict) else {}
    )
    calculation = _last_calculation(archive)
    fermi_j = _dig(calculation, "energy", "fermi")
    fermi_level = float(fermi_j) * JOULE_TO_EV if isinstance(fermi_j, (int, float)) and not isinstance(fermi_j, bool) else None

    precision = simulation.get("precision") if isinstance(simulation, dict) else None
    cutoff_j = (precision or {}).get("planewave_cutoff") if isinstance(precision, dict) else None
    energy_cutoff = float(cutoff_j) * JOULE_TO_EV if isinstance(cutoff_j, (int, float)) and not isinstance(cutoff_j, bool) else None

    dft = simulation.get("dft") if isinstance(simulation, dict) else {}
    dft = dft if isinstance(dft, dict) else {}
    run_method = _run_method(archive)
    runs = archive.get("run")
    last_run = runs[-1] if isinstance(runs, list) and runs and isinstance(runs[-1], dict) else {}
    program = last_run.get("program") if isinstance(last_run.get("program"), dict) else {}
    basis_set = _dig(_last_of(run_method.get("electrons_representation")) or {}, "basis_set")
    if not basis_set:
        basis_set = run_method.get("basis_set")
    basis_set = _last_of(basis_set) or {}

    total_magnetization = None
    is_magnetic = None
    magnetic = properties.get("magnetic")
    if isinstance(magnetic, dict):
        candidate = magnetic.get("total_magnetization")
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            # NOMAD reports magnetization in J/T; convert to Bohr magneton.
            total_magnetization = float(candidate) / 9.2740100783e-24
            is_magnetic = abs(total_magnetization) > MAGNETIC_TOLERANCE

    enriched: dict[str, Any] = {
        "_requested_id": requested_id,
        "source_id": source_id,
        "source_url": f"https://nomad-lab.eu/prod/v1/gui/search/entries/entry/id/{entry_id}" if entry_id else None,
        "formula": material.get("chemical_formula_descriptive") or material.get("chemical_formula_hill"),
        "formula_reduced": material.get("chemical_formula_reduced"),
        "formula_anonymous": material.get("chemical_formula_anonymous"),
        "elements": elements,
        "chemical_system": "-".join(sorted(elements)) if elements else None,
        "atom_count": atom_count,
        "structure": None,
        "crystal_system": crystal_system,
        "spacegroup_number": spacegroup_number,
        "spacegroup_symbol": spacegroup_symbol,
        "point_group": point_group,
        "calculation_method": "DFT" if simulation else None,
        "code": (simulation.get("program_name") if isinstance(simulation, dict) else None)
        or program.get("name"),
        "code_version": (simulation.get("program_version") if isinstance(simulation, dict) else None)
        or program.get("version"),
        "functional": _functional(simulation),
        "kpoint_mesh": _kpoint_mesh(archive),
        "energy_cutoff": energy_cutoff,
        "total_energy": _energy_value(archive, "total"),
        "energy_per_atom": None,
        "formation_energy": _energy_value(archive, "formation"),
        "formation_energy_per_atom": None,
        "band_gap": band_gap,
        "band_gap_type": band_gap_type,
        "is_metal": is_metal,
        "is_gap_direct": None,
        "cbm": cbm,
        "vbm": vbm,
        "fermi_level": fermi_level,
        "magnetic_ordering": None,
        "total_magnetization": total_magnetization,
        "magnetization_per_atom": None,
        "magnetic_site_count": None,
        "magnetic_moments": None,
        "is_magnetic": is_magnetic,
        "last_updated": metadata.get("last_processing_time") or metadata.get("entry_timestamp")
        or metadata.get("upload_create_time"),
        "api_version": API_VERSION,
        # Retained in source_extra for provenance.
        "upload_id": _dig(document, "data", "upload_id") or metadata.get("upload_id"),
        "mainfile": metadata.get("mainfile"),
        "parser_name": _dig(document, "data", "parser_name") or metadata.get("parser_name"),
        "entry_type": metadata.get("entry_type"),
        "domain": metadata.get("domain"),
        "upload_name": metadata.get("upload_name"),
        "external_db": metadata.get("external_db"),
        "origin": metadata.get("origin"),
        "license": metadata.get("license"),
        "references": metadata.get("references"),
        "datasets": metadata.get("datasets"),
        "upload_create_time": metadata.get("upload_create_time"),
        "formula_descriptive": material.get("chemical_formula_descriptive"),
        "formula_hill": material.get("chemical_formula_hill"),
        "formula_iupac": material.get("chemical_formula_iupac"),
        "structural_type": material.get("structural_type"),
        "basis_set_type": dft.get("basis_set_type") or basis_set.get("type"),
        "core_electron_treatment": dft.get("core_electron_treatment") or basis_set.get("frozen_core"),
        "scf_threshold_energy_change": dft.get("scf_threshold_energy_change")
        or _dig(run_method, "scf", "threshold_energy_change"),
        "n_calculations": properties.get("n_calculations"),
    }
    enriched.update(_lattice_fields(structure))
    for key, value in _composition_fields(structure).items():
        enriched.setdefault(key, value)
    if structure is not None:
        enriched["structure"] = structure.as_dict()
    return enriched


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _apply_mapping(enriched: dict[str, Any], structure_root: str | Path | None,
                   raw_path: str | None = None) -> dict[str, Any]:
    standard = _load_yaml_cached(str(STANDARD_PATH))
    mapping = _load_yaml_cached(str(MAPPING_PATH))
    rules = mapping.get("mapping", {})
    result: dict[str, Any] = {}
    for name in standard.get("fields", {}):
        rule = rules.get(name) or {}
        if "value" in rule:
            value = rule["value"]
        else:
            value = enriched.get(rule.get("field"))
        if value is None and "default" in rule:
            value = rule["default"]
        if rule.get("transform"):
            value = TRANSFORMS[rule["transform"]](value, enriched)
        result[name] = value
    consumed = {
        rule.get("field")
        for rule in rules.values()
        if isinstance(rule, dict) and rule.get("field")
    }
    excluded = set(mapping.get("source_extra_exclude", []))
    result["source_extra"] = {
        key: value
        for key, value in enriched.items()
        if key not in consumed and key not in excluded and not key.startswith("_") and key != "structure"
    } or None
    if structure_root and enriched.get("structure") is not None:
        result["structure_path"] = _materialize_cif(
            enriched.get("source_id"), _structure_from_enriched(enriched), structure_root
        )
    if raw_path:
        result["property_paths"] = {"raw": raw_path}
    fill_derived_pairs(result)
    return result


def _structure_from_enriched(enriched: dict[str, Any]) -> Any:
    payload = enriched.get("structure")
    if not isinstance(payload, dict):
        return None
    try:
        from pymatgen.core import Structure

        return Structure.from_dict(payload)
    except Exception:
        return None


def normalize_nomad_archive(
    document: dict[str, Any],
    *,
    structure_root: str | Path | None = None,
    raw_path: str | None = None,
    requested_id: str | None = None,
    derive_symmetry: bool = True,
) -> dict[str, Any]:
    """Normalize one NOMAD archive document into a complete DFT standard record."""
    enriched = enrich_archive(document, requested_id=requested_id, derive_symmetry=derive_symmetry)
    return _apply_mapping(enriched, structure_root, raw_path=raw_path)


__all__ = [
    "enrich_archive",
    "normalize_nomad_archive",
]
