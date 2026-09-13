# 🎉 AFLOW

AFLOW is a high-throughput computational materials database and workflow ecosystem. The AFLOW adapter is designed for AFLOWLIB entries, AFLUX search results, structures, electronic-structure files, plots, elastic properties, thermal properties, magnetic data, Bader analysis, and selected VASP files.

- Official website: [aflow.org](https://aflow.org/)
- AFLUX API: [aflow.org/aflux](https://aflow.org/aflux/)
- Raw download: [sources/dft/aflow/download.py](../../sources/dft/aflow/download.py)
- Pipeline batch runner: [crawler/dft/aflow/run_batch.py](../../crawler/dft/aflow/run_batch.py)
- Source mapping: [normalizers/dft/aflow/mapping.yaml](../../normalizers/dft/aflow/mapping.yaml)

## 🚀 Current Scope

The adapter currently supports:

- AFLOWLIB metadata through `aflowlib.json`
- AFLUX filtering and pagination
- AURL and AUID-based material identification
- Download profiles for core structures, plots, electronic data, symmetry, Bader, VASP raw files, or all files
- AFLOW-specific category JSON files
- Raw file preservation
- Normalized records indexed in SQLite
- Retry and resume behavior in batch extraction

AFLOW uses AURLs and AUIDs rather than Materials Project material IDs. Raw files remain source-specific, while normalized records follow DFT schema `3.0` with 115 fields. Unavailable fields are null, and explicitly reserved fields must remain null. Normalized records live only in `index.sqlite`.

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

The source field inventory in the AFLOW mapping is connected to the shared contract through [mapping.yaml](../../normalizers/dft/aflow/mapping.yaml). The normalizer enriches metadata with available local files before applying the mapping.

Schema 3.0 converts pressure from kbar to GPa and computes atomic number density as `natoms / volume_cell` in `atom/Angstrom^3`. It splits the AFLOW `code` string into program name and version and uses the last entry in the source date history. Missing band-gap information remains null. Thermal conductivity currently denotes the AGL value at 300 K; source conditions still matter when comparing materials. Every normalized record stores its canonical structure as a CIF at `data/dft/aflow/structure/<source_id>/<source_id>.cif`; `structure_path` points to it, converting a raw CIF, `structure_relax*` JSON, or POSCAR/CONTCAR when needed.

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
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

AFLOW's original filenames are preserved because they identify the calculation artifacts and file formats. Files ending in .xz use the XZ compression format; after a successful download the crawler decompresses them in place, removes the .xz file, and keeps the uncompressed filename in raw/. If decompression fails, the compressed file is retained and the error is recorded. Normalized records are stored only in `index.sqlite`. Runtime logs are stored in logs/, and manifests are stored in manifests/.

## 🧩 Module Layout

- `sources/dft/aflow/download.py`: AFLOWLIB metadata, file download, AFLUX search, raw storage.
- `normalizers/dft/aflow/mapping.yaml`: AFLOW field to standard field mapping.
- `normalizers/dft/aflow/normalize.py`: enrichment and mapping to the unified DFT schema.
- `crawler/dft/aflow/`: single and batch pipeline runners.

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

Run commands from the repository root. Batch resume skips records already present in `index.sqlite` for the current schema version. Add `--no-resume` to reprocess them:

```powershell
python -m crawler.dft.aflow.run_batch --species Li,N --max 10 --profile plots --no-resume
```

Batch resume skips records already present in `index.sqlite` for the current schema version; add `--no-resume` to reprocess them.






