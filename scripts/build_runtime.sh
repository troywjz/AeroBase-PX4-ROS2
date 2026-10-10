#!/usr/bin/env bash
set -eo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runtime=${AEROBASE_RUNTIME:-$HOME/aerobase-runtime}
jobs=${AEROBASE_BUILD_JOBS:-4}
if (( EUID == 0 )); then
    echo 'Build as an ordinary user, after installing system dependencies.' >&2
    exit 1
fi
for required_command in git python3 cmake make colcon; do
    command -v "$required_command" >/dev/null || { echo "Missing required command: $required_command. Install documented system dependencies first." >&2; exit 1; }
done
[[ -r /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy is missing; install documented system dependencies first.' >&2; exit 1; }
python3 "$repo_dir/scripts/fetch_sources.py" --runtime "$runtime"
python3 "$repo_dir/scripts/check_interfaces.py" --runtime "$runtime"
python3 -m venv "$runtime/px4-venv"
"$runtime/px4-venv/bin/python" -m pip install -r "$runtime/PX4-Autopilot/Tools/setup/requirements.txt"
PATH="$runtime/px4-venv/bin:$PATH" make -C "$runtime/PX4-Autopilot" -j"$jobs" px4_sitl_default
# Reuse Jazzy's DDS libraries rather than building another floating DDS branch.
source /opt/ros/jazzy/setup.bash
cmake -S "$runtime/spdlog" -B "$runtime/spdlog-build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$runtime/agent-install" \
    -DSPDLOG_BUILD_SHARED=ON -DSPDLOG_FMT_EXTERNAL=OFF -DSPDLOG_BUILD_EXAMPLE=OFF
cmake --build "$runtime/spdlog-build" --parallel "$jobs"
cmake --install "$runtime/spdlog-build"
cmake -S "$runtime/Micro-XRCE-DDS-Agent" -B "$runtime/agent-build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$runtime/agent-install" \
    -DUAGENT_SUPERBUILD=OFF -DUAGENT_P2P_PROFILE=OFF \
    -DUAGENT_USE_SYSTEM_FASTDDS=ON -DUAGENT_USE_SYSTEM_FASTCDR=ON \
    -DUAGENT_USE_SYSTEM_LOGGER=ON -Dspdlog_DIR="$runtime/agent-install/lib/cmake/spdlog"
cmake --build "$runtime/agent-build" --parallel "$jobs"
cmake --install "$runtime/agent-build"
# Use ROS's system Python, not the PX4 virtual environment.
cd "$runtime/ros2_ws"
CMAKE_BUILD_PARALLEL_LEVEL="$jobs" colcon build --symlink-install --parallel-workers "$jobs" --cmake-args -DBUILD_TESTING=OFF
echo "Built runtime at $runtime"
