使用指南 Usage Guide

常用流程 Common Flows

1) 初始化与规则摄取
- mcp-rules-assistant init
- mcp-rules-assistant ingest-rules README.md docs/
- mcp-rules-assistant rules-explain --json --with-suggestions short

2) 应用门禁与生成 CI
- mcp-rules-assistant enforce
- mcp-rules-assistant generate-ci

2.1) 规则引导（前置问答/快速建档）
- mcp-rules-assistant rules-onboard --scenario personal --complexity small --dev-mode tdd
- VS Code 面板：自然语言输入“规则引导/初始化规则”，按提示选择后自动应用

3) 覆盖率
- mcp-rules-assistant coverage
- mcp-rules-assistant coverage-groups
- mcp-rules-assistant coverage-report --json > coverage_report.json
- 导出追踪报表（CSV/JSON 到 .mcp/dashboard）：
- mcp-rules-assistant coverage-export --out-dir .mcp/dashboard --weak-top 20 --near-top 50 --within 3
- mcp-rules-assistant coverage-clean-cache  # 如遇到缓存不一致

4) 建议导出
- mcp-rules-assistant rules-suggestions --format json --output suggestions.json
- mcp-rules-assistant rules-suggestions --format csv --output suggestions.csv

5) 诊断
- mcp-rules-assistant diagnose --json > diagnose.json

6) 许可与试用（License & Trial）
- 查看状态：`mcp-rules-assistant license-status`
- 离线激活：`mcp-rules-assistant license-activate --file path/to/license.json`
- 校验签名：`mcp-rules-assistant license-verify`
- 发布前硬门禁演练（可选）：`make release-harden-on` 启用、`make release-harden-off` 关闭
 - 一键校验脚本：`sh scripts/release-harden-verify.sh`（开启门禁→验证 MCP 端口令→关闭）

7) VS Code 使用
- 面板：命令面板运行 `RuleFlow: Open Panel`（或点击状态栏左侧“RuleFlow”）
- 面板顶部自然语言：在输入框直接输入“摄取规则 README.md, docs/ / 加载覆盖率 / 开启滚动记忆”等回车执行；支持最近历史与快速范例
- 命令面板自然语言：`RuleFlow: Natural Command`
- Copilot 集成（可选）：按 `docs/COPILOT_MCP.md` 使其出现在 Copilot 的 MCP 面板
- 受限环境：`export MCP_VSCODE_TEST_ARGS="" && npm --prefix extensions/vscode test`

8) 多项目记忆（命名空间）
- 开启并绑定到子项目/命名空间：
  - `tools/call name="memory.toggle_auto" {"on": true, "project": "pkgA"}`
  - 或 `tools/call name="memory.toggle_auto" {"on": true, "scope": "experiments"}`
- 作用：在 `.mcp/` 生成独立的命名空间文件（例如 `.mcp/memory.pkgA.json`），避免多个子项目的对话记忆混淆，同时保留跨项目“链接”。
- 读取命名空间记忆：
  - 资源：`memory://<projectId>/rollup?ns=pkgA`（等价于读取 `.mcp/memory.pkgA.json` 的聚合快照）
  - 链接列表：`memory://<projectId>/links`
- 关闭自动记忆：`tools/call name="memory.toggle_auto" {"on": false}`
- 提示：也可使用 `project.switch`/`project.link` 记录项目切换与跨项目关联；面板“加载记忆/加载计划”会读取上述资源以保持 AI 与人类可读的一致视图。
 - 快速切换/关联（示例）：
   - `tools/call name="project.switch" {"path": "./packages/pkgA"}`
   - `tools/call name="project.link" {"project": "pkgB", "task": "integration", "note": "pkgA -> pkgB"}`
