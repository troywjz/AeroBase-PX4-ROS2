#!/usr/bin/env python3
"""Require semantic equality for the four monitored PX4 message definitions."""
import argparse
from pathlib import Path

MESSAGES = ("VehicleStatus", "VehicleOdometry", "BatteryStatus", "VehicleGlobalPosition")


def fields(path: Path) -> list[str]:
    return [" ".join(code.split()) for line in path.read_text().splitlines() if (code := line.partition("#")[0].strip())]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path.home() / "aerobase-runtime")
    args = parser.parse_args()
    for name in MESSAGES:
        px4 = args.runtime / "PX4-Autopilot/msg"
        candidates = [px4 / f"{name}.msg", px4 / "versioned" / f"{name}.msg"]
        source = next((path for path in candidates if path.exists()), None)
        ros = args.runtime / "ros2_ws/src/px4_msgs/msg" / f"{name}.msg"
        if source is None or not ros.exists() or fields(source) != fields(ros):
            raise SystemExit(f"Message definition mismatch: {name}; do not run this pair")
        print(f"PASS {name}: PX4 and px4_msgs field definitions match")


if __name__ == "__main__":
    main()
