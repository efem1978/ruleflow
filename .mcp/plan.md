# 项目计划 / Project Plan

- 状态: in_progress
- 当前步骤: 增补 mcp_server.py/cli.py 测试，提升核心覆盖率 ≥97%（当前通过；后续继续抬升至 98%）
- 下一步: 等待 PR #23 CI 全流程通过并自动合并；随后将 mcp_server.py/cli.py 覆盖率从 ≥97% 持续抬升至 ≥98%
- 风险与阻塞: 无；本地已生成 coverage.xml，整体 96.74%，核心两处未达标

摘要
- 本次审计完成：docs 全量遍历；实现逐项对照；测试 216/216 通过；coverage 总体 96.74%。已完成：coverage.policy 改为 basename；hooks/CI 由生成器产出；near/report 动态读取配置；清理测试产物。
- 待办聚焦：
  - 覆盖率政策对齐：将 `.mcp/assistant.yaml` 的 coverage.policy 改为 basename 前缀（如 `cli.py` 而非 `mcp_rules_assistant/cli.py`），与 coverage.xml 一致。
  - 覆盖率提升：为 `mcp_server.py`（95.7%）与 `cli.py`（97.2%）补充边界/错误分支测试，达成 ≥98%。
  - CI/文档同步：在 AI_DEVELOPER_GUIDE/CONFIG 中明确 policy 写法；`generate-ci` 产物已与规则一致（secrets/hadolint/semgrep 条件化）。
  - 清理样例文件：测试创建的 `ok2.py/bad.py` 为本地工件，应清理或将相关用例切到临时目录。
