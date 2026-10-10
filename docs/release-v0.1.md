# AeroBase v0.1.0 发布验收标准

v0.1.0 提供可复现的 PX4 SITL、Gazebo X500、uXRCE-DDS 与 ROS 2 只读遥测基线。原生 Ubuntu runner 和 WSL2 的验收已通过，条件及版本见[发布证据](evidence/2026-10-10-v0.1.md)。发布版本以 [v0.1.0 tag / GitHub Release](https://github.com/troywjz/AeroBase-PX4-ROS2/releases/tag/v0.1.0) 为准。

## 支持矩阵

| 项目 | v0.1.0 基线 | 验收条件 |
| --- | --- | --- |
| 系统与架构 | Ubuntu 24.04，amd64 | 全新 GitHub 托管 Ubuntu 24.04.5 runner；另有 WSL2 Ubuntu 24.04.4 证据。 |
| ROS 2 | Jazzy，Cyclone DDS RMW | `rmw_cyclonedds_cpp` 的实际消息链路通过；其他 RMW 需独立验证。 |
| PX4 | v1.17.0 | 固定源码，SITL X500 保持未解锁。 |
| PX4 消息 | `px4_msgs` `release/1.17` 固定提交 | 消息字段、Topic 版本、QoS 和四条遥测链路通过。 |
| 模拟器 | Gazebo Harmonic，Sim 8.15.0 | headless X500 模型和数据链路通过；GUI 未验收。 |
| XRCE Agent | Micro XRCE-DDS Agent v2.4.3 | 使用 Jazzy 的 Fast DDS / Fast CDR，断连与恢复通过。 |
| Agent 日志依赖 | spdlog v1.9.2 | 固定源码，普通用户构建通过。 |

四个源码提交由 [`config/stack.lock.json`](../config/stack.lock.json) 固定，并与公开摘要中的实际提交一致。Ubuntu / ROS / Gazebo 软件包来自各自软件仓库，实际版本保留在原生与 WSL2 摘要中；后续系统包更新需要重新验证，不能仅凭固定源码宣称兼容。该支持矩阵限于所记录的架构、软件组合和 headless 条件。

## v0.1.0 完成门

| 完成门 | 可检查条件 | 结果与证据 |
| --- | --- | --- |
| 1. 支持矩阵与来源 | 固定源码、核对消息定义与兼容条件、记录系统包版本；完成 Ubuntu 24.04 amd64 原生验收。 | 通过。[原生版本与结果](evidence/2026-10-10-native-json.json)、[WSL2 版本与结果](evidence/2026-10-10-wsl-json.json)。 |
| 2. 部署与遥测链路 | 从依赖安装到普通用户构建复现；四条遥测到达，订阅先就绪，Agent 断连恢复，无 PX4 控制发布器/命令服务客户端。 | 通过。[全新 runner CI](https://github.com/troywjz/AeroBase-PX4-ROS2/actions/runs/38060815092)、原生 text / JSON 和 WSL2 摘要。 |
| 3. 机器可读遥测 | 默认 text 保持兼容，JSON schema v1 字段、类型、单位、frame 和状态有定义；missing / stale 不暴露缓存数值。 | 通过。[遥测契约](telemetry-contract.md)、45 项测试、真实 JSON SITL 检查。 |
| 4. 环境与运行诊断 | 缺依赖、源码不匹配、包链接异常、启动失败或链路无数据时提供诊断；保护已有源码和既有进程。 | 通过。[静态 doctor](runtime-diagnostics.md)、启动预检、SITL 观测与回归测试。静态文件诊断不代表服务或飞行健康。 |
| 5. 测试、CI 与摘要 | 核心逻辑与真实 ROS 消息适配测试通过；原生 CI 覆盖完整链路；公开摘要保留证据范围且不携带原始私人日志。 | 通过。原生和 WSL2 均为 45 项测试通过；CI 仅上传白名单摘要，见[发布记录](evidence/2026-10-10-v0.1.md)。 |
| 6. 发布材料 | MIT、贡献说明、问题模板、CHANGELOG、版本标记与 GitHub Release 齐备。 | 材料齐备。[贡献指南](../CONTRIBUTING.md)、[CHANGELOG](../CHANGELOG.md)、[版本发布](https://github.com/troywjz/AeroBase-PX4-ROS2/releases/tag/v0.1.0)。标签和 Release 在审核合并后创建并核对。 |

## 范围与证据边界

状态与里程计是连接状态所需的必选流；电池与全局位置为可选遥测。`vehicle_monitor` 只报告所选字段及新鲜度，不判断是否具备起飞条件。

ARM、实体飞控、实体传感器、真实飞行、Gazebo GUI 视觉验收、Offboard 或其他控制、MAVLink 后端、ArduPilot 与具体应用闭环均不属于 v0.1.0 完成门。它们需要独立的需求、接口、失联行为和验证证据。SITL 结果不代表实体飞行能力或安全认证。证据等级见[验证方法](validation.md)。