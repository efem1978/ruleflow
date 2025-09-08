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
- 集成：
  - 启动/调用本地 MCP Server（stdio），或复用现有进程。
  - 受控写入（保存后检查）入口与配置。

边界与原则
- 不复制 VS Code 前端；以“最小可用”为目标。
- 与 Python 端通过 JSON-RPC 交互，严格遵守错误码约定（见 `docs/MCP.md`）。

里程碑
- M1：项目骨架（plugin.xml、Gradle、Hello ToolWindow）
- M2：调用 MCP `resources/list`/`resources/read` 展示 plan/memory/coverage
- M3：动作菜单与命令路由（rules.ingest / coverage.report / ci.generate）
- M4：受控写入（fs.apply_patch）入口与结果提示
- M5：打包、离线安装、基础冒烟测试

目录
- 后续将在 `extensions/jetbrains/` 内建立 Gradle 项目；当前为计划说明，待你确认后启用。

