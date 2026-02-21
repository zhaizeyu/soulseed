# 数字生命 MVP (VedalAI Project)

基于 Gemini 多模态原生架构的数字生命 MVP，详见 [arch.md](arch.md)。

## 目录结构概览

- `main.py` — 程序入口
- `config.yaml` — 全局配置
- `.env` — API 密钥（从 `.env.example` 复制并填写）
- `assets/` — 人设、世界书、音效、TTS 临时文件
- `src/` — 核心 / 感官 / 大脑 / 表达 / 工具 源码

## 快速开始

1. 复制 `.env.example` 为 `.env`，填入 `GEMINI_API_KEY`、`OPENAI_API_KEY`、`VTS_PORT` 等。
2. 安装依赖：`pip install -r requirements.txt`
3. 运行：`python main.py`

## 开发与扩展

- 人设与 System Instruction：编辑 `assets/personas/vedal_main.json`
- 世界书（关键词触发的 Lore/规则，用于组装提示词）：放入 `assets/world_books/*.json`，使用 `src.utils.io_utils.load_world_book` / `list_world_books` / `get_world_book_prompt_snippet` 加载与拼接
- 业务工具（供 Gemini 调用）：在 `src/brain/tools_registry.py` 中注册
- 配置项说明见 `config.yaml` 与 `arch.md`
