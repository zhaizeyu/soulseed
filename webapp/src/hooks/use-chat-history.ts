import { useQuery } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

async function fetchHistory(): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error("Failed to fetch history");
  const data = (await res.json()) as { messages?: Message[] };
  return Array.isArray(data.messages) ? data.messages : [];
}

export function useChatHistory() {
  return useQuery({
    queryKey: ["chat", "history"],
    queryFn: fetchHistory,
    retry: 1,
    refetchOnWindowFocus: true,
    // 每 10 秒轮询一次，便于收到心跳触发的主动消息
    refetchInterval: 10_000,
  });
}
