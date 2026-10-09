#!/usr/bin/env bash
set -eo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
python3 -m pytest -q
python3 -m compileall -q ros2_ws/src/aerobase_monitor scripts
for aerobase_script in scripts/*.sh; do
    bash -n "$aerobase_script"
done
shellcheck --severity=warning scripts/*.sh
