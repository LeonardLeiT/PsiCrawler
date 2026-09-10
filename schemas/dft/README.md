# Standard DFT Fields

This directory defines PsiCrawler's unified DFT (Density Functional Theory) data contract. The current standard version is `dft-v1`, with 51 fields. `standard.yaml` is the authoritative field definition, `catalog.yaml` stores the field catalog, and each source-specific `*.yaml` file defines source mappings.

All fields are currently optional and nullable. Use `null` when a source does not provide a value, the value has not been fetched, or the property is not applicable. Do not use `0`, an empty string, or `false` to represent missing data. `false` means the negative value is known; `0` means the numeric value is known to be zero. Path fields refer to local files and should not be assumed to be remote URLs.

## Field Groups

| Group | Count | Fields |
| --- | ---: | --- |
| Source and record metadata | 4 | `source`, `source_id`, `schema_version`, `ingested_at` |
| Chemical composition | 4 | `formula`, `formula_pretty`, `elements`, `composition` |
| Structure and crystallography | 6 | `nsites`, `volume`, `density`, `symmetry_symbol`, `symmetry_number`, `crystal_system` |
| Energy and stability | 5 | `energy`, `energy_per_atom`, `formation_energy_per_atom`, `energy_above_hull`, `is_stable` |
| Electronic structure | 3 | `band_gap`, `is_metal`, `efermi` |
| Magnetism | 4 | `total_magnetization`, `magnetic_ordering`, `is_magnetic`, `magnetic_moment` |
| Elastic and mechanical properties | 12 | `volume_change`, `bulk_modulus`, `shear_modulus`, `elastic_anisotropy`, `homogeneous_poisson`, `g_reuss`, `g_voigt`, `k_reuss`, `k_voigt`, `universal_anisotropy`, `elastic_tensor`, `has_elasticity` |
| Electronic and phonon files | 10 | `dos_path`, `bandstructure_path`, `charge_density_path`, `phonon_bandstructure_path`, `phonon_dos_path`, `phonon_modes_path`, `has_dos`, `has_bandstructure`, `has_charge_density`, `has_phonon` |
| Structure and calculation output files | 3 | `cif_path`, `poscar_path`, `output_dir` |
| **Total** | **51** | |

## 1. Source and Record Metadata

| Field | Type | Unit / format | Description |
| --- | --- | --- | --- |
| `source` | string | enum | Data source: `mp`, `oqmd`, `aflow`, `citrine`, `jarvis`, or `other`. |
| `source_id` | string | source-local ID | Material or calculation record ID in the source, such as `mp-149`; not guaranteed to be globally unique. |
| `schema_version` | string | version | Standard version followed by the record; currently `dft-v1`. |
| `ingested_at` | string | ISO 8601 | Time when the record entered the normalization pipeline, normally in UTC. |

## 2. Chemical Composition

| Field | Type | Unit / format | Description |
| --- | --- | --- | --- |
| `formula` | string | chemical formula | Original formula string supplied by the source, preserving source representation where possible. |
| `formula_pretty` | string | chemical formula | Normalized or display-friendly formula for presentation and search. |
| `elements` | array[string] | element symbols | Unique elements in the structure, for example [`Si`, `O`]. |
| `composition` | object | element-to-amount map | Composition mapping, for example `{"Si": 1, "O": 2}`; amounts may be integer counts or normalized ratios. |

## 3. Structure and Crystallography

| Field | Type | Unit / range | Description |
| --- | --- | --- | --- |
| `nsites` | integer | count | Number of atoms in the calculated unit cell; not the number of element species. |
| `volume` | number | Å³ | Calculated unit-cell volume. |
| `density` | number | g/cm³ | Material density, normally derived from unit-cell mass and volume. |
| `symmetry_symbol` | string | Hermann-Mauguin | Space-group symbol, such as `Fd-3m`. |
| `symmetry_number` | integer | 1–230 | International space-group number. |
| `crystal_system` | string | enum | `cubic`, `tetragonal`, `orthorhombic`, `hexagonal`, `trigonal`, `monoclinic`, `triclinic`, or `other`. |

## 4. Energy and Stability

| Field | Type | Unit / range | Description |
| --- | --- | --- | --- |
| `energy` | number | eV / cell | Total energy of the calculated system; compare across materials only after checking cell-size consistency. |
| `energy_per_atom` | number | eV/atom | Total energy divided by the number of atoms in the unit cell. |
| `formation_energy_per_atom` | number | eV/atom | Formation energy per atom relative to elemental reference states; references vary by source. |
| `energy_above_hull` | number | eV/atom | Energy relative to the convex hull of the same chemical system; values closer to 0 are generally more stable. |
| `is_stable` | boolean | true / false | Stability judgment supplied by the source; preserve the source's threshold semantics. |

## 5. Electronic Structure

| Field | Type | Unit / range | Description |
| --- | --- | --- | --- |
| `band_gap` | number | eV | Band gap. Metals commonly have 0 or a near-zero value, but the source classification should be preserved. |
| `is_metal` | boolean | true / false | Whether the material is metallic; do not infer false from a missing band-gap value. |
| `efermi` | number | eV | Fermi level. Source inputs may call this `efermi` or `fermi_level`; the normalized name is always `efermi`. |

## 6. Magnetism

| Field | Type | Unit / range | Description |
| --- | --- | --- | --- |
| `total_magnetization` | number | μB / cell | Total cell magnetization or magnetic moment; the exact definition follows the source. |
| `magnetic_ordering` | string | enum | `NM`, `FM`, `AFM`, `FiM`, or `unknown`. |
| `is_magnetic` | boolean | true / false | Whether magnetism is present; do not fill false automatically when total magnetization is missing. |
| `magnetic_moment` | number | μB | Source-provided magnetic-moment summary; it may be per atom, per ion, or per structure and must be interpreted with source metadata. |

## 7. Elastic and Mechanical Properties

Elastic fields primarily use GPa. Dimensionless fields have no unit. `bulk_modulus` and `shear_modulus` use Voigt-Reuss-Hill (VRH) averages.

| Field | Type | Unit / range | Description |
| --- | --- | --- | --- |
| `volume_change` | number | % | Volume change from an elastic or structural calculation. |
| `bulk_modulus` | number | GPa | VRH bulk modulus, describing resistance to uniform compression. |
| `shear_modulus` | number | GPa | VRH shear modulus, describing resistance to shear deformation. |
| `elastic_anisotropy` | number | dimensionless | Elastic-anisotropy summary value; exact definition follows the source. |
| `homogeneous_poisson` | number | dimensionless | Homogeneous Poisson ratio. |
| `g_reuss` | number | GPa | Reuss average of the shear modulus. |
| `g_voigt` | number | GPa | Voigt average of the shear modulus. |
| `k_reuss` | number | GPa | Reuss average of the bulk modulus. |
| `k_voigt` | number | GPa | Voigt average of the bulk modulus. |
| `universal_anisotropy` | number | dimensionless | Universal Elastic Anisotropy Index; it is commonly 0 for an isotropic material. |
| `elastic_tensor` | object | usually GPa | Elastic stiffness tensor or source-native structure, such as an object containing `C11`; internal keys are not fixed by the standard layer. |
| `has_elasticity` | boolean | true / false | Whether usable elastic data exists, normally determined by successful retrieval of a tensor or elastic-constant file. |

## 8. Electronic and Phonon Data Files

These fields point to downloaded or generated local artifacts. Use `null` when a path does not exist, has not been downloaded, or the source has no corresponding calculation. The `has_*` fields provide quick availability flags.

| Field | Type | Unit / format | Description |
| --- | --- | --- | --- |
| `dos_path` | string | local path | Total density-of-states (DOS) data file. |
| `bandstructure_path` | string | local path | Electronic band-structure data file. |
| `charge_density_path` | string | local path | Charge-density data file. |
| `phonon_bandstructure_path` | string | local path | Phonon band-structure data file. |
| `phonon_dos_path` | string | local path | Phonon density-of-states data file. |
| `phonon_modes_path` | string | local path | Phonon-mode, displacement, or mode-resolved data file. |
| `has_dos` | boolean | true / false | Whether usable DOS data exists. |
| `has_bandstructure` | boolean | true / false | Whether usable electronic band-structure data exists. |
| `has_charge_density` | boolean | true / false | Whether usable charge-density data exists. |
| `has_phonon` | boolean | true / false | Whether any phonon data exists, normally based on the presence of any phonon artifact. |

## 9. Structure and Calculation Output Files

| Field | Type | Unit / format | Description |
| --- | --- | --- | --- |
| `cif_path` | string | local path | CIF structure-file path. |
| `poscar_path` | string | local path | VASP POSCAR/CONTCAR-style structure-file path. |
| `output_dir` | string | local directory path | Directory containing raw outputs for the material or calculation record. |

## Source Mapping

| Source | source value | source_id example | Mapping file |
| --- | --- | --- | --- |
| Materials Project | `mp` | `mp-149` | `mp.yaml` |
| OQMD | `oqmd` | OQMD entry ID | `oqmd.yaml` |
| AFLOW | `aflow` | AUID | `aflow.yaml` |
| Citrine | `citrine` | Citrine entry ID | `citrine.yaml` |
| JARVIS | `jarvis` | JID | `jarvis.yaml` |

When a source field has no corresponding standard field, it is not forcibly converted. Complete source data and non-normalized properties should remain traceable through raw output files or source-specific structures.

## Maintenance and Validation

When changing fields, check all of the following:

1. `standard.yaml`: field names, types, enums, and descriptions.
2. `catalog.yaml`: field count and field order.
3. `sources/dft/*/normalize.py`: source normalization logic.
4. `schemas/dft/*.yaml`: field mappings and property endpoints.

```powershell
python -m compileall -q sources\dft\mp crawler\dft\mp
```

