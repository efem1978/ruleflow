import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

function ensureFile(p: string, content = '') {
  const dir = path.dirname(p);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(p)) fs.writeFileSync(p, content, 'utf-8');
}

suite('Quick actions open CSV/MD', () => {
  test('openWeakCsv / openNearCsv / openGroupsCsv / openJbGroupsMd', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required for test');

    // Prepare minimal files under .mcp/dashboard
    const weak = path.resolve(ws, '.mcp/dashboard/weak_top.csv');
    const near = path.resolve(ws, '.mcp/dashboard/near_top.csv');
    const groups = path.resolve(ws, '.mcp/dashboard/groups.csv');
    const md = path.resolve(ws, '.mcp/dashboard/jb_groups.md');
    ensureFile(weak, 'prefix,coverage,threshold,weak_count,files_count\n');
    ensureFile(near, 'file,coverage,threshold\n');
    ensureFile(groups, 'prefix,coverage,threshold,weak_count,files_count\n');
    ensureFile(md, '| prefix | coverage | threshold | weak/files |\n|---|---:|---:|---:|\n');

    // Dispatch test-only quick actions
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openWeakCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openNearCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openGroupsCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openJbGroupsMd');
  });
});

