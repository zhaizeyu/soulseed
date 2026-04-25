# 数字生命架构（精简版）

本项目当前实现已经统一为：**所有 LLM 调用经 `src/llm_gateway`（LiteLLM + Langfuse）**。

## 1. 核心运行链路

1. 客户端输入（CLI / Web / Telegram）构造成 `UserTurnInput`
2. 调用 `src/brain/conversation.py::run_one_turn_stream`
3. 流水线内部：
   - `memory.search` 检索 Mem0
   - 解析本回合视觉输入（截图或用户附图）
   - `conscious.chat_stream` 调 `llm_gateway.stream_chat` 流式生成
4. 客户端侧写历史 + `memory.add_background` 写长期记忆

## 2. 模块边界

- `src/llm_gateway/`
  - 统一网关调用（聊天、STT、Mem0 配置）
  - 统一 Langfuse callback / trace metadata
- `src/brain/`
  - `prompt_assembler.py`：运行时上下文组装（记忆/历史/环境/用户输入）
  - `conscious.py`：主脑流式调用（不拼提示词）
  - `memory.py`：Mem0 检索与写入（按 `user_id` 隔离）
  - `conversation.py`：单轮流水线（多端共用）
- `src/senses/`
  - `hearing.py`：语音转写，走 `llm_gateway.speech_to_text`
  - `vision.py`：截图与心跳变化检测
- `src/web/`
  - FastAPI API、SSE 流式、Web 心跳任务
- `src/telegram/`
  - PTB bot、命令/文本/语音/图片处理、按 `chat_id` 会话隔离

## 3. 提示词与记忆

- 系统提示词：仅从 Langfuse Prompt Management 拉取（映射文件 `assets/prompts/langfuse_prompts.json`）
- 运行时消息：由 `build_messages()` 组装，包括：
  - `[History Memory]`（Mem0）
  - `[Start Chat]`（历史）
  - `[Vision And Audio]`（时间与视觉规则）
  - 当前用户输入（空输入会自动注入“继续说话”占位）
- Mem0 记忆按 `user_id` 隔离：
  - CLI/Web 默认 `default`
  - Telegram 为 `tg_{chat_id}`

## 4. 当前目录约定（文档相关）

- `README.md`：启动与使用入口
- `docs/arch.md`：本架构概要（当前文件）
- `docs/prompt.md`：提示词机制
- `docs/web.md`：Web 模块
- `docs/telegram.md`：Telegram 模块
- `docs/deploy.md`：部署说明
- `docs/personality_optimization_roadmap.md`：后续人格优化路线（规划文档）

其余历史方案文档已删除，避免与现状冲突。