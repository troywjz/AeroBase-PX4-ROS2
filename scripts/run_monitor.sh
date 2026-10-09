#!/usr/bin/env bash
set -eo pipefail
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
source /opt/ros/jazzy/setup.bash
source "$runtime/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
exec ros2 run aerobase_monitor vehicle_monitor "$@"
