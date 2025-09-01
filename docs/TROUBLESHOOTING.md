故障排查 Troubleshooting

常见问题 Common Issues
- PyTest 外部插件干扰
  - 现象：本地 `pytest` 启动报第三方插件异常
  - 处理：使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q`

- VS Code 测试在本机失败
  - 现象：`npm --prefix extensions/vscode test` 失败，Electron 启动参数不被接受
  - 处理：
    - 移除默认参数：`export MCP_VSCODE_TEST_ARGS=""` 然后重新运行测试
    - 或自定义启动参数（逗号分隔）：`export MCP_VSCODE_TEST_ARGS="--disable-extensions"`
  - 说明：CI 会执行 headless 测试并上传日志工件

- 未生成 coverage.xml
  - 现象：面板“加载覆盖率”报缺少 coverage.xml
  - 处理：运行 `pytest --cov --cov-report=xml:coverage.xml`

- 规则未摄取/编译
  - 现象：面板/CLI 提示“未找到编译规则”
  - 处理：`mcp-rules-assistant ingest-rules README.md docs/`，确认 `.mcp/rules_compiled.*` 已生成

- 钩子未执行
  - 处理：`pip install pre-commit && pre-commit install && pre-commit install --hook-type commit-msg --hook-type pre-push`

