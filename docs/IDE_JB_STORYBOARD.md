JetBrains 插件替代方案（无需安装） / JetBrains Storyboard (No-IDE)

目的
- 在未安装 JetBrains 的环境下，复现插件面板会展示的数据内容（计划/记忆/覆盖率/受控写入dry-run）。
- 产物直接落到 `extensions/jetbrains/screenshots/`，供 README/文档引用或审阅。

用法
1) 生成覆盖率（如已有 `coverage.xml`）与状态：
   - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml`（可选）
   - `python3 -m mcp_rules_assistant.cli status-update`（可选）
2) 运行脚本生成 Storyboard：
   - `sh scripts/jb-storyboard.sh`

生成物（位于 `extensions/jetbrains/screenshots/`）
- `jb_plan.md`: 计划 Markdown（等价于工具窗口“打开计划”）
- `jb_memory.json`: 最近 20 轮记忆（等价于“加载记忆”）
- `jb_coverage_report.json`: 覆盖率报告 JSON（等价于“coverage.report”）
- `jb_fs_apply_patch_dry.json`: 受控写入（严格 + 干跑）返回 JSON（等价于 fs.apply_patch 对话框 Dry-Run）

说明
- 这些 JSON/MD 文件即为 JetBrains 工具窗口中展示的数据内容；插件只是以 UI 呈现。
- 若缺少 `coverage.xml`，脚本会跳过生成 `jb_coverage_report.json` 并给出 WARN 日志。
- `fs.apply_patch` 采用 `docs/jb_demo.md` 作为示例路径，严格/干跑下不会落盘；实际写入请在插件 UI 或 CLI 中根据项目策略执行。

后续（可选）
- 当获取到 JetBrains 实拍截图后，可将现有 SVG 示意图替换为 PNG 并更新 README 引用。
- CI 已包含 JetBrains Gradle 编译作业（compile-only），保障 Kotlin 源码可编译性。

