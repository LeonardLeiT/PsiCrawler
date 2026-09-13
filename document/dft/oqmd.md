# OQMD

OQMD provides computed materials properties for inorganic compounds, with a
focus on formation energies, phase stability, structures, and composition-based
search.

- Official website: [oqmd.org](https://oqmd.org/)
- Status: not implemented.

To add OQMD, follow the five-part pattern in
[architecture.md](../architecture.md): a `sources/dft/oqmd/download.py`, a
`normalizers/dft/oqmd/{mapping.yaml,normalize.py}`, a
`crawler/dft/oqmd/{run_single.py,run_batch.py}`, a
`tests/dft/oqmd/{extract_single.py,extract_batch.py}`, and this document.
