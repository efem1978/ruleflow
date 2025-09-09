# JetBrains 插件计划 / JetBrains Plugin Plan

目标
- 为 IDEA 平台提供“完整插件级体验”：工具窗口 + 命令动作 + 调用本地 MCP Server + 资源展示。

范围（首期 P2）
- 技术栈：Gradle + Kotlin；使用 JB 平台 SDK。
- 窗口：RuleFlow 工具窗口（显示 plan/memory/coverage/ci）。
- 动作：
  - “摄取规则 / Ingest rules”
  - “生成 CI / Generate CI”
  - “加载覆盖率 / Load Coverage”
  - “自然语言指令 / Natural Command”
  - “启动/停止 MCP / Ping / 资源列表 / 加载计划 / 规则摄取 / 覆盖率报告 / 生成 CI / 校验 CI / 安装 hooks / 受控写入(fs.apply_patch)”（最小直连）
- 集成：
  - 启动/调用本地 MCP Server（stdio），或复用现有进程。
  - 受控写入（保存后检查）入口与配置。

边界与原则
- 不复制 VS Code 前端；以“最小可用”为目标。
- 与 Python 端通过 JSON-RPC 交互，严格遵守错误码约定（见 `docs/MCP.md`）。

里程碑（进度）
- M1（已完成）：项目骨架（plugin.xml、Gradle、工具窗口）
- M2（已完成）：最小 MCP 直连（启动/请求）；支持 `resources/list` 与 `resources/read`
- M3（已完成）：动作菜单与命令路由（rules.ingest / coverage.report / ci.generate / ci.validate / git.install_hooks）
- M4（已完成）：受控写入（fs.apply_patch）入口（单文件/多文件、dry-run/strict）与结果展示
- M5（计划）：打包、离线安装、基础冒烟测试

目录
- 已在 `extensions/jetbrains/` 建立 Gradle 项目与最小实现（ToolWindow + MCP 直连）。

无 IDE 替代方案（Storyboard）
- 未安装 JetBrains 也可复现面板展示的数据内容，参见：`docs/IDE_JB_STORYBOARD.md`
- 执行 `sh scripts/jb-storyboard.sh` 即可在 `extensions/jetbrains/screenshots/` 生成 `jb_*.{json,md}` 样例输出。

运行（开发）
- 打开该子目录作为项目，使用 IntelliJ IDEA Community 2023.1+
- Gradle 面板运行 `Run Plugin`；或使用 `./gradlew runIde`
- 在新启动的 IDE 实例中打开目标仓库，打开工具窗口“RuleFlow”，即可使用上述按钮

输出与便捷操作
- JSON 美化：勾选“JSON 美化”开关，美化 resources/read 与 tools/call 输出
- 复制输出：点击“复制输出”复制当前文本到剪贴板
- 保存输出：点击“保存输出”保存当前文本到文件

受控写入（fs.apply_patch）
- 按钮：“MCP: 受控写入(dry-run)” 与 “MCP: 受控写入(严格写入)”
- 输入：相对路径（如 `mcp_rules_assistant/tmp_demo.py`）与多行内容
- 行为：严格模式禁止内容包含 `pytest.mark.skip/xfail`；白名单/扩展名/大小限制与项目配置一致

截图（示意）
> 当前为示意 SVG，后续将替换为实际运行截图（PNG）。
- ToolWindow（计划/记忆）：`screenshots/jetbrains-toolwindow-plan.svg`
- 覆盖率报告：`screenshots/jetbrains-coverage-report.svg`
- 受控写入对话框：`screenshots/jetbrains-fs-apply-patch.svg`

JSON 示例（coverage.report）
```json
{
  "weak": [],
  "groups": [
    {"prefix": "mcp_server.py", "coverage": 0.983, "threshold": 0.98},
    {"prefix": "dev_agent.py", "coverage": 0.9513, "threshold": 0.95}
  ],
  "near": [
    {"file": "mcp_server.py", "coverage": 0.983, "threshold": 0.98}
  ],
  "min_module": 0.96
}
```
