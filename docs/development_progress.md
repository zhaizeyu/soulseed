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
| prompt_assembler | ✅ | 按 prompt.md §1–§8 顺序组装，不合并、用户可空 |
| conscious | ✅ | Gemini 流式、消息逐条转 Content、无 API Key 时友好提示 |
| chat_history_store | ✅ | JSON 持久化、每次加载最近 N 条、配置化路径与条数 |
| memory | ⏳ 占位 | search / add_background 空实现，未接 Mem0 |
| tools_registry | ⏳ 占位 | 未实现业务工具，未接入 conscious |

### 3. 调度与主循环（第一步闭环）
| 模块 | 状态 | 说明 |
|------|------|------|
| orchestrator | ✅ 部分 | 模拟输入 → 主脑流式 → 控制台；历史加载/写入；**未接** 真实 hearing/vision/mouth/player/body |
| main.py | ✅ | 入口，asyncio 跑 orchestrator.run() |

### 4. 感官层
| 模块 | 状态 | 说明 |
|------|------|------|
| vision | ✅ 简易 | capture_screen() 用 mss 截屏，**未**接入 orchestrator，无 Diff/摘要 |
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

---

## 二、后续开发阶段建议

### 阶段 2：记忆（Mem0）
- **memory.py**：集成 Mem0（或 Qdrant/Chroma），实现 `search(query)`、`add_background(content)`。
- **orchestrator / conscious**：每轮前 `mem0_lines = await memory.search(当前用户输入)` 传入组装；每轮后异步 `memory.add_background(回复摘要)`。
- **可选**：配置中增加 Mem0/向量库相关项。

### 阶段 3：耳朵（语音输入）
- **hearing.py**：VAD（WebRTC VAD 或 Silero）+ 录音，静音检测结束送 Whisper（或本地 STT）得到文本。
- **orchestrator**：用 `hearing` 的语音流/事件替代 `input()`，得到用户文本后仍走现有 `_run_one_turn`；支持「插嘴」时调用 `player.interrupt()`（若已实现播放）。

### 阶段 4：嘴 + 播放器（语音输出）
- **mouth.py**：消费主脑文本流，按句切分，调用 Edge-TTS / FishAudio 等生成音频，路径入队。
- **player.py**：异步消费队列、播放音频、播放完清理 `assets/temp/`；暴露 `interrupt()`；可选将 RMS 推给 body。
- **orchestrator**：主脑流式输出不再直接 `print`，改为接入 `mouth.consume_text_stream(stream)`（或等价接口）。

### 阶段 5：眼睛接入与视听摘要
- **vision**：在现有 capture_screen 上增加可选 Diff、或对图像做轻量摘要（如调用一次视觉模型得到「当前画面描述」）。
- **orchestrator**：每轮或定时取 `vision.capture_screen()`，得到图像或摘要文本，作为 `vision_audio_text`（或多模态）传入 prompt_assembler / conscious。

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

---

## 三、推荐推进顺序

1. **阶段 2（记忆）** — 提升对话连贯与人设一致性。  
2. **阶段 4（嘴 + 播放器）** — 先实现「文字→语音播放」与 interrupt，再接耳朵更自然。  
3. **阶段 3（耳朵）** — 语音输入替代打字，并与阶段 4 的 interrupt 联动。  
4. **阶段 5（眼睛接入）** — 为多模态/环境感知打基础。  
5. **阶段 6（身体）** — 口型与表情，依赖阶段 4 的播放与音量。  
6. **阶段 7（工具箱）** — 按产品需求决定优先级。  
7. **阶段 8（调度整合）** — 全链路并联与稳定性收尾。

当前可运行链路：**模拟输入 → 提示词组装 → Gemini 流式 → 控制台输出 + 历史持久化**；其余感官与表达均为占位或未接入。
