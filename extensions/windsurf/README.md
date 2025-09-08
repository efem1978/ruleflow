# Windsurf 集成指南 / Windsurf Integration

Windsurf 基于 VS Code 扩展生态，可直接安装 VSIX 包使用本项目扩展功能。

安装
1) 构建 VSIX：
   - `npm --prefix ../../extensions/vscode run package`
   - 产物：`extensions/vscode/mcp-rules-assistant-*.vsix`
2) 在 Windsurf 中：
   - 打开扩展管理 → 安装本地 VSIX → 选择 VSIX 文件。

兼容性说明
- 若遇到 Node 或 Webview API 差异，请反馈版本信息；建议使用 Node 20+。

诊断
- 无头测试：`MCP_VSCODE_TEST_ARGS="" npm --prefix ../../extensions/vscode test`
- Server 启动失败：`export MCP_PYTHON_BIN=python3`。

