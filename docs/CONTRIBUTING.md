贡献指南 Contributing

开发流程 Development Flow
- TDD：先写红，再实现，最后重构，保持测试绿灯
- CLI 快捷：见 Makefile（`make setup|test|ci|vscode-test|ingest|coverage`）
- 提交规范：建议约定式提交（feat/fix/docs/test/chore 等）

本地环境 Local Setup
- Python ≥3.10，Node ≥18
- `pip install -e .` 安装 CLI
- 可选：`make setup` 创建 `.mcp/venv` 并安装工具链

测试 Tests
- Python：`make test`（禁用外部 PyTest 插件）
- VS Code：`make vscode-test`（受限环境可设置 `MCP_VSCODE_TEST_ARGS=""`）

代码规范 Code Style
- ruff/black/isort/mypy/bandit 在 CI 执行；本地可运行 `make lint type`

CI 与 Hooks
- 生成：`mcp-rules-assistant generate-ci`，校验：`mcp-rules-assistant ci-validate`
- 安装钩子：`mcp-rules-assistant install-hooks`

