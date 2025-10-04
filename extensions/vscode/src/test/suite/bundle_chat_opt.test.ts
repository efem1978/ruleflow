import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('Bundle contains Chat (optional) UI', () => {
  test('chat enable/disable/preview buttons exist', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('btnChatEnable'), 'Expected btnChatEnable');
    assert.ok(js.includes('btnChatDisable'), 'Expected btnChatDisable');
    assert.ok(js.includes('btnChatPreview'), 'Expected btnChatPreview');
  });
});

