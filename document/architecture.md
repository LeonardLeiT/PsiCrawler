# PsiCrawler Architecture

PsiCrawler batch-collects public research data, normalizes it to a shared
standard contract, and indexes the result for retrieval. The codebase is split
by responsibility so that downloads, normalization, orchestration, and shared
utilities never leak into each other.

## Directory layout

```
PsiCrawler/
├─ README.md  README_zh.md          # entry points, link into document/
├─ requirements.txt  .env.example
│
├─ document/                        # all documentation
│  ├─ architecture.md
│  ├─ dft/{overview,mp,aflow,oqmd}.md
│  └─ papers/{overview,arxiv,crossref,openalex}.md
│
├─ sources/                         # raw download only -> data/<domain>/<source>/raw
│  ├─ dft/mp/download.py
│  ├─ dft/aflow/download.py
│  ├─ dft/alexandria/download.py
│  └─ papers/{arxiv,crossref,openalex}/download.py
│
├─ normalizers/                     # standard contract + per-source normalization
│  ├─ dft/standard.yaml
│  ├─ dft/mp/{mapping.yaml,normalize.py}
│  ├─ dft/aflow/{mapping.yaml,normalize.py}
│  ├─ dft/alexandria/{mapping.yaml,normalize.py}
│  └─ papers/<source>/{standard.yaml,mapping.yaml,normalize.py}
│
├─ crawler/                         # pipeline: download + normalize + index
│  ├─ dft/{mp,aflow,alexandria}/{run_single.py,run_batch.py}
│  └─ papers/{arxiv,crossref,openalex}/{run_single.py,run_batch.py}
│
├─ core/                            # shared, source-agnostic utilities
│  ├─ logging.py  manifest.py  storage.py
│
├─ tests/                           # runnable download examples
│  └─ dft/{mp,aflow,alexandria}/{extract_single.py,extract_batch.py}
│
└─ data/                            # runtime output (gitignored)
   └─ <domain>/<source>/{raw/<id>/…, index.sqlite}
```

## Responsibilities

| Layer | Does | Never does |
|---|---|---|
| `sources/` | Access upstream APIs, download raw files, write `data/<domain>/<source>/raw`, return raw documents and paths | Know standard fields, touch SQLite, normalize |
| `normalizers/` | Define the standard contract (`standard.yaml`) and map each source's raw documents into it | Make network requests, write files, provide a CLI |
| `crawler/` | Select IDs, call `sources` to download, call `normalizers` to map, write `core.storage`, record manifests/logs | Contain inline download or mapping implementations |
| `core/` | Generic utilities: logging, run manifests, unified SQLite storage | Contain any source-specific or standard-field semantics |
| `tests/` | Runnable download examples per source | Hold unit tests |
| `document/` | All prose documentation | Hold code |

There is intentionally **no shared normalization engine**. Each database has its
own `mapping.yaml` and `normalize.py`. For DFT, the standard field contract is
shared at `normalizers/dft/standard.yaml`; paper sources vary more, so each has
its own `normalizers/papers/<source>/standard.yaml`.

## Data flow

```
crawler CLI
  -> sources.download      (fetch upstream, write data/<domain>/<source>/raw)
  -> normalizers.normalize (raw documents -> standard record, all fields present)
  -> core.storage.save     (insert/replace in data/<domain>/<source>/index.sqlite, compute content_hash)
  -> core.manifest/logging (run manifest and logs)
```

Resume decisions do not live in `core`: each source exposes its own
`completed(...)` check, and the crawler reads the index and calls it.

Raw documents are preserved verbatim under `data/<domain>/<source>/raw`. Only
normalized records reach SQLite; there is no normalized JSON copy on disk. The
`raw_path` field points back to the original document, and `content_hash` is the
SHA-256 of that document.

## Commands

```powershell
# One Materials Project record
python -m crawler.dft.mp.run_single mp-149

# Batch Materials Project
python -m crawler.dft.mp.run_batch --mp-ids mp-149,mp-13,mp-22526 --sleep 1
python -m crawler.dft.mp.run_batch --chemsys Si-O --max 50

# One AFLOW record (downloads files allowed by a profile)
python -m crawler.dft.aflow.run_single --profile core

# Batch AFLOW via AFLUX
python -m crawler.dft.aflow.run_batch --species Li --max 10

# Limited-sample Alexandria bulk ingestion
python -m crawler.dft.alexandria.run_batch --dataset pbe-3d --max-files 1 --max-records 100

# One Alexandria record through OPTIMADE
python -m crawler.dft.alexandria.run_single agm001010489 --dataset pbesol

# Run the download examples
python -m tests.dft.mp.extract_single mp-149
python -m tests.dft.aflow.extract_batch --species Li --max 5
python -m tests.dft.alexandria.extract_batch --dataset pbe-3d --max-files 1 --max-records 100
```

## Storage contract

`core/storage.py` is write-only and source-agnostic. It exposes a single
function; callers pass the standard column list (read from
`normalizers/<domain>/standard.yaml`) and any searchable index fields:

- `save(db_path, record, raw, *, columns, index_fields)` — lazily creates or
  evolves the table, computes `content_hash`, and upserts one record. The
  connection uses WAL and a busy timeout and retries on lock contention.

Reading records, completeness policy, and resume logic belong to each source
(for example `sources.dft.mp.download.completed`).

## Extending

Adding a database means adding five pieces and one document:

1. `sources/<domain>/<source>/download.py`
2. `normalizers/<domain>/<source>/{mapping.yaml,normalize.py}`
3. `crawler/<domain>/<source>/{run_single.py,run_batch.py}`
4. `tests/<domain>/<source>/{extract_single.py,extract_batch.py}`
5. `document/<domain>/<source>.md`

## Compliance

PsiCrawler is intended only for public web pages, public APIs, and openly
accessible data. Users must follow each target's terms of service, copyright
policy, data license, citation requirements, robots.txt rules, rate limits, and
applicable laws.
