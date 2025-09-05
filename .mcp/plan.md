# 项目计划 / Project Plan

- 状态: in_progress
- 当前步骤: 整理并统一开发文档体系，落实 TDD 逐层推进计划
- 下一步: 按层推进补齐测试与覆盖率门槛（核心≥98%、其余≥95%）
- 风险与阻塞: 无；注意保持文档与实现、配置与 CI 的一致性

摘要
- 已完成：
  - 容器无人值守看板/UI 已移除；Compose 统一为 `compose.yml`
  - `dev_agent` 仅写状态文件（无端口），文档/Makefile/测试均已对齐
  - `DEVELOPMENT.md` 作为根入口，新增 TDD 逐层计划与 AI 协作约束
- 待推进：
  - 单元/组件/集成/MCP/扩展五层测试增强与覆盖率门槛达标
  - 代码与文档的持续一致性校验（生成器/快照）

任务清单（实时驱动看板）
- [x] 单元层：`coverage_summary.py` 边界/错误分支补测，弱项归零
- [x] 组件层：`checks.py` 降级/失败缓存用例；`hooks.py` 一致性快照
- [x] 集成层：`dev_agent.py` 单循环写入与冻结/解冻分支覆盖（含自动提交/推送/打标签开关分支）
- [x] 接口层：`mcp_server.py` initialize/capabilities 及基础 tools/resources 错误路径
- [x] 扩展层：VS Code 近阈值/覆盖率加载交互回归（无头用例已覆盖关键处理与生成覆盖率 lcov）
- [x] 安装并启用 Git hooks：`make hooks` 或 `mcp-rules-assistant install-hooks`（含 commit-msg/pre-push）
- [x] Codecov 徽章与上传策略核对（公共/私有仓库）；CI 默认上传，私有仓库以 `CODECOV_TOKEN` 条件化；VS Code lcov 覆盖率预警（非阻断）
 - [x] VS Code 无头测试纳入 CI 必跑项；默认开启 `ci.vscode_required`
 - [x] 文档快照门禁：关键锚点/禁用陈旧模式/README 与 AI 指南的入口一致性

验收标准
- 覆盖率 Gate 通过（核心 ≥98%，其余 ≥95%，弱项为 0）
- 本地与 CI 均安装/启用门禁（commit-msg、pre-push、branch、TDD）
- 文档与实现完全对齐，无样例/临时工件遗留
