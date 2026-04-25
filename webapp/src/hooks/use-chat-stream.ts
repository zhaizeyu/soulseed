import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export interface StreamingTurn {
  userMessage: string;
  assistantContent: string;
}

export function useChatStream() {
  const [loading, setLoading] = useState(false);
  const [streamingTurn, setStreamingTurn] = useState<StreamingTurn | null>(null);
  const queryClient = useQueryClient();
  /** 防止连点发送或 StrictMode 下的重入导致两条请求、两条占位 */
  const inFlightRef = useRef(false);

  const sendMessage = useCallback(
    async (input: string, currentLength: number) => {
      if (inFlightRef.current) return;
      const userContent = input.trim() || "(继续说话)";
      if (!input.trim() && currentLength === 0) return;

      inFlightRef.current = true;
      setLoading(true);
      setStreamingTurn({
        userMessage: input.trim() ? userContent : "",
        assistantContent: "",
      });

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userContent }),
        });
        if (!res.ok || !res.body) {
          setStreamingTurn((prev) =>
            prev ? { ...prev, assistantContent: `[请求失败 ${res.status}]` } : null
          );
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let full = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6)) as {
                  chunk?: string;
                  done?: boolean;
                };
                if (data.chunk != null) full += data.chunk;
                setStreamingTurn((prev) =>
                  prev ? { ...prev, assistantContent: full } : null
                );
              } catch {
                /* ignore */
              }
            }
          }
        }
        // 必须先结束「流式占位」，再拉历史；否则 messages 已含本轮而 streamingTurn 仍在，会重复渲染两条
        setStreamingTurn(null);
        await queryClient.invalidateQueries({ queryKey: ["chat", "history"] });
      } catch (e) {
        setStreamingTurn((prev) =>
          prev
            ? { ...prev, assistantContent: `[网络错误: ${String(e)}]` }
            : null
        );
      } finally {
        setStreamingTurn(null);
        setLoading(false);
        inFlightRef.current = false;
      }
    },
    [queryClient]
  );

  return { sendMessage, loading, streamingTurn };
}
