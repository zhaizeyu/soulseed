# Telegram 模块说明（精简版）

Telegram 是与 CLI / Web 并列的客户端入口，走同一套核心流水线。

## 1. 核心能力

- 文本消息：直接进入单轮流水线
- 语音消息：`hearing.speech_to_text` 转写后再进入流水线
- 图片消息：压缩后作为 `UserTurnInput.images` 进入流水线
- 命令：`/start`、`/help`、`/clear`
- 多用户隔离：按 `chat_id` 对应 `mem0_user_id=tg_{chat_id}`

## 2. 关键数据流

1. `handlers.py` 接收 Telegram 消息
2. 构造 `UserTurnInput`
3. 调 `service.run_turn`
4. `service` 调 `brain.conversation.run_one_turn_stream(..., mem0_user_id=f"tg_{chat_id}")`
5. 收集回复后写入：
   - `telegram/history.py`（本端历史）
   - `memory.add_background(..., user_id=f"tg_{chat_id}")`（长期记忆）

## 3. 目录职责

- `src/telegram/bot.py`：PTB Application 与 polling 启动
- `src/telegram/handlers.py`：命令、文本、语音、图片入口
- `src/telegram/service.py`：单轮对话编排与记忆写入
- `src/telegram/history.py`：按 `chat_id` 的历史持久化
- `src/telegram/format_reply.py`：回复格式化为 Telegram HTML

## 4. 配置

`.env`：

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
```

`config.yaml`（可选）：

```yaml
telegram_enabled: true
telegram_max_history_entries: 20
# telegram_speaker_name: "Kurisu"
# telegram_chat_history_dir: "data/telegram/chats"
```

## 5. 运行

```bash
python -m src.telegram
```

未配置 `TELEGRAM_BOT_TOKEN` 或 `telegram_enabled=false` 时不启动。
