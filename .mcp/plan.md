# 项目计划 / Project Plan

- 状态: in_progress
- 当前步骤: 全面代码与文档一致性审计、覆盖率与门禁策略核对
- 下一步: 统一阈值与生成物(版本/CI/hooks)、补齐 AI_DEVELOPER_GUIDE、决定 hadolint/semgrep 策略开关
- 风险与阻塞: 本地环境缺少 pytest 无法生成实时覆盖率；需在 CI 或开发机验证

摘要
- 本次审计完成：docs 全量遍历；与实现逐项对照；发现若干不一致（阈值/生成物/版本）；占位模块与改进点已梳理。
- 待办聚焦：
  - 版本号对齐：pyproject 与 __init__ 不一致
  - 统一覆盖率阈值来源（配置 vs 生成的 CI/hooks 里的硬编码）
  - 根据规则/配置决定是否启用 hadolint/semgrep（而非无条件）
  - 新增 AI_DEVELOPER_GUIDE.md（按文档体系补齐）
  - 可选：将测试夹带样例文件迁移到 tests/fixtures（或保留并标注用途）

