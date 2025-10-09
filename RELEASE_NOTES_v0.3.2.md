# v0.3.2 - OSS Release (MIT License) | OSS 开源版本发布

**Release Date | 发布日期**: October 9, 2025

> **Language | 语言**: [English](#english) | [中文](#中文)

---

<a name="english"></a>
## English Version

## 🌟 Why RuleFlow?

**RuleFlow** (MCP Rules & Context Assistant) solves a critical challenge in AI-assisted development: **maintaining consistency and quality across multi-turn AI collaboration sessions**. 

### What Makes Us Different

- **🧠 Context Memory**: 20-turn rolling memory ensures AI assistants remember your project rules across sessions
- **📋 Smart Rule Governance**: Auto-extract coding standards from docs, generate enforceable CI/CD gates
- **✅ Quality Gatekeeper**: Built-in coverage policies (core≥98%, others≥95%) prevent quality degradation
- **🌍 Bilingual by Design**: Full English/中文 support in CLI, docs, and MCP interface
- **🔒 Privacy First**: Zero telemetry, all data stays local

### Perfect For

- **AI Pair Programmers**: Keep multi-session AI workflows consistent
- **Quality-Conscious Teams**: Enforce strict coverage and security standards
- **Multi-IDE Organizations**: Unified rules across VS Code, Cursor, Windsurf, JetBrains
- **Open Source Projects**: Transparent governance with audit trails

---

## 🎉 Major Changes

### Open Source Transition
This release marks the **complete transition to open source** under the MIT License. All proprietary licensing mechanisms have been removed, making the entire codebase freely available for commercial and personal use.

### What's New

#### 🚀 One-Click Installation
- **Cross-platform installer scripts** (`install.sh` for Linux/macOS, `install.bat` for Windows)
- Zero-config setup with automatic dependency checking
- Virtual environment creation and package installation

#### 📚 Comprehensive Documentation
- **README.md**: Complete rewrite with bilingual (English/中文) support
- **CONTRIBUTING.md**: OSS contribution guidelines
- **CODE_OF_CONDUCT.md**: Community standards (Contributor Covenant)
- **SUPPORT.md**: Help resources and FAQ

### 🔧 Technical Changes

#### Removed
- ❌ All license validation gates from server and VS Code extension
- ❌ `license_utils.py` module and 18+ license test files
- ❌ Commercial release validation scripts
- ❌ License UI, commands, and message handlers from VS Code extension

#### Improved
- ✅ Fixed code quality issues (`hooks.py` undefined variable)
- ✅ Enhanced Mypy type safety configuration
- ✅ Updated all documentation to reflect OSS model

### 📊 Quality Metrics
- **Tests**: 677/815 passing (83%)
- **Coverage**: 95.6% (core modules maintain high coverage)
- **License**: MIT (synchronized across LICENSE file and `pyproject.toml`)

---

## 📥 Installation

### Quick Start

**Linux / macOS**:
```bash
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow
bash install.sh
```

**Windows**:
```bat
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow
install.bat
```

---

## 🔗 Resources

- **Documentation**: [README.md](https://github.com/efem1978/ruleflow/blob/release/open-source/README.md)
- **Contributing**: [CONTRIBUTING.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CONTRIBUTING.md)
- **Support**: [SUPPORT.md](https://github.com/efem1978/ruleflow/blob/release/open-source/SUPPORT.md)
- **License**: [MIT License](https://github.com/efem1978/ruleflow/blob/release/open-source/LICENSE)

---

## 📝 Full Changelog

See [CHANGELOG.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CHANGELOG.md) for complete version history.

### Commits in this Release
- `36557a2`: test: remove license-related tests for OSS release
- `bac2bc1`: docs(oss): add OSS release documentation and install scripts
- `a22b92a`: refactor(oss)!: finalize OSS conversion - fix residuals & sync versions

---

## 🤝 Join Our Community

We're building the future of AI-assisted development together! **Your expertise is needed.**

### How You Can Contribute

#### 🧪 **For Testers & Users**
- Try the tool in your projects and share feedback
- Report bugs or edge cases you encounter
- Suggest features that would make your workflow better
- Star ⭐ the repo to show support

#### 💻 **For Developers**
- **Backend**: Improve rule parsing, coverage analysis, or MCP server logic
- **Frontend**: Enhance VS Code/Cursor/Windsurf extension UX
- **DevOps**: Optimize CI/CD pipelines or Docker workflows
- **See [CONTRIBUTING.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CONTRIBUTING.md) for dev setup**

#### 📝 **For Writers & Translators**
- Improve documentation clarity
- Add tutorials or use case examples
- Translate docs to more languages (Spanish, Japanese, German, etc.)
- Write blog posts or case studies

#### 🎨 **For Designers**
- Propose UI/UX improvements for IDE extensions
- Create demo videos or screenshots
- Design better onboarding experiences

#### 🌐 **For Community Builders**
- Answer questions in [GitHub Discussions](https://github.com/efem1978/ruleflow/discussions)
- Share your success stories
- Help newcomers get started

### Get Started Today

1. **Try it**: `bash install.sh` (takes < 2 minutes)
2. **Give feedback**: [Open an issue](https://github.com/efem1978/ruleflow/issues/new)
3. **Spread the word**: Share with colleagues who use AI coding tools

---

## 🙏 Acknowledgments

Thank you to everyone who contributed ideas, feedback, and code to make this OSS release possible. Special thanks to the MCP (Model Context Protocol) community for inspiring this approach to AI-assisted development.

**Together, we're making AI pair programming more reliable, consistent, and accessible to everyone.**

---

⭐ **Star us on GitHub** if you find this project useful!  
🐦 **Share** with your network  
💬 **Join** the conversation in [Discussions](https://github.com/efem1978/ruleflow/discussions)

---
---

<a name="中文"></a>
## 中文版本

## 🌟 为什么选择 RuleFlow？

**RuleFlow**（MCP 规则与上下文助手）解决了 AI 辅助开发中的一个关键挑战：**在多轮 AI 协作会话中保持一致性和质量**。

### 我们的独特之处

- **🧠 上下文记忆**：20轮滚动记忆确保 AI 助手跨会话记住您的项目规则
- **📋 智能规则治理**：从文档自动提取编码标准，生成可执行的 CI/CD 门禁
- **✅ 质量守门员**：内置覆盖率策略（核心≥98%，其他≥95%）防止质量下降
- **🌍 双语设计**：CLI、文档和 MCP 接口全面支持中英文
- **🔒 隐私优先**：零遥测，所有数据保留在本地

### 完美适用于

- **AI 结对编程者**：保持多会话 AI 工作流的一致性
- **质量意识团队**：执行严格的覆盖率和安全标准
- **多 IDE 组织**：在 VS Code、Cursor、Windsurf、JetBrains 间统一规则
- **开源项目**：透明的治理与审计追踪

---

## 🎉 重大变更

### 开源转型
本次发布标志着**完全转型为开源**，采用 MIT 许可证。所有专有许可机制已被移除，整个代码库可免费用于商业和个人用途。

### 新增功能

#### 🚀 一键安装
- **跨平台安装脚本**（Linux/macOS 用 `install.sh`，Windows 用 `install.bat`）
- 零配置设置，自动依赖检查
- 虚拟环境创建和包安装

#### 📚 完善文档
- **README.md**：完全重写，支持双语（English/中文）
- **CONTRIBUTING.md**：OSS 贡献指南
- **CODE_OF_CONDUCT.md**：社区准则（Contributor Covenant）
- **SUPPORT.md**：帮助资源和常见问题

### 🔧 技术变更

#### 移除
- ❌ 从服务器和 VS Code 扩展中移除所有许可验证门禁
- ❌ `license_utils.py` 模块和 18+ 个许可测试文件
- ❌ 商业发布验证脚本
- ❌ VS Code 扩展中的许可 UI、命令和消息处理器

#### 改进
- ✅ 修复代码质量问题（`hooks.py` 未定义变量）
- ✅ 增强 Mypy 类型安全配置
- ✅ 更新所有文档以反映 OSS 模型

### 📊 质量指标
- **测试**：677/815 通过（83%）
- **覆盖率**：95.6%（核心模块保持高覆盖率）
- **许可证**：MIT（LICENSE 文件和 `pyproject.toml` 同步）

---

## 📥 安装

### 快速开始

**Linux / macOS**：
```bash
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow
bash install.sh
```

**Windows**：
```bat
git clone https://github.com/efem1978/ruleflow.git
cd ruleflow
install.bat
```

---

## 🔗 资源

- **文档**：[README.md](https://github.com/efem1978/ruleflow/blob/release/open-source/README.md)
- **贡献指南**：[CONTRIBUTING.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CONTRIBUTING.md)
- **支持**：[SUPPORT.md](https://github.com/efem1978/ruleflow/blob/release/open-source/SUPPORT.md)
- **许可证**：[MIT License](https://github.com/efem1978/ruleflow/blob/release/open-source/LICENSE)

---

## 📝 完整更新日志

查看 [CHANGELOG.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CHANGELOG.md) 了解完整版本历史。

### 本次发布的提交
- `36557a2`：测试：移除 OSS 发布相关的许可测试
- `bac2bc1`：文档：添加 OSS 发布文档和安装脚本
- `a22b92a`：重构：完成 OSS 转换 - 修复残留并同步版本

---

## 🤝 加入我们的社区

我们正在共同构建 AI 辅助开发的未来！**需要您的专业知识。**

### 您可以如何贡献

#### 🧪 **测试者 & 用户**
- 在您的项目中试用工具并分享反馈
- 报告您遇到的 bug 或边缘案例
- 建议能改善您工作流的功能
- Star ⭐ 仓库表示支持

#### 💻 **开发者**
- **后端**：改进规则解析、覆盖率分析或 MCP 服务器逻辑
- **前端**：增强 VS Code/Cursor/Windsurf 扩展的用户体验
- **DevOps**：优化 CI/CD 流水线或 Docker 工作流
- **查看 [CONTRIBUTING.md](https://github.com/efem1978/ruleflow/blob/release/open-source/CONTRIBUTING.md) 了解开发设置**

#### 📝 **作者 & 翻译者**
- 提高文档清晰度
- 添加教程或用例示例
- 将文档翻译成更多语言（西班牙语、日语、德语等）
- 撰写博客文章或案例研究

#### 🎨 **设计师**
- 为 IDE 扩展提出 UI/UX 改进建议
- 创建演示视频或截图
- 设计更好的入门体验

#### 🌐 **社区建设者**
- 在 [GitHub Discussions](https://github.com/efem1978/ruleflow/discussions) 中回答问题
- 分享您的成功故事
- 帮助新手入门

### 今天就开始

1. **试用**：`bash install.sh`（不到 2 分钟）
2. **提供反馈**：[提交 Issue](https://github.com/efem1978/ruleflow/issues/new)
3. **传播**：与使用 AI 编程工具的同事分享

---

## 🙏 致谢

感谢所有为这次 OSS 发布贡献想法、反馈和代码的人。特别感谢 MCP（Model Context Protocol）社区对这种 AI 辅助开发方法的启发。

**我们共同让 AI 结对编程变得更可靠、一致和普及。**

---

⭐ **在 GitHub 上给我们 Star**，如果您觉得这个项目有用！  
🐦 **分享**给您的社交网络  
💬 **加入** [Discussions](https://github.com/efem1978/ruleflow/discussions) 中的对话
