# 发布指南 / Release Guide

## Python 包 Packaging

- 版本：在 `mcp_rules_assistant/__init__.py` 更新 `__version__`
- 打包：`make package`（或 `python -m build`）
- 发布：`python -m pip install --upgrade twine && twine upload dist/*`
- 检查：`make release-check`（执行 `twine check dist/*`）
- 依赖安全：`python -m pip install --upgrade pip-audit && pip-audit || true`

## VS Code 扩展（可选）

- 编译：`npm --prefix extensions/vscode run compile`
- 打包：可使用 `vsce package`（需安装 `@vscode/vsce`）
  - 示例：`npm i -g @vscode/vsce && vsce package`
- 商店素材：
  - 图标：`extensions/vscode/images/icon.svg`（如需 PNG，可导出为 128x128 并在 `package.json` 指向 PNG）
  - 截图：`extensions/vscode/images/screenshot1.svg`、`screenshot2.svg`
  - `package.json` 已配置 `icon.galleryBanner/screenshots`，可直接用于预览页
- 建议：首发阶段保持"无遥测、覆盖率门禁、近阈值导出"亮点，README 中突出两大支柱与一键命令

## 标记与变更日志

- 变更记录：`CHANGELOG.md`
- Git 标签：`git tag vX.Y.Z && git push --tags`
