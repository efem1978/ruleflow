import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('VS Code bundle CI buttons', () => {
  test('bundle includes ci buttons ids', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    ['btnCiSave','btnCiGen','btnCiPreview','btnCiOpen','btnCiValidate','btnInsertRules']
      .forEach(id => assert.ok(js.includes(id), 'Missing id in bundle: ' + id));
  });
});

