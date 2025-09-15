# IDE Support Matrix & One‑Click

- VS Code / Cursor / Windsurf
  - 共享 VSIX 扩展；本仓库已提供 VSIX 打包。打开仓库即可使用。
  - 状态栏“RuleFlow”提供“Quick Actions”，命令面板提供全部操作与自然语言入口。
  - 面板文档入口：提供“打开用户上手 / Open User Guide”“打开 IDE 支持 / Open IDE Support”按钮，便于新手快速查阅使用说明与支持矩阵。
- JetBrains（IDEA/PyCharm 等）
  - 提供最小工具窗口：启动/停止 MCP、自然语言输入、快速加载计划/记忆/覆盖率、环境准备、计划设置、CI/Hooks 等。
  - Gradle 任务 `runIde` 可在沙箱 IDE 运行；Docker 环境可一键打包 zip。
- Neovim
  - 提供 Vim/Lua 最小脚手架，命令 `:RuleFlowStart` 或绑定快捷键。

> 所有 IDE 均优先使用工作区 `.mcp/venv` 的 Python 解释器；安装与配置已自动化，开箱即用。

## 安全与隔离指引（强烈建议）
- 请阅读《docs/IDE_SECURITY.md》获取 VS Code / Cursor / JetBrains 的安全安装与隔离说明：
  - VS Code：显式指定 `VSCODE_BIN`，使用隔离目录安装与启动；默认严格隔离，记忆写入需项目允许。
  - Cursor：仅通过 UI 手动安装 VSIX；脚本默认不操作 Cursor，避免唤起窗口。
  - JetBrains：与 VS Code 同策略；支持 smoke 验证脚本。

## Workspace Isolation

- VS Code 扩展的状态存储改为按工作区隔离：
  - 自然语言历史 `ruleflow.nl.history` 与 Chat 追加开关 `ruleflow.chat.appendEnabled` 使用 `workspaceState` 存储，不再跨项目/跨 IDE 混淆。
  - 旧版本写入的 `globalState` 不再被读取，避免把其他工作区的历史带入当前窗口。
- 后端 MCP 服务器在启动时优先使用环境变量 `MCP_PROJECT_ROOT` 作为项目根目录；VS Code 扩展在启动子进程时会设置该变量为当前工作区路径，并以此作为工作目录（cwd）。
- 以上保证 `.mcp/memory.json` 与相关工件严格落在各自工作区内，实现项目级隔离。
