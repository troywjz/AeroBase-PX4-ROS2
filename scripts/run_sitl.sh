#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
[[ -x "$runtime/PX4-Autopilot/build/px4_sitl_default/bin/px4" ]] || { echo 'PX4 SITL is not built; run scripts/build_runtime.sh first.' >&2; exit 1; }
[[ -x "$runtime/px4-venv/bin/python" ]] || { echo 'PX4 Python virtual environment is missing; run scripts/build_runtime.sh first.' >&2; exit 1; }
export PATH="$runtime/px4-venv/bin:$PATH"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export PX4_UXRCE_DDS_PORT=${AEROBASE_XRCE_PORT:-8888}
cd "$runtime/PX4-Autopilot"
exec make -j"${AEROBASE_BUILD_JOBS:-4}" px4_sitl gz_x500
