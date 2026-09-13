# 🎉 Alexandria (AMD)

Alexandria is an open, high-throughput materials database from the group of Prof. Miguel A. L. Marques (ICAMS, Ruhr University Bochum). It provides DFT-relaxed inorganic crystals with optimized geometries, convex hulls, phonons, benchmarks, and PBE/PBEsol/SCAN geometries.

The PsiCrawler Alexandria adapter supports both bulk archive ingestion and OPTIMADE queries, keeps raw archives verbatim, normalizes records into DFT schema `3.0`, and indexes them in SQLite.

- Official website: [alexandria.icams.rub.de](https://alexandria.icams.rub.de/)
- OPTIMADE API: `https://alexandria.icams.rub.de/<prefix>/v1`
- Raw download: [sources/dft/alexandria/download.py](../../sources/dft/alexandria/download.py)
- Source mapping: [normalizers/dft/alexandria/mapping.yaml](../../normalizers/dft/alexandria/mapping.yaml)
- Batch runner: [crawler/dft/alexandria/run_batch.py](../../crawler/dft/alexandria/run_batch.py)
- Single runner: [crawler/dft/alexandria/run_single.py](../../crawler/dft/alexandria/run_single.py)

## 🚀 Access Paths

The adapter uses two complementary channels:

1. **Bulk archives (primary).** The nginx directory index serves versioned `*.json.bz2` files. Each archive is one JSON object `{"entries": [ComputedStructureEntry, ...]}` serialized by pymatgen. Archives are streamed entry by entry, so multi-hundred-megabyte files never need to fit in memory.
2. **OPTIMADE REST API (on demand).** Endpoints `/info`, `/info/structures`, `/structures`, and `/references` follow OPTIMADE 1.1.0. `run_single` fetches one record by its `agm...` identifier; a filter can drive paged queries through `sources.dft.alexandria.download.OptimadeClient`.

The PBE OPTIMADE data endpoints can return HTTP 500 (backend PostgreSQL errors). The bulk archives remain reliable, so the batch runner is the default path and the single runner should target PBEsol when PBE is unavailable.

## 🗂️ Datasets

Primary datasets carry standard entry documents and are normalized into the DFT schema:

| Dataset | Path | Functional | Dimension |
|---|---|---|---|
| `pbe-3d` | `data/pbe/2025.07.02/alexandria_*.json.bz2` | PBE | 3D |
| `pbe-2d` | `data/pbe_2d/alexandria_2d_*.json.bz2` | PBE | 2D |
| `pbe-1d` | `data/pbe_1d/alexandria_1d_*.json.bz2` | PBE | 1D |
| `pbesol` | `data/pbesol/alexandria_ps_*.json.bz2` | PBEsol (+ SCAN fields via API) | 3D |
| `scan` | `data/scan/alexandria_scan_*.json.bz2` | SCAN | 3D |

Auxiliary datasets are preserved raw with `--download-only`: convex hulls, geometry-optimization paths, phonons, benchmarks, the phonon benchmark, prototypes, POTCARs, and selected older datasets. The 72 GB transfer-learning archive is intentionally excluded.

The full 3D PBE snapshot is roughly 3.4 GB compressed across 58 files. Use `--max-files` and `--max-records` to sample before scaling up.

## 🧬 Field Mapping

Bulk entries and OPTIMADE records converge on the same standard record. Key mappings:

- Identity: `data.mat_id` → `source_id` (namespaced), raw `mat_id` retained in `source_extra`.
- Composition: `data.formula`, `data.elements`; reduced/anonymous formula and reduced composition come from pymatgen.
- Structure: the inline pymatgen `structure`; lattice parameters, volume, density, and atomic number density are derived, and a canonical CIF is written under `data/dft/alexandria/structure/`.
- Symmetry: `data.spg` → `spacegroup_number`; the space-group symbol and crystal system are derived with pymatgen.
- Energetics: `energy_total` → `total_energy`/`energy_per_atom`; `data.e_form` → `formation_energy_per_atom`; `data.e_above_hull` → `energy_above_hull`.
- Electronic: `data.band_gap_ind` → `band_gap`, with `is_metal` and `is_gap_direct` derived from the indirect/direct gaps; the direct gap value is kept in `source_extra`.
- Magnetism: `data.total_mag` → `total_magnetization`; site moments → `magnetic_moments`.
- Decomposition: the decomposition string is parsed into `decomposes_to`.

Because the same `agm...` identifier can appear in more than one functional tier, `source_id` is prefixed with the dataset name, for example `pbe-3d:agm005737469`. The raw identifier stays in `source_extra.mat_id`.

Unmapped values (`dos_ef`, `energy_corrected`, `phase_separation_energy`, `stress`, `prototype_id`, `location`, `run_timestamp`, `dataset`, `dimensionality`) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/alexandria/
├── raw/
│   ├── pbe-3d/alexandria_00000.json.bz2
│   ├── optimade/pbesol/agm001010489.json
│   └── potcar-pbesol/potcar_pbesol.dat
├── structure/<dataset>_<mat_id>/<dataset>_<mat_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`raw_path` points at the source archive, and `source_documents` records the dataset, file, and entry index. Normalized records live only in `index.sqlite`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.alexandria.extract_batch --dataset pbe-3d --max-files 1 --max-records 100
```

Batch pipeline with manifest and resume:

```powershell
python -m crawler.dft.alexandria.run_batch --dataset pbe-3d --max-files 1 --max-records 1000
python -m crawler.dft.alexandria.run_batch --dataset pbesol
python -m crawler.dft.alexandria.run_batch --dataset pbe-3d --no-resume
```

Auxiliary download only:

```powershell
python -m crawler.dft.alexandria.run_batch --dataset geo-opt-pbe --download-only
python -m crawler.dft.alexandria.run_batch --dataset potcar-pbesol --download-only
```

Single OPTIMADE record (use PBEsol while the PBE backend is unavailable):

```powershell
python -m crawler.dft.alexandria.run_single agm001010489 --dataset pbesol
python -m tests.dft.alexandria.extract_single agm001010489 --dataset pbesol
```

Dataset names are listed in `sources/dft/alexandria/download.py::DATASETS`.

## ⚖️ License and Citation

Alexandria is distributed under the [Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/). Cite:

> Th. Cavignac, J. Schmidt, P.-P. De Breuck, A. Loew, T. F. T. Cerqueira, H.-C. Wang, A. Bochkarev, Y. Lysogorskiy, A. H. Romero, R. Drautz, S. Botti and M. A. L. Marques, *AI-Driven expansion and application of the Alexandria database*, J. Phys. Mater. **9**, 025014 (2026). doi:10.1088/2515-7639/ae6620

## 🧩 Module Layout

- `sources/dft/alexandria/download.py`: dataset catalog, bulk archive streaming, OPTIMADE client, resume.
- `normalizers/dft/alexandria/mapping.yaml`: Alexandria field to standard field mapping.
- `normalizers/dft/alexandria/normalize.py`: entry and OPTIMADE normalization.
- `crawler/dft/alexandria/`: single and batch pipeline runners.
- `tests/dft/alexandria/`: runnable limited-sample examples.
