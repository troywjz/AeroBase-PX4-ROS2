#!/usr/bin/env python3
"""Fetch fixed source revisions without resetting an existing checkout."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def run(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Could not inspect an existing source checkout; no files were changed.") from exc


NETWORK_FAILURE = re.compile(r"(timed? out|timeout|could not resolve|failed to connect|connection reset|network is unreachable|unable to access|ssl|tls|proxy)", re.I)


def git_operation(args: list[str], *, network: bool, proxy: str | None = None) -> None:
    """Run one Git operation, optionally retrying a detected network failure."""
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return
    if network and proxy and NETWORK_FAILURE.search(result.stdout + "\n" + result.stderr):
        retry = [args[0], "-c", f"http.proxy={proxy}", *args[1:]]
        retry_result = subprocess.run(retry, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if retry_result.returncode == 0:
            return
    raise SystemExit("Git source operation failed. Check network access and the source checkout; detailed output is suppressed to protect credentials and local paths.")


def reject_partial_clone(destination: Path) -> None:
    promisor = subprocess.run(["git", "-C", str(destination), "config", "--get", "remote.origin.promisor"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    partial = subprocess.run(["git", "-C", str(destination), "config", "--get", "extensions.partialClone"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if promisor.returncode == 0 and promisor.stdout.strip() == "true" or partial.returncode == 0 and partial.stdout.strip():
        raise SystemExit(f"Partial clone is unsupported for {destination.name}; it was left unchanged. Fetch a complete checkout manually.")


def fetch(entry: dict, destination: Path) -> None:
    proxy = os.environ.get("AEROBASE_GIT_PROXY") or None
    newly_cloned = not destination.exists()
    if newly_cloned:
        clone = ["git", "clone", "--depth", "1", "--branch", entry["ref"], entry["url"], str(destination)]
        git_operation(clone, network=True, proxy=proxy)
    reject_partial_clone(destination)
    current = run("git", "-C", str(destination), "rev-parse", "HEAD")
    if current != entry["commit"]:
        if not newly_cloned:
            raise SystemExit(f"Existing checkout does not match the locked commit {entry['commit']}; it was left unchanged.")
        git_operation(["git", "-C", str(destination), "fetch", "origin", entry["commit"]], network=True, proxy=proxy)
        git_operation(["git", "-C", str(destination), "checkout", "--detach", entry["commit"]], network=False)
    actual = run("git", "-C", str(destination), "rev-parse", "HEAD")
    if actual != entry["commit"] or run("git", "-C", str(destination), "status", "--porcelain"):
        raise SystemExit(f"Existing checkout must be clean and at {entry['commit']}; it was left unchanged.")
    print(f"Verified {destination.name}: {actual}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path.home() / "aerobase-runtime")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    lock = json.loads((repo / "config/stack.lock.json").read_text(encoding="utf-8"))
    args.runtime.mkdir(parents=True, exist_ok=True)
    fetch(lock["px4"], args.runtime / "PX4-Autopilot")
    git_operation(["git", "-C", str(args.runtime / "PX4-Autopilot"), "submodule", "update", "--init", "--recursive", "--depth", "1"], network=True, proxy=os.environ.get("AEROBASE_GIT_PROXY") or None)
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
