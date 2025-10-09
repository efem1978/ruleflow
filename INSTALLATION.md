# RuleFlow 安装指南 | Installation Guide

> **一键安装，跨平台支持 | One-Click Installation, Cross-Platform Support**

[English](#english) | [中文](#中文)

---

<a name="中文"></a>
## 中文版本

### 🚀 快速开始

RuleFlow 提供**一键安装脚本**，自动完成以下安装：
- ✅ Python CLI 工具
- ✅ VS Code/Cursor/Windsurf 扩展
- ✅ Git hooks 和配置

**无需分别安装，一次搞定！**

---

### 📦 安装步骤

#### Linux / macOS

```bash
# 1. 克隆仓库
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow

# 2. 运行一键安装脚本
bash install.sh

# 3. 完成！
```

#### Windows

```bat
REM 1. 克隆仓库
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow

REM 2. 运行一键安装脚本
install.bat

REM 3. 完成！
```

---

### 🎯 安装内容

一键安装脚本会自动完成：

| 组件 | 说明 |
|------|------|
| **Python 环境** | 创建虚拟环境 `.venv` |
| **CLI 工具** | 安装 `mcp-rules-assistant` 命令行工具 |
| **配置初始化** | 创建 `.mcp/assistant.yaml` 配置文件 |
| **Git Hooks** | 安装代码质量检查钩子 |
| **IDE 扩展** | 自动检测并安装 VS Code/Cursor/Windsurf 扩展 |

---

### 🔧 支持的 IDE

**好消息：VS Code 扩展通用！**

| IDE | 支持状态 | 说明 |
|-----|---------|------|
| **VS Code** | ✅ 完全支持 | 自动安装 .vsix 扩展 |
| **Cursor** | ✅ 完全支持 | 兼容 VS Code 扩展 |
| **Windsurf** | ✅ 完全支持 | 兼容 VS Code 扩展 |
| **JetBrains** | ⏳ 计划中 | 需要单独插件 |

**一次安装，多个 IDE 通用！无需重复安装。**

---

### 📝 安装后验证

```bash
# 1. 激活虚拟环境
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 验证 CLI 工具
mcp-rules-assistant --version

# 3. 检查配置
mcp-rules-assistant diagnose

# 4. 查看帮助
mcp-rules-assistant --help
```

---

### 🔄 环境变量控制

安装脚本支持环境变量自定义：

```bash
# 跳过 IDE 扩展安装
INSTALL_VSCODE_EXT=0 bash install.sh

# 跳过 Git hooks 安装
INSTALL_HOOKS=0 bash install.sh

# 跳过配置初始化
SKIP_INIT=1 bash install.sh

# 安装开发依赖
INSTALL_DEV=1 bash install.sh
```

---

### 🛠️ 手动安装（高级用户）

如果需要手动控制安装过程：

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装 Python 包
pip install -e .

# 3. 初始化配置
mcp-rules-assistant init

# 4. 安装 Git hooks（可选）
mcp-rules-assistant install-hooks

# 5. 手动安装 IDE 扩展（可选）
code --install-extension extensions/vscode/mcp-rules-assistant-0.3.2.vsix
```

---

### ❓ 常见问题

**Q: 是否需要为不同 IDE 分别安装？**  
A: **不需要！** VS Code 扩展兼容 VS Code、Cursor 和 Windsurf。一次安装，所有 IDE 都能用。

**Q: 没有检测到 IDE 怎么办？**  
A: 可以手动安装扩展：
```bash
code --install-extension extensions/vscode/mcp-rules-assistant-0.3.2.vsix
```
或在 IDE 中：`扩展 → 从 VSIX 安装...`

**Q: 如何更新到新版本？**  
A: 
```bash
git pull
bash install.sh
```

---

## 🆘 需要帮助？

- **文档**: [README.md](README.md)
- **支持**: [SUPPORT.md](SUPPORT.md)
- **Issues**: [GitHub Issues](https://github.com/efem1978/ruleflow/issues)

---
---

<a name="english"></a>
## English Version

### 🚀 Quick Start

RuleFlow provides **one-click installation scripts** that automatically install:
- ✅ Python CLI tool
- ✅ VS Code/Cursor/Windsurf extension
- ✅ Git hooks and configuration

**No separate installations needed!**

---

### 📦 Installation Steps

#### Linux / macOS

```bash
# 1. Clone repository
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow

# 2. Run one-click installer
bash install.sh

# 3. Done!
```

#### Windows

```bat
REM 1. Clone repository
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow

REM 2. Run one-click installer
install.bat

REM 3. Done!
```

---

### 🎯 What Gets Installed

The installer automatically sets up:

| Component | Description |
|-----------|-------------|
| **Python Environment** | Creates virtual environment `.venv` |
| **CLI Tool** | Installs `mcp-rules-assistant` command |
| **Configuration** | Creates `.mcp/assistant.yaml` config file |
| **Git Hooks** | Installs code quality check hooks |
| **IDE Extension** | Auto-detects and installs for VS Code/Cursor/Windsurf |

---

### 🔧 Supported IDEs

**Good news: VS Code extension is universal!**

| IDE | Support | Notes |
|-----|---------|-------|
| **VS Code** | ✅ Full | Auto-installs .vsix extension |
| **Cursor** | ✅ Full | Compatible with VS Code extensions |
| **Windsurf** | ✅ Full | Compatible with VS Code extensions |
| **JetBrains** | ⏳ Planned | Requires separate plugin |

**Install once, works everywhere! No duplicate installations needed.**

---

### 📝 Verify Installation

```bash
# 1. Activate virtual environment
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Verify CLI tool
mcp-rules-assistant --version

# 3. Check configuration
mcp-rules-assistant diagnose

# 4. View help
mcp-rules-assistant --help
```

---

### 🔄 Environment Variables

Customize installation with environment variables:

```bash
# Skip IDE extension installation
INSTALL_VSCODE_EXT=0 bash install.sh

# Skip Git hooks installation
INSTALL_HOOKS=0 bash install.sh

# Skip configuration initialization
SKIP_INIT=1 bash install.sh

# Install development dependencies
INSTALL_DEV=1 bash install.sh
```

---

### 🛠️ Manual Installation (Advanced)

For manual control over the installation process:

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python package
pip install -e .

# 3. Initialize configuration
mcp-rules-assistant init

# 4. Install Git hooks (optional)
mcp-rules-assistant install-hooks

# 5. Manually install IDE extension (optional)
code --install-extension extensions/vscode/mcp-rules-assistant-0.3.2.vsix
```

---

### ❓ FAQ

**Q: Do I need to install separately for different IDEs?**  
A: **No!** The VS Code extension works with VS Code, Cursor, and Windsurf. Install once, use everywhere.

**Q: What if my IDE isn't detected?**  
A: Install manually:
```bash
code --install-extension extensions/vscode/mcp-rules-assistant-0.3.2.vsix
```
Or in IDE: `Extensions → Install from VSIX...`

**Q: How to update to a new version?**  
A: 
```bash
git pull
bash install.sh
```

---

## 🆘 Need Help?

- **Documentation**: [README.md](README.md)
- **Support**: [SUPPORT.md](SUPPORT.md)
- **Issues**: [GitHub Issues](https://github.com/efem1978/ruleflow/issues)
