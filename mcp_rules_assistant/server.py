from __future__ import annotations

from typing import NoReturn

from .mcp_server import serve_stdio


def start() -> None:
    """启动 JSON-RPC/stdio MCP 兼容服务（最小骨架）。"""
    serve_stdio()
