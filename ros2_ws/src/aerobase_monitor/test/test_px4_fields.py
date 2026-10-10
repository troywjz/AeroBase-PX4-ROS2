"""Run with the built ROS workspace sourced; core-only CI skips this module."""
import math
import json

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
    data = adapter.state.snapshot(adapter.state.samples["battery"].received_at)["streams"]["battery"]["data"]
    assert data == {"connected": True, "remaining_fraction": None, "voltage_v": None, "current_a": None}
    json.dumps(adapter.state.snapshot(adapter.state.samples["battery"].received_at), allow_nan=False)
    msg.timestamp = 2
    msg.connected = False
    adapter.on_battery(msg)
    assert adapter.state.samples["battery"].fields["battery"] == "not connected"


def test_battery_nonfinite_values_become_json_null(adapter):
    msg = messages.BatteryStatus(timestamp=2, connected=True, remaining=math.inf,
                                 voltage_v=12.0, current_a=math.nan)
    adapter.on_battery(msg)
    data = adapter.state.snapshot(adapter.state.samples["battery"].received_at)["streams"]["battery"]["data"]
    assert data == {"connected": True, "remaining_fraction": None, "voltage_v": 12.0, "current_a": None}
    json.dumps(adapter.state.snapshot(adapter.state.samples["battery"].received_at), allow_nan=False)


def test_global_position_respects_validity_flags(adapter):
    msg = messages.VehicleGlobalPosition(timestamp=1, lat=47.397742, lon=8.545594, alt=488.0, lat_lon_valid=False, alt_valid=False)
    adapter.on_global(msg)
    text = adapter.state.samples["global_position"].fields["global_position"]
    assert "lat/lon=unknown" in text
    assert "alt=unknown" in text
    assert "47.397" not in text
    assert adapter.state.snapshot(adapter.state.samples["global_position"].received_at)["streams"]["global_position"]["data"] == {
        "latitude_deg": None, "longitude_deg": None, "altitude_amsl_m": None,
    }


def test_global_position_json_keeps_valid_values_and_rejects_out_of_range(adapter):
    msg = messages.VehicleGlobalPosition(timestamp=2, lat=47.397742, lon=8.545594, alt=488.0, lat_lon_valid=True, alt_valid=True)
    adapter.on_global(msg)
    data = adapter.state.snapshot(adapter.state.samples["global_position"].received_at)["streams"]["global_position"]["data"]
    assert data == {"latitude_deg": 47.397742, "longitude_deg": 8.545594, "altitude_amsl_m": 488.0}
    msg.timestamp = 3
    msg.lat = 91.0
    adapter.on_global(msg)
    data = adapter.state.snapshot(adapter.state.samples["global_position"].received_at)["streams"]["global_position"]["data"]
    assert data == {"latitude_deg": None, "longitude_deg": 8.545594, "altitude_amsl_m": 488.0}


def test_odometry_preserves_frames_and_invalid_components(adapter):
    msg = messages.VehicleOdometry(timestamp=1, position=[math.nan, 1.0, 2.0], velocity=[0.0, math.inf, 0.0], pose_frame=1, velocity_frame=3)
    adapter.on_odometry(msg)
    fields = adapter.state.samples["odometry"].fields
    assert "unknown" in fields["position"]
    assert "[ned(1)]" in fields["position"]
    assert "[body_frd(3)]" in fields["velocity"]
    data = adapter.state.snapshot(adapter.state.samples["odometry"].received_at)["streams"]["odometry"]["data"]
    assert data["position_m"] == [None, 1.0, 2.0]
    assert data["velocity_m_s"] == [0.0, None, 0.0]
    assert data["pose_frame"] == {"value": 1, "name": "ned"}
    assert data["velocity_frame"] == {"value": 3, "name": "body_frd"}
    json.dumps(adapter.state.snapshot(adapter.state.samples["odometry"].received_at), allow_nan=False)
    msg.timestamp = 2
    msg.pose_frame = 999
    msg.velocity_frame = 999
    adapter.on_odometry(msg)
    data = adapter.state.snapshot(adapter.state.samples["odometry"].received_at)["streams"]["odometry"]["data"]
    assert data["pose_frame"] == {"value": 999, "name": "unknown"}
    assert data["position_m"] == [None, 1.0, 2.0]


def test_status_json_contains_numeric_enums_and_boolean_failsafe(adapter):
    msg = messages.VehicleStatus(timestamp=1, arming_state=messages.VehicleStatus.ARMING_STATE_DISARMED,
                                 nav_state=messages.VehicleStatus.NAVIGATION_STATE_MANUAL, failsafe=True)
    adapter.on_status(msg)
    data = adapter.state.snapshot(adapter.state.samples["status"].received_at)["streams"]["status"]["data"]
    assert data == {
        "arming_state": messages.VehicleStatus.ARMING_STATE_DISARMED,
        "arming_state_name": "disarmed",
        "nav_state": messages.VehicleStatus.NAVIGATION_STATE_MANUAL,
        "nav_state_name": "manual",
        "failsafe": True,
    }
