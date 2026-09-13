# 🎉 Materials Project (MP)

Materials Project (MP) is a public computational materials database for exploring calculated crystal structures, thermodynamic stability, electronic structure, magnetic behavior, mechanical response, synthesis information, and provenance.

- Official website: [materialsproject.org](https://materialsproject.org/)
- API documentation: [Materials Project API](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started)
- Local mapping: [normalizers/dft/mp/mapping.yaml](../../normalizers/dft/mp/mapping.yaml)
- Unified DFT schema: [normalizers/dft/standard.yaml](../../normalizers/dft/standard.yaml)

## 🎯 Adapter Scope

The MP adapter aims to download everything the Materials Project API exposes for
a material:

- Single-material and comma-separated batch extraction
- The complete Summary document with `_all_fields=true`
- All 25 per-material REST routes, each with `_all_fields=true`
- Full pymatgen objects: structure (CIF + JSON), band structure and projected
  band structure for all three k-path conventions, DOS, phonon band structure
  and DOS, Wulff shape, thermo entries, and references
- Charge density (`CHGCAR`)
- Raw VASP archives mirrored through NoMaD
- MP AlphaID and legacy numeric ID preservation
- Schema-driven normalization and SQLite indexing

Each category can be disabled per run: `--no-properties`, `--no-files`,
`--no-charge-density`, `--no-raw-vasp`. The separate `/doi` route is not
material-scoped and is not downloaded.

## 🚀 Run

Configure an API key in a local `.env` file:

```powershell
Copy-Item .env.example .env
```

Set `MP_API_KEY` in `.env`, then run one record:

```powershell
python -m crawler.dft.mp.run_single mp-149
```

Run a batch:

```powershell
python -m crawler.dft.mp.run_batch --mp-ids mp-149,mp-13,mp-22526 --sleep 1
python -m crawler.dft.mp.run_batch --chemsys Si-O --max 100 --sleep 1
```

The API key file is ignored by Git. Never commit it or place it in source code.

## 🧩 Query Strategies

MP routes do not share one universal query syntax. The adapter uses route-specific strategies:

- `summary`: retrieve the complete MP Summary document with `_all_fields=true`.
- `material_ids`: use a material ID when the route supports direct material filtering.
- `task_ids`: query calculation-level data such as tasks, task entries, EOS, and XAS records.
- `identifiers`: resolve phonon IDs from Summary `phonon_IDs` before querying phonon data.
- `formula`: query insertion-electrode records by material formula.
- `target_formula`: query synthesis records by their target formula; this route does not support `material_ids`.
- `film_id`: query substrate records by film material ID.

The route names, API paths, and query strategies are executable configuration in [`sources/dft/mp/download.py`](../../sources/dft/mp/download.py), not a manually maintained comment-only list.

Multi-ID filters are sent as comma-separated values; empty context filters return no documents without making an unfiltered request. Every route requests `_all_fields=true` except `synthesis` and `tasks/entries`, whose APIs reject that parameter. Pagination follows offsets or the returned token and checks `meta.total_doc`. Premature end, repeated pages/tokens, and changing totals raise a route error and result in a partial extraction rather than silently reporting success.

Complete downloads are marked by `source_documents.property_download_version = 4`. Full band structure, DOS, and phonon data are stored as serialized pymatgen objects rather than summary references, and the raw VASP archives come from NoMaD.

### Resume and deduplication

`run_single`/`run_batch` skip a material only when it is genuinely complete. The check (in [`sources/dft/mp/download.py`](../../sources/dft/mp/download.py), function `completed`) requires all of:

- the stored `schema_version` matches and `download_status == "success"`;
- `property_download_version` matches the current version;
- the stored `download_categories` cover every category requested this run
  (`properties`, `files`, `charge_density`, `raw_vasp`,
  `bandstructure_projections`);
- `bs_path_types` match when band-structure files are requested;
- `raw_path` and the per-category sentinel files still exist on disk.

Matching accepts either the stored `source_id` (the canonical AlphaID) or the
`requested_id`, so legacy numeric IDs such as `mp-149` resume correctly. Changing
the requested categories (for example adding `--no-raw-vasp`) makes a record
incomplete and it is downloaded again; repeating an identical command skips
everything. `--force` always re-downloads.

### Parallelism

`run_batch --workers N` downloads different materials concurrently. Each worker
reuses its own `MPClient`/`MPArtifactsClient` (thread-local), so no HTTP session
is shared. The SQLite index uses WAL and a busy timeout, and write retries on
lock contention. `--sleep` throttles dispatch in both sequential and parallel
modes. The default is `--workers 1`; values around 4-8 are reasonable.

## 📦 Data Coverage

### Summary fields

The adapter requests the complete Summary response with `_all_fields=true` and preserves the raw document in `summary.json`. The upstream field inventory may change independently of the local normalized schema.

The fields cover:

- **Identity:** `material_id`, `formula_pretty`, `formula_anonymous`, `chemsys`, `elements`
- **Composition and structure:** `composition`, `composition_reduced`, `structure`, `nsites`, `nelements`, `volume`, `density`, `density_atomic`, `symmetry`
- **Thermodynamics:** `energy_per_atom`, `formation_energy_per_atom`, `energy_above_hull`, `equilibrium_reaction_energy_per_atom`, `decomposes_to`, `is_stable`
- **Electronic structure:** `band_gap`, `cbm`, `vbm`, `efermi`, `is_gap_direct`, `is_metal`, `bandstructure`, `dos`, `dos_energy_up`, `dos_energy_down`
- **Magnetism:** `is_magnetic`, `ordering`, `total_magnetization`, normalized magnetization values, magnetic-site counts, and magnetic species
- **Mechanical and dielectric summaries:** bulk and shear modulus, Poisson ratio, anisotropy, dielectric components, refractive index, piezoelectric maximum, surface energy, work function, and shape factor
- **Metadata and provenance:** deprecation status, warnings, origins, database identifiers, builder metadata, task identifiers, and update timestamps
- **Related properties:** XAS summaries, grain-boundary references, possible species, reconstructed status, and available-property flags

Internal calculation identifiers such as `task_ids`, `database_IDs`, and `phonon_IDs` remain available in the raw response for traceability, but are intentionally excluded from the cross-database comparison fields.

### REST routes

Every per-material route is stored with all fields:

`absorption`, `alloys`, `bonds`, `chemenv`, `core`, `dielectric`, `elasticity`,
`electronic_structure`, `eos`, `grain_boundaries`, `insertion_electrodes`,
`magnetism`, `oxidation_states`, `phonon`, `piezoelectric`, `provenance`,
`robocrys`, `similarity`, `substrates`, `surface_properties`, `synthesis`,
`tasks`, `tasks/entries`, `thermo`, `xas`.

### Full objects and raw files

- `structure.cif` / `structure.json`
- `bandstructure_<setyawan_curtarolo|hinuma|latimer_munro>.json`
- `bandstructure_<path_type>_projections.json` (atom/orbital projections)
- `dos.json`
- `phonon_bandstructure.json`, `phonon_dos.json`
- `wulff_shape.json`
- `entries.json` (thermo entries), `references.json`
- `charge_density/CHGCAR`
- `nomad/archive_<nnn>/` with the raw VASP files MP mirrors through NoMaD

### Unified DFT record

The executable standard schema is version `3.0` with 115 fields. Its categories include implemented properties, pipeline metadata, source extensions, and explicitly reserved fields:

- **Material identity and provenance**
- **Formula, composition, elements, and atom counts**
- **Crystal structure, lattice, density, symmetry, and space group**
- **Calculation method and computational settings**
- **Energy, formation energy, stability, and decomposition**
- **Band gap, Fermi level, band structure, and density of states**
- **Magnetic properties**
- **Elastic and dielectric properties**
- **Piezoelectric, surface, phonon, thermal, and XAS properties**
- **Source paths, retrieval status, route errors, and schema metadata**

Fields unavailable from MP or from a particular route are represented as `null`; reserved fields are required to remain null. Route documents are saved in `raw/<requested-id>/properties/<route>.json` and referenced by `property_paths` and `source_documents`. Unmapped Summary values are retained in `source_extra`, subject to the mapping's exclusions.

Every normalized record stores its canonical structure as a CIF at `data/dft/mp/structure/<source_id>/<source_id>.cif`; `structure_path` points to it. Normalization prefers an already downloaded CIF, then the inline Summary structure, then a raw POSCAR/CONTCAR, and leaves `structure_path` null if conversion fails.

Schema 3.0 normalization derives atomic number density from `nsites / volume`, converts and cross-checks weighted surface energy in `J/m^2`, maps `has_props`, and treats `dos_energy_up/down` as scalar DOS gaps. The `elasticity` route document supplies `debye_temperature` and provides `elastic_tensor_path`; `youngs_modulus` is derived from the VRH bulk and shear moduli as `E = 9KG/(3K+G)`. `builder_meta` is an object; decomposition, grain-boundary, and XAS summaries are lists. Missing functional information remains null rather than defaulting to PBE.

`core/storage.py` computes the raw-content SHA-256 (`content_hash`) when the record is indexed. A successful download status does not imply that all physical properties are available.

## 🗂️ Storage Layout

Downloaded data is local-only and ignored by Git:

```text
data/dft/mp/
├── raw/<requested-id>/
│   ├── summary.json                    # complete Summary document
│   ├── properties/<route>.json         # one file per REST route
│   ├── files/
│   │   ├── structure.cif  structure.json
│   │   ├── bandstructure_<path_type>.json
│   │   ├── dos.json
│   │   ├── phonon_bandstructure.json  phonon_dos.json
│   │   ├── wulff_shape.json
│   │   ├── entries.json  references.json
│   │   └── charge_density/CHGCAR
│   └── nomad/
│       ├── download_info.json
│       └── archive_<nnn>/…             # extracted raw VASP files
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`<requested-id>` preserves the ID supplied by the user, while the normalized record also stores the canonical MP `source_id`. This supports both legacy numeric IDs such as `mp-149` and current AlphaIDs. Normalized records live only in `index.sqlite`; the raw documents and artifacts above are never modified.

## 🔍 Search Index

The SQLite index is optimized for common material screening fields, including:

- source and material identifiers
- formula and chemical system
- elements and atom count
- density and volume
- crystal system and space group
- energy per atom and energy above hull
- stability
- band gap and metallicity
- Fermi level
- elastic moduli
- magnetization

The complete source response remains in JSON; SQLite is an index for application search and filtering, not a replacement for the raw or normalized record.

The modulus columns are `bulk_modulus_vrh` and `shear_modulus_vrh`. Storage initialization adds missing columns to existing databases without deleting old columns or rows. New columns receive values when a record is saved again. Resume checks reject old schema versions, so old records are eligible for reprocessing.

## 🧱 Implementation Files

- `sources/dft/mp/download.py` · `MPClient` (REST, all routes), `MPArtifactsClient`
  (pymatgen objects + NoMaD archives), and raw storage
- `normalizers/dft/mp/mapping.yaml` · raw field to standard field mapping
- `normalizers/dft/mp/normalize.py` · executable schema normalization
- `crawler/dft/mp/run_single.py` · single-record pipeline CLI
- `crawler/dft/mp/run_batch.py` · batch pipeline CLI

## ⚖️ Data Use

Use the MP API responsibly. Respect API rate limits, source licenses, attribution requirements, and the official citation guidance. Large downloads should be cached locally and performed only once where possible.
