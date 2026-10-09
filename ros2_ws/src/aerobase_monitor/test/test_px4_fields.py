"""Run with the built ROS workspace sourced; core-only CI skips this module."""
import math

import pytest

pytest.importorskip("rclpy", reason="ROS adapter checks need a sourced ROS workspace")
messages = pytest.importorskip("px4_msgs.msg", reason="Build and source the pinned px4_msgs first")

from aerobase_monitor.telemetry import TelemetryState
from aerobase_monitor.vehicle_monitor import VehicleMonitor


@pytest.fixture
def adapter():
    # Call field translators without starting a DDS participant or any process.
    node = object.__new__(VehicleMonitor)
    node.state = TelemetryState()
    return node


def test_battery_invalid_sentinels_are_not_zero_percent(adapter):
    msg = messages.BatteryStatus(timestamp=1, connected=True, remaining=-1.0, voltage_v=0.0, current_a=-1.0)
    adapter.on_battery(msg)
    text = adapter.state.samples["battery"].fields["battery"]
    assert text.count("unknown") == 3
    assert "0.0%" not in text
    msg.timestamp = 2
    msg.connected = False
    adapter.on_battery(msg)
    assert adapter.state.samples["battery"].fields["battery"] == "not connected"


def test_global_position_respects_validity_flags(adapter):
    msg = messages.VehicleGlobalPosition(timestamp=1, lat=47.397742, lon=8.545594, alt=488.0, lat_lon_valid=False, alt_valid=False)
    adapter.on_global(msg)
    text = adapter.state.samples["global_position"].fields["global_position"]
    assert "lat/lon=unknown" in text
    assert "alt=unknown" in text
    assert "47.397" not in text


def test_odometry_preserves_frames_and_invalid_components(adapter):
    msg = messages.VehicleOdometry(timestamp=1, position=[math.nan, 1.0, 2.0], velocity=[0.0, math.nan, 0.0], pose_frame=1, velocity_frame=3)
    adapter.on_odometry(msg)
    fields = adapter.state.samples["odometry"].fields
    assert "unknown" in fields["position"]
    assert "[ned(1)]" in fields["position"]
    assert "[body_frd(3)]" in fields["velocity"]
