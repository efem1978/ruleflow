import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('Open Panel command (smoke)', () => {
  test('mcpRulesAssistant.openPanel does not throw', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    const sentinel = path.resolve(ws, '.mcp/dashboard/fake_mode');
    fs.mkdirSync(path.dirname(sentinel), { recursive: true });
    fs.writeFileSync(sentinel, '1', 'utf-8');
    await ext!.activate();
    // Even在无 Python 的受限环境下，openPanel 只会尝试启动后端并渲染 Webview，不应抛出异常
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
  });
});
