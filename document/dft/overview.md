# DFT Data Sources

Each database is implemented independently because upstream APIs, identifiers,
document models, pagination rules, available properties, and licensing
conditions differ.

## Sources

- [Materials Project](./mp.md) · computed structures and materials properties
- [AFLOW](./aflow.md) · high-throughput materials calculations
- [Alexandria](./alexandria.md) · DFT-relaxed crystals, convex hulls, phonons, PBE/PBEsol/SCAN
- [Materials Cloud](./materialscloud.md) · curated MC3D and MC2D crystals via OPTIMADE
- [OQMD](./oqmd.md) · thermodynamic and phase-stability data (not implemented)

## Standard contract

The shared field contract is [`normalizers/dft/standard.yaml`](../../normalizers/dft/standard.yaml).
Every database maps its own raw documents into that contract:

- Materials Project: [`normalizers/dft/mp/`](../../normalizers/dft/mp)
- AFLOW: [`normalizers/dft/aflow/`](../../normalizers/dft/aflow)
- Alexandria: [`normalizers/dft/alexandria/`](../../normalizers/dft/alexandria)
- Materials Cloud: [`normalizers/dft/materialscloud/`](../../normalizers/dft/materialscloud)

There is no shared normalization engine: only `standard.yaml` is common to all
databases, while each source keeps its own `mapping.yaml` and `normalize.py`.
Missing comparable fields are represented as `null`. The number of standard
fields is a contract size, not a claim of upstream coverage.

## Pipeline

- Downloads: [`sources/dft/`](../../sources/dft) write raw files under `data/dft/<source>/raw`.
- Normalization: [`normalizers/dft/`](../../normalizers/dft) maps raw documents to standard records.
- Orchestration: [`crawler/dft/`](../../crawler/dft) runs download → normalize → index.

See [architecture.md](../architecture.md) for the full data flow.
