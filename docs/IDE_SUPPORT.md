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
