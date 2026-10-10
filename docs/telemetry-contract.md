# 只读遥测 JSON 契约

`vehicle_monitor` 的只读启动参数 `output_format` 支持 `text`（默认）和 `json`。文本输出保持现有行格式。JSON 模式每个报告在 stdout 输出一行独立 JSON；ROS 日志输出到 stderr。该分流针对 ROS 日志配置，不承诺隔离任意第三方库可能写入 stdout 的内容。

## Schema v1

顶层字段为：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `schema_version` | integer | 固定为 `1`。 |
| `backend` | string | 固定为 `px4_dds`。 |
| `vehicle_namespace` | string | 节点参数的车辆命名空间；空字符串表示无前缀。 |
| `connection` | string | 必选流的整体新鲜度：`waiting`、`degraded`、`connected` 或 `disconnected`。 |
| `streams` | object | 本次启用流的状态与数据。必含 `status`、`odometry`；可选 `battery`、`global_position`。 |

每个 `streams` 项都含 `state`、`age_s`、`source_timestamp_us` 和 `data`。`state` 为 `missing`、`fresh` 或 `stale`。缺失流的年龄、源时间戳和数据均为 JSON `null`。新鲜流包含规范化数值数据。过期流保留最后一次源时间戳和接收年龄，但 `data` 为 `null`，避免将缓存值误认为当前值。关闭可选订阅时，该流从 `streams` 中省略。

```json
{"schema_version":1,"backend":"px4_dds","vehicle_namespace":"","connection":"connected","streams":{"status":{"state":"fresh","age_s":0.12,"source_timestamp_us":1234567,"data":{"arming_state":1,"arming_state_name":"disarmed","nav_state":0,"nav_state_name":"manual","failsafe":false}},"odometry":{"state":"fresh","age_s":0.11,"source_timestamp_us":1234550,"data":{"position_m":[1.0,2.0,-3.0],"velocity_m_s":[0.0,0.0,0.0],"pose_frame":{"value":1,"name":"ned"},"velocity_frame":{"value":1,"name":"ned"}}},"battery":{"state":"missing","age_s":null,"source_timestamp_us":null,"data":null},"global_position":{"state":"missing","age_s":null,"source_timestamp_us":null,"data":null}}}
```

## 数据字段

- `status.data` 提供 PX4 `arming_state` 和 `nav_state` 的整数枚举值及小写名称（分别为 `arming_state_name`、`nav_state_name`），以及布尔 `failsafe`。未知枚举名称为 `unknown`，整数原值仍保留。
- `odometry.data.position_m` 和 `velocity_m_s` 分别是米和米每秒的数组。分量顺序与 PX4 消息一致；单个非有限分量表示为 `null`。`pose_frame` 与 `velocity_frame` 含 PX4 整数 `value` 和小写 `name`。例如 `ned`、`body_frd`。本契约保留 PX4 NED/FRD 坐标，不隐式转换为 ENU/FLU；未知 frame 仍保留数值和 `unknown` 名称。
- `battery.data` 包含布尔 `connected`，以及 `remaining_fraction`（0 到 1）、`voltage_v`（伏特）和 `current_a`（安培）。断开、PX4 无效哨兵、超出范围或非有限的读数表示为 `null`；因此电压 0 和电流 -1 不作为有效测量值。
- `global_position.data` 包含 `latitude_deg`、`longitude_deg` 和 `altitude_amsl_m`。纬度、经度受消息有效标志和合法范围约束；高度以米表示，为 AMSL，并受 `alt_valid` 约束。无效字段各自为 `null`。

所有 JSON 数值均为有限数值；非有限浮点值输出为 `null`，不会产生非标准 JSON 的 NaN/Infinity。源时间戳是 PX4 消息时间戳，单位微秒；它可能与主机时钟不同步。`age_s` 使用本机单调时钟上的接收时刻计算，不从两种时钟直接相减。默认超时为 3 秒；超时边界及连接状态沿用监测器的新鲜度规则：两路必选流新鲜为 `connected`，其中一路新鲜为 `degraded`，必选流均不新鲜但至少曾收到一路为 `disconnected`，两路都未收到为 `waiting`。重复源时间戳不会刷新流；PX4 时间戳重置后可接受新样本。

v1 内字段名、类型和语义保持兼容。新增可选字段时应使既有消费者忽略未知字段；改变字段含义、单位或结构需提升 schema 版本。该契约供遥测观测与集成使用，不是通用数值 SDK，也不表示状态估计有效、具备起飞条件、飞行许可、安全认证或实体硬件/飞行验收。
