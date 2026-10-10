import math
import json

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


def test_default_text_report_keeps_its_existing_rows_and_spacing():
    state = TelemetryState()
    assert state.report(10) == (
        "Vehicle: waiting\n"
        "Arming: unknown (no data)\n"
        "Nav state: unknown (no data)\n"
        "Failsafe: unknown (no data)\n"
        "Position: unknown (no data)\n"
        "Velocity: unknown (no data)\n"
        "Battery: unknown (no data)\n"
        "Global position: unknown (no data)"
    )


def test_snapshot_has_missing_fresh_and_stale_numeric_payloads():
    state = TelemetryState(stale_timeout_s=3)
    missing = state.snapshot(10)
    assert missing["connection"] == "waiting"
    assert missing["streams"]["status"] == {
        "state": "missing", "age_s": None, "source_timestamp_us": None, "data": None,
    }

    state.update("status", {"arming": "disarmed"}, 100, 10, {"arming_state": 1})
    state.update("odometry", {}, 200, 10, {"position_m": [1.0, None, 3.0]})
    fresh = state.snapshot(11, "/uav_1", battery=False, global_position=False)
    assert fresh["connection"] == "connected"
    assert fresh["vehicle_namespace"] == "/uav_1"
    assert set(fresh["streams"]) == {"status", "odometry"}
    assert fresh["streams"]["odometry"] == {
        "state": "fresh", "age_s": 1, "source_timestamp_us": 200,
        "data": {"position_m": [1.0, None, 3.0]},
    }
    stale = state.snapshot(13)
    assert stale["streams"]["status"] == {
        "state": "stale", "age_s": 3, "source_timestamp_us": 100, "data": None,
    }
    assert json.loads(json.dumps(stale, allow_nan=False))["schema_version"] == 1


def test_normalized_data_is_copied_on_update_and_snapshot():
    state = TelemetryState()
    data = {"vector": [1.0, 2.0]}
    state.update("odometry", {}, 1, 10, data)
    data["vector"][0] = 99.0
    snapshot = state.snapshot(10)
    assert snapshot["streams"]["odometry"]["data"]["vector"] == [1.0, 2.0]
    snapshot["streams"]["odometry"]["data"]["vector"][1] = 88.0
    assert state.samples["odometry"].data["vector"] == [1.0, 2.0]


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
    state.update("status", {"arming": "disarmed"}, 100, 10, {"arming_state": 1})
    state.update("status", {"arming": "armed"}, 100, 13, {"arming_state": 2})
    assert not state.fresh("status", 13)
    state.update("status", {"arming": "disarmed"}, 1, 14, {"arming_state": 1})
    assert state.fresh("status", 14)
    assert state.field("status", "arming", 14) == "disarmed"
    assert state.snapshot(14)["streams"]["status"]["data"] == {"arming_state": 1}


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
