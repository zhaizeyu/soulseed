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
| turn_input | ✅ | UserTurnInput(text/images/audio_path/metadata)，单轮用户输入统一对象；Web/Orchestrator 先封装再调 memory + conscious，后续扩展不改签名 |
| prompt_assembler | ✅ | §1–§8 全在此组装，主脑不注入；§4 记忆带 timestamp/time_context/情绪/重要度格式化；§6 截图/耳朵，§7 无输入时「继续说话」占位 |
| conscious | ✅ | 使用 **google-genai** 流式生成；组装好的 current_user_content + 可选 vision_image（PIL→JPEG bytes）送 Gemini；config 支持 gemini_max_output_tokens 控制输出长度 |
| chat_history_store | ✅ | JSON 持久化、每次加载最近 N 条、配置化路径与条数 |
| memory | ✅ | Mem0：search/add_background 支持 user_id 多端隔离；metadata（情绪、重要度等）+ timestamp/time_context；inspect_mem0_vectors.py 可查看完整元数据 |
| tools_registry | ⏳ 占位 | 未实现业务工具，未接入 conscious |

### 3. 调度与主循环（第一步闭环 + 记忆）
| 模块 | 状态 | 说明 |
|------|------|------|
| orchestrator | ✅ 部分 | 每轮封装 **UserTurnInput** → memory.search(user_id=default) + 截屏/首图 → conscious 流式 → 控制台；每轮后 append 历史、await add_background；CLI 端未接 hearing/player/body（嘴巴 TTS 已在 Web 端独立实现） |
| main.py | ✅ | 入口，asyncio 跑 orchestrator.run() |

### 4. 感官层
| 模块 | 状态 | 说明 |
|------|------|------|
| vision | ✅ | capture_screen() + get_screen_for_turn()；**心跳检测**：每 N 秒（如 30）截图与上一帧缩略图对比，差异超阈值则触发主动说话（check_heartbeat）；已接入 orchestrator 队列 |
| hearing | ✅ 部分 | 使用 **google-genai** 多模态转写；Web `POST /api/speech-to-text`、Telegram 语音消息均调用；与主脑共用 GEMINI_API_KEY；CLI 端 VAD+录音未接 |

### 5. 表达层
| 模块 | 状态 | 说明 |
|------|------|------|
| mouth | ✅ | 嘴巴（TTS）已可用：Edge-TTS 合成，Web 端 `tts_reply_enabled` 开启后流式结束自动播报「说的话」；CLI 端未接、未与 player 联动 |
| player | ⏳ 占位 | 无播放队列、interrupt、RMS 送 body（与 mouth 联动后用于 CLI 端播放与口型） |
| body | ⏳ 占位 | 后端计算口型/表情参数并推送给 Web 前端；前端用 Cubism Web SDK 渲染 Live2D |

### 6. 工具与资源
| 模块 | 状态 | 说明 |
|------|------|------|
| io_utils | ✅ 部分 | 人设/世界书加载、load_persona、get_world_book_prompt_snippet；图片压缩/音频未做 |
| api_client | ⏳ 占位 | 未实现 aiohttp 封装 |
| assets | ✅ | personas、prompts、world_books、sounds、temp 就绪 |

### 7. Web 模块 — ✅ 已完成
| 模块 | 状态 | 说明 |
|------|------|------|
| src/web | ✅ | service.py 单轮对话封装，与 CLI 共用 chat_history_store；server.py：GET /api/history、GET /api/config、POST /api/chat（SSE）、POST /api/chat/sync、POST /api/speech-to-text、**POST /api/tts**（TTS）；Web 心跳 + 日志 |
| webapp | ✅ | 深色主题、输入框贴底、空输入可发送；麦克风语音输入；流式结束后按 **tts_reply_enabled** 自动播报「说的话」；format-content 心理/说的话/场景、反引号高亮；**双引号内字数少于 5 按场景文字渲染**；轮询 /api/history |
| scripts | ✅ | start_web.sh、stop_web.sh 一键起停；前端 5173，后端 8765 |

### 8. Telegram 模块 — ✅ 已完成
| 模块 | 状态 | 说明 |
|------|------|------|
| src/telegram | ✅ | 独立入口 `python -m src.telegram`；handlers：/start、/help、/clear、文本、语音（STT）、图片（vision 压缩）；service 按 chat_id 调 memory + conscious，user_id=tg_{chat_id}；history 全量存盘、读取最近 N 条；format_reply 将回复转为 Telegram HTML（语言 `<b>角色名："内容"</b>`、心理 `<i>…</i>`）；config：telegram_enabled、telegram_max_history_entries、telegram_speaker_name。 |

---

## 二、后续开发阶段建议

### 阶段 2：记忆（Mem0）— ✅ 已完成
- **memory.py**：已集成 Mem0，embedder 与 LLM 均用 **Google Gemini**；实现 `search(query, top_k)` 返回 `List[Dict]`（含 memory、metadata、score）、`add_background(user_input, reply_text, metadata=None)`；支持**记忆元数据**（user_emotion、ai_emotion、importance、memory_type 等），写入时自动附加 timestamp、time_context；缺 key 或缺库时降级。
- **orchestrator / web**：每轮将入参封装为 **UserTurnInput**，用 `effective_text()` 做 memory.search、首图做 vision，再调 conscious；每轮后 `add_background(..., user_id=...)` 并等待落盘（metadata 可接入情绪识别，当前可传 None）。
- **prompt_assembler**：§4 潜意识记忆接收带 metadata 的 mem0_lines，按情绪/时间/重要度格式化后注入（带温度前缀与「重要记忆」后缀）。
- **config.yaml**：已增加 `mem0_*` 等项。数据目录为 `data/mem0/`（含 history.db、qdrant/）。查看向量库及元数据：先退出主程序，再运行 `python scripts/inspect_mem0_vectors.py`。

### 阶段 3：耳朵（语音输入）— ✅ Web 已接
- **hearing.py**：`speech_to_text(audio_bytes, filename)` 使用 **Google Gemini** 多模态做语音转写，供 Web `POST /api/speech-to-text` 使用；与主脑共用 GEMINI_API_KEY 与 gemini_model，未配置时跳过并打日志。
- **mouth.py**：`text_to_speech_async(text)` 使用 **Edge-TTS** 合成 mp3，供 Web `POST /api/tts`；前端在助手回复流式结束后自动解析「说的话」并依次请求 TTS 播放。
- **Web 前端**：输入框旁麦克风按钮，点击录音、再点击停止并上传音频，识别结果追加到输入框。
- **CLI（可选）**：VAD + 本地录音后调 `speech_to_text`，orchestrator 用语音替代 `input()`；插嘴时 `player.interrupt()`。

### 阶段 4：CLI 端嘴 + 播放器（与 orchestrator 联动）
- **说明**：Web 端语音回复（mouth + 前端播报）已完成；本阶段指 **CLI** 端主脑流式输出经 mouth 合成后由 player 播放，并支持插嘴打断。
- **mouth.py**：在现有 TTS 基础上，消费主脑文本流、按句切分并生成音频入队（或复用现有接口由 player 拉取）。
- **player.py**：异步消费队列、播放音频、播放完清理 `assets/temp/`；暴露 `interrupt()`；将 RMS/音量数据提供给 body 用于口型。
- **orchestrator**：主脑流式输出不再仅 `print`，改为接入 mouth/player 链路。

### 阶段 5：眼睛接入与视听摘要 — ✅ 已完成（多模态截图 + 心跳检测）
- **vision**：`get_screen_for_turn()` 按 config 截屏、缩放、可选存 `data/vision/`；**心跳检测**：`check_heartbeat()` 每 N 秒（config `vision_heartbeat_interval_sec`，如 30）截图与上一帧 64×64 灰度缩略图对比，差异超过 `vision_heartbeat_diff_threshold` 则返回当前帧，供调度器触发主动说话。
- **orchestrator**：每轮取截图传入主脑；**直接回车**也执行一轮（继续说话）；后台心跳任务每 N 秒检测，有变化则向队列注入「画面发生了你感兴趣的变化…」回合并带当前截图执行一轮。
- **prompt_assembler**：§6 有本回合附图时说明本回合附图=当前画面、历史 [图: 时间]=过往；无图时说明不能描述「此刻」所见、但可回忆/引用历史视觉；**所有提示词仅在此组装**，conscious 不注入。
- **conscious**：仅发送组装好的 current_user_content + 可选 vision_image。

### 阶段 6：身体（Cubism Web SDK + 后端参数）
- **前端 (webapp)**：使用 **Cubism Web SDK** 官方 SDK 在浏览器中加载、渲染 Live2D 模型（.moc3 / .model3.json）；通过 WebSocket 或 SSE 接收后端下发的参数，驱动口型、表情、视线等，不在前端计算参数。
- **body.py（后端）**：根据 player 的 RMS/音量计算口型开合等参数；解析主脑输出中的情感标签（如 `*laughs*`）得到表情 ID；通过 Web API（SSE/WebSocket 或 REST）将参数流推送给已连接的前端。
- **orchestrator**：播放时把 RMS 等数据交给 body；可选在 conscious 输出里解析情感标签并通知 body。不依赖 VTube Studio，全部在 Web 端展示。

### 阶段 7：工具箱与主脑增强
- **tools_registry.py**：实现若干工具（如 search_web、execute_code），带类型与 docstring，转为 Gemini Function Calling 格式。
- **conscious**：将 tools 注册到 Gemini，开启自动调用；按需做 io_utils 的图片压缩（如先压缩再送 API）。

### 阶段 8：调度整合与稳定性
- 用 **asyncio.gather** 同时跑：语音监听、视觉定时采样、主脑流式、TTS 入队、播放、body 参数计算并推送到 Web 前端。
- 统一**插嘴**逻辑：新语音触发时 interrupt + 重新组 prompt 并请求主脑。
- 错误重试、超时、日志标签（如 [AUDIO]、[VISION]）完善；可选 api_client 统一 HTTP。

### 人格与长期一致优化（规划）
- **完整路线与优先级**：见 [docs/personality_optimization_roadmap.md](personality_optimization_roadmap.md)。
- **P0（状态与提示词）**：`state_manager.py` + `data/state/relationships.json`；羁绊值 intimacy 每轮隐式更新；2–3 档关系描述注入 prompt_assembler；当前情绪 state + 衰减规则 + §6 注入；ToM 一句（内心先推断再回应）；task/示例口吻与拒绝边界。
- **P1（记忆坍缩）**：`reflection.py` 按 session 总结短期对话 → 高 importance 写 Mem0；定时触发；可选 Reflection 输出 intimacy_delta 回写关系。
- **P2（主动意图）**：`agent_loop.py` 定时唤醒 + 内部 LLM 意图 + 可选主动发一条消息；social_battery 简单公式。
- **目标**：长期一致（Reflection）、关系演变（Relationship）、有活感（Agent Loop）、有温度（Emotion+ToM）、口吻稳定（task/示例/边界）。

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
5. **阶段 6（身体）** — 前端 Cubism Web SDK 渲染 Live2D，后端 body 计算口型/表情参数并推送；依赖阶段 4 的播放与音量。  
6. **阶段 7（工具箱）** — 按产品需求决定优先级。  
7. **阶段 8（调度整合）** — 全链路并联与稳定性收尾。

当前可运行链路：**CLI**（`main.py`）：模拟输入（直接回车=继续说话）→ Mem0 检索 → 每轮截屏（可选）→ 提示词全在 assembler 组装 → Gemini 多模态流式 → 控制台 + 历史 + 长期记忆写入。**Web**（`start_web.sh`）：打字/语音输入 → 同上流式 → 历史 + 记忆；`tts_reply_enabled=true` 时助手「说的话」自动 TTS 播报。**Telegram**（`python -m src.telegram`）：文本/语音/图片 → STT 或 vision 压缩后 → 同主脑流程，按 chat_id 隔离历史与 Mem0；回复按语言/心理/场景转 HTML 后发送。耳朵（STT）/嘴巴（TTS）在 Web 端均已接入；player/body 未接入（仅影响 CLI 端播放与 Live2D 口型驱动）。
