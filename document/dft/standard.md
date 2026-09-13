# DFT Standard Field Contract

The DFT standard contract defines the shared field set that every source adapter normalizes into. It is defined in [`normalizers/dft/standard.yaml`](../../normalizers/dft/standard.yaml) and is the only artifact common to all database adapters; each source keeps its own mapping and normalizer.

- **Schema name:** `dft`
- **Schema version:** `3.0`
- **Total fields:** 115
- **Active fields:** 110
- **Reserved fields:** 5
- **Fields with a unit:** 53
- **Field groups:** 12

## Conventions

- Field order follows the declaration order in `standard.yaml`; the index below is continuous from 1 to 115.
- A field that is unavailable from a source is represented as `null`.
- Reserved fields are declared in the contract but must remain `null`: they have no producer yet, and a value may only be populated once a source and its semantics are defined.

## Field groups

| Group | Fields |
| --- | ---: |
| `source_and_record_metadata` | 4 |
| `composition_and_identity` | 5 |
| `structure_and_crystallography` | 15 |
| `calculation_settings` | 6 |
| `energy_and_stability` | 9 |
| `electronic_structure` | 9 |
| `magnetism` | 5 |
| `elastic_and_mechanical_properties` | 10 |
| `dielectric_piezoelectric_and_surface_properties` | 10 |
| `phonon_and_thermal_properties` | 4 |
| `provenance_and_artifacts` | 13 |
| `extended_and_source_fields` | 25 |

## source_and_record_metadata

Identifies the upstream provider, the record it assigned, and the identifier that was originally requested. These fields anchor every record to a concrete source entry.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 1 | `source` | string | — | Name of the upstream database or provider. |
| 2 | `requested_id` | string | — | Identifier requested by the user or crawler before source lookup. |
| 3 | `source_id` | string | — | Stable identifier assigned to this record by the upstream source. |
| 4 | `source_url` | string | — | Canonical URL of the upstream record or source page. |

## composition_and_identity

Chemical identity of the material: formula, reduced formula, chemical system, unique elements, and the number of distinct elements.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 5 | `formula` | string | — | Chemical formula of the material in the source representation. |
| 6 | `formula_reduced` | string | — | Reduced chemical formula normalized to the smallest whole-number ratio. |
| 7 | `chemical_system` | string | — | Unordered chemical system, usually represented as element symbols joined by hyphens. |
| 8 | `elements` | array | — | Unique chemical elements present in the material. |
| 9 | `element_count` | integer | 1 | Number of distinct chemical elements in the composition. |

## structure_and_crystallography

Parsed crystal structure and its geometry: lattice parameters, cell volume, density, atom count, crystal system, space group, and point group. The canonical structure artifact is a CIF in data/dft/<source>/structure/<source_id>/<source_id>.cif.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 10 | `structure` | object | — | Parsed crystal structure, including lattice and site information, when available. |
| 11 | `structure_path` | string | — | Local path to the canonical CIF structure artifact stored under data/dft/<source>/structure/<source_id>/<source_id>.cif. |
| 12 | `lattice_a` | number | Angstrom | Length of the first lattice vector. |
| 13 | `lattice_b` | number | Angstrom | Length of the second lattice vector. |
| 14 | `lattice_c` | number | Angstrom | Length of the third lattice vector. |
| 15 | `angle_alpha` | number | degree | Angle between the second and third lattice vectors. |
| 16 | `angle_beta` | number | degree | Angle between the first and third lattice vectors. |
| 17 | `angle_gamma` | number | degree | Angle between the first and second lattice vectors. |
| 18 | `volume` | number | Angstrom^3 | Volume of the unit cell. |
| 19 | `density` | number | g/cm^3 | Mass density calculated or reported for the material. |
| 20 | `atom_count` | integer | 1 | Total number of atoms in the represented structure or record. |
| 21 | `crystal_system` | string | — | Crystal-system classification, such as cubic or triclinic. |
| 22 | `spacegroup_number` | integer | 1 | International space-group number of the structure. |
| 23 | `spacegroup_symbol` | string | — | International or Hermann-Mauguin space-group symbol. |
| 24 | `point_group` | string | — | Point-group symmetry of the structure. |

## calculation_settings

Settings that describe how the calculation was performed: the method, the simulation program name and version, the exchange-correlation functional, the k-point mesh, and the energy cutoff.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 25 | `calculation_method` | string | — | High-level method used to obtain the calculation, such as DFT or a derived workflow. |
| 26 | `code` | string | — | Name of the simulation program used for the calculation, without its version. |
| 27 | `code_version` | string | — | Version of the simulation program used. |
| 28 | `functional` | string | — | Named exchange-correlation functional used in the calculation. |
| 29 | `kpoint_mesh` | array | — | Three positive integers for a regular reciprocal-space mesh. Paths or lists of explicit points belong in source artifacts. |
| 30 | `energy_cutoff` | number | eV | Plane-wave or basis energy cutoff used in the calculation. |

## energy_and_stability

Energetics and thermodynamic stability: total and formation energies (cell and per atom), energy above the convex hull, stability and theoretical flags, temperature, and pressure.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 31 | `total_energy` | number | eV | Total energy of the calculated cell. |
| 32 | `energy_per_atom` | number | eV/atom | Total energy normalized by the number of atoms. |
| 33 | `formation_energy` | number | eV | Formation energy of the calculated cell relative to reference states. |
| 34 | `formation_energy_per_atom` | number | eV/atom | Formation energy normalized per atom. |
| 35 | `energy_above_hull` | number | eV/atom | Energy above the thermodynamic convex hull for the chemical system. |
| 36 | `is_stable` | boolean | — | Source classification indicating whether the material is stable under its stated criterion. |
| 37 | `theoretical` | boolean | — | Whether the record is marked as theoretical rather than experimentally confirmed. |
| 38 | `temperature` | number | K | Temperature associated with the calculation or reported property. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| 39 | `pressure` | number | GPa | Hydrostatic pressure in GPa; AFLOW reports unrelaxed pressure in kbar, converted by factor 0.1. |

## electronic_structure

Electronic-structure results: band gap and gap character, band edges, Fermi level, and pointers to band-structure and density-of-states artifacts.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 40 | `band_gap` | number | eV | Electronic band gap between the valence-band maximum and conduction-band minimum. |
| 41 | `band_gap_type` | string | — | Classification of the band gap, such as direct or indirect. |
| 42 | `is_metal` | boolean | — | Whether the electronic structure is classified as metallic. |
| 43 | `is_gap_direct` | boolean | — | Whether the fundamental band gap is direct in reciprocal space. |
| 44 | `cbm` | number | eV | Energy of the conduction-band minimum. |
| 45 | `vbm` | number | eV | Energy of the valence-band maximum. |
| 46 | `fermi_level` | number | eV | Fermi level reported by the calculation or source. |
| 47 | `band_structure_path` | string | — | Local path to the electronic band-structure artifact. |
| 48 | `dos_path` | string | — | Local path to the electronic density-of-states artifact. |

## magnetism

Magnetic ordering classification and magnetization values, including site-resolved moments.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 49 | `magnetic_ordering` | string | — | Magnetic ordering classification, such as nonmagnetic, ferromagnetic, or antiferromagnetic. |
| 50 | `total_magnetization` | number | Bohr magneton | Total magnetization of the calculated cell. |
| 51 | `magnetization_per_atom` | number | Bohr magneton/atom | Total magnetization normalized per atom. |
| 52 | `magnetic_site_count` | integer | 1 | Number of atomic sites carrying a nonzero or source-defined magnetic moment. |
| 53 | `magnetic_moments` | array | Bohr magneton | Site-resolved scalar magnetic moments in Bohr magneton, ordered by source atom/site order. |

## elastic_and_mechanical_properties

Elastic response in Voigt, Reuss, and Voigt-Reuss-Hill forms, Young's modulus, Poisson ratio, anisotropy, and the elastic-tensor artifact path.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 54 | `bulk_modulus_voigt` | number | GPa | Voigt estimate of the bulk modulus. |
| 55 | `bulk_modulus_reuss` | number | GPa | Reuss estimate of the bulk modulus. |
| 56 | `bulk_modulus_vrh` | number | GPa | Voigt-Reuss-Hill average of the bulk modulus. |
| 57 | `shear_modulus_voigt` | number | GPa | Voigt estimate of the shear modulus. |
| 58 | `shear_modulus_reuss` | number | GPa | Reuss estimate of the shear modulus. |
| 59 | `shear_modulus_vrh` | number | GPa | Voigt-Reuss-Hill average of the shear modulus. |
| 60 | `youngs_modulus` | number | GPa | Young modulus describing tensile stiffness. |
| 61 | `poisson_ratio` | number | 1 | Poisson ratio describing transverse strain relative to axial strain. |
| 62 | `elastic_anisotropy` | number | 1 | Measure of how elastic response varies with direction. |
| 63 | `elastic_tensor_path` | string | — | Local path to the elastic-tensor artifact. |

## dielectric_piezoelectric_and_surface_properties

Dielectric response, refractive index, piezoelectric response, surface energy, work function, and shape factor.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 64 | `dielectric_total` | number | 1 | Source scalar total static relative dielectric response; dimensionless. Scalar averaging convention remains source-specific. |
| 65 | `dielectric_ionic` | number | 1 | Source scalar ionic relative dielectric contribution; dimensionless. |
| 66 | `dielectric_electronic` | number | 1 | Source scalar electronic relative dielectric contribution; dimensionless. |
| 67 | `refractive_index` | number | 1 | Optical refractive index reported by the source. |
| 68 | `piezoelectric_modulus` | number | C/m^2 | Maximum piezoelectric stress response magnitude from MP e_ij_max, in C/m^2. |
| 69 | `piezoelectric_tensor` | array | C/m^2 | Piezoelectric stress tensor in C/m^2, 3 by 6 in Voigt notation. Reserved: no current producer. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| 70 | `weighted_surface_energy` | number | J/m^2 | Surface-orientation-weighted energy in J/m^2. MP eV/Angstrom^2 is converted and cross-checked; weighting is source-defined. |
| 71 | `surface_anisotropy` | number | 1 | Directional variation of surface energy. |
| 72 | `weighted_work_function` | number | eV | Surface-orientation-weighted work function in eV; weighting is source-defined. |
| 73 | `shape_factor` | number | 1 | Dimensionless shape or geometric factor supplied by the source. |

## phonon_and_thermal_properties

Phonon artifact paths and thermal properties such as Debye temperature and lattice thermal conductivity.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 74 | `phonon_band_structure_path` | string | — | Local path to the phonon band-structure artifact. |
| 75 | `phonon_dos_path` | string | — | Local path to the phonon density-of-states artifact. |
| 76 | `debye_temperature` | number | K | Debye temperature derived or reported for the material. |
| 77 | `thermal_conductivity` | number | W/(m*K) | Lattice thermal conductivity. The current AFLOW adapter supplies the AGL scalar at 300 K; do not compare at other temperatures without source metadata. |

## provenance_and_artifacts

Local storage paths, download status, per-property errors, retrieval timestamps, and schema/API versioning for the normalized record.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 78 | `xas_path` | string | — | Local path to the X-ray absorption spectroscopy artifact. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| 79 | `property_paths` | object | — | Mapping from property names to local artifact paths. |
| 80 | `property_errors` | object | — | Errors encountered while retrieving or processing individual properties. |
| 81 | `download_status` | string | — | Pipeline outcome after artifact retrieval; success does not imply every physical property exists. |
| 82 | `properties_requested` | boolean | — | Whether optional property or artifact retrieval was requested in this run. |
| 83 | `raw_path` | string | — | Local path to the raw source record. |
| 84 | `retrieved_at` | string | — | Time when the source record was retrieved by the crawler. |
| 85 | `updated_at` | string | — | Source or pipeline last-update string. Legacy AFLOW date text is preserved, so this field has no strict date-time format. |
| 86 | `schema_version` | string | — | Version of the normalized DFT schema used for this record. |
| 87 | `api_version` | string | — | Version of the upstream API or endpoint that supplied the record. |
| 88 | `content_hash` | string | — | SHA-256 of raw JSON serialized with sorted keys, UTF-8, no ASCII escaping and compact separators; excludes normalized pipeline metadata. |
| 89 | `license` | string | — | Upstream reuse license, when explicitly supplied; never inferred from missing data. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| 90 | `citation` | string | — | Upstream recommended citation or DOI, when explicitly supplied. Not populated by current adapters; null is required until a producer and its semantics are implemented. |

## extended_and_source_fields

Provider-specific extensions and upstream values that are retained for provenance or are not yet part of the core comparable set.

| # | Field | Type | Unit | Description |
| ---: | --- | --- | --- | --- |
| 91 | `formula_anonymous` | string | — | Anonymous formula that preserves stoichiometric pattern while replacing element names. |
| 92 | `composition_reduced` | object | — | Element amounts reduced to the smallest stoichiometric ratio, independent of the represented cell atom count. |
| 93 | `density_atomic` | number | atom/Angstrom^3 | Atomic number density, computed as atom_count / cell volume in atom/Angstrom^3. MP density_atomic is not copied because its implementation and documentation disagree. |
| 94 | `decomposes_to` | array | — | Decomposition products with source material identifier, formula and amount in formula units. Applicable to unstable or metastable materials. |
| 95 | `deprecation_reasons` | array | — | Reasons supplied by the source for deprecating the record. |
| 96 | `grain_boundaries` | array | — | Grain-boundary structures or properties reported by the source. |
| 97 | `has_props` | object | — | Source-level availability map or summary for requested properties. |
| 98 | `has_reconstructed` | boolean | — | Whether any of the material's calculated surfaces are reconstructed. |
| 99 | `is_magnetic` | boolean | — | Whether the record is classified as magnetic. |
| 100 | `last_updated` | string | — | Last-update timestamp reported by the upstream source. |
| 101 | `num_unique_magnetic_sites` | integer | 1 | Number of symmetry-unique magnetic sites. |
| 102 | `origins` | array | — | Provenance records describing where the material or property data originated. |
| 103 | `possible_species` | array | — | Species or oxidation-state candidates considered possible for the structure. |
| 104 | `property_name` | string | — | Name of the property represented by the record or artifact. |
| 105 | `types_of_magnetic_species` | array | — | Chemical species identified as carrying magnetic moments. |
| 106 | `uncorrected_energy_per_atom` | number | eV/atom | Uncorrected total energy normalized per atom. |
| 107 | `warnings` | array | — | Warnings emitted by the source or normalization pipeline. |
| 108 | `bandstructure_summary` | object | — | Provider-specific band-structure metadata; complete data are referenced by property_paths or band_structure_path. |
| 109 | `dos_summary` | object | — | Provider-specific DOS metadata; complete data are referenced by property_paths or dos_path. |
| 110 | `dos_energy_up` | number | eV | Spin-up DOS band gap, a scalar energy; not a DOS energy grid. |
| 111 | `dos_energy_down` | number | eV | Spin-down DOS band gap, a scalar energy; not a DOS energy grid. |
| 112 | `xas_summary` | array | — | List of MP XAS summary entries; route documents are referenced by property_paths. |
| 113 | `builder_meta` | object | — | Source-native builder metadata object. Keys are provider-specific and preserved for provenance. |
| 114 | `source_documents` | object | — | Raw source documents used to build the normalized record. |
| 115 | `source_extra` | object | — | Unmapped upstream or adapter-enriched values, retained with source-specific semantics; excluded from cross-source equivalence claims. |

## Reserved fields

Reserved fields are declared in the contract but must remain `null`: they have no producer yet, and a value may only be populated once a source and its semantics are defined.

| # | Field | Description |
| ---: | --- | --- |
| — | `temperature` | Temperature associated with the calculation or reported property. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| — | `piezoelectric_tensor` | Piezoelectric stress tensor in C/m^2, 3 by 6 in Voigt notation. Reserved: no current producer. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| — | `xas_path` | Local path to the X-ray absorption spectroscopy artifact. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| — | `license` | Upstream reuse license, when explicitly supplied; never inferred from missing data. Not populated by current adapters; null is required until a producer and its semantics are implemented. |
| — | `citation` | Upstream recommended citation or DOI, when explicitly supplied. Not populated by current adapters; null is required until a producer and its semantics are implemented. |

## References

- Standard contract: [`normalizers/dft/standard.yaml`](../../normalizers/dft/standard.yaml)
- DFT overview: [`document/dft/overview.md`](./overview.md)
- Source adapters: [`mp.md`](./mp.md), [`aflow.md`](./aflow.md)
- Cross-source field comparison: [`field_comparison.md`](../../field_comparison.md)
