#!/usr/bin/env bash
# 后端启动 Telegram Bot（nohup，断终端也保持运行），在项目根目录执行

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PID_FILE="$ROOT/.telegram.pid"
LOG_FILE="$ROOT/logs/telegram.log"

[ -d "$ROOT/logs" ] || mkdir -p "$ROOT/logs"
if [ -d "$ROOT/.venv" ]; then
  . "$ROOT/.venv/bin/activate"
fi

if [ -f "$PID_FILE" ]; then
  pid=$(cat "$PID_FILE")
  if kill -0 "$pid" 2>/dev/null; then
    echo "Telegram Bot 已在运行 (PID $pid)。先执行 scripts/stop_telegram.sh 再启动。"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo "启动 Telegram Bot（后端运行，日志: $LOG_FILE）..."
nohup python -m src.telegram >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "已启动 PID $(cat "$PID_FILE")。停止: ./scripts/stop_telegram.sh"
