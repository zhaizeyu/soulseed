# Web 模块说明

Web 模块将对话能力以 HTTP API 形式暴露，并与 `main.py` 的 CLI 调度器**解耦**：不依赖 `Orchestrator`，仅复用 `brain`（conscious、memory、prompt_assembler）与 `senses`（vision）能力。

## 架构

- **后端**：`src/web/`  
  - `service.py`：`ConversationService` 封装单轮对话（Mem0 检索 → 截屏 → 主脑流式），历史与 CLI **共用唯一数据源**（`chat_history_store`，即 config 中的 `chat_history_file`，默认 `data/chat_history.json`）。  
  - `server.py`：FastAPI 应用，提供 `GET /api/history`、`POST /api/chat`（SSE 流式）与 `POST /api/chat/sync`（非流式）。  
  - 启动方式：`python -m src.web` 或 `uvicorn src.web.server:app --host 0.0.0.0 --port 8765`。

- **前端**：`webapp/`（Vite + React + TypeScript + Tailwind CSS + shadcn/ui 风格 + Lucide + TanStack Query + Framer Motion）  
  - **配色**：深色主题（背景 `#0f1117`），顶栏 VedalAI | Terminal，绿色状态点、Secure/Online。  
  - 聊天界面：消息列表 + **输入框固定在底部**（`shrink-0` 贴底通栏），回车发送；**空输入也可发送**（表示「继续说话」）。流式打字机效果（SSE）；历史由 TanStack Query 拉取并缓存。  
  - **消息渲染**：`webapp/src/lib/format-content.ts` 解析助手回复，按类型分段展示：
    - `(...)` / `（...）` → 心理想的（褐色斜体 `text-thought`）
    - `"..."` / `「...」` / 弯双引号 `"..."` → 说的话（黄色 `text-speech`）
    - 其余 → 场景描写（白色）
    - 单引号 `'...'` 不视为说的话
  - **反引号**：`` `code` `` 使用蓝色高亮（`text-indigo-300` + `bg-white/[0.05]`）。  
  - 开发时通过 Vite `proxy` 将 `/api` 转发到后端，生产可配置 `VITE_API_URL` 指向后端。

## 运行步骤

1. 确保已配置 `.env` 中的 `GEMINI_API_KEY`（与 CLI 共用）。
2. **一键起停（推荐）**  
   在项目根目录执行：
   ```bash
   ./scripts/start_web.sh   # 启动后端 + 前端（后台运行）
   ./scripts/stop_web.sh   # 停止后端与前端
   ```
   首次使用前端前需先执行一次 `cd webapp && npm install`。启动后后端为 `http://127.0.0.1:8765`，前端为 `http://localhost:5173`。
3. **分别启动**  
   - 启动 API 服务：`python -m src.web`，默认监听 `http://0.0.0.0:8765`。可在 `config.yaml` 中设置 `web_host`、`web_port`、`web_reload`。  
   - 另开终端启动前端：`cd webapp && npm run dev`，浏览器访问 `http://localhost:5173`（Vite 默认端口）。
4. 生产部署：前端 `npm run build`，将 `webapp/dist` 交给任意静态服务器；后端单独用 uvicorn 部署；前端通过 `VITE_API_URL` 指向后端。

## API 说明

- **GET /**、**GET /api/health**：健康检查。
- **GET /api/history**：返回当前对话历史 `{"messages": [{"role": "user"|"assistant", "content": "..."}, ...]}`，与 CLI 共用唯一数据源（config `chat_history_file`，默认 `data/chat_history.json`）。**前端只读此接口展示，不以本地聊天记录覆盖后端。**
- **POST /api/chat**  
  - 请求体：`{"message": "用户输入"}`，`message` 可为空（表示「继续说话」）。  
  - 响应：`Content-Type: text/event-stream`，每行 `data: {"chunk": "片段", "done": false}`，结束行为 `data: {"chunk": null, "done": true}`。
- **POST /api/chat/sync**  
  - 请求体同上。  
  - 响应：`{"reply": "完整回复文本"}`。

## 与现有代码的关系

| 组件       | 使用方式 |
|------------|----------|
| orchestrator | **不使用**；Web 不 import 调度器。 |
| config_loader | 使用，读取 `config.yaml` 与 `.env`。 |
| memory     | 使用，`search` / `add_background`。 |
| conscious  | 使用，`chat_stream`。 |
| vision     | 使用，`get_screen_for_turn`。 |
| chat_history_store | **使用**；与 CLI 共用，读写 config 中的 `chat_history_file`（唯一数据源）。 |

因此 CLI 与 Web 共用同一份对话历史文件，数据源唯一。若之前使用过 `data/chat_history_web.json`，该文件已不再使用，可手动合并到 `data/chat_history.json` 后删除。
