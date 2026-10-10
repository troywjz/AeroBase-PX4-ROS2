# AeroBase — General-Purpose Aerial Robotics Integration Framework

**AeroBase 通用飞行机器人集成框架 · PX4 + ROS 2 部署与集成基线**

AeroBase 是面向部署者、集成项目和贡献者的开源工程基线，用于部署和集成 PX4 与 ROS 2。仓库固定一组软件源码版本，提供依赖安装和运行环境构建脚本，并包含一个连接 PX4 SITL 与 Gazebo X500 的只读遥测监测节点。

GitHub：[troywjz/AeroBase-PX4-ROS2](https://github.com/troywjz/AeroBase-PX4-ROS2)

## 快速部署

v0.1.0 面向 Ubuntu 24.04 amd64。全新 GitHub 托管 Ubuntu 24.04 runner 与 WSL2 Ubuntu 24.04 的 headless 集成验收均已通过，具体条件见[发布验收记录](docs/evidence/2026-10-10-v0.1.md)。以下命令在 Ubuntu Bash 中运行：

```bash
git clone https://github.com/troywjz/AeroBase-PX4-ROS2.git ~/AeroBase-PX4-ROS2
cd ~/AeroBase-PX4-ROS2
bash scripts/install_ubuntu_deps.sh
bash scripts/build_runtime.sh
```

依赖安装通过系统包管理器执行，可能需要 `sudo`。运行源码和构建产物默认放在 `~/aerobase-runtime`；构建应以普通用户执行。打开三个 Ubuntu 终端，在仓库目录分别运行：

```bash
# 终端 1：Micro XRCE-DDS Agent
bash scripts/run_agent.sh

# 终端 2：PX4 SITL + Gazebo Harmonic X500；去掉 HEADLESS=1 可启动界面
HEADLESS=1 bash scripts/run_sitl.sh

# 终端 3：只读 ROS 2 遥测监测
bash scripts/run_monitor.sh
```

参数覆盖和运行目录设置见[运行配置](#运行配置)。完整验收流程见[验证文档](docs/validation.md)；安装与排错步骤以脚本和验证记录为准。

安装、构建后，可在当前终端加载 ROS 环境并检查运行目录：

```bash
source /opt/ros/jazzy/setup.bash
source ~/aerobase-runtime/ros2_ws/install/setup.bash
bash scripts/doctor.sh --strict
```

`--strict` 会将警告也视为未就绪；使用 `--json` 可输出机器可读诊断。机器遥测可通过 `bash scripts/run_monitor.sh --ros-args -p output_format:=json` 启用，默认仍为 text。详细字段见[遥测 JSON 契约](docs/telemetry-contract.md)，环境检查见[诊断指南](docs/runtime-diagnostics.md)。

## 软件版本基线

| 组件 | 基线 |
| --- | --- |
| 操作系统目标 | Ubuntu 24.04 amd64；原生 runner 与 WSL2 已验证 |
| 飞控栈 | PX4 v1.17.0 |
| ROS 2 | Jazzy、`rclpy`、Cyclone DDS RMW (`rmw_cyclonedds_cpp`) |
| 模拟器 | Gazebo Harmonic，X500 模型 |
| XRCE Agent | Micro XRCE-DDS Agent v2.4.3 |
| PX4 消息定义 | `px4_msgs` `release/1.17` 固定提交 |

源码版本记录在 [stack.lock.json](config/stack.lock.json)。系统软件包来自 Ubuntu、ROS 和 Gazebo 软件仓库，实际安装版本见[发布验证证据](docs/evidence/2026-10-10-v0.1.md)。源码修订已固定；发行版软件包来自对应仓库，可能随仓库更新。

## 当前功能

PX4 通过 uXRCE-DDS Client 发布选定的 uORB 遥测。Micro XRCE-DDS Agent 将消息接入 ROS 2，`vehicle_monitor` 订阅：

- 必选：`VehicleStatus`、`VehicleOdometry`
- 可选：`BatteryStatus`、`VehicleGlobalPosition`

监测输出包括解锁状态、导航状态、Failsafe 标记、本地位置与速度，以及可用时的电池和全局位置。`connected` 表示两条必选流都在新鲜度窗口内更新；一条缺失时为 `degraded`，两条都过期时为 `disconnected`，尚未收到必选消息时为 `waiting`。缓存字段过期后标记为 `stale`。这些状态反映遥测新鲜度，不评估是否具备起飞条件。

`vehicle_monitor` 只订阅遥测，不包含 PX4 命令发布器或命令服务客户端。解锁、模式切换、参数写入、Offboard、执行器输出及其他控制操作均不属于当前基线。

## 运行配置

ROS 节点参数在启动后只读：

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `vehicle_namespace` | 空 | 为车辆 PX4 Topic 添加前缀 |
| `report_interval_s` | `1.0` | 终端报告周期 |
| `stale_timeout_s` | `3.0` | 遥测新鲜度窗口 |
| `enable_battery` | `true` | 是否订阅可选电池遥测 |
| `enable_global_position` | `true` | 是否订阅可选全局位置遥测 |
| `output_format` | `text` | 文本报告或 schema v1 JSON 行 |

参数覆盖示例：

```bash
bash scripts/run_monitor.sh --ros-args -p stale_timeout_s:=5.0
```

`vehicle_namespace` 必须与 PX4 发布的 Topic 前缀一致。XRCE 端口与 DDS domain 也需在对应进程中保持一致。

脚本支持环境变量：`AEROBASE_RUNTIME` 指定运行目录，默认 `~/aerobase-runtime`；`AEROBASE_BUILD_JOBS` 指定并行构建任务数，默认 `4`；`AEROBASE_XRCE_PORT` 指定 XRCE UDP 端口，默认 `8888`。`ROS_DOMAIN_ID` 默认 `0`。监测节点默认使用 Cyclone DDS；其他 ROS RMW 可通过 `RMW_IMPLEMENTATION` 选择，但需要独立集成验证。网络失败时，可用 `AEROBASE_GIT_PROXY` 为源码获取的单次 Git 重试指定代理。

## 验证集成

在仓库根目录运行 SITL 自动验证：

```bash
bash scripts/verify_sitl.sh --monitor-first --output "$PWD/.runtime/evidence/run"
```

脚本启动 PX4 SITL、Gazebo X500、XRCE Agent 和监测节点，检查必选及可选遥测、过期与恢复行为、只读边界，随后关闭本次启动的进程。添加 `--monitor-output json` 可验证机器输出。原始日志放在 Git 忽略的 `.runtime/evidence/` 目录；公开的[发布验收记录](docs/evidence/2026-10-10-v0.1.md)包含原生 runner、WSL2、软件版本和范围限制。单元测试与 SITL 证据各自有适用范围，均不能证明实体飞行表现或硬件验收。

## 架构与路线图

[系统架构与接口](docs/architecture.md)说明模块职责、DDS 与 MAVLink 链路、消息与 QoS 契约、坐标系、时间处理和扩展接口。[工程能力与路线图](docs/roadmap.md)记录当前实现、证据和待验证项。

发布范围和完成门见[v0.1.0 发布验收标准](docs/release-v0.1.md)，当前变更记录见[CHANGELOG](CHANGELOG.md)；验证证据的公开摘要命令见[验证方法](docs/validation.md)。贡献流程见[贡献指南](CONTRIBUTING.md)。

本仓库代码采用 [MIT License](LICENSE)。PX4、ROS 2、Gazebo、Micro XRCE-DDS Agent 及其他第三方组件保留各自许可证；使用时应查阅对应上游项目和软件包的适用条款。
