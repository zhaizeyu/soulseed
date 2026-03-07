/**
 * 将助手回复按「场景描述 / 心理想的 / 说的话」分段并标注类型，用于区分颜色展示。
 * - ( ... ) / （ ... ） → 心理想的（褐色斜体）
 * - " ... " / 「 ... 」/ \u201C ... \u201D → 说的话（黄色）
 * - 单引号 ' ' 不算说的话，按场景描写处理
 * - 其余 → 场景描写（白色）
 */
export type SegmentType = "narrative" | "thought" | "speech";

export interface ContentSegment {
  type: SegmentType;
  text: string;
  open?: string;
  close?: string;
}

function findMatchingParen(s: string, afterOpen: number, open: string, close: string): number {
  let depth = 1;
  for (let i = afterOpen; i < s.length; i++) {
    if (s[i] === open) depth++;
    else if (s[i] === close) {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

export function parseContentSegments(content: string): ContentSegment[] {
  if (!content) return [];
  const segments: ContentSegment[] = [];
  let pos = 0;

  // 只有括号和双引号类算特殊段；单引号不算说的话
  const pairs: { open: string; close: string; type: SegmentType; nested?: boolean }[] = [
    { open: "(", close: ")", type: "thought", nested: true },
    { open: "\uFF08", close: "\uFF09", type: "thought", nested: true }, // （ ）
    { open: "\u300C", close: "\u300D", type: "speech" }, // 「 」
    { open: '"', close: '"', type: "speech" },
    { open: "\u201C", close: "\u201D", type: "speech" }, // " "
  ];

  while (pos < content.length) {
    let nextIdx = content.length;
    let chosen = pairs[0];
    for (const p of pairs) {
      const i = content.indexOf(p.open, pos);
      if (i !== -1 && i < nextIdx) {
        nextIdx = i;
        chosen = p;
      }
    }

    if (nextIdx > pos) {
      segments.push({
        type: "narrative",
        text: content.slice(pos, nextIdx),
      });
    }
    if (nextIdx === content.length) break;

    pos = nextIdx + chosen.open.length;
    const closeIdx = chosen.nested
      ? findMatchingParen(content, pos, chosen.open, chosen.close)
      : content.indexOf(chosen.close, pos);
    if (closeIdx === -1) {
      segments.push({
        type: "narrative",
        text: content.slice(nextIdx),
      });
      break;
    }
    const innerText = content.slice(pos, closeIdx);
    // 双引号内字数少于 5 则按场景文字渲染（不算「说的话」）
    const isShortQuoted =
      chosen.type === "speech" && innerText.replace(/\s/g, "").length < 5;
    segments.push({
      type: isShortQuoted ? "narrative" : chosen.type,
      text: innerText,
      open: chosen.open,
      close: chosen.close,
    });
    pos = closeIdx + chosen.close.length;
  }

  return segments;
}
