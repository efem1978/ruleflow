# 项目审计与整改计划（唯一权威）

- 状态: in_progress
- 当前步骤: JetBrains 按钮采集与计划设置/受控写入 GUI 完善
- Status: in_progress
- Current step: JetBrains 按钮采集与计划设置/受控写入 GUI 完善
- 下一步: Onboard 问答深化与模板分层
- 说明: 本文件为唯一权威任务清单来源。面板/CLI/钩子与 CI 均以此为准。

本轮审计基于真实代码与测试产物（coverage.xml 与 CLI 解析），不依赖任何文档描述。

审计结论（事实口径）
- 覆盖率: `coverage-report --json` 显示 weak=[]；核心模块≥98%，非核心≥95%；近阈值（near）为空，窗口 within=0.8%。
- 测试: Python 端严格 `-W error`、无 skip/xfail；CI/本地均生成 coverage.xml；VS Code 端 CI 设 95% 硬门禁且含 near/worst 导出。
- 目录结构: 包/扩展/脚本/文档分层清晰；`mcp_rules_assistant/`、`extensions/`、`docs/`、`tests/` 分布合理，无错位文件。
- 文档体系: `DEVELOPMENT.md` 与 `README.md` 顶部已声明“.mcp/plan.md 为唯一权威”，docs/* 为专题与索引；未发现需删除的过时/冗余文档。
- 配置与 CI: `.mcp/assistant.yaml` 与生成的 CI 对 hadolint=2.12.0、semgrep=1.91.x 固定版本一致；`ci.vscode_required=true` 与文档一致。

P0 已完成（本轮）
- [x] 覆盖率与测试门禁复核（weak=0、skipped=0、-W error 无警告）
- [x] CI 健康检查复核：`make local-ci-run` 与 `ci-validate` 通过（含 Coverage Policy Gate）
- [x] 文档入口一致性核验：README/DEVELOPMENT/docs/* 已统一指向 `.mcp/plan.md` 为唯一权威

P1 质量与发布（已完成）
- [x] 夜间/本地回归与覆盖率导出：`.mcp/dashboard/coverage_summary.json`、`weak_top.csv`、`near_top.csv`、`groups.csv`
- [x] 规则编译与建议：`ingest-rules README.md docs/` 刷新 `.mcp/rules_compiled.*`
- [x] 发行物料演练：`.mcp/dashboard/release_check.md` 等

记录与门槛
- 覆盖率策略：核心≥0.98，其它≥0.95（项目配置 `min_module=0.96`；核心按文件后缀 0.98 覆盖）；`coverage.policy` 同时支持前缀/后缀匹配。
- 前端阈值：VS Code CI 95% 硬门禁（`check-lcov.sh ... 95 gate`），失败导出 near/worst 清单。

完成定义（DoD）
- `make local-ci-run` 全绿；`coverage-report --json` 的 weak 为空；`.mcp/assistant.yaml` 与 README/docs 的阈值描述一致。

跟进清单（严格 TDD 批次，最大单批次 ≤ 6 项）

Batch 1（VS Code 事件采集与文档入口）
- [x] VS Code：在 NL/Quick Actions/Panel“加载覆盖率”/Plan Set/CI/Hooks/受控写入等动作后，统一调用 memory.append_turn（含摘要）
- [x] VS Code：USER_GUIDE/IDE_SUPPORT 入口挂接到面板（帮助/文档一键打开）
- [x] 文档：完善 USER_GUIDE/NATURAL_LANGUAGE/IDE_SUPPORT 索引（README/DEVELOPMENT.md 更新链接）
- [x] 测试：补 NL 路由与 append_turn 的契约测试；保持全绿与覆盖率门禁
- [x] 提交门禁：以 `[step:NL 事件采集与自动滚动记忆（VS Code 首批）]` 提交；本批完成后更新“当前步骤/下一步”

Batch 2（JetBrains 采集与 GUI 完善）
- [ ] JetBrains：按钮与 NL 执行后统一 append_turn（覆盖率/摄取/CI/Hooks/Env/PlanSet）
- [ ] JetBrains：受控写入 GUI（多文件、dry‑run、strict 开关）
- [ ] JetBrains：Plan Set 对话增强（预设选项 + 校验）
- [ ] 测试：JB UI 验证脚本扩展（jb-ui-verify 增加 turn 计数断言）
- [ ] 提交门禁：`[step:JB 事件采集与 GUI]`

Batch 3（Onboard 问答深化与模板分层）
- [ ] rules.onboard：增加安全/容器/许可/门禁强度/测试分级的引导问题与默认解释
- [ ] 模板分层：按语言/框架/阶段生成建议门禁（Python/Node/Rust 起步）
- [ ] 面板：展示“将启用的规则摘要”，一键采纳回写
- [ ] 测试：onboard 选择组合 → 配置回写的契约测试
- [ ] 提交门禁：`[step:Onboard 深化]`

Batch 4（NL 别名与受控写入 UX）
- [ ] NL：为受控写入/计划设置/规则摘要等再增中文/英文别名
- [ ] VS Code：Guarded Write 支持多文件 + diff 预览（dry‑run 阶段）
- [ ] 测试：fs.apply_patch UI 合同与安全分支
- [ ] 提交门禁：`[step:NL&Write UX]`

Batch 5（容器与 Chat 集成可选项）
- [ ] 容器：dev-agent 增加自动 append_turn（最小摘要），频率与上限受控
- [ ] VS Code Chat（可选）：如启用 Chat API，追加“上一轮问答摘要”
- [ ] 文档：在 USER_GUIDE 附“可选功能”与隐私/性能说明
- [ ] 提交门禁：`[step:容器与Chat可选]`

审计附注
- 未发现需删除的重复/弃用文档；docs/CONTRIBUTING.md 为根文档的本地化补充且已标注权威来源；docs/LICENSE.md 仅为演示说明，法律文本以根 LICENSE 为准。
