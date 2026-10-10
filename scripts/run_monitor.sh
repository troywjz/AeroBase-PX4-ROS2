#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
[[ -r /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy is missing; install documented system dependencies first.' >&2; exit 1; }
[[ -r "$runtime/ros2_ws/install/setup.bash" ]] || { echo 'ROS workspace is not built; run scripts/build_runtime.sh first.' >&2; exit 1; }
source /opt/ros/jazzy/setup.bash
source "$runtime/ros2_ws/install/setup.bash"
command -v ros2 >/dev/null || { echo 'ros2 is unavailable after sourcing Jazzy; check the ROS installation.' >&2; exit 1; }
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
exec ros2 run aerobase_monitor vehicle_monitor "$@"
