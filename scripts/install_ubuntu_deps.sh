#!/usr/bin/env bash
# System packages only; run builds as an ordinary user.
set -euo pipefail
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
    echo 'This baseline requires Ubuntu 24.04.' >&2
    exit 1
fi
priv=()
if (( EUID != 0 )); then priv=(sudo); fi
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ros_source_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ros_apt_source_version"])' "$repo_dir/config/stack.lock.json")
"${priv[@]}" apt-get update
"${priv[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg locales software-properties-common
"${priv[@]}" add-apt-repository -y universe
"${priv[@]}" locale-gen en_US.UTF-8
ros_source_deb=$(mktemp --suffix=.deb)
trap 'rm -f -- "$ros_source_deb"' EXIT
curl -fL --retry 3 "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_source_version}/ros2-apt-source_${ros_source_version}.noble_all.deb" -o "$ros_source_deb"
"${priv[@]}" dpkg -i "$ros_source_deb"
curl -fsSL --retry 3 https://packages.osrfoundation.org/gazebo.gpg | "${priv[@]}" tee /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg >/dev/null
printf 'deb [arch=%s signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable noble main\n' "$(dpkg --print-architecture)" | "${priv[@]}" tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
"${priv[@]}" apt-get update
"${priv[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ros-jazzy-ros-base ros-jazzy-rmw-fastrtps-cpp ros-jazzy-rmw-cyclonedds-cpp \
    python3-colcon-common-extensions python3-venv python3-pip python3-dev python3-pytest \
    build-essential cmake ninja-build git ccache astyle cppcheck file gdb lcov \
    libssl-dev libxml2-dev libxml2-utils libspdlog-dev python3-setuptools python3-wheel \
    rsync shellcheck unzip zip bc gz-harmonic libunwind-dev cppzmq-dev \
    libeigen3-dev libopencv-dev libgstreamer-plugins-base1.0-dev pkg-config protobuf-compiler
