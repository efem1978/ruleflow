# 发布操作清单 / Publishing Checklist (Local-Only Guidance)

> 说明：本清单只提供本地与 CI 的发布操作参考，不会触发任何对外网络动作。请根据你所在组织的安全策略与凭据管理，替换占位内容后再执行。

## 0) 预发布校验（必做）
- 刷新状态与生成报告（本仓库已内置脚本）：
  - `sh scripts/pre-release-check.sh`
  - 查看 `.mcp/dashboard/pre_release_report.md`、`release_body.md`、`release_note_snippet.md`
- 本地打包（Wheel + VSIX + 归档）：
  - `sh scripts/release-local-pack.sh`
  - 校验 `dist/release-bundle-<ver>.tar.gz` 内容：`tar tzf dist/release-bundle-*.tar.gz | head -n 50`
- 可选：容器内 VS Code 无头测试与 lcov（CI/容器环境）：
  - `make docker-vscode-test`

## 1) Git 标签（本地打 Tag 后手动推送）
- 确认 `pyproject.toml` 的版本号与 VSIX 版本一致（本仓库 v0.2.5 示例）。
- 命令模板：
  - `git tag -a v0.2.5 -m "RuleFlow v0.2.5"`
  - `git push origin v0.2.5`

## 2) GitHub Release（人工在 Web 上操作）
- 新建 Release（指向标签 v0.2.5）：
  - 正文建议粘贴 `.mcp/dashboard/release_body.md` 或 `RELEASE.md` 摘要段（本仓库附 `.mcp/dashboard/release_github_draft.md` 草案）。
  - 附件：
    - `extensions/vscode/mcp-rules-assistant-0.2.5.vsix`
    - `dist/mcp_rules_assistant-0.2.5-py3-none-any.whl`
    - `dist/mcp_rules_assistant-0.2.5.tar.gz`
    - `dist/release-bundle-0.2.5.tar.gz`（可选）

## 3) PyPI 发布（示例指令，需 PyPI 凭据）
- 环境：`python -m pip install --upgrade build twine`
- 构建：`python -m build`
- 校验：`python -m twine check dist/*`
- 发布（替换凭据来源为组织推荐的安全方式，如 keyring 或 CI secrets）：
  - `python -m twine upload dist/*`

## 4) VS Code Marketplace（示例指令，需 PAT）
- 安装 vsce：`npm i -g @vscode/vsce`（或 `npx @vscode/vsce`）
- 打包：`(cd extensions/vscode && vsce package --no-dependencies)`
- 登录：`vsce login <publisher>`（或使用环境变量/CI 机密）
- 发布：`(cd extensions/vscode && vsce publish)`

## 5) 验收与回滚准备
- 下载安装验证：
  - VSIX：`code --install-extension extensions/vscode/mcp-rules-assistant-0.2.5.vsix`
  - Wheel：`pip install dist/mcp_rules_assistant-0.2.5-py3-none-any.whl`
- 失败回滚：删除标签/撤销 Release；PyPI/VSCE 按各平台回滚或撤销流程执行。

> 提示：本地/CI 发布操作建议使用只读或最小权限令牌；所有操作均应由人工确认后再执行。
