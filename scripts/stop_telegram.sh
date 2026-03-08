#!/usr/bin/env bash
# 停止 Telegram Bot（由 start_telegram.sh 启动的进程），在项目根目录执行

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/.telegram.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "未找到 .telegram.pid，Telegram Bot 可能未运行。"
  exit 0
fi

pid=$(cat "$PID_FILE")
if kill -0 "$pid" 2>/dev/null; then
  kill -TERM "$pid" 2>/dev/null && echo "已停止 Telegram Bot (PID $pid)"
else
  echo "进程 $pid 已不存在。"
fi
rm -f "$PID_FILE"
