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
  hadolint_image: "hadolint/hadolint:latest"  # 运行用的容器镜像
  hadolint_args: ""          # 额外参数（可留空）
  semgrep_config: "auto"     # SAST 配置（规则集），如：p/ci, p/security-audit 等
  vscode_required: true       # VS Code 扩展测试是否必跑（默认 true；true 时不再使用 if: hashFiles 条件）
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

配置拓展（可选 Optional）
```yaml
rules:
  conflict_delta: 0.05       # 规则冲突阈值（覆盖率等数值差异 > 该值 视为冲突），默认 0.05（5%）
  # 或按键覆盖（覆盖全局默认）：
  # conflict_delta:
  #   coverage.min_module: 0.05
  #   coverage.min_core: 0.02
```
