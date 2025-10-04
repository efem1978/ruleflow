# Cursor 集成指南 / Cursor Integration

Cursor 基于 VS Code 内核，可直接安装本项目 VS Code 扩展的 VSIX 包实现完整功能。

安装
1) 构建 VSIX：
   - `npm --prefix ../../extensions/vscode run package`
   - 产物：`extensions/vscode/mcp-rules-assistant-*.vsix`
2) 在 Cursor 中：
   - 打开扩展视图（Extensions）→ 安装本地 VSIX → 选择上述 VSIX 文件。

诊断
- 若面板无法打开，查看“开发者工具”日志；或运行：
  - `MCP_VSCODE_TEST_ARGS="" npm --prefix ../../extensions/vscode test`
- 若 server 未启动：设置环境变量 `MCP_PYTHON_BIN=python3`。

备注
- 功能等同 VS Code：面板/自然语言命令/规则摄取/覆盖率/CI/Hooks 等。

