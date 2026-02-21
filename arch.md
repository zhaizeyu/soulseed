# 数字生命 MVP 架构设计文档 (基于 Gemini 多模态原生架构)

## 📐 1. 项目目录结构总览

```text
VedalAI_Project/
├── .env                    # [机密] 存放 API Keys (GEMINI_API_KEY, OPENAI_API_KEY, VTS_PORT)
├── config.yaml             # [配置] 全局参数 (刷新频率, 音色, VAD灵敏度)
├── main.py                 # [入口] 程序启动总入口
├── requirements.txt        # Python 依赖库列表
├── README.md               # 项目开发与运行文档
│
├── assets/                 # [资源文件]
│   ├── personas/           # 人设与提示词配置
│   │   └── vedal_main.json # 主脑 System Instruction (核心人设、行为准则)
│   ├── world_books/        # 世界书 (Lore/规则) JSON，关键词触发，供组装提示词
│   │   └── *.json         # 如 sex_acts_world_info.json
│   ├── sounds/             # 预置音效 (如"思考中"提示音)
│   └── temp/               # [临时] 存放 TTS 实时生成的音频切片 (自动轮转清理)
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
    │   ├── tools_registry.py # [工具箱] 纯 Python 业务函数库 (代码执行/搜索等)，供 Gemini 自动调用
    │   └── memory.py       # [海马体] 封装 Mem0，负责长期记忆的异步写入与检索
    │
    ├── expression/         # === 表达层 (行为输出) ===
    │   ├── __init__.py
    │   ├── mouth.py        # [发声器官] 文本流接收与 TTS 语音合成
    │   ├── player.py       # [播放器] 异步音频播放队列控制及硬件打断机制
    │   └── body.py         # [物理表征] VTube Studio 协议封装，控制口型同步与面部表情
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
* **执行逻辑**：
1. 初始化所有感官和表达模块的实例。
2. 启动 `asyncio.gather` 监听任务。
3. 协调数据流：`hearing.py` 监听到用户说话 -> 触发 `vision.py` 获取当前屏幕 `PIL.Image` -> 将文本和图像打包发送给 `brain.conscious.py` -> 将生成的文本流管道接入 `expression.mouth.py`。


* **中断处理**：监听用户插嘴事件，一旦检测到新输入，立即调用 `player.interrupt()` 清空播放队列并中断当前生成。


* **`config_loader.py`**
* **核心职责**：单例模式的配置加载器。将 `config.yaml` 的业务配置（如 `vision_interval`, `tts_voice`）和 `.env` 的机密凭证合并为一个全局可访问的配置对象。


* **`logger.py`**
* **核心职责**：提供彩色终端日志输出，区分 `[INFO]`, `[DEBUG]`, `[ERROR]`, `[VISION]`, `[AUDIO]` 等标签，确保异步多线程环境下日志不穿插错乱。



### B. 感官层 (`src/senses/`)

* **`hearing.py` (耳朵)**
* **核心职责**：捕捉外部语音指令并转为文本。
* **实现细节**：集成 WebRTC VAD 或 Silero VAD 进行环境音检测。当音量超过阈值触发录音，检测到持续静音（如 1 秒）则停止录音。将截获的音频块发送至 Whisper API，返回识别出的 `str` 文本。


* **`vision.py` (眼睛)**
* **核心职责**：获取数字生命的视觉输入。
* **实现细节**：基于 `mss` 或 `Pillow.ImageGrab` 抓取主屏幕或特定窗口内容。包含简单的图像差异对比算法（Diff），若画面变化极小则跳过抓取。**直接返回 `PIL.Image` 对象**或字节流，不涉及任何大模型调用。



### C. 大脑层 (`src/brain/`)

* **`conscious.py` (主脑 - Gemini 核心)**
* **核心职责**：处理认知逻辑、记忆融合与决策下发。
* **实现细节**：
1. 实例化 `gemini-3-flash-preview` 模型。
2. 读取 `vedal_main.json` 加载 `system_instruction`。
3. 将 `tools_registry.py` 中的函数列表传入 `tools` 参数，并开启 `enable_automatic_function_calling=True`。
4. 开启自带思考模型特性 (`thinking_config`)。
5. **处理入口**：接收 `(user_text, image_obj)`。先调用 `memory.py` 获取相关长期记忆，将其与用户文本、截图对象共同传入 `ChatSession.send_message_async(stream=True)`。
6. 返回异步文本流生成器。




* **`tools_registry.py` (原生工具箱)**
* **核心职责**：提供供 Gemini 自动调用的扩展能力。
* **实现细节**：包含一系列纯 Python 异步函数（例如 `search_web(query: str)`, `execute_code(script: str)`）。**强制要求**包含严谨的 Type Hints 和详细的 Docstring，因为 Gemini 会直接解析 Docstring 作为 Function Calling 的触发描述。


* **`memory.py` (海马体 - Mem0)**
* **核心职责**：维护长期记忆与人格一致性。
* **实现细节**：封装 Mem0 库。配置使用 OpenAI API 生成 Embedding 并存储在轻量级向量库（如 Qdrant / Chroma 内存版）。提供 `search()` 方法供对话前查询，提供 `add_background()` 异步方法在每次对话结束后提取事实并更新记忆库，确保写入过程不阻塞主回复流。



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