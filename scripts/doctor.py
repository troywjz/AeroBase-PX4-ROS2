#!/usr/bin/env python3
"""Read-only checks for an AeroBase PX4/ROS 2 runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _git(*args: str, cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _os_release(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _source_check(name: str, checkout: Path, commit: str) -> list[dict[str, str]]:
    if not checkout.is_dir():
        return [_check(f"source.{name}", "warn", "Source checkout is missing; run scripts/build_runtime.sh to fetch and build the locked sources.")]
    actual = _git("-C", str(checkout), "rev-parse", "HEAD")
    if actual is None:
        return [_check(f"source.{name}", "fail", "Directory exists but is not a readable Git checkout.")]
    partial = _git("-C", str(checkout), "config", "--get", "remote.origin.promisor") == "true" or _git("-C", str(checkout), "config", "--get", "extensions.partialClone") is not None
    if partial:
        return [_check(f"source.{name}", "fail", "Partial clone detected; fetch a complete checkout manually. Doctor will not alter it.")]
    if actual != commit:
        return [_check(f"source.{name}", "fail", "Checkout commit does not match the repository lock; review it manually before rebuilding.")]
    dirty = _git("-C", str(checkout), "status", "--porcelain")
    if dirty is None:
        return [_check(f"source.{name}", "fail", "Could not inspect checkout status.")]
    if dirty:
        return [_check(f"source.{name}", "warn", "Tracked or non-ignored source changes are present; review before rebuilding. Ignored build and log files are excluded by Git status.")]
    return [_check(f"source.{name}", "pass", "Clean checkout matches the locked commit.")]


def diagnose(repo: Path, runtime: Path, env: dict[str, str] | None = None,
             release_file: Path = Path("/etc/os-release"),
             ros_setup: Path = Path("/opt/ros/jazzy/setup.bash"),
             system: str | None = None, machine: str | None = None) -> dict:
    env = os.environ if env is None else env
    system = platform.system() if system is None else system
    machine = platform.machine().lower() if machine is None else machine.lower()
    release = _os_release(release_file)
    checks: list[dict[str, str]] = []

    if system != "Linux":
        checks.append(_check("platform", "fail", "Target platform is Ubuntu 24.04 on Linux."))
    elif release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04":
        checks.append(_check("platform", "pass", "Ubuntu 24.04 detected."))
    else:
        checks.append(_check("platform", "fail", "Target platform is Ubuntu 24.04; this environment does not match."))
    if machine in ("x86_64", "amd64"):
        checks.append(_check("architecture", "pass", "amd64 is the documented target architecture."))
    elif machine in ("aarch64", "arm64"):
        checks.append(_check("architecture", "warn", "ARM architecture is not yet accepted for this deployment baseline."))
    else:
        checks.append(_check("architecture", "fail", "Architecture is outside the documented target matrix."))

    if env.get("ROS_DISTRO") == "jazzy":
        checks.append(_check("ros.environment", "pass", "ROS_DISTRO is jazzy in this environment."))
    else:
        checks.append(_check("ros.environment", "warn", "ROS_DISTRO is not jazzy; source /opt/ros/jazzy/setup.bash in this shell."))
    checks.append(_check("ros.installation", "pass" if ros_setup.is_file() else "warn",
                         "ROS 2 Jazzy setup file is present." if ros_setup.is_file() else "ROS 2 Jazzy setup file is missing; install dependencies before building."))

    required_commands = ("git", "python3", "cmake", "make", "colcon", "ros2", "gz")
    for command in required_commands:
        checks.append(_check(f"command.{command}", "pass" if shutil.which(command) else "warn",
                             "Available on PATH." if shutil.which(command) else f"Missing {command}; install the documented system dependencies."))

    lock_path = repo / "config" / "stack.lock.json"
    try:
        lock_data = lock_path.read_bytes()
        lock = json.loads(lock_data)
        if not isinstance(lock, dict):
            raise ValueError
        for key in ("px4", "px4_msgs", "agent", "agent_logger"):
            entry = lock.get(key)
            if not isinstance(entry, dict) or not isinstance(entry.get("commit"), str) or not entry["commit"]:
                raise ValueError
        digest = hashlib.sha256(lock_data).hexdigest()
        checks.append(_check("source.lock", "pass", f"stack.lock.json is readable (SHA-256 {digest})."))
    except OSError:
        lock = None
        checks.append(_check("source.lock", "fail", "Cannot read config/stack.lock.json."))
    except (TypeError, ValueError):
        lock = None
        checks.append(_check("source.lock", "fail", "config/stack.lock.json is malformed or missing required source commit fields."))

    if lock:
        sources = (
            ("px4", runtime / "PX4-Autopilot", lock["px4"]["commit"]),
            ("px4_msgs", runtime / "ros2_ws" / "src" / "px4_msgs", lock["px4_msgs"]["commit"]),
            ("agent", runtime / "Micro-XRCE-DDS-Agent", lock["agent"]["commit"]),
            ("spdlog", runtime / "spdlog", lock["agent_logger"]["commit"]),
        )
        for source in sources:
            checks.extend(_source_check(*source))

    required_files = (
        ("runtime.px4", runtime / "PX4-Autopilot" / "build" / "px4_sitl_default" / "bin" / "px4", "PX4 SITL executable", True),
        ("runtime.agent", runtime / "agent-install" / "bin" / "MicroXRCEAgent", "Micro XRCE-DDS Agent executable", True),
        ("runtime.agent_libraries", runtime / "agent-install" / "lib", "Agent runtime library directory", False),
        ("runtime.ros_install", runtime / "ros2_ws" / "install" / "setup.bash", "ROS workspace install setup", False),
        ("runtime.px4_venv", runtime / "px4-venv" / "bin" / "python", "PX4 Python virtual environment", True),
    )
    for key, path, label, executable in required_files:
        exists = path.exists() and (not executable or path.is_file() and os.access(path, os.X_OK))
        checks.append(_check(key, "pass" if exists else "warn",
                             f"{label} is present and executable." if exists and executable else f"{label} is present." if exists else f"{label} is missing or not executable; run scripts/build_runtime.sh after dependency installation."))

    expected_package = repo / "ros2_ws" / "src" / "aerobase_monitor"
    package_link = runtime / "ros2_ws" / "src" / "aerobase_monitor"
    if not package_link.exists() and not package_link.is_symlink():
        checks.append(_check("runtime.package_link", "warn", "Project package link is missing; fetch sources with scripts/build_runtime.sh, then build and source the workspace."))
    else:
        try:
            matches = package_link.resolve(strict=True) == expected_package.resolve(strict=True)
        except OSError:
            matches = False
        if matches and package_link.is_symlink():
            checks.append(_check("runtime.package_link", "pass", "Project package link resolves to the current repository package."))
        else:
            checks.append(_check("runtime.package_link", "fail", "Project package link points elsewhere or is not a symlink to the current package. Keep the existing target intact; use a new runtime directory or perform an explicit manual migration after reviewing its contents."))

    failures = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    overall = "fail" if failures else "warn" if warnings else "pass"
    host_architecture = "amd64" if machine in ("x86_64", "amd64") else "arm64" if machine in ("aarch64", "arm64") else machine
    return {"schema_version": 1, "target": {"platform": "Ubuntu 24.04", "ros_distro": "jazzy", "architecture": "amd64"},
            "host_architecture": host_architecture,
            "scope": "Environment and runtime file diagnostics only; this is not a flight-health, hardware-acceptance, or flight-safety assessment.",
            "overall": overall, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    runtime_default = Path(os.environ.get("AEROBASE_RUNTIME", str(Path.home() / "aerobase-runtime")))
    parser.add_argument("--runtime", type=Path, default=runtime_default)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if any check is a warning or failure.")
    args = parser.parse_args()
    report = diagnose(args.repo, args.runtime)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"AeroBase runtime doctor: {report['overall'].upper()}")
        for check in report["checks"]:
            print(f"{check['status'].upper():4} {check['name']}: {check['detail']}")
        print(report["scope"])
    if args.strict:
        return 1 if report["overall"] != "pass" else 0
    return 1 if report["overall"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
