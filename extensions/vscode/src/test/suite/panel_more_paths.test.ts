import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Panel more message paths (fake, split)', () => {
  test('memory only', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
  await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
  await new Promise(r => setTimeout(r, 300));
  await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'memory' });
  await new Promise(r => setTimeout(r, 150));
  });

  test('ciFetch/ciSave only', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
  await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
  await new Promise(r => setTimeout(r, 300));
  await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciFetch' });
  await new Promise(r => setTimeout(r, 150));
  await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciSave', data: { mutation_gate_strict: false } });
  await new Promise(r => setTimeout(r, 150));
  });

  test('prepare env only', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
  await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
  await new Promise(r => setTimeout(r, 300));
  await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'prepareEnvDry' });
  await new Promise(r => setTimeout(r, 150));
  await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'prepareEnvInstall' });
  await new Promise(r => setTimeout(r, 150));
  });
});
