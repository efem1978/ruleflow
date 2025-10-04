# IDE 安全安装与隔离说明 / IDE Security & Isolation

本页给出 VS Code / Cursor / JetBrains 三端的“安全安装、隔离与注意事项”。本工具在所有 IDE 中默认启用严格隔离（Strict Isolation），不会因环境变量而开启记忆写入；仅在项目 `.mcp/assistant.yaml` 显式 `memory.allow_write: true` 时，才允许写入 `.mcp/memory.json`。

## 通用安全要点（适用于所有 IDE）
- 严格隔离：扩展启动后端时以 `MCP_STRICT_ISOLATION=1` 运行。
  - 仅当 `.mcp/assistant.yaml` 中 `memory.allow_write: true` 时才允许写记忆。
  - `project.switch` 默认拒绝（避免跨项目写入）。
  - 记忆路径强校验：仅允许 `<project_root>/.mcp`；读取同样受限且默认拒绝通过符号链接与硬链接读取（防跨项目“借读/共享”）。如需放宽，可显式设置 `MCP_MEMORY_TRUST_SYMLINK=1` 或 `MCP_MEMORY_TRUST_HARDLINK=1`。
- 硬禁用（最高优先级）：`memory.hard_disable: true` → 任何来源一律拒绝写入。
- 全局紧急硬禁用：设置 `MCP_MEMORY_HARD_DISABLE=1` → 进程内一切记忆写入被拒（应急场景）。
- 安全审计：拒写/越界/切换被拒等事件写入 `.mcp/dashboard/security_audit.jsonl`（逐行 JSON）。

## VS Code（推荐路径）
### 安装（隔离目录）
1) 指定 VS Code CLI，避免被 Cursor 接管的 `code`：
```
export VSCODE_BIN="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
```
2) 安装到工作区隔离目录：
```
bash scripts/vscode_isolated_install.sh
```
3) 启动（完全隔离）：
```
"$VSCODE_BIN" . --extensions-dir '.mcp/vscode-extensions' --user-data-dir '.mcp/vscode-user'
```

### 项目级策略示例
```
memory:
  allow_write: false      # 默认关闭
  # hard_disable: true    # 推荐给“绝不写入”的项目
project:
  allow_switch: false     # 禁止跨项目切换（严格隔离默认）
```

## Cursor（保持功能一致，避免脚本触碰）
- 安装：在 Cursor 的扩展面板选择 “Install from VSIX…”，手动选择本项目生成的 VSIX。
- 建议：不使用脚本安装/卸载；我们的脚本默认跳过 Cursor，避免唤起 Cursor 窗口。
- 运行时行为与 VS Code 完全一致：严格隔离、写入需 allow_write、硬禁用优先、路径强校验、审计日志。

## JetBrains（IDEA/PyCharm 等）
- 运行工具窗口“RuleFlow”：启动/停止 MCP、自然语言命令、加载计划/记忆/覆盖率、受控写入。
- 生成 UI 验证材料（smoke）：`bash scripts/jb-ui-verify.sh`。
- 安全策略与 VS Code 相同（strict/hard_disable/path 校验/审计）。

## 批量加固与验证（多项目）
```
python3 scripts/harden_projects.py --verify /path/to/projA /path/to/projB
```
- 为每个项目写入：`memory.hard_disable: true`、`memory.allow_write: false`、`project.allow_switch: false`。
- 生成 `.mcp/dashboard/security_verify.json` 拒写验证日志。
