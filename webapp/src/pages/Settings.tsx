import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const SETTING_SECTIONS = [
  { title: "角色卡", subtitle: "使用预设角色卡与人设" },
  { title: "机体模块", subtitle: "思维、视觉、言语综合、游戏等" },
  { title: "场景", subtitle: "配置角色所在环境" },
  { title: "角色模型", subtitle: "切换角色的 Live2D、VRM 模型" },
  { title: "记忆体", subtitle: "存放记忆的地方，以及策略" },
  { title: "服务来源", subtitle: "LLM、语音合成、语音识别服务来源等" },
  { title: "Data", subtitle: "管理存储数据、导出和重置", showArrow: true },
];

export default function Settings() {
  return (
    <div className="flex-1 overflow-y-auto min-h-0" style={{ backgroundColor: "#252526" }}>
      <div className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-8" style={{ color: "#d4d4d4" }}>设置</h1>
        <div className="rounded overflow-hidden" style={{ backgroundColor: "#2d2d2d", borderColor: "#3d3d3d", borderWidth: 1, borderStyle: "solid" }}>
          {SETTING_SECTIONS.map((section, i) => (
            <button
              key={section.title}
              type="button"
              className={cn(
                "w-full flex items-center justify-between text-left px-5 py-4 transition-colors",
                i > 0 && "border-t"
              )}
              style={{
                borderColor: "#3d3d3d",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#333333"; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-base font-semibold" style={{ color: "#d4d4d4" }}>
                  {section.title}
                </span>
                <span className="text-sm" style={{ color: "#9c9c9c" }}>{section.subtitle}</span>
              </div>
              {section.showArrow && (
                <ChevronDown className="w-5 h-5 shrink-0" style={{ color: "#6e6e6e" }} />
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
