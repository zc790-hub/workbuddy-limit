#!/bin/bash
# 前台启动菜单栏挂件（关掉终端即退出）。想常驻请用菜单里的「开机自启」。
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="${PYTHON:-python3}"

exec "$PY" -u workbuddy-limit.py
