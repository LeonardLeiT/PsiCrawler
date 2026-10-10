# 🎉 MatPES

MatPES (Materials Potential Energy Surface) is an open potential-energy-surface dataset with near-complete coverage of the periodic table, produced by Materialyze.AI and the Materials Project. It contains static DFT calculations from 300 K molecular-dynamics structures, computed with both PBE and the r2SCAN meta-GGA, and is designed to train foundation interatomic potentials.

The PsiCrawler MatPES adapter streams the dataset's JSON Lines files from Hugging Face, normalizes each entry into DFT schema `3.0`, and indexes it in SQLite.

- Official website: [matpes.ai](https://matpes.ai/)
- Dataset repository: [github.com/materialyzeai/matpes](https://github.com/materialyzeai/matpes)
- Hugging Face dataset: `materialyze/matpes`
- Raw download: [sources/dft/matpes/download.py](../../sources/dft/matpes/download.py)
- Source mapping: [normalizers/dft/matpes/mapping.yaml](../../normalizers/dft/matpes/mapping.yaml)
- Batch runner: [crawler/dft/matpes/run_batch.py](../../crawler/dft/matpes/run_batch.py)
- Single runner: [crawler/dft/matpes/run_single.py](../../crawler/dft/matpes/run_single.py)

## 🚀 Access Path

MatPES publishes its releases as JSON Lines on Hugging Face:

| Function | File | Size |
|---|---|---|
| r2SCAN | `MatPES-R2SCAN-2025.2.jsonl` | ~1.9 GB |
| PBE | `MatPES-PBE-2025.2.jsonl` | ~1.9 GB |

Each line is one static DFT calculation with an inline pymatgen `structure`, total energy, forces, stress, band gap, and magnetic moments. The files are multi-gigabyte, so entries are **streamed over HTTP** line by line; a limited run transfers only the lines it consumes.

The endpoint defaults to `https://huggingface.co` and can be pointed at a mirror with the `HF_ENDPOINT` environment variable or `--endpoint`:

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

## 🧬 Field Mapping

- Identity: `matpes_id` → `source_id`.
- Composition: `formula_pretty` → `formula`; `formula_anonymous`; `elements`; `chemsys` → `chemical_system`; reduced formula and reduced composition are derived with pymatgen.
- Structure: the inline pymatgen `structure`; lattice parameters, volume, density, and atomic density are derived, and a canonical CIF is written under `data/dft/matpes/structure/<source_id>/`.
- Symmetry: `symmetry.number` → `spacegroup_number`; `symbol`, `crystal_system`, `point_group`.
- Energetics: `energy` → `total_energy`/`energy_per_atom`; `formation_energy_per_atom`.
- Electronic: `bandgap` → `band_gap`; `is_metal` is derived (`bandgap <= 0`). MatPES does not mark directness, so `band_gap_type` is `unknown` for gapped entries.
- Magnetism: the structure's site `magmom` values are summed into `total_magnetization` and retained in `magnetic_moments`.

Unmapped values (`forces`, `stress`, `abs_forces`, `cohesive_energy_per_atom`, `bader_charges`, `bader_magmoms`, `provenance`, `builder_meta`) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/matpes/
├── structure/<source_id>/<source_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

MatPES is streamed rather than stored whole, so `raw_path` points at the remote `resolve` URL and `source_documents` records the dataset, URL, and line index. `api_version` is `matpes-2025.2`, `calculation_method` is `DFT`, and `functional` is the entry's `r2SCAN` or `PBE`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.matpes.extract_batch --function r2scan --max-records 5
```

Batch pipeline (sample first; omit `--max-records` for the full file):

```powershell
python -m crawler.dft.matpes.run_batch --function r2scan --max-records 1000
python -m crawler.dft.matpes.run_batch --function pbe
python -m crawler.dft.matpes.run_batch --function r2scan --no-resume
```

Single record (scan bound with `--max-scan`):

```powershell
python -m crawler.dft.matpes.run_single matpes-20240214_999485_2 --max-scan 1000
python -m tests.dft.matpes.extract_single matpes-20240214_999485_2 --max-scan 1000
```

## ⚖️ License and Citation

The MatPES toolkit is released under the BSD 3-Clause License; see the dataset page for the data license. Cite:

> Goodall, R. et al. MatPES: a foundational potential energy surface dataset for materials. (2025)

## 🧩 Module Layout

- `sources/dft/matpes/download.py`: resolve URLs, endpoint configuration, JSON Lines streaming, resume.
- `normalizers/dft/matpes/mapping.yaml`: MatPES field to standard field mapping.
- `normalizers/dft/matpes/normalize.py`: entry normalization.
- `crawler/dft/matpes/`: single and batch pipeline runners.
- `tests/dft/matpes/`: runnable limited-sample examples.
