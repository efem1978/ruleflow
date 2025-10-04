# Markdownlint 配置说明 / Markdownlint Configuration Guide

## 目标

- 确保所有 Markdown 文档符合一致的格式规范
- 通过 CI 和 pre-commit hooks 自动检查，防止格式问题进入代码库
- 提供灵活的配置策略，适应不同类型文档的需求

## 配置文件层级

### 1. 根目录配置：`.markdownlint.json`

适用于根目录的 Markdown 文件（如 `README.md`、`CHANGELOG.md`等）。

**策略**：放宽大部分规则，保留基本的 Markdown 语法检查。

**禁用规则**：
- `MD009`：行尾空格
- `MD012`：多余空行
- `MD013`：行长度限制
- `MD022`：标题周围空行
- `MD024`：重复标题
- `MD029`：有序列表编号
- `MD031`/`MD032`：代码围栏和列表周围空行
- `MD033`：内联 HTML
- `MD034`：裸 URL
- `MD040`：代码围栏语言
- `MD041`：首行必须是 H1 标题
- `MD005`/`MD007`：列表缩进

### 2. docs/ 目录配置：`docs/.markdownlint.json`

适用于 `docs/` 目录下的所有文档。

**策略**：与根目录相同，保持灵活性以适应技术文档的复杂需求。

### 3. docs/releases/ 目录配置：`docs/releases/.markdownlint.json`

适用于发布说明文档。

**策略**：针对自动生成的发布说明，禁用特定规则。

**禁用规则**：
- `MD013`：行长度限制
- `MD022`：标题周围空行
- `MD032`：列表周围空行
- `MD012`：多余空行

### 4. 特殊文档：文件级禁用指令

对于特定的操作清单或大型参考文档，在文件头部添加禁用指令：

```markdown
<!-- markdownlint-disable MD013 MD031 MD032 MD040 MD022 MD003 MD026 MD009 -->
<!-- 说明：本文件为操作清单，保留紧凑格式以便快速执行 -->
```

## CI 集成

在 `.github/workflows/ci.yml` 中添加了 Markdown lint 检查：

```yaml
- name: Markdown Lint (markdownlint-cli2)
  run: |
    npx -y markdownlint-cli2 "docs/**/*.md" "*.md"
```

**执行时机**：每次 push 和 pull request

**失败策略**：任何 markdownlint 错误都会导致 CI 失败

## Pre-commit Hooks 集成

在 `.pre-commit-config.yaml` 中添加了两个 markdownlint hooks：

```yaml
- repo: https://github.com/igorshubovych/markdownlint-cli
  rev: v0.42.0
  hooks:
    - id: markdownlint-fix
      stages: [pre-commit]
      args: ["--config", ".markdownlint.json"]
    - id: markdownlint
      stages: [push]
      args: ["--config", ".markdownlint.json"]
```

**执行时机**：
- `markdownlint-fix`：pre-commit 阶段，自动修复可修复的问题
- `markdownlint`：pre-push 阶段，严格检查所有规则

## 本地使用

### 检查所有 Markdown 文件

```bash
npx markdownlint-cli2 "*.md" "docs/**/*.md"
```

### 检查特定文件

```bash
npx markdownlint-cli2 README.md
```

### 自动修复

```bash
npx markdownlint-cli2-fix "*.md" "docs/**/*.md"
```

### 使用 pre-commit

```bash
# 安装 hooks
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push

# 手动运行所有 hooks
pre-commit run --all-files

# 运行特定 hook
pre-commit run markdownlint --all-files
```

## 配置策略说明

### 为什么放宽这么多规则？

1. **实用性优先**：技术文档需要灵活性，严格的格式限制可能影响内容质量
2. **兼容性**：支持自动生成的文档、操作清单、长命令行等特殊格式
3. **渐进式改进**：先确保零告警，再根据需要逐步收紧规则
4. **团队效率**：避免花费过多时间在格式调整上

### 何时应该收紧规则？

如果团队决定收紧某些规则，建议按以下顺序：

1. **启用 MD040**（代码围栏语言）：提升代码块的语法高亮
2. **启用 MD029**（有序列表编号）：统一列表格式
3. **启用 MD031/MD032**（围栏和列表周围空行）：提升可读性
4. **启用 MD013**（行长度限制，设置为 120-150）：改善代码审查体验

## 维护与审查

### 定期审查（每季度）

1. 检查是否有新的规则可以启用
2. 评估当前配置是否仍然适用
3. 更新文档说明禁用规则的原因

### 文档质量检查清单

- [ ] 所有 Markdown 文件通过 markdownlint 检查
- [ ] CI 中的 markdownlint 步骤运行成功
- [ ] Pre-commit hooks 正常工作
- [ ] 配置文件有清晰的注释说明
- [ ] 团队成员了解配置策略

## 常见问题

### Q: 为什么 pre-commit 没有自动修复我的文件？

A: `markdownlint-fix` 只在 pre-commit 阶段运行。你可以手动运行：
```bash
pre-commit run markdownlint-fix --all-files
```

### Q: 如何为特定文件禁用某个规则？

A: 在文件头部添加注释：
```markdown
<!-- markdownlint-disable MD013 -->
```

### Q: 如何查看所有可用的 markdownlint 规则？

A: 访问 [markdownlint 规则文档](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md)

### Q: CI 失败了，但本地检查通过？

A: 确保你使用的是相同版本的 markdownlint-cli2：
```bash
npx markdownlint-cli2@latest "*.md" "docs/**/*.md"
```

## 参考资源

- [markdownlint GitHub](https://github.com/DavidAnson/markdownlint)
- [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)
- [markdownlint 规则文档](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md)
- [pre-commit 文档](https://pre-commit.com/)
