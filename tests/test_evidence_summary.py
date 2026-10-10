import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_evidence import SummaryInputError, create_summary


STARTED = "2026-10-10T10:00:00Z"
FINISHED = "2026-10-10T10:01:00+00:00"
GOOD_COMMIT = "0123456789abcdef0123456789abcdef01234567"


class EvidenceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.result_path = self.directory / "result.json"
        self.versions_path = self.directory / "versions.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def result(self, **overrides):
        value = {
            "passed": True,
            "checks": {
                "required_streams_connected": True,
                "gazebo_x500_model": True,
                "no_px4_command_interfaces": True,
                "battery_received": True,
                "global_position_received": True,
                "agent_stop_marks_stale": True,
                "agent_restart_recovers": True,
                "remained_disarmed": True,
                "strict_json_stdout": True,
                "subscriber_started_first": True,
                "unexpected_check": "PRIVATE-CHECK-VALUE",
            },
            "started_utc": STARTED,
            "finished_utc": FINISHED,
            "commands": {"secret": "PRIVATE-COMMAND-PATH"},
            "error": "PRIVATE-ERROR-TEXT",
            "host": "PRIVATE-HOSTNAME",
        }
        value.update(overrides)
        return value

    def versions(self, **overrides):
        value = {
            "ubuntu": "Ubuntu 24.04.4 LTS",
            "python": "Python 3.12.3",
            "gazebo": "8.15.0",
            "px4_commit": GOOD_COMMIT,
            "px4_msgs_commit": GOOD_COMMIT,
            "agent_commit": GOOD_COMMIT,
            "agent_logger_commit": GOOD_COMMIT,
            "kernel": "PRIVATE-KERNEL-ID",
            "hostname": "PRIVATE-HOSTNAME",
            "device_id": "PRIVATE-DEVICE-ID",
            "proxy": "http://PRIVATE-PROXY:7890",
            "settings": {
                "headless": True,
                "model": "x500",
                "monitor_first": True,
                "monitor_output": "json",
                "ros_rmw": "rmw_cyclonedds_cpp",
                "stale_timeout_s": 3.0,
                "ros_domain_id": "PRIVATE-DOMAIN-SETTING",
            },
            "system_packages": (
                "libgz-sim8:amd64 8.15.0-1~noble\n"
                "ros-jazzy-ros-base 0.11.0-1noble\n"
                "private-proxy PRIVATE-PACKAGE-SECRET"
            ),
        }
        value.update(overrides)
        return value

    def test_only_allow_listed_public_fields_survive(self):
        self.write_json(self.result_path, self.result())
        self.write_json(self.versions_path, self.versions())

        summary = create_summary(self.result_path, self.versions_path)
        serialized = json.dumps(summary)

        self.assertTrue(summary["passed"])
        self.assertEqual(summary["checks"]["required_streams_connected"], True)
        self.assertEqual(summary["source_commits"]["px4"], GOOD_COMMIT)
        self.assertEqual(summary["settings"]["monitor_output"], "json")
        self.assertEqual(summary["software_packages"]["libgz-sim8"], "8.15.0-1~noble")
        for secret in (
            "PRIVATE-COMMAND-PATH",
            "PRIVATE-ERROR-TEXT",
            "PRIVATE-HOSTNAME",
            "PRIVATE-KERNEL-ID",
            "PRIVATE-DEVICE-ID",
            "PRIVATE-PROXY",
            "PRIVATE-DOMAIN-SETTING",
            "PRIVATE-PACKAGE-SECRET",
            "PRIVATE-CHECK-VALUE",
        ):
            self.assertNotIn(secret, serialized)

    def test_failed_result_without_versions_emits_generic_failure_summary(self):
        self.write_json(
            self.result_path,
            self.result(passed=False, checks={"required_streams_connected": False}),
        )

        summary = create_summary(self.result_path)

        self.assertFalse(summary["passed"])
        self.assertEqual(summary["failure_category"], "verification_failed")
        self.assertEqual(summary["source_commits"], {})
        self.assertNotIn("error", summary)

    def test_success_without_versions_is_rejected(self):
        self.write_json(self.result_path, self.result())
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path)

    def test_bad_checks_type_is_rejected(self):
        self.write_json(self.result_path, self.result(checks=[True]))
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)

    def test_non_boolean_whitelisted_check_is_rejected(self):
        self.write_json(
            self.result_path,
            self.result(checks={"required_streams_connected": "true"}),
        )
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)

    def test_malformed_commit_is_rejected(self):
        self.write_json(self.result_path, self.result())
        self.write_json(self.versions_path, self.versions(px4_commit="/private/path"))
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)

    def test_invalid_setting_type_is_rejected(self):
        self.write_json(self.result_path, self.result())
        self.write_json(
            self.versions_path,
            self.versions(settings={"headless": "yes"}),
        )
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)

    def test_incomplete_success_evidence_is_rejected(self):
        self.write_json(self.result_path, self.result(checks={"required_streams_connected": True}))
        self.write_json(self.versions_path, self.versions())
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)
        self.write_json(self.result_path, self.result())
        self.write_json(self.versions_path, {})
        with self.assertRaises(SummaryInputError):
            create_summary(self.result_path, self.versions_path)


if __name__ == "__main__":
    unittest.main()
