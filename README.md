# 数字生命 MVP (SoulSeed Project)

基于 Gemini 多模态原生架构的数字生命 MVP，详见 [arch.md](docs/arch.md)。

## 目录结构概览

- `main.py` — 程序入口
- `config.yaml` — 全局配置
- `.env` — API 密钥（从 `.env.example` 复制并填写）
- `assets/` — 人设、世界书、音效、TTS 临时文件
- `src/` — 核心 / 感官 / 大脑 / 表达 / 工具 源码

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 **`GEMINI_API_KEY`**（在 [Google AI Studio](https://aistudio.google.com/apikey) 申请）；**主脑、长期记忆（Mem0）、语音转写（STT）** 均使用该 Key，全为 Google Gemini，无需其他厂商 API。
2. 安装依赖：`pip install -r requirements.txt`（主脑、Mem0、语音转写均用 **google-genai**）。
3. 运行：`python main.py`。**模拟输入**：终端输入内容回车发送，主脑流式输出；**直接回车**让助手继续说话；输入 `exit` 或 `quit` 退出。
4. **历史对话**持久化在 `data/chat_history.json`，每次启动加载最近 N 条（见 `config.yaml` 的 `chat_history_max_entries`）。
5. **长期记忆**：配置了 `GEMINI_API_KEY` 后自动启用 Mem0，数据落在 `data/mem0/`。支持记忆元数据（情绪、重要度、时间、类型）；每轮结束后会等待写入再进入下一轮。查看已存记忆及元数据：先退出主程序，再运行 `python scripts/inspect_mem0_vectors.py`。
6. **眼睛**：默认每轮截屏并作为多模态输入传给主脑（Gemini 可见当前屏幕）。会先按 `vision_max_longer_side` 缩放再发送（省 token），并可选将截图存到 `data/vision/`（`vision_save_enabled`、`vision_save_dir`、`vision_save_format`、`vision_jpeg_quality`）。设 `vision_enabled: false` 可关闭截屏。
7. **主脑输出长度**：`config.yaml` 中 `gemini_max_output_tokens`（默认 8192）控制单轮回复上限，过小可能导致输出被截断。
8. 运行期日志写入 `logs/soulseed.log`（可在 `config.yaml` 中配置 `log_dir` / `log_file`）。

## Web 对话（与 CLI 解耦）

Web 模块独立于 `main.py` 调度器，通过 FastAPI 暴露对话 API，前端用 React 打字输入、流式展示回复。

1. **一键起停**：在项目根执行 `./scripts/start_web.sh` 启动后端与前端，`./scripts/stop_web.sh` 停止。首次需先 `cd webapp && npm install`。
2. **分别启动**：后端 `python -m src.web`（默认 `http://0.0.0.0:8765`）；前端 `cd webapp && npm run dev`（Vite 默认 `http://localhost:5173`）。可在 `config.yaml` 配置 `web_host` / `web_port`。
3. **接口**：`GET /api/history` 读历史；`GET /api/config` 读前端配置（如 `tts_reply_enabled`）；`POST /api/chat` 流式对话；`POST /api/chat/sync` 非流式；`POST /api/speech-to-text` 语音转文本（Gemini）；`POST /api/tts` 文本转语音（Edge-TTS）。历史与 CLI 共用唯一数据源（config `chat_history_file`，默认 `data/chat_history.json`）。
4. **语音输入**：输入框左侧麦克风按钮，点击开始录音、再点击停止并识别，结果追加到输入框。
5. **嘴巴（TTS）**：当 `config.yaml` 中 **`tts_reply_enabled: true`** 时，助手回复中的「说的话」（`"..."`、`「...」` 等）在流式结束后会自动用 Edge-TTS 读出来；设为 `false` 可关闭语音回复。音色见 `tts_voice`。
6. 详见 [docs/web.md](docs/web.md)。

## Telegram Bot（与 CLI/Web 并列）

独立入口 `python -m src.telegram`，与 **CLI**（`main.py` 终端模式）、**Web**（`./scripts/start_web.sh`）并列。

1. **配置**：`.env` 中填 `TELEGRAM_BOT_TOKEN`（[@BotFather](https://t.me/BotFather) 创建）；`config.yaml` 中设 `telegram_enabled: true`。可选 `telegram_speaker_name`（回复中「说的话」前的角色名，默认 Kurisu）。
2. **运行**：`python -m src.telegram`。支持文本、语音（STT 转文字）、图片（按眼睛配置压缩后送主脑）。
3. **回复渲染**：发送时按 **语言**（`<b>角色名："内容"</b>`）、**心理**（`<i>…</i>`）、**场景**（纯文本）转成 Telegram HTML。
4. **记忆**：按 `chat_id` 隔离，`user_id = tg_{chat_id}`，与 CLI/Web 的 default 互不干扰。详见 [docs/telegram.md](docs/telegram.md)。

## 部署到 Debian 云服务器

**无需改代码**：路径与网络绑定已跨平台。在服务器上保持 `vision_enabled: false`（默认）、配置 `.env` 中的 `GEMINI_API_KEY`，安装依赖后直接运行 `python -m src.web` 或 `python -m src.telegram` 即可。详见 [docs/deploy.md](docs/deploy.md)。

## 开发与扩展

- **人设与 System Instruction**：编辑 `assets/personas/character.json`
- **单轮用户输入**：`src.brain.turn_input.UserTurnInput` 统一封装文本、图片、语音路径、metadata，Web/CLI 每轮先构造再调 memory + conscious，后续扩展 Telegram 图片/语音等不改接口。
- **提示词组装**（顺序见 `docs/prompt.md`）：**所有面向模型的提示词仅在** `src.brain.prompt_assembler.build_messages()` 中组装（主脑不注入）；§4 记忆带时间/情绪/重要度；§6 截图/耳朵，§7 无输入时插入「继续说话」；数据来自 `assets/prompts/`、persona、Mem0、历史、vision_image_attached 等。
- **长期记忆 (Mem0)**：配置见 `config.yaml` 的 `mem0_*` 项。**按 user_id 隔离**：CLI/Web 不传则用 `"default"`（共用一份）；Telegram 用 `tg_{chat_id}`（每会话独立）。支持元数据（情绪、重要度、时间、类型）；向量库路径默认 `data/mem0/qdrant`。详见 `docs/arch.md` § 大脑层 memory.py
- **世界书**：放入 `assets/world_books/*.json`，使用 `src.utils.io_utils` 的 `load_world_book` / `get_world_book_prompt_snippet` 等
- **业务工具**（供 Gemini 调用）：在 `src/brain/tools_registry.py` 中注册
- **进度与阶段**：见 `docs/development_progress.md`；配置项说明见 `config.yaml` 与 `docs/arch.md`
