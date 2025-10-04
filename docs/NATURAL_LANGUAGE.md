# 自然语言指令 / Natural Language Commands

下列短语在面板“自然语言输入”或命令“RuleFlow: Natural Command”中输入即可触发。中文/英文均可，模糊匹配。

记忆 Memory
- 开启滚动记忆 / 关闭滚动记忆 / enable rolling memory / disable rolling memory → memory.toggle_auto
- 记忆快照 / snapshot → memory.snapshot

规则 Rules
- 初始化规则 / init rules → rules.init
- 摄取规则 / ingest rules（可附路径，如：README.md, docs/）→ rules.ingest
- 校验规则 / validate rules → rules.validate
- 应用门禁 / enforce rules / apply gates → rules.enforce

覆盖率 Coverage
- 加载覆盖率 / load coverage → 读取覆盖率并展示弱项
- 近阈值 / near threshold → coverage.near（默认窗口 3%）

CI / Hooks / 配置
- 安装钩子 / install hooks → git.install_hooks
- 生成 CI / 生成CI → ci.generate
- 校验 CI / 校验 ci → ci.validate
- 自修复 CI / 自修复 ci → ci.autofix
- 准备环境 / prepare env / prepare environment → env.prepare（默认 dry-run 预览）

规则资源（只读）
- 载入规则 / load rules → 显示编译规则（Markdown）
- 加载建议 / load suggestions → 显示冲突与建议（Markdown）

说明
- 某些指令需要附带路径（例如“摄取规则 README.md, docs/”），如未提供会弹出输入框询问。
- Copilot 聊天中可用“用 ruleflow …”句式更易命中（参见 `docs/COPILOT_MCP.md`）。

