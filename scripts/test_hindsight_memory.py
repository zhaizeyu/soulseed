#!/usr/bin/env python3
"""
测试 Hindsight 记忆的存取与记忆坍缩（Reflect）。
需先以 Docker 模式部署 Hindsight（如 http://localhost:8888），并安装：pip install hindsight-client

用法（项目根目录执行）：
  .venv/bin/python scripts/test_hindsight_memory.py
  .venv/bin/python scripts/test_hindsight_memory.py --url http://localhost:8888 --bank test_vedal
"""
import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 Hindsight 记忆存取与记忆坍缩")
    parser.add_argument("--url", default="http://localhost:8888", help="Hindsight API 地址")
    parser.add_argument("--bank", default="test_vedal", help="测试用 bank_id（与 user_id 对应）")
    parser.add_argument("--no-retain", action="store_true", help="跳过写入，仅做 recall + reflect")
    parser.add_argument("--timeout", type=float, default=120.0, help="请求超时秒数（Reflect 需调 LLM，建议 ≥120）")
    args = parser.parse_args()

    try:
        from hindsight_client import Hindsight
    except ImportError:
        print("请安装: pip install hindsight-client", file=sys.stderr)
        return 1

    bank_id = args.bank

    # 使用 with 确保 aiohttp ClientSession 在退出时关闭，避免 Unclosed client session
    timeout = max(30.0, args.timeout)
    try:
        with Hindsight(base_url=args.url, timeout=timeout) as client:
            return _run_tests(client, bank_id, args.no_retain)
    except AttributeError:
        # 旧版 client 可能无 __enter__，退化为手动 close
        client = Hindsight(base_url=args.url, timeout=timeout)
        try:
            return _run_tests(client, bank_id, args.no_retain)
        finally:
            if hasattr(client, "close"):
                try:
                    client.close()
                except Exception:
                    pass


def _run_tests(client, bank_id: str, skip_retain: bool) -> int:
    # ---------- 1. Retain：写入几条测试记忆 ----------
    if not skip_retain:
        print("--- 1. Retain（写入记忆）---")
        samples = [
            {
                "content": "User: 我最近在学 Python，想做个聊天机器人。\nAssistant: 不错呀，可以用 Gemini 做多模态，再配上长期记忆。",
                "context": "对话",
                "metadata": {"source": "test_script"},
            },
            {
                "content": "用户说他的老板最近在学 Python，压力很大，经常加班。",
                "context": "用户近况",
                "metadata": {"source": "test_script"},
            },
            {
                "content": "用户喜欢在晚上和周末和助手聊天，偏好口语化、带点傲娇的回复风格。",
                "context": "用户偏好",
                "metadata": {"source": "test_script"},
            },
        ]
        for i, s in enumerate(samples):
            try:
                client.retain(
                    bank_id=bank_id,
                    content=s["content"],
                    context=s.get("context", ""),
                    timestamp=datetime.utcnow(),
                    metadata=s.get("metadata"),
                )
                print(f"  [{i+1}] 已写入: {s['content'][:50]}...")
            except Exception as e:
                print(f"  [{i+1}] 写入失败: {e}", file=sys.stderr)
        print()
    else:
        print("--- 跳过 Retain（--no-retain）---\n")

    # ---------- 2. Recall：检索记忆 ----------
    print("--- 2. Recall（检索记忆）---")
    query = "用户最近在做什么、有什么偏好？"
    print(f"  Query: {query}")
    try:
        results = client.recall(bank_id=bank_id, query=query, max_tokens=1024)
        # 兼容 .results 或直接为 list
        items = getattr(results, "results", results)
        if not isinstance(items, list):
            items = list(items) if items else []
        if not items:
            print("  (无结果)")
        else:
            for i, r in enumerate(items):
                text = getattr(r, "text", str(r))
                mtype = getattr(r, "type", "")
                print(f"  [{i+1}] {mtype and f'[{mtype}] '}{text[:120]}{'...' if len(text) > 120 else ''}")
    except Exception as e:
        print(f"  Recall 失败: {e}", file=sys.stderr)
        return 1
    print()

    # ---------- 3. Reflect：记忆坍缩（基于记忆生成总结/回答）----------
    print("--- 3. Reflect（记忆坍缩 / 总结）---")
    reflect_query = "根据已有记忆，用 2～3 句话总结：这位用户是谁、最近在做什么、对助手有什么期待。"
    print(f"  Query: {reflect_query}")
    print("  (Reflect 会调服务端 LLM，可能需数十秒，请稍候…)")
    try:
        # 仅传 bank_id + query，避免部分服务端不支持 budget/context 导致空异常
        answer = client.reflect(bank_id=bank_id, query=reflect_query)
        text = getattr(answer, "text", str(answer))
        print(f"  Reflect 输出:\n  {text}")
    except Exception as e:
        print(f"  Reflect 失败: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    print()

    # ---------- 4. 可选：将 Reflect 结果再次 Retain（坍缩写回）----------
    print("--- 4. 可选：坍缩写回（将 Reflect 结果写入为一条高阶记忆）---")
    try:
        client.retain(
            bank_id=bank_id,
            content=f"[记忆坍缩摘要] {text}",
            context="记忆坍缩",
            timestamp=datetime.utcnow(),
            metadata={"source": "test_script", "type": "reflection_summary"},
        )
        print("  已写入 Reflect 摘要为一条新记忆。")
    except Exception as e:
        print(f"  写入失败: {e}", file=sys.stderr)
    print()

    print("测试完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
