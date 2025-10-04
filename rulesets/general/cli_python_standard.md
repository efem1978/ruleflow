# Python CLI 工具（标准档）/ Python CLI Tool (Standard)

- 风格与静态：ruff + black + mypy 全绿
- 测试：pytest；核心命令≥90%覆盖率；subprocess 模拟
- 命令规范：Click/Typer；子命令清晰；--help 完整
- 输出：支持 --json 和人类可读格式；进度条（tqdm）
- 错误处理：退出码明确（0=成功，1=错误）；友好错误提示
- 配置：支持配置文件（YAML/TOML）；环境变量覆盖
- 安全：输入验证；路径遍历防护；敏感信息掩码
- 打包：pyproject.toml；entry_points；支持 pipx
- 文档：README 安装和快速开始；命令示例；故障排除
- 提交：Conventional Commits；pre-commit hooks
- 推送：全量测试 + 覆盖率≥90% + bandit 扫描
- 跨平台：Windows/Linux/macOS 兼容；路径使用 pathlib
