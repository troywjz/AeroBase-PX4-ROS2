"""Telemetry freshness and formatting, independent of ROS and PX4 bindings."""
from dataclasses import dataclass
import math
import re


def px4_topic(base: str, message_type: type, vehicle_namespace: str = "") -> str:
    """PX4 appends _vN only when MESSAGE_VERSION is nonzero."""
    namespace = vehicle_namespace.strip("/")
    if namespace and not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in namespace.split("/")):
        raise ValueError("vehicle_namespace must contain valid ROS namespace segments")
    version = int(getattr(message_type, "MESSAGE_VERSION", 0))
    suffix = f"_v{version}" if version else ""
    return f"/{namespace + '/' if namespace else ''}fmu/out/{base}{suffix}"


def enum_label(message_type: type, prefix: str, value: int) -> str:
    for name in dir(message_type):
        if name.startswith(prefix) and not name.endswith("_MAX") and getattr(message_type, name) == value:
            return f"{name[len(prefix):].lower()}({value})"
    return f"unknown({value})"


def number(value: float, precision: int = 2) -> str:
    return f"{value:.{precision}f}" if math.isfinite(value) else "unknown"


def vector(values) -> str:
    return "(" + ", ".join(number(float(value)) for value in values) + ")"


@dataclass(frozen=True)
class Sample:
    fields: dict[str, str]
    received_at: float
    source_timestamp: int


class TelemetryState:
    """connected means both mandatory streams advance within the timeout.

    Freshness uses the local monotonic receipt clock, not a subtraction between
    the PX4 simulation clock and the host clock. Replayed identical timestamps
    cannot keep a stopped stream fresh. A timestamp reset is accepted.
    """

    REQUIRED = ("status", "odometry")

    def __init__(self, stale_timeout_s: float = 3.0) -> None:
        if not math.isfinite(stale_timeout_s) or stale_timeout_s <= 0:
            raise ValueError("stale_timeout_s must be finite and positive")
        self.stale_timeout_s = stale_timeout_s
        self.samples: dict[str, Sample] = {}

    def update(self, stream: str, fields: dict[str, str], source_timestamp: int, now: float) -> None:
        previous = self.samples.get(stream)
        if source_timestamp <= 0 or (previous and previous.source_timestamp == source_timestamp):
            return
        self.samples[stream] = Sample(dict(fields), now, source_timestamp)

    def fresh(self, stream: str, now: float) -> bool:
        sample = self.samples.get(stream)
        return sample is not None and 0 <= now - sample.received_at < self.stale_timeout_s

    def connection(self, now: float) -> str:
        count = sum(self.fresh(stream, now) for stream in self.REQUIRED)
        if count == len(self.REQUIRED):
            return "connected"
        if count:
            return "degraded"
        return "disconnected" if any(stream in self.samples for stream in self.REQUIRED) else "waiting"

    def field(self, stream: str, name: str, now: float) -> str:
        sample = self.samples.get(stream)
        if sample is None:
            return "unknown (no data)"
        if not self.fresh(stream, now):
            return f"stale (age={max(0, now - sample.received_at):.1f}s)"
        return sample.fields.get(name, "unknown")

    def report(self, now: float, battery: bool = True, global_position: bool = True) -> str:
        rows = [
            f"Vehicle: {self.connection(now)}",
            f"Arming: {self.field('status', 'arming', now)}",
            f"Nav state: {self.field('status', 'nav_state', now)}",
            f"Failsafe: {self.field('status', 'failsafe', now)}",
            f"Position: {self.field('odometry', 'position', now)}",
            f"Velocity: {self.field('odometry', 'velocity', now)}",
        ]
        if battery:
            rows.append(f"Battery: {self.field('battery', 'battery', now)}")
        if global_position:
            rows.append(f"Global position: {self.field('global_position', 'global_position', now)}")
        return "\n".join(rows)
