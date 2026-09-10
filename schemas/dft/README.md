# DFT Standard Schema

This document groups the standard DFT record in the exact field order defined by `standard.yaml`; see [standard.yaml](./standard.yaml) for the machine-readable definition.
The current standard schema version is `1.0`, with 142 fields.

## Source and Record Metadata

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| source | string | - | Name of the upstream database or provider. |
| requested_id | string | - | Identifier requested by the user or crawler before source lookup. |
| source_id | string | - | Stable identifier assigned to this record by the upstream source. |
| source_url | string | - | Canonical URL of the upstream record or source page. |

## Composition and Identity

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| formula | string | - | Chemical formula of the material in the source representation. |
| formula_reduced | string | - | Reduced chemical formula normalized to the smallest whole-number ratio. |
| chemical_system | string | - | Unordered chemical system, usually represented as element symbols joined by hyphens. |
| elements | list[string] | list | Unique chemical elements present in the material. |
| composition | object | object | Mapping from each element to its amount or stoichiometric fraction. |
| element_count | integer | - | Number of distinct chemical elements in the composition. |
| atom_count | integer | - | Total number of atoms in the represented structure or record. |

## Structure and Crystallography

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| structure | object | object | Parsed crystal structure, including lattice and site information, when available. |
| structure_path | string | path | Local path to the canonical structure artifact. |
| structure_json_path | string | path | Local path to the serialized structure JSON. |
| structure_format | list[string] | - | File or representation formats available for the structure. |
| lattice_matrix | array | Angstrom | Three lattice vectors defining the unit cell. |
| lattice_a | float | Angstrom | Length of the first lattice vector. |
| lattice_b | float | Angstrom | Length of the second lattice vector. |
| lattice_c | float | Angstrom | Length of the third lattice vector. |
| angle_alpha | float | degree | Angle between the second and third lattice vectors. |
| angle_beta | float | degree | Angle between the first and third lattice vectors. |
| angle_gamma | float | degree | Angle between the first and second lattice vectors. |
| volume | float | Angstrom^3 | Volume of the unit cell. |
| density | float | g/cm^3 | Mass density calculated or reported for the material. |
| crystal_system | string | - | Crystal-system classification, such as cubic or triclinic. |
| spacegroup_number | integer | - | International space-group number of the structure. |
| spacegroup_symbol | string | - | International or Hermann-Mauguin space-group symbol. |
| point_group | string | - | Point-group symmetry of the structure. |
| symmetry_precision | float | - | Numerical precision or number of digits used when reporting symmetry. |
| symmetry_tolerance | float | - | Distance or geometric tolerance used for symmetry detection. |

## Calculation Settings

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| calculation_method | string | - | High-level method used to obtain the calculation, such as DFT or a derived workflow. |
| calculation_type | string | - | Specific calculation task or property workflow represented by the record. |
| code | string | - | Electronic-structure or simulation program used for the calculation. |
| code_version | string | - | Version of the simulation program used. |
| functional | string | - | Named exchange-correlation functional used in the calculation. |
| exchange_correlation | string | - | Exchange-correlation approximation or family used by the calculation. |
| pseudopotential | string | - | Pseudopotential or projector data used for the atomic species. |
| basis_set | string | - | Basis-set definition used to represent the electronic states. |
| kpoint_mesh | array | - | Reciprocal-space sampling mesh used for Brillouin-zone integration. |
| energy_cutoff | float | eV | Plane-wave or basis energy cutoff used in the calculation. |
| smearing | string | - | Electronic occupation smearing method or width. |
| spin_polarized | boolean | - | Whether spin polarization was enabled. |
| spin_orbit_coupling | boolean | - | Whether spin-orbit coupling was included. |
| hubbard_u | boolean | - | Whether a Hubbard-U correction was applied. |
| u_values | object | eV | Element- or orbital-specific Hubbard-U parameters. |
| relaxation_status | string | - | State or outcome of structural and ionic relaxation. |

## Energy and Stability

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| total_energy | float | eV | Total energy of the calculated cell. |
| uncorrected_energy | float | eV | Total energy before source-specific corrections. |
| energy_per_atom | float | eV/atom | Total energy normalized by the number of atoms. |
| formation_energy | float | eV | Formation energy of the calculated cell relative to reference states. |
| formation_energy_per_atom | float | eV/atom | Formation energy normalized per atom. |
| energy_above_hull | float | eV/atom | Energy above the thermodynamic convex hull for the chemical system. |
| decomposition_energy | float | eV/atom | Energy change associated with decomposition into competing phases. |
| equilibrium_reaction_energy | float | eV/atom | Energy change for the source-defined equilibrium reaction. |
| is_stable | boolean | - | Source classification indicating whether the material is stable under its stated criterion. |
| theoretical | boolean | - | Whether the record is marked as theoretical rather than experimentally confirmed. |
| deprecated | boolean | - | Whether the source record has been deprecated or withdrawn. |
| temperature | float | K | Temperature associated with the calculation or reported property. |
| pressure | float | GPa | Pressure associated with the calculation or reported property. |

## Electronic Structure

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| band_gap | float | eV | Electronic band gap between the valence-band maximum and conduction-band minimum. |
| band_gap_type | string | varies | Classification of the band gap, such as direct or indirect. |
| is_metal | boolean | - | Whether the electronic structure is classified as metallic. |
| is_gap_direct | boolean | varies | Whether the fundamental band gap is direct in reciprocal space. |
| cbm | float | eV | Energy of the conduction-band minimum. |
| vbm | float | eV | Energy of the valence-band maximum. |
| fermi_level | float | eV | Fermi level reported by the calculation or source. |
| band_structure_path | string | path | Local path to the electronic band-structure artifact. |
| dos_path | string | path | Local path to the electronic density-of-states artifact. |

## Magnetism

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| magnetic_ordering | string | - | Magnetic ordering classification, such as nonmagnetic, ferromagnetic, or antiferromagnetic. |
| total_magnetization | float | Bohr magneton | Total magnetization of the calculated cell. |
| magnetization_per_atom | float | Bohr magneton/atom | Total magnetization normalized per atom. |
| magnetic_site_count | integer | - | Number of atomic sites carrying a nonzero or source-defined magnetic moment. |
| magnetic_moments | array | - | Magnetic moment values resolved by site, atom, or species. |

## Elastic and Mechanical Properties

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| bulk_modulus_voigt | float | GPa | Voigt estimate of the bulk modulus. |
| bulk_modulus_reuss | float | GPa | Reuss estimate of the bulk modulus. |
| bulk_modulus_vrh | float | GPa | Voigt-Reuss-Hill average of the bulk modulus. |
| shear_modulus_voigt | float | GPa | Voigt estimate of the shear modulus. |
| shear_modulus_reuss | float | GPa | Reuss estimate of the shear modulus. |
| shear_modulus_vrh | float | GPa | Voigt-Reuss-Hill average of the shear modulus. |
| youngs_modulus | float | GPa | Young modulus describing tensile stiffness. |
| poisson_ratio | float | varies | Poisson ratio describing transverse strain relative to axial strain. |
| elastic_anisotropy | float | - | Measure of how elastic response varies with direction. |
| elastic_tensor | array | GPa | Elastic stiffness tensor or its source-native array representation. |
| elastic_tensor_path | string | path | Local path to the elastic-tensor artifact. |

## Dielectric, Piezoelectric, and Surface Properties

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| dielectric_total | float | - | Total static dielectric response. |
| dielectric_ionic | float | - | Ionic contribution to the dielectric response. |
| dielectric_electronic | float | - | Electronic contribution to the dielectric response. |
| refractive_index | float | - | Optical refractive index reported by the source. |
| dielectric_tensor | array | - | Directional dielectric-response tensor. |
| piezoelectric_modulus | float | varies | Piezoelectric response magnitude reported by the source. |
| piezoelectric_tensor | array | - | Tensor describing the directional piezoelectric response. |
| weighted_surface_energy | float | J/m^2 | Surface energy averaged or weighted over the source-defined surface orientations. |
| surface_energy | float | J/m^2 | Energy cost per unit area of a material surface. |
| surface_anisotropy | float | - | Directional variation of surface energy. |
| weighted_work_function | float | eV | Work function averaged or weighted over source-defined surfaces. |
| work_function | float | eV | Energy required to remove an electron from the material surface. |
| shape_factor | float | - | Dimensionless shape or geometric factor supplied by the source. |

## Phonon and Thermal Properties

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| phonon_band_structure_path | string | path | Local path to the phonon band-structure artifact. |
| phonon_dos_path | string | path | Local path to the phonon density-of-states artifact. |
| debye_temperature | float | K | Debye temperature derived or reported for the material. |
| heat_capacity | object | varies | Heat-capacity data or temperature-dependent heat-capacity representation. |
| thermal_conductivity | float | varies | Thermal conductivity reported or calculated for the material. |

## Provenance and Artifacts

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| xas_path | string | path | Local path to the X-ray absorption spectroscopy artifact. |
| property_paths | object | object | Mapping from property names to local artifact paths. |
| property_errors | object | object | Errors encountered while retrieving or processing individual properties. |
| download_status | string | - | Status of downloading the record or its associated artifacts. |
| properties_requested | boolean | - | Whether the requested property set was submitted to or processed by the source. |
| raw_path | string | path | Local path to the raw source record. |
| normalized_path | string | path | Local path to the normalized record. |
| retrieved_at | string | - | Time when the source record was retrieved by the crawler. |
| updated_at | string | - | Timestamp when the normalized or stored record was last updated. |
| schema_version | string | - | Version of the normalized DFT schema used for this record. |
| api_version | string | - | Version of the upstream API or endpoint that supplied the record. |
| content_hash | string | - | Hash of the stored content used for change detection and deduplication. |
| license | string | - | License governing reuse of the source data. |
| citation | string | - | Recommended publication, DOI, or citation for the source data. |

## Extended and Source Fields

| Field | Type | Unit / Format | Meaning |
| --- | --- | --- | --- |
| formula_anonymous | string | - | Anonymous formula that preserves stoichiometric pattern while replacing element names. |
| composition_reduced | object | - | Composition mapping after reducing stoichiometric amounts to their simplest ratio. |
| density_atomic | float | varies | Atomic number density, describing atoms per unit volume. |
| decomposes_to | object | list | Products or competing phases predicted when the material decomposes. |
| deprecation_reasons | array | object | Reasons supplied by the source for deprecating the record. |
| grain_boundaries | object | - | Grain-boundary structures or properties reported by the source. |
| has_props | object | - | Source-level availability map or summary for requested properties. |
| has_reconstructed | boolean | - | Whether a reconstructed structure or record is available. |
| is_magnetic | boolean | - | Whether the record is classified as magnetic. |
| last_updated | string | - | Last-update timestamp reported by the upstream source. |
| num_unique_magnetic_sites | integer | - | Number of symmetry-unique magnetic sites. |
| origins | array | object | Provenance records describing where the material or property data originated. |
| possible_species | array | list | Species or oxidation-state candidates considered possible for the structure. |
| property_name | string | - | Name of the property represented by the record or artifact. |
| types_of_magnetic_species | array | list | Chemical species identified as carrying magnetic moments. |
| uncorrected_energy_per_atom | float | eV/atom | Uncorrected total energy normalized per atom. |
| warnings | array | object | Warnings emitted by the source or normalization pipeline. |
| weighted_surface_energy_ev_per_ang2 | float | eV/Angstrom^2 | Weighted surface energy expressed in eV per square Angstrom. |
| bandstructure_summary | object | object | Compact summary or derived metadata for the electronic band structure. |
| dos_summary | object | object | Compact summary or derived metadata for the density of states. |
| dos_energy_up | array | eV | Energy grid or energy-resolved values for the spin-up DOS channel. |
| dos_energy_down | array | eV | Energy grid or energy-resolved values for the spin-down DOS channel. |
| xas_summary | object | object | Compact summary or derived metadata for the XAS data. |
| builder_meta | array | object | Metadata produced by the pipeline builder that assembled the record. |
| source_documents | object | object | Raw source documents used to build the normalized record. |
| source_extra | object | object | Source-specific fields retained without promotion to a standard field. |

## Data Source Mapping

| Source | Mapping file |
| --- | --- |
| Materials Project | [mp.yaml](./mp.yaml) |
| AFLOW | [aflow.yaml](./aflow.yaml) |

**Total: 142 fields.**



