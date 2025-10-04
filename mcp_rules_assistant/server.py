from __future__ import annotations

from .mcp_server import serve_stdio


def start() -> None:
    """启动 JSON-RPC/stdio MCP 服务（轻量实现，生产门禁已具备）。"""
    serve_stdio()
