#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
[[ -r /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy is missing; install documented system dependencies first.' >&2; exit 1; }
[[ -x "$runtime/agent-install/bin/MicroXRCEAgent" ]] || { echo 'Micro XRCE-DDS Agent is not built; run scripts/build_runtime.sh first.' >&2; exit 1; }
[[ -d "$runtime/agent-install/lib" ]] || { echo 'Agent runtime libraries are missing; run scripts/build_runtime.sh first.' >&2; exit 1; }
source /opt/ros/jazzy/setup.bash
export LD_LIBRARY_PATH="$runtime/agent-install/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$runtime/agent-install/bin/MicroXRCEAgent" udp4 -p "${AEROBASE_XRCE_PORT:-8888}" "$@"
