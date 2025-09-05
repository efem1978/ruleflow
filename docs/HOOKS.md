Git Hooks 与门禁（性能优先）

目标
- 保存零负担；提交轻；推送/CI 才跑重型检查。

安装
- 确保项目已初始化 git：`git init`（如未）
- 生成配置与钩子：`mcp-rules-assistant install-hooks`
- 安装 pre-commit（如未安装）：`pip install pre-commit`

行为
- pre-commit（提交阶段）：ruff/black/isort/mypy（改动范围）
- commit-msg（提交信息门禁）：
  - 计划状态机：要求 `.mcp/plan.md` 处于 `in_progress` 且存在“当前步骤”
  - 提交信息需包含标记 `[step:当前步骤]`，否则阻断
- 分支命名（提交阶段）：默认要求分支名匹配 `main|master|develop|dev|feat/*|fix/*|chore/*|docs/*|test/*|refactor/*|release/*|hotfix/*`；
  - 可用环境变量覆盖：`MCP_BRANCH_REGEX`；或通过 `MCP_BRANCH_IGNORE=1` 临时跳过
- pre-push（推送阶段，经 pre-commit 触发）：
  - pytest + 覆盖率（最低模块≥90%，取自 `.mcp/assistant.yaml`）
  - 禁止 skip/xfail（git grep 扫描）
  - bandit 安全扫描
  - 生成 `coverage.xml`（用于面板“加载覆盖率”与薄弱模块展示）
  - 若规则启用 `security.secrets_scan`：自动在 pre-commit 配置中加入 `detect-secrets`（push 阶段），保存阶段不运行

注意（本地脚本生成时机）
- `.pre-commit-config.yaml` 中引用的本地脚本（如 `.mcp/plan_gate.py`、`.mcp/dockerfile_gate.py`）由 `mcp-rules-assistant install-hooks` 生成。
- 请优先执行一次 `install-hooks` 再进行提交/推送；后续计划将这些条目改为“条件生成”，避免首次运行时因缺失脚本而失败。

CI 生成
- `mcp-rules-assistant generate-ci` 会生成基础工作流；若已存在编译规则：
  - 开启了 `security.secrets_scan`：在 CI 中添加 `pre-commit --all-files` 步骤以扫描密钥
  - 开启了 `container.required`：在 CI 中检查 `Dockerfile` 是否存在
  - 开启了 `container.policy.baseline`：在 pre-commit（push 阶段）添加 Dockerfile 基线本地检查（禁用 USER root、禁止 :latest 等）
  - 开启了 `security.sast_strict`（预留）：建议集成 `semgrep` 或组织内部 SAST 规则（可在 CI 中追加）
  - Python 测试后附加“近阈值摘要”步骤：执行 `coverage-near --within 3 --top 10` 打印距离阈值不超过 3% 的文件清单（仅报告，不影响门禁）
  - 生成工件：`coverage.xml`、`pytest-junit.xml`、`near.txt/near.csv/near.json`，并打包为 `tests-artifacts.tar.gz` 上传，便于 PR 审阅与归档
  - 新增（可选）：`prepare` 作业将调用 `env.prepare` 创建 `.mcp/venv` 并在 venv 中跑 pytest+覆盖率，便于隔离环境验证

VS Code 无头测试（必跑项）
- 在 `.mcp/assistant.yaml` 设置 `ci.vscode_required: true` 时，生成的 CI 将总是包含 `vscode` 作业（Node 20 + xvfb 无头运行 `npm test`），作为必跑项；
- 未开启时，生成器会在 `extensions/vscode/package.json` 存在时自动包含该作业（可选项）。

CI
- 生成 GitHub Actions：`mcp-rules-assistant generate-ci`
- 工作流路径：`.github/workflows/ci.yml`
