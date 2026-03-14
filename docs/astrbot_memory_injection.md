# AstrBot 记忆库与提示词注入可行性

结论：**可以**。在 AstrBot 中通过插件可以自由增加一个记忆库，并在 LLM 请求前把检索到的记忆注入到提示词中，实现与本项目（VedalAI）类似的「长期记忆插入」效果。

---

## 1. 机制概览

### 1.1 插件在 LLM 请求前的钩子

AstrBot 提供 **`on_req_llm`** 钩子，在请求发往 LLM **之前**执行，可修改本次请求内容：

- **钩子签名**（插件内实现即可被框架调用）：
  ```text
  async def on_req_llm(self, event: AstrMessageEvent, req: ProviderRequest)
  ```
- **`ProviderRequest` 可修改字段**（见 [PR #1963](https://github.com/AstrBotDevs/AstrBot/pull/1963) 等）：
  - `prompt`：用户当轮输入 / 主提示
  - `system_prompt`：系统提示词
  - `contexts`：上下文消息列表（历史等）
  - `tool_calls_result`：工具调用结果（多轮工具调用时使用）

插件在 `on_req_llm` 里对 `req` 做修改即可，**不应**在钩子里直接给用户发消息。

### 1.2 记忆注入的等价实现

与本项目「Mem0 检索 → prompt_assembler 组装进 §4 → 发给模型」的流程对应到 AstrBot，可以这样做：

| 步骤           | 本项目 (VedalAI)              | AstrBot 插件做法                                      |
|----------------|-------------------------------|--------------------------------------------------------|
| 会话标识       | `session_id` / `user_id`      | `event.unified_msg_origin`（或按人格/会话配置取 scope） |
| 记忆存储       | Mem0 + Qdrant                 | 插件自建任意存储（SQLite/向量/文件等）                 |
| 检索           | `memory.search(query, user_id)` | 在 `on_req_llm` 内用当前 `prompt`/`contexts` 做 query 检索 |
| 注入位置       | §4 潜意识记忆 (system)        | 修改 `req.system_prompt` 或向 `req.contexts` 插入一条   |
| 写入记忆       | 对话后 `add_background`       | 在 `on_resp_llm`（或等价响应钩子）里把本轮对话写入自建库 |

因此：**在 AstrBot 里增加一个自有记忆库，并在 `on_req_llm` 中把检索结果拼进 `system_prompt` 或 `contexts`，就能实现与本项目类似的长期记忆插入效果。**

---

## 2. 现有插件如何做

- **Angel Memory**（[astrbot_plugin_angel_memory](https://github.com/kawayiYokami/astrbot_plugin_angel_memory)）：自建三层检索（BM25 + 向量 + 重排）、灵魂状态、睡眠巩固等；在**潜意识层**做检索与整理，再注入到 LLM 的上下文中（依赖 Angel Heart 的聊天记录等）。  
  说明：AstrBot 上已经可以通过插件实现「自有记忆库 + 注入到提示/上下文」。
- **astrbot_plugin_simple_injections**：通过 `on_req_llm` 修改请求，实现按轮次的提示词注入，可作为「在请求前改 `req`」的简单参考。
- **astrbot_plugin_group_context**：在 `on_req_llm` 中处理群聊历史，增强 `req` 的上下文，与「向上下文注入内容」同属一类用法。
- **Memos 集成 / Mnemosyne** 等：外部记忆服务 + 在请求前拉取并注入，思路一致（只是记忆库在插件外部）。

---

## 3. 实现时注意点

- **会话/用户隔离**：用 `event.unified_msg_origin`（及人格名、会话 ID 等）区分不同用户/会话，再按此 key 做检索与写入，避免记忆串会话。
- **注入方式**：  
  - 拼进 **`req.system_prompt`**：适合「背景知识 / 长期记忆」类内容（类似本项目的 §4）。  
  - 或插入 **`req.contexts`**：适合作为一条或多条「记忆摘要」消息，与历史对话一起送模型。
- **持久化位置**：AstrBot 建议插件把持久化数据放在 `data` 目录，而不是插件自己的目录，避免更新/重装时丢失。
- **异步与性能**：`on_req_llm` 中若有网络或 IO（如向量检索），应用异步接口，避免阻塞主流程；Angel Memory 等插件也是在请求前异步做检索再注入。
- **缓存与污染**：若在钩子里缓存了原始 prompt/contexts，需在响应路径或超时情况下做好清理，避免长期占用或误用旧数据（见 [memos_integrator 的 memory leak 讨论](https://github.com/AstrBotDevs/AstrBot/issues/4009)）。

---

## 4. 小结

| 问题                             | 结论 |
|----------------------------------|------|
| AstrBot 能否自由增加一个记忆库？ | 能，插件内自建存储（DB/向量/文件）即可。 |
| 能否把记忆插入到提示词中？       | 能，在 `on_req_llm` 中修改 `req.system_prompt` 或 `req.contexts`。 |
| 能否实现本项目式的长期记忆效果？ | 能，检索 → 格式化为文本 → 注入 system_prompt/contexts，等价于本项目的 Mem0 → §4 注入。 |

参考：AstrBot 插件开发 [Plugin Development Guide](https://docs.astrbot.app/en/dev/star/plugin-new.html)、[AI 接口与对话管理](https://docs.astrbot.app/dev/star/guides/ai.html)；记忆/注入相关插件见 [simple_injections](https://github.com/AstrBotDevs/AstrBot/issues/4862)、[group_context](https://github.com/AstrBotDevs/AstrBot/issues/4021)、[Angel Memory](https://github.com/kawayiYokami/astrbot_plugin_angel_memory)。
