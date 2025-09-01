TDD 开发计划 / TDD Development Plan

目标与范围 Goals & Scope
- 目标：以 TDD 模式完善本仓库，确保功能按文档落地，覆盖率达标（模块≥90%，核心≥95%）。
- 范围：Python MCP Server、规则摄取/编译、覆盖率摘要、受控写入检查、Hooks/CI 生成、VS Code 扩展交互的核心路径。

覆盖率策略 Coverage Targets
- 近期：总覆盖率 65–75%（建立基线与关键路径用例）。
- 强化：总覆盖率 80–88%（规则解析/覆盖率/检查分支补齐）。
- 达标：coverage.policy — { "mcp_rules_assistant/": 0.95, ".": 0.90 }。

分阶段执行 Phased Plan
Phase A — 基线与修复（Red → Green → Refactor）
- 写“红”用例：config.get/update、rules.enforce。
- 实现修复：
  - config.get/update：使用 `.mcp/assistant.yaml` 与 yaml.safe_load/dump；替换未定义符号。
  - rules.enforce：将 `.mcp/rules_compiled.json` 的阈值合并入配置（min_module/min_core）。
- 小重构：最小可读性与错误处理增强（不改对外行为）。

Phase B — 规则与覆盖率（核心逻辑）
- rules_ingest：
  - 文本/YAML/JSON 摄取、规则键识别、5% 冲突判定、更严格值合并、建议生成。
  - 表征测试：对真实样例文档集保持稳定输出。
- coverage_summary：
  - summarize / summarize_groups 针对最小 coverage.xml 样例的正确性与策略分组。

Phase C — 检查与门禁（边界与降级）
- checks：
  - 受影响测试（索引/导入匹配、失败缓存与近期加权）。
  - 工具缺失降级分支（ruff/mypy/pytest 不存在时返回 skipped）。
- hooks：
  - render_github_ci_yaml 条件步骤（secrets/hadolint/semgrep/Dockerfile 检查）。
  - generate_pre_commit_config 启动 secrets 与 Docker 基线（push 阶段）。

Phase D — 集成与 CLI
- CLI（Typer）烟雾测试：init / ingest-rules / coverage / coverage-groups。
- MCP 集成：tools/call rules.ingest/validate、fs.apply_patch(strict) 正常与拒绝路径、resources/read 各类 URI。

验收准则 Definition of Done
- 覆盖率：总体 ≥90%，`mcp_rules_assistant/` ≥95%（coverage.policy 落盘）。
- 钩子/CI：pre-push 跑 pytest+cov（阈值阻断）、bandit；CI 含 ruff/black/isort/mypy/pytest+cov/bandit，按规则启用 hadolint/semgrep/Dockerfile 检查。
- VS Code 面板：规则/建议/覆盖率资源可加载；CI 配置可读写；安装钩子与生成 CI 可用。

风险与缓解 Risks & Mitigations
- 外部工具缺失：使用“跳过/降级”分支，测试注入替身或检查返回字段 `skipped`。
- 规则解析多样性：以表征测试绑定样例，避免过度拟合；后续用 schema 约束。
- 覆盖率波动：先按模块阈值推进，核心代码优先补齐。

工件与沟通 Artifacts & Communication
- 计划：`.mcp/plan.md`（状态/当前步骤/下一步）；本文件 `docs/DEV_PLAN_TDD.md`。
- 覆盖率：`coverage.xml` 与 CLI 输出（薄弱项/分组）。
- 规则：`.mcp/rules_compiled.{json,md}` 与 `rules_suggestions.md`。

近期待办 Next Actions
- 修复 config.get/update、实现 rules.enforce → 通过已有“红”用例。
- 写 coverage.policy 到 `.mcp/assistant.yaml` 并生成 CI；提交“绿”。
- 进入 Phase B，完善 rules_ingest/coverage_summary 用例提升覆盖率至 >70%。

