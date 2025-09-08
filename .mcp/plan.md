# 项目计划 / Project Plan（进行中）

- 状态: in_progress
- 当前步骤: 持续迭代
- 下一步: （无）
- 风险与阻塞: （待补充）

## 任务清单（可勾选，唯一权威）

CI 与门禁
- [x] 修复 `.github/workflows/ci.yml` 的 matrix 表达式（`${{ matrix.python-version }}`），或运行 `mcp-rules-assistant ci-autofix` 重新生成
- [x] 回归构建：`make local-ci-run` 全绿，覆盖率 Gate 通过

自动任务记录与面板
- [x] CLI `status-update` 增强：在 `.mcp/dashboard/status.json` 中输出 `tasks.pending/done` 列表
- [x] VS Code 面板“状态”区域补充显示剩余任务（可选）

覆盖率与测试（细化）
- `mcp_rules_assistant/mcp_server.py` ≥98%
  - [x] initialize/capabilities 成功与未知方法错误
  - [x] 速率限制/请求体超限（`rate_limit_rps`/`max_request_bytes`）错误
  - [x] tools/list 返回注册项；tools/call 许可门禁（`license.required: true` + 无效许可 → 拒绝）
  - [x] resources/list 完整项；rules 资源缺失时报错（需先/未 ingest 的两路）
  - [x] resources/read：memory/links、rules(compiled/md/json/suggestions/maxima)、coverage(summary/groups/tree/near/report)、progress、config、ci
  - [x] fs.apply_patch：
        - dryRun 返回 would_write；maxFiles 超限拒绝；内容大小超限拒绝
        - strict+runChecks：内容包含 skip/xfail 片段拒绝；写入后检查失败拒绝
        - allowed_write_prefixes/extensions 生效（允许/拒绝各一例）
  - [x] env.prepare：dry-run 计划；create+install 成功；失败路径返回 message
  - [x] env.diagnose：工具探测字段存在、coverage/compiled 状态判定
  - [x] plan.suggest_next：基于 plan/summary 给出建议
  - [x] coverage.report：weak/groups/near 合并输出的结构与字段

- `mcp_rules_assistant/fs_wrapper.py` ≥95%
  - [x] 目标为符号链接 → 严格模式拒绝；非严格允许写入
  - [x] allowed_write_prefixes/allowed_write_extensions 白名单命中/未命中两路
  - [x] fs_guard_post_checks=True：写入后 run_checks 被调用；严格模式失败抛错；非严格仅记录
  - [x] 正常写入：内容落盘，未触发异常

- `mcp_rules_assistant/license_utils.py` ≥90%
  - [x] hs256：签名正确/错误验签
  - [x] rs256：生成并验签（设置 `MCP_LICENSE_PUBKEY`）；缺失公钥/非 RSA 公钥 → 验签失败
  - [x] 过期日期/无效日期格式路径
  - [x] generate_license：hs256/rs256 输出字段完整性

文档与可发现性
- [x] 在 `DEVELOPMENT.md` 增加“下一步 / Next Actions”指向 `.mcp/plan.md`（单一权威）
- [x] 更新 `docs/DEV_PLAN_TDD.md` 的严格 TDD 清单，聚焦上述覆盖率与 CI 差距

清理与一致性
- [x] 移除根部样例文件 `a.py`、`bad.py`、`ok2.py`、`link.py` 与 `docs/b.txt`
- [x] 校对文档中“已清理样例文件”的表述与实际一致

可选增强
- [x] prompts 最小内置：`prompts/list` 返回 1–2 个 handoff/规则摘要模板（通过环境变量/配置开关）
- [x] 发布模式开关：新增 CLI `license-require-on/off` 便于切换出货/开发模式
- [x] 在 `.mcp/assistant.yaml` 明确 `execution.allowed_write_prefixes/allowed_write_extensions` 提升受控写入安全
- [x] 规则引导（rules.onboard）：CLI/MCP/VS Code NL 触发，应用推荐阈值到配置

## 验收标准（Definition of Done）
- [x] `make local-ci-run` 通过；CI 与门禁（覆盖率 Gate 无 weak）一致
- [x] 覆盖率达标：mcp_server≥98%、fs_wrapper≥95%、license_utils≥90%
- [x] `.mcp/plan.md` 勾选与提交门禁匹配（commit-msg 含 `[step:...]`）

## 说明
- 任务清单为单一权威：所有更新以本文件为准。
- 提交门禁：需保证本文件处于 in_progress，且提交消息包含 `[step:当前步骤]`。
