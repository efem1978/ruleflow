# 其它 IDE 完整插件化路线图 / Roadmap

目标：在保持“最小集成可用”的前提下，分阶段为 Cursor、Windsurf、JetBrains 提供“完整插件级体验”。

阶段与里程碑
- P0（现状）：
  - VS Code 扩展完整（面板/命令/资源/无头测试/CI 条件纳入）。
  - Cursor/Windsurf 可直接安装 VSIX（基于 VS Code 引擎）获得同等功能（最小集成）。
- P1（Cursor / Windsurf 提升，1–2 周）：
  - 兼容性验证矩阵（激活事件、Webview API、Node 版本）。
  - 发布通道与签名（可复用 VSIX）；安装指南与诊断文档。
  - UI 微调（标题/图标/产品名），适配各商店展示规范。
- P2（JetBrains 最小插件，2–4 周）：
  - 插件骨架（Gradle/Kotlin）：动作/工具窗口/UI 面板。
  - 调用本地 MCP Server（stdio）与资源呈现（memory/progress/coverage/ci）。
  - 受控写入（保存后检查）入口与配置面板。
  - 基本 E2E 测试（IDEA IU Headless 的 smoke）。
- P3（统一能力细节，>2 周，按需）：
  - 统一“自然语言路由”入口（命令面板/操作面板）。
  - 统一“覆盖率/近阈值/规则建议”可视化与导出。
  - 发布/升级策略与反馈/错误上报（无遥测前提下，基于本地日志与诊断包）。

范围界定
- Cursor / Windsurf：
  - 以 VSIX 直接分发；功能等同 VS Code；必要时做小幅兼容补丁。
  - 目标：0 代码分叉；统一源代码仓库。
- JetBrains：
  - 新建 `extensions/jetbrains` 模块（Gradle），后续 PR 分支推进。
  - 目标：最小可用（动作/面板/调用 MCP 端点），后续按反馈增强。

任务清单（首期）
1) 编写 Cursor/Windsurf 安装与诊断指南（本仓库内）。
2) 验证 VSIX 在 Cursor/Windsurf 的 API 兼容性（本地与 CI 报告）。
3) 产出 JetBrains 插件骨架设计（模块结构、入口点、与 server 的交互）。

备注
- 坚持“奥卡姆剃刀原则”：
  - Cursor/Windsurf 复用 VSIX；不单独分叉代码。
  - JetBrains 仅实现“必要出口 + 面板”，避免与 VS Code 面板在 UI 上过度一致而导致高成本。

