# 🎉 Catalysis-Hub

Catalysis-Hub is an open database of DFT surface-reaction energetics maintained by the SUNCAT Center for Interface Science and Catalysis (SLAC/Stanford). Its backend is an ASE database: the `systems` table stores atomic configurations (clean slabs and adsorbates) with total energies and embedded CIFs, and the `reactions` table stores reaction and activation energies that reference those systems.

The PsiCrawler Catalysis-Hub adapter queries the `systems` table through GraphQL with cursor pagination, normalizes each system into DFT schema `3.0`, and indexes it in SQLite.

- Official website: [catalysis-hub.org](https://www.catalysis-hub.org/)
- GraphQL endpoint: `https://api-catalysis-hub.slac.stanford.edu/graphql`
- API documentation: [docs.catalysis-hub.org](https://docs.catalysis-hub.org/)
- Raw download: [sources/dft/catalysishub/download.py](../../sources/dft/catalysishub/download.py)
- Source mapping: [normalizers/dft/catalysishub/mapping.yaml](../../normalizers/dft/catalysishub/mapping.yaml)
- Batch runner: [crawler/dft/catalysishub/run_batch.py](../../crawler/dft/catalysishub/run_batch.py)
- Single runner: [crawler/dft/catalysishub/run_single.py](../../crawler/dft/catalysishub/run_single.py)

## 🚀 Access Path

The GraphQL endpoint requires a **free API key**, sent in the `X-API-Key` header. Obtain one at <https://api-catalysis-hub.slac.stanford.edu/auth/login> and set it in a local `.env`:

```text
CATALYSIS_HUB_API_KEY=replace_with_your_key
```

Each `systems` node requested by the adapter carries `id`, `uniqueId`, `energy`, `natoms`, `volume`, `Formula`, `Cifdata`, `DftCode`, `DftFunctional`, `Substrate`, `Facet`, `Adsorbate`, and timestamps. Pagination follows the Relay `pageInfo { hasNextPage endCursor }` convention with `first`/`after`.

Because the contract is crystal-centric, the primary normalized records are `systems` (structures and total energies). Reaction energetics in the `reactions` table are not part of the standard contract and are not indexed here.

## 🧬 Field Mapping

- Identity: `id` → `source_id`; `source_url` is the Catalysis-Hub home page.
- Composition: `Formula` → `formula`; elements, reduced formula, and reduced composition are derived from the parsed CIF.
- Structure: `Cifdata` is parsed with pymatgen; lattice parameters, volume, density, and atomic density are derived, and a canonical CIF is written under `data/dft/catalysishub/structure/<source_id>/`.
- Calculation: `DftCode` → `code`; `DftFunctional` → `functional`; `calculation_method` is `DFT`.
- Energetics: `energy` → `total_energy`/`energy_per_atom`.

Unmapped values (`uniqueId`, `volume`, `ctime`, `mtime`, `Substrate`, `Facet`, `Adsorbate`) are retained in `source_extra`.

## 🗂️ Storage Layout

```text
data/dft/catalysishub/
├── raw/systems/<source_id>.json
├── structure/<source_id>/<source_id>.cif
├── index.sqlite          # normalized standard records
├── logs/
└── manifests/
```

`api_version` is `catalysishub-graphql`.

## ▶️ Usage

Limited-sample batch (requires the API key):

```powershell
python -m tests.dft.catalysishub.extract_batch --max-records 5
```

Batch pipeline with paging and resume:

```powershell
python -m crawler.dft.catalysishub.run_batch --max-records 1000
python -m crawler.dft.catalysishub.run_batch
python -m crawler.dft.catalysishub.run_batch --no-resume
```

Single system (numeric `systems.id` or the base64 global id both work):

```powershell
python -m crawler.dft.catalysishub.run_single 68351
python -m crawler.dft.catalysishub.run_single U3lzdGVtOjY4MzUx
```

The API is rate limited (10 requests/minute, 500/day). Use `--max-records` and cursor paging to keep runs within the cap.

## ⚖️ License and Citation

Catalysis-Hub data are published for research use; see the site's terms. Cite:

> Winther, K.T., Hoffmann, M.J. et al. (2019) Catalysis-Hub.org, an open electronic structure database for surface reactions. *Scientific Data* **6**, 75. https://doi.org/10.1038/s41597-019-0081-y

## 🧩 Module Layout

- `sources/dft/catalysishub/download.py`: GraphQL client, key handling, cursor pagination, resume.
- `normalizers/dft/catalysishub/mapping.yaml`: system field to standard field mapping.
- `normalizers/dft/catalysishub/normalize.py`: system normalization.
- `crawler/dft/catalysishub/`: single and batch pipeline runners.
- `tests/dft/catalysishub/`: runnable limited-sample examples.
