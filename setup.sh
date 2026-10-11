#!/bin/bash
# 一键安装依赖：Python 虚拟环境（rumps / pyobjc）+ Node 依赖（playwright-core）
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "❌ 未找到 $PYTHON_BIN，请先安装 Python 3。"
  exit 1
fi

echo "→ 创建虚拟环境 .venv"
"$PYTHON_BIN" -m venv .venv

echo "→ 安装 Python 依赖"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  echo "→ 安装 Node 依赖（playwright-core）"
  npm install --silent --no-fund --no-audit
else
  echo "⚠️  未找到 npm。请安装 Node.js 后在本目录执行：npm install"
fi

if [ ! -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  echo "ℹ️  未检测到系统 Google Chrome —— 抓取需要 Chromium 内核浏览器，"
  echo "   请安装 Google Chrome，或用 WB_LIMIT_CHROME 指定浏览器路径。"
fi

echo
echo "✅ 安装完成。运行："
echo "   ./run.sh                     # 前台启动菜单栏挂件"
echo "   或在菜单里打开「开机自启」   # 登录时自动启动"
