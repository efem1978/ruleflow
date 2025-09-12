import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

suite('Webview open message (inside workspace)', () => {
  test('simulate open .mcp/dashboard/weak_top.csv', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required for test');
    // 准备一个存在的文件（verify/coverage-export 后通常存在）；若不存在则创建一个最小占位
    const p = path.resolve(ws, '.mcp/dashboard/weak_top.csv');
    if (!fs.existsSync(p)) {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, 'prefix,coverage,threshold,weak_count,files_count\n', 'utf-8');
    }
    await vscode.commands.executeCommand('mcpRulesAssistant._test_openPanelLite');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_simulateWebviewMessage', { t: 'open', path: '.mcp/dashboard/weak_top.csv', line: 1 });
  });
});

