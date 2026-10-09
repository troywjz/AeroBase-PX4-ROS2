#!/usr/bin/env bash
set -eo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
source /opt/ros/jazzy/setup.bash
source "$runtime/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
exec python3 "$repo_dir/scripts/verify_sitl.py" --runtime "$runtime" "$@"
