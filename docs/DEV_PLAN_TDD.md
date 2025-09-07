TDD 开发计划 / TDD Development Plan

目标与范围 Goals & Scope
- 目标：以 TDD 模式完善本仓库，确保功能按文档落地；覆盖率达标（核心≥98%，非核心≥95%），测试全绿且无警告/跳过；CI/钩子具备生产级门禁。
- 范围：Python MCP Server、规则摄取/编译、覆盖率摘要、受控写入检查、Hooks/CI 生成、VS Code 扩展交互的核心路径。

覆盖率策略 Coverage Targets（目标示例，非门禁；门槛以 `.mcp/assistant.yaml` 为准）
- 近期：目标区间 85–92%（建立基线并覆盖核心路径，非门禁）。
- 达标（示例）：
  - 全局目标 95% 以上（CI 可用 `--cov-fail-under` 控制；以配置为准）。
  - 核心模块目标更高（如 98% 以上，受 `coverage.policy` 约束并在 CI 按政策阻断）。
  - 其余模块目标 95% 以上。

分阶段执行 Phased Plan（逐层推进）
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

逐层检查清单 Layered Checklists（可作为执行清单）
- 单元层（config/progress/tools/memory/coverage_summary）
  - [ ] 为公开函数补齐失败用例（边界/异常/类型）
  - [ ] 通过后重构（去重/提取），保证对外行为不变
  - [ ] 覆盖率：核心≥98%，其余≥95%
- 组件层（checks/hooks/fs_wrapper）
  - [ ] 工具缺失降级（ruff/mypy/pytest 缺失 → skipped）
  - [ ] 最近失败优先的受影响测试策略
  - [ ] 生成的 CI/Hooks 与配置一致性快照
- 集成层（cli/dev_agent）
  - [ ] CLI 烟雾与参数校验
  - [ ] dev_agent 单循环：写入 status.json/history/fail_counters
  - [ ] 冻结/解冻阈值与逻辑路径覆盖
- 接口层（mcp_server）
  - [ ] initialize/capabilities & 基础 tools/resources 的错误路径
  - [ ] fs.apply_patch(strict) 拒绝路径
- 扩展层（VS Code）
  - [ ] 无头测试 & 近阈值/覆盖率交互回归

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

近期待办 Next Actions（与根目录 DEVELOPMENT.md 同步）
已完成（对齐项）
 - 用生成器覆盖 .pre-commit-config.yaml 与 .github/workflows/ci.yml，阈值取自 .mcp/assistant.yaml；detect-secrets 改为 push 阶段；CI 条件化步骤生效。
 - 覆盖率策略改为与 coverage.xml 一致的 basename 前缀，核心≥98% 实际受控。
 - FSGuard 写入后置挂钩：支持 execution.fs_guard_post_checks 与 fs_guard_strict（严格模式失败阻断）。
 - VS Code Webview 近阈值交互修复：采用 postMessage → 扩展侧调用 MCP，再回传结果。
 - MCP prompts 能力对齐：实现 prompts/list 与 prompts/get 最小占位端点。
 - 依赖精简：已无 pydantic。
 - 版本号对齐：pyproject.toml 与 mcp_rules_assistant/__init__.py 已一致（0.2.3）。

1) 统一门槛来源与生成物（高优先级，持续）
   - 持续校验生成物与配置一致性；文档与实现保持同频（已将 env.prepare 更新为“可创建 venv 并可选安装工具”）。
2) 清理与结构
   - 将根部样例/临时工件迁移或忽略：bad.py/ok2.py（测试运行产生）不入库；将 cov.json/cjson.json 移除并加入 .gitignore；README 标注为生成型工件。
3) 覆盖率与类型
   - 保持核心≥98%、其余≥95%；跟踪 near 报告稳定性；压降非核心 mypy 告警。
4) Codecov 行为对齐
   - CI 增加 codecov 上传（公共仓库免 token；私有使用 CODECOV_TOKEN）。
5) pre-commit 本地脚本生成时机
   - install-hooks 首次引导并写入 .mcp/plan_gate.py 与（按规则）.mcp/dockerfile_gate.py；或在生成器中按需条件生成。
