# 提示词机制

## 1) 系统提示词（仅 Langfuse）

系统提示词作为 `system_instruction` 注入，**只**从 Langfuse Prompt Management 拉取。

- 映射文件：**`assets/prompts/langfuse_prompts.json`**（逻辑 key → 字符串或 `{"name","label","type"}`）。
- 默认使用 key **`system`**，可用环境变量 **`LANGFUSE_PROMPT_MAP_KEY`** 指定其它 key。
- 实现：`src/llm_gateway/prompt_mapping.py`、`src/llm_gateway/langfuse_prompt.py`；组装侧入口：`src/brain/prompt_assembler.py` 的 **`load_system_prompt()`**。
- 需配置 **`LANGFUSE_PUBLIC_KEY`**、**`LANGFUSE_SECRET_KEY`**、**`LANGFUSE_BASE_URL`**（或 `LANGFUSE_HOST`）。可用 **`LANGFUSE_SYSTEM_PROMPT_ENABLED=false`** 关闭拉取（关闭后系统提示词为空，主脑会报错提示）。

若 Langfuse 模板含必填变量，当前以无参 `compile()` 为主；需传参时可在后续版本扩展。

## 2) 运行时上下文（messages）

`src/brain/prompt_assembler.py` 的 **`build_messages()`** 仅组装运行时上下文：

- `[History Memory]`：Mem0 检索结果（可带情绪/时间/重要度元数据）
- `[Start Chat]`：历史对话滑窗（用户历史图像会附 `[图: 时间]` 标记）
- `[Vision And Audio]`：当前时间 + 本回合视觉规则 + 可选耳朵转写
- 当前回合 `user` 输入（空输入时自动注入“继续说话”占位）

## 3) 注入路径

`src/brain/conscious.py` 合并：

- `messages`：`build_messages(...)`
- `system_instruction`：`load_system_prompt()`

底层调用统一走 **`src/llm_gateway`**（LiteLLM + Langfuse）。
