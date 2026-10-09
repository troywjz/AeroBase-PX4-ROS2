#!/usr/bin/env python3
"""Fetch fixed source revisions without resetting an existing checkout."""
import argparse
import json
import subprocess
from pathlib import Path


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def fetch(entry: dict, destination: Path) -> None:
    if not destination.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", entry["ref"], entry["url"], str(destination)],
            check=True,
        )
        if run("git", "-C", str(destination), "rev-parse", "HEAD") != entry["commit"]:
            subprocess.run(["git", "-C", str(destination), "fetch", "origin", entry["commit"]], check=True)
            subprocess.run(["git", "-C", str(destination), "checkout", "--detach", entry["commit"]], check=True)
    actual = run("git", "-C", str(destination), "rev-parse", "HEAD")
    if actual != entry["commit"] or run("git", "-C", str(destination), "status", "--porcelain"):
        raise SystemExit(f"Existing checkout must be clean and at {entry['commit']}: {destination}")
    print(f"Verified {destination.name}: {actual}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path.home() / "aerobase-runtime")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    lock = json.loads((repo / "config/stack.lock.json").read_text(encoding="utf-8"))
    args.runtime.mkdir(parents=True, exist_ok=True)
    fetch(lock["px4"], args.runtime / "PX4-Autopilot")
    subprocess.run(["git", "-C", str(args.runtime / "PX4-Autopilot"), "submodule", "update", "--init", "--recursive", "--depth", "1"], check=True)
    workspace = args.runtime / "ros2_ws/src"
    workspace.mkdir(parents=True, exist_ok=True)
    fetch(lock["px4_msgs"], workspace / "px4_msgs")
    fetch(lock["agent"], args.runtime / "Micro-XRCE-DDS-Agent")
    fetch(lock["agent_logger"], args.runtime / "spdlog")
    package = workspace / "aerobase_monitor"
    source = repo / "ros2_ws/src/aerobase_monitor"
    if not package.exists() and not package.is_symlink():
        package.symlink_to(source, target_is_directory=True)
    if package.resolve() != source.resolve():
        raise SystemExit(f"Unexpected existing package: {package}")


if __name__ == "__main__":
    main()
