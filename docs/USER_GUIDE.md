# 用户上手指南 / User Guide (Newbie Friendly)

本指南面向编程新手，提供一步一步的“开箱即用”路径与常见问题提示。无需提前了解 Python/Node 等细节。

## 一键安装 / One‑Click
- 终端运行：`sh scripts/install-all.sh`
  - 自动创建并使用工作区 `.mcp/venv`（Python 虚拟环境）
  - 安装本工具、初始化与规则摄取、运行测试并生成 `coverage.xml`
  - 构建并安装 VS Code 扩展；JetBrains 插件可在 Docker 环境下一键打包
- 之后在 IDE 打开本仓库即可直接使用（VS Code/Cursor/Windsurf 共用 VSIX；JetBrains 提供工具窗口）。

## VS Code / Cursor / Windsurf
- 打开命令面板（Cmd/Ctrl+Shift+P）：
  - “RuleFlow: Open Panel”：打开面板视图
  - “RuleFlow: Quick Actions”：状态栏也可一键打开（左侧“RuleFlow”）
  - “RuleFlow: Natural Command”：输入中文/英文短语即可操作（如“加载覆盖率/摄取规则/生成CI/校验CI/安装钩子/计划：当前=…/受控写入”）
- 面板帮助入口：面板提供“打开用户上手 / Open User Guide”与“打开 IDE 支持 / Open IDE Support”按钮，可一键打开 `docs/USER_GUIDE.md` 与 `docs/IDE_SUPPORT.md`。
- 新手建议短语：
  - “规则引导” → 工具会提出场景/复杂度/模式的简单选项（不会的可以直接回车采用默认）
  - “摄取规则 README.md, docs/” → 将你编写的规则文档纳入并整理
  - “应用门禁” → 把规则写回配置、生成标准门禁（覆盖率/安全/容器）
  - “加载覆盖率” → 弹窗显示弱项/近阈值/分组摘要；面板显示明细与目录树
  - “计划：状态=进行中；当前=实现入口；下一步=完善测试” → 一键更新 `.mcp/plan.md`
  - “受控写入” → 进入 Guarded Write，对选中内容进行 dry‑run/strict 检查后写入

## JetBrains（IDEA/PyCharm 等）
- 打开工具窗口“RuleFlow”：
  - “启动 MCP” → 直接用工作区 `.mcp/venv` 的 Python 启动服务
  - “自然语言 / NL” → 输入短语（覆盖率/摄取/生成CI/校验CI/安装钩子…）
  - “加载计划/记忆/覆盖率摘要” → 一键查看 `.mcp/plan.md`、`.mcp/memory.json` 与 coverage 摘要
  - “环境：预览 / 创建并安装” → 运行 `env.prepare` 预览或一键安装工具链
  - “计划设置 / Plan Set” → 快速更新 status/current/next

## 不会就让工具帮你选
- 如果你不确定：
  - 运行“规则引导”（rules.onboard），工具会按你的项目结构给出推荐阈值与门禁
  - 运行“准备环境”（env.prepare），可选择“预览”先看将要做什么，再选择“创建并安装”
  - 运行“摄取规则”，将你的规则文档（README、docs 等）纳入，工具会输出冲突/建议并提示下一步

## 状态可见性
- VS Code：
  - 状态栏 `RuleFlow ✓ wX/nY`（悬停显示 groups 与 min_module）
  - 面板“加载覆盖率”会弹窗摘要并刷新状态栏；CSV 预览/目录树/分组视图便于定位
- JetBrains：
  - 顶部状态标签显示 weak/near 摘要；“刷新状态”会读取 `.mcp/dashboard/status.json`

## 常见问题（快速判断）
- 看不到覆盖率？先运行测试（已在 install‑all 中自动运行）；或运行“加载覆盖率/Status Update”。
- Python 解释器路径？工具自动使用 `.mcp/venv`；无需再设置。
- CI/Hooks？“生成 CI”“安装钩子”一键完成；提交信息建议包含 `[step:...]`，并确保 `.mcp/plan.md` 在 in_progress。
