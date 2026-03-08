# Telegram 对接 — 功能与架构设计

基于 **python-telegram-bot**（PTB v21+ 异步）将 Telegram 作为**可插拔客户端**之一接入 VedalAI。核心原则：**核心与客户端解耦、插件化，客户端可随便换**。核心层只提供「按会话（session_id）的对话与记忆」通用能力，不感知 Telegram；Telegram 仅作为插件调用同一套会话 API，并自行管理本端历史与 I/O。

---

## 一、功能设计

### 1. 核心能力

| 功能 | 说明 |
|------|------|
| **文本对话** | 用户发文字 → 主脑流式生成 → 机器人逐句或整段回复（受 Telegram 流式限制，见下） |
| **语音消息** | 用户发语音 → Bot 下载音频 → **hearing.speech_to_text** 转成文字 → 该文字作为**用户说的话**，与文本消息走同一套流程（Mem0 检索 + 主脑生成 + 写历史与记忆） |
| **图片输入** | 用户发照片 → 下载后经 **vision.prepare_image_for_turn** 压缩（与眼睛同配置），作为本回合 vision 传入主脑 |
| **多用户隔离** | 按 Telegram `chat_id` 隔离：每个会话独立历史、独立 Mem0 user_id，互不串戏 |
| **长期记忆** | 每轮结束后写入 Mem0，`user_id = f"tg_{chat_id}"`，检索时同 id，实现「每个用户有专属记忆」 |
| **命令** | `/start` 欢迎语；`/help` 简要说明；`/clear` 清空当前会话历史（不删 Mem0，仅清上下文窗口） |
| **回复渲染** | 发送前将助手回复转为 Telegram HTML：**语言** `<b>角色名："内容"</b>`（角色名由 config `telegram_speaker_name` 指定，默认 Kurisu）、**心理** `<i>…</i>`、场景纯文本 |

### 2. 可选扩展（后续阶段）

| 功能 | 说明 |
|------|------|
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
│   ├── bot.py                  # PTB Application、polling
│   ├── handlers.py             # /start、/help、/clear、文本/语音/图片
│   ├── service.py              # 薄封装：session_id="tg_{chat_id}"，history.get → memory + conscious → history.append + add_background
│   ├── history.py              # 按 chat_id 会话历史（data/telegram/chats/{chat_id}.json），全量存、读最近 N 条
│   └── format_reply.py         # 回复转 Telegram HTML（语言加粗、心理斜体）
└── ...
```

- **brain** 中不出现 Telegram；**telegram** 中不出现 Web/CLI 业务逻辑，只做「Telegram I/O + session_id 映射 + 本端历史」。
- **service.py**：从 `history.get(chat_id)` 取历史 → 构建 `UserTurnInput(text=..., images=[...] 若用户发图)`；**若本回合是语音消息**，则先将语音文件下载为 bytes，调 **hearing.speech_to_text(audio_bytes, filename)** 得到文字，再设 `UserTurnInput(text=转写结果)`。之后与文本消息同一套：`memory.search(user_id="tg_"+chat_id)` + `conscious.chat_stream(...)` → 收集回复 → `history.append`、`memory.add_background(..., user_id="tg_"+chat_id)` → 把回复交给 handlers 发回 Telegram。

### 4. 数据流（Telegram 插件内）

- **文本消息**：用户发文字 → handlers → service 用 `UserTurnInput(text=消息)` + `history.get(chat_id)` → `memory.search` + `conscious.chat_stream` → 收集回复 → `history.append`、`memory.add_background` → handlers 发回 reply。
- **语音消息**：用户发语音 → handlers 用 `bot.get_file(voice.file_id)` 下载音频为 bytes → **hearing.speech_to_text(audio_bytes, "voice.ogg")** 得到「用户说的话」→ service 用 `UserTurnInput(text=转写结果)`，其后与文本消息**完全同一套**（history.get → memory.search → conscious.chat_stream → history.append + add_background → 发回 reply）。
- **图片消息**：用户发图 → handlers 取最大尺寸、下载为 bytes → PIL 打开后 **vision.prepare_image_for_turn(img, save=True)** 压缩并可选存 data/vision → `UserTurnInput(text=caption 或占位, images=[img])` → service 同上。

**会话历史**：`history.py` 全量写入 `data/telegram/chats/{chat_id}.json`，读取时只取最近 `telegram_max_history_entries` 条作为上下文发给主脑，与 Web/CLI 的 chat_history 逻辑一致。

**回复 HTML**：`format_reply.py` 按场景/心理/说的话分段（规则与 Web 端 format-content 一致），转为 Telegram 可用的 HTML：说的话 → `<b>角色名："内容"</b>`，心理 → `<i>内容</i>`，场景 → 仅转义。角色名来自 config `telegram_speaker_name`（默认 Kurisu）。发送时 `parse_mode="HTML"`，失败则回退纯文本。

### 5. 与核心的依赖关系（仅「使用」通用能力）

| 依赖 | 说明 |
|------|------|
| config_loader | 读本插件配置与 GEMINI_API_KEY |
| hearing.speech_to_text(audio_bytes, filename) | 语音消息转文字，与 Web 端 STT 共用（Gemini 多模态），转写结果作为用户说的话 |
| memory.search / add_background(user_id=session_id) | 仅传会话标识，核心不感知 Telegram |
| conscious.chat_stream | 与现有一致 |
| **不依赖** | chat_history_store、orchestrator、任何 Web 专有逻辑；历史完全在 telegram/history.py |

### 6. 配置项建议

**config.yaml：**

```yaml
# Telegram（可选）
telegram_enabled: false
telegram_max_history_entries: 20   # 每会话：磁盘全量保存；发给主脑的上下文只取最近 N 条
# telegram_speaker_name: "Kurisu"  # 回复中「说的话」前的角色名，不填默认 Kurisu；可改为 "牧濑红莉栖" 等
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

---

## 七、开发步骤（推荐顺序）

按下面顺序实现，可先跑通「文本对话 + 多用户隔离」，再补命令与可选功能。

| 步骤 | 做什么 | 产出 |
|------|--------|------|
| **1. 依赖与配置** | `pip install python-telegram-bot`；在 `.env` 增加 `TELEGRAM_BOT_TOKEN`；在 `config.yaml` 增加 `telegram_enabled`、`telegram_max_history_entries`（及可选 `telegram_chat_history_dir`）。 | 环境就绪，未写代码 |
| **2. history.py** | 实现按 `chat_id` 的会话历史：`get(chat_id) -> list[dict]`、`append(chat_id, user_content, assistant_content)`、`clear(chat_id)`；存储路径如 `data/telegram/chats/{chat_id}.json`，格式与现有 `chat_history.json` 一致，只保留最近 N 条（config）。 | 可单独测：读/写/清空某 chat 历史 |
| **3. service.py** | 实现「单轮对话」：入参 `chat_id`、用户文本（及可选图片）；`session_id = f"tg_{chat_id}"`；`chat_history = history.get(chat_id)`；构建 `UserTurnInput(text=..., images=[...])`；`mem0_lines = await memory.search(query, user_id=session_id)`；`async for chunk in conscious.chat_stream(..., chat_history=chat_history, mem0_lines=mem0_lines, vision_image=...)` 收集 `full_reply`；`history.append(chat_id, user_text, full_reply)`；`await memory.add_background(..., user_id=session_id)`；返回 `full_reply`。 | 给定 chat_id + 文本，能拿回助手回复字符串 |
| **4. handlers.py** | 注册命令与消息：`/start`、`/help`、`/clear`（同上）；**文本消息** → 调 service 取回复并 `send_message`；**语音消息** → 见步骤 4b。 | 在 Telegram 里能和 Bot 文本对话、清空历史 |
| **4b. 语音消息处理** | 在 handlers 中处理 `message.voice`：用 `context.bot.get_file(message.voice.file_id)` 下载音频到内存（bytes）；调用 **`hearing.speech_to_text(audio_bytes, "voice.ogg")`**（Telegram 语音多为 ogg）；将返回的文本作为**用户说的话**，构建 `UserTurnInput(text=转写结果)` 再调 service，回复发回用户。若转写为空可回复「没听清，再说一次吧」。 | 用户发语音 → 转成文字 → 与发文字等价，大模型按「用户说的话」回复 |
| **5. bot.py** | 从 config/环境读 `TELEGRAM_BOT_TOKEN`，校验 `telegram_enabled`；构建 PTB `Application`，注册 `handlers`；提供 `run_polling()`（或 `run_webhook()`）。 | 能 `python -m src.telegram` 启动 Bot |
| **6. __main__.py** | `if __name__ == "__main__"` 中调用 `bot.run_polling()`，并做 asyncio 启动。 | 独立入口可运行 |
| **7. 可选：图片** | 在 handlers 中处理 `message.photo`：下载到临时文件，构建 `UserTurnInput(text=..., images=[path])`，再调 service；回复后删除临时文件。 | 用户发图也能进主脑多模态 |
| **8. 可选：流式体验** | 先发「正在想…」，再在循环中收 `conscious.chat_stream` 的 chunk，累积到一定长度或遇到句号时 `bot.edit_message_text` 更新同一条消息，最后一次编辑成完整回复。 | 近似流式效果 |

**验收**：同一 Telegram 账号在多端或不同群组/私聊中，`chat_id` 不同，历史与 Mem0 互不干扰；`/clear` 只清当前会话历史，Mem0 中该 user_id 的记忆仍在。
