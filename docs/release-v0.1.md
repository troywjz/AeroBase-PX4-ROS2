# AeroBase v0.1.0 发布验收标准

本文定义 v0.1.0 的受支持组合、只读能力边界和可检查的完成门。v0.1.0 是可复现的 PX4 SITL 与 ROS 2 遥测基线，不包含尚未实现或尚未验证的控制与硬件能力。

## 支持矩阵

| 项目 | v0.1.0 基线 | 当前证据与状态 |
| --- | --- | --- |
| 系统与架构 | Ubuntu 24.04，amd64 | 依赖脚本限制 Ubuntu 24.04；现有集成报告记录 WSL2 Ubuntu 24.04.4。原生 Ubuntu 24.04 amd64 验收待完成。 |
| ROS 2 | Jazzy，Cyclone DDS RMW | 两次 WSL2 SITL 记录使用 `rmw_cyclonedds_cpp`；干净 runner 端到端验证待完成。 |
| PX4 | v1.17.0，提交 `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` | 固定于 [`stack.lock.json`](../config/stack.lock.json)，并出现在现有运行版本记录中。 |
| PX4 消息 | `px4_msgs` `release/1.17`，提交 `86d8239e962f6939e05c3737784f60c02fa884db` | 固定源及四类消息接口检查由锁文件和构建脚本约束；发布验收仍须通过下述完成门。 |
| 模拟器 | Gazebo Harmonic，X500，headless 验证 | WSL2 报告记录 Gazebo Sim 8.15.0 和 X500；原生 Ubuntu 与干净 runner 验收待完成。GUI 不属于完成门。 |
| XRCE Agent | Micro XRCE-DDS Agent v2.4.3，提交 `73622810d984349b80bbac0ef55fc0b694d62222` | 固定源见锁文件；现有 WSL2 SITL 报告覆盖断连与恢复。 |
| Agent 日志依赖 | spdlog v1.9.2，提交 `eb3220622e73a4889eee355ffa37972b3cac3df5` | 固定源见锁文件；现有报告记录更新版 spdlog 的兼容性问题。 |

源码版本由 [`config/stack.lock.json`](../config/stack.lock.json) 固定；Ubuntu / ROS / Gazebo 软件包来自对应软件仓库，需在验收证据中记录实际安装版本。当前 WSL2 记录证明该特定 WSL2 配置，不等于原生 Ubuntu 已验收，也不自动证明干净 Linux runner 已验收。现有环境与运行记录见[版本证据](evidence/2026-10-09-versions.json)及[集成报告](evidence/2026-10-09-phase1.md)。

## v0.1.0 完成门

以下各门均须有可复核的命令、版本、条件、结果和证据位置。状态未明确记录为通过前均为**待验收**；已有证据仅按其实际环境和覆盖范围计入。

| 完成门 | 可检查条件 | 当前状态 |
| --- | --- | --- |
| 1. 支持矩阵与来源 | 确认 Ubuntu 24.04 amd64、ROS 2 Jazzy、PX4 v1.17.0、Gazebo Harmonic 的目标组合；核对固定源码引用、消息定义与兼容依据，并记录包版本。完成原生 Ubuntu 24.04 amd64 验收，明确区分已有 WSL2 证据。 | 固定源码及 WSL2 证据已记录；原生 Ubuntu 验收待完成。 |
| 2. 部署与遥测链路 | 在原有验证环境及干净 Linux runner 分别执行依赖安装和普通用户构建；验证 `VehicleStatus`、`VehicleOdometry`、`BatteryStatus`、`VehicleGlobalPosition` 四类遥测，监测节点先启动、Agent 断连与恢复，以及无 PX4 控制发布器/命令服务客户端。 | WSL2 集成报告覆盖四类遥测、monitor 先启动、Agent 恢复和只读边界；完整依赖安装/构建复现及干净 runner 验收待完成。 |
| 3. 机器可读遥测 | 通用遥测程序保留兼容的默认 text 输出，并提供严格符合 `schema_v1` 的 JSON machine 输出；字段、类型、单位、frame 与状态有明确定义。缺失或 stale 字段不得作为 fresh 数值输出。 | 待实现并验收。 |
| 4. 环境诊断 | 环境诊断工具在缺依赖、版本不符或服务不可用时给出具体原因和可执行提示；诊断失败不得停止、重启或改坏已有服务。 | 待实现并验收。 |
| 5. 测试、CI 与摘要 | 核心逻辑测试和使用真实 ROS/PX4 消息类的适配测试通过；native CI 集成验收覆盖目标链路；提交不含原始私人运行日志，并提供可公开、脱敏且保留证据限制的摘要。 | 当前记录包含 14 项 Python 测试及部分 CI 结果；真实消息、native CI 集成验收和本次发布摘要待复核/补齐。 |
| 6. 发布材料 | MIT 许可、贡献说明与问题模板齐备；`CHANGELOG.md` 记录版本范围和限制；创建 v0.1.0 tag 与 GitHub Release，并核对最终发布内容。 | MIT 许可已存在；其余发布材料及 tag/Release 待完成。 |

## 范围与证据边界

v0.1.0 的运行能力是 PX4 SITL、Gazebo X500、uXRCE-DDS 与 ROS 2 之间的只读遥测集成。状态与里程计是连接状态所需的必选流；电池和全局位置为可选遥测。`vehicle_monitor` 报告数据新鲜度，不判断飞行器是否具备起飞条件。

ARM、实体飞控、实体传感器、真实飞行、Gazebo GUI 视觉验收、Offboard 或其他控制、MAVLink 后端、ArduPilot 以及具体应用闭环均不属于 v0.1.0 完成门。它们需要各自独立的需求、接口、失联行为和验证证据。SITL 结果不代表实体飞行能力或安全认证。证据等级见[验证方法](validation.md)。
