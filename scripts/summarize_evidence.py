#!/usr/bin/env python3
"""Create a public, allow-listed summary from a SITL verification run."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


MAX_RESULT_BYTES = 1_000_000
MAX_VERSIONS_BYTES = 64_000
MAX_TEXT_LENGTH = 100
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
UBUNTU_RE = re.compile(r"^Ubuntu 24\.04(?:\.\d+)? LTS$")
PYTHON_RE = re.compile(r"^Python \d+\.\d+\.\d+$")
GAZEBO_RE = re.compile(r"^\d+\.\d+\.\d+$")
PACKAGE_VERSION_RE = re.compile(r"^\d[A-Za-z0-9.+:~_-]{0,99}$")

CHECK_NAMES = frozenset(
    {
        "required_streams_connected",
        "gazebo_x500_model",
        "no_px4_command_interfaces",
        "battery_received",
        "global_position_received",
        "agent_stop_marks_stale",
        "agent_restart_recovers",
        "remained_disarmed",
        "strict_json_stdout",
        "subscriber_started_first",
    }
)
COMMIT_FIELDS = {
    "px4_commit": "px4",
    "px4_msgs_commit": "px4_msgs",
    "agent_commit": "micro_xrce_dds_agent",
    "agent_logger_commit": "agent_logger",
}
PACKAGE_NAMES = frozenset(
    {
        "libgz-sim8",
        "libopencv-dev",
        "ros-jazzy-cyclonedds",
        "ros-jazzy-fastcdr",
        "ros-jazzy-fastrtps",
        "ros-jazzy-rclpy",
        "ros-jazzy-rmw-cyclonedds-cpp",
        "ros-jazzy-rmw-fastrtps-cpp",
        "ros-jazzy-ros-base",
        "ros2-apt-source",
    }
)


class SummaryInputError(ValueError):
    """An input cannot be represented by the public summary schema."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def _load_object(path: Path, limit: int, category: str) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise SummaryInputError(category)
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except SummaryInputError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise SummaryInputError(category) from None
    if not isinstance(value, dict):
        raise SummaryInputError(category)
    return value


def _utc_timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise SummaryInputError("invalid_result")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SummaryInputError("invalid_result") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise SummaryInputError("invalid_result")
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_result(path: Path) -> dict[str, Any]:
    source = _load_object(path, MAX_RESULT_BYTES, "invalid_result")
    passed = source.get("passed")
    checks_source = source.get("checks")
    if not isinstance(passed, bool) or not isinstance(checks_source, dict):
        raise SummaryInputError("invalid_result")

    checks: dict[str, bool] = {}
    for name, value in checks_source.items():
        if not isinstance(name, str) or len(name) > 80:
            raise SummaryInputError("invalid_result")
        if name in CHECK_NAMES:
            if not isinstance(value, bool):
                raise SummaryInputError("invalid_result")
            checks[name] = value

    if passed and (not (CHECK_NAMES - {"strict_json_stdout", "subscriber_started_first"}).issubset(checks) or not all(checks.values())):
        raise SummaryInputError("invalid_result")

    result: dict[str, Any] = {
        "passed": passed,
        "checks": checks,
        "started_utc": _utc_timestamp(source.get("started_utc")),
        "finished_utc": _utc_timestamp(source.get("finished_utc")),
    }
    if datetime.fromisoformat(result["finished_utc"].replace("Z", "+00:00")) < datetime.fromisoformat(
        result["started_utc"].replace("Z", "+00:00")
    ):
        raise SummaryInputError("invalid_result")
    if not passed:
        result["failure_category"] = "verification_failed"
    return result


def _clean_version(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise SummaryInputError("invalid_versions")
    value = value.strip()
    pattern = {"ubuntu": UBUNTU_RE, "python": PYTHON_RE, "gazebo": GAZEBO_RE}[field]
    if not pattern.fullmatch(value):
        raise SummaryInputError("invalid_versions")
    return value


def _clean_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SummaryInputError("invalid_versions")
    output: dict[str, Any] = {}
    for key, setting in value.items():
        if not isinstance(key, str) or len(key) > 80:
            raise SummaryInputError("invalid_versions")
        if key in {"headless", "monitor_first"}:
            if not isinstance(setting, bool):
                raise SummaryInputError("invalid_versions")
            output[key] = setting
        elif key == "model":
            if not isinstance(setting, str) or setting != "x500":
                raise SummaryInputError("invalid_versions")
            output[key] = setting
        elif key == "monitor_output":
            if not isinstance(setting, str) or setting not in {"text", "json"}:
                raise SummaryInputError("invalid_versions")
            output[key] = setting
        elif key == "ros_rmw":
            if not isinstance(setting, str) or setting not in {
                "rmw_cyclonedds_cpp",
                "rmw_fastrtps_cpp",
            }:
                raise SummaryInputError("invalid_versions")
            output[key] = setting
        elif key in {
            "stale_timeout_s",
            "report_interval_s",
            "timeout_s",
            "timeout",
        }:
            if isinstance(setting, bool) or not isinstance(setting, (int, float)):
                raise SummaryInputError("invalid_versions")
            if not 0 < setting <= 3600:
                raise SummaryInputError("invalid_versions")
            if isinstance(setting, float) and not math.isfinite(setting):
                raise SummaryInputError("invalid_versions")
            output[key] = setting
    return output


def _clean_system_packages(value: Any) -> dict[str, str]:
    if not isinstance(value, str) or len(value) > 16_000:
        raise SummaryInputError("invalid_versions")
    packages: dict[str, str] = {}
    for line in value.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name, version = parts
        if name.endswith(":amd64"):
            name = name[:-len(":amd64")]
        if name in PACKAGE_NAMES:
            if not PACKAGE_VERSION_RE.fullmatch(version):
                raise SummaryInputError("invalid_versions")
            packages[name] = version
    return dict(sorted(packages.items()))


def _read_versions(path: Path) -> dict[str, Any]:
    source = _load_object(path, MAX_VERSIONS_BYTES, "invalid_versions")
    software: dict[str, str] = {}
    for field in ("ubuntu", "python", "gazebo"):
        if field in source:
            software[field] = _clean_version(source[field], field)

    commits: dict[str, str] = {}
    for field, name in COMMIT_FIELDS.items():
        if field in source:
            value = source[field]
            if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
                raise SummaryInputError("invalid_versions")
            commits[name] = value.lower()

    output: dict[str, Any] = {
        "software": software,
        "source_commits": commits,
        "settings": _clean_settings(source.get("settings", {})),
    }
    if "system_packages" in source:
        output["software_packages"] = _clean_system_packages(source["system_packages"])
    return output


def create_summary(result_path: Path, versions_path: Path | None = None) -> dict[str, Any]:
    """Return only public, validated fields from a SITL result and version record."""
    result = _read_result(result_path)
    if versions_path is None:
        candidate = result_path.with_name("versions.json")
        if candidate.is_file():
            versions_path = candidate

    if versions_path is None:
        if result["passed"]:
            raise SummaryInputError("versions_required_for_success")
        result.update({"software": {}, "source_commits": {}, "settings": {}})
        return result

    try:
        result.update(_read_versions(versions_path))
        if result["passed"]:
            if set(result["source_commits"]) != set(COMMIT_FIELDS.values()) or set(result["software"]) != {"ubuntu", "python", "gazebo"}:
                raise SummaryInputError("incomplete_versions")
            if result["settings"].get("monitor_output") == "json" and not result["checks"].get("strict_json_stdout"):
                raise SummaryInputError("missing_json_check")
            if result["settings"].get("monitor_first") and not result["checks"].get("subscriber_started_first"):
                raise SummaryInputError("missing_subscriber_check")
    except SummaryInputError:
        if result["passed"]:
            raise
        # Failed runs can still produce a useful, non-sensitive summary when
        # their optional version artifact is missing or malformed.
        result.update({"software": {}, "source_commits": {}, "settings": {}})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json", type=Path, help="verify_sitl.py result.json")
    parser.add_argument("--versions", type=Path, help="optional verify_sitl.py versions.json")
    parser.add_argument("--output", type=Path, help="write the public summary to this file")
    args = parser.parse_args(argv)

    try:
        summary = create_summary(args.result_json, args.versions)
    except SummaryInputError as exc:
        print(json.dumps({"error_category": str(exc)}), file=sys.stderr)
        return 2

    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError:
            print(json.dumps({"error_category": "output_unavailable"}), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
