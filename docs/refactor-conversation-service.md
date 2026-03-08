# 单轮对话服务统一方案

目标：把「单轮对话」流水线（Mem0 检索 → 视觉 → 主脑流式 → 写历史 → 写记忆）从三处（orchestrator、web、telegram）抽到一层，三端只调同一套逻辑，便于维护与扩展（含后续多会话 API）。

---

## 实施状态

- **Phase 1：统一单轮流水线** — **已完成**。已新增 `src/brain/conversation.py` 的 `run_one_turn_stream`，orchestrator、Web ConversationService、Telegram `run_turn` 均已改为调用该入口；单轮逻辑只维护一处。
- **Phase 2：多会话与历史抽象** — 未实施（可选）。

---

## 原现状（Phase 1 前）

| 调用方 | 历史存储 | Mem0 user_id | 单轮逻辑位置 |
|--------|----------|--------------|--------------|
| CLI (orchestrator) | `chat_history_store` 单文件 | `"default"` | `orchestrator._run_one_turn` |
| Web | 同上，`ConversationService` | 未传（默认） | `src/web/service.py` |
| Telegram | `telegram/history` 按 chat_id | `tg_{chat_id}` | `src/telegram/service.py` |

三处都重复：mem0 search → 组 vision → `conscious.chat_stream`；差异只在历史来源、mem0 user_id、是否流式输出。

---

## 方案概览

- **Phase 1**：在 brain 层新增「单轮流水线」入口，只负责 **Mem0 + 视觉 + 主脑流式**，不碰历史与记忆的持久化；三端改为调该入口，各自负责「取历史 → 调流水线 → 写历史 → 写记忆」。
- **Phase 2（可选）**：为 Web 提供多会话（如按 `session_id` 隔离历史），通过「历史抽象 + 单会话/多会话实现」完成，不改变 Phase 1 的流水线接口。

---

## Phase 1：统一单轮流水线（brain 层）

### 1.1 新增模块 `src/brain/conversation.py`（已实现）

职责：**仅做「单轮推理」**——输入当前回合 + 已有历史 + 可选视觉，输出主脑流式文本；不读不写任何存储。

已实现接口：

```python
# 类型与常量
from typing import Any, AsyncIterator, Callable, Awaitable

# 可选：默认获取截图的协程（CLI/Web 用）；Telegram 传 None，只用 turn_input.images
GetVisionImage = Callable[[], Awaitable[Any]]


async def run_one_turn_stream(
    turn_input: UserTurnInput,
    chat_history: list[dict[str, str]],
    *,
    persona_name: str = "character",
    user_info: str | None = None,
    mem0_user_id: str = "default",
    vision_image_override: Any = None,
    get_vision_image: GetVisionImage | None = None,
    vision_audio_text: str | None = None,
) -> AsyncIterator[str]:
    """
    单轮对话流水线：Mem0 检索 → 解析本回合视觉 → 主脑流式生成；yield 文本片段。
    不读写历史与记忆，由调用方在迭代结束后自行 append_turns + memory.add_background。
    """
```

逻辑顺序（与现有一致）：

1. `query = turn_input.effective_text()`；若既无文字也无图片，可先 yield 空或由调用方保证不调用。
2. Mem0：`memory.search(query, top_k=config, user_id=mem0_user_id)`，失败则 `mem0_lines=[]`。
3. 视觉：优先 `vision_image_override`，否则若 `get_vision_image` 则 `await get_vision_image()`，否则 `turn_input.images[0]`。
4. `use_defaults_for_missing = (len(chat_history) == 0)`。
5. `async for chunk in conscious.chat_stream(...): yield chunk`。

依赖：`get_config`、`conscious`、`memory`、`UserTurnInput`；不依赖 `chat_history_store`、`telegram`、`web`。

### 1.2 三端改为调用 `run_one_turn_stream`（已实现）

- **Orchestrator**  
  - `_run_one_turn` 内：`chat_history = self._chat_history`，`turn_input = UserTurnInput(...)`，`get_vision_image = self._get_vision_image`。  
  - `async for chunk in run_one_turn_stream(turn_input, chat_history, get_vision_image=get_vision_image, vision_image_override=vision_image_override): ...`  
  - 收集 `full_reply` 后：`append_turns`、裁剪 `self._chat_history`、`memory.add_background(..., user_id="default")`。  
  - 不再内联 mem0/conscious 调用。

- **Web**  
  - `ConversationService.run_one_turn`：内部 `chat_history = self._chat_history`，`turn_input = UserTurnInput(text=user_input, images=[vision_image] if vision_image else None)`。  
  - 调用 `run_one_turn_stream(turn_input, chat_history, get_vision_image=self._get_vision_image, vision_image_override=vision_image_override)`，yield 其产出。  
  - `commit_turn` 与 `memory.add_background` 仍由 server 在流结束后调用，逻辑不变。

- **Telegram**  
  - `run_turn(chat_id, turn_input)`：`chat_history = tg_history.get(chat_id)`，`mem0_user_id = f"tg_{chat_id}"`。  
  - 调用 `run_one_turn_stream(turn_input, chat_history, mem0_user_id=mem0_user_id)`（不传 `get_vision_image`，只用 `turn_input.images`）。  
  - 收集完整回复后：`tg_history.append(chat_id, ...)`、`memory.add_background(..., user_id=mem0_user_id)`。

这样，「和数字生命对话」的规则只维护在 `conversation.run_one_turn_stream` 一处；三端仅负责「历史从哪来、写哪去、mem0 用哪个 user_id」。

### 1.3 可选：`ConversationService` 迁到 brain

若希望「对话服务」与 Web 解耦，便于其他入口（如未来 RPC、脚本）复用：

- 将 `src/web/service.py` 中的 `ConversationService` 迁到 `src/brain/conversation.py`（或 `src/core/conversation_service.py`），依赖「历史加载/追加」的抽象（见下）。
- Web 的 `server.py` 只做 HTTP：收到请求 → 调 `ConversationService.run_one_turn`（内部用 `run_one_turn_stream`）→ 写历史与记忆。

若暂不抽象历史，可保留 `ConversationService` 在 `src/web/service.py`，仅把其内部「单轮逻辑」换成对 `run_one_turn_stream` 的调用，效果相同。

---

## Phase 2（可选）：多会话与历史抽象

目标：Web API 支持 `session_id`，不同会话历史隔离；CLI/Telegram 行为不变。

### 2.1 历史抽象

定义「历史存储」接口（可放在 `src/brain/` 或 `src/core/`）：

```python
# 例如 src/brain/history_store.py
from typing import Protocol

class ChatHistoryStore(Protocol):
    def load(self, session_id: str | None) -> list[dict[str, str]]: ...
    def append(self, session_id: str | None, turns: list[dict[str, str]]) -> None: ...
```

- **单会话实现**（CLI/Web 当前行为）：`session_id` 忽略，读写 `config chat_history_file`，逻辑与现有 `chat_history_store` 一致。
- **多会话实现**（Web 可选）：`session_id` 作 key，后端用目录 `data/sessions/{session_id}.json` 或 Redis 等；无 `session_id` 时退化为默认会话或单文件。

### 2.2 Web API 使用方式

- `POST /api/chat` 请求体增加可选字段 `session_id`。  
- 若提供 `session_id`：用多会话 store 的 `load(session_id)` / `append(session_id, turns)`。  
- 若不提供：用单会话 store（与现有一致）。  
- Mem0 的 `user_id` 可与 `session_id` 对齐（如 `web_{session_id}`），便于按会话隔离长期记忆。

### 2.3 与 Phase 1 的关系

Phase 1 的 `run_one_turn_stream` 只接收 `chat_history: list`，不关心 session。Phase 2 仅在「调用方」层做文章：根据 `session_id` 从对应 store 取 `chat_history`，再调 `run_one_turn_stream`，结束后向同一 store 写回。无需改 brain 流水线接口。

---

## 实施顺序建议

1. 实现 `src/brain/conversation.py` 中的 `run_one_turn_stream`，单元测试可用「假 history + 假 turn_input」只测流水线出口（如 mock conscious）。
2. 依次把 orchestrator、Web ConversationService、Telegram 改为调用 `run_one_turn_stream`，并跑通现有 CLI、Web、Telegram 流程。
3. 若需要多会话，再引入 `ChatHistoryStore` 与多会话实现，并在 Web 层接入 `session_id`。

---

## 小结

- **Phase 1**：brain 层新增 `run_one_turn_stream`，三端只调此入口做「单轮推理」，历史与记忆仍由各端按现有方式读写；单轮逻辑收敛到一处，解耦达标。
- **Phase 2**：通过历史抽象 + `session_id` 支持 Web 多会话，不改变流水线接口，core + brain 的 API 仍可通过「调用 run_one_turn_stream + 某 HistoryStore」实现与数字生命对话。

这样 core + brain 的「对话能力」以 `run_one_turn_stream` 为统一 API，既可被当前 Web/CLI/Telegram 复用，也可被未来其他服务或脚本直接调用。
