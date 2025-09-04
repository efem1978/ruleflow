MCP 规则与上下文助手 / MCP Rules & Context Assistant

以“插件 + MCP Server”模式，提供跨 IDE 的上下文滚动记忆、编程规则强约束、
包裹式改动门禁与性能优先的开发体验。默认启用“快速内环（Fast Inner Loop）”，
将重型检查后移到推送/CI，尽量把保存和小步迭代的开销压到最低。

- 语言 Language: Python (Server) + TypeScript (VS Code extension)
- 模式 Mode: VS Code 插件 + MCP Server（可独立使用 CLI/CI）
- 双语 Bilingual: 所有命令/提示/文档均支持中英文

关键能力 Highlights
- 20 轮滚动记忆（自动压缩/跨项目隔离/关系边）
- 通用规则包 + 项目级规则摄取/去重/冲突检测
- 包裹式改动：写入/提交/推送统一经过门禁（lint/type/test/cov/security）
- 性能优先：保存时仅增量与缓存；重型校验集中在 pre-push/CI
- 自然语言命令（中英双语 + 模糊语义）

状态 Status

![CI](https://img.shields.io/github/actions/workflow/status/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/ci.yml?branch=main&label=CI)
![Release](https://img.shields.io/github/v/tag/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool?label=release)
![Coverage](https://codecov.io/gh/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool/branch/main/graph/badge.svg)
![PyPI](https://img.shields.io/pypi/v/mcp-rules-assistant?label=pypi)

快速开始 Quick Start（性能优先）
- 安装：`pip install -e .`（开发模式）
- 初始化：`mcp-rules-assistant init`（生成 `.mcp/assistant.yaml`）
- 查看性能模式：`mcp-rules-assistant explain-performance`
- 启动占位服务：`mcp-rules-assistant start`（MCP Server 骨架，后续扩展）
- 环境准备（可选）：`mcp-rules-assistant prepare-env --install`（或 `--dry-run` 查看计划）

文档 Docs
- docs/ARCHITECTURE.md：架构与模块
- docs/PERFORMANCE.md：性能模式与触发点（默认 Fast）
- docs/CONFIG.md：配置与双语命令触发
- docs/USAGE.md：常用使用示例与流程
- docs/RULESETS.md：规则包与选择器
- docs/HOOKS.md：Git hooks 与 CI 生成
- docs/RULES_INGEST.md：规则摄取与校验
- docs/SECURITY_TOOLS.md：安全工具示例（hadolint/semgrep）
 - extensions/vscode/README.md：插件说明

测试与覆盖率 Tests & Coverage
- 本地运行（严格模式，无警告/跳过，覆盖率门槛 ≥95%）：
  - 创建环境并安装依赖（任选其一）
    - `pip install -e . && pip install -U pytest pytest-cov ruff black isort mypy bandit`
    - 或 `make setup`（使用内置 .mcp/venv）
  - 运行测试：
    - `pytest -q --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=term-missing --cov-fail-under=95`
  - 清理覆盖率缓存：`mcp-rules-assistant coverage-clean-cache`
- CI 中按项目配置的 `coverage.min_module` 动态设置门槛（默认 95%），并上传 `coverage.xml` 到 Codecov 以生成覆盖率徽章。

说明（测试样例文件）
- 测试中涉及的示例文件已内置于测试逻辑中创建；仓库根目录不再保留 `bad.py`、`foo.py`、`ok2.py`。

 - Codecov 上传
   - CI 已配置条件上传步骤：
     - 公共仓库：如安装了 Codecov GitHub App，可在无 token 情况下上传（推荐）。
     - 私有仓库：在 GitHub → Settings → Secrets and variables → Actions 配置 `CODECOV_TOKEN`。
     - 上传失败不阻断 CI（`fail_ci_if_error: false`），但建议按需修复以保障徽章与历史数据。
   - 首次 push 后可访问徽章链接确认数据是否入库：
  - https://codecov.io/gh/efem1978/Contextual-Cohesion-and-Programming-Rules-Assistant-MCP-Tool

性能与约束 Performance & Enforcement
- 默认 Fast：保存仅格式化+改动文件 lint；提交增量；推送/CI 才跑重型门禁
- 可切换 Standard/Strict；企业/机构建议 Strict（含变异测试）
 - 受影响测试：受控写入的 quick tests 使用启发式（文件名映射/导入引用）+“上次失败缓存”（`.mcp/last_failed_tests.json`）优先跑高风险测试，进一步降低本地等待时间

Hooks & CI（最小闭环）
- 安装钩子：`mcp-rules-assistant install-hooks`
- 生成 CI：`mcp-rules-assistant generate-ci`
 - CI 将包含 `prepare` 作业：调用 `env.prepare` 创建 `.mcp/venv` 并在 venv 中执行 pytest+覆盖率
- 提交信息约束：计划处于 in_progress，提交信息需包含 `[step:当前步骤]`
- 自动增强：若已摄取规则包含 `security.secrets_scan`/`container.required` 等，将自动加入 detect-secrets（push 阶段）与 Dockerfile 检查等步骤（CI），不影响保存性能
 - 可配置：`ci.hadolint: true`（容器存在时在 CI 中运行 hadolint）；`ci.semgrep_config: auto|自定义规则集`，`ci.hadolint_image/ci.hadolint_args` 可调
 - 近阈值摘要：CI 在 Python 测试后打印 `coverage-near --within 3 --top 10` 结果，用于在 PR 中快速识别“接近阈值”的文件并优先补测
 - 首次使用建议：执行一次 `mcp-rules-assistant install-hooks`，该命令会写入本地脚本（如 `.mcp/plan_gate.py`）并尝试执行 `pre-commit install`（含 commit-msg、pre-push）。若未安装 pre-commit，请先运行 `pip install pre-commit`。

规则摄取（项目级）
- CLI：`mcp-rules-assistant ingest-rules <文件或目录>` → 写入 `.mcp/rules_compiled.*`（含冲突报告）
- MCP：`tools/call rules.ingest { paths: [...] }`，`resources/read rules://project/<id>/compiled`、`.../compiled.json` 与 `.../suggestions`

VS Code 插件（软拦截）
- 打开面板：命令“MCP: Open Panel”，可一键“摄取/校验/载入规则/载入建议”，支持冲突定位与跳转
- 软拦截提交：命令“MCP: Commit (run checks)”（运行 pre-commit 提交阶段并提交）
- 软拦截推送：命令“MCP: Push (run gates)”（触发 pre-push 钩子跑重型门禁）
- 加载覆盖率：面板按钮“加载覆盖率 / Load Coverage”，展示 coverage.xml 产生的薄弱模块
- 覆盖率分组：面板展示“覆盖率分组”，可按策略前缀过滤薄弱文件
- 覆盖率目录树：面板展示“覆盖率目录树（弱项）”，按目录层级折叠浏览并跳转
 - 近阈值：点击“仅看近阈值 / Show Near”可输入窗口（默认 3%），仅显示接近阈值的文件；加载覆盖率时也会自动统计近阈值数量
 - CI 配置：面板提供 hadolint/semgrep 的开关与参数，保存即更新 `.mcp/assistant.yaml`；可一键“生成 CI”
 - 信息条与快速操作：面板顶部有“信息条”，在资源缺失时提示原因与下一步操作；当缺少规则/建议时，会插入“快速摄取 / Quick Ingest”按钮便捷触发摄取。
 - Python 解释器：扩展默认在非 Windows 平台使用 `python3` 启动服务器；可通过环境变量 `MCP_PYTHON_BIN` 覆盖
 - 手测指南：见 `docs/VS_CODE_TEST.md`

记忆与计划（可读可机读）
- 记忆：`resources/read memory://<id>/rollup`（最近 20 轮 JSON）→ 面板“加载记忆”查看
- 计划：`resources/read progress://<id>/plan`（Markdown）→ 面板“加载计划”查看；CLI 有 `plan-init/plan-update`
 - 面板计划操作：可标记“进行中/完成”，并更新“当前步骤”

覆盖率 CLI
- `mcp-rules-assistant coverage`：薄弱文件 Top 20
- `mcp-rules-assistant coverage-groups`：按模块策略分组摘要
- `mcp-rules-assistant coverage-tree`：按目录构建薄弱文件树（前3层）
- `mcp-rules-assistant coverage-near --within 3 --top 20`：近阈值清单（未低于阈值但距离≤3% 的文件）
- `mcp-rules-assistant coverage-near-set --within 5 --top 10`：设置近阈值窗口（百分比）与 Top N，面板“加载覆盖率”与 MCP 资源 `coverage://.../near` 将自动应用
- `mcp-rules-assistant coverage-report --json`：一次性输出弱项/分组/近阈值（默认 JSON）
- `mcp-rules-assistant coverage-clean-cache`：删除覆盖率解析缓存 `.mcp/coverage_cache.json`

一页流（从摄取到门禁）
- 摄取规则：`mcp-rules-assistant ingest-rules <文件或目录>`
- 解释规则：`mcp-rules-assistant rules-explain`（或 `--json --with-suggestions short`）
- 应用门禁：`mcp-rules-assistant enforce`（输出门禁摘要；如提示需要，执行下面两步）
- 生成 CI：`mcp-rules-assistant generate-ci`
- 安装钩子：`mcp-rules-assistant install-hooks`
- 覆盖率与近阈值：`mcp-rules-assistant coverage` / `coverage-near --within 3 --top 20`
 - 建议导出：`mcp-rules-assistant rules-suggestions --format json|csv`
 - 环境诊断：`mcp-rules-assistant diagnose --json`（默认 JSON；或加 `--text`）

示例 Examples
```bash
# 摄取规则与生成建议
mcp-rules-assistant ingest-rules README.md docs/
mcp-rules-assistant rules-explain --json --with-suggestions short

# 覆盖率报告（弱项/分组/近阈值）
mcp-rules-assistant coverage-report --json > coverage_report.json

# 导出建议（CSV）
mcp-rules-assistant rules-suggestions --format csv --output suggestions.csv

# 环境诊断
mcp-rules-assistant diagnose --json > diagnose.json
```

快捷操作 Makefile（可选）
- 一键环境准备：`make setup`
- 本地测试（禁用外部 PyTest 插件）：`make test`
- 生成与校验 CI：`make ci`
- VS Code 扩展测试：`make vscode-test`（若受限可先 `export MCP_VSCODE_TEST_ARGS=""`）
- 规则摄取：`make ingest`
- 覆盖率摘要：`make coverage`

许可证与商业化
- 预留本地授权/离线激活能力接口（见 docs/ARCHITECTURE.md）。
- 默认不开启任何遥测；所有数据本地优先存储。
