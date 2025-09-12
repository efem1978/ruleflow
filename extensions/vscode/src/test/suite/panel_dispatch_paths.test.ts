import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

function ensureFile(p: string, content: string) {
  const dir = path.dirname(p);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(p, content, 'utf-8');
}

suite('Panel dispatch common paths (fake mode, split)', () => {
  test('loadRules (compiled+json fallback)', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext);
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws);
    ensureFile(path.resolve(ws, '.mcp/rules_compiled.md'), '# Rules\n');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await new Promise(r => setTimeout(r, 100));
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'loadRules' });
    await new Promise(r => setTimeout(r, 50));
  });

  test('coverage summary/groups/near (single message)', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext);
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws);
    ensureFile(path.resolve(ws, '.mcp/dashboard/weak_top.csv'), 'file,coverage,threshold,weak_count,files_count\nmod.py,0.90,0.95,1,1\n');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await new Promise(r => setTimeout(r, 100));
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverage' });
    await new Promise(r => setTimeout(r, 50));
  });

  test('csvPreviewPick weak_top only', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext);
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws);
    ensureFile(path.resolve(ws, '.mcp/dashboard/weak_top.csv'), 'file,coverage,threshold,weak_count,files_count\nmod.py,0.90,0.95,1,1\n');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await new Promise(r => setTimeout(r, 100));
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'csvPreviewPick', which: 'weak_top.csv' });
    await new Promise(r => setTimeout(r, 50));
  });

  test('ciCheck only', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext);
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws);
    ensureFile(path.resolve(ws, '.github/workflows/ci.yml'), 'name: CI\n');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await new Promise(r => setTimeout(r, 100));
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'ciCheck' });
    await new Promise(r => setTimeout(r, 50));
  });
});
