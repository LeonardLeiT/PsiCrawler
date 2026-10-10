# 🎉 2DMatPedia

2DMatPedia is an open computational database of two-dimensional materials from top-down exfoliation and bottom-up chemical substitution, produced by the Centre for Advanced 2D Materials (National University of Singapore). Structures and properties were computed with VASP (PBE, with vdW-optB88 for exfoliation).

The PsiCrawler 2DMatPedia adapter downloads the whole database as one JSON Lines file, streams its entries, normalizes them into DFT schema `3.0`, and indexes them in SQLite.

- Official website: [2dmatpedia.org](https://www.2dmatpedia.org/)
- Bulk download: `http://www.2dmatpedia.org/static/db.json.gz`
- Raw download: [sources/dft/twodmatpedia/download.py](../../sources/dft/twodmatpedia/download.py)
- Source mapping: [normalizers/dft/twodmatpedia/mapping.yaml](../../normalizers/dft/twodmatpedia/mapping.yaml)
- Batch runner: [crawler/dft/twodmatpedia/run_batch.py](../../crawler/dft/twodmatpedia/run_batch.py)
- Single runner: [crawler/dft/twodmatpedia/run_single.py](../../crawler/dft/twodmatpedia/run_single.py)

## 🚀 Access Path

2DMatPedia publishes its complete database as a single file at `/static/db.json.gz`. Despite the `.gz` suffix and the transport `Content-Encoding: gzip`, the decoded payload is **JSON Lines**: one JSON object per line, one line per material. The adapter downloads the file once (removing the transport encoding), stores it verbatim under `data/dft/2dmatpedia/raw/db.json`, and streams its lines.

The current snapshot holds **6,351 records**. There is no public per-record API, so `run_single` reads the identifier from the bulk file (downloading it on first use).

## 🧬 Field Mapping

- Identity: `material_id` → `source_id` (for example `2dm-1`); `source_url` is the database home page.
- Composition: `formula_pretty` → `formula`; `formula_anonymous`; `elements`; `chemsys` → `chemical_system`; reduced formula and reduced composition are derived with pymatgen.
- Structure: the inline pymatgen `structure`; lattice parameters, volume, density, and atomic density are derived, and a canonical CIF is written verbatim under `data/dft/2dmatpedia/structure/<source_id>/`.
- Symmetry: `sg_number`, `sg_symbol`, and `spacegroup.crystal_system`/`point_group` → `spacegroup_number`, `spacegroup_symbol`, `crystal_system`, `point_group`.
- Energetics: `thermo.energy` → `total_energy`/`energy_per_atom`; `decomposition_energy` → `energy_above_hull`.
- Electronic: `bandgap` → `band_gap`; `bandstructure.is_metal`/`is_gap_direct`/`cbm`/`vbm`; `band_gap_type` is derived from directness.
- Magnetism: `total_magnetization` → `total_magnetization`, with `is_magnetic` derived.

Unmapped values (`exfoliation_energy_per_atom`, `energy_vdw_per_atom`, `discovery_process`, `relative_id`, the parent MP `source_id`, `calc_settings`, `thermo`, `bandstructure`, `magnetism`) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/2dmatpedia/
├── raw/db.json
├── structure/<source_id>/<source_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`api_version` is `2dmatpedia-2019`, `calculation_method` is `DFT`, and `functional` is `PBE`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.twodmatpedia.extract_batch --max-records 5
```

Batch pipeline with manifest and resume:

```powershell
python -m crawler.dft.twodmatpedia.run_batch --max-records 1000
python -m crawler.dft.twodmatpedia.run_batch
python -m crawler.dft.twodmatpedia.run_batch --no-resume
```

Download the raw database without normalizing:

```powershell
python -m crawler.dft.twodmatpedia.run_batch --download-only
```

Single record:

```powershell
python -m crawler.dft.twodmatpedia.run_single 2dm-1
python -m tests.dft.twodmatpedia.extract_single 2dm-1
```

## ⚖️ License and Citation

2DMatPedia is an open database; the website does not state an explicit license. Cite:

> Zhou, J., Shen, L., Costa, M.D. et al. (2019) 2DMatPedia, an open computational database of two-dimensional materials from top-down and bottom-up approaches. *Scientific Data* **6**, 86. https://doi.org/10.1038/s41597-019-0097-3

A few records have `material_id` gaps: the file contains 6,351 lines but the identifiers are not fully contiguous.

## 🧩 Module Layout

- `sources/dft/twodmatpedia/download.py`: bulk URL, gzip handling, JSON Lines streaming, resume.
- `normalizers/dft/twodmatpedia/mapping.yaml`: 2DMatPedia field to standard field mapping.
- `normalizers/dft/twodmatpedia/normalize.py`: entry normalization.
- `crawler/dft/twodmatpedia/`: single and batch pipeline runners.
- `tests/dft/twodmatpedia/`: runnable limited-sample examples.
