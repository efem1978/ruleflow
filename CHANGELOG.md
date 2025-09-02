# Changelog

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
- 初始版本：MCP Server + CLI + 规则摄取/编译骨架 + VS Code 扩展脚手架
## Unreleased

- CI: Enforce Coverage Policy Gate (core≥98%, others≥95%); forbid `skip/xfail`; keep `-W error` strict.
- Types: mypy clean across package; expand blocking to `cli`, `mcp_server`, `server`.
- Coverage: Add tests for `__main__` entrypoint and defensive branches in `coverage_summary`.
- Docs/Plan: Update `docs/DEV_PLAN_TDD.md` and `.mcp/plan.md` to production-grade gates; track PR-A/B/C.
- CI threshold: Raise global `--cov-fail-under` from 95 to 96.
