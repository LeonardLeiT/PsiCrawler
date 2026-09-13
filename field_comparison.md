# DFT 字段对比表：standard.yaml vs Materials Project vs AFLOW

本文件用于对照当前标准字段契约 `normalizers/dft/standard.yaml` 与两个上游官方网站提供的字段，以便挑选需要保留/新增的标准字段。

## 说明

- **去重规则**：当同一物理量在多个来源中出现时，只保留优先级最高的来源，优先级为 `standard` > `MP` > `AFLOW`。判定依据是现有的 `normalizers/dft/mp/mapping.yaml` 与 `normalizers/dft/aflow/mapping.yaml` 映射关系（含归一化过程中的中间别名）。
- **MP 字段范围**：官方 OpenAPI（`https://api.materialsproject.org/openapi.json`）中的 `SummaryDoc` 以及全部材料相关 REST 路由文档，取文档顶层字段并展开一层嵌套对象；跨路由去重后列出未被标准字段覆盖的部分。
- **AFLOW 字段范围**：官方 AFLUX schema（`https://aflow.org/API/aflux/?schema`）中的全部 193 个属性，剔除已被标准字段覆盖的部分。
- **单位**：`—` 表示官方未给出单位，或该字段为字符串/对象/数组等无量纲属性。
- **描述**：`译：` 之后为本文件提供的中文翻译（非官方）；MP/AFLOW 官方字段的英文描述来自官方 schema。标准字段的中文取自 `standard.yaml` 的 `description_zh`。
- `@module` / `@class` / `@version` 等为 pymatgen 序列化内部键，通常无需纳入标准字段。

**统计**：标准字段 115 条，MP 独有字段 368 条，AFLOW 独有字段 153 条，合计 636 条。

## 一、standard 标准字段（`normalizers/dft/standard.yaml`）

| 索引 | 字段（值） | 单位 | 来源 | 描述 |
| ---: | --- | --- | --- | --- |
| 1 | `source` | — | standard | Name of the upstream database or provider.<br>译：上游数据源名称。 |
| 2 | `requested_id` | — | standard | Identifier requested by the user or crawler before source lookup.<br>译：用户提交给爬虫的查询标识符。 |
| 3 | `source_id` | — | standard | Stable identifier assigned to this record by the upstream source.<br>译：上游数据源分配的稳定标识符。 |
| 4 | `source_url` | — | standard | Canonical URL of the upstream record or source page.<br>译：上游数据库中该材料或记录的规范页面地址。 |
| 5 | `formula` | — | standard | Chemical formula of the material in the source representation.<br>译：数据源报告的材料化学式。 |
| 6 | `formula_reduced` | — | standard | Reduced chemical formula normalized to the smallest whole-number ratio.<br>译：按最简整数比归一化后的化学式。 |
| 7 | `chemical_system` | — | standard | Unordered chemical system, usually represented as element symbols joined by hyphens.<br>译：材料所包含的元素集合，通常按字母顺序用连字符连接。 |
| 8 | `elements` | — | standard | Unique chemical elements present in the material.<br>译：材料中出现的去重元素符号列表。 |
| 9 | `element_count` | 1 | standard | Number of distinct chemical elements in the composition.<br>译：组成中不同元素的数量。 |
| 10 | `structure` | — | standard | Parsed crystal structure, including lattice and site information, when available.<br>译：可用时保存的解析后晶体结构对象。 |
| 11 | `structure_path` | — | standard | Local path to the canonical CIF structure artifact stored under data/dft/<source>/structure/<source_id>/<source_id>.cif.<br>译：标准 CIF 结构文件的本地路径，位于 data/dft/<source>/structure/<source_id>/<source_id>.cif。 |
| 12 | `lattice_a` | Angstrom | standard | Length of the first lattice vector.<br>译：第一晶格矢量的长度。 |
| 13 | `lattice_b` | Angstrom | standard | Length of the second lattice vector.<br>译：第二晶格矢量的长度。 |
| 14 | `lattice_c` | Angstrom | standard | Length of the third lattice vector.<br>译：第三晶格矢量的长度。 |
| 15 | `angle_alpha` | degree | standard | Angle between the second and third lattice vectors.<br>译：第二、第三晶格矢量之间的夹角。 |
| 16 | `angle_beta` | degree | standard | Angle between the first and third lattice vectors.<br>译：第一、第三晶格矢量之间的夹角。 |
| 17 | `angle_gamma` | degree | standard | Angle between the first and second lattice vectors.<br>译：第一、第二晶格矢量之间的夹角。 |
| 18 | `volume` | Angstrom^3 | standard | Volume of the unit cell.<br>译：晶胞体积。 |
| 19 | `density` | g/cm^3 | standard | Mass density calculated or reported for the material.<br>译：材料的质量密度。 |
| 20 | `atom_count` | 1 | standard | Total number of atoms in the represented structure or record.<br>译：结构或计算晶胞中的原子总数。 |
| 21 | `crystal_system` | — | standard | Crystal-system classification, such as cubic or triclinic.<br>译：晶系分类，例如立方、四方或三斜。 |
| 22 | `spacegroup_number` | 1 | standard | International space-group number of the structure.<br>译：结构所属空间群的国际编号。 |
| 23 | `spacegroup_symbol` | — | standard | International or Hermann-Mauguin space-group symbol.<br>译：结构所属空间群的国际或 Hermann-Mauguin 符号。 |
| 24 | `point_group` | — | standard | Point-group symmetry of the structure.<br>译：结构的点群对称性。 |
| 25 | `calculation_method` | — | standard | High-level method used to obtain the calculation, such as DFT or a derived workflow.<br>译：获得该计算结果所采用的高层次方法，例如 DFT 或派生计算流程。 |
| 26 | `code` | — | standard | Name of the simulation program used for the calculation, without its version.<br>译：执行计算所使用的模拟程序名称（不含版本）。 |
| 27 | `code_version` | — | standard | Version of the simulation program used.<br>译：计算程序的版本。 |
| 28 | `functional` | — | standard | Named exchange-correlation functional used in the calculation.<br>译：计算所采用的交换-相关泛函名称。 |
| 29 | `kpoint_mesh` | — | standard | Three positive integers for a regular reciprocal-space mesh. Paths or lists of explicit points belong in source artifacts.<br>译：规则倒空间网格的三个正整数；显式 k 点和路径保留在来源文件中。 |
| 30 | `energy_cutoff` | eV | standard | Plane-wave or basis energy cutoff used in the calculation.<br>译：平面波或基组计算使用的能量截断值。 |
| 31 | `total_energy` | eV | standard | Total energy of the calculated cell.<br>译：计算晶胞的总能量。 |
| 32 | `energy_per_atom` | eV/atom | standard | Total energy normalized by the number of atoms.<br>译：按原子数归一化后的总能量。 |
| 33 | `formation_energy` | eV | standard | Formation energy of the calculated cell relative to reference states.<br>译：相对于参考态的晶胞形成能。 |
| 34 | `formation_energy_per_atom` | eV/atom | standard | Formation energy normalized per atom.<br>译：按原子数归一化后的形成能。 |
| 35 | `energy_above_hull` | eV/atom | standard | Energy above the thermodynamic convex hull for the chemical system.<br>译：材料相对于所属化学体系热力学凸包的能量。 |
| 36 | `is_stable` | — | standard | Source classification indicating whether the material is stable under its stated criterion.<br>译：按照数据源判据判断材料是否稳定。 |
| 37 | `theoretical` | — | standard | Whether the record is marked as theoretical rather than experimentally confirmed.<br>译：该记录是否被标记为理论预测而非实验确认。 |
| 38 | `temperature` | K | standard | Temperature associated with the calculation or reported property. Not populated by current adapters; null is required until a producer and its semantics are implemented.<br>译：计算或性质对应的温度。 |
| 39 | `pressure` | GPa | standard | Hydrostatic pressure in GPa; AFLOW reports unrelaxed pressure in kbar, converted by factor 0.1.<br>译：以 GPa 表示的静水压力；AFLOW 的未弛豫压力由 kbar 乘 0.1 转换。 |
| 40 | `band_gap` | eV | standard | Electronic band gap between the valence-band maximum and conduction-band minimum.<br>译：价带顶与导带底之间的电子带隙。 |
| 41 | `band_gap_type` | — | standard | Classification of the band gap, such as direct or indirect.<br>译：带隙类型，例如直接带隙或间接带隙。 |
| 42 | `is_metal` | — | standard | Whether the electronic structure is classified as metallic.<br>译：材料是否被判定为金属。 |
| 43 | `is_gap_direct` | — | standard | Whether the fundamental band gap is direct in reciprocal space.<br>译：基本带隙是否为直接带隙。 |
| 44 | `cbm` | eV | standard | Energy of the conduction-band minimum.<br>译：导带底的能量位置。 |
| 45 | `vbm` | eV | standard | Energy of the valence-band maximum.<br>译：价带顶的能量位置。 |
| 46 | `fermi_level` | eV | standard | Fermi level reported by the calculation or source.<br>译：计算或数据源报告的费米能级。 |
| 47 | `band_structure_path` | — | standard | Local path to the electronic band-structure artifact.<br>译：能带结构文件的存储路径。 |
| 48 | `dos_path` | — | standard | Local path to the electronic density-of-states artifact.<br>译：电子态密度数据文件的本地路径。 |
| 49 | `magnetic_ordering` | — | standard | Magnetic ordering classification, such as nonmagnetic, ferromagnetic, or antiferromagnetic.<br>译：磁序分类，例如非磁、铁磁或反铁磁。 |
| 50 | `total_magnetization` | Bohr magneton | standard | Total magnetization of the calculated cell.<br>译：计算晶胞的总磁化强度。 |
| 51 | `magnetization_per_atom` | Bohr magneton/atom | standard | Total magnetization normalized per atom.<br>译：按原子数归一化后的磁化强度。 |
| 52 | `magnetic_site_count` | 1 | standard | Number of atomic sites carrying a nonzero or source-defined magnetic moment.<br>译：带有非零或数据源定义磁矩的原子位点数量。 |
| 53 | `magnetic_moments` | Bohr magneton | standard | Site-resolved scalar magnetic moments in Bohr magneton, ordered by source atom/site order.<br>译：按位点、原子或元素记录的磁矩数值。 |
| 54 | `bulk_modulus_voigt` | GPa | standard | Voigt estimate of the bulk modulus.<br>译：体积模量的 Voigt 估计值。 |
| 55 | `bulk_modulus_reuss` | GPa | standard | Reuss estimate of the bulk modulus.<br>译：体积模量的 Reuss 估计值。 |
| 56 | `bulk_modulus_vrh` | GPa | standard | Voigt-Reuss-Hill average of the bulk modulus.<br>译：体积模量的 Voigt-Reuss-Hill 平均值。 |
| 57 | `shear_modulus_voigt` | GPa | standard | Voigt estimate of the shear modulus.<br>译：剪切模量的 Voigt 估计值。 |
| 58 | `shear_modulus_reuss` | GPa | standard | Reuss estimate of the shear modulus.<br>译：剪切模量的 Reuss 估计值。 |
| 59 | `shear_modulus_vrh` | GPa | standard | Voigt-Reuss-Hill average of the shear modulus.<br>译：剪切模量的 Voigt-Reuss-Hill 平均值。 |
| 60 | `youngs_modulus` | GPa | standard | Young modulus describing tensile stiffness.<br>译：描述拉伸刚度的杨氏模量。 |
| 61 | `poisson_ratio` | 1 | standard | Poisson ratio describing transverse strain relative to axial strain.<br>译：横向应变与轴向应变之比，即泊松比。 |
| 62 | `elastic_anisotropy` | 1 | standard | Measure of how elastic response varies with direction.<br>译：材料弹性响应随方向变化的程度。 |
| 63 | `elastic_tensor_path` | — | standard | Local path to the elastic-tensor artifact.<br>译：弹性张量文件的存储路径。 |
| 64 | `dielectric_total` | 1 | standard | Source scalar total static relative dielectric response; dimensionless. Scalar averaging convention remains source-specific.<br>译：材料的总静态介电响应。 |
| 65 | `dielectric_ionic` | 1 | standard | Source scalar ionic relative dielectric contribution; dimensionless.<br>译：介电响应中的离子贡献。 |
| 66 | `dielectric_electronic` | 1 | standard | Source scalar electronic relative dielectric contribution; dimensionless.<br>译：介电响应中的电子贡献。 |
| 67 | `refractive_index` | 1 | standard | Optical refractive index reported by the source.<br>译：数据源报告的光学折射率。 |
| 68 | `piezoelectric_modulus` | C/m^2 | standard | Maximum piezoelectric stress response magnitude from MP e_ij_max, in C/m^2.<br>译：MP e_ij_max 对应的压电应力响应最大值，单位 C/m^2。 |
| 69 | `piezoelectric_tensor` | C/m^2 | standard | Piezoelectric stress tensor in C/m^2, 3 by 6 in Voigt notation. Reserved: no current producer. Not populated by current adapters; null is required until a producer and its semantics are implemented.<br>译：3×6 Voigt 表示的压电应力张量，单位 C/m^2；当前未实现。 |
| 70 | `weighted_surface_energy` | J/m^2 | standard | Surface-orientation-weighted energy in J/m^2. MP eV/Angstrom^2 is converted and cross-checked; weighting is source-defined.<br>译：按数据源定义的晶面方向加权或平均后的表面能。 |
| 71 | `surface_anisotropy` | 1 | standard | Directional variation of surface energy.<br>译：表面能随晶面方向变化的程度。 |
| 72 | `weighted_work_function` | eV | standard | Surface-orientation-weighted work function in eV; weighting is source-defined.<br>译：按数据源定义的表面方向加权或平均后的功函数。 |
| 73 | `shape_factor` | 1 | standard | Dimensionless shape or geometric factor supplied by the source.<br>译：数据源提供的无量纲形状或几何因子。 |
| 74 | `phonon_band_structure_path` | — | standard | Local path to the phonon band-structure artifact.<br>译：声子能带结构数据文件的本地路径。 |
| 75 | `phonon_dos_path` | — | standard | Local path to the phonon density-of-states artifact.<br>译：声子态密度数据文件的本地路径。 |
| 76 | `debye_temperature` | K | standard | Debye temperature derived or reported for the material.<br>译：材料的德拜温度。 |
| 77 | `thermal_conductivity` | W/(m*K) | standard | Lattice thermal conductivity. The current AFLOW adapter supplies the AGL scalar at 300 K; do not compare at other temperatures without source metadata.<br>译：晶格热导率；当前 AFLOW 提供 AGL 的 300 K 标量，比较时应检查温度与来源。 |
| 78 | `xas_path` | — | standard | Local path to the X-ray absorption spectroscopy artifact. Not populated by current adapters; null is required until a producer and its semantics are implemented.<br>译：X 射线吸收光谱数据文件的本地路径。 |
| 79 | `property_paths` | — | standard | Mapping from property names to local artifact paths.<br>译：性质名称到文件路径的映射。 |
| 80 | `property_errors` | — | standard | Errors encountered while retrieving or processing individual properties.<br>译：获取或处理各项性质时产生的错误信息。 |
| 81 | `download_status` | — | standard | Pipeline outcome after artifact retrieval; success does not imply every physical property exists.<br>译：记录或相关数据文件的下载状态。 |
| 82 | `properties_requested` | — | standard | Whether optional property or artifact retrieval was requested in this run.<br>译：此次是否请求了额外属性或文件下载。 |
| 83 | `raw_path` | — | standard | Local path to the raw source record.<br>译：原始数据源记录的本地路径。 |
| 84 | `retrieved_at` | — | standard | Time when the source record was retrieved by the crawler.<br>译：爬虫获取数据源记录的时间。 |
| 85 | `updated_at` | — | standard | Source or pipeline last-update string. Legacy AFLOW date text is preserved, so this field has no strict date-time format.<br>译：标准化或存储记录最近一次更新的时间。 |
| 86 | `schema_version` | — | standard | Version of the normalized DFT schema used for this record.<br>译：该记录使用的标准 schema 版本。 |
| 87 | `api_version` | — | standard | Version of the upstream API or endpoint that supplied the record.<br>译：提供该记录的数据源 API 或接口版本。 |
| 88 | `content_hash` | — | standard | SHA-256 of raw JSON serialized with sorted keys, UTF-8, no ASCII escaping and compact separators; excludes normalized pipeline metadata.<br>译：对原始 JSON 按键排序、紧凑 UTF-8 编码计算 SHA-256；不包含归一化流程元数据。 |
| 89 | `license` | — | standard | Upstream reuse license, when explicitly supplied; never inferred from missing data. Not populated by current adapters; null is required until a producer and its semantics are implemented.<br>译：数据源规定的数据使用或再分发许可。 |
| 90 | `citation` | — | standard | Upstream recommended citation or DOI, when explicitly supplied. Not populated by current adapters; null is required until a producer and its semantics are implemented.<br>译：数据源要求或推荐使用的论文、DOI 或引用信息。 |
| 91 | `formula_anonymous` | — | standard | Anonymous formula that preserves stoichiometric pattern while replacing element names.<br>译：保留化学计量模式、但用匿名元素替代真实元素名称的化学式。 |
| 92 | `composition_reduced` | — | standard | Element amounts reduced to the smallest stoichiometric ratio, independent of the represented cell atom count.<br>译：按最简整数比归一化后的组成映射。 |
| 93 | `density_atomic` | atom/Angstrom^3 | standard | Atomic number density, computed as atom_count / cell volume in atom/Angstrom^3. MP density_atomic is not copied because its implementation and documentation disagree.<br>译：原子数密度，由原子数除以晶胞体积计算；不直接复制定义与实现不一致的 MP 同名值。 |
| 94 | `decomposes_to` | — | standard | Decomposition products with source material identifier, formula and amount in formula units. Applicable to unstable or metastable materials.<br>译：分解产物列表，包含来源材料编号、化学式及以化学式单元计的量。 |
| 95 | `deprecation_reasons` | — | standard | Reasons supplied by the source for deprecating the record.<br>译：数据源给出的记录废弃原因。 |
| 96 | `grain_boundaries` | — | standard | Grain-boundary structures or properties reported by the source.<br>译：数据源报告的晶界结构或晶界性质。 |
| 97 | `has_props` | — | standard | Source-level availability map or summary for requested properties.<br>译：数据源对各项请求性质可用性的映射或摘要。 |
| 98 | `has_reconstructed` | — | standard | Whether any of the material's calculated surfaces are reconstructed.<br>译：材料的已计算表面是否包含重构表面。 |
| 99 | `is_magnetic` | — | standard | Whether the record is classified as magnetic.<br>译：该记录对应的材料是否被判定为磁性材料。 |
| 100 | `last_updated` | — | standard | Last-update timestamp reported by the upstream source.<br>译：上游数据源报告的最近更新时间。 |
| 101 | `num_unique_magnetic_sites` | 1 | standard | Number of symmetry-unique magnetic sites.<br>译：对称性不等价的磁性位点数量。 |
| 102 | `origins` | — | standard | Provenance records describing where the material or property data originated.<br>译：材料或性质数据来源的 provenance 记录。 |
| 103 | `possible_species` | — | standard | Species or oxidation-state candidates considered possible for the structure.<br>译：结构中可能的物种或氧化态候选集合。 |
| 104 | `property_name` | — | standard | Name of the property represented by the record or artifact.<br>译：该记录或文件所代表的性质名称。 |
| 105 | `types_of_magnetic_species` | — | standard | Chemical species identified as carrying magnetic moments.<br>译：被识别为携带磁矩的化学物种。 |
| 106 | `uncorrected_energy_per_atom` | eV/atom | standard | Uncorrected total energy normalized per atom.<br>译：未修正总能量按原子数归一化后的值。 |
| 107 | `warnings` | — | standard | Warnings emitted by the source or normalization pipeline.<br>译：数据源或标准化流程产生的警告信息。 |
| 108 | `bandstructure_summary` | — | standard | Provider-specific band-structure metadata; complete data are referenced by property_paths or band_structure_path.<br>译：电子能带结构的摘要或派生元数据。 |
| 109 | `dos_summary` | — | standard | Provider-specific DOS metadata; complete data are referenced by property_paths or dos_path.<br>译：电子态密度的摘要或派生元数据。 |
| 110 | `dos_energy_up` | eV | standard | Spin-up DOS band gap, a scalar energy; not a DOS energy grid.<br>译：自旋向上 DOS 带隙，单位 eV，为标量而非能量网格。 |
| 111 | `dos_energy_down` | eV | standard | Spin-down DOS band gap, a scalar energy; not a DOS energy grid.<br>译：自旋向下 DOS 带隙，单位 eV，为标量而非能量网格。 |
| 112 | `xas_summary` | — | standard | List of MP XAS summary entries; route documents are referenced by property_paths.<br>译：MP XAS 摘要条目列表；详细数据通过 property_paths 引用。 |
| 113 | `builder_meta` | — | standard | Source-native builder metadata object. Keys are provider-specific and preserved for provenance.<br>译：来源构建流程元数据对象；内部键采用来源自己的定义。 |
| 114 | `source_documents` | — | standard | Raw source documents used to build the normalized record.<br>译：用于构建标准记录的原始来源文档。 |
| 115 | `source_extra` | — | standard | Unmapped upstream or adapter-enriched values, retained with source-specific semantics; excluded from cross-source equivalence claims.<br>译：未提升为标准字段、但保留的来源特有字段。 |

## 二、MP 官方独有字段（Summary + 全部材料 REST 路由，未纳入标准）

| 索引 | 字段（值） | 单位 | 来源 | 描述 |
| ---: | --- | --- | --- | --- |
| 116 | `_norients` | — | MP | Number of possible surface orientations for the substrate.<br>译：衬底可能的表面取向数量。 |
| 117 | `absorbing_element` | — | MP | Absoring element.<br>译：吸收元素。 |
| 118 | `absorption_coefficient` | — | MP | Absorption coefficient in cm^-1<br>译：吸收系数，单位 cm^-1。 |
| 119 | `adj_pairs` | — | MP | Returns all of the voltage steps material pairs.<br>译：所有电压步对应的材料对。 |
| 120 | `alloy_pair` | — | MP | 译：合金对信息对象。 |
| 121 | `alloy_pair.@class` | — | MP | 译：合金对对象的序列化类键。 |
| 122 | `alloy_pair.@module` | — | MP | 译：合金对对象的序列化模块键。 |
| 123 | `alloy_pair.@version` | — | MP | 译：合金对对象的序列化版本键。 |
| 124 | `alloy_pair.alloy_oxidation_state` | — | MP | 译：合金的氧化态。 |
| 125 | `alloy_pair.alloying_element_a` | — | MP | 译：组元 A 的合金化元素。 |
| 126 | `alloy_pair.alloying_element_b` | — | MP | 译：组元 B 的合金化元素。 |
| 127 | `alloy_pair.alloying_species_a` | — | MP | 译：组元 A 的合金化物种。 |
| 128 | `alloy_pair.alloying_species_b` | — | MP | 译：组元 B 的合金化物种。 |
| 129 | `alloy_pair.anions_a` | — | MP | 译：组元 A 的阴离子。 |
| 130 | `alloy_pair.anions_b` | — | MP | 译：组元 B 的阴离子。 |
| 131 | `alloy_pair.anonymous_formula` | — | MP | 译：合金对的匿名化学式。 |
| 132 | `alloy_pair.cations_a` | — | MP | 译：组元 A 的阳离子。 |
| 133 | `alloy_pair.cations_b` | — | MP | 译：组元 B 的阳离子。 |
| 134 | `alloy_pair.chemsys` | — | MP | 译：合金对的化学体系。 |
| 135 | `alloy_pair.formula_a` | — | MP | 译：合金组元 A 的化学式。 |
| 136 | `alloy_pair.formula_b` | — | MP | 译：合金组元 B 的化学式。 |
| 137 | `alloy_pair.id_a` | — | MP | 译：合金组元 A 的材料编号。 |
| 138 | `alloy_pair.id_b` | — | MP | 译：合金组元 B 的材料编号。 |
| 139 | `alloy_pair.isoelectronic` | — | MP | 译：是否为等电子合金对。 |
| 140 | `alloy_pair.lattice_parameters_a` | — | MP | 译：组元 A 的晶格参数。 |
| 141 | `alloy_pair.lattice_parameters_b` | — | MP | 译：组元 B 的晶格参数。 |
| 142 | `alloy_pair.members` | — | MP | 译：构成合金对的成员。 |
| 143 | `alloy_pair.nelements` | — | MP | 译：合金对的元素数量。 |
| 144 | `alloy_pair.observer_elements` | — | MP | 译：用于观察的元素。 |
| 145 | `alloy_pair.observer_species` | — | MP | 译：用于观察的物种。 |
| 146 | `alloy_pair.pair_formula` | — | MP | 译：合金对化学式。 |
| 147 | `alloy_pair.pair_id` | — | MP | 译：合金对编号。 |
| 148 | `alloy_pair.properties_a` | — | MP | 译：组元 A 的性质。 |
| 149 | `alloy_pair.properties_b` | — | MP | 译：组元 B 的性质。 |
| 150 | `alloy_pair.spacegroup_intl_number_a` | — | MP | 译：组元 A 的国际空间群编号。 |
| 151 | `alloy_pair.spacegroup_intl_number_b` | — | MP | 译：组元 B 的国际空间群编号。 |
| 152 | `alloy_pair.structure_a` | — | MP | 译：合金组元 A 的结构。 |
| 153 | `alloy_pair.structure_b` | — | MP | 译：合金组元 B 的结构。 |
| 154 | `alloy_pair.volume_cube_root_a` | — | MP | 译：组元 A 体积的立方根。 |
| 155 | `alloy_pair.volume_cube_root_b` | — | MP | 译：组元 B 体积的立方根。 |
| 156 | `area` | — | MP | Minimum coincident interface area in Å².<br>译：最小共格界面面积，单位 Å²。 |
| 157 | `authors` | — | MP | list of authors for this material<br>译：该材料的作者列表。 |
| 158 | `average_imaginary_dielectric` | — | MP | Imaginary part of the dielectric function corresponding to the energies<br>译：与能量对应的介电函数虚部。 |
| 159 | `average_oxidation_states` | — | MP | Average oxidation states for each unique species.<br>译：各不同种类的平均氧化态。 |
| 160 | `average_real_dielectric` | — | MP | Real part of the dielectric function corresponding to the energies<br>译：与能量对应的介电函数实部。 |
| 161 | `average_voltage` | — | MP | The average voltage in V for a particular voltage step.<br>译：特定电压步的平均电压，单位 V。 |
| 162 | `bandgap` | — | MP | The electronic band gap<br>译：电子带隙。 |
| 163 | `batch_id` | — | MP | Identifier for this calculation; should provide rough information about the calculation origin and purpose.<br>译：该计算的标识符，粗略说明计算来源与用途。 |
| 164 | `battery_formula` | — | MP | Reduced formula with working ion range produced by combining the charge and discharge formulas.<br>译：由充电与放电化学式合并得到的含工作离子范围的简约化学式。 |
| 165 | `battery_type` | — | MP | The type of battery (insertion or conversion).<br>译：电池类型（嵌入型或转换型）。 |
| 166 | `bond_length_stats` | — | MP | Dictionary of statistics of bonds in structure<br>译：结构中共价键长度的统计信息。 |
| 167 | `bond_length_stats.all_weights` | — | MP | 译：全部键的权重。 |
| 168 | `bond_length_stats.max` | — | MP | 译：键长最大值。 |
| 169 | `bond_length_stats.mean` | — | MP | 译：键长平均值。 |
| 170 | `bond_length_stats.min` | — | MP | 译：键长最小值。 |
| 171 | `bond_length_stats.variance` | — | MP | 译：键长方差。 |
| 172 | `bond_types` | — | MP | Dictionary of bond types to their length, e.g. a Fe-O to a list of the lengths of Fe-O bonds in Angstrom.<br>译：键类型到其长度的映射，例如 Fe-O 键的长度列表（Å）。 |
| 173 | `born` | — | MP | Born charges, only for symmetrically inequivalent atoms<br>译：Born 电荷，仅针对对称性不等价原子。 |
| 174 | `calc_meta` | — | MP | Metadata for individual calculations used to build this document.<br>译：构建该文档所用各计算的元数据。 |
| 175 | `calc_type` | — | MP | The functional and task type used in the calculation.<br>译：计算所用的泛函与任务类型。 |
| 176 | `calc_types` | — | MP | Calculation types for all the calculations that make up this material<br>译：构成该材料的所有计算的类型。 |
| 177 | `capacity_grav` | — | MP | Gravimetric capacity in mAh/g.<br>译：质量比容量，单位 mAh/g。 |
| 178 | `capacity_vol` | — | MP | Volumetric capacity in mAh/cc.<br>译：体积比容量，单位 mAh/cc。 |
| 179 | `chemenv_iucr` | — | MP | List of symbols for unique (cationic) species in structure in IUCR format<br>译：结构中各（阳离子）物种的 IUCR 格式符号。 |
| 180 | `chemenv_iupac` | — | MP | List of symbols for unique (cationic) species in structure in IUPAC format<br>译：结构中各（阳离子）物种的 IUPAC 格式符号。 |
| 181 | `chemenv_name` | — | MP | List of text description of coordination environment for unique (cationic) species in structure.<br>译：结构中各（阳离子）物种配位环境的文字描述。 |
| 182 | `chemenv_name_with_alternatives` | — | MP | List of text description of coordination environment including alternative descriptions for unique (cationic) species in structure.<br>译：结构中各（阳离子）物种配位环境的文字描述（含备选描述）。 |
| 183 | `chemenv_symbol` | — | MP | List of ChemEnv symbols for unique (cationic) species in structure<br>译：结构中各（阳离子）物种的 ChemEnv 符号。 |
| 184 | `code` | — | MP | String describing the code for the computation.<br>译：描述计算所用程序代码的字符串。 |
| 185 | `completed_at` | — | MP | Timestamp for when this task was completed<br>译：该任务完成的时间戳。 |
| 186 | `compliance_tensor` | — | MP | Compliance tensor<br>译：柔度张量。 |
| 187 | `compliance_tensor.ieee_format` | — | MP | Compliance tensor corresponding to IEEE orientation (TPa^-1)<br>译：对应 IEEE 取向的柔度张量（TPa^-1）。 |
| 188 | `compliance_tensor.raw` | — | MP | Compliance tensor corresponding to structure orientation (TPa^-1)<br>译：对应结构取向的柔度张量（TPa^-1）。 |
| 189 | `composition` | — | MP | Full composition for the material.<br>译：材料的完整组成（元素到化学计量量的映射）。 |
| 190 | `condensed_structure` | — | MP | Model for data in the condensed structure robocrystallographer field More details: https://hackingmaterials.lbl.gov/robocrystallographer/format.html<br>译：Robocrystallographer 精简结构字段的数据模型。 |
| 191 | `condensed_structure.crystal_system` | — | MP | Crystal system of the material.<br>译：材料的晶系。 |
| 192 | `condensed_structure.dimensionality` | — | MP | Dimensionality of the material.<br>译：材料的维度。 |
| 193 | `condensed_structure.formula` | — | MP | Formula for the material.<br>译：材料的化学式。 |
| 194 | `condensed_structure.mineral` | — | MP | Model for mineral data in the condensed structure robocrystallographer field<br>译：精简结构字段中矿物数据的数据模型。 |
| 195 | `condensed_structure.spg_symbol` | — | MP | Space group symbol of the material.<br>译：材料的空间群符号。 |
| 196 | `coordination_envs` | — | MP | List of co-ordination environments, e.g. ['Mo-S(6)', 'S-Mo(3)'].<br>译：配位环境列表，例如 ['Mo-S(6)', 'S-Mo(3)']。 |
| 197 | `coordination_envs_anonymous` | — | MP | List of co-ordination environments without elements present, e.g. ['A-B(6)', 'A-B(3)'].<br>译：不含元素名的配位环境列表，例如 ['A-B(6)', 'A-B(3)']。 |
| 198 | `created_at` | — | MP | Timestamp for when this material document was first created.<br>译：该材料文档首次创建的时间戳。 |
| 199 | `csm` | — | MP | Saves the continous symmetry measures for unique (cationic) species in structure<br>译：结构中各（阳离子）物种的连续对称性度量。 |
| 200 | `database_IDs` | — | MP | External database IDs corresponding to this material.<br>译：该材料对应的外部数据库编号。 |
| 201 | `decomposition_enthalpy` | — | MP | Decomposition enthalpy as defined by `get_decomp_and_phase_separation_energy` in pymatgen.<br>译：按 pymatgen `get_decomp_and_phase_separation_energy` 定义的分解焓。 |
| 202 | `decomposition_enthalpy_decomposes_to` | — | MP | List of decomposition data associated with the decomposition_enthalpy quantity.<br>译：与分解焓量相关的分解产物数据。 |
| 203 | `density_atomic` | — | MP | The atomic packing density in Å³/atom.<br>译：原子堆积密度，单位 Å³/atom。 |
| 204 | `deprecated` | — | MP | Whether this property document is deprecated.<br>译：该材料记录是否已被废弃或撤回。 |
| 205 | `deprecated_tasks` | — | MP | 译：已废弃的计算任务。 |
| 206 | `description` | — | MP | Description text from robocrytallographer.<br>译：来自 Robocrystallographer 的描述文本。 |
| 207 | `dir_name` | — | MP | The directory for this VASP task<br>译：该 VASP 任务所在目录。 |
| 208 | `edge` | — | MP | The interaction edge for XAS.<br>译：XAS 的吸收边。 |
| 209 | `elastic_tensor` | — | MP | Elastic tensor<br>译：弹性张量。 |
| 210 | `elastic_tensor.ieee_format` | GPa | MP | Elastic tensor corresponding to IEEE orientation (GPa)<br>译：对应 IEEE 取向的弹性张量（GPa）。 |
| 211 | `elastic_tensor.raw` | GPa | MP | Elastic tensor corresponding to structure orientation (GPa)<br>译：对应结构取向的弹性张量（GPa）。 |
| 212 | `electrode_object` | — | MP | The Pymatgen conversion electrode object.<br>译：Pymatgen 转换电极对象。 |
| 213 | `electronic` | — | MP | Electronic contribution to dielectric tensor.<br>译：介电张量的电子贡献。 |
| 214 | `energies` | eV | MP | Absorption energy in eV starting from 0<br>译：从 0 开始的吸收能量，单位 eV。 |
| 215 | `energy` | — | MP | Elastic energy in meV.<br>译：弹性能量，单位 meV。 |
| 216 | `energy_grav` | — | MP | Gravimetric energy (Specific energy) in Wh/kg.<br>译：质量比能量（比能量），单位 Wh/kg。 |
| 217 | `energy_max` | — | MP | Maximum energy<br>译：最大能量。 |
| 218 | `energy_type` | — | MP | The type of calculation this energy evaluation comes from.<br>译：该能量评估所来自的计算类型。 |
| 219 | `energy_uncertainy_per_atom` | — | MP | 译：每原子能量的不确定度。 |
| 220 | `energy_vol` | — | MP | Volumetric energy (Energy Density) in Wh/l.<br>译：体积能量密度，单位 Wh/l。 |
| 221 | `entries` | — | MP | Dictionary for tracking entries for VASP calculations<br>译：用于追踪 VASP 计算条目的字典。 |
| 222 | `entries.GGA` | — | MP | 译：GGA 泛函下的计算条目。 |
| 223 | `entries.GGA+U` | — | MP | 译：GGA+U 泛函下的计算条目。 |
| 224 | `entries.HSE06` | — | MP | 译：HSE06 泛函下的计算条目。 |
| 225 | `entries.PBEsol` | — | MP | 译：PBEsol 泛函下的计算条目。 |
| 226 | `entries.SCAN` | — | MP | 译：SCAN 泛函下的计算条目。 |
| 227 | `entries.r2SCAN` | — | MP | 译：r2SCAN 泛函下的计算条目。 |
| 228 | `entries_composition_summary` | — | MP | Composition summary data for all material entries associated with this electrode. Included to enable better searching via the API.<br>译：与该电极关联的全部材料条目的组成摘要。 |
| 229 | `entries_composition_summary.all_chemsys` | — | MP | Chemical systems for material entries across all voltage pairs.<br>译：所有电压对材料条目的化学体系。 |
| 230 | `entries_composition_summary.all_composition_reduced` | — | MP | Composition reduced data for entries across all voltage pairs.<br>译：所有电压对条目的最简组成数据。 |
| 231 | `entries_composition_summary.all_elements` | — | MP | Elements in material entries across all voltage pairs.<br>译：所有电压对材料条目中的元素。 |
| 232 | `entries_composition_summary.all_formula_anonymous` | — | MP | Anonymous formulas for material entries across all voltage pairs.<br>译：所有电压对材料条目的匿名化学式。 |
| 233 | `entries_composition_summary.all_formulas` | — | MP | Reduced formulas for material entries across all voltage pairs.<br>译：所有电压对材料条目的简约化学式。 |
| 234 | `entry` | — | MP | Computed structure entry for the calculation associated with the task doc.<br>译：与该任务文档关联的计算所对应的结构条目。 |
| 235 | `entry_types` | — | MP | List of available energy types computed for this material.<br>译：为该材料计算得到的可用能量类型列表。 |
| 236 | `eos` | — | MP | Data for each type of equation of state.<br>译：各类型状态方程的数据。 |
| 237 | `epsilon_electronic` | — | MP | The electronic contribution to the high-frequency dielectric constant.<br>译：高频介电常数的电子贡献。 |
| 238 | `epsilon_static` | — | MP | The high-frequency dielectric constant.<br>译：高频介电常数。 |
| 239 | `equilibrium_reaction_energy_per_atom` | eV | MP | The reaction energy of a stable entry from the neighboring equilibrium stable materials in eV. Also known as the inverse distance to hull.<br>译：稳定条目相对相邻平衡稳定材料的反应能（离凸包的反距离），单位 eV/atom。 |
| 240 | `exchange_symmetry` | — | MP | Exchange symmetry.<br>译：交换对称性。 |
| 241 | `feature_vector` | — | MP | The feature / embedding vector of the structure.<br>译：结构的特征/嵌入向量。 |
| 242 | `film_id` | — | MP | The Materials Project ID of the film material. This comes in the form: mp-******.<br>译：薄膜材料的 Materials Project 编号，形如 mp-******。 |
| 243 | `film_orient` | — | MP | Surface orientation of the film material.<br>译：薄膜材料的表面取向。 |
| 244 | `final_structure` | — | MP | Final grain boundary structure.<br>译：最终晶界结构。 |
| 245 | `final_structure.@class` | — | MP | 译：最终晶界结构的序列化类键。 |
| 246 | `final_structure.@module` | — | MP | 译：最终晶界结构的序列化模块键。 |
| 247 | `final_structure.ab_shift` | — | MP | 译：最终晶界结构的 a/b 方向平移。 |
| 248 | `final_structure.gb_plane` | — | MP | 译：最终晶界结构的晶界面。 |
| 249 | `final_structure.init_cell` | — | MP | 译：最终晶界结构的初始晶胞。 |
| 250 | `final_structure.join_plane` | — | MP | 译：最终晶界结构的连接面。 |
| 251 | `final_structure.lattice` | — | MP | 译：最终晶界结构的晶格。 |
| 252 | `final_structure.oriented_unit_cell` | — | MP | 译：最终晶界结构的取向单胞。 |
| 253 | `final_structure.rotation_angle` | — | MP | 译：最终晶界结构的旋转角。 |
| 254 | `final_structure.rotation_axis` | — | MP | 译：最终晶界结构的旋转轴。 |
| 255 | `final_structure.sites` | — | MP | 译：最终晶界结构的位点。 |
| 256 | `final_structure.vacuum_thickness` | — | MP | 译：最终晶界结构的真空层厚度。 |
| 257 | `fitting_data` | — | MP | Data used to fit the elastic tensor. Note, this only consists of the explicitly calculated primary data. With the data here, one can redo the fitting to regenerate the elastic data, e.g. using `ElasticityDoc.from_deformations_and_stresses()`.<br>译：用于拟合弹性张量的数据。 |
| 258 | `fitting_data.cauchy_stresses` | — | MP | Cauchy stress tensors on strained structures<br>译：应变结构上的 Cauchy 应力张量。 |
| 259 | `fitting_data.deformation_dir_names` | — | MP | Paths to the running directories of deformation tasks<br>译：形变任务运行目录的路径。 |
| 260 | `fitting_data.deformation_tasks` | — | MP | Deformation task ids corresponding to the strained structures<br>译：与应变结构对应的形变任务 ID。 |
| 261 | `fitting_data.deformations` | — | MP | Deformations corresponding to the strained structures<br>译：与应变结构对应的形变。 |
| 262 | `fitting_data.equilibrium_cauchy_stress` | — | MP | Cauchy stress tensor of the relaxed structure<br>译：弛豫结构的 Cauchy 应力张量。 |
| 263 | `fitting_data.num_total_strain_stress_states` | — | MP | Number of total strain--stress states used for fitting, i.e. the sum of explicitly calculated deformations and derived deformations from symmetry.<br>译：用于拟合的应变-应力状态总数（显式形变与对称性导出形变之和）。 |
| 264 | `fitting_data.optimization_dir_name` | — | MP | Path to the running directory of the optimization task<br>译：优化任务运行目录的路径。 |
| 265 | `fitting_data.optimization_task` | — | MP | Optimization task corresponding to the relaxed structure<br>译：与弛豫结构对应的优化任务。 |
| 266 | `fitting_data.second_pk_stresses` | — | MP | Second Piola-Kirchhoff stress tensors on structures<br>译：结构上的第二 Piola-Kirchhoff 应力张量。 |
| 267 | `fitting_data.strains` | — | MP | Lagrangian strain tensors applied to structures<br>译：施加于结构的 Lagrangian 应变张量。 |
| 268 | `fitting_method` | — | MP | Method used to fit the elastic tensor<br>译：拟合弹性张量的方法。 |
| 269 | `force_constants` | — | MP | Force constants between every pair of atoms in the structure<br>译：结构中每一对原子之间的力常数。 |
| 270 | `formula_charge` | — | MP | The chemical formula of the charged material.<br>译：充电态材料的化学式。 |
| 271 | `formula_discharge` | — | MP | The chemical formula of the discharged material.<br>译：放电态材料的化学式。 |
| 272 | `formula_units` | — | MP | Formula units per cell.<br>译：每个晶胞的化学式单元数。 |
| 273 | `fracA_charge` | — | MP | Atomic fraction of the working ion in the charged state.<br>译：充电态工作离子的原子分数。 |
| 274 | `fracA_discharge` | — | MP | Atomic fraction of the working ion in the discharged state.<br>译：放电态工作离子的原子分数。 |
| 275 | `framework` | — | MP | The chemical compositions of the host framework.<br>译：主体框架的化学组成。 |
| 276 | `framework_formula` | — | MP | The id for this battery document.<br>译：该电池文档的编号。 |
| 277 | `gb_energy` | J/m^2 | MP | Grain boundary energy in J/m^2.<br>译：晶界能，单位 J/m²。 |
| 278 | `gb_plane` | — | MP | Grain boundary plane.<br>译：晶界面。 |
| 279 | `history` | — | MP | list of history nodes specifying the transformations or orignation of this material for the entry closest matching the material input<br>译：描述该材料变换或来源的历史节点列表。 |
| 280 | `host_structure` | — | MP | Host structure (structure without the working ion).<br>译：主体结构（不含工作离子的结构）。 |
| 281 | `host_structure.@class` | — | MP | 译：主体结构的序列化类键。 |
| 282 | `host_structure.@module` | — | MP | 译：主体结构的序列化模块键。 |
| 283 | `host_structure.charge` | — | MP | 译：主体结构的电荷。 |
| 284 | `host_structure.lattice` | — | MP | 译：主体结构的晶格。 |
| 285 | `host_structure.properties` | — | MP | 译：主体结构的性质。 |
| 286 | `host_structure.sites` | — | MP | 译：主体结构的位点。 |
| 287 | `icsd_id` | — | MP | Inorganic Crystal Structure Database id of the structure<br>译：结构的无机晶体结构数据库（ICSD）编号。 |
| 288 | `id_charge` | — | MP | The Materials Project ID of the charged structure.<br>译：充电态结构的 Materials Project 编号。 |
| 289 | `id_discharge` | — | MP | The Materials Project ID of the discharged structure.<br>译：放电态结构的 Materials Project 编号。 |
| 290 | `identifier` | — | MP | The identifier of this phonon analysis task.<br>译：该声子分析任务的标识符。 |
| 291 | `ieee_format` | — | MP | Compliance tensor corresponding to IEEE orientation (TPa^-1)<br>译：对应 IEEE 取向的柔度张量（TPa^-1）。 |
| 292 | `initial_comp_formula` | — | MP | The starting composition for the ConversionElectrode represented as a string/formula.<br>译：转换电极的起始组成（以化学式字符串表示）。 |
| 293 | `initial_structure` | — | MP | Initial grain boundary structure.<br>译：初始晶界结构。 |
| 294 | `initial_structure.@class` | — | MP | 译：初始晶界结构的序列化类键。 |
| 295 | `initial_structure.@module` | — | MP | 译：初始晶界结构的序列化模块键。 |
| 296 | `initial_structure.ab_shift` | — | MP | 译：初始晶界结构的 a/b 方向平移。 |
| 297 | `initial_structure.gb_plane` | — | MP | 译：初始晶界结构的晶界面。 |
| 298 | `initial_structure.init_cell` | — | MP | 译：初始晶界结构的初始晶胞。 |
| 299 | `initial_structure.join_plane` | — | MP | 译：初始晶界结构的连接面。 |
| 300 | `initial_structure.lattice` | — | MP | 译：初始晶界结构的晶格。 |
| 301 | `initial_structure.oriented_unit_cell` | — | MP | 译：初始晶界结构的取向单胞。 |
| 302 | `initial_structure.rotation_angle` | — | MP | 译：初始晶界结构的旋转角。 |
| 303 | `initial_structure.rotation_axis` | — | MP | 译：初始晶界结构的旋转轴。 |
| 304 | `initial_structure.sites` | — | MP | 译：初始晶界结构的位点。 |
| 305 | `initial_structure.vacuum_thickness` | — | MP | 译：初始晶界结构的真空层厚度。 |
| 306 | `initial_structures` | — | MP | Initial structures used in the DFT optimizations corresponding to this material.<br>译：该材料对应的 DFT 优化所使用的初始结构。 |
| 307 | `input` | — | MP | Document defining VASP calculation inputs. Note that the following fields were formerly top-level fields on InputDoc, but are now properties of `CalculationInput`: pseudo_potentials (Potcar) : summary of the POTCARs used in the calculation xc_override (str) : the exchange-correlation functional used if not the one specified by POTCAR is_lasph (bool) : how the calculation set LASPH (aspherical corrections) magnetic_mo...<br>译：定义 VASP 计算输入的文档。 |
| 308 | `input.hubbards` | — | MP | The hubbard parameters used<br>译：使用的 Hubbard 参数。 |
| 309 | `input.incar` | — | MP | INCAR parameters for the calculation<br>译：计算的 INCAR 参数。 |
| 310 | `input.is_hubbard` | — | MP | Is this a Hubbard +U calculation<br>译：是否为 Hubbard +U 计算。 |
| 311 | `input.kpoints` | — | MP | KPOINTS for the calculation<br>译：计算的 KPOINTS。 |
| 312 | `input.lattice_rec` | — | MP | Reciprocal lattice of the structure<br>译：结构的倒晶格。 |
| 313 | `input.nkpoints` | — | MP | Total number of k-points<br>译：k 点总数。 |
| 314 | `input.parameters` | — | MP | Parameters from vasprun<br>译：来自 vasprun 的参数。 |
| 315 | `input.potcar` | — | MP | The symbols of the POTCARs used in the calculation.<br>译：计算所用 POTCAR 的元素符号。 |
| 316 | `input.potcar_spec` | — | MP | Title and hash of POTCAR files used in the calculation<br>译：计算所用 POTCAR 文件的标题与哈希。 |
| 317 | `input.potcar_type` | — | MP | List of POTCAR functional types.<br>译：POTCAR 泛函类型列表。 |
| 318 | `input.structure` | — | MP | Input structure for the calculation<br>译：计算的输入结构。 |
| 319 | `ionic` | — | MP | Ionic contribution to dielectric tensor.<br>译：介电张量的离子贡献。 |
| 320 | `magmoms` | — | MP | Magnetic moments for each site.<br>译：各位点的磁矩。 |
| 321 | `magnetic_ordering` | — | MP | Magnetic ordering of the calculation.<br>译：计算的磁序。 |
| 322 | `material_ids` | — | MP | The ids of all structures that matched to the present host lattice, regardless of stability. The stable entries can be found in the adjacent pairs.<br>译：与当前主体晶格匹配的所有结构编号（不论稳定性）。 |
| 323 | `max_delta_volume` | — | MP | Volume changes in % for a particular voltage step using: max(charge, discharge) / min(charge, discharge) - 1.<br>译：特定电压步的体积变化百分比：max(charge, discharge)/min(charge, discharge) - 1。 |
| 324 | `max_direction` | — | MP | Miller direction for maximum piezo response<br>译：最大压电响应对应的 Miller 方向。 |
| 325 | `max_voltage_step` | — | MP | Maximum absolute difference in adjacent voltage steps.<br>译：相邻电压步之间的最大绝对差。 |
| 326 | `method` | — | MP | Method used to compute structure graph.<br>译：构建结构图的方法。 |
| 327 | `mol_from_site_environments` | — | MP | List of Molecule Objects describing the detected environment.<br>译：描述所检测环境的 Molecule 对象列表。 |
| 328 | `nelements` | — | MP | Number of elements.<br>译：元素数量。 |
| 329 | `nkpoints` | — | MP | The number of kpoints used in the calculation<br>译：计算使用的 k 点数量。 |
| 330 | `num_steps` | — | MP | The number of distinct voltage steps in from fully charge to discharge based on the stable intermediate states.<br>译：由稳定中间态确定的从满充到放电压降步骤数。 |
| 331 | `order` | — | MP | Order of the expansion of the elastic tensor<br>译：弹性张量展开的阶数。 |
| 332 | `orient` | — | MP | Surface orientation of the substrate material.<br>译：衬底材料的表面取向。 |
| 333 | `orig_inputs` | — | MP | Document defining VASP calculation inputs. Note that the following fields were formerly top-level fields on InputDoc, but are now properties of `CalculationInput`: pseudo_potentials (Potcar) : summary of the POTCARs used in the calculation xc_override (str) : the exchange-correlation functional used if not the one specified by POTCAR is_lasph (bool) : how the calculation set LASPH (aspherical corrections) magnetic_mo...<br>译：定义 VASP 计算输入的原始文档。 |
| 334 | `orig_inputs.hubbards` | — | MP | The hubbard parameters used<br>译：原始计算使用的 Hubbard 参数。 |
| 335 | `orig_inputs.incar` | — | MP | INCAR parameters for the calculation<br>译：计算的原始 INCAR 参数。 |
| 336 | `orig_inputs.is_hubbard` | — | MP | Is this a Hubbard +U calculation<br>译：原始计算是否为 Hubbard +U。 |
| 337 | `orig_inputs.kpoints` | — | MP | KPOINTS for the calculation<br>译：计算的原始 KPOINTS。 |
| 338 | `orig_inputs.lattice_rec` | — | MP | Reciprocal lattice of the structure<br>译：原始结构的倒晶格。 |
| 339 | `orig_inputs.nkpoints` | — | MP | Total number of k-points<br>译：原始 k 点总数。 |
| 340 | `orig_inputs.parameters` | — | MP | Parameters from vasprun<br>译：来自 vasprun 的原始参数。 |
| 341 | `orig_inputs.potcar` | — | MP | The symbols of the POTCARs used in the calculation.<br>译：原始计算所用 POTCAR 的元素符号。 |
| 342 | `orig_inputs.potcar_spec` | — | MP | Title and hash of POTCAR files used in the calculation<br>译：原始计算所用 POTCAR 文件的标题与哈希。 |
| 343 | `orig_inputs.potcar_type` | — | MP | List of POTCAR functional types.<br>译：原始 POTCAR 泛函类型列表。 |
| 344 | `orig_inputs.structure` | — | MP | Input structure for the calculation<br>译：原始输入结构。 |
| 345 | `output` | — | MP | Document defining core VASP calculation outputs.<br>译：定义 VASP 核心计算输出的文档。 |
| 346 | `output.bandgap` | eV | MP | The band gap from the calculation in eV<br>译：计算得到的带隙，单位 eV。 |
| 347 | `output.cbm` | eV | MP | The conduction band minimum in eV (if system is not metallic)<br>译：导带底，单位 eV（非金属体系）。 |
| 348 | `output.density` | — | MP | Density of final structure in units of g/cc.<br>译：最终结构的密度，单位 g/cc。 |
| 349 | `output.dielectric_properties` | eV | MP | Store electronic response properties. Note the units and tensor ranks: - Dielectric tensors are dimensionless (no units apply), and are 3x3 - Piezoelectric tensors are in C(oulomb)/m^2, and are 3x6 - Strain tensors, for each atom, are in eV/Å, and are 3x6 - Born charges, for each atom, are in units of the elementary charge, and are 3x3 For both Born charges and strain, the tensors are listed for each site in the stru...<br>译：电子响应性质（介电、压电、Born 电荷等）。 |
| 350 | `output.direct_gap` | eV | MP | Direct band gap in eV (if system is not metallic)<br>译：直接带隙，单位 eV（非金属体系）。 |
| 351 | `output.dos_properties` | eV | MP | Element- and orbital-projected band properties (in eV) for the DOS. All properties are with respect to the Fermi level.<br>译：DOS 的元素与轨道投影带性质，单位 eV（相对费米能级）。 |
| 352 | `output.efermi` | eV | MP | The Fermi level from the calculation in eV<br>译：计算得到的费米能级，单位 eV。 |
| 353 | `output.energy` | — | MP | The final total DFT energy for the calculation<br>译：计算的最终总 DFT 能量。 |
| 354 | `output.energy_per_atom` | — | MP | The final DFT energy per atom for the calculation<br>译：计算的最终每原子 DFT 能量。 |
| 355 | `output.epsilon_ionic` | — | MP | The ionic part of the dielectric constant<br>译：介电常数的离子贡献部分。 |
| 356 | `output.epsilon_static` | — | MP | The high-frequency dielectric constant<br>译：高频介电常数。 |
| 357 | `output.epsilon_static_wolfe` | — | MP | The high-frequency dielectric constant w/o local field effects<br>译：不含局域场效应的高频介电常数。 |
| 358 | `output.frequency_dependent_dielectric` | — | MP | Frequency-dependent dielectric data.<br>译：频率相关介电数据。 |
| 359 | `output.is_gap_direct` | — | MP | Whether the band gap is direct<br>译：带隙是否为直接带隙。 |
| 360 | `output.is_metal` | — | MP | Whether the system is metallic<br>译：体系是否为金属。 |
| 361 | `output.locpot` | — | MP | Average of the local potential along the crystal axes<br>译：沿晶轴方向的局域势平均值。 |
| 362 | `output.mag_density` | — | MP | The magnetization density, defined as total_mag/volume (units of A^-3)<br>译：磁化密度，定义为 total_mag/volume（单位 Å^-3）。 |
| 363 | `output.optical_absorption_coeff` | — | MP | Optical absorption coefficient in cm^-1<br>译：光学吸收系数，单位 cm^-1。 |
| 364 | `output.outcar` | — | MP | Information extracted from the OUTCAR file<br>译：从 OUTCAR 文件提取的信息。 |
| 365 | `output.structure` | — | MP | The final structure from the calculation<br>译：计算得到的最终结构。 |
| 366 | `output.transition` | — | MP | Band gap transition given by CBM and VBM k-points<br>译：由 CBM 与 VBM 的 k 点给出的带隙跃迁。 |
| 367 | `output.vbm` | eV | MP | The valence band maximum in eV (if system is not metallic)<br>译：价带顶，单位 eV（非金属体系）。 |
| 368 | `pair_id` | — | MP | 译：材料对编号。 |
| 369 | `pair_id.id_a` | — | MP | 译：材料对中 A 的编号。 |
| 370 | `pair_id.id_b` | — | MP | 译：材料对中 B 的编号。 |
| 371 | `pair_id.separator` | — | MP | 译：材料对编号的分隔符。 |
| 372 | `phonon_IDs` | — | MP | Identfiers for phonon documents associated with this material.<br>译：与该材料关联的声子文档标识符。 |
| 373 | `phonon_bandstructure` | — | MP | Define schema of pymatgen phonon band structure.<br>译：pymatgen 声子能带结构模式。 |
| 374 | `phonon_bandstructure.eigendisplacements` | — | MP | Phonon eigendisplacements in Cartesian coordinates.<br>译：笛卡尔坐标下的声子本征位移。 |
| 375 | `phonon_bandstructure.frequencies` | — | MP | The eigen-frequencies, with the first index representing the band, and the second the k-point.<br>译：本征频率，第一维为能带、第二维为 k 点。 |
| 376 | `phonon_bandstructure.has_nac` | — | MP | Whether the calculation includes non-analytical corrections at Gamma.<br>译：计算是否包含 Gamma 点的非解析修正。 |
| 377 | `phonon_bandstructure.identifier` | — | MP | The identifier of this object.<br>译：该对象的标识符。 |
| 378 | `phonon_bandstructure.kpath` | — | MP | 译：声子能带结构的高对称 k 路径。 |
| 379 | `phonon_bandstructure.labels_dict` | — | MP | The high-symmetry labels of specific q-points.<br>译：特定 q 点的高对称标签。 |
| 380 | `phonon_bandstructure.path_convention` | — | MP | High symmetry path convention of the band structure<br>译：能带结构的高对称路径约定。 |
| 381 | `phonon_bandstructure.qpoints` | — | MP | The wave vectors (q-points) at which the band structure was sampled, in direct coordinates.<br>译：能带结构取样的波矢（q 点），以直接坐标给出。 |
| 382 | `phonon_bandstructure.reciprocal_lattice` | — | MP | The reciprocal lattice.<br>译：倒晶格。 |
| 383 | `phonon_bandstructure.run_type` | — | MP | The functional used in the calculation.<br>译：计算所用的泛函。 |
| 384 | `phonon_bandstructure.structure` | — | MP | The structure associated with this calculation.<br>译：与该计算关联的结构。 |
| 385 | `phonon_dos` | — | MP | Define schema of pymatgen phonon density of states.<br>译：pymatgen 声子态密度模式。 |
| 386 | `phonon_dos.densities` | — | MP | The phonon density of states.<br>译：声子态密度。 |
| 387 | `phonon_dos.frequencies` | — | MP | The phonon frequencies in THz.<br>译：声子频率，单位 THz。 |
| 388 | `phonon_dos.identifier` | — | MP | The identifier of this object.<br>译：该对象的标识符。 |
| 389 | `phonon_dos.projected_densities` | — | MP | The projected phonon density of states.<br>译：投影声子态密度。 |
| 390 | `phonon_dos.run_type` | — | MP | The functional used in the calculation.<br>译：计算所用的泛函。 |
| 391 | `phonon_dos.structure` | — | MP | The structure associated with this calculation.<br>译：与该计算关联的结构。 |
| 392 | `phonon_method` | — | MP | The method used to calculate phonon properties.<br>译：计算声子性质的方法。 |
| 393 | `possible_valences` | — | MP | List of valences for each site in this material.<br>译：该材料中各位点的可能价态列表。 |
| 394 | `post_process_settings` | — | MP | Collection to store computational settings for the phonon computation.<br>译：声子计算设置集合。 |
| 395 | `post_process_settings.kpath_scheme` | — | MP | indicates the kpath scheme<br>译：k 路径方案。 |
| 396 | `post_process_settings.kpoint_density_dos` | — | MP | number of points for computation of free energies and densities of states<br>译：自由能与态密度计算的 k 点密度。 |
| 397 | `post_process_settings.npoints_band` | — | MP | number of points for band structure computation<br>译：能带结构计算的点数。 |
| 398 | `pretty_formula` | — | MP | Reduced formula of the material.<br>译：材料的简约化学式。 |
| 399 | `primitive_matrix` | — | MP | matrix describing relationship to primitive cell.<br>译：描述与原胞关系的矩阵。 |
| 400 | `raw` | — | MP | Compliance tensor corresponding to structure orientation (TPa^-1)<br>译：对应结构取向的柔度张量（TPa^-1）。 |
| 401 | `reaction` | — | MP | The reaction that characterizes that particular voltage step.<br>译：刻画该电压步的反应。 |
| 402 | `reaction.@class` | — | MP | 译：反应对象的序列化类键。 |
| 403 | `reaction.@module` | — | MP | 译：反应对象的序列化模块键。 |
| 404 | `reaction.products` | — | MP | 译：产物。 |
| 405 | `reaction.reactants` | — | MP | 译：反应物。 |
| 406 | `references` | — | MP | Bibtex reference strings for this material<br>译：该材料的 BibTeX 引用字符串。 |
| 407 | `remarks` | — | MP | list of remarks for the provenance of this material<br>译：该材料来源的备注列表。 |
| 408 | `robocrys_version` | — | MP | The version of Robocrystallographer used to generate this document.<br>译：生成该文档所用 Robocrystallographer 的版本。 |
| 409 | `rotation_angle` | — | MP | Rotation angle in degrees.<br>译：旋转角，单位度。 |
| 410 | `rotation_axis` | — | MP | Rotation axis.<br>译：旋转轴。 |
| 411 | `run_type` | — | MP | The functional used in the calculation.<br>译：计算所用的泛函。 |
| 412 | `run_types` | — | MP | Run types for all the calculations that make up this material<br>译：构成该材料的所有计算的泛函类型。 |
| 413 | `sigma` | — | MP | Sigma value of the boundary.<br>译：晶界的 sigma 值。 |
| 414 | `sim` | — | MP | List containing similar structure data for a given material.<br>译：给定材料的相似结构数据列表。 |
| 415 | `sound_velocity` | — | MP | Sound velocity<br>译：声速。 |
| 416 | `sound_velocity.longitudinal` | — | MP | Longitudinal sound velocity (SI units)<br>译：纵波声速（SI 单位）。 |
| 417 | `sound_velocity.snyder_acoustic` | — | MP | Snyder's acoustic sound velocity (SI units)<br>译：Snyder 声学声速（SI 单位）。 |
| 418 | `sound_velocity.snyder_optical` | — | MP | Snyder's optical sound velocity (SI units)<br>译：Snyder 光学声速（SI 单位）。 |
| 419 | `sound_velocity.snyder_total` | — | MP | Snyder's total sound velocity (SI units)<br>译：Snyder 总声速（SI 单位）。 |
| 420 | `sound_velocity.transverse` | — | MP | Transverse sound velocity (SI units)<br>译：横波声速（SI 单位）。 |
| 421 | `species` | — | MP | List of unique (cationic) species in structure.<br>译：结构中去重后的（阳离子）物种列表。 |
| 422 | `spectrum` | — | MP | The XAS spectrum for this calculation.<br>译：该计算的 XAS 谱。 |
| 423 | `spectrum.@class` | — | MP | 译：XAS 谱对象的序列化类键。 |
| 424 | `spectrum.@module` | — | MP | 译：XAS 谱对象的序列化模块键。 |
| 425 | `spectrum.@version` | — | MP | 译：XAS 谱对象的序列化版本键。 |
| 426 | `spectrum.absorbing_element` | — | MP | 译：XAS 谱的吸收元素。 |
| 427 | `spectrum.absorbing_index` | — | MP | 译：XAS 谱吸收原子的索引。 |
| 428 | `spectrum.edge` | — | MP | 译：XAS 谱的吸收边。 |
| 429 | `spectrum.spectrum_type` | — | MP | 译：XAS 谱类型。 |
| 430 | `spectrum.structure` | — | MP | 译：XAS 谱对应的结构。 |
| 431 | `spectrum.x` | — | MP | 译：XAS 谱的能量轴 x。 |
| 432 | `spectrum.y` | — | MP | 译：XAS 谱的吸收强度轴 y。 |
| 433 | `spectrum_name` | — | MP | 译：XAS 谱名称。 |
| 434 | `spectrum_type` | — | MP | XAS spectrum type.<br>译：XAS 谱类型。 |
| 435 | `stability_charge` | eV/atom | MP | The energy above hull of the charged material in eV/atom.<br>译：充电态材料的凸包以上能量，单位 eV/atom。 |
| 436 | `stability_discharge` | eV/atom | MP | The energy above hull of the discharged material in eV/atom.<br>译：放电态材料的凸包以上能量，单位 eV/atom。 |
| 437 | `state` | — | MP | State of the fitting/analysis: `successful` or `failed`<br>译：拟合/分析状态：successful 或 failed。 |
| 438 | `strain_for_max` | — | MP | Normalized strain direction for maximum piezo repsonse<br>译：最大压电响应对应的归一化应变方向。 |
| 439 | `structure_graph` | — | MP | Structure graph<br>译：结构图。 |
| 440 | `structure_graph.@class` | — | MP | 译：结构图对象的序列化类键。 |
| 441 | `structure_graph.@module` | — | MP | 译：结构图对象的序列化模块键。 |
| 442 | `structure_graph.graphs` | — | MP | 译：结构图包含的图。 |
| 443 | `structure_graph.structure` | — | MP | 译：结构图对应的结构。 |
| 444 | `sub_form` | — | MP | Reduced formula of the substrate.<br>译：衬底的简约化学式。 |
| 445 | `sub_id` | — | MP | Materials Project ID of the substrate material. This comes in the form: mp-******.<br>译：衬底材料的 Materials Project 编号，形如 mp-******。 |
| 446 | `sum_rules_breaking` | — | MP | Container class for defining sum rule checks.<br>译：定义求和规则检验的容器类。 |
| 447 | `sum_rules_breaking.asr` | — | MP | The violation of the acoustic sum rule.<br>译：声学求和规则的违背量。 |
| 448 | `sum_rules_breaking.cnsr` | — | MP | The violation of the charge neutral sum rule.<br>译：电荷中性求和规则的违背量。 |
| 449 | `supercell_matrix` | — | MP | matrix describing the supercell.<br>译：描述超胞的矩阵。 |
| 450 | `surfaces` | — | MP | List of individual surface data.<br>译：各个表面数据的列表。 |
| 451 | `symmetry.angle_tolerance` | — | MP | Angle tolerance provided to spglib to determine the symmetry of this structure.<br>译：用于确定结构对称性的 spglib 角度容差。 |
| 452 | `symmetry.hall` | — | MP | Hall symbol for the lattice<br>译：晶格的 Hall 符号。 |
| 453 | `symmetry.symprec` | — | MP | The precision provided to spglib to determine the symmetry of this structure.<br>译：用于确定结构对称性的 spglib 精度参数。 |
| 454 | `symmetry.version` | — | MP | 译：对称性分析所用 spglib 的版本。 |
| 455 | `tags` | — | MP | Metadata tagged to a given task.<br>译：赋予给定任务的元数据标签。 |
| 456 | `task_id` | — | MP | The (task) ID of this calculation, used as a universal reference across property documents.<br>译：该计算的任务 ID，作为跨性质文档的通用引用。 |
| 457 | `task_ids` | — | MP | List of Calculations IDs associated with this material.<br>译：与该材料关联的计算任务 ID 列表。 |
| 458 | `task_type` | — | MP | The type of calculation.<br>译：计算类型。 |
| 459 | `task_types` | — | MP | Task types for all the calculations that make up this material<br>译：构成该材料的所有计算的任务类型。 |
| 460 | `thermal_conductivity` | — | MP | Thermal conductivity<br>译：热导率。 |
| 461 | `thermal_conductivity.cahill` | — | MP | Cahill's thermal conductivity (SI units)<br>译：Cahill 热导率（SI 单位）。 |
| 462 | `thermal_conductivity.clarke` | — | MP | Clarke's thermal conductivity (SI units)<br>译：Clarke 热导率（SI 单位）。 |
| 463 | `thermal_displacement_data` | — | MP | Collection to store information on the thermal displacement matrices.<br>译：热位移矩阵信息集合。 |
| 464 | `thermal_displacement_data.freq_min_thermal_displacements` | — | MP | cutoff frequency in THz to avoid numerical issues in the computation of the thermal displacement parameters<br>译：计算热位移参数时用于避免数值问题的截止频率（THz）。 |
| 465 | `thermal_displacement_data.temperatures_thermal_displacements` | — | MP | temperatures at which the thermal displacement matriceshave been computed<br>译：计算热位移矩阵所对应的温度。 |
| 466 | `thermal_displacement_data.thermal_displacement_matrix` | — | MP | field including thermal displacement matrices in Cartesian coordinate system<br>译：笛卡尔坐标系下的热位移矩阵。 |
| 467 | `thermal_displacement_data.thermal_displacement_matrix_cif` | — | MP | field including thermal displacement matrices in CIF format<br>译：CIF 格式的热位移矩阵。 |
| 468 | `thermo_type` | — | MP | The functional type used to compute the thermodynamics of this electrode document.<br>译：用于计算该电极文档热力学的泛函类型。 |
| 469 | `total` | — | MP | Total dielectric tensor.<br>译：总介电张量。 |
| 470 | `total_dft_energy` | eV/atom | MP | total DFT energy in eV/atom.<br>译：总 DFT 能量，单位 eV/atom。 |
| 471 | `total_magnetization_normalized_formula_units` | μB/f.u. | MP | Total magnetization normalized by formula unit in μB/f.u. .<br>译：按化学式单元归一化的总磁化强度，单位 μB/f.u.。 |
| 472 | `total_magnetization_normalized_vol` | μB | MP | Total magnetization normalized by volume in μB/Å³.<br>译：按体积归一化的总磁化强度，单位 μB/Å³。 |
| 473 | `transformations` | — | MP | Information on the structural transformations, parsed from a transformations.json file<br>译：从 transformations.json 解析得到的结构变换信息。 |
| 474 | `type` | — | MP | Grain boundary type.<br>译：晶界类型。 |
| 475 | `valences` | — | MP | List of valences for each site in this material to determine cations<br>译：材料中各位点的价态，用于判定阳离子。 |
| 476 | `vasp_objects` | — | MP | Vasp objects associated with this task<br>译：与该任务关联的 VASP 对象。 |
| 477 | `vasp_version` | — | MP | The version of VASP used for this task.<br>译：该任务使用的 VASP 版本。 |
| 478 | `volume_per_formula_unit` | — | MP | volume per formula unit in Angstrom**3.<br>译：每个化学式单元的体积，单位 Å³。 |
| 479 | `volumes` | — | MP | Volumes in A³ that the equations of state are plotted with.<br>译：绘制状态方程所用的体积（Å³）。 |
| 480 | `w_sep` | J/m^2 | MP | Work of separation in J/m^2.<br>译：分离功，单位 J/m²。 |
| 481 | `weighted_surface_energy_EV_PER_ANG2` | eV | MP | Weighted surface energy in eV/Å².<br>译：以 eV/Å² 为单位的加权表面能。 |
| 482 | `working_ion` | — | MP | The working ion as an Element object.<br>译：工作离子（Element 对象）。 |
| 483 | `wyckoff_positions` | — | MP | List of Wyckoff positions for unique (cationic) species in structure.<br>译：结构中各（阳离子）物种的 Wyckoff 位置列表。 |

## 三、AFLOW 官方独有字段（AFLUX schema 193 键，未纳入标准）

| 索引 | 字段（值） | 单位 | 来源 | 描述 |
| ---: | --- | --- | --- | --- |
| 484 | `ael_applied_pressure` | GPa | AFLOW | Returns the applied pressure for the AEL calculations.<br>译：AEL 计算所施加的压力。 |
| 485 | `ael_average_external_pressure` | GPa | AFLOW | Returns the average external pressure for the AEL calculations.<br>译：AEL 计算的平均外部压力。 |
| 486 | `ael_compliance_tensor` | GPa^-1 | AFLOW | Returns the compliance tensor calculated by AEL.<br>译：AEL 计算得到的柔度张量。 |
| 487 | `ael_pughs_modulus_ratio` | — | AFLOW | Returns the Pugh's modulus ratio calculated by AEL.<br>译：AEL 计算的 Pugh 模量比。 |
| 488 | `ael_speed_of_sound_average` | m/s | AFLOW | Returns the average speed of sound calculated by AEL<br>译：AEL 计算的平均声速。 |
| 489 | `ael_speed_of_sound_longitudinal` | m/s | AFLOW | Returns the longitudinal speed of sound calculated by AEL<br>译：AEL 计算的纵波声速。 |
| 490 | `ael_speed_of_sound_transverse` | m/s | AFLOW | Returns the transverse speed of sound calculated by AEL<br>译：AEL 计算的横波声速。 |
| 491 | `ael_speed_sound_average` | m/s | AFLOW | Returns the average speed of sound calculated by AEL<br>译：AEL 计算的平均声速（重复别名）。 |
| 492 | `ael_speed_sound_longitudinal` | m/s | AFLOW | Returns the longitudinal speed of sound calculated by AEL<br>译：AEL 计算的纵波声速（重复别名）。 |
| 493 | `ael_speed_sound_transverse` | m/s | AFLOW | Returns the transverse speed of sound calculated by AEL<br>译：AEL 计算的横波声速（重复别名）。 |
| 494 | `ael_stiffness_tensor` | GPa | AFLOW | Returns the stiffness tensor calculated by AEL<br>译：AEL 计算的刚度张量。 |
| 495 | `aflow_prototype_label_orig` | — | AFLOW | Returns the AFLOW prototype label for the unrelaxed structure.<br>译：未弛豫结构的 AFLOW 原型标签。 |
| 496 | `aflow_prototype_label_relax` | — | AFLOW | Returns the AFLOW prototype label for the relaxed structure.<br>译：弛豫后结构的 AFLOW 原型标签。 |
| 497 | `aflow_prototype_parameters_orig` | — | AFLOW | Returns the AFLOW prototype parameter labels and values for the unrelaxed structure.<br>译：未弛豫结构的 AFLOW 原型参数标签与数值。 |
| 498 | `aflow_prototype_parameters_relax` | — | AFLOW | Returns the AFLOW prototype parameter labels and values for the relaxed structure.<br>译：弛豫后结构的 AFLOW 原型参数标签与数值。 |
| 499 | `aflow_prototype_params_list_orig` | — | AFLOW | Returns the AFLOW prototype parameter labels for the unrelaxed structure.<br>译：未弛豫结构的 AFLOW 原型参数标签。 |
| 500 | `aflow_prototype_params_list_relax` | — | AFLOW | Returns the AFLOW prototype parameter labels for the relaxed structure.<br>译：弛豫后结构的 AFLOW 原型参数标签。 |
| 501 | `aflow_prototype_params_values_orig` | — | AFLOW | Returns the AFLOW prototype parameter values for the unrelaxed structure.<br>译：未弛豫结构的 AFLOW 原型参数数值。 |
| 502 | `aflow_prototype_params_values_relax` | — | AFLOW | Returns the AFLOW prototype parameter values for the relaxed structure.<br>译：弛豫后结构的 AFLOW 原型参数数值。 |
| 503 | `aflow_version` | — | AFLOW | Returns the version number of AFLOW used to perform the calculation.<br>译：执行计算所用的 AFLOW 版本号。 |
| 504 | `aflowlib_entries` | — | AFLOW | Returns the AFLOWLIB entries that matched the search criterion.<br>译：匹配检索条件的 AFLOWLIB 条目。 |
| 505 | `aflowlib_entries_number` | — | AFLOW | Returns the number AFLOWLIB entries that matched the search criterion.<br>译：匹配检索条件的 AFLOWLIB 条目数量。 |
| 506 | `aflowlib_version` | — | AFLOW | Returns the version of the AFLOW post-processor which generated the entry in the library.<br>译：生成该库条目的 AFLOW 后处理程序版本。 |
| 507 | `agl_acoustic_debye` | K | AFLOW | Returns the acoustic Debye temperature calculated by AGL.<br>译：AGL 计算的声学德拜温度。 |
| 508 | `agl_bulk_modulus_isothermal_300K` | GPa | AFLOW | Returns the isothermal bulk modulus calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 等温体积模量。 |
| 509 | `agl_bulk_modulus_static_300K` | GPa | AFLOW | Returns the static bulk modulus calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 静态体积模量。 |
| 510 | `agl_gruneisen` | — | AFLOW | Returns the Grüneisen parameter calculated by AGL.<br>译：AGL 计算的 Grüneisen 参数。 |
| 511 | `agl_heat_capacity_Cp_300K` | k_B/cell | AFLOW | Returns the heat capacity per cell, at constant pressure, calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 定压每晶胞热容。 |
| 512 | `agl_heat_capacity_Cv_300K` | k_B/cell | AFLOW | Returns the heat capacity per cell, at constant volume, calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 定容每晶胞热容。 |
| 513 | `agl_poisson_ratio_source` | — | AFLOW | Returns the source of the Poisson ratio used for AGL calculations.<br>译：AGL 计算所用泊松比的来源。 |
| 514 | `agl_thermal_expansion_300K` | K^-1 | AFLOW | Returns the thermal expansion coefficient calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 热膨胀系数。 |
| 515 | `agl_vibrational_entropy_300K_atom` | meV/(K atom) | AFLOW | Returns the vibrational entropy per atom calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 每原子振动熵。 |
| 516 | `agl_vibrational_entropy_300K_cell` | meV/(K cell) | AFLOW | Returns the vibrational entropy per cell calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 每晶胞振动熵。 |
| 517 | `agl_vibrational_free_energy_300K_atom` | meV/atom | AFLOW | Returns the vibrational free energy per atom calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 每原子振动自由能。 |
| 518 | `agl_vibrational_free_energy_300K_cell` | meV/cell | AFLOW | Returns the vibrational free energy per cell calculated by AGL at 300 K.<br>译：AGL 计算的 300 K 每晶胞振动自由能。 |
| 519 | `author` | — | AFLOW | Returns the name (not necessarily an individual) and affiliation associated with authorship of the data.<br>译：数据作者（不一定是个人）及其单位信息。 |
| 520 | `bader_atomic_volumes` | Å^3 | AFLOW | Returns the volume of each atom calculated by the Atoms in Molecules (AIM) Bader analysis.<br>译：AIM Bader 分析得到的每个原子体积。 |
| 521 | `bader_net_charges` | e^- | AFLOW | Returns the partial charge of each atom calculated by the Atoms in Molecules (AIM) Bader analysis.<br>译：AIM Bader 分析得到的每个原子部分电荷。 |
| 522 | `Bravais_lattice_lattice_system` | — | AFLOW | Returns the Bravais lattice of the lattice system for the relaxed structure.<br>译：弛豫后结构的 Bravais 晶格系统。 |
| 523 | `Bravais_lattice_lattice_system_orig` | — | AFLOW | Returns the Bravais lattice of the lattice system for the unrelaxed structure.<br>译：未弛豫结构的 Bravais 晶格系统。 |
| 524 | `Bravais_lattice_lattice_type` | — | AFLOW | Returns the lattice centering type for the relaxed structure.<br>译：弛豫后结构的晶格中心类型。 |
| 525 | `Bravais_lattice_lattice_type_orig` | — | AFLOW | Returns the lattice centering type for the unrelaxed structure.<br>译：未弛豫结构的晶格中心类型。 |
| 526 | `Bravais_lattice_lattice_variation_type` | — | AFLOW | Returns the Bravais lattice variation of the lattice system for the relaxed structure.<br>译：弛豫后结构的 Bravais 晶格变体类型。 |
| 527 | `Bravais_lattice_lattice_variation_type_orig` | — | AFLOW | Returns the Bravais lattice variation of the lattice system for the unrelaxed structure.<br>译：未弛豫结构的 Bravais 晶格变体类型。 |
| 528 | `Bravais_lattice_orig` | — | AFLOW | Returns the Bravais lattice of the crystal for the unrelaxed structure.<br>译：未弛豫结构的晶体 Bravais 晶格。 |
| 529 | `Bravais_lattice_relax` | — | AFLOW | Returns the Bravais lattice of the crystal for the relaxed structure.<br>译：弛豫后结构的晶体 Bravais 晶格。 |
| 530 | `Bravais_superlattice_lattice_system` | — | AFLOW | Returns the Bravais superlattice of the lattice system for the relaxed structure.<br>译：弛豫后结构的 Bravais 超晶格系统。 |
| 531 | `Bravais_superlattice_lattice_system_orig` | — | AFLOW | Returns the Bravais superlattice of the lattice system for the unrelaxed structure.<br>译：未弛豫结构的 Bravais 超晶格系统。 |
| 532 | `Bravais_superlattice_lattice_type` | — | AFLOW | Returns the Bravais superlattice centering type for the relaxed structure.<br>译：弛豫后结构的 Bravais 超晶格中心类型。 |
| 533 | `Bravais_superlattice_lattice_type_orig` | — | AFLOW | Returns the Bravais superlattice centering type for the unrelaxed structure.<br>译：未弛豫结构的 Bravais 超晶格中心类型。 |
| 534 | `Bravais_superlattice_lattice_variation_type` | — | AFLOW | Returns the Bravais superlattice variation of the lattice system for the relaxed structure.<br>译：弛豫后结构的 Bravais 超晶格变体类型。 |
| 535 | `Bravais_superlattice_lattice_variation_type_orig` | — | AFLOW | Returns the Bravais superlattice variation of the lattice system for the unrelaxed structure<br>译：未弛豫结构的 Bravais 超晶格变体类型。 |
| 536 | `calculation_cores` | — | AFLOW | Returns the number of CPUs used by the calculation.<br>译：计算使用的 CPU 核数。 |
| 537 | `calculation_memory` | MB | AFLOW | Returns the maximum RAM used by the calculation.<br>译：计算使用的最大内存。 |
| 538 | `calculation_time` | seconds | AFLOW | Returns the total time taken by the calculation.<br>译：计算总耗时。 |
| 539 | `catalog` | — | AFLOW | Returns the database name for the calculation.<br>译：计算所属数据库名称。 |
| 540 | `corresponding` | — | AFLOW | Returns the name (not necessarily an individual) and affiliation associated with the data origin concerning correspondence about data.<br>译：数据来源方的通讯联系人及单位信息。 |
| 541 | `crystal_class` | — | AFLOW | Returns the crystal class for the relaxed structure.<br>译：弛豫后结构的晶类。 |
| 542 | `crystal_class_orig` | — | AFLOW | Returns the crystal class for the unrelaxed structure.<br>译：未弛豫结构的晶类。 |
| 543 | `crystal_family` | — | AFLOW | Returns the crystal family for the relaxed structure.<br>译：弛豫后结构的晶族。 |
| 544 | `crystal_family_orig` | — | AFLOW | Returns the crystal family for the unrelaxed structure.<br>译：未弛豫结构的晶族。 |
| 545 | `crystal_system_orig` | — | AFLOW | Returns the crystal system for the unrelaxed structure.<br>译：未弛豫结构的晶系。 |
| 546 | `data_api` | — | AFLOW | Returns the REST API version for the entry.<br>译：该条目的 REST API 版本。 |
| 547 | `data_language` | — | AFLOW | Gives the language of the data in AFLOWLIB.<br>译：AFLOWLIB 中数据的语言。 |
| 548 | `data_source` | — | AFLOW | Returns the data source for the entry.<br>译：该条目的数据来源。 |
| 549 | `delta_electronic_energy_convergence` | eV | AFLOW | Returns the change in total energy from the last step of the self-consistent field (SCF) iteration.<br>译：自洽场最后一步的总能量变化。 |
| 550 | `delta_electronic_energy_threshold` | eV | AFLOW | Returns the threshold for the self-consistent field (SCF) convergence.<br>译：自洽场收敛阈值。 |
| 551 | `eentropy_atom` | eV/atom | AFLOW | Returns the electronic entropy per atom used to converge the calculation.<br>译：用于收敛计算的每原子电子熵。 |
| 552 | `eentropy_cell` | eV/cell | AFLOW | Returns the electronic entropy per cell used to converge the calculation.<br>译：用于收敛计算的每晶胞电子熵。 |
| 553 | `Egap_fit` | eV | AFLOW | Simple cross-validated correction (fit) of Egap.<br>译：Egap 的简单交叉验证拟合修正值。 |
| 554 | `enthalpy_atom` | eV/atom | AFLOW | Returns the enthalpy per atom.<br>译：每原子焓。 |
| 555 | `enthalpy_cell` | eV/cell | AFLOW | Returns the enthalpy per cell.<br>译：每晶胞焓。 |
| 556 | `entropic_temperature` | K | AFLOW | Returns the entropic temperature.<br>译：熵温度。 |
| 557 | `files` | — | AFLOW | Returns the input and output files used in the simulation.<br>译：模拟所用的输入与输出文件列表。 |
| 558 | `forces` | eV/Å | AFLOW | Returns the forces on the atoms for the relaxed structure.<br>译：弛豫后结构各原子的受力。 |
| 559 | `geometry` | — | AFLOW | Returns the lattice parameters of the relaxed simulation cell.<br>译：弛豫后模拟晶胞的晶格参数。 |
| 560 | `geometry_orig` | — | AFLOW | Returns the lattice parameters of the unrelaxed simulation cell.<br>译：未弛豫模拟晶胞的晶格参数。 |
| 561 | `icsd_number` | — | AFLOW | Returns the ICSD entry number<br>译：ICSD 条目编号。 |
| 562 | `keywords` | — | AFLOW | This includes the list of keywords available in the entry, separated by commas.<br>译：该条目可用关键字列表，以逗号分隔。 |
| 563 | `kpoints` | — | AFLOW | Set of k-point meshes uniquely identifying the various steps of the calculations, e.g. relaxation, static and electronic band structure (specifying the k-space symmetry points of the structure).<br>译：标识各计算步骤的 k 点网格集合。 |
| 564 | `kpoints_bands_nkpts` | — | AFLOW | Returns the number of points, between the high-symmetry k-points, used for the band structure calculation.<br>译：能带计算中高对称点之间的点数。 |
| 565 | `kpoints_bands_path` | — | AFLOW | Returns the high-symmetry k-point path used for the band structure calculation.<br>译：能带计算使用的高对称 k 点路径。 |
| 566 | `lattice_system_orig` | — | AFLOW | Returns the lattice system for the unrelaxed structure.<br>译：未弛豫结构的晶格系统。 |
| 567 | `lattice_system_relax` | — | AFLOW | Returns the lattice system for the relaxed structure.<br>译：弛豫后结构的晶格系统。 |
| 568 | `lattice_variation_orig` | — | AFLOW | Returns the lattice variation for the unrelaxed structure.<br>译：未弛豫结构的晶格变体。 |
| 569 | `lattice_variation_relax` | — | AFLOW | Returns the lattice variation for the relaxed structure.<br>译：弛豫后结构的晶格变体。 |
| 570 | `ldau_j` | eV | AFLOW | Returns the J parameters of the DFT+U calculation.<br>译：DFT+U 计算的 J 参数。 |
| 571 | `ldau_l` | — | AFLOW | Returns The orbitals of the DFT+U calculation.<br>译：DFT+U 计算涉及的轨道。 |
| 572 | `ldau_TLUJ` | — | AFLOW | This vector of numbers contains the parameters of the DFT+U calculations, based on a corrective functional inspired by the Hubbard model.<br>译：基于 Hubbard 模型校正泛函的 DFT+U 参数向量。 |
| 573 | `ldau_type` | — | AFLOW | Returns the type of DFT+U calculation performed.<br>译：所执行 DFT+U 计算的类型。 |
| 574 | `ldau_u` | eV | AFLOW | Returns the U parameters of the DFT+U calculation.<br>译：DFT+U 计算的 U 参数。 |
| 575 | `loop` | — | AFLOW | Returns information about the type of post-processing that was performed.<br>译：所执行后处理类型的相关信息。 |
| 576 | `nbondxx` | Å | AFLOW | Returns the nearest neighbors distances for the relaxed structure.<br>译：弛豫后结构的最近邻距离。 |
| 577 | `node_CPU_Cores` | — | AFLOW | Returns information about the number of CPUs on the node/cluster where the calculation was performed.<br>译：计算节点/集群的 CPU 核数。 |
| 578 | `node_CPU_MHz` | MHz | AFLOW | Returns information about the speed of CPUs on the node/cluster where the calculation was performed.<br>译：计算节点/集群的 CPU 主频。 |
| 579 | `node_CPU_Model` | — | AFLOW | Returns information about the model of CPUs on the node/cluster where the calculation was performed.<br>译：计算节点/集群的 CPU 型号。 |
| 580 | `node_RAM_GB` | Gb | AFLOW | Returns information about the RAM on the node/cluster where the calculation was performed.<br>译：计算节点/集群的内存容量。 |
| 581 | `nspecies` | — | AFLOW | Returns the number of unique species in the structure.<br>译：结构中不同种类的数量。 |
| 582 | `Pearson_symbol_orig` | — | AFLOW | Returns the Pearson symbol for the unrelaxed structure.<br>译：未弛豫结构的 Pearson 符号。 |
| 583 | `Pearson_symbol_relax` | — | AFLOW | Returns the Pearson symbol for the relaxed structure.<br>译：弛豫后结构的 Pearson 符号。 |
| 584 | `Pearson_symbol_superlattice` | — | AFLOW | Returns the Pearson symbol of the superlattice for the relaxed structure.<br>译：弛豫后结构超晶格的 Pearson 符号。 |
| 585 | `Pearson_symbol_superlattice_orig` | — | AFLOW | Returns the Pearson symbol of the superlattice for the unrelaxed structure.<br>译：未弛豫结构超晶格的 Pearson 符号。 |
| 586 | `point_group_Hermann_Mauguin_orig` | — | AFLOW | Returns the point group, in Hermann-Mauguin notation, for the unrelaxed structure.<br>译：未弛豫结构的 Hermann-Mauguin 点群。 |
| 587 | `point_group_orbifold` | — | AFLOW | Returns the point group orbifold for the relaxed structure.<br>译：弛豫后结构的点群轨形符号。 |
| 588 | `point_group_orbifold_orig` | — | AFLOW | Returns the point group orbifold for the unrelaxed structure.<br>译：未弛豫结构的点群轨形符号。 |
| 589 | `point_group_order` | — | AFLOW | Returns the point group order for the relaxed structure.<br>译：弛豫后结构的点群阶。 |
| 590 | `point_group_order_orig` | — | AFLOW | Returns the point group order for the unrelaxed structure.<br>译：未弛豫结构的点群阶。 |
| 591 | `point_group_Schoenflies` | — | AFLOW | Returns the point group, in Schoenflies notation, for the relaxed structure.<br>译：弛豫后结构的 Schoenflies 点群。 |
| 592 | `point_group_Schoenflies_orig` | — | AFLOW | Returns the point group, in Schoenflies notation, for the unrelaxed structure.<br>译：未弛豫结构的 Schoenflies 点群。 |
| 593 | `point_group_structure` | — | AFLOW | Returns the point group structure for the relaxed structure.<br>译：弛豫后结构的点群结构。 |
| 594 | `point_group_structure_orig` | — | AFLOW | Returns the point group structure for the unrelaxed structure<br>译：未弛豫结构的点群结构。 |
| 595 | `point_group_type` | — | AFLOW | Returns the point group type for the relaxed structure.<br>译：弛豫后结构的点群类型。 |
| 596 | `point_group_type_orig` | — | AFLOW | Returns the point group type for the unrelaxed structure.<br>译：未弛豫结构的点群类型。 |
| 597 | `positions_cartesian` | Å | AFLOW | Returns the Cartesian coordinates of the atoms for the relaxed structure.<br>译：弛豫后结构各原子的笛卡尔坐标。 |
| 598 | `positions_fractional` | — | AFLOW | Returns the fractional coordinates of the atoms for the relaxed structure.<br>译：弛豫后结构各原子的分数坐标。 |
| 599 | `pressure_final` | kbar | AFLOW | Returns the hydrostatic pressure on the simulation cell for the relaxed structure.<br>译：弛豫后模拟晶胞的静水压力。 |
| 600 | `pressure_residual` | kbar | AFLOW | Returns the hydrostatic pressure, corrected by the Pulay stress, on the simulation cell for the relaxed structure.<br>译：经 Pulay 应力校正后的弛豫结构静水压力。 |
| 601 | `prototype` | — | AFLOW | Returns the AFLOW prototype for the unrelaxed structure.<br>译：未弛豫结构的 AFLOW 原型。 |
| 602 | `Pulay_stress` | kbar | AFLOW | Returns the Pulay stress correcton for the calculation.<br>译：计算的 Pulay 应力校正。 |
| 603 | `Pullay_stress` | kbar | AFLOW | Returns the Pulay stress correction for the calculation.<br>译：计算的 Pulay 应力校正（拼写别名）。 |
| 604 | `PV_atom` | eV/atom | AFLOW | Returns the pressure multiplied by volume per atom for the relaxed structure.<br>译：弛豫结构的压力乘体积（每原子）。 |
| 605 | `PV_cell` | eV/cell | AFLOW | Returns the pressure multiplied by volume per atom for the relaxed structure.<br>译：弛豫结构的压力乘体积（每晶胞）。 |
| 606 | `reciprocal_geometry` | — | AFLOW | Returns the reciprocal lattice parameters of the relaxed simulation cell.<br>译：弛豫后模拟晶胞的倒格矢参数。 |
| 607 | `reciprocal_geometry_orig` | — | AFLOW | Returns the reciprocal lattice parameters of the unrelaxed simulation cell.<br>译：未弛豫模拟晶胞的倒格矢参数。 |
| 608 | `reciprocal_lattice_type` | — | AFLOW | Returns the reciprocal lattice centering type for the relaxed structure.<br>译：弛豫后结构的倒格中心类型。 |
| 609 | `reciprocal_lattice_type_orig` | — | AFLOW | Returns the reciprocal lattice centering type for the unrelaxed structure.<br>译：未弛豫结构的倒格中心类型。 |
| 610 | `reciprocal_lattice_variation_type` | — | AFLOW | Returns the reciprocal lattice centering type variation for the relaxed structure.<br>译：弛豫后结构的倒格中心变体类型。 |
| 611 | `reciprocal_lattice_variation_type_orig` | — | AFLOW | Returns the reciprocal lattice centering type variation for the unrelaxed structure.<br>译：未弛豫结构的倒格中心变体类型。 |
| 612 | `reciprocal_volume_cell` | Å^-3 | AFLOW | Returns the volume of the reciprocal cell for the relaxed structure.<br>译：弛豫后结构的倒晶胞体积。 |
| 613 | `reciprocal_volume_cell_orig` | Å^-3 | AFLOW | Returns the volume of the reciprocal cell for the unrelaxed structure.<br>译：未弛豫结构的倒晶胞体积。 |
| 614 | `scintillation_attenuation_length` | cm | AFLOW | Returns the scintillation attenuation length.<br>译：闪烁衰减长度。 |
| 615 | `sg` | — | AFLOW | Returns the space groups for the structure, before the first relaxation step (unrelaxed), after the first relaxation step and after the last relaxation step (relaxed), using a loose tolerance.<br>译：宽松容差下，结构在弛豫前、首次弛豫后及最终弛豫后的空间群。 |
| 616 | `sg2` | — | AFLOW | Returns the space groups for the structure, before the first relaxation step (unrelaxed), after the first relaxation step and after the last relaxation step (relaxed), using a tight (default) tolerance.<br>译：严格（默认）容差下，结构在弛豫前、首次弛豫后及最终弛豫后的空间群。 |
| 617 | `spacegroup_orig` | — | AFLOW | Returns the space group for the unrelaxed structure.<br>译：未弛豫结构的空间群。 |
| 618 | `species_pp` | — | AFLOW | Returns the pseudopotential of the species.<br>译：各元素的赝势。 |
| 619 | `species_pp_version` | — | AFLOW | Returns the pseudopotential version of the species.<br>译：各元素赝势的版本。 |
| 620 | `species_pp_ZVAL` | e^- | AFLOW | Returns the number of valence electrons of the species.<br>译：各元素的价电子数。 |
| 621 | `spinD_magmom_orig` | μ_B | AFLOW | Returns the magnetic moment on each atom of the unrelaxed structure.<br>译：未弛豫结构各原子的磁矩。 |
| 622 | `spinF` | μ_B/cell | AFLOW | Returns the magnetization of the simulation cell, at the Fermi energy.<br>译：模拟晶胞在费米能级处的磁化。 |
| 623 | `sponsor` | — | AFLOW | Returns information about funding agencies and other sponsors for the entry.<br>译：该条目的资助机构等信息。 |
| 624 | `stoich` | — | AFLOW | Similar to composition, returns a comma delimited stoichiometry description of the structure entry in the calculated cell.<br>译：与 composition 类似，以逗号分隔描述计算晶胞的化学计量。 |
| 625 | `stoichiometry` | — | AFLOW | Returns the normalized composition of the structure.<br>译：结构的归一化组成。 |
| 626 | `stress_tensor` | kbar | AFLOW | Returns the stress tensor for the relaxed structure.<br>译：弛豫后结构的应力张量。 |
| 627 | `valence_cell_iupac` | — | AFLOW | Returns the sum of the valence electrons, based on IUPAC standards, of the atoms in the simulation cell.<br>译：按 IUPAC 标准计算的晶胞价电子总数。 |
| 628 | `valence_cell_std` | — | AFLOW | Returns the sum of the valence electrons, based on the outermost shell(s), of the atoms in the simulation cell.<br>译：按最外壳层计算的晶胞价电子总数。 |
| 629 | `volume_atom` | Å^3/atom | AFLOW | Returns the volume per atom of the simulation cell for the relaxed structure.<br>译：弛豫后结构每原子体积。 |
| 630 | `Wyckoff_letters` | — | AFLOW | Returns the Wyckoff letters of each site for the relaxed structure.<br>译：弛豫后结构各位点的 Wyckoff 字母。 |
| 631 | `Wyckoff_letters_orig` | — | AFLOW | Returns the Wyckoff letters of each site for the unrelaxed structure.<br>译：未弛豫结构各位点的 Wyckoff 字母。 |
| 632 | `Wyckoff_multiplicities` | — | AFLOW | Returns the Wyckoff multiplicity of each site for the relaxed structure.<br>译：弛豫后结构各位点的 Wyckoff 重数。 |
| 633 | `Wyckoff_multiplicities_orig` | — | AFLOW | Returns the Wyckoff multiplicity of each site for the unrelaxed structure.<br>译：未弛豫结构各位点的 Wyckoff 重数。 |
| 634 | `Wyckoff_positions_orig` | — | AFLOW | The Wyckoff positions of each site for the unrelaxed structure.<br>译：未弛豫结构各位点的 Wyckoff 位置。 |
| 635 | `Wyckoff_site_symmetries` | — | AFLOW | Returns the Wyckoff symmetry of each site for the relaxed structure.<br>译：弛豫后结构各位点的 Wyckoff 对称性。 |
| 636 | `Wyckoff_site_symmetries_orig` | — | AFLOW | Returns the Wyckoff symmetry of each site for the unrelaxed structure.<br>译：未弛豫结构各位点的 Wyckoff 对称性。 |
