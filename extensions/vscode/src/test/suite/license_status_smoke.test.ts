import * as assert from 'assert';
import * as vscode from 'vscode';

suite('License Status (smoke)', () => {
  test('mcpRulesAssistant.licenseStatus does not throw', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    // 后端可能未安装 Python；命令内部会捕获错误并以信息提示，不应抛出异常
    await vscode.commands.executeCommand('mcpRulesAssistant.licenseStatus');
  });
});
