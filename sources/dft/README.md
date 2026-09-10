# 🧪 DFT Data Sources

This directory contains source-specific adapters for computational materials databases.

Each database is implemented independently because source APIs, identifiers, document models, pagination rules, available properties, and licensing conditions differ.

## Sources

- [Materials Project](./mp/README.md) · computed structures and materials properties
- [AFLOW](./aflow/README.md) · high-throughput materials calculations
- [OQMD](./oqmd/README.md) · thermodynamic and phase-stability data

## Shared Schema

The executable unified schema is defined in [schemas/dft/standard.yaml](../../schemas/dft/standard.yaml). Source mappings are stored beside it, for example [schemas/dft/mp.yaml](../../schemas/dft/mp.yaml).

A source adapter may expose additional source-specific fields without forcing them into the shared comparison layer. Missing comparable fields are represented as `null` after normalization.
