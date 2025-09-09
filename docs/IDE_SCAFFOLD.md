# 多 IDE 最小集成使用指南 / IDE Integration Guide

目标
- 通过最小集成配置，使各 IDE 可一键启动本项目的 MCP Server 与常用 CLI，保持“保存轻/推送重”的开发体验。

总览
- 生成入口（二选一）：
  - CLI：`mcp-rules-assistant ide-scaffold --editor <vscode|cursor|jetbrains|neovim>`
  - MCP 工具：`tools/call name="ide.scaffold" {"editor": "vscode"}`
- 生成位置：`.mcp/ide/<editor>/`
- 支持编辑器：VS Code / Cursor / JetBrains / Neovim

兼容性说明
- Cursor / Windsurf：直接安装 VSIX（与 VS Code 共享引擎），功能等同 VS Code；无需单独分叉。
- JetBrains：最小骨架与路线图见 `docs/IDE_PLUGIN_ROADMAP.md`；骨架代码位于 `extensions/jetbrains/`。

VS Code / Cursor
- 输出：`.mcp/ide/vscode/settings.sample.json` 与 README
- 使用：
  1) 将 `settings.sample.json` 合并进工作区 `.vscode/settings.json`
  2) 打开命令面板运行 `RuleFlow: Open Panel`，或在 Copilot MCP 面板选择 `ruleflow`
  3) 若 Python 可执行名不是 `python3`，设置环境变量 `MCP_PYTHON_BIN` 指定解释器路径
  4) 快捷命令：`RuleFlow: Open Plan` / `RuleFlow: Open Memory` 直接打开 `.mcp/plan.md` / `.mcp/memory.json`

JetBrains（IDEA / PyCharm 等）
- 输出：`.mcp/ide/jetbrains/externalTools.sample.xml` 与 README
- 使用：
  1) Settings → Tools → External Tools → Import，导入 `externalTools.sample.xml`
  2) 或手动添加一个 External Tool：可执行程序 `python3`，参数 `-m mcp_rules_assistant.cli start`，工作目录 `$ProjectFileDir$`
  3) 通过 External Tool 或 Terminal 启动服务器/执行 CLI
 - RuleFlow 工具窗口：提供“加载计划/记忆/覆盖率摘要”按钮与“在编辑器打开计划/记忆”动作，便于快速查看 `.mcp/` 状态。

Neovim
- 输出：`.mcp/ide/neovim/init.sample.vim`、`.mcp/ide/neovim/init.sample.lua` 与 README
- 使用（Vimscript）：在 `init.vim` 引入示例片段，使用 `:RuleFlowStart` 启动 MCP 服务器
- 使用（Lua）：在 `init.lua` 引入示例函数 `RuleFlowStart()`，或映射快捷键执行

注意事项
- 最小集成不改变项目行为，仅提供一套“如何在该 IDE 中高效启动和交互”的示例配置。
- 首次运行前建议执行：`mcp-rules-assistant install-hooks` 与 `mcp-rules-assistant generate-ci`
- 若希望在容器内持续运行并落盘状态：`docker compose up -d dev-agent`（详见 `docs/DOCKER_DEV.md`）
