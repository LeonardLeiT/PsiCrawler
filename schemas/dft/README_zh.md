# DFT 标准字段

本目录定义 PsiCrawler 的统一 DFT（Density Functional Theory，密度泛函理论）数据契约。当前标准版本为 `dft-v1`，共 51 个字段。字段定义以 `standard.yaml` 为权威来源，`catalog.yaml` 保存字段目录，各数据源的 `*.yaml` 文件保存映射。

所有字段目前均可选且可为 `null`。数据源未提供、尚未抓取或性质不适用时使用 `null`，不要用 `0`、空字符串或 `false` 代替缺失值。`false` 仅表示已知为否，`0` 仅表示已知数值为零。路径字段表示本地文件路径，不默认表示远程 URL。

## 字段分组总览

| 分组 | 数量 | 字段 |
| --- | ---: | --- |
| 来源与记录元数据 | 4 | `source`, `source_id`, `schema_version`, `ingested_at` |
| 化学组成 | 4 | `formula`, `formula_pretty`, `elements`, `composition` |
| 结构与晶体学 | 6 | `nsites`, `volume`, `density`, `symmetry_symbol`, `symmetry_number`, `crystal_system` |
| 能量与稳定性 | 5 | `energy`, `energy_per_atom`, `formation_energy_per_atom`, `energy_above_hull`, `is_stable` |
| 电子结构 | 3 | `band_gap`, `is_metal`, `efermi` |
| 磁性 | 4 | `total_magnetization`, `magnetic_ordering`, `is_magnetic`, `magnetic_moment` |
| 弹性与力学性质 | 12 | `volume_change`, `bulk_modulus`, `shear_modulus`, `elastic_anisotropy`, `homogeneous_poisson`, `g_reuss`, `g_voigt`, `k_reuss`, `k_voigt`, `universal_anisotropy`, `elastic_tensor`, `has_elasticity` |
| 电子与声子数据文件 | 10 | `dos_path`, `bandstructure_path`, `charge_density_path`, `phonon_bandstructure_path`, `phonon_dos_path`, `phonon_modes_path`, `has_dos`, `has_bandstructure`, `has_charge_density`, `has_phonon` |
| 结构与计算输出文件 | 3 | `cif_path`, `poscar_path`, `output_dir` |
| **合计** | **51** | |

## 1. 来源与记录元数据

| 字段 | 类型 | 单位/格式 | 说明 |
| --- | --- | --- | --- |
| `source` | string | 枚举 | 数据来源：`mp`、`oqmd`、`aflow`、`citrine`、`jarvis`、`other`。 |
| `source_id` | string | 来源内 ID | 数据源中的材料或计算记录 ID，例如 `mp-149`；不保证跨来源唯一。 |
| `schema_version` | string | 版本 | 记录遵循的标准版本，当前为 `dft-v1`。 |
| `ingested_at` | string | ISO 8601 | 记录进入标准化流程的时间，通常为 UTC。 |

## 2. 化学组成

| 字段 | 类型 | 单位/格式 | 说明 |
| --- | --- | --- | --- |
| `formula` | string | 化学式 | 数据源提供的原始化学式字符串，尽量保留来源表达。 |
| `formula_pretty` | string | 化学式 | 面向展示和检索的规范化或美化化学式。 |
| `elements` | array[string] | 元素符号数组 | 结构中的去重元素，例如 [`Si`, `O`]。 |
| `composition` | object | 元素到数量 | 组成映射，例如 `{"Si": 1, "O": 2}`；数量可为整数或归一化比例。 |

## 3. 结构与晶体学

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `nsites` | integer | 个 | 计算晶胞中的原子数，不等同于元素种类数。 |
| `volume` | number | Å³ | 计算晶胞体积。 |
| `density` | number | g/cm³ | 材料密度，通常由晶胞质量和体积得到。 |
| `symmetry_symbol` | string | Hermann-Mauguin | 空间群符号，例如 `Fd-3m`。 |
| `symmetry_number` | integer | 1–230 | 空间群国际编号。 |
| `crystal_system` | string | 枚举 | `cubic`、`tetragonal`、`orthorhombic`、`hexagonal`、`trigonal`、`monoclinic`、`triclinic`、`other`。 |

## 4. 能量与稳定性

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `energy` | number | eV / 晶胞 | 计算体系总能量；跨材料比较时需确认晶胞规模一致。 |
| `energy_per_atom` | number | eV/atom | 总能量除以晶胞原子数。 |
| `formation_energy_per_atom` | number | eV/atom | 相对于组成元素参考态的每原子形成能，参考态随数据源而异。 |
| `energy_above_hull` | number | eV/atom | 相对同一化学体系凸包的能量；越接近 0 通常越稳定。 |
| `is_stable` | boolean | true / false | 数据源给出的稳定性判断，应保留来源阈值语义。 |

## 5. 电子结构

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `band_gap` | number | eV | 带隙；金属通常为 0 或接近 0，但应保留来源判定。 |
| `is_metal` | boolean | true / false | 是否为金属，缺少数据时不能仅凭带隙值强行推断。 |
| `efermi` | number | eV | 费米能级；输入可能叫 `efermi` 或 `fermi_level`，标准名固定为 `efermi`。 |

## 6. 磁性

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `total_magnetization` | number | μB / 晶胞 | 晶胞总磁矩或总磁化强度，具体定义遵循数据源。 |
| `magnetic_ordering` | string | 枚举 | `NM`、`FM`、`AFM`、`FiM` 或 `unknown`。 |
| `is_magnetic` | boolean | true / false | 是否存在磁性，不能用缺失总磁矩自动填充为 false。 |
| `magnetic_moment` | number | μB | 磁矩摘要值；可能是每原子、每离子或整个结构的值，需结合来源定义。 |

## 7. 弹性与力学性质

弹性字段主要使用 GPa；无量纲字段不附加单位。`bulk_modulus` 和 `shear_modulus` 使用 Voigt-Reuss-Hill（VRH）平均值。

| 字段 | 类型 | 单位/范围 | 说明 |
| --- | --- | --- | --- |
| `volume_change` | number | % | 弹性或结构计算中的体积变化百分比。 |
| `bulk_modulus` | number | GPa | 体积模量 VRH 平均值，反映抵抗均匀压缩的能力。 |
| `shear_modulus` | number | GPa | 剪切模量 VRH 平均值，反映抵抗剪切变形的能力。 |
| `elastic_anisotropy` | number | 无量纲 | 弹性各向异性摘要值，具体定义遵循数据源。 |
| `homogeneous_poisson` | number | 无量纲 | 均匀泊松比。 |
| `g_reuss` | number | GPa | 剪切模量 Reuss 平均值。 |
| `g_voigt` | number | GPa | 剪切模量 Voigt 平均值。 |
| `k_reuss` | number | GPa | 体积模量 Reuss 平均值。 |
| `k_voigt` | number | GPa | 体积模量 Voigt 平均值。 |
| `universal_anisotropy` | number | 无量纲 | Universal Elastic Anisotropy Index；通常为 0 表示各向同性。 |
| `elastic_tensor` | object | 通常为 GPa | 弹性刚度张量或来源原生结构，例如包含 `C11` 等分量的对象；内部键名不固定。 |
| `has_elasticity` | boolean | true / false | 是否存在可用弹性数据，通常由张量或弹性常数文件是否成功获取判断。 |

## 8. 电子与声子数据文件

以下字段指向下载或生成后的本地产物。路径不存在、尚未下载或来源没有对应计算时使用 `null`；`has_*` 字段用于快速判断数据是否可用。

| 字段 | 类型 | 单位/格式 | 说明 |
| --- | --- | --- | --- |
| `dos_path` | string | 本地路径 | 总态密度（DOS）数据文件。 |
| `bandstructure_path` | string | 本地路径 | 电子能带结构数据文件。 |
| `charge_density_path` | string | 本地路径 | 电荷密度数据文件。 |
| `phonon_bandstructure_path` | string | 本地路径 | 声子能带结构数据文件。 |
| `phonon_dos_path` | string | 本地路径 | 声子态密度数据文件。 |
| `phonon_modes_path` | string | 本地路径 | 声子模式、位移或模态数据文件。 |
| `has_dos` | boolean | true / false | 是否有可用 DOS 文件或数据。 |
| `has_bandstructure` | boolean | true / false | 是否有可用电子能带结构文件或数据。 |
| `has_charge_density` | boolean | true / false | 是否有可用电荷密度文件或数据。 |
| `has_phonon` | boolean | true / false | 是否存在任一种声子数据，通常由三类声子文件任一存在决定。 |

## 9. 结构与计算输出文件

| 字段 | 类型 | 单位/格式 | 说明 |
| --- | --- | --- | --- |
| `cif_path` | string | 本地路径 | CIF 结构文件路径。 |
| `poscar_path` | string | 本地路径 | VASP POSCAR/CONTCAR 类结构文件路径。 |
| `output_dir` | string | 本地目录路径 | 材料或计算记录的原始输出文件目录。 |

## 数据源映射

| 来源 | source 值 | source_id 示例 | 映射文件 |
| --- | --- | --- | --- |
| Materials Project | `mp` | `mp-149` | `mp.yaml` |
| OQMD | `oqmd` | OQMD 条目 ID | `oqmd.yaml` |
| AFLOW | `aflow` | AUID | `aflow.yaml` |
| Citrine | `citrine` | Citrine 条目 ID | `citrine.yaml` |
| JARVIS | `jarvis` | JID | `jarvis.yaml` |

源字段没有对应标准字段时不会强行转换；完整源数据和未归一化属性应通过原始输出文件或来源专用数据结构追溯。

## 维护与验证

修改字段时应同步检查：

1. `standard.yaml`：字段名称、类型、枚举和描述。
2. `catalog.yaml`：字段数量和字段顺序。
3. `sources/dft/*/normalize.py`：数据源归一化逻辑。
4. `schemas/dft/*.yaml`：字段映射和属性端点。

```powershell
python -m compileall -q sources\dft\mp crawler\dft\mp
```


