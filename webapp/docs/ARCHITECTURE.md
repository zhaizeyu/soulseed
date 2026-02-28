# 前端架构说明

## 当前技术栈（Vite + Tailwind）

- **Vite + React + TypeScript**：构建与开发服务器，HMR 快、配置简单
- **Tailwind CSS**：样式，主题变量在 `src/index.css`
- **shadcn/ui 风格**：Radix + CVA + `cn()`，组件在 `src/components/ui/`
- **Lucide React**：图标
- **TanStack Query**：服务端状态（历史拉取、缓存，发送后 invalidate）
- **Framer Motion**：消息列表入场动画

## 可优化点（可选）

1. **历史请求**：`useChatHistory` 已设 `retry: 1`、`refetchOnWindowFocus: true`
2. **包体**：若仅需简单淡入，可用 CSS 替代 Framer Motion 减小首包
3. **长列表**：历史很多时可引入虚拟列表（如 `@tanstack/react-virtual`）
4. **无障碍**：对话区已用 `role="log"`、`aria-live="polite"`
