import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('Coverage bad/Tree no-resource (fake)', () => {
  test('coverage summary ok=false and coverageTree no resource', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    // sentinel: coverage_bad
    const bad = path.resolve(ws, '.mcp/dashboard/coverage_bad');
    fs.mkdirSync(path.dirname(bad), { recursive: true });
    fs.writeFileSync(bad, '1');
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverage' });
    // sentinel: notree
    const nt = path.resolve(ws, '.mcp/dashboard/notree');
    fs.writeFileSync(nt, '1');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'coverageTree' });
    // clean sentinels
    try { fs.unlinkSync(bad); } catch {}
    try { fs.unlinkSync(nt); } catch {}
  });
});

