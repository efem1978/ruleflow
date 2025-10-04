from mcp_rules_assistant.mcp_server import JsonRpcServer


def _req(method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def test_mcp_initialize_and_lists() -> None:
    srv = JsonRpcServer()
    r0 = srv.handle(_req("initialize"))
    caps = r0.get("result", {}).get("capabilities", {})
    assert (
        caps.get("tools") is True
        and caps.get("resources") is True
        and caps.get("prompts") is True
    )

    r1 = srv.handle(_req("tools/list"))
    tools = r1.get("result", {}).get("tools", [])
    assert isinstance(tools, list) and len(tools) > 0

    r2 = srv.handle(_req("resources/list"))
    resources = r2.get("result", {}).get("resources", [])
    assert isinstance(resources, list) and len(resources) > 0

    # prompts default disabled -> empty list
    r3 = srv.handle(_req("prompts/list"))
    assert r3.get("result", {}).get("prompts") == []
