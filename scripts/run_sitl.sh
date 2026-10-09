#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
export PATH="$runtime/px4-venv/bin:$PATH"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export PX4_UXRCE_DDS_PORT=${AEROBASE_XRCE_PORT:-8888}
cd "$runtime/PX4-Autopilot"
exec make -j"${AEROBASE_BUILD_JOBS:-4}" px4_sitl gz_x500
