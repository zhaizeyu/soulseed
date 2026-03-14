# 使用 Hindsight 作为长期记忆底层 — 设计方案

[Hindsight](https://github.com/vectorize-io/hindsight) 是「Agent Memory That Learns」：支持 **Retain（存储）**、**Recall（检索）**、**Reflect（深度反思）**，内部用语义 + BM25 + 图 + 时间多路检索再重排，LongMemEval 上表现优异。本文档说明在本项目（VedalAI）中如何用 Hindsight 替代或并列 Mem0，实现长期记忆的写入与注入。

---

## 一、与当前 Mem0 的接口对齐

本项目对长期记忆的用法可归纳为两类：

| 能力 | 当前 (Mem0) | 目标 (Hindsight) |
|------|-------------|------------------|
| **检索** | `memory.search(query, top_k, user_id)` → `List[{memory, metadata, score}]` | `recall(bank_id, query)` → 映射为同结构 |
| **写入** | `memory.add_background(user_input, reply_text, metadata, user_id)` | `retain(bank_id, content, context, timestamp)`，metadata 按 Hindsight 能力使用 |

因此设计原则：**在现有调用方（conversation、orchestrator、web、telegram）不改的前提下，通过「记忆后端可插拔」或「Hindsight 适配层」统一接口**。

---

## 二、核心概念映射

| 本项目 | Hindsight |
|--------|------------|
| `user_id`（如 `default`、`tg_8103409829`） | **bank_id**（每用户/每会话一个 memory bank） |
| 每轮对话后写入 | **Retain**：`content` = 本轮对话或摘要，可选 `context`、`timestamp`、`metadata` |
| 每轮请求前按 query 检索 | **Recall**：按 `bank_id` + 当前用户输入（或摘要）检索，返回若干条记忆 |
| 可选「深度回忆」 | **Reflect**：对某问题做基于记忆的生成，可作为 §4 的一条高阶摘要 |

Hindsight 的 [Retain 流程](https://github.com/vectorize-io/hindsight)：内部用 LLM 抽取事实、时间、实体、关系并归一化，形成 World / Experiences / Mental Models 等通路，无需本项目在外部再做一次「事实抽取」；若希望保留现有 metadata（如情绪、重要度），可通过 **metadata** 传入（注意 [metadata 不参与 recall 过滤](https://github.com/vectorize-io/hindsight/discussions/422)，仅作上下文；需过滤时用 **Tags**）。

---

## 三、部署与依赖

### 3.1 两种运行方式

1. **Docker（推荐生产）**  
   - 单独起 Hindsight 服务，本项目通过 HTTP 调用。  
   - 示例（README）：  
     `docker run --rm -it -p 8888:8888 -p 9999:9999 -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY -v $HOME/.hindsight-docker:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest`  
   - API: `http://localhost:8888`，UI: `http://localhost:9999`。  
   - 支持 `HINDSIGHT_API_LLM_PROVIDER=gemini`，可与现有 Gemini 主脑一致。

2. **Python 内嵌（无独立服务）**  
   - `pip install hindsight-all`，在进程内启动 `HindsightServer`（内嵌 PostgreSQL），适合单机/开发。  
   - 代码示例（README）：  
     `with HindsightServer(llm_provider="openai", llm_model="gpt-5-mini", llm_api_key=...) as server: client = HindsightClient(base_url=server.url); ...`

### 3.2 依赖与配置

- **pip**：  
  - 仅客户端：`hindsight-client`（连已有 Hindsight 服务）。  
  - 内嵌全量：`hindsight-all`（自带服务与 DB）。  
- **config.yaml 建议新增**（示例）：  
  - `memory_backend: "mem0" | "hindsight"`：选择长期记忆后端。  
  - `hindsight_base_url: "http://localhost:8888"`：Hindsight API 地址（内嵌时由代码填 server.url）。  
  - `hindsight_llm_provider: "gemini"`、`hindsight_llm_model`、API key：若用内嵌且希望与主脑统一，可复用 `GEMINI_API_KEY`。  
  - `hindsight_recall_max_tokens`（可选）：Recall 返回内容的总 token 上限，与现有「检索条数」语义类似，由 Hindsight 内部做 trim。

---

## 四、接口设计（保持现有调用方不变）

### 4.1 统一入口：仍为 `src/brain/memory.py`

- **方案 A（推荐）**：在 `memory.py` 内根据 `config["memory_backend"]` 分支，  
  - `mem0`：保持现有 Mem0 实现（`search` / `add_background`）；  
  - `hindsight`：内部调用 Hindsight 客户端，实现同一套 `search` / `add_background` 签名。
- **方案 B**：新建 `src/brain/memory_hindsight.py`，实现与当前 `search` / `add_background` 同签名的异步函数；`memory.py` 在 `memory_backend == "hindsight"` 时 `from src.brain.memory_hindsight import search, add_background` 并 re-export。  

两种方式对 **conversation、prompt_assembler、orchestrator、web、telegram** 均透明。

### 4.2 search(query, top_k, user_id) → 用 Recall 实现

- `bank_id` = `user_id`（空则用 `"default"`），与现有一致。  
- 调用 `client.recall(bank_id=bank_id, query=query, ...)`，若 API 支持 `max_tokens` / `limit` 则传入（与 `top_k` 或 config 中的 `hindsight_recall_max_tokens` 对应）。  
- 将 Hindsight 返回的「记忆列表」映射为现有格式：  
  `[{"memory": 文本, "metadata": {...}, "score": 可选}]`  
  若 Hindsight 无 score，可缺省或按顺序赋权。  
- **prompt_assembler** 已按 `mem0_lines` 的 `memory` / `metadata` 渲染 §4，只要结构一致即可复用。

### 4.3 add_background(user_input, reply_text, metadata, user_id) → 用 Retain 实现

- `bank_id` = `user_id`（空则 `"default"`）。  
- **content**：  
  - 若希望 Hindsight 自己做「事实抽取」：传本轮对话，例如  
    `"User: {user_input}\nAssistant: {reply_text}"`（或按 Hindsight 文档推荐的格式）。  
  - 若希望更可控：可先在项目内做一次摘要再 `content=摘要`（与现有 mem0_infer 逻辑二选一或并存）。  
- **context**：可用现有 `time_context`（如「夜晚」「周末」）或简短场景描述。  
- **timestamp**：用当前时间 ISO 字符串，与现有 `timestamp` 一致。  
- **metadata**：传入 `user_emotion`、`ai_emotion`、`importance` 等；检索时 Hindsight 不按 metadata 过滤，但可随记忆返回，供 prompt_assembler 做「带温度」展示。  
- 若需按「会话/人格」过滤，可查阅 Hindsight 的 **Tags** 用法，在 retain 时打 tag，recall 时按 tag 过滤。

---

## 五、Reflect 的用法（可选）

- **Recall**：直接对应「每轮检索若干条记忆注入 §4」。  
- **Reflect**：基于已有记忆做一次「反思/总结」，返回一段生成文本，适合：  
  - 作为 §4 的**一条**高阶记忆（例如「对当前用户，你已知：…」）；  
  - 或用于 Reflection 离线任务（与 [personality_optimization_roadmap.md](personality_optimization_roadmap.md) 中的「记忆坍缩」结合）。  
- 实现上可在「每轮检索」时仅用 **recall**；在「定时 Reflection」或「需要深度总结」时再调 **reflect**，将结果当作一条或数条 `mem0_lines` 注入。

---

## 六、配置示例（config.yaml 片段）

```yaml
# 长期记忆后端：mem0 | hindsight
memory_backend: "hindsight"

# Hindsight（仅当 memory_backend=hindsight 时生效）
hindsight_base_url: "http://localhost:8888"   # Docker 或远程服务
# 内嵌模式时由代码使用 HindsightServer.url，此处可留空或忽略
hindsight_recall_max_tokens: 1024             # 可选，Recall 返回总 token 上限
hindsight_llm_provider: "gemini"              # 内嵌时与主脑统一
hindsight_llm_model: "gemini-2.0-flash"       # 内嵌时
# API Key 复用 .env 的 GEMINI_API_KEY
```

---

## 七、实施步骤建议

1. **依赖与配置**：在 `requirements.txt` 增加 `hindsight-client`（或 `hindsight-all`）；在 `config.yaml` 增加 `memory_backend` 与 `hindsight_*` 项。  
2. **适配层**：在 `memory.py` 或 `memory_hindsight.py` 中实现 Hindsight 版 `search` / `add_background`（bank_id=user_id，retain/recall 映射，返回格式与现有 mem0_lines 一致）。  
3. **分支**：在 `memory.py` 的 `search` / `add_background` 入口根据 `memory_backend` 调用 Mem0 或 Hindsight 实现。  
4. **测试**：用现有 `scripts/inspect_last_prompt.py` 与单轮对话流程验证：写入后能通过 recall 再次注入 §4，且格式正确。  
5. **可选**：Reflection 定时任务中调用 `reflect` 生成高阶摘要并写回或注入，与 roadmap 中的「记忆坍缩」结合。

按上述设计，可在不改动 conversation、prompt_assembler 及三端调用方的前提下，用 [Hindsight](https://github.com/vectorize-io/hindsight) 作为长期记忆底层，并保留与 Mem0 的切换能力。

---

## 八、测试脚本

Hindsight 以 Docker 部署到 `http://localhost:8888` 后，可用项目内脚本验证存取与记忆坍缩：

```bash
pip install hindsight-client
.venv/bin/python scripts/test_hindsight_memory.py
.venv/bin/python scripts/test_hindsight_memory.py --url http://localhost:8888 --bank test_vedal
```

- **Retain**：写入 3 条示例记忆（对话、用户近况、用户偏好）。
- **Recall**：按 query 检索并打印。
- **Reflect**：按 query 做「记忆坍缩」式总结并打印。
- **坍缩写回**：将 Reflect 输出再 retain 为一条高阶记忆。
- `--no-retain`：跳过写入，仅做 recall + reflect（适合已有数据的 bank）。
