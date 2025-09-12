import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Open Panel command (smoke)', () => {
  test('mcpRulesAssistant.openPanel does not throw', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    // Even在无 Python 的受限环境下，openPanel 只会尝试启动后端并渲染 Webview，不应抛出异常
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
  });
});

