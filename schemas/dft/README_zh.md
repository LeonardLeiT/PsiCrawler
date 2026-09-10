# DFT 标准 Schema

本文按 `standard.yaml` 的字段顺序分组说明 DFT 标准记录；机器可读定义见 [standard.yaml](./standard.yaml)。
当前标准 schema 版本为 `1.0`，共 142 个字段。

## 来源与记录元数据

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| source | string | - | 上游数据源名称。 |
| requested_id | string | - | 用户提交给爬虫的查询标识符。 |
| source_id | string | - | 上游数据源分配的稳定标识符。 |
| source_url | string | - | 上游数据库中该材料或记录的规范页面地址。 |

## 组成与身份

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| formula | string | - | 数据源报告的材料化学式。 |
| formula_reduced | string | - | 按最简整数比归一化后的化学式。 |
| chemical_system | string | - | 材料所包含的元素集合，通常按字母顺序用连字符连接。 |
| elements | list[string] | list | 材料中出现的去重元素符号列表。 |
| composition | object | object | 元素到化学计量数量或比例的映射。 |
| element_count | integer | - | 组成中不同元素的数量。 |
| atom_count | integer | - | 结构或计算晶胞中的原子总数。 |

## 结构与晶体学

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| structure | object | object | 可用时保存的解析后晶体结构对象。 |
| structure_path | string | path | 标准结构文件的存储路径。 |
| structure_json_path | string | path | 序列化结构 JSON 的存储路径。 |
| structure_format | list[string] | - | 当前结构数据可用的文件格式或表示格式。 |
| lattice_matrix | array | Angstrom | 定义晶胞的三个晶格矢量。 |
| lattice_a | float | Angstrom | 第一晶格矢量的长度。 |
| lattice_b | float | Angstrom | 第二晶格矢量的长度。 |
| lattice_c | float | Angstrom | 第三晶格矢量的长度。 |
| angle_alpha | float | degree | 第二、第三晶格矢量之间的夹角。 |
| angle_beta | float | degree | 第一、第三晶格矢量之间的夹角。 |
| angle_gamma | float | degree | 第一、第二晶格矢量之间的夹角。 |
| volume | float | Angstrom^3 | 晶胞体积。 |
| density | float | g/cm^3 | 材料的质量密度。 |
| crystal_system | string | - | 晶系分类，例如立方、四方或三斜。 |
| spacegroup_number | integer | - | 结构所属空间群的国际编号。 |
| spacegroup_symbol | string | - | 结构所属空间群的国际或 Hermann-Mauguin 符号。 |
| point_group | string | - | 结构的点群对称性。 |
| symmetry_precision | float | - | 报告对称性时使用的数值精度。 |
| symmetry_tolerance | float | - | 识别对称性时采用的几何距离容差。 |

## 计算设置

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| calculation_method | string | - | 获得该计算结果所采用的高层次方法，例如 DFT 或派生计算流程。 |
| calculation_type | string | - | 记录所代表的具体计算任务或性质计算流程。 |
| code | string | - | 执行计算所使用的电子结构或模拟程序。 |
| code_version | string | - | 计算程序的版本。 |
| functional | string | - | 计算所采用的交换-相关泛函名称。 |
| exchange_correlation | string | - | 计算所采用的交换-相关近似或近似族。 |
| pseudopotential | string | - | 各元素使用的赝势或投影子数据。 |
| basis_set | string | - | 表示电子态所使用的基组定义。 |
| kpoint_mesh | array | - | 布里渊区积分使用的倒空间 k 点采样网格。 |
| energy_cutoff | float | eV | 平面波或基组计算使用的能量截断值。 |
| smearing | string | - | 电子占据数使用的展宽方法或展宽宽度。 |
| spin_polarized | boolean | - | 是否启用自旋极化计算。 |
| spin_orbit_coupling | boolean | - | 是否包含自旋-轨道耦合。 |
| hubbard_u | boolean | - | 是否施加 Hubbard-U 修正。 |
| u_values | object | eV | 按元素或轨道指定的 Hubbard-U 参数。 |
| relaxation_status | string | - | 结构和离子弛豫的状态或结果。 |

## 能量与稳定性

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| total_energy | float | eV | 计算晶胞的总能量。 |
| uncorrected_energy | float | eV | 应用数据源特定修正之前的总能量。 |
| energy_per_atom | float | eV/atom | 按原子数归一化后的总能量。 |
| formation_energy | float | eV | 相对于参考态的晶胞形成能。 |
| formation_energy_per_atom | float | eV/atom | 按原子数归一化后的形成能。 |
| energy_above_hull | float | eV/atom | 材料相对于所属化学体系热力学凸包的能量。 |
| decomposition_energy | float | eV/atom | 材料分解为竞争相时的能量变化。 |
| equilibrium_reaction_energy | float | eV/atom | 数据源定义的平衡反应能变化。 |
| is_stable | boolean | - | 按照数据源判据判断材料是否稳定。 |
| theoretical | boolean | - | 该记录是否被标记为理论预测而非实验确认。 |
| deprecated | boolean | - | 该数据源记录是否已废弃或撤回。 |
| temperature | float | K | 计算或性质对应的温度。 |
| pressure | float | GPa | 计算或性质对应的压力。 |

## 电子结构

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| band_gap | float | eV | 价带顶与导带底之间的电子带隙。 |
| band_gap_type | string | varies | 带隙类型，例如直接带隙或间接带隙。 |
| is_metal | boolean | - | 材料是否被判定为金属。 |
| is_gap_direct | boolean | varies | 基本带隙是否为直接带隙。 |
| cbm | float | eV | 导带底的能量位置。 |
| vbm | float | eV | 价带顶的能量位置。 |
| fermi_level | float | eV | 计算或数据源报告的费米能级。 |
| band_structure_path | string | path | 能带结构文件的存储路径。 |
| dos_path | string | path | 电子态密度数据文件的本地路径。 |

## 磁性

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| magnetic_ordering | string | - | 磁序分类，例如非磁、铁磁或反铁磁。 |
| total_magnetization | float | Bohr magneton | 计算晶胞的总磁化强度。 |
| magnetization_per_atom | float | Bohr magneton/atom | 按原子数归一化后的磁化强度。 |
| magnetic_site_count | integer | - | 带有非零或数据源定义磁矩的原子位点数量。 |
| magnetic_moments | array | - | 按位点、原子或元素记录的磁矩数值。 |

## 弹性与力学性质

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| bulk_modulus_voigt | float | GPa | 体积模量的 Voigt 估计值。 |
| bulk_modulus_reuss | float | GPa | 体积模量的 Reuss 估计值。 |
| bulk_modulus_vrh | float | GPa | 体积模量的 Voigt-Reuss-Hill 平均值。 |
| shear_modulus_voigt | float | GPa | 剪切模量的 Voigt 估计值。 |
| shear_modulus_reuss | float | GPa | 剪切模量的 Reuss 估计值。 |
| shear_modulus_vrh | float | GPa | 剪切模量的 Voigt-Reuss-Hill 平均值。 |
| youngs_modulus | float | GPa | 描述拉伸刚度的杨氏模量。 |
| poisson_ratio | float | varies | 横向应变与轴向应变之比，即泊松比。 |
| elastic_anisotropy | float | - | 材料弹性响应随方向变化的程度。 |
| elastic_tensor | array | GPa | 材料的弹性刚度张量或数据源原生数组表示。 |
| elastic_tensor_path | string | path | 弹性张量文件的存储路径。 |

## 介电、压电与表面性质

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| dielectric_total | float | - | 材料的总静态介电响应。 |
| dielectric_ionic | float | - | 介电响应中的离子贡献。 |
| dielectric_electronic | float | - | 介电响应中的电子贡献。 |
| refractive_index | float | - | 数据源报告的光学折射率。 |
| dielectric_tensor | array | - | 描述方向相关介电响应的张量。 |
| piezoelectric_modulus | float | varies | 数据源报告的压电响应大小。 |
| piezoelectric_tensor | array | - | 描述方向相关压电响应的张量。 |
| weighted_surface_energy | float | J/m^2 | 按数据源定义的晶面方向加权或平均后的表面能。 |
| surface_energy | float | J/m^2 | 形成单位面积材料表面所需的能量。 |
| surface_anisotropy | float | - | 表面能随晶面方向变化的程度。 |
| weighted_work_function | float | eV | 按数据源定义的表面方向加权或平均后的功函数。 |
| work_function | float | eV | 从材料表面移出电子所需的能量。 |
| shape_factor | float | - | 数据源提供的无量纲形状或几何因子。 |

## 声子与热学性质

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| phonon_band_structure_path | string | path | 声子能带结构数据文件的本地路径。 |
| phonon_dos_path | string | path | 声子态密度数据文件的本地路径。 |
| debye_temperature | float | K | 材料的德拜温度。 |
| heat_capacity | object | varies | 热容数据或随温度变化的热容表示。 |
| thermal_conductivity | float | varies | 材料的热导率。 |

## 来源追踪与文件

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| xas_path | string | path | X 射线吸收光谱数据文件的本地路径。 |
| property_paths | object | object | 性质名称到文件路径的映射。 |
| property_errors | object | object | 获取或处理各项性质时产生的错误信息。 |
| download_status | string | - | 记录或相关数据文件的下载状态。 |
| properties_requested | boolean | - | 是否向数据源请求或处理了指定的性质集合。 |
| raw_path | string | path | 原始数据源记录的本地路径。 |
| normalized_path | string | path | 标准化记录的本地路径。 |
| retrieved_at | string | - | 爬虫获取数据源记录的时间。 |
| updated_at | string | - | 标准化或存储记录最近一次更新的时间。 |
| schema_version | string | - | 该记录使用的标准 schema 版本。 |
| api_version | string | - | 提供该记录的数据源 API 或接口版本。 |
| content_hash | string | - | 用于变化检测和去重的内容哈希。 |
| license | string | - | 数据源规定的数据使用或再分发许可。 |
| citation | string | - | 数据源要求或推荐使用的论文、DOI 或引用信息。 |

## 扩展与来源字段

| 字段 | 类型 | 单位 / 格式 | 含义 |
| --- | --- | --- | --- |
| formula_anonymous | string | - | 保留化学计量模式、但用匿名元素替代真实元素名称的化学式。 |
| composition_reduced | object | - | 按最简整数比归一化后的组成映射。 |
| density_atomic | float | varies | 单位体积内的原子数，即原子数密度。 |
| decomposes_to | object | list | 材料分解后预测生成的产物或竞争相。 |
| deprecation_reasons | array | object | 数据源给出的记录废弃原因。 |
| grain_boundaries | object | - | 数据源报告的晶界结构或晶界性质。 |
| has_props | object | - | 数据源对各项请求性质可用性的映射或摘要。 |
| has_reconstructed | boolean | - | 是否存在重构后的结构或记录。 |
| is_magnetic | boolean | - | 该记录对应的材料是否被判定为磁性材料。 |
| last_updated | string | - | 上游数据源报告的最近更新时间。 |
| num_unique_magnetic_sites | integer | - | 对称性不等价的磁性位点数量。 |
| origins | array | object | 材料或性质数据来源的 provenance 记录。 |
| possible_species | array | list | 结构中可能的物种或氧化态候选集合。 |
| property_name | string | - | 该记录或文件所代表的性质名称。 |
| types_of_magnetic_species | array | list | 被识别为携带磁矩的化学物种。 |
| uncorrected_energy_per_atom | float | eV/atom | 未修正总能量按原子数归一化后的值。 |
| warnings | array | object | 数据源或标准化流程产生的警告信息。 |
| weighted_surface_energy_ev_per_ang2 | float | eV/Angstrom^2 | 加权表面能，单位为 eV/平方 Angstrom。 |
| bandstructure_summary | object | object | 电子能带结构的摘要或派生元数据。 |
| dos_summary | object | object | 电子态密度的摘要或派生元数据。 |
| dos_energy_up | array | eV | 自旋向上态密度通道使用的能量网格或能量分辨数据。 |
| dos_energy_down | array | eV | 自旋向下态密度通道使用的能量网格或能量分辨数据。 |
| xas_summary | object | object | X 射线吸收光谱数据的摘要或派生元数据。 |
| builder_meta | array | object | 构建该标准记录的流程生成的元数据。 |
| source_documents | object | object | 用于构建标准记录的原始来源文档。 |
| source_extra | object | object | 未提升为标准字段、但保留的来源特有字段。 |

## 数据源映射

| 数据源 | 映射文件 |
| --- | --- |
| Materials Project | [mp.yaml](./mp.yaml) |
| AFLOW | [aflow.yaml](./aflow.yaml) |

**合计：142 个字段。**




