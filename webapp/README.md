# SoulSeed Web 前端

- **构建**: Vite + React + TypeScript
- **样式**: Tailwind CSS
- **组件**: shadcn/ui 风格（Radix + CVA + tailwind-merge）
- **图标**: Lucide React
- **状态/请求**: TanStack Query（拉取并缓存 `/api/history`，发送后 invalidate）
- **动画**: Framer Motion（消息进入与流式光标）

## 开发

```bash
npm install
npm run dev   # http://localhost:5173，/api 由 Vite proxy 转发到后端 8765
```

## 环境变量

- `VITE_API_URL`：生产或前后端分离时填后端地址，开发可不填（走 proxy）。

## 构建与运行

```bash
npm run build
npm run preview
```
