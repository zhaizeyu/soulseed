import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Mic, Square } from "lucide-react";
import { useChatHistory } from "@/hooks/use-chat-history";
import { useChatStream } from "@/hooks/use-chat-stream";
import { parseContentSegments } from "@/lib/format-content";
import { cn } from "@/lib/utils";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

/** 将段落内的 `code` 渲染为等宽高亮 */
function withCodeParts(text: string) {
  const parts = text.split("`");
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <code
        key={i}
        className="bg-white/[0.05] text-indigo-300 px-1.5 py-0.5 rounded text-sm font-mono"
      >
        {part}
      </code>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

function AssistantContent({
  content,
  isStreaming,
  showCaret,
}: {
  content: string;
  isStreaming?: boolean;
  showCaret?: boolean;
}) {
  const segments = parseContentSegments(content);
  return (
    <>
      {segments.map((seg, j) => (
        <span
          key={j}
          className={cn(
            seg.type === "thought" && "text-thought italic",
            seg.type === "speech" && "text-speech"
          )}
        >
          {seg.open}
          {withCodeParts(seg.text)}
          {seg.close}
        </span>
      ))}
      {showCaret && isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-indigo-400 animate-pulse" />
      )}
    </>
  );
}

const ASSISTANT_LABEL = "助手";

export default function App() {
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const { data: messages = [], isLoading: loadingHistory } = useChatHistory();
  const { sendMessage, loading, streamingTurn } = useChatStream();
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const lastStreamedContentRef = useRef<string>("");
  const [ttsReplyEnabled, setTtsReplyEnabled] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/config`)
      .then((r) => r.ok ? r.json() : {})
      .then((d: { tts_reply_enabled?: boolean }) => setTtsReplyEnabled(d.tts_reply_enabled !== false))
      .catch(() => setTtsReplyEnabled(true));
  }, []);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, streamingTurn?.assistantContent, scrollToBottom]);

  // 流式时缓存当前内容，便于结束后播报「说的话」
  useEffect(() => {
    if (streamingTurn?.assistantContent)
      lastStreamedContentRef.current = streamingTurn.assistantContent;
  }, [streamingTurn?.assistantContent]);

  // 流式结束后：识别「说的话」并依次 TTS 播报
  const playSpeechSegments = useCallback(async (content: string) => {
    const segments = parseContentSegments(content).filter((s) => s.type === "speech");
    if (segments.length === 0) return;
    const playNext = async (index: number) => {
      if (index >= segments.length) return;
      const text = segments[index].text.trim();
      if (!text) {
        playNext(index + 1);
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => {
          URL.revokeObjectURL(url);
          playNext(index + 1);
        };
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          playNext(index + 1);
        };
        await audio.play();
      } catch {
        playNext(index + 1);
      }
    };
    playNext(0);
  }, []);

  useEffect(() => {
    if (streamingTurn !== null || !ttsReplyEnabled) return;
    const content = lastStreamedContentRef.current;
    if (!content) return;
    lastStreamedContentRef.current = "";
    playSpeechSegments(content);
  }, [streamingTurn, ttsReplyEnabled, playSpeechSegments]);

  const displayMessages = [...messages];
  if (streamingTurn) {
    if (streamingTurn.userMessage)
      displayMessages.push({ role: "user", content: streamingTurn.userMessage });
    displayMessages.push({
      role: "assistant",
      content: streamingTurn.assistantContent,
    });
  }

  const handleSubmit = () => {
    const text = input;
    setInput("");
    sendMessage(text, messages.length);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const sendAudioToStt = useCallback(async (blob: Blob) => {
    setSpeechError(null);
    const form = new FormData();
    form.append("audio", blob, "audio.webm");
    try {
      const res = await fetch(`${API_BASE}/api/speech-to-text`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(res.statusText);
      const data = (await res.json()) as { text?: string };
      const text = (data.text ?? "").trim();
      if (text) setInput((prev) => (prev ? prev + " " + text : text));
    } catch (e) {
      setSpeechError(e instanceof Error ? e.message : "识别失败");
    }
  }, []);

  const handleMicClick = useCallback(() => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      mediaRecorderRef.current = null;
      setIsRecording(false);
      return;
    }
    setSpeechError(null);
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        const mr = new MediaRecorder(stream);
        mediaRecorderRef.current = mr;
        const chunks: Blob[] = [];
        mr.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
        mr.onstop = () => {
          const blob = new Blob(chunks, { type: mimeType });
          sendAudioToStt(blob);
        };
        mr.start();
        setIsRecording(true);
      })
      .catch((e) => setSpeechError(e?.message ?? "无法访问麦克风"));
  }, [isRecording, sendAudioToStt]);

  return (
    <div className="flex h-dvh w-full bg-[#0f1117] text-slate-300 font-sans antialiased overflow-hidden">
      <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full relative">
        {/* 顶部极简导航 */}
        <header className="h-20 flex items-center justify-between px-6 border-b border-white/[0.03]">
          <div className="flex items-center space-x-4">
            <div
              className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
              aria-hidden
            />
            <div>
              <h1 className="text-sm font-medium tracking-tight text-white uppercase opacity-90">
                SoulSeed{" "}
                <span className="text-slate-500 font-light mx-2">|</span>{" "}
                <span className="text-indigo-400">Terminal</span>
              </h1>
            </div>
          </div>
        </header>

        {/* 对话列表 */}
        <div
          className="flex-1 overflow-y-auto px-6 py-8 space-y-10 scroll-smooth"
          role="log"
          aria-live="polite"
          aria-label="对话记录"
        >
          {loadingHistory && (
            <p className="text-sm text-slate-500 text-center py-8 animate-fade-in">
              正在加载对话历史…
            </p>
          )}
          {!loadingHistory && displayMessages.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-8 animate-fade-in">
              输入消息开始对话，或直接回车让助手先开口
            </p>
          )}
          <AnimatePresence initial={false}>
            {!loadingHistory &&
              displayMessages.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={cn(
                    "flex flex-col max-w-[90%] md:max-w-[85%] leading-relaxed text-[15px]",
                    m.role === "user" ? "items-end" : "items-start"
                  )}
                >
                  {m.role === "user" ? (
                    <div className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-100 px-5 py-3 rounded-2xl rounded-tr-none shadow-lg shadow-indigo-500/5 whitespace-pre-wrap break-words">
                      {m.content.split("`").map((part, j) =>
                        j % 2 === 1 ? (
                          <code
                            key={j}
                            className="bg-white/[0.08] text-indigo-200 px-1.5 py-0.5 rounded text-sm font-mono"
                          >
                            {part}
                          </code>
                        ) : (
                          part
                        )
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="text-white whitespace-pre-wrap break-words">
                        <AssistantContent
                          content={
                            m.content ||
                            (streamingTurn && i === displayMessages.length - 1
                              ? "…"
                              : "")
                          }
                          isStreaming={
                            !!(
                              streamingTurn &&
                              i === displayMessages.length - 1
                            )
                          }
                          showCaret={
                            !!(
                              streamingTurn &&
                              i === displayMessages.length - 1
                            )
                          }
                        />
                      </div>
                      <span className="mt-2 text-[10px] text-slate-600 font-medium uppercase tracking-tighter opacity-50">
                        {ASSISTANT_LABEL} // 01
                      </span>
                    </>
                  )}
                </motion.div>
              ))}
          </AnimatePresence>
          <div ref={bottomRef} className="h-4" />
        </div>

        {/* 输入栏 — 贴底通栏，支持语音输入 */}
        <div className="shrink-0 border-t border-white/[0.06] bg-[#0f1117]">
          {speechError && (
            <p className="px-4 py-1 text-xs text-amber-500/90" role="alert">
              {speechError}
            </p>
          )}
          <div className="flex items-center gap-2 px-4 py-2">
            <button
              type="button"
              onClick={handleMicClick}
              disabled={loading}
              className={cn(
                "p-2 transition-all duration-200 flex items-center justify-center rounded",
                isRecording
                  ? "text-red-400 hover:text-red-300 bg-red-500/10"
                  : !loading
                    ? "text-slate-400 hover:text-white"
                    : "text-slate-700 cursor-not-allowed"
              )}
              aria-label={isRecording ? "停止录音" : "语音输入"}
              title={isRecording ? "点击停止并识别" : "点击开始录音"}
            >
              {isRecording ? <Square size={18} /> : <Mic size={18} />}
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="输入想发送的消息，或点击麦克风语音输入"
              disabled={loading}
              className="flex-1 bg-transparent border-none focus:ring-0 text-slate-200 py-2 text-sm placeholder-slate-600 focus:outline-none disabled:opacity-60"
              aria-label="输入消息"
            />
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className={cn(
                "p-2 transition-all duration-200 flex items-center justify-center",
                !loading
                  ? "text-slate-400 hover:text-white"
                  : "text-slate-700 cursor-not-allowed"
              )}
              aria-label="发送"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
