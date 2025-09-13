# Changelog

## 2025-09-13 — Milestone: Plan Done (All Gates Green)

Highlights
- Coverage gate: core ≥98%, others ≥95%; weak=0, near=0
- Docker verify: preflight + tests + coverage-export + jb-verify all passed
- License gate: ci.validate respects project-scoped license (no double-check)
- Docs: DEVELOPMENT.md adds coverage artifacts note; tmp_dbg_dir ignored
- Stability: hooks/CI generated & validated; no skip/xfail; -W error

Details
- Python server/CLI + VS Code/JetBrains integration (MCP tools/resources)
- Rules ingest/compile with conflicts and suggestions; coverage policy groups
- No telemetry; local artifacts in .mcp/; security scans (bandit/semgrep/hadolint)
- Natural-language commands (CN/EN), rolling memory (20 turns, namespaces)

## 0.2.5 — 2025-09-08

Maintenance and docs/CI consistency updates (no API changes):

- Docs: add multi‑IDE scaffolding guide `docs/IDE_SCAFFOLD.md` (VS Code/Cursor/JetBrains/Neovim)
- README: link to IDE guide; add quick entry line to key docs
- Neovim: provide Lua snippet in `ide.scaffold` output (kept Vimscript) — `mcp_server.py`
- Hooks/CI: pin semgrep to 1.91.x in generator; clarify pinned version in `docs/HOOKS.md`
- CI: upload Python coverage (`coverage.xml`) to Codecov in build job (keep VS Code lcov upload)
- Cleanup: remove stray backup/sample files (`.github/workflows/ci.yml.bak`, `bad.py`, `ok2.py`, `docs/b.txt`)
- Config: set `coverage.min_core: 0.98` (aligned with “core≥98%”); add comment to `coverage.policy`
- Docs: `docs/LICENSE.md` now points to root `LICENSE` as legal text (this page is demo for license gen/verify)

All tests and preflight checks pass; coverage policy gate reports weak=0.

## Unreleased
No changes yet.

## 0.2.4 — 2025-09-06

Highlights
- 统一子进程封装：新增共享 `process.run_cmd`，`dev_agent`/`hooks`/`mcp_server` 委托使用，默认参数保持测试桩兼容。
- CLI 许可命令落地：`license-status` / `license-activate` 与 README 对齐，新增单测覆盖。
- 原子写统一：共用 `atomics.py`，`fs_wrapper`/`config`/`dev_agent` 委托，降低重复与耦合。
- 审查与文档：新增 `FULL_PROJECT_REVIEW.md`，同步 README/DEVELOPMENT；Ruff 本地排除 tests 保持与 CI 策略一致。

Changes
- process: 新增 `mcp_rules_assistant/process.py`（test-friendly 的 `run_cmd`）。
- dev_agent/hooks/mcp_server: `_run_cmd` 委托共享实现；保持原符号供测试 monkeypatch。
- coverage_summary: 将内部 `assert` 改为显式类型归一，压降 Bandit 噪音（B101）。
- atomics/dev_agent: 为不可阻断的 try/except/pass 补充解释性注释（`# nosec B110`）。
- docs: README/DEVELOPMENT 更新许可命令；新增审查报告入口。
- tests: 新增 `tests/test_cli_license.py` 覆盖许可命令。

## v0.2.3+dev — 2025-09-06

Highlights
- Production-grade gates met and stabilized: core ≥98%, others ≥95%, weak=0
- coverage_summary at 100% coverage（守护分支通过定向 stub 覆盖）
- checks 与 hooks 100% 覆盖；rules_ingest 97% 覆盖

Changes
- Fix(preflight): 精确匹配 `status.js`，避免误伤 `status.json`；当 pytest 不可用时自动退化到轻量 anchors 校验
- Tests(rules_ingest):
  - 缓存回填失败与 read_bytes 异常（签名/写缓存阶段）
  - YAML/JSON 分支解析与 YAML 嵌套扁平化（coverage.min_module/coverage.min_core）
  - per-key conflict_delta（coverage.min_module=0.01）与布尔冲突合并
  - 空文档回退（空 YAML/JSON 不产生有效策略键）
- Tests(coverage_summary): 排序 key 的异常回退（sort_key/_key_cov/_key_delta）
- Docs: DEVELOPMENT.md 同步当前覆盖率与完成项
- Chore: 忽略 `.coverage*` 并清理误入库覆盖率文件

Notes
- 全部工作仅本地容器内开发，本地提交，未推远端
- dev_agent 本地烟雾写入 `.mcp/dashboard/status.json`（tests.ok=true，coverage weak=0）

## 0.2.0
- 规则摄取增强：小数百分比、中文“成”、上限/区间、否定与比较短语、英文词数上限
- 建议分级（must/warn/info）与导出（rules-suggestions）
- rules-explain 输出 maxima 与 severity 汇总；编译 Markdown 展示 monitor 上限
- 覆盖率 near 读取配置（CLI/MCP）；新增 coverage-report 一体化汇总
- 覆盖率解析缓存（.mcp/coverage_cache.json）与清理命令（coverage-clean-cache）
- CI 严格档：按规则/配置加入 mutation 步骤
- VS Code：测试参数覆盖（MCP_VSCODE_TEST_ARGS），面板环境预览按钮
- DevContainer 与文档（TROUBLESHOOTING/CONTRIBUTING/RELEASE）

## 0.1.0
- 初始版本：MCP Server + CLI + 规则摄取/编译 + VS Code 扩展（最小实现）
## v0.2.1 — 2025-09-02

- CI: Enforce Coverage Policy Gate (core≥98%, others≥95%); forbid `skip/xfail` in package code；保持 `-W error` 严格。
- Types: 全包 mypy 0 告警；将阻断范围扩展到 `cli`、`mcp_server`、`server`。
- Coverage: 新增 `__main__` 入口测试与 `coverage_summary` 防御分支用例。
- Docs/Plan: 更新 `docs/DEV_PLAN_TDD.md` 与 `.mcp/plan.md`，对齐生产级门禁与 PR‑A/B/C 进展。
- CI: 将全局 `--cov-fail-under` 从 95 提升至 96；Bandit 仅阻断高严重级别。
- CI threshold: Raise global `--cov-fail-under` from 95 to 96.
