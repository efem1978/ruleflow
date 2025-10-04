# 前端 TypeScript + React（TDD 严格档）/ Frontend TypeScript + React (TDD Strict)

- 风格与静态：ESLint + Prettier + TypeScript strict mode 全绿
- 类型检查：tsc --noEmit 零错误；禁止 any（除明确注释的 escape hatch）
- 测试：Jest/Vitest + React Testing Library；核心组件≥95%覆盖率
- E2E测试：Playwright 关键用户流程；视觉回归测试（Percy/Chromatic）
- 警告：零警告策略；禁止 skip/only/fit
- 安全：npm audit 无高危；依赖锁定（package-lock.json/yarn.lock）
- 提交：Conventional Commits；Husky pre-commit hooks
- 推送：全量测试 + 类型检查 + 打包验证 + Bundle 大小门禁
- 组件规范：单一职责；Props 类型严格；Hooks 依赖完整
- 状态管理：避免过度嵌套；优先组合 Context；全局状态最小化
- 性能：懒加载路由；代码分割；memo 优化关键组件
- 可访问性：ARIA 标签；键盘导航；屏幕阅读器兼容
- 浏览器兼容：支持最近2个主版本；Polyfill 按需加载
