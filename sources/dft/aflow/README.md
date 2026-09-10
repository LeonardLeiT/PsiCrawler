# 🎉 AFLOW

AFLOW is a high-throughput computational materials database and workflow ecosystem. The AFLOW adapter is designed for AFLOWLIB entries, AFLUX search results, structures, electronic-structure files, plots, elastic properties, thermal properties, magnetic data, Bader analysis, and selected VASP files.

- Official website: [aflow.org](https://aflow.org/)
- AFLUX API: [aflow.org/aflux](https://aflow.org/aflux/)
- Local extractor: [extractor.py](./extractor.py)
- Batch crawler: [crawler/dft/aflow/run_batch.py](../../../crawler/dft/aflow/run_batch.py)
- Source mapping: [schemas/dft/aflow.yaml](../../../schemas/dft/aflow.yaml)

## 🚀 Current Scope

The implementation is migrated from the AFLOW reference extractors in the repository root and currently supports:

- AFLOWLIB metadata through `aflowlib.json`
- AFLUX filtering and pagination
- AURL and AUID-based material identification
- Download profiles for core structures, plots, electronic data, symmetry, Bader, VASP raw files, or all files
- AFLOW-specific category JSON files
- Raw file preservation
- SQLite material and downloaded-file indexes
- Extraction status JSON and database extraction logs
- Retry and resume behavior in batch extraction

AFLOW uses AURLs and AUIDs rather than Materials Project material IDs. Raw files remain source-specific, while normalized/<aflow-id>/record.json follows the shared DFT schema and contains null for fields unavailable from the selected AFLOW entry.

## 🧬 AFLOW Fields

The AFLOW metadata record is stored from the complete `aflowlib.json` response. The current source field inventory includes:

- **Identity:** `auid`, `aurl`, `catalog`, `data_api`, `data_source`, `compound`, `prototype`
- **Composition and structure:** `species`, `composition`, `stoichiometry`, `geometry`, `geometry_orig`, atom and species counts, cell volumes, density, and Pearson symbols
- **Symmetry:** original and relaxed space groups, Bravais lattice, crystal family, crystal system, crystal class, and point group
- **Energetics:** cell and atom energies, formation enthalpy, pressure, stress, and residual pressure
- **Electronic properties:** `Egap`, gap type, electronic-structure files, band data, DOS data, and plots
- **Mechanical properties:** AEL bulk, shear, Young's, Poisson, and Debye values
- **Thermal properties:** AGL Debye temperature, thermal conductivity, and thermal expansion
- **Magnetism:** cell and atom spin, spin density, and magnetic files
- **Bader analysis:** net charges and atomic volumes
- **Calculation metadata:** code, DFT type, cutoff, k-points, runtime, memory, cores, AFLOW version, and node information

The executable source field inventory is defined in `extractor.py` and will be connected to the shared DFT normalization layer through `schemas/dft/aflow.yaml`.

## 🗂️ Storage Layout

The default AFLOW output is source-specific:

```text
data/dft/aflow/
├── raw/
│   └── aflow_014330e00a10f30d/
│       ├── metadata/
│       ├── structures/
│       ├── electronic_structure/
│       ├── figure/
│       ├── calculation/
│       └── raw/
├── normalized/
│   └── aflow_014330e00a10f30d/record.json
├── database/aflow.sqlite
├── logs/
└── manifests/
```

AFLOW's original filenames are preserved because they identify the calculation artifacts and file formats. Files ending in .xz use the XZ compression format; after a successful download the crawler decompresses them in place, removes the .xz file, and keeps the uncompressed filename in raw/. If decompression fails, the compressed file is retained and the error is recorded. The SQLite database is stored in database/aflow.sqlite, matching the Materials Project layout. Runtime logs are stored in logs/, and status/manifests are stored in manifests/.

## 🧩 Module Layout

- `config.py`: AFLOW data paths and HTTP settings.
- `client.py`: AFLOWLIB metadata and AFLUX HTTP access.
- `storage.py`: Material directories, raw files, and SQLite storage facade.
- `normalize.py`: Mapping from AFLOWLIB metadata to the unified DFT schema.
- `extractor.py`: Single-material extraction orchestration and compatibility helpers.
- `crawler/dft/aflow/`: Single and batch command-line runners.

## ▶️ Usage

Single entry:

```powershell
python -m crawler.dft.aflow.run_single "aflowlib.duke.edu:AFLOWDATA/ICSD_WEB/HEX/Li3N1_ICSD_642176"
```

Core structures and plots:

```powershell
python -m crawler.dft.aflow.run_single --profile plots
```

Electronic-structure profile:

```powershell
python -m crawler.dft.aflow.run_single --profile electronic
```

AFLUX batch search:

```powershell
python -m crawler.dft.aflow.run_batch --species Li,N --max 10 --profile plots
python -m crawler.dft.aflow.run_batch --query "Egap(1*,*2),catalog('ICSD')" --max 50
```

The reference scripts remain at the repository root for comparison. New development should use the project entrypoints under `crawler/dft/aflow`.








