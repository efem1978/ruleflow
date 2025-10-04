# 隐私政策 / Privacy Policy (Minimal-Info)

## 数据采集 / Data Collection

- 本项目默认不采集任何遥测数据，不主动向外发送使用数据或代码片段。
- 可选功能（如 Dev Agent 自动记忆）在工作区本地生成 `.mcp/memory.json`，不上传到任何云端。

## 第三方集成 / Third-Party Integrations

- Codecov：仅在 CI 环境中（公共仓库默认）上传覆盖率报告（`.coverage`、`coverage.xml`），不包含任何业务源码。
- MCP：如启用 Claude Desktop / Cursor 等 MCP 客户端，Agent 会读取工作区 `.mcp/` 文件夹以提供上下文，不发送到本项目服务器。

## 本地持久化 / Local Persistence

- CLI/Server 默认在当前工作区读写 `.mcp/`；如需共享/备份，由你手动管理。
- 测试、覆盖率、规则摄取等产物均留存在本地（项目根 `.mcp/dashboard/`、`coverage.xml`、`.coverage`）。

## 数据保留 / Data Retention

- `.mcp/` 目录下的产物留存在你的仓库或工作目录中；不上传到任何外部服务器。
- 建议将 `.mcp/memory*.json` 加入 `.gitignore`（仅在需要时提交版本控制）。

## 联系 / Contact

- 联系邮箱：<support@ruleflow.app>
- GitHub：<https://github.com/your-org/mcp-rules-assistant>
