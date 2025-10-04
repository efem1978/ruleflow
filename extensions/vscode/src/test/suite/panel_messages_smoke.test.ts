import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('Panel message branches (test-only dispatch)', () => {
  test('statusUpdate (test-only) writes status.json', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    const p = path.resolve(ws, '.mcp/dashboard/status.json');
    try { fs.rmSync(p, { force: true }); } catch {}
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'statusUpdate');
    assert.ok(fs.existsSync(p), 'status.json should exist');
  });

  test('ideScaffold/compliance/openCompliance (test-only)', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    const ideDir = path.resolve(ws, '.mcp/ide');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ideScaffold');
    assert.ok(fs.existsSync(ideDir), '.mcp/ide should exist');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'compliance');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'openCompliance');
  });

  test('covNearPrompt (test-only)', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'covNearPrompt');
  });
});

