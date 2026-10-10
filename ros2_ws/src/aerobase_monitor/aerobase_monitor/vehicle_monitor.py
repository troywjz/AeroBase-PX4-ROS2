"""PX4 DDS adapter: subscriptions only; no vehicle command publisher/client."""
import json
import math
import os
import time

import rclpy
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.msg import ParameterDescriptor
from px4_msgs.msg import BatteryStatus, VehicleGlobalPosition, VehicleOdometry, VehicleStatus

from aerobase_monitor.telemetry import TelemetryState, enum_label, enum_name, number, px4_topic, vector


def _finite(value):
    """Normalize a PX4 numeric value to a JSON-safe number or null."""
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _vector(values):
    return [_finite(value) for value in values]


class VehicleMonitor(Node):
    def __init__(self) -> None:
        super().__init__("vehicle_monitor")
        readonly = ParameterDescriptor(read_only=True)
        self.declare_parameter("vehicle_namespace", "", readonly)
        self.declare_parameter("report_interval_s", 1.0, readonly)
        self.declare_parameter("stale_timeout_s", 3.0, readonly)
        self.declare_parameter("enable_battery", True, readonly)
        self.declare_parameter("enable_global_position", True, readonly)
        self.declare_parameter("output_format", "text", readonly)
        namespace = self.get_parameter("vehicle_namespace").value
        interval = float(self.get_parameter("report_interval_s").value)
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("report_interval_s must be finite and positive")
        self.state = TelemetryState(float(self.get_parameter("stale_timeout_s").value))
        self.battery_enabled = self.get_parameter("enable_battery").value
        self.global_enabled = self.get_parameter("enable_global_position").value
        self.output_format = self.get_parameter("output_format").value
        if self.output_format not in ("text", "json"):
            raise ValueError("output_format must be 'text' or 'json'")
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
        arming_state = int(msg.arming_state)
        nav_state = int(msg.nav_state)
        fields = {
            "arming": enum_label(VehicleStatus, "ARMING_STATE_", arming_state),
            "nav_state": enum_label(VehicleStatus, "NAVIGATION_STATE_", nav_state),
            "failsafe": str(msg.failsafe).lower(),
        }
        data = {
            "arming_state": arming_state,
            "arming_state_name": enum_name(VehicleStatus, "ARMING_STATE_", arming_state),
            "nav_state": nav_state,
            "nav_state_name": enum_name(VehicleStatus, "NAVIGATION_STATE_", nav_state),
            "failsafe": bool(msg.failsafe),
        }
        self.state.update("status", fields, msg.timestamp, time.monotonic(), data)

    def on_odometry(self, msg: VehicleOdometry) -> None:
        pose_frame = enum_label(VehicleOdometry, "POSE_FRAME_", msg.pose_frame)
        velocity_frame = enum_label(VehicleOdometry, "VELOCITY_FRAME_", msg.velocity_frame)
        fields = {
            "position": f"{vector(msg.position)} m [{pose_frame}]",
            "velocity": f"{vector(msg.velocity)} m/s [{velocity_frame}]",
        }
        data = {
            "position_m": _vector(msg.position),
            "velocity_m_s": _vector(msg.velocity),
            "pose_frame": {
                "value": int(msg.pose_frame),
                "name": enum_name(VehicleOdometry, "POSE_FRAME_", msg.pose_frame),
            },
            "velocity_frame": {
                "value": int(msg.velocity_frame),
                "name": enum_name(VehicleOdometry, "VELOCITY_FRAME_", msg.velocity_frame),
            },
        }
        self.state.update("odometry", fields, msg.timestamp, time.monotonic(), data)

    def on_battery(self, msg: BatteryStatus) -> None:
        if not msg.connected:
            text = "not connected"
        else:
            remaining = number(msg.remaining * 100, 1) + "%" if math.isfinite(msg.remaining) and 0 <= msg.remaining <= 1 else "unknown"
            voltage = number(msg.voltage_v) + " V" if math.isfinite(msg.voltage_v) and msg.voltage_v > 0 else "unknown"
            current = number(msg.current_a) + " A" if math.isfinite(msg.current_a) and msg.current_a >= 0 else "unknown"
            text = f"{remaining}, {voltage}, {current} (id={msg.id})"
        connected = bool(msg.connected)
        remaining_value = _finite(msg.remaining)
        voltage_value = _finite(msg.voltage_v)
        current_value = _finite(msg.current_a)
        data = {
            "connected": connected,
            "remaining_fraction": (
                remaining_value
                if connected and remaining_value is not None and 0 <= remaining_value <= 1
                else None
            ),
            "voltage_v": (
                voltage_value if connected and voltage_value is not None and voltage_value > 0 else None
            ),
            "current_a": (
                current_value if connected and current_value is not None and current_value >= 0 else None
            ),
        }
        self.state.update("battery", {"battery": text}, msg.timestamp, time.monotonic(), data)

    def on_global(self, msg: VehicleGlobalPosition) -> None:
        valid_lat_lon = msg.lat_lon_valid and math.isfinite(msg.lat) and math.isfinite(msg.lon) and -90 <= msg.lat <= 90 and -180 <= msg.lon <= 180
        lat_lon = f"lat={msg.lat:.7f}, lon={msg.lon:.7f}" if valid_lat_lon else "lat/lon=unknown"
        alt = number(msg.alt) if msg.alt_valid else "unknown"
        latitude = _finite(msg.lat)
        longitude = _finite(msg.lon)
        altitude = _finite(msg.alt)
        data = {
            "latitude_deg": (
                latitude
                if msg.lat_lon_valid and latitude is not None and -90 <= latitude <= 90
                else None
            ),
            "longitude_deg": (
                longitude
                if msg.lat_lon_valid and longitude is not None and -180 <= longitude <= 180
                else None
            ),
            "altitude_amsl_m": altitude if msg.alt_valid and altitude is not None else None,
        }
        self.state.update("global_position", {"global_position": f"{lat_lon}, alt={alt} m AMSL [WGS84]"}, msg.timestamp, time.monotonic(), data)

    def report(self) -> None:
        now = time.monotonic()
        if self.output_format == "json":
            report = self.state.snapshot(
                now,
                self.get_parameter("vehicle_namespace").value,
                self.battery_enabled,
                self.global_enabled,
            )
            print(json.dumps(report, allow_nan=False, separators=(",", ":")), flush=True)
        else:
            print(self.state.report(now, self.battery_enabled, self.global_enabled) + "\n", flush=True)


def main(args=None) -> None:
    # Keep ROS framework logs away from JSON report lines on stdout.
    os.environ["RCUTILS_LOGGING_USE_STDOUT"] = "0"
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
