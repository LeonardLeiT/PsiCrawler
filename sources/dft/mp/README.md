# 🎉 Materials Project (MP)

Materials Project (MP) is a public computational materials database for exploring calculated crystal structures, thermodynamic stability, electronic structure, magnetic behavior, mechanical response, synthesis information, and provenance.

- Official website: [materialsproject.org](https://materialsproject.org/)
- API documentation: [Materials Project API](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started)
- Local mapping: [schemas/dft/mp.yaml](../../../schemas/dft/mp.yaml)
- Unified DFT schema: [schemas/dft/standard.yaml](../../../schemas/dft/standard.yaml)

## 🎯 Adapter Scope

The MP adapter supports:

- Single-material extraction
- Comma-separated batch extraction
- Summary data capture with all currently exposed MP Summary fields
- Source-specific property routes
- MP AlphaID and legacy numeric ID preservation
- Structure export to JSON and CIF
- Schema-driven normalization
- SQLite indexing for common search fields
- Per-route raw JSON storage

The adapter currently covers the 26 material routes documented by MP, excluding the general `/summary` route and the separate `/doi` route.

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
- `task_ids`: query calculation-level data such as tasks and EOS records.
- `identifiers`: resolve phonon IDs from Summary `phonon_IDs` before querying phonon data.
- `summary_field`: preserve band-structure and DOS references exposed by Summary.
- `formula`: query XAS and insertion-electrode records by material formula.
- `film_id`: query substrate records by film material ID.

The route names, API paths, and query strategies are executable configuration in [mp.yaml](../../../schemas/dft/mp.yaml), not a manually maintained comment-only list.

## 📦 Data Coverage

### Summary fields

The MP Summary response currently exposes 69 fields. The adapter requests the complete response and preserves the raw document in `summary.json`.

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

### Unified DFT record

The executable standard schema currently contains 162 fields. It provides a stable comparison layer for other DFT sources:

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

Fields unavailable from MP or from a particular route are represented as `null`. Route-specific documents remain nested under `source_properties` rather than being flattened into unrelated universal fields.

## 🗂️ Storage Layout

Downloaded data is local-only and ignored by Git:

```text
data/dft/mp/
├── raw/<requested-id>/
│   ├── summary.json
│   ├── structure.json
│   ├── structure.cif
│   └── properties/
│       └── <route>.json
├── normalized/<requested-id>/
│   └── record.json
├── database/
│   └── mp.sqlite
├── logs/
└── manifests/
```

`<requested-id>` preserves the ID supplied by the user, while the normalized record also stores the canonical MP `source_id`. This supports both legacy numeric IDs such as `mp-149` and current AlphaIDs.

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

## 🧱 Implementation Files

- `client.py` · MP REST client and route-specific query parameters
- `config.py` · environment variables and local storage paths
- `extractor.py` · single-material orchestration across all routes
- `normalize.py` · executable schema normalization
- `storage.py` · JSON, CIF, and SQLite persistence
- `structure.py` · MP structure-to-CIF conversion
- `crawler/dft/mp/run_single.py` · single-record CLI
- `crawler/dft/mp/run_batch.py` · batch CLI

## ⚖️ Data Use

Use the MP API responsibly. Respect API rate limits, source licenses, attribution requirements, and the official citation guidance. Large downloads should be cached locally and performed only once where possible.
