import * as assert from 'assert';
import * as vscode from 'vscode';

suite('NL history (test-only)', () => {
  test('add and clear history', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const n1 = await vscode.commands.executeCommand('mcpRulesAssistant._test_nlHistory', 'add', 'first');
    assert.ok(typeof n1 === 'number' && (n1 as number) >= 1);
    const n2 = await vscode.commands.executeCommand('mcpRulesAssistant._test_nlHistory', 'add', 'second');
    assert.ok(typeof n2 === 'number' && (n2 as number) >= 2);
    const n3 = await vscode.commands.executeCommand('mcpRulesAssistant._test_nlHistory', 'clear');
    assert.strictEqual(n3, 0);
  });
});

