# 数字生命 MVP (VedalAI Project)

基于 Gemini 多模态原生架构的数字生命 MVP，详见 [arch.md](docs/arch.md)。

## 目录结构概览

- `main.py` — 程序入口
- `config.yaml` — 全局配置
- `.env` — API 密钥（从 `.env.example` 复制并填写）
- `assets/` — 人设、世界书、音效、TTS 临时文件
- `src/` — 核心 / 感官 / 大脑 / 表达 / 工具 源码

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 `GEMINI_API_KEY`（在 [Google AI Studio](https://aistudio.google.com/apikey) 申请）、`OPENAI_API_KEY`、`VTS_PORT` 等。
2. 安装依赖：`pip install -r requirements.txt`
3. 运行：`python main.py`（第一步为模拟输入：终端输入内容回车发送，主脑流式输出；输入 `exit` 或 `quit` 退出。需配置 `GEMINI_API_KEY` 才有真实回复。）
4. 运行期日志与 API 报错详情写入**日志文件**（默认 `logs/vedalai.log`，可在 `config.yaml` 中配置 `log_dir` / `log_file`）。
5. **历史对话**持久化在 `data/chat_history.json`，每次启动只加载最近 20 条；可在 `config.yaml` 中配置 `chat_history_file`、`chat_history_max_entries`。

## 开发与扩展

- 人设与 System Instruction：编辑 `assets/personas/vedal_main.json`
- 提示词组装（顺序见 `docs/prompt.md`）：`src.brain.prompt_assembler.build_messages()`，数据来自 `assets/prompts/`（jailbreak、task、user_info、prompt_defaults）与 persona、Mem0、历史对话、眼睛与耳朵
- 世界书（关键词触发的 Lore/规则，用于组装提示词）：放入 `assets/world_books/*.json`，使用 `src.utils.io_utils.load_world_book` / `list_world_books` / `get_world_book_prompt_snippet` 加载与拼接
- 业务工具（供 Gemini 调用）：在 `src/brain/tools_registry.py` 中注册
- 配置项说明见 `config.yaml` 与 `docs/arch.md`
