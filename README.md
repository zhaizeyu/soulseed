# 数字生命 MVP (VedalAI Project)

基于 Gemini 多模态原生架构的数字生命 MVP，详见 [arch.md](docs/arch.md)。

## 目录结构概览

- `main.py` — 程序入口
- `config.yaml` — 全局配置
- `.env` — API 密钥（从 `.env.example` 复制并填写）
- `assets/` — 人设、世界书、音效、TTS 临时文件
- `src/` — 核心 / 感官 / 大脑 / 表达 / 工具 源码

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 **`GEMINI_API_KEY`**（在 [Google AI Studio](https://aistudio.google.com/apikey) 申请）；主脑与长期记忆（Mem0）均使用该 Key，无需 OpenAI。
2. 安装依赖：`pip install -r requirements.txt`（含 `mem0ai`、`google-genai` 用于长期记忆）。
3. 运行：`python main.py`。第一步为**模拟输入**：终端输入内容回车发送，主脑流式输出；输入 `exit` 或 `quit` 退出。
4. **历史对话**持久化在 `data/chat_history.json`，每次启动加载最近 N 条（见 `config.yaml` 的 `chat_history_max_entries`）。
5. **长期记忆**：配置了 `GEMINI_API_KEY` 后自动启用 Mem0（Gemini 嵌入 + LLM 抽事实），数据落在 `data/mem0/`（`history.db`、`qdrant/`）。每轮结束后会等待写入再进入下一轮；查看已存记忆需先退出主程序，再运行 `python scripts/inspect_mem0_vectors.py`。
6. 运行期日志写入 `logs/vedalai.log`（可在 `config.yaml` 中配置 `log_dir` / `log_file`）。

## 开发与扩展

- **人设与 System Instruction**：编辑 `assets/personas/vedal_main.json`
- **提示词组装**（顺序见 `docs/prompt.md`）：`src.brain.prompt_assembler.build_messages()`，数据来自 `assets/prompts/` 与 persona、**Mem0 检索结果**、历史对话、眼睛与耳朵
- **长期记忆 (Mem0)**：配置见 `config.yaml` 的 `mem0_*` 项。`mem0_infer: true`（默认）为只存 LLM 抽取的事实，`false` 为存助手回复原文；向量库路径默认 `data/mem0/qdrant`。详见 `docs/arch.md` § 大脑层 memory.py
- **世界书**：放入 `assets/world_books/*.json`，使用 `src.utils.io_utils` 的 `load_world_book` / `get_world_book_prompt_snippet` 等
- **业务工具**（供 Gemini 调用）：在 `src/brain/tools_registry.py` 中注册
- **进度与阶段**：见 `docs/development_progress.md`；配置项说明见 `config.yaml` 与 `docs/arch.md`
