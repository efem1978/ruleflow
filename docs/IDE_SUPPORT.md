# IDE 支持 / IDE Support

本文档描述 MCP Rules Assistant 对各种主流 IDE 的全面支持情况。

## 支持的 IDE / Supported IDEs

### VS Code
- **状态**: ✅ 完全支持
- **安装**: 通过 VSIX 包自动安装
- **功能**: 对话式入口为主；面板为辅助视图
- **命令**: `RuleFlow: One-Click Setup (Newbie)`, `RuleFlow: Ask (Natural Command)`, `RuleFlow: Open Panel`, `RuleFlow: Load Coverage`

### Cursor
- **状态**: ✅ 完全支持（复用 VS Code 扩展）
- **安装**: 通过 VSIX 包自动安装
- **功能**: 与 VS Code 完全相同
- **兼容性**: 100% VS Code 扩展兼容

### Windsurf
- **状态**: ✅ 完全支持（复用 VS Code 扩展）
- **安装**: 通过 VSIX 包自动安装
- **功能**: 与 VS Code 完全相同
- **兼容性**: 100% VS Code 扩展兼容

### JetBrains 系列
- **状态**: ✅ 完全支持
- **支持的 IDE**: IntelliJ IDEA, PyCharm, WebStorm, PhpStorm, GoLand, CLion, Rider
- **安装**: 通过插件包（Docker 构建 + 手动安装）
- **功能**: 工具窗口界面，完整命令支持，状态显示
- **特性**: Kotlin 原生实现，完整 UI 集成

### Neovim/Vim
- **状态**: ✅ 完全支持
- **安装**: Lua 插件自动安装
- **功能**: 用户命令集成，状态通知
- **命令**: `:MCPStatus`, `:MCPCoverage`, `:MCPIngest`, `:MCPGenerateCI`
- **配置**: 自动生成 `~/.config/nvim/lua/mcp-rules/init.lua`

### Sublime Text
- **状态**: ✅ 完全支持
- **安装**: Python 插件自动安装
- **功能**: 菜单集成，对话框反馈
- **位置**: Tools → MCP Rules Assistant
- **特性**: 跨平台路径自适应

### Visual Studio (Windows)
- **状态**: ✅ 完全支持
- **安装**: VSIX 扩展包
- **功能**: 工具窗口，菜单命令，解决方案集成
- **版本**: 支持 VS 2022 (17.0+)
- **特性**: C# 原生实现，完整 .NET 集成

### Eclipse
- **状态**: ✅ 完全支持
- **安装**: Eclipse 插件
- **功能**: 视图面板，菜单命令，项目集成
- **特性**: Java 原生实现，工作区集成

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
