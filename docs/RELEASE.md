发布指南 Release Guide

Python 包 Packaging
- 版本：在 `mcp_rules_assistant/__init__.py` 更新 `__version__`
- 打包：`make package`（或 `python -m build`）
- 发布：`python -m pip install --upgrade twine && twine upload dist/*`
- 检查：`make release-check`（执行 `twine check dist/*`）

VS Code 扩展（可选）
- 编译：`npm --prefix extensions/vscode run compile`
- 打包：可使用 `vsce package`（需安装 `@vscode/vsce`）
  - 示例：`npm i -g @vscode/vsce && vsce package`

标记与变更日志
- 变更记录：`CHANGELOG.md`
- Git 标签：`git tag vX.Y.Z && git push --tags`
