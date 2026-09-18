# 🎉 Materials Cloud

Materials Cloud is an open-science platform for sharing computational materials
science data, maintained by EPFL and its partners. Beyond the community Archive,
it hosts curated databases such as the Materials Cloud 3D structure database
(MC3D) and the 2D database (MC2D).

The PsiCrawler Materials Cloud adapter pages the OPTIMADE API of each curated
child database, keeps archive bulk artifacts verbatim, normalizes records into
DFT schema `3.0`, and indexes them in SQLite.

- Official website: [materialscloud.org](https://www.materialscloud.org/)
- OPTIMADE index: `https://optimade.materialscloud.org/main/index/v1`
- Archive file API: `https://archive.materialscloud.org/api/records/<uuid>/files`
- Raw download: [sources/dft/materialscloud/download.py](../../sources/dft/materialscloud/download.py)
- Source mapping: [normalizers/dft/materialscloud/mapping.yaml](../../normalizers/dft/materialscloud/mapping.yaml)
- Batch runner: [crawler/dft/materialscloud/run_batch.py](../../crawler/dft/materialscloud/run_batch.py)
- Single runner: [crawler/dft/materialscloud/run_single.py](../../crawler/dft/materialscloud/run_single.py)

## 🚀 Access Paths

The adapter uses two complementary channels:

1. **OPTIMADE REST API (primary).** Each child database exposes
   `https://optimade.materialscloud.org/main/<prefix>/v1` with `/info`,
   `/links`, `/structures`, and `/references`. No API key is required. Records
   carry standard OPTIMADE geometry fields plus `_mcloud_*` extensions.
2. **Archive bulk files.** The curated archives are stored on the Materials
   Cloud Archive (InvenioRDM). `list_bulk_files` resolves the download links and
   `download_bulk_file` streams the files into `raw/<dataset>/`. The
   multi-gigabyte provenance archives are excluded from the default selection.

> The Materials Cloud OPTIMADE servers report the total entry count in
> `meta.data_returned` instead of the page length, so `OptimadeClient` paginates
> using `meta.data_available` and the actual number of returned records.
>
> The edge also rejects oversized pages with HTTP 403, so `page_limit` is bounded
> to `1`-`500`. The batch runner validates `--page-limit` before starting and the
> client raises a clear error if a larger value is passed programmatically.

## 🗂️ Datasets

| Dataset | OPTIMADE prefix | Functional | Dimension | Records |
|---|---|---|---|---|
| `mc3d-pbe-v1` | `mc3d-pbe-v1` | PBE | 3D | ~34,970 |
| `mc3d-pbesol-v1` | `mc3d-pbesol-v1` | PBEsol | 3D | ~34,111 |
| `mc3d-pbesol-v2` | `mc3d-pbesol-v2` | PBEsol | 3D | ~33,142 |
| `mc2d` | `mc2d` | PBE | 2D | ~2,683 |

Bulk artifacts (Archive record `eqzc6-e2579` for MC3D, `17gf6-84915` for MC2D)
include `MC3D-structures.aiida`, `MC3D-cifs.zip`, `structure_2d.json`,
`optimized_2d_structures.zip`, and `bands.zip`. The 12 GB `MC3D-provenance.aiida`
and the 8.4 GB `MC2D_export_*.aiida` are intentionally left out of the default
bulk selection.

## 🧬 Field Mapping

- Identity: `source_id` is namespaced as `<dataset>:<id>`, for example
  `mc3d-pbesol-v2:0290c725-d663-426f-b857-524aabebc244`. `_mcloud_mc3d_id` and
  the source database (`_mcloud_source_db`, `_mcloud_source_db_id`) are retained
  in `source_extra`.
- Composition: `chemical_formula_descriptive`/`_reduced`/`_anonymous` →
  `formula`/`formula_reduced`/`formula_anonymous`; `elements`; reduced formula
  and composition are also derived with pymatgen.
- Structure: the inline OPTIMADE geometry (`lattice_vectors`,
  `cartesian_site_positions`, `species_at_sites`) is rebuilt with pymatgen, and
  lattice parameters, volume, density, and atomic number density are derived. A
  canonical CIF is written under `data/dft/materialscloud/structure/`.
- Symmetry: OPTIMADE does not expose a space-group number, so `crystal_system`,
  `spacegroup_number`, and `spacegroup_symbol` are derived with spglib through
  pymatgen; disable with `--no-symmetry`.
- Energetics: `_mcloud_total_energy` → `total_energy`/`energy_per_atom`.
- Electronic: `_mcloud_band_gap` → `band_gap`, with `is_metal` set when the gap
  is non-positive. The direct/indirect flag is not published, so
  `is_gap_direct`/`band_gap_type` remain `null`.
- Magnetism: `_mcloud_total_magnetization` → `total_magnetization` and
  `magnetization_per_atom`; `_mcloud_absolute_magnetization` stays in
  `source_extra`.
- Unmapped values (`_mcloud_cell_volume`, `_mcloud_ctime`, `mc3d_id`,
  `source_db`, `source_db_id`) are retained in `source_extra`.

MC3D and MC2D publish structures and a limited set of scalar properties, so
formation energy, hull energy, elastic, dielectric, and phonon fields are `null`.

## 🗂️ Storage Layout

```text
data/dft/materialscloud/
├── raw/
│   ├── mc3d-pbesol-v2/MC3D-structures.aiida
│   ├── mc2d/structure_2d.json
│   └── mc3d-pbesol-v2/optimade/<id>.json
├── structure/<dataset>_<id>/<dataset>_<id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

Batch OPTIMADE runs do not persist per-record files; the OPTIMADE URL is kept in
`source_documents`. `run_single` preserves the raw record JSON. Normalized
records live only in `index.sqlite`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.materialscloud.extract_batch --dataset mc2d --max-records 50
```

Batch pipeline with manifest and resume:

```powershell
python -m crawler.dft.materialscloud.run_batch --dataset mc2d --max-records 1000
python -m crawler.dft.materialscloud.run_batch --dataset mc3d-pbesol-v2
python -m crawler.dft.materialscloud.run_batch --dataset mc3d-pbe-v1,mc3d-pbesol-v1,mc3d-pbesol-v2
```

Single OPTIMADE record:

```powershell
python -m crawler.dft.materialscloud.run_single 0290c725-d663-426f-b857-524aabebc244 --dataset mc3d-pbesol-v2
python -m tests.dft.materialscloud.extract_single 0290c725-d663-426f-b857-524aabebc244 --dataset mc3d-pbesol-v2
```

Preserve curated archive bulk files without normalizing:

```powershell
python -m crawler.dft.materialscloud.run_batch --dataset mc2d --download-bulk
```

Dataset names are listed in `sources/dft/materialscloud/download.py::DATASETS`.

## ⚖️ License and Citation

Materials Cloud curated data are distributed under the
[Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/).
Cite the dataset and its underlying paper:

> S. P. Huber, M. Bercx, N. Hörmann, M. Uhrin, G. Pizzi, N. Marzari, *Materials Cloud three-dimensional crystals database (MC3D)*, Materials Cloud Archive (2022), doi:10.24435/materialscloud:rw-t0

> D. Campi, N. Mounet, M. Gibertini, G. Pizzi, N. Marzari, *Expansion of the Materials Cloud 2D Database*, ACS Nano **17**, 11268-11278 (2023). doi:10.1021/acsnano.2c11510

MC3D is derived from MPDS, COD, and ICSD; the original ICSD and MPDS records are
copyrighted, so only the relaxed structures and their provenance are public.

## 🧩 Module Layout

- `sources/dft/materialscloud/download.py`: dataset catalog, OPTIMADE client, archive bulk files, resume.
- `normalizers/dft/materialscloud/mapping.yaml`: Materials Cloud field to standard field mapping.
- `normalizers/dft/materialscloud/normalize.py`: OPTIMADE and structure normalization.
- `crawler/dft/materialscloud/`: single and batch pipeline runners.
- `tests/dft/materialscloud/`: runnable limited-sample examples.
