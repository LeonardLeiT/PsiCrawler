# 🎉 PsiCrawler

<p align="center">
  <a href="./README.md">English</a> |
  <a href="./README_zh.md">简体中文</a>
</p>

## 🚀 Project Overview

PsiCrawler is a research data crawling, normalization, storage, and retrieval project. It is designed to batch collect publicly accessible DFT calculation databases, paper databases, scientific datasets, and related experimental records from the open web.

Each database and paper source is implemented independently because different sources provide different APIs, identifiers, fields, access rules, pagination methods, and storage formats. Shared schemas are used to normalize comparable fields across sources.

## 🔥 Latest Updates

- 2026-09-10 Added a schema-driven Materials Project adapter with source-specific API access, 26 material routes, complete Summary capture, route-specific queries, CIF export, normalized records, and SQLite indexing.
- Added single-record and batch crawling entrypoints for Materials Project.
- Downloaded data is stored locally under `data/` and excluded from Git.

## 🌟 Quick Start

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Configure the Materials Project API key:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `MP_API_KEY`, then run a single-material download:

```powershell
python -m crawler.dft.mp.run_single mp-149
```

Run a batch download:

```powershell
python -m crawler.dft.mp.run_batch --mp-ids mp-149,mp-13,mp-22526 --sleep 1
```

The `.env` file and downloaded data are ignored by Git and must not be committed.

## 📚 Data Sources

### 🧪 DFT Databases

DFT sources are implemented separately because each database has different APIs, material identifiers, document models, fields, pagination rules, and data licenses.

Overview: [DFT Sources](./sources/dft/README.md)

The unified DFT field definitions, categories, units, enum values, and null-value conventions are documented in [DFT Databases standard fields](./schemas/dft/README.md).

#### Materials Project <img src="./Figure/mp_logo.png" alt="logo" style="height:1.5em;">

Materials Project is a large computational materials database for crystal structures, thermodynamic properties, electronic structure, magnetic and mechanical properties, synthesis information, provenance, and related materials metadata.

Official website: [materialsproject.org](https://materialsproject.org/)

Local Source: [Materials Project README](./sources/dft/mp/README.md)

#### AFLOW
<img src="./Figure/aflow_logo.png" alt="logo" style="height:3em;">

AFLOW provides high-throughput computational materials data, including structural, thermodynamic, electronic, magnetic, elastic, and related calculation outputs.

Official website: [aflow.org](https://aflow.org/)

Local Source: [AFLOW README](./sources/dft/aflow/README.md)

#### OQMD

OQMD provides computed materials properties for inorganic compounds, with a focus on formation energies, phase stability, structures, and composition-based search.

Official website: [oqmd.org](https://oqmd.org/)

Local Source: [OQMD README](./sources/dft/oqmd/README.md)

---

### 📝 Paper Databases

Paper sources are also implemented separately because each service exposes different metadata, identifiers, citation relationships, full-text links, access rules, and rate limits.

Overview: [Paper Sources](./sources/papers/README.md)

#### arXiv

arXiv provides open-access preprint metadata and links for papers across physics, mathematics, computer science, quantitative biology, and related fields.

Official website: [arxiv.org](https://arxiv.org/)

Local Source: [arXiv README](./sources/papers/arxiv/README.md)

#### Crossref

Crossref provides DOI-centered scholarly metadata, including titles, authors, publishers, journals, publication dates, references, and related identifiers.

Official website: [crossref.org](https://www.crossref.org/)

Local Source: [Crossref README](./sources/papers/crossref/README.md)

#### OpenAlex

OpenAlex provides open scholarly metadata for works, authors, institutions, venues, concepts, citations, and open-access links.

Official website: [openalex.org](https://openalex.org/)

Local Source: [OpenAlex README](./sources/papers/openalex/README.md)

## ⚖️ Compliance

PsiCrawler is intended only for public web pages, public APIs, and openly accessible data resources. Users should follow the target site's terms of service, copyright policy, data license, citation requirements, robots.txt rules, rate limits, and applicable laws.







