import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send } from "lucide-react";
import { useChatHistory } from "@/hooks/use-chat-history";
import { useChatStream } from "@/hooks/use-chat-stream";
import { parseContentSegments } from "@/lib/format-content";
import { cn } from "@/lib/utils";

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
  const { data: messages = [], isLoading: loadingHistory } = useChatHistory();
  const { sendMessage, loading, streamingTurn } = useChatStream();
  const [input, setInput] = useState("");

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, streamingTurn?.assistantContent, scrollToBottom]);

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
                VedalAI{" "}
                <span className="text-slate-500 font-light mx-2">|</span>{" "}
                <span className="text-indigo-400">Terminal</span>
              </h1>
            </div>
          </div>
          <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-500 uppercase tracking-widest">
            <span className="bg-white/[0.03] px-2 py-1 rounded">Secure</span>
            <span className="text-emerald-500/80">Online</span>
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

        {/* 输入栏 — 贴底通栏 */}
        <div className="shrink-0 border-t border-white/[0.06] bg-[#0f1117]">
          <div className="flex items-center gap-2 px-4 py-2">
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
              placeholder="输入想发送的消息，或输入 /? 获取帮助"
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
