import math

import pytest

from aerobase_monitor.telemetry import TelemetryState, enum_label, px4_topic, vector


def test_missing_required_streams_and_optional_data():
    state = TelemetryState()
    assert state.connection(10) == "waiting"
    state.update("battery", {"battery": "100%"}, 1, 10)
    assert state.connection(10) == "waiting"
    state.update("status", {"arming": "disarmed"}, 1, 10)
    assert state.connection(10) == "degraded"
    state.update("odometry", {"position": "(1, 2, 3) m [NED]"}, 1, 10)
    assert state.connection(10) == "connected"
    assert "unknown (no data)" in state.report(10)


def test_disconnect_masks_cached_arming_and_position():
    state = TelemetryState(stale_timeout_s=3)
    state.update("status", {"arming": "armed"}, 1, 10)
    state.update("odometry", {"position": "previous position"}, 1, 10)
    assert state.connection(13) == "disconnected"
    report = state.report(13)
    assert "Arming: stale (age=3.0s)" in report
    assert "previous position" not in report
    assert "Arming: armed" not in report


def test_one_stream_stops_then_recovers():
    state = TelemetryState()
    state.update("status", {}, 1, 10)
    state.update("odometry", {}, 1, 10)
    state.update("status", {}, 2, 13)
    assert state.connection(13) == "degraded"
    state.update("odometry", {}, 2, 13.1)
    assert state.connection(13.1) == "connected"


def test_duplicate_timestamps_do_not_refresh_but_px4_restart_does():
    state = TelemetryState()
    state.update("status", {"arming": "disarmed"}, 100, 10)
    state.update("status", {"arming": "armed"}, 100, 13)
    assert not state.fresh("status", 13)
    state.update("status", {"arming": "disarmed"}, 1, 14)
    assert state.fresh("status", 14)
    assert state.field("status", "arming", 14) == "disarmed"


def test_zero_source_timestamp_is_not_live_data():
    state = TelemetryState()
    state.update("status", {}, 0, 1)
    assert state.connection(1) == "waiting"


def test_topic_version_and_vehicle_namespace():
    class Versioned:
        MESSAGE_VERSION = 1

    class Unversioned:
        MESSAGE_VERSION = 0

    assert px4_topic("vehicle_status", Versioned) == "/fmu/out/vehicle_status_v1"
    assert px4_topic("vehicle_odometry", Unversioned, "/uav_1/") == "/uav_1/fmu/out/vehicle_odometry"
    with pytest.raises(ValueError):
        px4_topic("vehicle_status", Versioned, "uav-1")


def test_invalid_numbers_and_unknown_enums():
    class Navigation:
        NAVIGATION_STATE_OFFBOARD = 14
        NAVIGATION_STATE_MAX = 31

    assert enum_label(Navigation, "NAVIGATION_STATE_", 14) == "offboard(14)"
    assert enum_label(Navigation, "NAVIGATION_STATE_", 31) == "unknown(31)"
    assert vector([math.nan, math.inf, 0]) == "(unknown, unknown, 0.00)"


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError):
        TelemetryState(timeout)
