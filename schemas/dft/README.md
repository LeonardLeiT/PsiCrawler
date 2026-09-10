# DFT Standard Schema

This document groups the standard DFT record into practical categories. The machine-readable definition is [standard.yaml](./standard.yaml).

## Source and Record Metadata

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| source | string | - | Name of the upstream data source. |
| requested_id | string | - | Identifier supplied to the crawler by the user. |
| source_id | string | - | Stable identifier assigned by the upstream source. |
| source_url | string | - | Source-reported source url; use it with the other fields in this category. |
| calculation_method | string | - | Source-reported calculation method; use it with the other fields in this category. |
| calculation_type | string | - | Source-reported calculation type; use it with the other fields in this category. |
| code | string | - | Source-reported code; use it with the other fields in this category. |
| code_version | string | - | Source-reported code version; use it with the other fields in this category. |
| retrieved_at | string | - | Source-reported retrieved at; use it with the other fields in this category. |
| schema_version | string | - | Source-reported schema version; use it with the other fields in this category. |
| api_version | string | - | Source-reported api version; use it with the other fields in this category. |
| license | string | object | Source-reported license; use it with the other fields in this category. |
| citation | string | object | Source-reported citation; use it with the other fields in this category. |

## Composition and Identity

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| formula | string | - | Chemical formula reported for the material. |
| formula_reduced | string | - | Source-reported formula reduced; use it with the other fields in this category. |
| chemical_system | string | - | Source-reported chemical system; use it with the other fields in this category. |
| elements | list[string] | list | Source-reported elements; use it with the other fields in this category. |
| composition | object | object | Source-reported composition; use it with the other fields in this category. |
| element_count | integer | - | Source-reported element count; use it with the other fields in this category. |
| formula_anonymous | string | - | Source-reported formula anonymous; use it with the other fields in this category. |
| composition_reduced | object | - | Source-reported composition reduced; use it with the other fields in this category. |
| possible_species | array | list | Source-reported possible species; use it with the other fields in this category. |

## Structure and Crystallography

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| structure | object | object | Parsed crystal structure object when available. |
| structure_path | string | path | Path to the canonical structure file. |
| structure_json_path | string | path | Path to the serialized structure JSON. |
| structure_format | list[string] | - | Source-reported structure format; use it with the other fields in this category. |
| lattice_matrix | array | angstrom | Source-reported lattice matrix; use it with the other fields in this category. |
| lattice_a | float | angstrom | Source-reported lattice a; use it with the other fields in this category. |
| lattice_b | float | angstrom | Source-reported lattice b; use it with the other fields in this category. |
| lattice_c | float | angstrom | Source-reported lattice c; use it with the other fields in this category. |
| angle_alpha | float | degree | Source-reported angle alpha; use it with the other fields in this category. |
| angle_beta | float | degree | Source-reported angle beta; use it with the other fields in this category. |
| angle_gamma | float | degree | Source-reported angle gamma; use it with the other fields in this category. |
| volume | float | varies | Source-reported volume; use it with the other fields in this category. |
| density | float | varies | Source-reported density; use it with the other fields in this category. |
| crystal_system | string | - | Source-reported crystal system; use it with the other fields in this category. |
| spacegroup_number | integer | - | Source-reported spacegroup number; use it with the other fields in this category. |
| spacegroup_symbol | string | - | Source-reported spacegroup symbol; use it with the other fields in this category. |
| point_group | string | - | Source-reported point group; use it with the other fields in this category. |
| symmetry_precision | float | - | Source-reported symmetry precision; use it with the other fields in this category. |
| symmetry_tolerance | float | - | Source-reported symmetry tolerance; use it with the other fields in this category. |
| density_atomic | float | varies | Source-reported density atomic; use it with the other fields in this category. |

## Calculation Settings

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| functional | string | - | Source-reported functional; use it with the other fields in this category. |
| exchange_correlation | string | - | Source-reported exchange correlation; use it with the other fields in this category. |
| pseudopotential | string | - | Source-reported pseudopotential; use it with the other fields in this category. |
| basis_set | string | - | Source-reported basis set; use it with the other fields in this category. |
| kpoint_mesh | array | - | Source-reported kpoint mesh; use it with the other fields in this category. |
| energy_cutoff | float | varies | Source-reported energy cutoff; use it with the other fields in this category. |
| smearing | string | - | Source-reported smearing; use it with the other fields in this category. |
| spin_polarized | boolean | - | Source-reported spin polarized; use it with the other fields in this category. |
| spin_orbit_coupling | boolean | - | Source-reported spin orbit coupling; use it with the other fields in this category. |
| hubbard_u | boolean | - | Source-reported hubbard u; use it with the other fields in this category. |
| u_values | object | - | Source-reported u values; use it with the other fields in this category. |
| theoretical | boolean | - | Source-reported theoretical; use it with the other fields in this category. |
| temperature | float | varies | Source-reported temperature; use it with the other fields in this category. |
| pressure | float | varies | Source-reported pressure; use it with the other fields in this category. |
| shape_factor | float | - | Source-reported shape factor; use it with the other fields in this category. |
| origins | array | object | Source-reported origins; use it with the other fields in this category. |
| builder_meta | array | object | Source-reported builder meta; use it with the other fields in this category. |

## Energy and Stability

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| relaxation_status | string | - | Source-reported relaxation status; use it with the other fields in this category. |
| total_energy | float | varies | Source-reported total energy; use it with the other fields in this category. |
| uncorrected_energy | float | varies | Source-reported uncorrected energy; use it with the other fields in this category. |
| energy_per_atom | float | varies | Source-reported energy per atom; use it with the other fields in this category. |
| formation_energy | float | varies | Source-reported formation energy; use it with the other fields in this category. |
| formation_energy_per_atom | float | varies | Source-reported formation energy per atom; use it with the other fields in this category. |
| energy_above_hull | float | varies | Source-reported energy above hull; use it with the other fields in this category. |
| decomposition_energy | float | varies | Source-reported decomposition energy; use it with the other fields in this category. |
| equilibrium_reaction_energy | float | varies | Source-reported equilibrium reaction energy; use it with the other fields in this category. |
| is_stable | boolean | - | Source-reported is stable; use it with the other fields in this category. |
| deprecated | boolean | - | Source-reported deprecated; use it with the other fields in this category. |
| download_status | string | - | Source-reported download status; use it with the other fields in this category. |
| decomposes_to | object | list | Source-reported decomposes to; use it with the other fields in this category. |
| deprecation_reasons | array | object | Source-reported deprecation reasons; use it with the other fields in this category. |
| uncorrected_energy_per_atom | float | varies | Source-reported uncorrected energy per atom; use it with the other fields in this category. |

## Electronic Structure

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| band_gap | float | varies | Source-reported band gap; use it with the other fields in this category. |
| band_gap_type | string | varies | Source-reported band gap type; use it with the other fields in this category. |
| is_metal | boolean | - | Source-reported is metal; use it with the other fields in this category. |
| is_gap_direct | boolean | varies | Source-reported is gap direct; use it with the other fields in this category. |
| cbm | float | varies | Source-reported cbm; use it with the other fields in this category. |
| vbm | float | varies | Source-reported vbm; use it with the other fields in this category. |
| fermi_level | float | varies | Source-reported fermi level; use it with the other fields in this category. |
| band_structure_path | string | path | Path to the downloaded band-structure artifact. |
| dos_path | string | path | Path to the downloaded density-of-states artifact. |
| refractive_index | float | - | Source-reported refractive index; use it with the other fields in this category. |
| bandstructure_summary | object | object | Source-reported bandstructure summary; use it with the other fields in this category. |
| dos_summary | object | object | Source-reported dos summary; use it with the other fields in this category. |
| dos_energy_up | array | varies | Source-reported dos energy up; use it with the other fields in this category. |
| dos_energy_down | array | varies | Source-reported dos energy down; use it with the other fields in this category. |

## Magnetism

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| magnetic_ordering | string | - | Source-reported magnetic ordering; use it with the other fields in this category. |
| total_magnetization | float | - | Source-reported total magnetization; use it with the other fields in this category. |
| magnetization_per_atom | float | - | Source-reported magnetization per atom; use it with the other fields in this category. |
| magnetic_site_count | integer | - | Source-reported magnetic site count; use it with the other fields in this category. |
| magnetic_moments | array | - | Source-reported magnetic moments; use it with the other fields in this category. |
| is_magnetic | boolean | - | Source-reported is magnetic; use it with the other fields in this category. |
| num_unique_magnetic_sites | integer | - | Source-reported num unique magnetic sites; use it with the other fields in this category. |
| types_of_magnetic_species | array | list | Source-reported types of magnetic species; use it with the other fields in this category. |

## Elastic and Mechanical

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| bulk_modulus_voigt | float | varies | Source-reported bulk modulus voigt; use it with the other fields in this category. |
| bulk_modulus_reuss | float | varies | Source-reported bulk modulus reuss; use it with the other fields in this category. |
| bulk_modulus_vrh | float | varies | Source-reported bulk modulus vrh; use it with the other fields in this category. |
| shear_modulus_voigt | float | varies | Source-reported shear modulus voigt; use it with the other fields in this category. |
| shear_modulus_reuss | float | varies | Source-reported shear modulus reuss; use it with the other fields in this category. |
| shear_modulus_vrh | float | varies | Source-reported shear modulus vrh; use it with the other fields in this category. |
| youngs_modulus | float | varies | Source-reported youngs modulus; use it with the other fields in this category. |
| poisson_ratio | float | varies | Source-reported poisson ratio; use it with the other fields in this category. |
| elastic_anisotropy | float | - | Source-reported elastic anisotropy; use it with the other fields in this category. |
| elastic_tensor | array | - | Source-reported elastic tensor; use it with the other fields in this category. |
| elastic_tensor_path | string | path | Path to the downloaded elastic-tensor artifact. |

## Dielectric, Piezoelectric and Surface

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| dielectric_total | float | - | Source-reported dielectric total; use it with the other fields in this category. |
| dielectric_ionic | float | - | Source-reported dielectric ionic; use it with the other fields in this category. |
| dielectric_electronic | float | - | Source-reported dielectric electronic; use it with the other fields in this category. |
| dielectric_tensor | array | - | Source-reported dielectric tensor; use it with the other fields in this category. |
| piezoelectric_modulus | float | varies | Source-reported piezoelectric modulus; use it with the other fields in this category. |
| piezoelectric_tensor | array | - | Source-reported piezoelectric tensor; use it with the other fields in this category. |
| weighted_surface_energy | float | varies | Source-reported weighted surface energy; use it with the other fields in this category. |
| surface_energy | float | varies | Source-reported surface energy; use it with the other fields in this category. |
| surface_anisotropy | float | - | Source-reported surface anisotropy; use it with the other fields in this category. |
| weighted_work_function | float | varies | Source-reported weighted work function; use it with the other fields in this category. |
| work_function | float | varies | Source-reported work function; use it with the other fields in this category. |
| grain_boundaries | object | - | Source-reported grain boundaries; use it with the other fields in this category. |
| weighted_surface_energy_ev_per_ang2 | float | varies | Source-reported weighted surface energy ev per ang2; use it with the other fields in this category. |

## Phonon and Thermal

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| phonon_band_structure_path | string | path | Path to the downloaded phonon band-structure artifact. |
| phonon_dos_path | string | path | Path to the downloaded phonon DOS artifact. |
| debye_temperature | float | varies | Source-reported debye temperature; use it with the other fields in this category. |
| heat_capacity | object | varies | Source-reported heat capacity; use it with the other fields in this category. |
| thermal_conductivity | float | varies | Source-reported thermal conductivity; use it with the other fields in this category. |

## XAS and Provenance

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| xas_path | string | path | Path to the downloaded XAS artifact. |
| property_paths | object | object | Map of property names to stored artifact paths. |
| property_errors | object | object | Source-reported property errors; use it with the other fields in this category. |
| properties_requested | boolean | object | Source-reported properties requested; use it with the other fields in this category. |
| raw_path | string | path | Source-reported raw path; use it with the other fields in this category. |
| normalized_path | string | path | Source-reported normalized path; use it with the other fields in this category. |
| content_hash | string | - | Content hash for change detection and deduplication. |
| has_props | object | - | Source-reported has props; use it with the other fields in this category. |
| has_reconstructed | boolean | - | Source-reported has reconstructed; use it with the other fields in this category. |
| property_name | string | - | Source-reported property name; use it with the other fields in this category. |
| warnings | array | object | Source-reported warnings; use it with the other fields in this category. |
| xas_summary | object | object | Source-reported xas summary; use it with the other fields in this category. |
| source_documents | object | object | Raw source documents used to build this record. |
| source_extra | object | object | Source-specific fields not promoted to the standard schema. |

## Other Source Fields

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| atom_count | integer | - | Source-reported atom count; use it with the other fields in this category. |
| updated_at | string | - | Source-reported updated at; use it with the other fields in this category. |
| last_updated | string | - | Source-reported last updated; use it with the other fields in this category. |

## Data Source Mapping

| Source | Mapping file |
| --- | --- |
| Materials Project | [mp.yaml](./mp.yaml) |
| AFLOW | [aflow.yaml](./aflow.yaml) |

**Total: 142 fields.**
