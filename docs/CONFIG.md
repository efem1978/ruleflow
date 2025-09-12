配置与双语命令 Config & Bilingual Commands

项目配置 Project Config
- 路径：`.mcp/assistant.yaml`（项目）与 `~/.mcp/assistant.yaml`（全局）
- 合并：全局 <- 项目（项目覆盖）

示例 Example
```yaml
performance:
  mode: fast
  on_save:
    format_on_save: true
    lint_changed_only: true
    typecheck_incremental: false
    quick_tests: false
  on_commit:
    lint: true
    typecheck_incremental: true
    test_impacted: true
  on_push:
    test_all: true
    coverage: {enforce: true, min_module: 0.9, min_core: 0.95}
    security_scan: true
    mutation_test: false
language: python
bilingual: true
coverage:
  policy:
    "src/core/": 0.95  # 核心模块更高阈值
    "src/": 0.90      # 其余模块保持 90%
tests:
  quick_fail_decay:
    high_days: 3      # 近3天失败权重
    high_bonus: 2
    mid_days: 7       # 近7天失败权重
    mid_bonus: 1
    history_limit: 400
ci:
  hadolint: false            # 在 CI 中启用 hadolint（Dockerfile lint），默认关闭
  # 建议固定镜像标签以确保可重复性（本仓库与生成器使用 2.12.0）
  hadolint_image: "hadolint/hadolint:2.12.0"  # 运行用的容器镜像（固定版本）
  hadolint_args: ""          # 额外参数（可留空）
  semgrep_config: "auto"     # SAST 配置（规则集），如：p/ci, p/security-audit 等
  vscode_required: true       # VS Code 扩展测试是否必跑（默认 true；true 时不再使用 if: hashFiles 条件）
  mutation_gate_strict: false # 严格门禁：为 true 或 performance.mode=strict 时，CI 中的变异测试作为硬门禁（默认非阻断）
```

说明（coverage.policy 键的写法）
- 匹配规则：同时支持“前缀匹配（prefix）”与“后缀匹配（basename）”。工具将先尝试前缀匹配，未命中则回退到后缀匹配。
- 因此，既可以写目录前缀（如 `mcp_rules_assistant/` 或 `src/core/`），也可以直接写文件名（如 `cli.py`、`mcp_server.py`）。
- 建议做法：
  - 若要对一类目录生效，使用目录前缀：`mcp_rules_assistant/`: 0.95。
 - 若要对单个模块设更高门槛，使用文件名后缀：`cli.py: 0.98`、`mcp_server.py: 0.98`。

命令 Commands（中英 + 模糊）
- 开启滚动记忆 / enable rolling memory / 记忆开 / auto-memo on
- 查看计划 / show plan
- 应用改动 / apply patch
- 加载覆盖率 / load coverage

CLI
- `mcp-rules-assistant init`
- `mcp-rules-assistant print-config`
- `mcp-rules-assistant explain-performance`
- `mcp-rules-assistant rules-onboard --scenario personal --complexity small --dev-mode tdd`  # 规则引导：根据场景/复杂度/模式应用推荐阈值
- `mcp-rules-assistant prepare-env`  # 创建 .mcp/venv 并可选安装工具（支持 --dry-run）
- `mcp-rules-assistant ci-set --hadolint --hadolint-image hadolint/hadolint:latest --hadolint-args "--ignore DL3008"`
- `mcp-rules-assistant ci-set --semgrep-config p/ci`
- `mcp-rules-assistant ci-set --vscode-required`  # 将 VS Code 扩展测试设为“必跑”
- `mcp-rules-assistant insert-security-samples`  # 在项目根插入 `.semgrep.yml` 与 `.hadolint.yaml` 示例
- `mcp-rules-assistant ci-validate`  # 校验 CI 工作流关键步骤
- `mcp-rules-assistant ci-autofix`   # 自修复/覆盖生成 CI（备份原文件）
- `mcp-rules-assistant coverage-tree`  # 输出覆盖率薄弱文件目录树（前3层）
- `mcp-rules-assistant coverage-near --within 3 --top 20`  # 输出“近阈值”（未低于阈值但距离≤3%）的文件
- `mcp-rules-assistant coverage-near-set --within 5 --top 10`  # 设置“近阈值”窗口（百分比）与 Top N
- `mcp-rules-assistant enforce`  # 应用已编译规则到配置并输出门禁摘要
 - `mcp-rules-assistant plan-set --status in_progress --current <步骤> --next-step <下一步>`  # 快捷设置计划字段
- `mcp-rules-assistant rules-validate`  # 校验规则（基于已摄取原始数据）并输出冲突/建议摘要
 - `mcp-rules-assistant rules-suggestions --format json|csv`  # 导出建议清单（含 severity/action/value）
 - `mcp-rules-assistant coverage-clean-cache`  # 删除覆盖率解析缓存（.mcp/coverage_cache.json）
- `mcp-rules-assistant coverage-report --json`  # 一次性输出弱项/分组/近阈值（默认 JSON）

近阈值窗口（near）说明
- 文档示例默认窗口为 3%（即 `within=0.03`）。本仓库为便于抛光核心模块，将项目配置覆盖为 0.8%（`coverage.near.within=0.008`）。
- 工具允许的窗口范围为 1–10%（CLI/报告会按需夹紧到该范围）。
- 可用 CLI 快速调整：`mcp-rules-assistant coverage-near-set --within 3 --top 20`（将窗口改回 3%，Top=20）。
- 读取/导出近阈值：`mcp-rules-assistant coverage-near --within 3 --top 20 --format json`。

配置更新（config.update）兼容性
- 推荐：`tools/call name="config.update" {"data": {"mutation_gate_strict": true, "execution": {"checks_delegate_run_cmd": true}}}`
- 兼容：未提供 `data` 时，可直接传入顶层键：`{"mutation_gate_strict": true, "execution": {"checks_delegate_run_cmd": true}}`

配置拓展（可选 Optional）
```yaml
rules:
  conflict_delta: 0.05       # 规则冲突阈值（覆盖率等数值差异 > 该值 视为冲突），默认 0.05（5%）
  # 或按键覆盖（覆盖全局默认）：
  # conflict_delta:
  #   coverage.min_module: 0.05
  #   coverage.min_core: 0.02

execution:
  # 允许 fs.apply_patch 写入的相对路径前缀白名单；为空表示不限制
  # 例如：限制只能改动包代码、测试、文档与 .mcp 工件
  allowed_write_prefixes:
    - "mcp_rules_assistant/"
    - "tests/"
    - "docs/"
    - ".mcp/"
  # checks 委托到统一 process runner（可选，默认关闭；也可用环境变量 MCP_CHECKS_PROCESS_RUNNER=1 开启）
  checks_delegate_run_cmd: false
  # 可选：禁用片段命中时升级为硬门禁（默认 false；命中 disallow_patterns 直接拒绝写入）
  # disallow_patterns: ['import pdb', 'os.system(']
  disallow_patterns_hard: false

组合建议（只读/严格/限制）
- 只读保护：`execution.readonly: true` 时，`fs.apply_patch` 在非 dry-run 下将被拒绝（可用于冻结窗口）。
- 文件/内容限制：`max_files` 与 `max_content_bytes` 可限制一次写入的文件数量与单文件大小（默认 100、512KB）。
- 路径/扩展白名单：同时设置 `allowed_write_prefixes` 与 `allowed_write_extensions`，精确约束可改动范围。
- 严格挂钩：开启 `fs_guard_post_checks: true` 与 `fs_guard_strict: true`，写入后若增量 lint/type/tests 失败，将直接阻断（与 `fs.apply_patch --strict` 语义一致）。

注意与实践建议
- 符号链接：fs.apply_patch 默认拒绝写入符号链接目标（避免路径混淆）。
- disallow_patterns：默认“软拦截”（记录/提示）。如需将其提升为硬门禁，请设置 `execution.disallow_patterns_hard: true`；
  仍保持 `pytest.mark.skip/xfail` 在 strict 情况下的硬阻断语义不变。

license:
  # 是否启用许可硬门禁：开启后，部分敏感操作（rules.enforce / ci.generate / ci.validate / ci.autofix / git.install_hooks）
  # 需通过 license-verify 校验（演示支持 hs256/rs256）。默认 false。
  required: false
```

维护与兼容建议
- 预提交阶段命名：pre-commit v4 推荐使用 Git 钩子名作为 stage（如 `pre-commit`/`pre-push`）。
  - 如需将现有 `.pre-commit-config.yaml` 的 `stages: [commit/push]` 批量迁移，可运行：
    - `mcp-rules-assistant precommit-migrate-stages`
- CI 工具版本固定：建议固定 hadolint/semgrep 版本以提升构建可重复性；本仓库生成的 CI 已固定 semgrep（pip 安装）与 hadolint（容器镜像）版本，仍可在 `ci-set` 中覆盖。

可选开关（摘要）
- `execution.checks_delegate_run_cmd`：为 true（或 `MCP_CHECKS_PROCESS_RUNNER=1`）时，`checks.py` 将在内部委托 `process.run_cmd` 执行外部命令；默认保持旧实现以兼容历史测试桩。
- `ci.mutation_gate_strict`：为 true（或 `performance.mode: strict`）时，CI 的变异测试变为硬门禁；否则为非阻断（`|| true`）。
