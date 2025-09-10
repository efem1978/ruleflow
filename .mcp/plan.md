# 项目计划 / Project Plan（进行中）

- 状态: in_progress
- 当前步骤: 批次G — 预发布验证（不发布）
- 下一步: 批次H — README 安装与本地验证段落微调（可选）
- 风险与阻塞: 无（不进行发布，仅本地/CI 验证）

## 任务清单（可勾选，唯一权威）

批次A — 覆盖率抛光与门禁强化
- [x] dev_agent.py：补齐冻结/解冻/旁路与失败分支各 1–2 条用例，使覆盖率≥96.0%
- [x] mcp_server.py：补齐 env/coverage/resources 边界异常与大小/速率极端值用例，使覆盖率≥99.0%
- [x] rules_ingest.py：补齐“上限/区间/异常 YAML/JSON”用例，覆盖率≥98.0%
- [x] CLI 合同测试：文档示例命令存在性校验（抽样）与失败路径（如 rules-explain 无文件）
- [x] CI “禁止 skip/xfail（包内）”规则增强：额外扫描测试输出统计（仅报警，不误伤测试用例标记）

批次B — 清理与一致性（含占位项收敛）
- [x] 清理无用样例：docs/link.py、bad.py/ok2.py/ok.txt、docs/b.txt（并在 Makefile clean 与脚本中覆盖）
- [x] README 覆盖率策略说明：补充“policy 键可后缀匹配文件名”的最佳实践小贴士
- [x] docs/CI_HEALTH_CHECK.md：由占位改为“健康检查操作说明 + 触发方式 + 常见失败定位”
- [x] scripts/workspace-clean.sh：覆盖上述样例与临时工件的清理

批次C — JetBrains P3：打包与最小 E2E（本轮落地）
- [x] 脚本：`scripts/jb-package.sh` 完成 & 文档化（执行 `./gradlew buildPlugin`）
- [x] 最小 E2E：在 CI 新增 smoke（读取 `.mcp/dashboard/status.json` 并校验关键字段）
- [x] README/DEV_PLAN 增补 JB 打包与 E2E 说明

批次D — 统一子进程封装与开关验证
- [x] checks.py 委托 `process.run_cmd` 的配置开关回归测试（on/off 两路，保持历史桩兼容）

批次E — 文档与入口指南同步
- [x] `DEVELOPMENT.md`：更新“任务清单（当前 Sprint）”为本批次内容；保留锚点不变
- [x] `docs/DEV_PLAN_TDD.md`：更新“近期待办/执行批次”与阈值目标，纳入本轮清单

批次F — 商业化与出货演练
- [x] 许可门禁 E2E 小结：`release-harden-verify` 的摘要输出写入 `.mcp/dashboard/release_check.md`
- [x] PR 检查清单（贡献指南补充）：覆盖率 Gate/近阈值提示/许可门禁切换步骤

（允许暂缓项 — 仅图片）
- [ ] 将 JetBrains 占位 SVG 替换为实拍 PNG（完成即勾选；不阻断本批次验收）

批次G — 预发布验证（不发布）
- [ ] Python 打包：`python -m build`（wheel/sdist）
- [ ] 产物校验：`python -m twine check dist/*`
- [ ] CI 侧（可选）：添加 build/twine check 作业（非阻断）

## 验收标准（Definition of Done）
- `make local-ci-run` 通过；Coverage Policy Gate 无 weak；近阈值 Top5 中无“核心”模块
- 关键模块覆盖率：mcp_server≥99%、dev_agent≥96.5%、rules_ingest≥98%
- 清理项可在 `make clean` 与 `scripts/workspace-clean.sh` 一键完成
- CI 健康检查文档可按步骤复现；JB 打包脚本可用；E2E smoke 绿

## 说明
- 任务清单为单一权威：所有更新以本文件为准。
- 提交门禁：需保证本文件处于 in_progress，且提交消息包含 `[step:当前步骤]`。
