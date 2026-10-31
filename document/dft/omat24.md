# 🎉 OMat24

OMat24 (Open Materials 2024) is Meta FAIR's open inorganic materials dataset of DFT single-point and relaxation calculations, released alongside the UMA models. It covers the periodic table with PBE/PBE+U total energies, forces, and stresses, and is intended for training machine-learned interatomic potentials.

The PsiCrawler OMat24 adapter downloads one subdataset archive at a time, extracts its ASE LMDB database, streams rows, normalizes them into DFT schema `3.0`, and indexes them in SQLite.

- Official dataset: [huggingface.co/datasets/facebook/OMAT24](https://huggingface.co/datasets/facebook/OMAT24)
- Toolkit: [github.com/facebookresearch/fairchem](https://github.com/facebookresearch/fairchem)
- Paper: [arXiv:2410.12771](https://arxiv.org/abs/2410.12771)
- Raw download: [sources/dft/omat24/download.py](../../sources/dft/omat24/download.py)
- Source mapping: [normalizers/dft/omat24/mapping.yaml](../../normalizers/dft/omat24/mapping.yaml)
- Batch runner: [crawler/dft/omat24/run_batch.py](../../crawler/dft/omat24/run_batch.py)
- Single runner: [crawler/dft/omat24/run_single.py](../../crawler/dft/omat24/run_single.py)

## 🚀 Access Path

OMat24 is distributed as per-subdataset `tar.gz` archives served from `dl.fbaipublicfiles.com`; the Hugging Face repository is **not gated** and the data are CC BY 4.0. Each archive extracts to a directory containing `data.aselmdb`, an ASE LMDB database (readable with the `ase-db-backends` package; no `fairchem-core`/torch needed).

The adapter offers these subdatasets (`sources/dft/omat24/download.py::SUBSETS`):

| Subset | Rows | Approx. size |
|---|---|---|
| `val-rattled-1000-subsampled` (default) | 39,785 | 80 MB |
| `val-*` (11 validation subdatasets) | up to 220k each | 10–200 MB each |
| `1m` | 1,009,850 | 2.3 GB |
| `train-*` (11 training subdatasets) | up to 21M each | multi-GB each |
| `salex-train` / `salex-val` | 10.4M / 553k | multi-GB |

Full training is ~100.8M structures; start with `val-rattled-1000-subsampled` or `1m`.

Each row is an ASE `Atoms` object with `energy` (eV), `forces` (eV/Å), `stress` (eV/Å³, ASE sign convention), and a `data` block with `sid`, `calc_id`, `task_type`, `prototype_label`, and MP2020-corrected energies.

## 🧬 Field Mapping

- Identity: `data.sid` → `source_id` (a descriptive identifier such as `agm001014143_..._rattled-1000-subsampled_wj7ayw`); `source_url` is the Hugging Face dataset page.
- Composition: the ASE chemical formula → `formula`; elements, reduced formula, anonymous formula, and reduced composition are derived with pymatgen.
- Structure: the ASE `Atoms` object is converted with `AseAtomsAdaptor`; lattice parameters, volume, density, and atomic density are derived, and a canonical CIF is written under `data/dft/omat24/structure/<source_id>/`.
- Symmetry: the space-group number is parsed from the `_spgNNN_` token in `sid`; symbol, crystal system, and point group are resolved from pymatgen.
- Calculation: `calculation_method` is `DFT`; `functional` is `PBE/PBE+U`.
- Energetics: `row.energy` → `total_energy`/`energy_per_atom`.

Unmapped values (`forces`, `stress`, `sid`, `calc_id`, `task_type`, `subset`, `row_id`, `prototype_label`, `prototype_error`, `energy_corrected_mp2020`, `energy_correction_uncertainty_mp2020`, `energy_adjustments_mp2020`, `correction_warnings`, `parent_id`, `parent_prototype_label`) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/omat24/
├── raw/<subset>.tar.gz
├── raw/<subset>/<subdataset>/data.aselmdb
├── structure/<source_id>/<source_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`api_version` is `omat24-241220` (validation), `omat24-241018` (train/sAlex), or `omat24-251210` (1M subsplit).

## ▶️ Usage

Limited-sample batch (downloads the 80 MB validation subset):

```powershell
python -m tests.dft.omat24.extract_batch --subset val-rattled-1000-subsampled --max-records 5
```

Batch pipeline:

```powershell
python -m crawler.dft.omat24.run_batch --subset val-rattled-1000-subsampled --max-records 1000
python -m crawler.dft.omat24.run_batch --subset 1m
python -m crawler.dft.omat24.run_batch --subset val-rattled-relax --no-resume
```

Download and extract without normalizing:

```powershell
python -m crawler.dft.omat24.run_batch --subset 1m --download-only
```

Single row (by `sid` or integer row id):

```powershell
python -m crawler.dft.omat24.run_single <sid_or_row_id> --subset val-rattled-1000-subsampled
```

## ⚖️ License and Citation

OMat24 is licensed under the Creative Commons Attribution 4.0 License (CC BY 4.0). Cite:

> Barroso-Luque, L., Shuaibi, M., Fu, X., Wood, B. M., Dzamba, M., Gao, M., Rizvi, A., Zitnick, C. L., Ulissi, Z. W. (2024) Open Materials 2024 (OMat24) Inorganic Materials Dataset and Models. arXiv:2410.12771.

## ⚠️ Energy caveat

OMat24 energies use Meta's PBE/PBE+U reference scheme and are **not** directly comparable to Materials Project energies: pseudopotentials differ, magnetic ground states may differ, and MP2020 corrections are applied differently. The corrected energy is retained as `source_extra.energy_corrected_mp2020`.

## 🧩 Module Layout

- `sources/dft/omat24/download.py`: subdataset catalog, archive download/extraction, ASE LMDB streaming, resume.
- `normalizers/dft/omat24/mapping.yaml`: OMat24 field to standard field mapping.
- `normalizers/dft/omat24/normalize.py`: row normalization and ASE→pymatgen conversion.
- `crawler/dft/omat24/`: single and batch pipeline runners.
- `tests/dft/omat24/`: runnable limited-sample examples.
