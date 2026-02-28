# 数字生命 MVP — 开发进度与后续阶段

## 一、当前已完成（✅）

### 1. 基础设施
| 模块 | 状态 | 说明 |
|------|------|------|
| 目录结构 | ✅ | 按 arch 搭建，assets / src 分层清晰 |
| config_loader | ✅ | .env + config.yaml 单例加载 |
| logger | ✅ | 控制台 + 文件（logs），路径可配置 |
| 文档 | ✅ | docs/（arch、prompt、示例 JSON） |

### 2. 大脑层（主脑 + 提示词 + 历史）
| 模块 | 状态 | 说明 |
|------|------|------|
| prompt_assembler | ✅ | §1–§8 全在此组装，主脑不注入；§6 截图/耳朵，§7 无输入时「继续说话」占位；vision_audio_text 占位 |
| conscious | ✅ | 仅把组装好的 current_user_content + 可选 vision_image 送 Gemini 流式，不注入任何提示词 |
| chat_history_store | ✅ | JSON 持久化、每次加载最近 N 条、配置化路径与条数 |
| memory | ✅ | Mem0：Gemini embedder+LLM，Qdrant；search 在 query 空时直接返回 []（避免 400）；add_background 已接；mem0_infer 可配置；Invalid JSON 日志已过滤 |
| tools_registry | ⏳ 占位 | 未实现业务工具，未接入 conscious |

### 3. 调度与主循环（第一步闭环 + 记忆）
| 模块 | 状态 | 说明 |
|------|------|------|
| orchestrator | ✅ 部分 | 模拟输入（**直接回车也执行一轮，继续说话**）→ memory.search（空 query 不调 Mem0）→ 截屏 → 主脑流式 → 控制台；每轮后 await add_background；未接 hearing/mouth/player/body |
| main.py | ✅ | 入口，asyncio 跑 orchestrator.run() |

### 4. 感官层
| 模块 | 状态 | 说明 |
|------|------|------|
| vision | ✅ | capture_screen() + get_screen_for_turn()（config：vision_enabled、vision_max_longer_side）；**已接入** orchestrator，每轮截屏以 vision_image 传入主脑多模态 |
| hearing | ⏳ 占位 | 无 VAD、录音、Whisper |

### 5. 表达层
| 模块 | 状态 | 说明 |
|------|------|------|
| mouth | ⏳ 占位 | 未按句 TTS、未入队 |
| player | ⏳ 占位 | 无播放队列、interrupt、RMS 送 body |
| body | ⏳ 占位 | 无 pyvts、口型、表情 |

### 6. 工具与资源
| 模块 | 状态 | 说明 |
|------|------|------|
| io_utils | ✅ 部分 | 人设/世界书加载、load_persona、get_world_book_prompt_snippet；图片压缩/音频未做 |
| api_client | ⏳ 占位 | 未实现 aiohttp 封装 |
| assets | ✅ | personas、prompts、world_books、sounds、temp 就绪 |

### 7. Web 模块 — ✅ 已完成
| 模块 | 状态 | 说明 |
|------|------|------|
| src/web | ✅ | service.py 单轮对话封装，与 CLI 共用 chat_history_store；server.py FastAPI：GET /api/history、POST /api/chat（SSE）、POST /api/chat/sync；空输入=继续说话 |
| webapp | ✅ | Vite + React + TypeScript + Tailwind + shadcn/ui 风格；深色主题、输入框贴底、空输入可发送；format-content.ts 解析心理/说的话/场景、反引号高亮 |
| scripts | ✅ | start_web.sh、stop_web.sh 一键起停；前端 5173，后端 8765 |

---

## 二、后续开发阶段建议

### 阶段 2：记忆（Mem0）— ✅ 已完成
- **memory.py**：已集成 Mem0，embedder 与 LLM 均用 Gemini（不依赖 OpenAI）；实现 `search(query, top_k)`、`add_background(user_input, reply_text)`；缺 key 或缺库时降级。
- **orchestrator**：每轮前 `_mem0_lines = await memory.search(用户输入)` 传入主脑；每轮后 `await memory.add_background(user_input, reply_text)` 并等待落盘。
- **config.yaml**：已增加 `mem0_embedder_model`、`mem0_llm_model`、`mem0_search_limit`、`mem0_embedding_dims`、`mem0_llm_temperature`、`mem0_infer`、可选 `mem0_vector_store_path`。数据目录为 `data/mem0/`（含 history.db、qdrant/）。查看向量库内容：先退出主程序，再运行 `python scripts/inspect_mem0_vectors.py`。

### 阶段 3：耳朵（语音输入）
- **hearing.py**：VAD（WebRTC VAD 或 Silero）+ 录音，静音检测结束送 Whisper（或本地 STT）得到文本。
- **orchestrator**：用 `hearing` 的语音流/事件替代 `input()`，得到用户文本后仍走现有 `_run_one_turn`；支持「插嘴」时调用 `player.interrupt()`（若已实现播放）。

### 阶段 4：嘴 + 播放器（语音输出）
- **mouth.py**：消费主脑文本流，按句切分，调用 Edge-TTS / FishAudio 等生成音频，路径入队。
- **player.py**：异步消费队列、播放音频、播放完清理 `assets/temp/`；暴露 `interrupt()`；可选将 RMS 推给 body。
- **orchestrator**：主脑流式输出不再直接 `print`，改为接入 `mouth.consume_text_stream(stream)`（或等价接口）。

### 阶段 5：眼睛接入与视听摘要 — ✅ 已完成（多模态截图）
- **vision**：`get_screen_for_turn()` 按 config 截屏、缩放、可选存 `data/vision/`。
- **orchestrator**：每轮取截图传入主脑；**直接回车**也执行一轮（继续说话）。
- **prompt_assembler**：§6 在 `vision_image_attached` 时插入「本回合附屏幕截图…」说明；**所有提示词仅在此组装**，conscious 不注入。
- **conscious**：仅发送组装好的 current_user_content + 可选 vision_image。

### 阶段 6：身体（VTube Studio）
- **body.py**：pyvts 连接 VTS，接收 player 的 RMS/音量，映射 MouthOpen；主脑输出情感标签触发表情热键。
- **orchestrator**：播放时把音量/RMS 推给 body；可选在 conscious 输出里解析情感标签并通知 body。

### 阶段 7：工具箱与主脑增强
- **tools_registry.py**：实现若干工具（如 search_web、execute_code），带类型与 docstring，转为 Gemini Function Calling 格式。
- **conscious**：将 tools 注册到 Gemini，开启自动调用；按需做 io_utils 的图片压缩（如先压缩再送 API）。

### 阶段 8：调度整合与稳定性
- 用 **asyncio.gather** 同时跑：语音监听、视觉定时采样、主脑流式、TTS 入队、播放、VTS 更新。
- 统一**插嘴**逻辑：新语音触发时 interrupt + 重新组 prompt 并请求主脑。
- 错误重试、超时、日志标签（如 [AUDIO]、[VISION]）完善；可选 api_client 统一 HTTP。

### 建议补充：prompt_assembler 格式规则 (§7.5)
- 在 §8 输出风格限制之前插入 **格式规则** 提示词，约束模型输出格式：
  - 场景：`*场景*`
  - 心理：`(心理)`
  - 语言：直接输出
  - 【绝对格式铁律】：禁止嵌套；动作和心理描写必须独立成句，不能夹杂在语言中间。
- 若采用 `*...*` 作为场景标记，需在 `webapp/src/lib/format-content.ts` 中增加对应解析，前端用白色渲染。

---

## 三、推荐推进顺序

1. **阶段 2（记忆）** — 提升对话连贯与人设一致性。  
2. **阶段 4（嘴 + 播放器）** — 先实现「文字→语音播放」与 interrupt，再接耳朵更自然。  
3. **阶段 3（耳朵）** — 语音输入替代打字，并与阶段 4 的 interrupt 联动。  
4. **阶段 5（眼睛接入）** — 为多模态/环境感知打基础。  
5. **阶段 6（身体）** — 口型与表情，依赖阶段 4 的播放与音量。  
6. **阶段 7（工具箱）** — 按产品需求决定优先级。  
7. **阶段 8（调度整合）** — 全链路并联与稳定性收尾。

当前可运行链路：**模拟输入（直接回车=继续说话）→ Mem0 检索（空 query 不调）→ 每轮截屏（可选）→ 提示词全在 assembler 组装 → Gemini 多模态流式 → 控制台 + 历史 + 长期记忆写入**；耳朵/嘴/播放器/身体未接入。
