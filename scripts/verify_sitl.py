#!/usr/bin/env python3
"""Observe a real SITL chain; stop/restart only the agent started by this run."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


def output(command: list[str], timeout: int = 20) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=timeout)


def stop(process: subprocess.Popen) -> None:
    if getattr(process, "aerobase_stopped", False):
        return
    process.aerobase_stopped = True
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        pass
    # Terminate remaining descendants in this harness's private process group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()


def json_reports(content: str) -> list[dict]:
    """Reject non-JSON stdout and nonstandard numeric constants."""
    def reject_constant(value):
        raise ValueError(f"Nonstandard JSON constant: {value}")
    reports = []
    for line in content.splitlines():
        if not line.strip():
            continue
        report = json.loads(line, parse_constant=reject_constant)
        if not isinstance(report, dict) or report.get("schema_version") != 1:
            raise ValueError("Expected a schema v1 JSON report")
        streams = report.get("streams", {})
        for name in ("status", "odometry"):
            if name not in streams:
                raise ValueError("Required stream missing from JSON report")
        for stream in streams.values():
            if stream["state"] != "fresh" and stream["data"] is not None:
                raise ValueError("Non-fresh stream exposed cached data")
        reports.append(report)
    return reports


def observed_connection(content: str, state: str, output_format: str) -> bool:
    if output_format == "text":
        return f"Vehicle: {state}" in content
    return any(report["connection"] == state for report in json_reports(content))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, default=Path.home() / "aerobase-runtime")
    parser.add_argument("--monitor-first", action="store_true", help="Exercise a subscriber that starts before PX4")
    parser.add_argument("--monitor-output", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new evidence directory; previous logs will not be overwritten")
    if subprocess.run(["pgrep", "-x", "px4"], stdout=subprocess.DEVNULL).returncode == 0:
        raise SystemExit("An existing PX4 process is running; close it before this isolated check")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", 8888))
    args.output.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(AEROBASE_RUNTIME=str(args.runtime), ROS_DOMAIN_ID="0", AEROBASE_XRCE_PORT="8888", HEADLESS="1", RMW_IMPLEMENTATION=os.environ.get("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"), PYTHONUNBUFFERED="1")
    # Only local domain 0 topics are observed; this check sends no PX4 commands.
    processes = []
    files = []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = {"started_utc": started, "checks": {}, "commands": {}}

    def launch(script: str, logfile: str, extra: list[str] | None = None):
        command = ["bash", str(repo / "scripts" / script), *(extra or [])]
        handle = (args.output / logfile).open("w")
        files.append(handle)
        # Keep stdin open but never send commands: PX4's shell otherwise spins
        # on inherited EOF when a check is launched from a noninteractive host.
        error_handle = subprocess.STDOUT
        if script == "run_monitor.sh":
            error_handle = (args.output / "monitor-stderr.log").open("w")
            files.append(error_handle)
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=handle, stderr=error_handle, env=env, start_new_session=True)
        processes.append(process)
        results["commands"][logfile] = command
        return process

    def wait_for(state: str, offset: int = 0, timeout: int = 90) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            content = (args.output / "monitor.log").read_text(errors="replace")[offset:]
            # Read only complete records while the monitor is writing.
            content = content[:content.rfind("\n") + 1]
            if observed_connection(content, state, args.monitor_output):
                return content
            if monitor.poll() is not None or sitl.poll() is not None:
                raise RuntimeError("Monitor or SITL exited; inspect logs")
            time.sleep(0.2)
        raise TimeoutError(f"Did not observe {state!r}; inspect logs")

    def capture(name: str, command: list[str]) -> str:
        content = output(command)
        (args.output / name).write_text(content)
        return content

    try:
        capture("interfaces.log", ["python3", str(repo / "scripts/check_interfaces.py"), "--runtime", str(args.runtime)])
        agent = launch("run_agent.sh", "agent.log")
        monitor_args = ["--ros-args", "-p", f"output_format:={args.monitor_output}"]
        if args.monitor_first:
            monitor = launch("run_monitor.sh", "monitor.log", monitor_args)
        sitl = launch("run_sitl.sh", "sitl.log")
        # The supported startup sequence brings the DDS writers up before
        # creating the ROS subscriber. Observe readiness rather than sleeping.
        deadline = time.monotonic() + 90
        while True:
            startup_log = (args.output / "sitl.log").read_text(errors="replace")
            required = ("created rt/fmu/out/vehicle_status_v1 data writer", "created rt/fmu/out/vehicle_odometry data writer")
            if all(marker in startup_log for marker in required):
                break
            if agent.poll() is not None or sitl.poll() is not None:
                raise RuntimeError("Agent or SITL exited before DDS readiness")
            if time.monotonic() >= deadline:
                raise TimeoutError("PX4 DDS writers did not become ready")
            time.sleep(0.2)
        if not args.monitor_first:
            monitor = launch("run_monitor.sh", "monitor.log", monitor_args)
        wait_for("connected")
        results["checks"]["required_streams_connected"] = True
        print("PASS: real PX4 status and odometry reached vehicle_monitor", flush=True)
        time.sleep(5)
        capture("topics.log", ["ros2", "topic", "list", "-t", "--no-daemon"])
        node_info = capture("node-info.log", ["ros2", "node", "info", "/vehicle_monitor", "--no-daemon"])
        capture("status-topic.log", ["ros2", "topic", "info", "/fmu/out/vehicle_status_v1", "--verbose", "--no-daemon"])
        capture("odometry-topic.log", ["ros2", "topic", "info", "/fmu/out/vehicle_odometry", "--verbose", "--no-daemon"])
        models = capture("gazebo-models.log", ["gz", "model", "--list"])
        if "x500" not in models.lower():
            raise RuntimeError("X500 not listed by Gazebo")
        results["checks"]["gazebo_x500_model"] = True
        print("PASS: Gazebo reports an X500 model", flush=True)
        if "/fmu/in/" in node_info or "/fmu/vehicle_command" in node_info:
            raise RuntimeError("Unexpected vehicle command interface on monitor")
        results["checks"]["no_px4_command_interfaces"] = True
        # Ensure these specific streams actually yielded data, not only discovery.
        report = (args.output / "monitor.log").read_text()
        if args.monitor_output == "json":
            reports = json_reports(report)
            for stream, key in (("battery", "battery_received"), ("global_position", "global_position_received")):
                results["checks"][key] = any(item["streams"][stream]["state"] == "fresh" and item["streams"][stream]["data"] is not None for item in reports)
            results["checks"]["strict_json_stdout"] = bool(reports)
        else:
            results["checks"]["battery_received"] = any(line.startswith("Battery:") and "unknown (no data)" not in line and "stale" not in line for line in report.splitlines())
            results["checks"]["global_position_received"] = any(line.startswith("Global position:") and "unknown (no data)" not in line and "stale" not in line for line in report.splitlines())
        if not results["checks"]["battery_received"] or not results["checks"]["global_position_received"]:
            raise RuntimeError("Optional telemetry did not arrive in this baseline")
        def armed(content):
            if args.monitor_output == "text":
                return "Arming: armed(2)" in content
            return any(item["streams"]["status"]["data"] is not None and item["streams"]["status"]["data"]["arming_state"] == 2 for item in json_reports(content))
        if armed(report):
            raise RuntimeError("Unexpected armed SITL state")
        offset = len(report)
        stop(agent)
        disconnected = wait_for("disconnected", offset, timeout=12)
        masked = (any(item["connection"] == "disconnected" and all(item["streams"][key]["state"] == "stale" and item["streams"][key]["data"] is None for key in ("status", "odometry")) for item in json_reports(disconnected)) if args.monitor_output == "json" else "Arming: stale" in disconnected and "Position: stale" in disconnected)
        if not masked:
            raise RuntimeError("Disconnected report did not mask stale data")
        results["checks"]["agent_stop_marks_stale"] = True
        print("PASS: agent stop caused disconnected/stale telemetry", flush=True)
        offset = len((args.output / "monitor.log").read_text())
        agent = launch("run_agent.sh", "agent-restart.log")
        wait_for("connected", offset, timeout=60)
        results["checks"]["agent_restart_recovers"] = True
        if armed((args.output / "monitor.log").read_text()):
            raise RuntimeError("Unexpected armed SITL state during recovery")
        results["checks"]["remained_disarmed"] = True
        print("PASS: agent restart restored live telemetry", flush=True)
        versions = {
            "ubuntu": output(["lsb_release", "-ds"]).strip(),
            "kernel": output(["uname", "-r"]).strip(),
            "python": output(["python3", "--version"]).strip(),
            "gazebo": output(["gz", "sim", "--versions"]).strip(),
            "px4_commit": output(["git", "-C", str(args.runtime / "PX4-Autopilot"), "rev-parse", "HEAD"]).strip(),
            "px4_msgs_commit": output(["git", "-C", str(args.runtime / "ros2_ws/src/px4_msgs"), "rev-parse", "HEAD"]).strip(),
            "agent_commit": output(["git", "-C", str(args.runtime / "Micro-XRCE-DDS-Agent"), "rev-parse", "HEAD"]).strip(),
            "agent_logger_commit": output(["git", "-C", str(args.runtime / "spdlog"), "rev-parse", "HEAD"]).strip(),
            "system_packages": output(["dpkg-query", "-W", "ros-jazzy-ros-base", "ros-jazzy-rclpy", "ros-jazzy-rmw-fastrtps-cpp", "ros-jazzy-rmw-cyclonedds-cpp", "ros-jazzy-cyclonedds", "ros-jazzy-fastrtps", "ros-jazzy-fastcdr", "libgz-sim8", "libopencv-dev", "ros2-apt-source"]).strip(),
            "settings": {"headless": True, "ros_domain_id": 0, "xrce_udp_port": 8888, "model": "x500", "stale_timeout_s": 3.0, "dds_builtin_transports": env.get("FASTDDS_BUILTIN_TRANSPORTS", "DEFAULT"), "ros_rmw": env["RMW_IMPLEMENTATION"], "monitor_first": args.monitor_first, "monitor_output": args.monitor_output},
        }
        (args.output / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")
        capture("px4-python-requirements.txt", [str(args.runtime / "px4-venv/bin/python"), "-m", "pip", "freeze"])
        results["passed"] = True
    except (Exception, KeyboardInterrupt) as exc:
        results["passed"] = False
        results["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for process in reversed(processes):
            stop(process)
        for handle in files:
            handle.close()
        results["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (args.output / "result.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
