import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

suite('VS Code Extension Smoke', () => {
  test('activates and commands registered', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    assert.ok(ext!.isActive, 'Extension not active');
    const cmds = await vscode.commands.getCommands(true);
    assert.ok(cmds.includes('mcpRulesAssistant.openPanel'));
    assert.ok(cmds.includes('mcpRulesAssistant.commit'));
    assert.ok(cmds.includes('mcpRulesAssistant.push'));
  });

  test('webview includes coverage tree button in built bundle', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('btnCovTree'), 'Expected btnCovTree in bundled JS');
  });

  test('bundle contains covTreeData handler', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('covTreeData'), 'Expected covTreeData handler in bundled JS');
  });

  test('bundle contains covNear handler and button', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('covNear'), 'Expected covNear handler in bundled JS');
    assert.ok(js.includes('btnCovNear'), 'Expected btnCovNear button in bundled JS');
  });

  test('bundle contains btnShowWeak', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('btnShowWeak'), 'Expected btnShowWeak in bundled JS');
  });

  test('bundle contains view status strings', async () => {
    const ext = vscode.extensions.getExtension('your-team.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    const outJs = path.resolve(ext!.extensionPath, 'out', 'extension.js');
    const js = fs.readFileSync(outJs, 'utf-8');
    assert.ok(js.includes('当前视图') || js.includes('Show Near'), 'Expected view status strings in bundle');
  });
});
