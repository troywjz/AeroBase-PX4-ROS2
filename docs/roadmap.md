# 工程能力与路线图

## 当前基线

AeroBase 当前 PX4 + ROS 2 基线使用 [stack.lock.json](../config/stack.lock.json) 中固定的软件源码组合，建立从 PX4 SITL 到 ROS 2 的遥测链路。当前节点只读，默认提供兼容的 text 报告，也可输出 [schema v1 JSON](telemetry-contract.md) 供机器读取。

| 功能 | 当前状态 | 证据或范围 |
| --- | --- | --- |
| Ubuntu 24.04 依赖安装与运行环境构建脚本 | 已实现 | 脚本目标为 Ubuntu 24.04；源码修订固定，发行版系统包版本单独记录 |
| 环境与运行目录诊断 | 已实现 | `scripts/doctor.sh` 只读检查；严格模式要求当前 shell 已 source ROS Jazzy 与构建后的 workspace |
| 固定源码获取与运行目录保护 | 已实现 | 获取器核对锁定提交并保留已有源码和不匹配的包链接；详见部署指南 |
| PX4 SITL + Gazebo Harmonic X500 | 原生 Ubuntu runner 与 WSL2 已通过 | headless 模型和数据链路；条件见发布验收记录 |
| PX4 uXRCE-DDS 到 ROS 2 | 原生 Ubuntu runner 与 WSL2 已通过 | XRCE Agent Fast DDS 与 ROS Cyclone DDS RMW |
| 状态与里程计必选订阅 | 原生 Ubuntu runner 与 WSL2 已收到消息 | 两路消息均到达 `vehicle_monitor` |
| 电池与全局位置可选订阅 | 原生 Ubuntu runner 与 WSL2 已收到消息 | 无效读数在 text 为 unknown，在 JSON 为 null |
| 新鲜度、断连与恢复状态 | 已实现并验证 | Agent 停止后的过期与重启恢复通过；单流故障由单元测试覆盖，未做独立 SITL 注入 |
| 只读边界 | 已实现并检查 | 无 PX4 命令发布器或命令服务客户端；记录运行期间 PX4 始终未解锁 |
| 机器可读遥测 | 已实现 | `output_format:=json` 输出 schema v1；缺失或 stale 流不提供数值数据 |
| Gazebo GUI 视觉验收 | 未完成 | 已记录的 SITL 运行均为 headless |
| 实体飞控或传感器验收 | 未完成 | 尚无硬件测试证据 |
| 飞行控制、Offboard、参数写入、执行器输出 | 未实现 | 不属于当前工程范围 |
| ArduPilot、MAVLink 或其他后端适配器 | 未实现 | 架构保留适配接口，尚无第二种后端实现 |

[发布验收记录](evidence/2026-10-10-v0.1.md)列出原生 runner 与 WSL2 的条件、命令、版本、摘要与范围。两种环境中 45 项自动化测试通过，文本和 schema v1 JSON SITL 断连恢复检查通过；原生 runner 从依赖安装和锁定源码构建开始复现。v0.1.0 的完成门见[发布验收标准](release-v0.1.md)。

## 后续验证与工程扩展

以下列出当前尚待验证的环境、能力和扩展。每项都需要先界定范围和验收证据，再作为已交付功能对外描述。

1. 扩展其他目标环境与 ARM64 的部署证据，并持续复验系统包更新后的兼容性。
2. 增加 Gazebo GUI 检查，将视觉验收与 headless 启动检查分别记录。
3. 定义实体飞控测试环境，验证真实遥测、传感器有效性、时序、重连和故障行为。
4. 在数据契约和验收条件明确后，评估遥测记录、回放或可视化工具。
5. 通过独立测试的适配器接入其他飞控后端，并形成稳定、公开的遥测契约。
6. 如需控制、Offboard、参数或执行器功能，先独立定义接口、失联策略和 SITL 验收，再决定实现。
7. 依据项目需求评估规划、SLAM、感知、伴随硬件、多机和 AI 集成，逐项明确系统边界及可验收条件。

当前适配、传输、消息、时间和坐标约定见[系统架构与接口](architecture.md)；证据等级和报告规则见[验证方法](validation.md)。
