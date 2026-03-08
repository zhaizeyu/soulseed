#!/usr/bin/env bash
# 后端启动 Web 后端（FastAPI）与前端（Vite），nohup 断终端也保持运行，在项目根目录执行

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PID_FILE="$ROOT/.web.pids"
LOG_BACKEND="$ROOT/logs/web_backend.log"
LOG_FRONTEND="$ROOT/logs/web_frontend.log"

[ -d "$ROOT/logs" ] || mkdir -p "$ROOT/logs"
if [ -d "$ROOT/.venv" ]; then
  . "$ROOT/.venv/bin/activate"
fi

if [ -f "$PID_FILE" ]; then
  echo "已有 .web.pids，可能已在运行。先执行 scripts/stop_web.sh 再启动。"
  exit 1
fi

# 后端：默认 8765，nohup 写日志
echo "启动后端 (FastAPI)，日志: $LOG_BACKEND ..."
nohup python -m src.web >> "$LOG_BACKEND" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE"

# 前端：Vite 默认 5173，nohup 写日志
echo "启动前端 (Vite)，日志: $LOG_FRONTEND ..."
nohup bash -c "cd '$ROOT/webapp' && npm run dev" >> "$LOG_FRONTEND" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"

echo "后端 PID: $BACKEND_PID  前端 PID: $FRONTEND_PID"
echo "后端: http://127.0.0.1:8765  前端: http://localhost:5173"
echo "停止: ./scripts/stop_web.sh"
