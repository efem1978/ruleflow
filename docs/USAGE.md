使用指南 Usage Guide

常用流程 Common Flows

1) 初始化与规则摄取
- mcp-rules-assistant init
- mcp-rules-assistant ingest-rules README.md docs/
- mcp-rules-assistant rules-explain --json --with-suggestions short

2) 应用门禁与生成 CI
- mcp-rules-assistant enforce
- mcp-rules-assistant generate-ci

3) 覆盖率
- mcp-rules-assistant coverage
- mcp-rules-assistant coverage-groups
- mcp-rules-assistant coverage-report --json > coverage_report.json
- mcp-rules-assistant coverage-clean-cache  # 如遇到缓存不一致

4) 建议导出
- mcp-rules-assistant rules-suggestions --format json --output suggestions.json
- mcp-rules-assistant rules-suggestions --format csv --output suggestions.csv

5) 诊断
- mcp-rules-assistant diagnose --json > diagnose.json

6) VS Code 面板
- F5 启动扩展开发主机 → "MCP: Open Panel"
- 受限环境：export MCP_VSCODE_TEST_ARGS="" && npm --prefix extensions/vscode test

