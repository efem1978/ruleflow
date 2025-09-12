import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('CSV preview fallback formatting', () => {
  test('groups.csv with fewer columns triggers raw passthrough', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext);
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws);
    const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
    fs.mkdirSync(path.dirname(sentinel), { recursive: true });
    fs.writeFileSync(sentinel, '1', 'utf-8');
    const p = path.resolve(ws, '.mcp/dashboard/groups.csv');
    fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, 'prefix,coverage\nmod,0.97\n', 'utf-8');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await new Promise(r => setTimeout(r, 300));
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'csvPreviewPick', which: 'groups.csv' });
    await new Promise(r => setTimeout(r, 150));
  });
});
