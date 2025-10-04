import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Extension Host Commands (Light)', () => {
  test('openPlan/openMemory do not throw when files exist or not', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    // These commands should be registered and handle missing files gracefully.
    await vscode.commands.executeCommand('mcpRulesAssistant.openPlan');
    await vscode.commands.executeCommand('mcpRulesAssistant.openMemory');
  });
});

