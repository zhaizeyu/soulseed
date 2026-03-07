# Telegram 对接 — 功能与架构设计

基于 **python-telegram-bot**（PTB v21+ 异步）将 Telegram 作为**可插拔客户端**之一接入 VedalAI。核心原则：**核心与客户端解耦、插件化，客户端可随便换**。核心层只提供「按会话（session_id）的对话与记忆」通用能力，不感知 Telegram；Telegram 仅作为插件调用同一套会话 API，并自行管理本端历史与 I/O。

---

## 一、功能设计

### 1. 核心能力

| 功能 | 说明 |
|------|------|
| **文本对话** | 用户发文字 → 主脑流式生成 → 机器人逐句或整段回复（受 Telegram 流式限制，见下） |
| **多用户隔离** | 按 Telegram `chat_id` 隔离：每个会话独立历史、独立 Mem0 user_id，互不串戏 |
| **长期记忆** | 每轮结束后写入 Mem0，`user_id = f"tg_{chat_id}"`，检索时同 id，实现「每个用户有专属记忆」 |
| **命令** | `/start` 欢迎语；`/help` 简要说明；`/clear` 清空当前会话历史（不删 Mem0，仅清上下文窗口） |

### 2. 可选扩展（后续阶段）

| 功能 | 说明 |
|------|------|
| **图片输入** | 用户发照片 → 作为本回合 vision_image 传入主脑（需 conscious 支持多模态，已支持） |
| **语音输入** | 用户发语音 → 先 STT（hearing.speech_to_text 或 Telegram 自带语音识别）→ 再按文本对话 |
| **流式体验** | Telegram 无真正流式 API，可用「先发“正在想…”再编辑同一条消息」或分多条短消息模拟 |

### 3. 行为与限制

- **无眼睛心跳**：Telegram 端不截屏、不触发「画面变化」主动说话。
- **无 TTS 播报**：仅文字回复；若需语音可后续发 Voice 消息（需额外 TTS 合成）。
- **并发**：多用户同时发消息时，主脑按请求顺序或并发处理（建议单进程内顺序或限流，避免 Gemini 限频）。

---

## 二、架构设计（解耦与插件化）

### 1. 原则：核心不认客户端，客户端只认通用 API

- **核心层**只提供「会话级」能力：对任意 `session_id` 做检索、对话、写记忆；**不**依赖 CLI / Web / Telegram 任一具体客户端。
- **历史由客户端自己管**：核心只接收「当前会话历史」入参，不负责持久化；CLI/Web 用单文件、Telegram 用本插件内的按 chat 存储，互不共用、可随便换。
- **记忆隔离**：`memory.search` / `memory.add_background` 接受通用参数 `user_id`（即会话标识）。CLI 可用 `"default"`，Web 可用 `"web"` 或按用户 id，Telegram 用 `"tg_{chat_id}"`。核心不关心字符串含义。
- **Telegram 只是众多客户端之一**：只做两件事——(1) 把 `chat_id` 映射成 `session_id` 并准备好本端历史；(2) 调用与 CLI/Web 同一套会话 API，再把返回内容通过 Telegram 发出去。

### 2. 通用输入对象（核心契约）

- **统一输入**：`UserTurnInput`（`src.brain.turn_input`），字段：`text`、`images`（列表，首张作 vision）、`audio_path`、`metadata`。后续扩展 Telegram 图片/语音、Web 上传文件等只需往该结构填字段，调用方从 `turn_input.effective_text()` 与 `turn_input.images` 取内容再调现有 memory + conscious，无需改函数签名。
- 各客户端（CLI、Web、Telegram）自行：加载历史 → 构建 `UserTurnInput` → `memory.search` + `conscious.chat_stream`（或封装一层）→ 写回历史与 `add_background`。不新增统一「会话层」文件。

### 3. 模块划分（Telegram 仅作插件）

```
src/
├── core/                       # 与现有一致，不依赖任何客户端
├── brain/                      # 与现有一致；memory 支持通用 user_id，不感知 Telegram
├── web/                        # 客户端：Web，使用通用会话 API + 自己的历史存储
├── telegram/                   # 客户端插件：Telegram，使用通用会话 API + 自己的历史存储
│   ├── __init__.py
│   ├── bot.py                  # PTB Application、polling/webhook
│   ├── handlers.py             # /start、/help、/clear、文本（及可选图片/语音）
│   ├── service.py              # 薄封装：取 session_id="tg_{chat_id}"，加载本端历史，
│   │                            # 调通用 run_one_turn，写回本端历史并写记忆，返回回复
│   └── history.py              # 本插件专属：按 chat_id 的会话历史（如 data/telegram/chats/{chat_id}.json）
└── ...
```

- **brain** 中不出现 Telegram；**telegram** 中不出现 Web/CLI 业务逻辑，只做「Telegram I/O + session_id 映射 + 本端历史」。
- **service.py**：从 `history.get(chat_id)` 取历史 → 构建 `UserTurnInput(text=..., images=[...] 若用户发图)` → `memory.search(user_id="tg_"+chat_id)` + `conscious.chat_stream(...)`（与 Web/CLI 相同逻辑）→ 收集回复 → `history.append`、`memory.add_background(..., user_id="tg_"+chat_id)` → 把回复交给 handlers 发回 Telegram。

### 4. 数据流（Telegram 插件内）

```
用户 @Telegram 发消息
    → handlers 收到 Update
    → service：session_id = "tg_{chat_id}"，chat_history = history.get(chat_id)
    → 调用通用 run_one_turn(session_id, text, chat_history, vision_image=None)
    → service：history.append(chat_id, user_msg, reply)，memory.add_background(..., user_id=session_id)
    → handlers 将 reply 发回 Telegram
```

### 5. 与核心的依赖关系（仅「使用」通用能力）

| 依赖 | 说明 |
|------|------|
| config_loader | 读本插件配置与 GEMINI_API_KEY |
| 通用 run_one_turn(session_id, ...) | 与 CLI/Web 共用同一接口，不依赖具体客户端 |
| memory.search / add_background(user_id=session_id) | 仅传会话标识，核心不感知 Telegram |
| conscious.chat_stream | 与现有一致 |
| **不依赖** | chat_history_store、orchestrator、任何 Web 专有逻辑；历史完全在 telegram/history.py |

### 6. 配置项建议

**config.yaml：**

```yaml
# Telegram（可选）
telegram_enabled: false
telegram_max_history_entries: 20   # 每会话保留条数，默认与 chat_history_max_entries 一致
# telegram_chat_history_dir: "data/telegram/chats"  # 可选，默认 data/telegram/chats
```

**.env：**

```
TELEGRAM_BOT_TOKEN=your_bot_token_from_@BotFather
```

- 未配置 `TELEGRAM_BOT_TOKEN` 或 `telegram_enabled: false` 时不启动 Telegram 模块。

---

## 三、入口与运行方式

- **方式 A（推荐）**：独立入口 `python -m src.telegram`，仅启动 Telegram Bot（polling）。与 `main.py`（CLI）、`python -m src.web`（Web）并列，三选一或同时跑不同进程。
- **方式 B**：在 `main.py` 或某统一入口里根据 config 同时起 Web + Telegram（两进程或 asyncio 多任务）。设计上建议先做方式 A，后续再考虑 B。

---

## 四、依赖与安全

- **依赖**：`pip install python-telegram-bot`（建议 ≥21.0，纯异步）。
- **安全**：Bot Token 仅放在 `.env`，不提交仓库；可选白名单（仅允许特定 `user_id` 使用 Bot）在 handlers 内校验。

---

## 五、实现顺序建议

1. **核心已就绪**：`memory.search` / `add_background` 已支持 `user_id`；Web/CLI 每轮使用 **UserTurnInput** 封装入参后调 memory + conscious，无单独「会话层」。
2. **Telegram 插件**：在 `src/telegram/` 内实现 `history.py`（按 chat_id 的 JSON 读写与 clear）→ `service.py`（构建 `UserTurnInput(text=..., images=[...] 若用户发图)`，session_id=`tg_{chat_id}`，与 Web/CLI 相同逻辑：memory.search(user_id=session_id) + conscious.chat_stream，再写本端历史与 add_background(user_id=session_id)）→ `handlers.py`（/start、/help、/clear、文本）→ `bot.py` 与 `__main__.py`；配置仅限本插件（`TELEGRAM_BOT_TOKEN`、`telegram_*`）。
3. **可选**：用户发图时在 handler 中取 `message.photo`，下载后放入 `UserTurnInput(images=[path])`。

按上述顺序实现后，Telegram 与 CLI/Web 并列，客户端可替换、核心保持解耦。

---

## 六、为实现解耦/插件化，原有代码是否需要改？

### 必须改的（最小改动）

| 位置 | 改动 | 原因 |
|------|------|------|
| **memory.py** | `search(query, top_k=5, user_id=None)`、`add_background(..., user_id=None)` 增加可选参数 `user_id`；默认 `None` 时使用现有 `_DEFAULT_USER_ID` | 新客户端（如 Telegram）需要按会话隔离记忆；CLI/Web 不传 `user_id` 时行为与现在完全一致 |

仅此一处**必须**改，其余现有功能（CLI、Web、chat_history_store、conscious、prompt_assembler）**可不改**，照常运行。

### 可不改的

- **Web (service.py)**、**CLI (orchestrator)**：已用 **UserTurnInput** 封装入参，memory 不传 `user_id` 时用默认值；单份历史、chat_history_store 不变。
- **chat_history_store**：继续单文件、单会话，无需动。
- **conscious / prompt_assembler**：已按「入参」工作，不关心调用方是谁，无需动。

Telegram 实现时复用与 Web/CLI 相同的「UserTurnInput → memory.search(user_id) → conscious.chat_stream → 写历史与 add_background(user_id)」流程即可，无需新增统一会话层。
