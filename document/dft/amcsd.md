# 🎉 AMCSD

The American Mineralogist Crystal Structure Database (AMCSD) is a repository of experimental crystal structures of minerals and related inorganic phases, published in the *American Mineralogist*, the *Canadian Mineralogist*, the *European Journal of Mineralogy* and other peer-reviewed journals. It is maintained by the RRUFF project (University of Arizona) and served through the RRUFF platform.

Unlike the other DFT sources, AMCSD is an **experimental** structure database. The standard DFT contract is reused unchanged, but every calculation-dependent field is left `null`, `calculation_method` is `experimental`, and `theoretical` is `false`.

- Official website: [rruff.net/amcsd](https://www.rruff.net/amcsd/)
- Bulk download: `https://www.rruff.net/AMS/zipped_files/{amc,cif,dif}.zip`
- Raw download: [sources/dft/amcsd/download.py](../../sources/dft/amcsd/download.py)
- Source mapping: [normalizers/dft/amcsd/mapping.yaml](../../normalizers/dft/amcsd/mapping.yaml)
- Batch runner: [crawler/dft/amcsd/run_batch.py](../../crawler/dft/amcsd/run_batch.py)
- Single runner: [crawler/dft/amcsd/run_single.py](../../crawler/dft/amcsd/run_single.py)

## 🚀 Access Path

The adapter uses the official bulk archives only. It never crawls the site's search pages.

RRUFF publishes three Apache directory-index ZIP archives that are downloaded verbatim and preserved under `data/dft/amcsd/raw`:

| Archive | Local path | Content |
|---|---|---|
| `cif.zip` | `raw/cif/cif.zip` | Minimal CIF records: cell, symmetry, atomic coordinates |
| `amc.zip` | `raw/amc/amc.zip` | Native AMC text: mineral name, authors, journal, locality, experimental conditions |
| `dif.zip` | `raw/dif/dif.zip` | Tabular diffraction records |

Members are aligned across archives by the trailing AMCSD identifier in their filename, for example `Actinolite__0001982.cif`. The CIF archive is the superset: a small number of records have a CIF but no AMC/DIF, and a few identifiers carry both `Name__ID.cif` and `Name__original__ID.cif` (the adapter prefers the minimal record and keeps the original inside the raw archive).

The current snapshot holds roughly **21,500–21,700 records** (21,720 CIF members, 21,503 AMC members, 21,502 DIF members, 21,567 unique identifiers). Because AMCSD exposes no public per-record API, `run_single` reads the identifier from these bulk archives, downloading them on demand if missing.

## 🧬 Field Mapping

The CIF is authoritative for geometry and symmetry; the AMC text supplements metadata.

- Identity: AMCSD identifier → `source_id` (zero-padded seven digits), `source_url` → the ODR record page `https://www.rruff.net/odr/amcsd/<id>`.
- Composition: `_chemical_formula_sum` → `formula`; reduced and anonymous formulas and reduced composition are derived with pymatgen from the parsed structure.
- Structure: the minimal CIF is parsed with pymatgen; lattice parameters, volume, density and atomic density are derived, and the original minimal CIF is written verbatim as the canonical artifact under `data/dft/amcsd/structure/`. Because mineral structures routinely carry partial occupancies, the `structure` object is parsed leniently (`check_occu=False`); for roughly 5% of records a site's occupancies sum to more than one, so `Structure.from_dict(record["structure"])` may reject it. Consumers should prefer the canonical `structure_path` CIF and parse it with `CifParser(..., check_occu=False)` when full fidelity is required.
- Symmetry: the declared CIF Hermann-Mauguin symbol → `spacegroup_number`, `spacegroup_symbol`, `crystal_system`, `point_group`; if the symbol is missing or unrecognized, symmetry is re-derived from the structure with spglib.
- Classification: `calculation_method` = `experimental`, `theoretical` = `false`, `functional` = `null`.

Because the contract's `temperature`, `pressure`, `license` and `citation` columns are reserved (`const: null`), the following values are retained in `source_extra` instead:

- Experimental conditions: `temperature`, `pressure`, `radiation_source`, `wavelength`.
- Provenance: `mineral_name`, `authors`, `journal`, `title`, `locality`, `amc_cell`, `amc_database_code`, `cif_*` metadata (`cif_authors`, `cif_journal`, `cif_cell_volume`, `cif_density`, `cif_compound_source`, `cif_space_group_name`, …).
- Citations: `amcsd_citation` (database citation) and `dataset_citation` (the original publication).
- `api_version` is `amcsd-bulk-2026.06.29`.

Records whose CIF cannot be parsed (a small number of malformed or occupancy-heavy files) are still indexed with their metadata and `download_status` = `partial`, leaving `structure`/`structure_path` empty.

## 🗂️ Storage Layout

```text
data/dft/amcsd/
├── raw/
│   ├── amc/amc.zip
│   ├── cif/cif.zip
│   └── dif/dif.zip
├── structure/<amcsd_id>/<amcsd_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`raw_path` points at the CIF archive, `source_documents` records the aligned members and archive paths, and `property_paths` maps each archive to its local file. Normalized records live only in `index.sqlite`.

## ▶️ Usage

Limited-sample batch (recommended first run):

```powershell
python -m tests.dft.amcsd.extract_batch --max-records 5
```

Batch pipeline with manifest and resume:

```powershell
python -m crawler.dft.amcsd.run_batch --max-records 1000
python -m crawler.dft.amcsd.run_batch
python -m crawler.dft.amcsd.run_batch --no-resume
```

Download the archives without normalizing:

```powershell
python -m crawler.dft.amcsd.run_batch --download-only
```

Single record (extracted from the bulk archives):

```powershell
python -m crawler.dft.amcsd.run_single 0000130
python -m tests.dft.amcsd.extract_single 130
```

## ⚖️ License and Citation

AMCSD data are published for research use; the data are copyrighted by the RRUFF project and no explicit open license is stated. Cite both the database and the original publication of each structure:

> Downs, R.T. and Hall-Wallace, M. (2003) The American Mineralogist Crystal Structure Database. *American Mineralogist* **88**, 247–250.

> Lafuente, B., Downs, R. T., Yang, H., & Stone, N. (2015) The power of databases: the RRUFF project. *Highlights in Mineralogical Crystallography*, 1–30.

The AMCSD citation is stored on every record in `source_extra.amcsd_citation`, and the per-record publication citation in `source_extra.dataset_citation`.

### Compliance

Only the three official bulk ZIP files linked from the RRUFF "Download Files" page are fetched. The site's `robots.txt` disallows general crawling, so no search or record pages are crawled; per-record downloads are fulfilled by extracting from the already-downloaded archives.

## 🧩 Module Layout

- `sources/dft/amcsd/download.py`: archive URLs, ZIP download, aligned member access, resume.
- `normalizers/dft/amcsd/mapping.yaml`: AMCSD field to standard field mapping.
- `normalizers/dft/amcsd/normalize.py`: CIF/AMC parsing and standard-record normalization.
- `crawler/dft/amcsd/`: single and batch pipeline runners.
- `tests/dft/amcsd/`: runnable limited-sample examples.
