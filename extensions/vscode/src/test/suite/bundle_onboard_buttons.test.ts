import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('Bundle contains onboard buttons', () => {
  test('btnOnboardPreview and btnOnboardApply in bundle', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('btnOnboardPreview'), 'Expected btnOnboardPreview in bundled JS');
    assert.ok(js.includes('btnOnboardApply'), 'Expected btnOnboardApply in bundled JS');
  });
});

