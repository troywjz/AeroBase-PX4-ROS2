# Ubuntu / WSL2 部署、构建与运行

本指南部署 PX4 SITL、Gazebo Harmonic、ROS 2 Jazzy 与 `vehicle_monitor` 的只读遥测链路。锁定组合及验证配置见 [`stack.lock.json`](../config/stack.lock.json) 和[集成测试报告](evidence/2026-10-09-phase1.md)。

## 环境基线

推荐 Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic、PX4 v1.17.0 和 Micro XRCE-DDS Agent v2.4.3。已记录的完整集成验证运行于 WSL2 Ubuntu 24.04.4；该结果不代表所有原生 Ubuntu 或其他机器均已验收。不要混用 Ubuntu 22.04 / Humble / Agent v2.4.2 教程命令。

版本依据：[PX4 ROS 2 指南](https://docs.px4.io/main/en/ros2/user_guide)、[PX4 XRCE Agent 版本表](https://docs.px4.io/main/en/middleware/uxrce_dds#version-selection)、[PX4 v1.17.0](https://github.com/PX4/PX4-Autopilot/releases/tag/v1.17.0)、[该版本 Ubuntu 安装脚本](https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/Tools/setup/ubuntu.sh)。

Windows 上从 PowerShell 进入 WSL：

```powershell
wsl -d Ubuntu-24.04
```

以下命令在 Ubuntu Bash 中运行。建议把仓库放在 Linux 文件系统：

```bash
git clone https://github.com/troywjz/AeroBase-PX4-ROS2.git ~/AeroBase-PX4-ROS2
cd ~/AeroBase-PX4-ROS2
```

如果仓库位于 Windows 文件系统，对应 WSL 路径格式为 `/mnt/<drive>/<path>/AeroBase-PX4-ROS2`，将占位符替换为实际盘符和目录。第三方源码及构建产物默认放在 Linux 路径 `~/aerobase-runtime`；也可通过 `AEROBASE_RUNTIME` 指定其他目录，并在构建和运行时保持一致。

## 安装系统依赖

```bash
bash scripts/install_ubuntu_deps.sh
```

脚本安装 ROS 2 apt 源、Gazebo apt 源、Jazzy ROS Base、Gazebo Harmonic 和构建依赖，需要管理员权限。它不会全量升级发行版、卸载现有模拟器或安装实体飞控 NuttX 工具链。

此只读 DDS 部署不需要 QGroundControl、MAVSDK、MAVROS、`ros_gz_bridge` 或 Gazebo `/clock` 桥。ROS 节点通过 DDS 订阅 PX4 消息；Gazebo 传感器或世界数据接口属于另行集成的范围。

## 获取源码并构建

```bash
bash scripts/build_runtime.sh
```

脚本按锁文件获取 PX4、`px4_msgs`、Agent 及日志依赖，核对四条遥测消息字段，再构建 PX4 SITL、Agent 和 ROS 2 workspace。若源码目录已有修改或提交与锁定值不符，脚本会停止，不会重置这些目录。

Agent 使用系统 Jazzy 的 Fast DDS / Fast CDR 和锁定的 spdlog v1.9.2；运行脚本会加载所需动态库环境。ROS 端默认使用 Cyclone DDS RMW。不要直接将 Agent 的固定日志依赖替换为 Ubuntu 更新版 spdlog，该替换组合曾发生编译不兼容。ROS 2 的 RMW 说明见[官方文档](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/RMW-Implementations.rst)。

默认并行构建数为 4，内存受限时可以调低：

```bash
AEROBASE_BUILD_JOBS=2 bash scripts/build_runtime.sh
```

PX4 Python 依赖位于独立的 `px4-venv`；ROS 2 使用 Ubuntu 系统 Python。运行 ROS 2 命令时不要激活 PX4 虚拟环境。

构建后，在准备运行 ROS 2 命令的同一个终端先加载 Jazzy 和工作区，再运行严格环境诊断：

```bash
source /opt/ros/jazzy/setup.bash
source ~/aerobase-runtime/ros2_ws/install/setup.bash
bash scripts/doctor.sh --strict
```

若使用 `AEROBASE_RUNTIME` 指定其他运行目录，应 source 该目录中的 `ros2_ws/install/setup.bash`。JSON 诊断可用 `bash scripts/doctor.sh --json`；完整行为和状态含义见[运行环境诊断](runtime-diagnostics.md)。

## 启动仿真和监测节点

分别在三个 Ubuntu 终端中进入仓库目录，并按以下顺序启动：

```bash
# 终端 A：XRCE Agent，UDP 8888；同一连接端口只运行一个 Agent
bash scripts/run_agent.sh
```

```bash
# 终端 B：无界面 PX4 SITL + Gazebo X500
HEADLESS=1 bash scripts/run_sitl.sh
```

```bash
# 终端 C：ROS 2 遥测监测节点
bash scripts/run_monitor.sh
```

默认输出为兼容的 text。需要机器读取时，启动参数可选择 schema v1 JSON：

```bash
bash scripts/run_monitor.sh --ros-args -p output_format:=json
```

JSON 每行一个报告，字段、单位、缺失与 stale 语义见[只读遥测 JSON 契约](telemetry-contract.md)。

`HEADLESS=1` 关闭 Gazebo 图形界面，仿真仍运行。需要图形界面时去掉该变量；WSL 环境还需 WSLg 图形支持。界面显示不属于当前已记录的视觉验收范围。

可在节点启动时覆盖监测参数：

```bash
bash scripts/run_monitor.sh --ros-args \
  -p report_interval_s:=2.0 \
  -p stale_timeout_s:=5.0 \
  -p enable_battery:=false \
  -p enable_global_position:=false
```

默认 DDS domain 为 `ROS_DOMAIN_ID=0`，XRCE UDP 端口为 8888。启动时可能先显示 `waiting` 或 `degraded`，必要数据流到达后显示 `connected`。该状态只表示必要遥测持续更新，不代表飞控可解锁或可起飞。参数仅在启动时设定；车辆命名空间是 PX4 Topic 前缀，不等同于更改 ROS Node namespace。

## 查看 ROS 图和数据

```bash
source /opt/ros/jazzy/setup.bash
source ~/aerobase-runtime/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 topic list -t
ros2 node info /vehicle_monitor
ros2 topic info /fmu/out/vehicle_status_v1 --verbose
ros2 topic echo /fmu/out/vehicle_status_v1 --once --qos-reliability best_effort
ros2 topic echo /fmu/out/vehicle_odometry --once --qos-reliability best_effort
gz model --list
```

Topic 列表证明接口发现；`echo` 或 monitor 收到有效更新才证明消息已到达。节点内建 `/rosout` 和 `/parameter_events` 发布不属于 PX4 控制接口。

## 本地测试与 SITL 集成检查

运行 Python 检查：

```bash
bash scripts/check_local.sh
```

若需包含基于构建后 PX4 消息类的字段适配检查，先 source workspace，再执行：

```bash
source /opt/ros/jazzy/setup.bash
source ~/aerobase-runtime/ros2_ws/install/setup.bash
bash scripts/check_local.sh
```

停止手动启动的 SITL、Agent 和 monitor 后，可运行自动集成检查：

```bash
bash scripts/verify_sitl.sh --output "$PWD/.runtime/evidence/run-001"
```

`--monitor-first` 用于覆盖 ROS 监测节点早于 PX4 启动的情形。检查会启动并清理本次创建的进程，也会测试 Agent 断开和恢复。若 PX4 已在运行或 UDP 8888 已占用，检查会退出，不会关闭既有进程。输出目录必须是新目录，避免覆盖历史证据。原始结果保存在 Git 忽略目录 `.runtime/evidence/`。

## 常见检查

| 现象 | 检查项 |
| --- | --- |
| 没有 `/fmu/out` Topic | Agent 端口、SITL client 日志、DDS domain |
| Topic 可见但没有消息 | 消息版本、Topic 名称、QoS、RMW 配置 |
| `connected` 但某些值为 unknown | 估计器有效性、字段语义、仿真传感器状态 |
| 持续显示 degraded | 缺失的是状态流还是里程计流；不要通过放宽超时掩盖缺流 |
| Agent 无法加载动态库 | 使用 `run_agent.sh` 配置的库路径和 Jazzy 环境 |
| ROS 2 无法导入消息 | workspace 是否构建并 source；是否误用 PX4 虚拟环境 |
| Gazebo GUI 无法显示 | 先用 headless 检查仿真链路，再检查 WSLg 图形支持 |
| GitHub 下载失败 | 检查网络访问；如使用代理，将设置限制在本次命令或仓库范围；apt 按失败源排查 |

在记录的 WSL2 验证配置中，Fast DDS ROS RMW 出现接口可见但未收到遥测的现象，根因未确定。Cyclone DDS ROS RMW 在两次独立集成检查中通过。该观察仅描述该验证配置，不说明 Fast DDS 在其他环境中的普遍行为。完成后在各进程终端按 Ctrl+C 退出。
