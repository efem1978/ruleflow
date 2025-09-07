# 开发指南总览 / Development Guide

本指南是本仓库的开发入口，面向人类与 AI 协作者，提供：
- 统一的开发约束与协作规则（AI 编程约束）
- TDD 逐层推进计划（可直接执行的清单）
- 快速环境与运行说明（本地与容器）
- 文档体系索引（单页入口）

## 快速索引 / Docs Index（按常用度）
- 架构与模块：`docs/ARCHITECTURE.md` — 组件划分与性能模式
- 使用与示例：`docs/USAGE.md` — 常见命令与操作流
- 配置与性能：`docs/CONFIG.md` / `docs/PERFORMANCE.md` — 门槛与策略来源
- TDD 计划：`docs/DEV_PLAN_TDD.md` — 分层推进与清单（与本文件同步）
- CI 与 Hooks：`docs/HOOKS.md` / `docs/CI_HEALTH_CHECK.md` — 生成/自修复/健康检查
- 规则与短语：`docs/RULESETS.md` / `docs/RULES_INGEST.md` / `docs/RULES_PHRASES_INDEX.md`
- 安全工具：`docs/SECURITY_TOOLS.md` — hadolint/semgrep/detect-secrets 等
- 容器开发（无前端界面）：`docs/DOCKER_DEV.md` — 仅落盘状态文件
- VS Code 扩展与测试：`docs/VS_CODE_TEST.md` — 无头测试与参数
- AI 开发者指南（深入）：`docs/AI_DEVELOPER_GUIDE.md` — 设计理念与策略
- 版本与发布：`docs/RELEASE.md`
 - 文档维护映射：`docs/DOCS_MAP.md` — 文档所有者与触发条件

文档去重规则
- 主入口与权威约束：本文件（DEVELOPMENT.md）与 `docs/DEV_PLAN_TDD.md`
- 深入背景或扩展内容：保留在专题文档中（Architecture/AI_Developer_Guide 等）
- 若同一主题有冲突/重复，以本文件为准；专题文档增加“参考本入口”提示

## 环境与运行 / Environment & Run
- 前置：Python ≥3.10、Node ≥18（CI 使用 20）
- 本地开发：
  - 安装：`pip install -e .`
  - 工具链（可选）：`mcp-rules-assistant prepare-env --install` 或 `make setup`
  - 运行测试：
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=xml:coverage.xml`
- 本地一键 CI：`make local-ci-run`
- 安装 Git hooks（commit-msg / pre-push）：`make hooks` 或 `python -m mcp_rules_assistant.cli install-hooks`
  - 无 Python 环境的回退：`make hooks-sh`（安装最小 commit-msg 与 pre-push）
- 一键维护（安装 hooks + 自修复 CI）：`python -m mcp_rules_assistant.cli maintenance`
- 预检（无人值守快照自检）：`make preflight`（扫描禁用模式 / 验证 compose.yml / 跑文档锚点测试）
- Nightly（本地模拟）：`make nightly-local`（预检 + Python 测试 + VS Code 无头测试）
  - 云端每日：`.github/workflows/nightly.yml`（UTC 03:00 触发，可手动 `workflow_dispatch`）
 - 一键全套维护：`make maintenance-all`（安装 hooks + 预检 + 本地 CI 跑通）
- 容器开发（无前端 UI）：
  - 启动：`docker compose up -d dev-agent`
  - 状态：`.mcp/dashboard/status.json`（最近一次）、`history.json`（≤50 条）、`fail_counters.json`
  - 停止：`docker compose rm -sf dev-agent`
  - 说明：容器不再暴露端口/提供前端页面，专注落盘状态文件，便于无人值守编排

## TDD 逐层推进计划 / TDD Step-by-step Plan
遵循“先红后绿再重构”的节奏，按层推进，层内以“单元→组件→集成→接口→扩展”的粒度完成闭环。

1) 单元层（Core Units）
- 目标：`config.py`、`progress.py`、`tools.py`、`memory.py`、`coverage_summary.py`
- 步骤：
  - [ ] 为每个公开函数补齐失败用例（含边界/异常分支；禁止警告与跳过）
  - [ ] 实现最小通过代码；保持幂等与错误信息可诊断
  - [ ] 重构：去重/提取公共逻辑；不改变对外行为
  - [ ] 覆盖率：核心文件≥98%，其余≥95%

2) 组件层（Behaviors & Gates）
- 目标：`checks.py`（受影响测试/降级）、`hooks.py`（钩子生成）
- 步骤：
  - [ ] 构造工具缺失与异常分支的替身/桩（ruff/mypy/pytest 缺失时返回 skipped）
  - [ ] 失败历史缓存与优先级选择（最近失败优先）用例
  - [ ] 生成的钩子/CI 与配置一致性快照测试

3) 集成层（CLI & Dev Agent）
- 目标：`cli.py` 子命令、`dev_agent.py` 循环与状态文件
- 步骤：
  - [ ] CLI 烟雾测试：init/ingest-rules/coverage/coverage-groups/coverage-report
  - [ ] Dev Agent 单循环：写入 `status.json`/`history.json`/`fail_counters.json` 的端到端用例
  - [ ] 失败计数/冻结与解冻路径覆盖（阈值 1 的快速分支）
  - [ ] 自动提交/推送/打标签开关分支：默认 0，显式置 1 时覆盖对应路径

4) 接口层（MCP Server）
- 目标：`mcp_server.py` methods/resources（stdio 模式）
- 步骤：
  - [ ] initialize/capabilities 与核心 tools/resources 的正向与错误路径
  - [ ] fs.apply_patch(strict) 的拒绝路径与后置检查回退

5) 扩展层（VS Code Extension）
- 目标：交互与 Webview 消息桥
- 步骤：
  - [ ] Node 无头测试（`npm --prefix extensions/vscode test`；必要时 `MCP_VSCODE_TEST_ARGS=""`）
  - [ ] 覆盖规则摄取/覆盖率加载/近阈值/CI 配置保存

完成标准（DoD）
- 覆盖率 Gate 通过（已达成）：核心≥98%，其余≥95%，`coverage-report` 弱项清零
- 钩子/CI 生成并可用；commit-msg/branch/pre-push 门禁生效（pre-commit stages 已迁移）
- 所有测试无警告/跳过（CI 强制 `-W error` + `--strict-markers`）

## 提交与门禁 / Commits & Gates
- 提交信息：`[step:当前步骤]`，并在 `.mcp/plan.md` 中保持 `in_progress` 与 `当前步骤/下一步` 更新
- 本地钩子：`mcp-rules-assistant install-hooks`（含 commit-msg/pre-push），推送前运行全量门禁
- 覆盖率门槛：由 `.mcp/assistant.yaml` 的 `performance.on_push.coverage.min_module` 与 `coverage.policy` 同步控制

## 无人值守（AI 自主运行）/ Unattended AI Autopilot
- 容器侧（默认安全）：`DEV_AGENT_AUTOCOMMIT=0`、`DEV_AGENT_AUTOPUSH=0`、`DEV_AGENT_AUTOTAG=0`、`DEV_AGENT_BYPASS_COMMIT=0`
- 显式开启时：
  - `DEV_AGENT_AUTOCOMMIT=1`（定时提交，消息自动附 `[step:...]`）
  - `DEV_AGENT_AUTOPUSH=1`（提交后推送）
  - `DEV_AGENT_AUTOTAG=1`（全量测试通过且弱项清零后创建本地 tag）
  - `DEV_AGENT_COMMIT_INTERVAL=180`（秒）
- 旁路/冻结：
  - 失败计数超过阈值自动“冻结覆盖率”并保留上次稳定值；满足“tests ok 且弱项清零 且 lint/type ok”时解冻
  - `DEV_AGENT_BYPASS=1`、`DEV_AGENT_BYPASS_THRESHOLD`、`DEV_AGENT_BYPASS_COMMIT` 控制是否在旁路时伪装测试通过以不中断流水（默认不伪装）
- 安全写入约束：
  - 仅允许在工作区内修改代码/文档与 `.mcp/` 工件；禁止外部路径与隐式网络操作
  - 提交需满足计划门禁（`.mcp/plan.md` in_progress + `[step:...]`）与覆盖率政策（核心≥98%/其余≥95%）
  - 禁止新增端口暴露/UI 服务；容器仅落盘状态文件

## 文档维护与同步 / Documentation Maintenance
- 变更伴随更新：改动功能/流程时，需同步调整 `DEVELOPMENT.md` 与对应专题文档
- 许可激活：`mcp-rules-assistant license-status` 查看本地状态；`mcp-rules-assistant license-activate --file <path>` 将许可文件复制到 `~/.mcp/license.json`
- 参考：版本全面审查结论请参考近期审计输出；历史 `FULL_PROJECT_REVIEW.md` 已移除，后续按需在 PR 中附带审计纪要
- 自检脚本（建议本地执行）：
  - 禁止引用：避免在文档中出现旧式 Compose/本地端口/UI 静态资源等字样（例如 legacy compose 文件名、开发端口和前端文件名等），以免误导（预检会自动扫描并报错）
  - Compose 校验：`docker compose config -q`
- 计划一致性：`.mcp/plan.md` 当前/下一步与本文件“TDD 清单”应相符

## 快速衔接 / Quick Handoff
- 新窗口/新会话快速获悉上下文：
  - 运行 `mcp-rules-assistant status-update` 刷新 `.mcp/dashboard/status.json` 与 `history.json`。
  - 阅读：
    - `.mcp/plan.md`：`状态/当前步骤/下一步` 与任务复选清单（进度 = 勾选比率）。
    - `.mcp/dashboard/status.json`：综合快照（计划/覆盖率/总体进度/时间戳）。
    - `.mcp/memory.json`：近 20 轮摘要（`summary`）与最近若干 turn（AI 可直接读取）。
  - VS Code 面板或 MCP 资源：`progress://.../plan`、`coverage://.../report`、`memory://.../rollup`。
  - 容器无人值守：`docker compose up -d dev-agent` 将自动每分钟刷新上述状态。

## AI 协作与约束 / AI Collaboration Constraints
- 只按计划改动：任何实现改动需同步更新 `.mcp/plan.md` 与相关文档；禁止绕过计划直接重构
- 伴随测试与文档：新增/变更功能必须附带测试与文档修改；不得降低覆盖率门槛
- 改动最小化：避免无关重构与大范围 rename；保留公共 API 兼容性或提供迁移说明
- 安全与合规：
  - 不新增网络/遥测；不暴露端口（容器开发仅写状态文件）
  - 不新引入依赖，除非在 `docs/ARCHITECTURE.md` 与 `pyproject.toml` 说明动机与影响
- 容器与文件：统一使用 `compose.yml`；不得回退至旧命名（如 `docker‑compose.yml`）；禁止重新引入前端看板/UI 代码

## 任务清单（当前 Sprint）
- [x] TDD 单元层：补齐 coverage_summary 边界与错误分支（现 ~98% 覆盖）
- [x] 组件层：checks 降级/失败缓存用例（现 100%）与 hooks 一致性快照（现 ~100%）
- [x] 集成层：dev_agent 单循环与冻结/解冻分支；CLI 烟雾（dev_agent ~96%）
- [ ] MCP 层：mcp_server 覆盖率提升至 ≥98%（当前 ~85%）
- [ ] VS Code：近阈值/覆盖率加载交互的稳定性回归（待择机）
- [x] 规则摄取：补齐“中文区间（模块）”用例（介于 X% 和 Y% 之间）
- [x] 规则摄取：per-key conflict_delta 与缓存边界（现 ~97% 覆盖）
- [ ] 单元层补齐：memory.py 覆盖率提升至 ≥98%（当前 ~62%）
- [ ] 单元层补齐：fs_wrapper.py 覆盖与错误分支（当前 ~82%）
- [ ] 许可：license_utils 覆盖率 ≥90%（当前 ~38%），补齐 hs256/rs256 正反例
- [ ] 覆盖率策略：修正 coverage.policy 的按文件覆盖优先于 min_module 的应用（license_utils.py 等应命中专属阈值）
- [ ] 清理样例/临时工件：确保 cov.json 等生成物未入库（.gitignore 已覆盖）

## 审计快照（当前） / Audit Snapshot (Current)
- 覆盖率（coverage.xml 总体）: 92.24%
- 低于策略阈值的模块（示例）：license_utils.py（~38%）、memory.py（~62%）、fs_wrapper.py（~82%）、mcp_server.py（~85%）
- 策略阈值（.mcp/assistant.yaml）：min_module=0.96，核心文件（config/progress/tools/memory/mcp_server/cli/server）≥0.98；dev_agent ≥0.95；license_utils ≥0.90
- 发现的问题：部分文件未按 coverage.policy 的专属阈值匹配，落入 min_module 计算；需修正阈值匹配逻辑并补齐测试
## 统一子进程封装 / Unified Process Runner

- 模块：`mcp_rules_assistant/process.py` 提供 `run_cmd` 统一封装。
- 语义：
  - 默认超时 `300s`（可通过 `timeout` 覆盖）。
  - `capture_stdout=True` 时，同时捕获 `stderr`，并对 `stdout/stderr` 进行末尾截断（最大 8000 字符），便于日志与诊断。
  - 为兼容测试桩：当 `capture_stdout=False` 且未显式传 `env/timeout` 时，仅传递基础参数（`cmd/cwd/check`），不注入 `text/stdout/timeout` 等关键字。
- 使用约定：
  - `dev_agent`/`hooks`/`mcp_server` 均已委托 `run_cmd`；后续如需扩展统一日志/重试策略，只需修改该实现。
  - 测试建议对 `mcp_rules_assistant.process.run_cmd` 进行 monkeypatch（必要时也可对模块 re-export 的 `run_cmd` 打桩）。
