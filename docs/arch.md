# 数字生命 MVP 架构设计文档 (基于 Gemini 多模态原生架构)

## 📐 1. 项目目录结构总览

```text
VedalAI_Project/
├── .env                    # [机密] 存放 API Keys (GEMINI_API_KEY, OPENAI_API_KEY, VTS_PORT)
├── config.yaml             # [配置] 全局参数 (主脑/记忆/日志/感官/表达)
├── main.py                 # [入口] 程序启动总入口
├── requirements.txt        # Python 依赖库列表
├── README.md               # 项目开发与运行文档
├── docs/                   # [文档] 架构与提示词说明
│   ├── arch.md             # 本架构设计文档
│   ├── development_progress.md  # 开发阶段与进度
│   ├── prompt.md           # 提示词组装顺序说明
│   ├── prompt.json         # 组装示例/参考
│   └── assembled_prompt.json # 命令行组装输出 (python -m src.brain.prompt_assembler)
│
├── data/                   # [运行时数据]
│   ├── chat_history.json   # 历史对话持久化 (条数见 config chat_history_max_entries)
│   ├── vision/             # 每轮截图 (screenshot_*.jpg/png)，见 config vision_save_*
│   └── mem0/               # 长期记忆 (Mem0)：需配置 GEMINI_API_KEY 后使用
│       ├── config.json     # Mem0 库内部配置
│       ├── history.db      # 记忆元数据 (SQLite)
│       ├── qdrant/         # 向量库目录 (嵌入向量与检索索引)
│       └── migrations_qdrant/  # Qdrant 内部迁移目录，勿手动修改
│
├── scripts/                # [脚本]
│   └── inspect_mem0_vectors.py  # 查看向量库中已存储的记忆 (需先退出主程序)
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
├── webapp/                 # [前端] Vite + React，打字输入、流式展示；见 docs/web.md
│   ├── src/
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
    │   └── vision.py       # [眼睛] 屏幕截取，直接输出图像对象，无 API 消耗
    │
    ├── brain/              # === 大脑层 (认知与决策) ===
    │   ├── __init__.py
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
    │   └── body.py         # [物理表征] VTube Studio 协议封装，控制口型同步与面部表情
    │
    ├── web/                # === Web 模块 (与 main 解耦) ===
    │   ├── __init__.py
    │   ├── service.py      # [对话服务] 单轮对话封装，历史与 CLI 共用 chat_history_store（唯一数据源）
    │   ├── server.py       # [FastAPI] POST /api/chat 流式、/api/chat/sync 非流式
    │   └── __main__.py     # 入口: python -m src.web
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
1. 加载 `config`、历史对话（`chat_history_store`）与 Mem0 检索结果占位。
2. 每轮：先 `await memory.search(当前用户输入)` 得到 `_mem0_lines`（**用户直接回车时 query 为空，search 直接返回 [] 不调 Mem0**）；再在 executor 中取 `vision.get_screen_for_turn()` 得到本回合截图（可选）；调用 `conscious.chat_stream(..., vision_image=...)` 做主脑流式生成并打印。**用户直接回车（空输入）时仍执行本轮**，由 prompt_assembler §7 插入「继续说话」占位。
3. 每轮结束：有用户输入则追加 user 与 assistant，否则只追加 assistant；**等待** `memory.add_background(user_input, reply_text)` 写入长期记忆后再进入下一轮。
4. 后续阶段：接入 `hearing` / `vision` / `mouth` / `player` / `body`，用 `asyncio.gather` 并联；语音/插嘴时调用 `player.interrupt()`。


* **`config_loader.py`**
* **核心职责**：单例模式的配置加载器。将 `config.yaml` 的业务配置和 `.env` 的机密凭证合并为一个全局可访问的配置对象。

* **配置项摘要（config.yaml + .env）**
  * **.env**：`GEMINI_API_KEY`（主脑与 Mem0 共用）、`OPENAI_API_KEY`、`VTS_PORT`。
  * **主脑**：`gemini_model`。
  * **历史对话**：`chat_history_file`、`chat_history_max_entries`。
  * **长期记忆 (Mem0)**：`mem0_embedder_model`、`mem0_llm_model`、`mem0_search_limit`、`mem0_embedding_dims`、`mem0_llm_temperature`、`mem0_infer`（true=只存抽取事实，false=存原文）、可选 `mem0_vector_store_path`。
  * **日志**：`log_dir`、`log_file`。
  * **眼睛**：`vision_enabled`、`vision_max_longer_side`（先缩放再送主脑）；`vision_save_enabled`、`vision_save_dir`（截图存 data）、`vision_save_format`（jpg/png）、`vision_jpeg_quality`。
  * **感官/表达**：`vision_interval`、`tts_voice`、`vad_sensitivity`、`vts_host`、`vts_port`。


* **`logger.py`**
* **核心职责**：提供彩色终端日志输出，区分 `[INFO]`, `[DEBUG]`, `[ERROR]`, `[VISION]`, `[AUDIO]` 等标签，确保异步多线程环境下日志不穿插错乱。



### B. 感官层 (`src/senses/`)

* **`hearing.py` (耳朵)**
* **核心职责**：捕捉外部语音指令并转为文本。
* **实现细节**：集成 WebRTC VAD 或 Silero VAD 进行环境音检测。当音量超过阈值触发录音，检测到持续静音（如 1 秒）则停止录音。将截获的音频块发送至 Whisper API，返回识别出的 `str` 文本。


* **`vision.py` (眼睛)**
* **核心职责**：获取数字生命的视觉输入，供主脑多模态使用。
* **实现细节**：基于 `mss` 抓取主屏，返回 `PIL.Image`。`get_screen_for_turn()` 先按 `vision_max_longer_side` 缩放（压缩尺寸、省 token），再按 `vision_save_enabled` / `vision_save_dir` 将截图写入 `data/vision/`（文件名 `screenshot_YYYYMMDD_HHMMSS.jpg` 或 `.png`），最后返回图像供主脑多模态。配置项：`vision_save_format`（jpg/png）、`vision_jpeg_quality`（存为 jpg 时质量）。调度器每轮在 executor 中调用取图并传入 `conscious.chat_stream(..., vision_image=...)`。



### C. 大脑层 (`src/brain/`)

* **`prompt_assembler.py` (提示词组装)**
* **核心职责**：**所有面向模型的提示词仅在此组装**（主脑不再注入）。按 prompt.md §1–§8 顺序：Jailbreak → 角色卡 → 示例 → Mem0 → 历史 → §6 环境感知 → §7 用户当前回合 → Task。
* **实现细节**：§6 仅在 `vision_image_attached` 或 `vision_audio_text` 非空时插入（截图说明或耳朵摘要）；§7 有输入则用输入，**无输入则插入「(请根据上文以角色身份继续说话。)」**，保证本回合必有一条 user。`vision_audio_text` 为占位参数（当前主流程恒空，仅接入耳朵后有内容）。

* **`conscious.py` (主脑 - Gemini 核心)**
* **核心职责**：按 prompt_assembler 组装好的消息调用 Gemini 流式生成，**不在此注入任何提示词**。
* **实现细节**：调用 `build_messages(...)`（含 `vision_image_attached`）得到消息列表，转为 Gemini Content 后，本回合发送内容为「组装好的 current_user_content + 可选 vision_image」；无 system_instruction，全部按顺序进 history。模型名等来自 `config.yaml`。

* **`tools_registry.py` (原生工具箱)**
* **核心职责**：提供供 Gemini 自动调用的扩展能力。
* **实现细节**：包含一系列纯 Python 异步函数（例如 `search_web(query: str)`, `execute_code(script: str)`）。**强制要求**包含严谨的 Type Hints 和详细的 Docstring，因为 Gemini 会直接解析 Docstring 作为 Function Calling 的触发描述。


* **`memory.py` (海马体 - Mem0)**
* **核心职责**：维护长期记忆与人格一致性。
* **实现细节**：
  * 封装 Mem0，**全部使用 Gemini**（不依赖 OpenAI）：嵌入模型 `mem0_embedder_model`、记忆抽取用 LLM `mem0_llm_model`，向量库为本地 Qdrant（默认 `data/mem0/qdrant`）。数据目录 `MEM0_DIR=data/mem0`。
  * **`search(query, top_k)`**：按语义检索相关记忆；**query 为空时直接返回 []**，不调用 Mem0（避免 Gemini 报 400）。
  * **`add_background(user_input, reply_text)`**：每轮结束后写入记忆。由 **`mem0_infer`** 控制：`true` 时传入整轮 user+assistant 抽事实；`false` 或 user 为空时存助手回复原文。事实抽取若遇非法 JSON 会降级存原文；Mem0 的 Invalid JSON 日志已过滤不刷控制台。
  * 未配置 `GEMINI_API_KEY` 或未安装 `mem0ai`/`google-genai` 时自动降级。



### D. 表达层 (`src/expression/`)

* **`mouth.py` (发声器官)**
* **核心职责**：将文本转化为语音。
* **实现细节**：监听 `conscious.py` 传来的文本流。通过正则表达式缓存句子，遇到标点符号（如 `. ! ? 。 ！ ？`）即刻切断，并将该句异步发送至 TTS 引擎（如 Edge-TTS 或 FishAudio API）。将生成的音频文件路径压入播放队列。


* **`player.py` (播放器)**
* **核心职责**：音频的物理输出与状态同步。
* **实现细节**：后台常驻的音频消费队列。播放音频时向 `body.py` 广播状态和音量数据；播放完毕后清理 `assets/temp/` 下的缓存文件。对外暴露 `interrupt()` 方法以支持瞬间闭嘴。


* **`body.py` (物理表征 - VTS 接口)**
* **核心职责**：驱动 Live2D 皮套动作。
* **实现细节**：基于 `pyvts` 建立与 VTube Studio 的 WebSocket 连接。接收 `player.py` 计算出的音频 RMS（响度），将其映射为 VTS 中的 `MouthOpen` 参数以实现精准唇形同步（Lip-sync）。同时正则匹配主脑输出文本中的情感标签（如 `*laughs*`），触发预设的面部表情热键。