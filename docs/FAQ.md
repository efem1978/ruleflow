# 常见问题 FAQ

- PyTest 外部插件干扰 → 使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q`
- VS Code 测试在本机失败 → 试 `export MCP_VSCODE_TEST_ARGS="" && npm --prefix extensions/vscode test`
- 覆盖率报告缺失 → 运行 `pytest --cov --cov-report=xml:coverage.xml`
- 编译规则缺失 → 运行 `mcp-rules-assistant ingest-rules README.md docs/`
- 合规承诺缺失 → 运行 `mcp-rules-assistant compliance-commitment`
- 多 IDE 集成 → 运行 `mcp-rules-assistant ide-scaffold --editor vscode|cursor|jetbrains|neovim`

