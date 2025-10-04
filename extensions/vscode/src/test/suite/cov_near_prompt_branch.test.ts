import * as assert from 'assert';
import * as vscode from 'vscode';

suite('covNearPrompt input branches (fake mode)', () => {
  test('cancel and boundary clamp', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    const orig = (vscode.window as any).showInputBox;
    try {
      // cancel path
      (vscode.window as any).showInputBox = async () => '';
      await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'covNearPrompt', last: 3 });
      // boundary clamp path (input 15 => clamp to 10)
      (vscode.window as any).showInputBox = async () => '15';
      await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'covNearPrompt', last: 3 });
    } finally {
      (vscode.window as any).showInputBox = orig;
    }
  });
});

