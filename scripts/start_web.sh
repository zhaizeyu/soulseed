#!/usr/bin/env bash
# 启动 Web 后端（FastAPI）与前端（Vite），在项目根目录执行

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PID_FILE="$ROOT/.web.pids"

# 若已在运行则提示
if [ -f "$PID_FILE" ]; then
  echo "已有 .web.pids，可能已在运行。先执行 scripts/stop_web.sh 再启动。"
  exit 1
fi

# 后端：默认 8765
echo "启动后端 (FastAPI) ..."
python -m src.web &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE"

# 前端：Vite 默认 5173
echo "启动前端 (Vite) ..."
(cd webapp && npm run dev) &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_FILE"

echo "后端 PID: $BACKEND_PID  前端 PID: $FRONTEND_PID"
echo "后端: http://127.0.0.1:8765  前端: http://localhost:5173"
echo "停止: ./scripts/stop_web.sh"
