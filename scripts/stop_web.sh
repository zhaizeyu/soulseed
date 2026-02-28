#!/usr/bin/env bash
# 停止 Web 后端与前端，在项目根目录执行

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/.web.pids"

stop_by_pid_file() {
  [ ! -f "$PID_FILE" ] && return 1
  while read -r pid; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -TERM "$pid" 2>/dev/null && echo "已停止 PID $pid"
  done < "$PID_FILE"
  rm -f "$PID_FILE"
  return 0
}

stop_by_port() {
  for port in 8765 5173; do
    # macOS / Linux: lsof -ti:PORT
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -TERM 2>/dev/null && echo "已停止占用端口 $port 的进程" || true
    fi
  done
}

if stop_by_pid_file; then
  echo "已按 PID 文件停止。"
else
  stop_by_port
  echo "已按端口 8765/5173 清理。"
fi
