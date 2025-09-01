VS Code 面板手测指南 / VS Code Manual Test

前置
- 安装 Python3，并在 PATH 可用（或设置环境变量 `MCP_PYTHON_BIN` 指向 Python 解释器）
- 在根目录执行：`npm --prefix extensions/vscode install`（无依赖也可省略）

编译扩展
- `npm --prefix extensions/vscode run compile`

启动调试（建议）
- 使用 VS Code 打开仓库根目录
- 按 F5 启动“扩展开发主机”，侧边栏命令面板搜索并执行：`MCP: Open Panel`

基本流程
1) 打开面板
2) 点击“摄取规则 / Ingest”，输入示例：`README.md, docs/`
3) 点击“载入编译规则 / Load Rules” 与 “载入建议 / Load Suggestions”，确认展示内容
4) 点击“加载覆盖率 / Load Coverage”
   - 若项目根存在 `coverage.xml`，面板会展示分组和薄弱文件；否则给出提示
   - 新增：将自动渲染“覆盖率目录树（弱项）”，也可单独点击“加载目录树 / Load Weak Tree”
   - 新增：会自动统计“近阈值（≤3%）”文件数量；点击“仅看近阈值 / Show Near”可输入窗口（1–10%）并仅显示这些文件
5) CI 操作
   - 填写 hadolint/semgrep 配置，点击“保存 CI 配置”
   - 点击“生成 CI”，再点击“预览 CI”“校验 CI”“打开 CI 文件”
6) 插入示例安全规则
   - 点击“插入示例规则”，确认根目录生成 `.semgrep.yml` 与 `.hadolint.yaml`
7) 记忆与计划
   - 点击“加载记忆 / 加载计划”，确认可读取 `.mcp/plan.md` 与 memory JSON
8) 可选：环境准备（便于隔离验证）
   - CLI 执行：`mcp-rules-assistant prepare-env --install`（或 `--dry-run` 查看计划）
   - CI 中也会包含 `prepare` 作业，使用 `.mcp/venv` 执行 pytest + 覆盖率
   - 面板快速预览：点击“准备环境(预览) / Prepare Env (dry-run)”按钮，弹出 env.prepare 计划（不实际执行）
9) 受限环境的 VS Code 测试
   - 若 `npm --prefix extensions/vscode test` 在本机失败，可尝试：
     - 移除默认参数（不传任何启动参数）：`export MCP_VSCODE_TEST_ARGS=""`
     - 或自定义启动参数（逗号分隔）：`export MCP_VSCODE_TEST_ARGS="--disable-extensions"`
   - 再运行：`npm --prefix extensions/vscode test`

问题排查
- Server 无法启动：设置 `MCP_PYTHON_BIN` 环境变量，例如 `export MCP_PYTHON_BIN=python3`
- 执行工具失败：先在项目根运行 `pip install ruff black isort mypy bandit pytest pytest-cov pre-commit`
- 规则资源读取报错：先执行“摄取规则 / Ingest”或在根目录生成 `.mcp/rules_compiled.*`
 - 信息条与快速操作：资源缺失时，面板顶部“信息条”会提示缺失原因；缺少规则/建议时会出现“快速摄取 / Quick Ingest”按钮，点击按提示输入路径进行摄取
