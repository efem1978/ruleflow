import * as path from 'path';
import { runTests } from '@vscode/test-electron';

async function main() {
  try {
    const extensionDevelopmentPath = path.resolve(__dirname, '../../');
    const extensionTestsPath = path.resolve(__dirname, './suite');

    // 允许通过环境变量覆盖 VS Code 启动参数，便于在受限环境运行
    // MCP_VSCODE_TEST_ARGS：
    // - 未设置：使用默认 ['--disable-extensions']
    // - 设为空字符串：不传任何额外参数 []
    // - 其他：按逗号分隔解析
    const raw = process.env.MCP_VSCODE_TEST_ARGS;
    const launchArgs = (raw === undefined)
      ? ['--disable-extensions']
      : (raw.trim() === '' ? [] : raw.split(',').map(s => s.trim()).filter(Boolean));
    await runTests({ extensionDevelopmentPath, extensionTestsPath, launchArgs });
  } catch (err) {
    console.error('Failed to run VS Code tests:', err);
    process.exit(1);
  }
}

main();
