"""
工具箱 — 纯 Python 业务函数库 (代码执行/搜索等)，供 Gemini 自动调用。
强制 Type Hints 与详细 Docstring，Gemini 解析 Docstring 作为 Function Calling 描述。
"""
from typing import Any

# TODO: 定义 search_web(query: str), execute_code(script: str) 等，并导出为 list/dict 供 conscious 传入 tools
def get_tools_for_gemini() -> list[dict[str, Any]]:
    """返回供 Gemini Function Calling 使用的工具声明列表。"""
    return []
