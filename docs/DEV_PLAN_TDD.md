TDD 开发计划 / TDD Development Plan

目标与范围 Goals & Scope
- 目标：以 TDD 模式完善本仓库，确保功能按文档落地；覆盖率达标（核心≥98%，非核心≥95%），测试全绿且无警告/跳过；CI/钩子具备生产级门禁。
- 范围：Python MCP Server、规则摄取/编译、覆盖率摘要、受控写入检查、Hooks/CI 生成、VS Code 扩展交互的核心路径。

覆盖率策略 Coverage Targets
- 近期：总覆盖率 85–92%（建立基线并覆盖核心路径）。
- 达标：
  - 全局 ≥95%（CI `--cov-fail-under=95`）。
  - 核心模块（config.py/progress.py/tools.py/memory.py）≥98%（由 coverage.policy 约束并在 CI 按政策阻断）。
  - 其余模块 ≥95%。

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

Phase D — 覆盖率与政策门禁（生产化）
- 在 `.mcp/assistant.yaml` 中设置政策阈值：
  - config.py/progress.py/tools.py/memory.py → 0.98
  - 其余由 `min_module: 0.95` 统一控制
- CI 增加 “Coverage Policy Gate”：
  - 运行 `coverage-report --json`，若存在 `weak` 文件即失败
  - 新增无 skip/xfail 标记检查；继续维持 `-W error`

Phase E — 集成与 CLI
- CLI（Typer）烟雾测试：init / ingest-rules / coverage / coverage-groups。
- MCP 集成：tools/call rules.ingest/validate、fs.apply_patch(strict) 正常与拒绝路径、resources/read 各类 URI。

验收准则 Definition of Done
- 覆盖率：总体 ≥95%；核心模块 ≥98%；其余 ≥95%；`coverage-report` 的 `weak` 为空。
- 钩子/CI：
  - pre-push：pytest+cov 阈值阻断、bandit、禁止 skip/xfail、Docker 基线（如启用）
  - CI：ruff/black/isort、mypy（核心阻断，非核心观察）、pytest+cov、Coverage Policy Gate、bandit、可选 hadolint/semgrep/Dockerfile 检查。
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
1) PR-A：coverage_summary 类型收敛（TypedDict、排序 key 与数值转换），mypy 告警减至 <5。
2) PR-B：checks 事件/计数结构加强类型；mypy 告警减至 <3。
3) PR-C：mcp_server 与 cli 的关键路径类型补全；将其纳入“核心阻断”清单。
4) 将 CI 的 mypy 阶段从“核心四模块”扩展到 coverage_summary/mcp_server/cli（分步提交）。
5) 对照 Codecov/near 报告，补少量边界用例，确保持续满足核心≥98%、非核心≥95%。
