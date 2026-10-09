"""PX4 DDS adapter: subscriptions only; no vehicle command publisher/client."""
import math
import time

import rclpy
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.msg import ParameterDescriptor
from px4_msgs.msg import BatteryStatus, VehicleGlobalPosition, VehicleOdometry, VehicleStatus

from aerobase_monitor.telemetry import TelemetryState, enum_label, number, px4_topic, vector


class VehicleMonitor(Node):
    def __init__(self) -> None:
        super().__init__("vehicle_monitor")
        readonly = ParameterDescriptor(read_only=True)
        self.declare_parameter("vehicle_namespace", "", readonly)
        self.declare_parameter("report_interval_s", 1.0, readonly)
        self.declare_parameter("stale_timeout_s", 3.0, readonly)
        self.declare_parameter("enable_battery", True, readonly)
        self.declare_parameter("enable_global_position", True, readonly)
        namespace = self.get_parameter("vehicle_namespace").value
        interval = float(self.get_parameter("report_interval_s").value)
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("report_interval_s must be finite and positive")
        self.state = TelemetryState(float(self.get_parameter("stale_timeout_s").value))
        self.battery_enabled = self.get_parameter("enable_battery").value
        self.global_enabled = self.get_parameter("enable_global_position").value
        streams = [
            ("vehicle_status", VehicleStatus, self.on_status),
            ("vehicle_odometry", VehicleOdometry, self.on_odometry),
        ]
        if self.battery_enabled:
            streams.append(("battery_status", BatteryStatus, self.on_battery))
        if self.global_enabled:
            streams.append(("vehicle_global_position", VehicleGlobalPosition, self.on_global))
        self.telemetry_subscriptions = []
        for base, message_type, callback in streams:
            topic = px4_topic(base, message_type, namespace)
            self.telemetry_subscriptions.append(self.create_subscription(message_type, topic, callback, qos_profile_sensor_data))
            self.get_logger().info(f"Listening: {topic} [{message_type.__name__}]")
        # Keep disconnection reporting alive even when a /clock source pauses.
        self.steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.report_timer = self.create_timer(interval, self.report, clock=self.steady_clock)

    def on_status(self, msg: VehicleStatus) -> None:
        fields = {
            "arming": enum_label(VehicleStatus, "ARMING_STATE_", msg.arming_state),
            "nav_state": enum_label(VehicleStatus, "NAVIGATION_STATE_", msg.nav_state),
            "failsafe": str(msg.failsafe).lower(),
        }
        self.state.update("status", fields, msg.timestamp, time.monotonic())

    def on_odometry(self, msg: VehicleOdometry) -> None:
        pose_frame = enum_label(VehicleOdometry, "POSE_FRAME_", msg.pose_frame)
        velocity_frame = enum_label(VehicleOdometry, "VELOCITY_FRAME_", msg.velocity_frame)
        fields = {
            "position": f"{vector(msg.position)} m [{pose_frame}]",
            "velocity": f"{vector(msg.velocity)} m/s [{velocity_frame}]",
        }
        self.state.update("odometry", fields, msg.timestamp, time.monotonic())

    def on_battery(self, msg: BatteryStatus) -> None:
        if not msg.connected:
            text = "not connected"
        else:
            remaining = number(msg.remaining * 100, 1) + "%" if math.isfinite(msg.remaining) and 0 <= msg.remaining <= 1 else "unknown"
            voltage = number(msg.voltage_v) + " V" if math.isfinite(msg.voltage_v) and msg.voltage_v > 0 else "unknown"
            current = number(msg.current_a) + " A" if math.isfinite(msg.current_a) and msg.current_a >= 0 else "unknown"
            text = f"{remaining}, {voltage}, {current} (id={msg.id})"
        self.state.update("battery", {"battery": text}, msg.timestamp, time.monotonic())

    def on_global(self, msg: VehicleGlobalPosition) -> None:
        valid_lat_lon = msg.lat_lon_valid and math.isfinite(msg.lat) and math.isfinite(msg.lon) and -90 <= msg.lat <= 90 and -180 <= msg.lon <= 180
        lat_lon = f"lat={msg.lat:.7f}, lon={msg.lon:.7f}" if valid_lat_lon else "lat/lon=unknown"
        alt = number(msg.alt) if msg.alt_valid else "unknown"
        self.state.update("global_position", {"global_position": f"{lat_lon}, alt={alt} m AMSL [WGS84]"}, msg.timestamp, time.monotonic())

    def report(self) -> None:
        print(self.state.report(time.monotonic(), self.battery_enabled, self.global_enabled) + "\n", flush=True)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = VehicleMonitor()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
