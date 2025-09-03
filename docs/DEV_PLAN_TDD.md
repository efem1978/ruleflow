TDD 开发计划 / TDD Development Plan

目标与范围 Goals & Scope
- 目标：以 TDD 模式完善本仓库，确保功能按文档落地；覆盖率达标（核心≥98%，非核心≥95%），测试全绿且无警告/跳过；CI/钩子具备生产级门禁。
- 范围：Python MCP Server、规则摄取/编译、覆盖率摘要、受控写入检查、Hooks/CI 生成、VS Code 扩展交互的核心路径。

覆盖率策略 Coverage Targets
- 近期：总覆盖率 85–92%（建立基线并覆盖核心路径）。
- 达标：
  - 全局 ≥95%（CI `--cov-fail-under=95`）。
  - 核心模块（示例：config/progress/tools/memory/mcp_server/cli/server）≥98%（由 coverage.policy 约束并在 CI 按政策阻断）。
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
1) 统一门槛来源与生成物（高优先级）
   - 用生成器覆盖 .pre-commit-config.yaml 与 .github/workflows/ci.yml，阈值取自 .mcp/assistant.yaml（performance.on_push.coverage.min_module）与 coverage.policy。
   - 修正文档与实现的描述差异（env.prepare 不再仅“占位”）。
2) 版本对齐与小修复
   - 统一版本号：pyproject.toml vs mcp_rules_assistant/__init__.py。
   - rules_ingest._english_words_to_int 移除不可达 return；注释矫正。
3) FSGuard 增强（可选）
   - 写入后置挂钩可调用 checks.run_checks（按性能模式/strict 控制），失败时在 strict 下阻断。
4) 新增 AI_DEVELOPER_GUIDE.md（文档缺口）
   - 面向贡献者：架构综述、开发规范、性能模式、规则摄取/门禁路径、测试与覆盖率策略、CI/CD 与发布流程、VS Code 面板调试。
5) 覆盖率“核心≥98%”可操作化
   - 提供 coverage.policy 示例与“核心模块”清单写法；在 README/USAGE 中链接说明。
6) CI 安全步骤条件化
   - hadolint/semgrep 由编译规则或 ci-set 开关决定（默认不强制）。
7) 清理与结构
   - 评估将根部样例文件（bad.py/foo.py/ok2.py）迁移至 tests/fixtures 并在 README 标注用途。
8) 验证与指标
   - 本地/CI 跑覆盖率并生成 near 报告，确保核心≥98%、其余≥95%；mypy 告警持续压降（核心阻断，其余非阻断）。
9) VS Code 面板交互修复（高优先级）
   - Webview 中“仅看近阈值/Show Near”不应直接调用 vscode.window/client（Webview 无权访问）；改为 postMessage（带窗口参数），在扩展侧调用 MCP，再回传结果渲染。
10) MCP 能力声明对齐
   - initialize.capabilities 声明了 prompts:true，但当前未提供 prompts/list 或相关端点；修正为不声明或补齐最小占位。
11) Codecov 行为对齐
   - README 声明“公共仓库无需令牌”，而 CI 仅在 CODECOV_TOKEN 存在时上传；需调整为公共仓库分支不要求 token（或在文档中调整表述）。
12) pre-commit 本地脚本生成时机
   - 现有 .pre-commit-config.yaml 引用 .mcp/plan_gate.py 与 .mcp/dockerfile_gate.py；需保证 install-hooks 生成后再触发相关阶段，或将其改为条件生成，避免首次运行缺文件失败。
13) 依赖精简
   - pyproject.toml 中 pydantic 未被使用（仓库代码无引用）；考虑移除以缩小依赖面。
