#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
source /opt/ros/jazzy/setup.bash
export LD_LIBRARY_PATH="$runtime/agent-install/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$runtime/agent-install/bin/MicroXRCEAgent" udp4 -p "${AEROBASE_XRCE_PORT:-8888}" "$@"
