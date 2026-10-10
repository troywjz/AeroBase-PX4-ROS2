"""Acceptance parsing must reject invalid stdout and cached numeric data."""
import json

import pytest

from scripts.verify_sitl import json_reports, observed_connection


def report(state="fresh", data=None):
    return {"schema_version": 1, "connection": "connected", "streams": {
        "status": {"state": state, "data": data},
        "odometry": {"state": "fresh", "data": {"position_m": [0, 0, 0]}},
    }}


def test_strict_stdout_and_connection():
    content = json.dumps(report(data={"arming_state": 1})) + "\n"
    assert observed_connection(content, "connected", "json")
    assert not observed_connection(content, "disconnected", "json")
    with pytest.raises(ValueError):
        json_reports("[INFO] ROS log on stdout\n" + content)
    with pytest.raises(ValueError):
        json_reports(content.replace('[0, 0, 0]', '[NaN, 0, 0]'))


def test_stale_payload_is_masked_and_required_streams_exist():
    with pytest.raises(ValueError, match="cached"):
        json_reports(json.dumps(report("stale", {"arming_state": 1})))
    assert json_reports(json.dumps(report("stale")))[0]["streams"]["status"]["data"] is None
    invalid = report()
    del invalid["streams"]["odometry"]
    with pytest.raises(ValueError, match="Required stream"):
        json_reports(json.dumps(invalid))
