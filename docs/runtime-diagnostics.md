# Runtime diagnostics

Run the read-only doctor from the repository root after installing system dependencies, fetching sources, or building the runtime. For strict readiness, first source ROS 2 Jazzy and the built workspace in the same shell:

```bash
source /opt/ros/jazzy/setup.bash
source "${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}/ros2_ws/install/setup.bash"
bash scripts/doctor.sh --strict
bash scripts/doctor.sh --json --strict
```

The runtime defaults to `~/aerobase-runtime`; set `AEROBASE_RUNTIME` if the runtime is elsewhere. Paths containing spaces are supported. The doctor checks the host target, the current shell's ROS environment, required commands, locked source commits, expected build products, and the workspace link to this repository's `aerobase_monitor` package. It does not fetch, build, install, repair, reset, remove, or stop anything.

The JSON output uses schema version 1 and contains component names and diagnostic details rather than host absolute paths. Review reports before publishing them. `pass`, `warn`, and `fail` describe local environment readiness only. By default, exit status is `0` for pass or warn and `1` when any check fails. `--strict` returns nonzero unless every check passes, so missing required commands, ROS setup, or build products fail readiness automation while ordinary diagnosis remains advisory. The doctor only inspects local state; it does not fetch, build, install, repair, reset, remove, or stop anything.

When the runtime is new, the report explains which setup stage is missing:

1. Install system dependencies with `scripts/install_ubuntu_deps.sh` on Ubuntu 24.04.
2. Fetch locked sources and build with `scripts/build_runtime.sh`.
3. Source `/opt/ros/jazzy/setup.bash` and the runtime's `ros2_ws/install/setup.bash` in the shell used for ROS commands.

If the package link resolves to a different checkout, the doctor preserves it and gives a migration hint. Use a new runtime directory or review and migrate the existing runtime explicitly; the doctor never replaces the link.

## Target support

| Platform | Architecture | Diagnostic interpretation |
| --- | --- | --- |
| Ubuntu 24.04 | amd64 | Documented target for the deployment baseline. A passing doctor report does not constitute a deployment integration test. |
| Ubuntu 24.04 | ARM64 | Reported as not yet accepted; a successful file check must not be read as deployment acceptance. |
| Other operating systems or Ubuntu releases | Any | Outside the current target matrix. |

Headless SITL integration passed on a fresh GitHub-hosted Ubuntu 24.04.5 amd64 runner and WSL2 Ubuntu 24.04.4; see the [release evidence](evidence/2026-10-10-v0.1.md). The doctor reports environment and runtime files only; the separate SITL verifier checks the live data path and reports startup failures. Neither result assesses physical hardware, flight readiness or flight safety.
