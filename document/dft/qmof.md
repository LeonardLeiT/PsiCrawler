# 🎉 QMOF

The Quantum MOF (QMOF) Database is a public dataset of quantum-chemical properties for 20,000+ metal-organic frameworks (MOFs) and coordination polymers, derived from high-throughput periodic DFT (PBE-D3BJ) calculations, with additional HSE06 and HLE17 band gaps. It was produced by the groups of Andrew S. Rosen and collaborators.

The PsiCrawler QMOF adapter downloads the release property table and relaxed-structure archive, joins each property row with its CIF, normalizes records into DFT schema `3.0`, and indexes them in SQLite.

- Official repository: [github.com/Andrew-S-Rosen/QMOF](https://github.com/Andrew-S-Rosen/QMOF)
- Dataset paper: [Matter 4, 1578–1596 (2021)](https://doi.org/10.1016/j.matt.2021.02.015)
- Community mirror (release files): `vickie02736/QMOF_dataset` on Hugging Face
- Raw download: [sources/dft/qmof/download.py](../../sources/dft/qmof/download.py)
- Source mapping: [normalizers/dft/qmof/mapping.yaml](../../normalizers/dft/qmof/mapping.yaml)
- Batch runner: [crawler/dft/qmof/run_batch.py](../../crawler/dft/qmof/run_batch.py)
- Single runner: [crawler/dft/qmof/run_single.py](../../crawler/dft/qmof/run_single.py)

## 🚀 Access Path

The official release is distributed on figshare (DOI `10.6084/m9.figshare.13147324`). Because figshare is not reachable from every network, the adapter defaults to a community Hugging Face mirror that carries the release files verbatim:

| File | Size | Content |
|---|---|---|
| `qmof_database/qmof.csv` | ~22 MB | One row per MOF with DFT properties |
| `qmof_database/relaxed_structures.zip` | ~119 MB | Relaxed CIFs named `relaxed_structures/<qmof_id>.cif` |

Both are downloaded once. Each CSV row is joined with its CIF by `qmof_id`. The endpoint defaults to `https://huggingface.co` and can be pointed at a mirror with `HF_ENDPOINT` or `--endpoint`.

## 🧬 Field Mapping

- Identity: `qmof_id` → `source_id`; `source_url` is the Materials Project MOF Explorer.
- Composition: `info.formula` → `formula`; `info.formula_reduced`; elements and reduced composition are derived from the parsed CIF.
- Structure: the relaxed CIF is parsed with pymatgen; lattice parameters, volume, density, and atomic density are derived, and a canonical CIF is written under `data/dft/qmof/structure/<source_id>/`.
- Symmetry: `info.symmetry.spacegroup`, `...spacegroup_number`, `...spacegroup_crystal`, `...pointgroup`.
- Calculation: `inputs.pbe.theory` → `functional`; `inputs.pbe.encut` → `energy_cutoff`.
- Energetics: `outputs.pbe.energy_total` → `total_energy`/`energy_per_atom`.
- Electronic: `outputs.pbe.bandgap` → `band_gap`; `cbm`, `vbm`, `directgap` → `is_gap_direct`; `band_gap_type` is derived.
- Magnetism: `outputs.pbe.net_magmom` → `total_magnetization`.

Unmapped values (`name`, `info.source`, `info.doi`, `info.pld`, `info.lcd`, `mofid` block, `energy_vdw`, `energy_elec`, HSE06/HLE17 band gaps) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/qmof/
├── raw/qmof.csv
├── raw/relaxed_structures.zip
├── structure/<source_id>/<source_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`api_version` is `qmof-release`, `calculation_method` is `DFT`, and `functional` is `PBE-D3BJ`.

## ▶️ Usage

Limited-sample batch (downloads the assets once):

```powershell
python -m tests.dft.qmof.extract_batch --max-records 5
```

Batch pipeline:

```powershell
python -m crawler.dft.qmof.run_batch --max-records 1000
python -m crawler.dft.qmof.run_batch
```

Download the assets without normalizing:

```powershell
python -m crawler.dft.qmof.run_batch --download-only
```

Single record:

```powershell
python -m crawler.dft.qmof.run_single qmof-8a95c27
python -m tests.dft.qmof.extract_single qmof-8a95c27
```

## ⚖️ License and Citation

QMOF data are released under the Creative Commons Attribution 4.0 License (CC BY 4.0). Cite:

> Rosen, A.S., Iyer, S.M., Ray, D. et al. (2021) Machine Learning the Quantum-Chemical Properties of Metal-Organic Frameworks for Accelerated Materials Discovery. *Matter* **4**, 1578–1596. https://doi.org/10.1016/j.matt.2021.02.015

> Rosen, A.S., Fung, V., Huck, P. et al. (2022) High-Throughput Predictions of Metal-Organic Framework Electronic Properties. *Digital Discovery* **1**, 794–809.

## 🧩 Module Layout

- `sources/dft/qmof/download.py`: asset URLs, downloads, CSV/ZIP joining, resume.
- `normalizers/dft/qmof/mapping.yaml`: QMOF field to standard field mapping.
- `normalizers/dft/qmof/normalize.py`: record normalization.
- `crawler/dft/qmof/`: single and batch pipeline runners.
- `tests/dft/qmof/`: runnable limited-sample examples.
