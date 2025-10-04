# VS Code 面板手测指南 / VS Code Manual Test

## 前置

- 安装 Python3，并在 PATH 可用（或设置环境变量 `MCP_PYTHON_BIN` 指向 Python 解释器）
- 在根目录执行：`npm --prefix extensions/vscode install`（无依赖也可省略）

## 编译扩展

- `npm --prefix extensions/vscode run compile`

## 启动调试（建议）

- 使用 VS Code 打开仓库根目录
- 按 F5 启动“扩展开发主机”，命令面板执行：`RuleFlow: Open Panel`（或点击状态栏左侧“RuleFlow”）
- 自然语言：执行 `RuleFlow: Natural Command`，输入“摄取规则 README.md, docs/ / 加载覆盖率 / 开启滚动记忆”等

## 基本流程

1. 打开面板
2. 点击“摄取规则 / Ingest”，输入示例：`README.md, docs/`；或用 `RuleFlow: Natural Command` 输入“摄取规则 README.md, docs/”
3. 点击“载入编译规则 / Load Rules” 与 “载入建议 / Load Suggestions”，确认展示内容
4. 点击“加载覆盖率 / Load Coverage”
   - 若项目根存在 `coverage.xml`，面板会展示分组和薄弱文件；否则给出提示
   - 新增：将自动渲染“覆盖率目录树（弱项）”，也可单独点击“加载目录树 / Load Weak Tree”
   - 新增：会自动统计“近阈值（≤3%）”文件数量；点击“仅看近阈值 / Show Near”可输入窗口（1–10%）并仅显示这些文件
5. CI 操作
  - 填写 hadolint/semgrep 配置，点击“保存 CI 配置”
  - 点击“生成 CI”，再点击“预览 CI”“校验 CI”“打开 CI 文件”
  - 覆盖率策略（阶段性）：
    - 非阻断告警：CI 对 `lcov.info` 执行 80% 的检查，低于阈值仅发出警告：
      `sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 80`
    - 可选硬门禁（默认关闭）：将环境变量 `VSCODE_COVERAGE_GATE=1` 打开后，使用同阈值作为门禁：
      `sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 80 gate`
    - 建议：先在数个迭代内稳定≥80%，再逐步提升阈值到 90%/95%
  - 本仓库说明：
    - CI 已启用硬门禁且阈值为 98%
    - `VSCODE_COVERAGE_GATE=1` 与 `VSCODE_COVERAGE_THRESHOLD_WARN=98`
6. 插入示例安全规则
   - 点击“插入示例规则”，确认根目录生成 `.semgrep.yml` 与 `.hadolint.yaml`
7. 记忆与计划
   - 点击“加载记忆 / 加载计划”，确认可读取 `.mcp/plan.md` 与 memory JSON
8. 可选：环境准备（便于隔离验证）
   - CLI 执行：`mcp-rules-assistant prepare-env --install`（或 `--dry-run` 查看计划）
   - CI 中也会包含 `prepare` 作业，使用 `.mcp/venv` 执行 pytest + 覆盖率
   - 面板快速预览：点击“准备环境(预览) / Prepare Env (dry-run)”按钮，弹出 env.prepare 计划（不实际执行）
9. 受限环境的 VS Code 测试
   - 建议优先：清空默认参数后重试：`export MCP_VSCODE_TEST_ARGS="" && npm --prefix extensions/vscode test`
   - 若仍失败，可改用自定义启动参数（逗号分隔）：`export MCP_VSCODE_TEST_ARGS="--disable-extensions"`
  - 或使用容器路径（更稳定）：`docker compose run --rm vscode-test`

## 通过 Docker Compose 运行（推荐缓存）

首次构建会预装依赖并预下载 VS Code 测试内核（镜像层缓存），随后运行速度显著提升：

```bash
docker compose build vscode-test
docker compose run --rm vscode-test
```

## 快速命令（容器优先）

- 无头测试并生成 lcov（默认假后端以提升稳定性）：
  - `docker compose run --rm vscode-test`
  - 注：在 macOS 本机若出现 Electron 启动参数报错，优先使用容器路径运行上述命令。
- 本地快速：`npm --prefix extensions/vscode run test:fake`（主机需可下载 VS Code 测试内核）
- 导出阈值与 near/worst 清单：
  - `sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 98 || true`
  - `sh scripts/lcov-near.sh extensions/vscode/coverage/lcov.info 98 5 20 > near_vscode.txt || true`

## 例子输出（near/worst 摘录）

```text
[lcov-near] threshold: 98% window: 5% top: 20

[lcov-near] Near-below (within window, below threshold):
(none)

[lcov-near] Worst files (lowest coverage):
- 92.0% — extensions/vscode/src/extension.ts
- 90.5% — extensions/vscode/src/panel.ts
...
