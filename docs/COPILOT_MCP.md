# Copilot MCP 集成（可选）

目标
- 在 Copilot 的 MCP 面板显示并启动本工具（ruleflow），必要时在聊天中通过“让 ruleflow …”来触发能力。

前置
- 已安装本仓库的 Python 端与 VS Code 扩展。
- VS Code 已打开当前工作区。

步骤
- 工作区设置已预置登记（见 `.vscode/settings.json`）；如需手动添加：
  ```json
  {
    "copilot.mcp.tools": {
      "ruleflow": {
        "command": "python3",
        "args": ["-m", "mcp_rules_assistant.cli", "start"],
        "cwd": "${workspaceFolder}",
        "env": { "PYTHONUNBUFFERED": "1" }
      }
    }
  }
  ```
- 重载窗口：Cmd/Ctrl+Shift+P → Reload Window。
- 打开 Copilot 面板：侧边栏 COPILOT MCP → Installed；可见“ruleflow”，点击 Process 启动。
- 聊天触发（可选）：在 Copilot 聊天输入
  - “用 ruleflow 摄取规则 README.md, docs/”
  - “请让 ruleflow 加载覆盖率并列出近阈值文件”

排障
- 没看到 ruleflow：
  - 确认当前打开的是本工作区，并包含上述 settings.json。
  - 重载窗口；或手动把 JSON 片段粘到用户/工作区设置，再重载。
- Python 启动失败：设置 `MCP_PYTHON_BIN=python3`，或选用你机器上的 Python 解释器。
- 聊天没命中：在句子里明确提到“ruleflow”，更容易路由到该工具。

