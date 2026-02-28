import { useCallback, useState } from "react";
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

  const sendMessage = useCallback(
    async (input: string, currentLength: number) => {
      const userContent = input.trim() || "(继续说话)";
      if (!input.trim() && currentLength === 0 && !streamingTurn) return;

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
      }
    },
    [streamingTurn, queryClient]
  );

  return { sendMessage, loading, streamingTurn };
}
