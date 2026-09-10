# DFT 标准字段

本文按实际使用场景分类说明 DFT 标准记录；机器可读定义见 [standard.yaml](./standard.yaml)。
当前标准 schema 版本为 `1.0`，共 142 个字段。

## 来源与记录元数据

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| source | string | - | 上游数据源名称。 |
| requested_id | string | - | 用户提交给爬虫的查询标识符。 |
| source_id | string | - | 上游数据源分配的稳定标识符。 |
| source_url | string | - | 数据源记录的“source url”字段；应结合本类别中的其他字段使用。 |
| calculation_method | string | - | 数据源记录的“calculation method”字段；应结合本类别中的其他字段使用。 |
| calculation_type | string | - | 数据源记录的“calculation type”字段；应结合本类别中的其他字段使用。 |
| code | string | - | 数据源记录的“code”字段；应结合本类别中的其他字段使用。 |
| code_version | string | - | 数据源记录的“code version”字段；应结合本类别中的其他字段使用。 |
| retrieved_at | string | - | 数据源记录的“retrieved at”字段；应结合本类别中的其他字段使用。 |
| schema_version | string | - | 数据源记录的“schema version”字段；应结合本类别中的其他字段使用。 |
| api_version | string | - | 数据源记录的“api version”字段；应结合本类别中的其他字段使用。 |
| license | string | - | 数据源记录的“license”字段；应结合本类别中的其他字段使用。 |
| citation | string | - | 数据源记录的“citation”字段；应结合本类别中的其他字段使用。 |

## 组成与身份

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| formula | string | - | 数据源报告的材料化学式。 |
| formula_reduced | string | - | 数据源记录的“formula reduced”字段；应结合本类别中的其他字段使用。 |
| chemical_system | string | - | 数据源记录的“chemical system”字段；应结合本类别中的其他字段使用。 |
| elements | list[string] | list | 数据源记录的“elements”字段；应结合本类别中的其他字段使用。 |
| composition | object | object | 数据源记录的“composition”字段；应结合本类别中的其他字段使用。 |
| element_count | integer | - | 数据源记录的“element count”字段；应结合本类别中的其他字段使用。 |
| formula_anonymous | string | - | 数据源记录的“formula anonymous”字段；应结合本类别中的其他字段使用。 |
| composition_reduced | object | - | 数据源记录的“composition reduced”字段；应结合本类别中的其他字段使用。 |
| possible_species | array | list | 数据源记录的“possible species”字段；应结合本类别中的其他字段使用。 |

## 结构与晶体学

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| structure | object | object | 可用时保存的解析后晶体结构对象。 |
| structure_path | string | path | 标准结构文件的存储路径。 |
| structure_json_path | string | path | 序列化结构 JSON 的存储路径。 |
| structure_format | list[string] | - | 数据源记录的“structure format”字段；应结合本类别中的其他字段使用。 |
| lattice_matrix | array | Angstrom | 数据源记录的“lattice matrix”字段；应结合本类别中的其他字段使用。 |
| lattice_a | float | Angstrom | 数据源记录的“lattice a”字段；应结合本类别中的其他字段使用。 |
| lattice_b | float | Angstrom | 数据源记录的“lattice b”字段；应结合本类别中的其他字段使用。 |
| lattice_c | float | Angstrom | 数据源记录的“lattice c”字段；应结合本类别中的其他字段使用。 |
| angle_alpha | float | degree | 数据源记录的“angle alpha”字段；应结合本类别中的其他字段使用。 |
| angle_beta | float | degree | 数据源记录的“angle beta”字段；应结合本类别中的其他字段使用。 |
| angle_gamma | float | degree | 数据源记录的“angle gamma”字段；应结合本类别中的其他字段使用。 |
| volume | float | Angstrom^3 | 数据源记录的“volume”字段；应结合本类别中的其他字段使用。 |
| density | float | g/cm^3 | 数据源记录的“density”字段；应结合本类别中的其他字段使用。 |
| crystal_system | string | - | 数据源记录的“crystal system”字段；应结合本类别中的其他字段使用。 |
| spacegroup_number | integer | - | 数据源记录的“spacegroup number”字段；应结合本类别中的其他字段使用。 |
| spacegroup_symbol | string | - | 数据源记录的“spacegroup symbol”字段；应结合本类别中的其他字段使用。 |
| point_group | string | - | 数据源记录的“point group”字段；应结合本类别中的其他字段使用。 |
| symmetry_precision | float | - | 数据源记录的“symmetry precision”字段；应结合本类别中的其他字段使用。 |
| symmetry_tolerance | float | - | 数据源记录的“symmetry tolerance”字段；应结合本类别中的其他字段使用。 |
| density_atomic | float | varies | 数据源记录的“density atomic”字段；应结合本类别中的其他字段使用。 |

## 计算设置

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| functional | string | - | 数据源记录的“functional”字段；应结合本类别中的其他字段使用。 |
| exchange_correlation | string | - | 数据源记录的“exchange correlation”字段；应结合本类别中的其他字段使用。 |
| pseudopotential | string | - | 数据源记录的“pseudopotential”字段；应结合本类别中的其他字段使用。 |
| basis_set | string | - | 数据源记录的“basis set”字段；应结合本类别中的其他字段使用。 |
| kpoint_mesh | array | - | 数据源记录的“kpoint mesh”字段；应结合本类别中的其他字段使用。 |
| energy_cutoff | float | eV | 数据源记录的“energy cutoff”字段；应结合本类别中的其他字段使用。 |
| smearing | string | - | 数据源记录的“smearing”字段；应结合本类别中的其他字段使用。 |
| spin_polarized | boolean | - | 数据源记录的“spin polarized”字段；应结合本类别中的其他字段使用。 |
| spin_orbit_coupling | boolean | - | 数据源记录的“spin orbit coupling”字段；应结合本类别中的其他字段使用。 |
| hubbard_u | boolean | - | 数据源记录的“hubbard u”字段；应结合本类别中的其他字段使用。 |
| u_values | object | eV | 数据源记录的“u values”字段；应结合本类别中的其他字段使用。 |
| theoretical | boolean | - | 数据源记录的“theoretical”字段；应结合本类别中的其他字段使用。 |
| temperature | float | K | 数据源记录的“temperature”字段；应结合本类别中的其他字段使用。 |
| pressure | float | GPa | 数据源记录的“pressure”字段；应结合本类别中的其他字段使用。 |
| shape_factor | float | - | 数据源记录的“shape factor”字段；应结合本类别中的其他字段使用。 |
| origins | array | object | 数据源记录的“origins”字段；应结合本类别中的其他字段使用。 |
| builder_meta | array | object | 数据源记录的“builder meta”字段；应结合本类别中的其他字段使用。 |

## 能量与稳定性

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| relaxation_status | string | - | 数据源记录的“relaxation status”字段；应结合本类别中的其他字段使用。 |
| total_energy | float | eV | 数据源记录的“total energy”字段；应结合本类别中的其他字段使用。 |
| uncorrected_energy | float | eV | 数据源记录的“uncorrected energy”字段；应结合本类别中的其他字段使用。 |
| energy_per_atom | float | eV/atom | 数据源记录的“energy per atom”字段；应结合本类别中的其他字段使用。 |
| formation_energy | float | eV | 数据源记录的“formation energy”字段；应结合本类别中的其他字段使用。 |
| formation_energy_per_atom | float | eV/atom | 数据源记录的“formation energy per atom”字段；应结合本类别中的其他字段使用。 |
| energy_above_hull | float | eV/atom | 数据源记录的“energy above hull”字段；应结合本类别中的其他字段使用。 |
| decomposition_energy | float | eV/atom | 数据源记录的“decomposition energy”字段；应结合本类别中的其他字段使用。 |
| equilibrium_reaction_energy | float | eV/atom | 数据源记录的“equilibrium reaction energy”字段；应结合本类别中的其他字段使用。 |
| is_stable | boolean | - | 数据源记录的“is stable”字段；应结合本类别中的其他字段使用。 |
| deprecated | boolean | - | 数据源记录的“deprecated”字段；应结合本类别中的其他字段使用。 |
| download_status | string | - | 数据源记录的“download status”字段；应结合本类别中的其他字段使用。 |
| decomposes_to | object | list | 数据源记录的“decomposes to”字段；应结合本类别中的其他字段使用。 |
| deprecation_reasons | array | object | 数据源记录的“deprecation reasons”字段；应结合本类别中的其他字段使用。 |
| uncorrected_energy_per_atom | float | eV/atom | 数据源记录的“uncorrected energy per atom”字段；应结合本类别中的其他字段使用。 |

## 电子结构

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| band_gap | float | eV | 数据源记录的“band gap”字段；应结合本类别中的其他字段使用。 |
| band_gap_type | string | varies | 数据源记录的“band gap type”字段；应结合本类别中的其他字段使用。 |
| is_metal | boolean | - | 数据源记录的“is metal”字段；应结合本类别中的其他字段使用。 |
| is_gap_direct | boolean | varies | 数据源记录的“is gap direct”字段；应结合本类别中的其他字段使用。 |
| cbm | float | eV | 数据源记录的“cbm”字段；应结合本类别中的其他字段使用。 |
| vbm | float | eV | 数据源记录的“vbm”字段；应结合本类别中的其他字段使用。 |
| fermi_level | float | eV | 数据源记录的“fermi level”字段；应结合本类别中的其他字段使用。 |
| band_structure_path | string | path | 能带结构文件的存储路径。 |
| dos_path | string | path | 态密度文件的存储路径。 |
| refractive_index | float | - | 数据源记录的“refractive index”字段；应结合本类别中的其他字段使用。 |
| bandstructure_summary | object | object | 数据源记录的“bandstructure summary”字段；应结合本类别中的其他字段使用。 |
| dos_summary | object | object | 数据源记录的“dos summary”字段；应结合本类别中的其他字段使用。 |
| dos_energy_up | array | eV | 数据源记录的“dos energy up”字段；应结合本类别中的其他字段使用。 |
| dos_energy_down | array | eV | 数据源记录的“dos energy down”字段；应结合本类别中的其他字段使用。 |

## 磁性

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| magnetic_ordering | string | - | 数据源记录的“magnetic ordering”字段；应结合本类别中的其他字段使用。 |
| total_magnetization | float | Bohr magneton | 数据源记录的“total magnetization”字段；应结合本类别中的其他字段使用。 |
| magnetization_per_atom | float | Bohr magneton/atom | 数据源记录的“magnetization per atom”字段；应结合本类别中的其他字段使用。 |
| magnetic_site_count | integer | - | 数据源记录的“magnetic site count”字段；应结合本类别中的其他字段使用。 |
| magnetic_moments | array | - | 数据源记录的“magnetic moments”字段；应结合本类别中的其他字段使用。 |
| is_magnetic | boolean | - | 数据源记录的“is magnetic”字段；应结合本类别中的其他字段使用。 |
| num_unique_magnetic_sites | integer | - | 数据源记录的“num unique magnetic sites”字段；应结合本类别中的其他字段使用。 |
| types_of_magnetic_species | array | list | 数据源记录的“types of magnetic species”字段；应结合本类别中的其他字段使用。 |

## 弹性与力学

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| bulk_modulus_voigt | float | GPa | 数据源记录的“bulk modulus voigt”字段；应结合本类别中的其他字段使用。 |
| bulk_modulus_reuss | float | GPa | 数据源记录的“bulk modulus reuss”字段；应结合本类别中的其他字段使用。 |
| bulk_modulus_vrh | float | GPa | 数据源记录的“bulk modulus vrh”字段；应结合本类别中的其他字段使用。 |
| shear_modulus_voigt | float | GPa | 数据源记录的“shear modulus voigt”字段；应结合本类别中的其他字段使用。 |
| shear_modulus_reuss | float | GPa | 数据源记录的“shear modulus reuss”字段；应结合本类别中的其他字段使用。 |
| shear_modulus_vrh | float | GPa | 数据源记录的“shear modulus vrh”字段；应结合本类别中的其他字段使用。 |
| youngs_modulus | float | GPa | 数据源记录的“youngs modulus”字段；应结合本类别中的其他字段使用。 |
| poisson_ratio | float | varies | 数据源记录的“poisson ratio”字段；应结合本类别中的其他字段使用。 |
| elastic_anisotropy | float | - | 数据源记录的“elastic anisotropy”字段；应结合本类别中的其他字段使用。 |
| elastic_tensor | array | GPa | 数据源记录的“elastic tensor”字段；应结合本类别中的其他字段使用。 |
| elastic_tensor_path | string | path | 弹性张量文件的存储路径。 |

## 介电、压电与表面

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| dielectric_total | float | - | 数据源记录的“dielectric total”字段；应结合本类别中的其他字段使用。 |
| dielectric_ionic | float | - | 数据源记录的“dielectric ionic”字段；应结合本类别中的其他字段使用。 |
| dielectric_electronic | float | - | 数据源记录的“dielectric electronic”字段；应结合本类别中的其他字段使用。 |
| dielectric_tensor | array | - | 数据源记录的“dielectric tensor”字段；应结合本类别中的其他字段使用。 |
| piezoelectric_modulus | float | varies | 数据源记录的“piezoelectric modulus”字段；应结合本类别中的其他字段使用。 |
| piezoelectric_tensor | array | - | 数据源记录的“piezoelectric tensor”字段；应结合本类别中的其他字段使用。 |
| weighted_surface_energy | float | J/m^2 | 数据源记录的“weighted surface energy”字段；应结合本类别中的其他字段使用。 |
| surface_energy | float | J/m^2 | 数据源记录的“surface energy”字段；应结合本类别中的其他字段使用。 |
| surface_anisotropy | float | - | 数据源记录的“surface anisotropy”字段；应结合本类别中的其他字段使用。 |
| weighted_work_function | float | eV | 数据源记录的“weighted work function”字段；应结合本类别中的其他字段使用。 |
| work_function | float | eV | 数据源记录的“work function”字段；应结合本类别中的其他字段使用。 |
| grain_boundaries | object | - | 数据源记录的“grain boundaries”字段；应结合本类别中的其他字段使用。 |
| weighted_surface_energy_ev_per_ang2 | float | eV/Angstrom^2 | 数据源记录的“weighted surface energy ev per ang2”字段；应结合本类别中的其他字段使用。 |

## 声子与热学

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| phonon_band_structure_path | string | path | 声子能带文件的存储路径。 |
| phonon_dos_path | string | path | 声子态密度文件的存储路径。 |
| debye_temperature | float | K | 数据源记录的“debye temperature”字段；应结合本类别中的其他字段使用。 |
| heat_capacity | object | varies | 数据源记录的“heat capacity”字段；应结合本类别中的其他字段使用。 |
| thermal_conductivity | float | varies | 数据源记录的“thermal conductivity”字段；应结合本类别中的其他字段使用。 |

## XAS 与来源追踪

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| xas_path | string | path | XAS 文件的存储路径。 |
| property_paths | object | object | 性质名称到文件路径的映射。 |
| property_errors | object | object | 数据源记录的“property errors”字段；应结合本类别中的其他字段使用。 |
| properties_requested | boolean | - | 数据源记录的“properties requested”字段；应结合本类别中的其他字段使用。 |
| raw_path | string | path | 数据源记录的“raw path”字段；应结合本类别中的其他字段使用。 |
| normalized_path | string | path | 数据源记录的“normalized path”字段；应结合本类别中的其他字段使用。 |
| content_hash | string | - | 用于变化检测和去重的内容哈希。 |
| has_props | object | - | 数据源记录的“has props”字段；应结合本类别中的其他字段使用。 |
| has_reconstructed | boolean | - | 数据源记录的“has reconstructed”字段；应结合本类别中的其他字段使用。 |
| property_name | string | - | 数据源记录的“property name”字段；应结合本类别中的其他字段使用。 |
| warnings | array | object | 数据源记录的“warnings”字段；应结合本类别中的其他字段使用。 |
| xas_summary | object | object | 数据源记录的“xas summary”字段；应结合本类别中的其他字段使用。 |
| source_documents | object | object | 用于构建该记录的原始数据文档。 |
| source_extra | object | object | 未提升为标准字段的来源特有字段。 |

## 其他来源字段

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| atom_count | integer | - | 数据源记录的“atom count”字段；应结合本类别中的其他字段使用。 |
| updated_at | string | - | 数据源记录的“updated at”字段；应结合本类别中的其他字段使用。 |
| last_updated | string | - | 数据源记录的“last updated”字段；应结合本类别中的其他字段使用。 |

## 数据源映射

| 数据源 | 映射文件 |
| --- | --- |
| Materials Project | [mp.yaml](./mp.yaml) |
| AFLOW | [aflow.yaml](./aflow.yaml) |

**合计：142 个字段。**

