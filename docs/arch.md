# 数字生命 MVP 架构设计文档 (基于 Gemini 多模态原生架构)

**模型与 API**：主脑、长期记忆（Mem0）、语音转写（STT）均使用 **Google Gemini**（统一通过 **google-genai** SDK），仅需配置 `GEMINI_API_KEY`，无 OpenAI 或其他厂商依赖。

## 📐 1. 项目目录结构总览

```text
SoulSeed_Project/
├── .env                    # [机密] 存放 API Key：GEMINI_API_KEY（主脑、Mem0、语音转写均用 Google Gemini）
├── config.yaml             # [配置] 全局参数 (主脑/记忆/日志/感官/表达)
├── main.py                 # [入口] 程序启动总入口
├── requirements.txt        # Python 依赖库列表
├── README.md               # 项目开发与运行文档
├── docs/                   # [文档] 架构与提示词说明
│   ├── arch.md             # 本架构设计文档
│   ├── development_progress.md  # 开发阶段与进度
│   ├── telegram.md         # Telegram 对接功能与架构设计 (python-telegram-bot)
│   ├── prompt.md           # 提示词组装顺序说明
│   ├── prompt.json         # 组装示例/参考
│   └── assembled_prompt.json # 命令行组装输出 (python -m src.brain.prompt_assembler)
│
├── data/                   # [运行时数据]
│   ├── chat_history.json   # 历史对话持久化 (条数见 config chat_history_max_entries)
│   ├── vision/             # 每轮截图 (screenshot_*.jpg/png)，见 config vision_save_*
│   ├── telegram/           # [可选] Telegram 按会话历史 (chats/{chat_id}.json)
│   └── mem0/               # 长期记忆 (Mem0)：需配置 GEMINI_API_KEY 后使用
│       ├── config.json     # Mem0 库内部配置
│       ├── history.db      # 记忆元数据 (SQLite)
│       ├── qdrant/         # 向量库目录 (嵌入向量与检索索引)
│       └── migrations_qdrant/  # Qdrant 内部迁移目录，勿手动修改
│
├── scripts/                # [脚本]
│   ├── start_web.sh        # 一键启动 Web 后端 + 前端（8765 + 5173）
│   ├── stop_web.sh         # 一键停止后端与前端（按端口清理）
│   └── inspect_mem0_vectors.py  # 查看向量库中已存储的记忆及元数据 (需先退出主程序)
│
├── assets/                 # [资源文件]
│   ├── personas/           # 人设与提示词配置
│   │   └── vedal_main.json # 主脑 System Instruction (核心人设、行为准则)
│   ├── prompts/           # 提示词组装模板与默认数据
│   │   ├── jailbreak.json  # 越狱/核心规则 (绝对头部)
│   │   ├── task.json       # 输出风格限制 (绝对底部)
│   │   ├── user_info.json  # 用户身份描述
│   │   └── prompt_defaults.json # Mem0/历史/眼睛耳朵初始数据
│   ├── world_books/        # 世界书 (Lore/规则) JSON，关键词触发，供组装提示词
│   │   └── *.json         # 如 sex_acts_world_info.json
│   ├── sounds/             # 预置音效 (如"思考中"提示音)
│   └── temp/               # [临时] 存放 TTS 实时生成的音频切片 (自动轮转清理)
│
├── webapp/                 # [前端] Vite + React，Cubism Web SDK 加载 Live2D 模型；见 docs/web.md
│   ├── src/                # 聊天 UI + Live2D 画布，接收后端参数驱动模型
│   └── package.json
│
└── src/                    # [源代码核心层]
    ├── __init__.py
    │
    ├── core/               # === 核心层 (躯干与中枢神经) ===
    │   ├── __init__.py
    │   ├── orchestrator.py # [调度器] 核心主循环，管理所有模块的异步协同与生命周期
    │   ├── config_loader.py# [配置管理] 统一加载 .env 和 .yaml 参数
    │   └── logger.py       # [日志记录] 格式化日志输出，便于 API 报错调试
    │
    ├── senses/             # === 感官层 (数据输入) ===
    │   ├── __init__.py
    │   ├── hearing.py      # [耳朵] 麦克风录音控制、静音检测 (VAD)、语音转文本 (STT)
    │   └── vision.py       # [眼睛] 屏幕截取、心跳检测（定时截图对比，有变化则触发主动说话）
    │
    ├── brain/              # === 大脑层 (认知与决策) ===
    │   ├── __init__.py
    │   ├── turn_input.py   # [统一输入] UserTurnInput(text/images/audio_path/metadata)，多端扩展不改签名
    │   ├── conscious.py    # [主脑] 封装 Gemini API，处理多模态上下文、对话会话管理
    │   ├── prompt_assembler.py # [提示词组装] §1–§8 全在此组装，主脑不注入；§6 截图说明/耳朵，§7 无输入时「继续说话」
    │   ├── chat_history_store.py # [历史对话] JSON 持久化，每次加载最近 N 条
    │   ├── tools_registry.py # [工具箱] 纯 Python 业务函数库 (代码执行/搜索等)，供 Gemini 自动调用
    │   └── memory.py       # [海马体] 封装 Mem0，负责长期记忆的异步写入与检索
    │
    ├── expression/         # === 表达层 (行为输出) ===
    │   ├── __init__.py
    │   ├── mouth.py        # [发声器官] 文本流接收与 TTS 语音合成
    │   ├── player.py       # [播放器] 异步音频播放队列控制及硬件打断机制
    │   └── body.py         # [身体参数] 计算 Live2D 控制参数（口型、表情等），通过 Web API/WebSocket 推送给前端
    │
    ├── web/                # === Web 模块 (与 main 解耦) ===
    │   ├── __init__.py
    │   ├── service.py      # [对话服务] 单轮对话封装，历史与 CLI 共用 chat_history_store（唯一数据源）
    │   ├── server.py       # [FastAPI] POST /api/chat 流式、/api/chat/sync 非流式
    │   └── __main__.py     # 入口: python -m src.web
    │
    ├── telegram/           # === Telegram 模块 (与 main 解耦，可选) ===
    │   ├── __init__.py
    │   ├── bot.py          # PTB Application、polling 启动
    │   ├── handlers.py     # /start、/help、/clear、文本/语音/图片
    │   ├── service.py      # 按 chat_id 的单轮对话（历史 + 主脑 + Mem0 user_id 隔离）
    │   ├── history.py      # 按 chat_id 会话历史（全量存盘，读取最近 N 条）
    │   ├── format_reply.py # 回复转 Telegram HTML（语言加粗、心理斜体）
    │   └── __main__.py     # 入口: python -m src.telegram
    │
    └── utils/              # === 通用工具库 ===
        ├── __init__.py
        ├── api_client.py   # 统一的底层异步 HTTP 请求封装 (带重试机制)
        └── io_utils.py     # 图片压缩、人设/世界书加载、音频格式转换等 I/O 辅助

```

---

## 📂 2. 各个文件功能详细描述

### A. 核心层 (`src/core/`)

* **`orchestrator.py` (调度器)**
* **核心职责**：管理整个数字生命的“主游戏循环 (Main Loop)”。
* **当前执行逻辑（第一步闭环 + 长期记忆）**：
1. 加载 `config`、历史对话（`chat_history_store`）。
2. 每轮：将本回合入参封装为 **`UserTurnInput`**（text + 可选 images）；用 `turn_input.effective_text()` 做 `memory.search(..., user_id="default")` 得到 mem0 结果，取 `turn_input.images[0]` 作为 vision；调用 `conscious.chat_stream(..., mem0_lines=..., vision_image=...)` 做主脑流式生成并打印。**用户直接回车（空输入）时仍执行本轮**，由 prompt_assembler §7 插入「继续说话」占位。**眼睛心跳**：后台每 N 秒调用 `vision.check_heartbeat()`，有变化则向队列注入「画面发生了你感兴趣的变化…」回合，带当前截图执行一轮。
3. 每轮结束：用 `turn_input.effective_text()` 与回复追加 user/assistant；**等待** `memory.add_background(..., user_id="default")` 写入长期记忆后再进入下一轮（metadata 可接入情绪识别，当前可传 None）。
4. 后续阶段：接入 `hearing` / `vision` / `mouth` / `player` / `body`，用 `asyncio.gather` 并联；语音/插嘴时调用 `player.interrupt()`；`body` 计算参数并推送给 Web 前端以驱动 Live2D。


* **`config_loader.py`**
* **核心职责**：单例模式的配置加载器。将 `config.yaml` 的业务配置和 `.env` 的机密凭证合并为一个全局可访问的配置对象。

* **配置项摘要（config.yaml + .env）**
  * **.env**：`GEMINI_API_KEY`（主脑、Mem0、语音转写 STT 均用此 Key）；`TELEGRAM_BOT_TOKEN`（Telegram Bot 启用时必填）。
  * **调试**：`debug_log_prompt`（true=每次请求前将组装好的完整提示词打印到日志）。
  * **主脑**：`gemini_model`；`gemini_max_output_tokens`（单轮回复最大 token 数，默认 8192，过小易触发输出截断）。
  * **历史对话**：`chat_history_file`、`chat_history_max_entries`。
  * **长期记忆 (Mem0)**：`mem0_embedder_model`、`mem0_llm_model`、`mem0_search_limit`、`mem0_embedding_dims`、`mem0_llm_temperature`、`mem0_infer`（true=只存抽取事实，false=存原文）、可选 `mem0_vector_store_path`。
  * **日志**：`log_dir`、`log_file`。
  * **眼睛**：`vision_enabled`、`vision_max_longer_side`（先缩放再送主脑）；`vision_save_enabled`、`vision_save_dir`（截图存 data）、`vision_save_format`（jpg/png）、`vision_jpeg_quality`；**心跳检测**：`vision_heartbeat_enabled`、`vision_heartbeat_interval_sec`（如 30）、`vision_heartbeat_diff_threshold`（差异阈值 0~1）。
  * **感官/表达**：`vision_interval`、`tts_voice`、`tts_reply_enabled`（是否开启助手语音回复）、`vad_sensitivity`、`vts_host`、`vts_port`。
  * **Telegram**：`telegram_enabled`、`telegram_max_history_entries`（每会话上下文条数；磁盘全量存储）、可选 `telegram_speaker_name`（回复中「说的话」前角色名，默认 Kurisu）、`telegram_chat_history_dir`。


* **`logger.py`**
* **核心职责**：提供彩色终端日志输出，区分 `[INFO]`, `[DEBUG]`, `[ERROR]`, `[VISION]`, `[AUDIO]` 等标签，确保异步多线程环境下日志不穿插错乱。



### B. 感官层 (`src/senses/`)

* **`hearing.py` (耳朵)**
* **核心职责**：语音转文本 (STT)，供 Web、CLI、Telegram 使用。
* **实现细节**：`speech_to_text(audio_bytes, filename)` 使用 **google-genai**（Gemini 多模态）转写，支持 webm/mp3/wav/ogg 等；与主脑共用 `GEMINI_API_KEY` 与 `gemini_model`。未配置 Key 时返回空并打日志。**Web**：前端录音后 POST 到 `POST /api/speech-to-text`；**Telegram**：用户发语音时下载为 bytes 后调本函数，转写结果作为用户输入。CLI 端 VAD + 本地录音后调本函数（后续接入）。


* **`vision.py` (眼睛)**
* **核心职责**：获取数字生命的视觉输入，供主脑多模态使用；**心跳检测**：定时截图与上一帧对比，有显著变化则触发主动说话。
* **实现细节**：基于 `mss` 抓取主屏，返回 `PIL.Image`。`get_screen_for_turn()` 先按 `vision_max_longer_side` 缩放（压缩尺寸、省 token），再按 `vision_save_enabled` / `vision_save_dir` 将截图写入 `data/vision/`（文件名 `screenshot_YYYYMMDD_HHMMSS.jpg` 或 `.png`），最后返回图像供主脑多模态。**心跳检测**：`check_heartbeat()` 截取当前屏、与上一帧 64×64 灰度缩略图做像素差异比，超过 `vision_heartbeat_diff_threshold` 则返回 `(True, 当前帧)`，调度器据此注入一条系统提示（「画面发生了你感兴趣的变化…」）并带该截图执行一轮，实现主动说话。配置：`vision_heartbeat_enabled`、`vision_heartbeat_interval_sec`（如 30）、`vision_heartbeat_diff_threshold`（如 0.03）。



### C. 大脑层 (`src/brain/`)

* **`turn_input.py` (统一用户回合输入)**
* **核心职责**：将单轮用户输入抽象为 **`UserTurnInput`**（`text`、`images`、`audio_path`、`metadata`），供 CLI/Web/Telegram 等统一使用；后续扩展图片/语音/文件时只需往该结构填字段，无需改各端调用签名。
* **实现细节**：`effective_text()` 返回供检索与主脑使用的文本（当前即 `text`，后续可合并语音转写）。Web/Orchestrator 在每轮先将入参构造成 `UserTurnInput`，再从其中取 `effective_text()` 与首图调用 memory + conscious。

* **`prompt_assembler.py` (提示词组装)**
* **核心职责**：**所有面向模型的提示词仅在此组装**（主脑不再注入）。按 prompt.md §1–§8 顺序：Jailbreak → 角色卡 → 示例 → Mem0 → 历史 → §6 环境感知 → §7 用户当前回合 → Task。
* **实现细节**：**§4 潜意识记忆**：`mem0_lines` 为 `List[Dict]`，每项含 `memory`（正文）与可选 `metadata`。若有 `timestamp`/`time_context` 会组装成可读时间前缀（如「(3月7日 夜晚)」）；若有 `user_emotion`/`ai_emotion`/`importance` 会加情绪前缀与「重要记忆」后缀，便于主脑理解记忆的「温度」。§6 仅在 `vision_image_attached` 或 `vision_audio_text` 非空时插入；§7 有输入则用输入，**无输入则插入「(请根据上文以角色身份继续说话。)」**，保证本回合必有一条 user。`vision_audio_text` 为占位参数（当前主流程恒空，仅接入耳朵后有内容）。

* **`conscious.py` (主脑 - Gemini 核心)**
* **核心职责**：按 prompt_assembler 组装好的消息调用 Gemini 流式生成，**不在此注入任何提示词**。
* **实现细节**：使用 **google-genai**（`genai.Client`、`generate_content_stream`）。调用 `build_messages(...)`（含 `vision_image_attached`）得到消息列表，转为 `types.Content` 列表后，本回合发送「current_user_content + 可选 vision_image（PIL 转 JPEG bytes）」；无 system_instruction，全部按顺序进 history。模型名、`gemini_max_output_tokens`（单轮输出上限）等来自 `config.yaml`。

* **`tools_registry.py` (原生工具箱)**
* **核心职责**：提供供 Gemini 自动调用的扩展能力。
* **实现细节**：包含一系列纯 Python 异步函数（例如 `search_web(query: str)`, `execute_code(script: str)`）。**强制要求**包含严谨的 Type Hints 和详细的 Docstring，因为 Gemini 会直接解析 Docstring 作为 Function Calling 的触发描述。


* **`memory.py` (海马体 - Mem0)**
* **核心职责**：维护长期记忆与人格一致性；支持**记忆元数据**（情绪锚点、重要度、时间、类型）以区分「有温度」的记忆。
* **实现细节**：
  * 封装 Mem0，**全部使用 Google Gemini**：嵌入模型 `mem0_embedder_model`、记忆抽取用 LLM `mem0_llm_model`，向量库为本地 Qdrant（默认 `data/mem0/qdrant`）。数据目录 `MEM0_DIR=data/mem0`。
  * **`search(query, top_k, user_id=None)`**：按语义检索相关记忆，返回 `List[Dict]`，每项含 `memory`、`metadata`、`score`。**user_id** 用于多端/多用户隔离（不传则 `"default"`）；query 为空时返回 []，不调 Mem0。
  * **`add_background(user_input, reply_text, metadata=None, user_id=None)`**：每轮结束后写入记忆。**user_id** 同上；**metadata** 可选含 `user_emotion`、`ai_emotion`、`importance`、`memory_type` 等，写入时自动附加 `timestamp` 与 `time_context`。由 **`mem0_infer`** 控制：`true` 时抽事实，`false` 或 user 为空时存原文；非法 JSON 时降级存原文。
  * 未配置 `GEMINI_API_KEY` 或未安装 `mem0ai`/`google-genai` 时自动降级。
  * 查看已存记忆及元数据：先退出主程序，再运行 `python scripts/inspect_mem0_vectors.py`（会打印每条记忆的 Metadata 如 time_context、importance 等）。



### D. 表达层 (`src/expression/`)

* **`mouth.py` (嘴巴)**
* **核心职责**：将文本合成为语音，供 Web 播报「说的话」。
* **实现细节**：`text_to_speech_async(text)` 使用 **Edge-TTS** 合成，返回 mp3 字节；音色由 config `tts_voice`（如 `zh-CN-XiaoxiaoNeural`）指定。Web 端：当 config `tts_reply_enabled` 为 true 时，助手回复流式结束后前端解析「说的话」并请求 `POST /api/tts` 播放；为 false 时不播报。


* **`player.py` (播放器)**
* **核心职责**：音频的物理输出与状态同步。
* **实现细节**：后台常驻的音频消费队列。播放音频时向 `body.py` 提供 RMS/音量等数据供其计算口型参数；播放完毕后清理 `assets/temp/` 下的缓存文件。对外暴露 `interrupt()` 方法以支持瞬间闭嘴。


* **`body.py` (身体参数计算与推送)**
* **核心职责**：计算 Live2D 控制参数（口型、表情等），并推送给 Web 前端，由前端驱动模型。
* **实现细节**：接收 `player.py` 的音频 RMS（响度）等，计算口型开合等参数；解析主脑输出中的情感标签（如 `*laughs*`）得到表情 ID。通过 Web API（如 SSE/WebSocket 或 REST）将参数流推送给已连接的前端。**不在本机运行 VTube Studio**；Live2D 模型在浏览器端由 **Cubism Web SDK** 加载与渲染，前端仅接收后端下发的参数并驱动 SDK 更新模型状态。



### E. Web 层 (`src/web/`)

* **`service.py` (对话服务)**
* **核心职责**：封装单轮对话逻辑，与 CLI 共用 `chat_history_store`（唯一数据源）。
* **实现细节**：入参在内部封装为 **`UserTurnInput`**（text + 可选 images）；用 `turn_input.effective_text()` 与首图做 Mem0 检索 → 截屏或 override 图 → 主脑流式；历史读写 `config.chat_history_file`。空输入表示「继续说话」，与 orchestrator 行为一致。

* **`server.py` (FastAPI)**
* **核心职责**：暴露 HTTP API，供前端调用；**Web 模式含眼睛心跳**与统一日志。
* **实现细节**：`GET /api/history` 返回对话历史；`GET /api/config` 返回前端配置（如 `tts_reply_enabled`）；`POST /api/chat` SSE 流式；`POST /api/chat/sync` 非流式；`POST /api/speech-to-text` 语音转文本（Gemini）；`POST /api/tts` 文本转语音（Edge-TTS）。启动时（lifespan）根据 config 启动后台心跳任务；日志写入 config 的 `log_dir`/`log_file`。详见 `docs/web.md`。



### F. 前端 (webapp/)

* **技术栈**：Vite + React + TypeScript + Tailwind + shadcn/ui 风格 + Lucide + TanStack Query + Framer Motion；**Live2D 使用 Cubism Web SDK 官方 SDK** 在浏览器中加载与渲染模型。
* **UI 与渲染**：
  * **配色**：深色主题（背景 `#0f1117`），顶栏 SoulSeed | Terminal，绿色状态点。
  * **输入框**：固定在底部（`shrink-0`），贴底通栏；**空输入也可发送**（继续说话）。
  * **消息渲染**：`webapp/src/lib/format-content.ts` 解析助手回复，按类型分段：
    * `(...)` / `（...）` → 心理想的（褐色斜体 `text-thought`）
    * `"..."` / `「...」` / 弯双引号 `"..."` → 说的话（黄色 `text-speech`）；**双引号内字数少于 5（去空格后）则按场景文字渲染**（白色），不按「说的话」高亮
    * 其余 → 场景描写（白色）
    * 单引号 `'...'` 不视为说的话
  * **反引号**：`` `code` `` 使用蓝色高亮（`text-indigo-300` + `bg-white/[0.05]`）。
* **Live2D（身体展示）**：
  * **加载与渲染**：使用 **Cubism Web SDK** 官方方式在 Web 端加载 `.moc3` / `.model3.json` 等 Live2D 模型并渲染到 Canvas；模型资源可放在 `webapp/public/` 或通过配置指定 CDN/路径。
  * **驱动方式**：前端不计算口型/表情，仅接收后端（`body.py` + Web API）下发的参数（如口型开合度、表情 ID、视线等），按帧或按事件更新 Cubism 模型参数，实现口型同步与表情切换。后端负责根据音频 RMS、主脑文本情感标签等计算并推送这些参数。

### G. Telegram 模块 (`src/telegram/`，可选)

* **设计文档**：详见 **`docs/telegram.md`**。
* **核心职责**：基于 **python-telegram-bot** 对接 Telegram，使数字生命在 Telegram 中与用户对话；与 CLI/Web 解耦，**按 chat_id 隔离会话历史与 Mem0 user_id**。
* **模块组成**：`bot.py`（PTB Application、polling）；`handlers.py`（/start、/help、/clear、文本、语音、图片）；`service.py`（按 chat_id 调用主脑与记忆）；`history.py`（按 chat_id 持久化历史至 `data/telegram/chats/`，**全量存储**，读取时只取最近 N 条作上下文）；`format_reply.py`（将助手回复按场景/心理/说的话转为 Telegram HTML：**语言** `<b>角色名："内容"</b>`、**心理** `<i>…</i>`、场景纯文本；角色名由 config `telegram_speaker_name` 指定，默认 Kurisu）。
* **输入**：文本直接送主脑；语音经 `hearing.speech_to_text` 转写后作为用户输入；图片下载后经 `vision.prepare_image_for_turn` 压缩（与眼睛同配置）再送主脑。
* **运行方式**：独立入口 `python -m src.telegram`；需配置 `.env` 中 `TELEGRAM_BOT_TOKEN` 及 `config.yaml` 中 `telegram_enabled`；可选 `telegram_speaker_name`、`telegram_max_history_entries`、`telegram_chat_history_dir`。