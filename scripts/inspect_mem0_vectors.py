#!/usr/bin/env python3
"""
查看 Mem0 向量库中已存储的记忆内容。
用法：先退出主程序，再在项目根目录执行：
  python scripts/inspect_mem0_vectors.py
  或  .venv/bin/python scripts/inspect_mem0_vectors.py
"""
import sys
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("请先安装: pip install qdrant-client")
        return 1

    # 与 memory.py 默认一致
    from src.core.config_loader import get_config
    cfg = get_config()
    vector_path = cfg.get("mem0_vector_store_path") or str(ROOT / "data" / "mem0" / "qdrant")
    vector_path = Path(vector_path)
    if not vector_path.is_absolute():
        vector_path = ROOT / vector_path
    vector_path = vector_path.resolve()

    if not vector_path.exists():
        print(f"向量库目录不存在: {vector_path}")
        return 1

    try:
        client = QdrantClient(path=str(vector_path))
    except RuntimeError as e:
        if "already accessed" in str(e) or "Lock" in str(e):
            print("Qdrant 本地库正被占用（主程序可能未退出）。请先退出主程序再运行此脚本。")
        else:
            print("打开 Qdrant 失败:", e)
        return 1

    collections = client.get_collections().collections
    if not collections:
        print("当前没有任何 collection。")
        return 0

    # Mem0 默认 collection 名为 mem0
    name = "mem0"
    if not any(c.name == name for c in collections):
        print(f"未找到 collection '{name}'，现有: {[c.name for c in collections]}")
        return 0

    points, _ = client.scroll(
        collection_name=name,
        limit=500,
        with_payload=True,
        with_vectors=False,
    )
    print(f"共 {len(points)} 条记忆\n")
    for i, point in enumerate(points, 1):
        payload = point.payload or {}
        # Mem0 写入时用 data 存正文，search 返回格式用 memory
        memory_text = payload.get("memory") or payload.get("data") or payload.get("text") or ""
        user_id = payload.get("user_id", "")
        created = payload.get("created_at") or payload.get("updated_at") or ""
        print(f"--- [{i}] (user_id={user_id}) {created}")
        if memory_text:
            print(memory_text[:300] + ("..." if len(memory_text) > 300 else ""))
        else:
            print("(无 memory/text 字段) 原始 payload keys:", list(payload.keys()))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
