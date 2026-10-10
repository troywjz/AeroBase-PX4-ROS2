# Changelog

本文件记录对部署者和集成者有影响的版本变更。

## v0.1.0 — 2026-10-10

### Added

- 增加只读运行环境诊断工具，可检查 Ubuntu 目标、ROS 环境、锁定源码和运行目录，并提供 JSON 与严格就绪模式。
- 为 `vehicle_monitor` 增加可选 schema v1 JSON 遥测输出，默认 text 输出保持兼容；缺失和 stale 流不包含可被误认作当前值的数值数据。
- 固定源码获取和运行目录检查，遇到不匹配的现有源码或包链接时保留原内容并给出诊断。
- 增加公开证据摘要工具，仅输出经过白名单校验的检查、时间、版本、提交和已知设置。

### Validation status

- 当前记录的 45 项自动化测试（含真实 PX4 ROS 消息类适配测试）通过；WSL2 SITL 的 JSON 遥测断连与恢复检查通过。
- 全新 Ubuntu 24.04 amd64 runner 完成系统依赖安装、普通用户构建、严格 doctor、45 项测试，以及 text 和订阅先就绪的 JSON SITL 验收。公开版本及检查摘要见[发布证据](docs/evidence/2026-10-10-v0.1.md)。模拟器结果不代表实体硬件或真实飞行验收。
- ARM64、Gazebo GUI、控制/Offboard、MAVLink、ArduPilot 与其他飞行器后端不属于 v0.1.0 已交付范围。
