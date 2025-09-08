贡献指南 Contributing

开发流程 Development Flow
- TDD：先写红，再实现，最后重构，保持测试绿灯
- CLI 快捷：见 Makefile（`make setup|test|ci|vscode-test|ingest|coverage`）
- 提交规范：建议约定式提交（feat/fix/docs/test/chore 等）

本地环境 Local Setup
- Python ≥3.10，Node ≥18（CI 使用 20）
- `pip install -e .` 安装 CLI
- 可选：`make setup` 创建 `.mcp/venv` 并安装工具链

测试 Tests
- Python：`make test`（禁用外部 PyTest 插件）或运行：
  - `pytest -q --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=term-missing --cov-fail-under=95`
  - 覆盖率缓存清理：`mcp-rules-assistant coverage-clean-cache`
- VS Code：`make vscode-test`（受限环境可设置 `MCP_VSCODE_TEST_ARGS=""`）

代码规范 Code Style
- ruff/black/isort/mypy/bandit 在 CI 执行；本地可运行 `make lint type`

CI 与 Hooks
- 生成：`mcp-rules-assistant generate-ci`，校验：`mcp-rules-assistant ci-validate`
- 安装钩子：`mcp-rules-assistant install-hooks`
 - 覆盖率：CI 按 `.mcp/assistant.yaml` 的 `performance.on_push.coverage.min_module` 设置门槛，默认 0.95（95%）。CI 会上传 `coverage.xml` 至 Codecov 生成徽章（可选配置 `CODECOV_TOKEN`）。

Pre-commit
- 安装并启用：`pip install pre-commit && pre-commit install && pre-commit install --hook-type commit-msg && pre-commit install --hook-type pre-push`
- 推送时将运行覆盖率门槛与安全检查（见 `.pre-commit-config.yaml`）

GitHub 设置建议
- Branch protection：保护 `main`，要求 CI 通过（含覆盖率 ≥95%）
- Secrets（可选）：
  - `PYPI_API_TOKEN`（用于 `release.yml` 发布 PyPI）
  - `VSCE_PAT`（用于 VS Code 扩展发布）
