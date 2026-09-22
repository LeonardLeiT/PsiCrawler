# 🎉 NOMAD Archive

NOMAD is a free, open FAIR data management platform for materials science,
developed by FAIRmat. Its public Archive aggregates parsed and normalized
computational results from many codes (VASP, FHI-aims, Quantum ESPRESSO, and
more) and mirrors external databases such as AFLOW. Each record is a processed
*entry* with searchable metadata, a bounded processed *archive*, and the
original *raw* files.

The PsiCrawler NOMAD adapter enumerates public entries through the native API,
fetches each processed archive document, keeps it verbatim under `raw/`,
normalizes it into DFT schema `3.0`, and indexes it in SQLite.

- Official website: [nomad-lab.eu](https://nomad-lab.eu/)
- Native API: `https://nomad-lab.eu/prod/v1/api/v1`
- OPTIMADE API: `https://nomad-lab.eu/prod/v1/optimade/v1`
- GUI search: `https://nomad-lab.eu/prod/v1/gui/search/entries`
- Raw download: [sources/dft/nomad/download.py](../../sources/dft/nomad/download.py)
- Source mapping: [normalizers/dft/nomad/mapping.yaml](../../normalizers/dft/nomad/mapping.yaml)
- Batch runner: [crawler/dft/nomad/run_batch.py](../../crawler/dft/nomad/run_batch.py)
- Single runner: [crawler/dft/nomad/run_single.py](../../crawler/dft/nomad/run_single.py)

## 🚀 Access Paths

The adapter uses the native API, which carries richer search metadata than the
OPTIMADE projection and is the only channel that exposes the processed archive.

1. **Entry enumeration.** `POST /entries/query` returns public entry metadata
   with `page_after_value` pagination. The scope `dft` sends `{"domain": "dft"}`;
   `all` targets every public entry.
2. **Processed archive (primary).** `POST /entries/{entry_id}/archive/query`
   returns one archive document. The adapter requests a bounded `required` tree:
   identity and provenance, `results.{material,method,properties}`,
   `metadata.optimade` (already in Angstrom), the last `run.calculation` energy,
   and the resolved `run.system.atoms` plus selected `run.method` branches
   (`k_mesh`, `electrons_representation`, `basis_set`, `scf`). Only those
   sub-branches are requested because `"*"` would also pull the bulky
   code-specific dumps (for example VASP `x_vasp_incar_*`) and duplicate
   symmetry/descriptor blocks.
3. **Bulk zip.** `POST /entries/archive/download/query` streams a zip with
   `<upload-id>/<entry-id>.json` members plus a `manifest.json`.
4. **OPTIMADE (secondary).** `https://nomad-lab.eu/prod/v1/optimade/v1` exposes
   `/structures`, `/references`, `/info`, and `/links` (OPTIMADE 1.2.0) for
   structure-only paging.

Public data needs no authentication. Setting `NOMAD_API_TOKEN` is optional and
only relevant for non-public resources or to raise the anonymous limits. NOMAD
enforces per-IP rate limits and returns HTTP 503 when they are exceeded, so the
client retries with a linear backoff and the runners expose `--sleep`.

## 🗂️ Scale

| Metric | Value (live, 2026-09) |
|---|---|
| Entries (`domain: dft`) | ~19,340,000 |
| Entries (all public) | ~19,415,000 |
| Materials | ~4,344,000 |
| Calculations | ~212,800,000 |
| Uploads | ~11,045 |
| Datasets with DOI | ~2,115 |
| OPTIMADE structures | ~18,840,000 |

A full-archive run makes one archive request per entry. Plan for weeks to months
at the anonymous rate limits and for terabyte-scale raw storage; prefer
`--scope dft` with `--max-records` and filtered `--query-json` slices.

## 🧬 Field Mapping

- Identity: `source_id` is namespaced as `nomad:<entry_id>`; the GUI entry URL
  is `source_url`. `upload_id`, `mainfile`, `parser_name`, `entry_type`,
  `domain`, `external_db`, `origin`, and the source `license` are retained in
  `source_extra`.
- Composition: `results.material.chemical_formula_*` and `elements`; reduced and
  anonymous formulas and reduced composition are also derived with pymatgen.
- Structure: `metadata.optimade` (`lattice_vectors`, `cartesian_site_positions`,
  `species_at_sites`, all in Angstrom) is rebuilt with pymatgen. Lattice
  parameters, volume, density, and atomic number density are derived, and a
  canonical CIF is written under `data/dft/nomad/structure/`. When the OPTIMADE
  block has no lattice, the resolved `run.system.atoms` branch is used with
  metre→Angstrom conversion. Non-periodic entries (molecules) and entries whose
  upstream lattice is missing have no crystal structure: `structure` stays
  `null` and no CIF is written, but the geometry is still kept verbatim in
  `raw/`.
- Symmetry: `results.material.symmetry.{crystal_system,spacegroup_number,
  spacegroup_symbol,point_group}` when present; otherwise derived with spglib
  through pymatgen. Disable with `--no-symmetry`.
- Calculation settings: `results.method.simulation.program_name` (falling back
  to `run.program.name`) → `code`/`code_version`; `dft.xc_functional_names` →
  `functional`; the plane-wave cutoff is converted to eV → `energy_cutoff`.
  Basis-set type, core-electron treatment, and SCF threshold are kept in
  `source_extra`, falling back to `run.method` when the results branch omits
  them.
- K-points: `run.method.k_mesh.grid` becomes `kpoint_mesh` when it is a
  three-positive-integer mesh; otherwise `kpoint_mesh` is `null`.
- Energetics: the last `run.calculation.energy.total.value` (or the resolved
  `workflow.calculation_result_ref.energy.total.value`) is converted from Joule
  to eV → `total_energy`; `energy_per_atom` is derived from `atom_count`. Values
  are code- and basis-set-specific: all-electron codes (for example FHI-aims)
  report total energies orders of magnitude larger than pseudopotential codes
  (VASP, Quantum ESPRESSO), so compare only within the same
  `code`/`basis_set_type`/`core_electron_treatment`.
- Electronic: `results.properties.electronic.band_gap` (Joule → eV) →
  `band_gap`, with `is_metal` and `band_gap_type` derived; VBM/CBM come from
  `energy_highest_occupied`/`energy_lowest_unoccupied` and `fermi_level` from
  `run.calculation.energy.fermi`.
- Magnetism: `results.properties.magnetic.total_magnetization` (J/T) is
  converted to Bohr magneton when present; other magnetic orderings are not
  published consistently and remain `null`.

NOMAD is broad: only `domain: dft` entries map cleanly onto the DFT contract.
Because NOMAD mirrors external databases, a `nomad:<entry_id>` record can
semantically overlap an existing AFLOW or Materials Project record; the
`external_db`/`origin` provenance in `source_extra` supports later deduplication.
Per-entry licenses (for example `CC BY 4.0`) are preserved in `source_extra`
because the standard `license` field is reserved.

## 🗂️ Storage Layout

```text
data/dft/nomad/
├── raw/
│   ├── <upload_id>/<entry_id>.json
│   └── _bulk/nomad_<scope>_<run_id>.zip
├── structure/nomad_<entry_id>/nomad_<entry_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`raw_path` points at the archive document and `property_paths["raw"]` mirrors
it. Normalized records live only in `index.sqlite`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.nomad.extract_batch --scope dft --max-records 20
```

Batch pipeline with manifest and resume:

```powershell
python -m crawler.dft.nomad.run_batch --scope dft --max-records 1000
python -m crawler.dft.nomad.run_batch --mode bulk --scope dft --max-records 1000
python -m crawler.dft.nomad.run_batch --query-json '{"results.material.elements":{"all":["Si","O"]}}'
```

Single archive entry. NOMAD entry identifiers often start with `--`, so pass
them after `--` or with the flag form:

```powershell
python -m crawler.dft.nomad.run_single --entry-id=--0TXFv_aZUPi2bqjewWq3CTSGfc
python -m tests.dft.nomad.extract_single -- --0TXFv_aZUPi2bqjewWq3CTSGfc
```

Fixed identifier list:

```powershell
python -m crawler.dft.nomad.run_batch --entry-id-file ids.txt --no-symmetry
```

## ⚖️ License and Citation

NOMAD data carries per-entry licenses (commonly Creative Commons licenses) that
are preserved in `source_extra.license`. Cite NOMAD itself:

> M. Scheidgen, L. Himanen, A. N. Ladines, et al., *NOMAD: A distributed
> web-based platform for managing materials science research data*, Journal of
> Open Source Software **9**(102), 6363 (2024). doi:10.21105/joss.06363

When reusing data from a mirrored external database, cite that original source
as well.

## 🧩 Module Layout

- `sources/dft/nomad/download.py`: native API client, pagination, archive fetch, bulk zip, resume.
- `normalizers/dft/nomad/mapping.yaml`: NOMAD field to standard field mapping.
- `normalizers/dft/nomad/normalize.py`: SI→standard conversion and archive normalization.
- `crawler/dft/nomad/`: single and batch pipeline runners.
- `tests/dft/nomad/`: runnable limited-sample examples.
