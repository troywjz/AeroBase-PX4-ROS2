# 验证方法与证据

## 证据层级

| 证据 | 可支持的结论 | 不支持的结论 |
| --- | --- | --- |
| 静态代码与文档核对 | 接口和职责划分、是否存在控制入口 | 运行时收到真实消息 |
| Python 单元测试 | 新鲜度、过期遮蔽、版本 Topic、未知值等逻辑 | PX4、DDS、ROS 与模拟器集成 |
| 固定配置下的 SITL 集成测试 | 指定环境中的模拟数据链路与报告项 | 实体硬件可靠性、真实飞行能力或认证 |
| 实体台架或飞行试验 | 仅限该试验方案覆盖的真实系统表现 | 超出试验范围的安全或商业承诺 |

## SITL 集成验收条件

测试应记录实际运行目标为 PX4 SITL + Gazebo X500、软件版本和源码提交、启动命令、关键日志及结果文件。Headless 仿真可验证模型和数据链路；未执行 GUI 视觉检查时，不能标记 GUI 验收通过。

数据链路验收检查 ROS 图是否包含预期 Topic 与 `vehicle_monitor`，VehicleStatus 和 VehicleOdometry 是否持续更新并使 monitor 显示 `connected`。若电池和全局位置列为通过项，必须收到实际消息，单独发现 Topic 不足以通过。输出应保留源字段、单位和 frame；无效值不应伪造为零。monitor 不应发布 `/fmu/in` 消息或创建 PX4 命令服务客户端，测试中飞控应保持未解锁。

断连和恢复测试在 monitor 已连接后停止本次测试启动的 Agent。必要流过期后应显示 disconnected，Arming、Position 等缓存字段应标为 stale；恢复 Agent 后应重新 connected。单条必要流停止应显示 degraded；单元测试覆盖此行为，SITL 单流故障注入需另行记录。

## 证据记录

自动集成检查生成 SITL、Agent、monitor 日志，ROS Topic/Node 图、Gazebo 模型列表、`versions.json` 和 `result.json`。原始结果保存在本地忽略目录 `.runtime/evidence/`，可公开摘要保存在 `docs/evidence/`。记录使用实际执行日期和明确时区，失败、中断或超时均保留其真实结果。

生成脱敏的公开 JSON 摘要时，从仓库根目录将输入运行目录和输出文件替换为实际路径：

```bash
python3 scripts/summarize_evidence.py INPUT/result.json --output OUTPUT
```

摘要器只输出通过白名单校验的检查结果、UTC 时间、软件版本、固定源码提交和已知设置，不复制原始命令、错误文本、内核、主机绝对路径或设备/代理信息。公开前仍应复核摘要和周边材料。遥测节点的机器输出契约见[只读遥测 JSON 契约](telemetry-contract.md)。

原生 Ubuntu runner 与 WSL2 的 45 项自动化测试（含真实 PX4 ROS 消息类适配测试）通过。原生 CI 从新运行目录安装依赖、构建全部锁定源码，再验证 text、订阅先就绪的 schema v1 JSON、四条遥测及 Agent 断连恢复；只上传白名单摘要。结果见[发布验收记录](evidence/2026-10-10-v0.1.md)和[原生 CI](https://github.com/troywjz/AeroBase-PX4-ROS2/actions/runs/38060815092)。文档改动只运行核心检查；涉及源码、部署脚本、锁文件或测试的 PR 运行完整集成 CI，也可手动触发。

既有 WSL2 版本和运行记录见[Phase 1 集成测试报告](evidence/2026-10-09-phase1.md)及[版本记录](evidence/2026-10-09-versions.json)。实体硬件、控制功能和 GUI 视觉验收未验证。
