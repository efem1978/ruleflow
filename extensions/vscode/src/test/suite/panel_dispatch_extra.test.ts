import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

async function setFakeMode(ws: string) {
  const s = path.resolve(ws, '.mcp/dashboard/fake_mode');
  fs.mkdirSync(path.dirname(s), { recursive: true });
  fs.writeFileSync(s, '1', 'utf-8');
}

suite('panel dispatch extra coverage (fake)', () => {
  test('exercise extra panel actions and public commands', async () => {
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    assert.ok(ws, 'workspace required');
    await setFakeMode(ws);

    await vscode.commands.executeCommand('mcpRulesAssistant._test_clearFakeCalls');

    // Open panel and wait ready
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');

    // Dispatch a variety of panel actions to cover branches
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'statusUpdate');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ideScaffold');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'compliance');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'openCompliance');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'openIdeDir');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ciOpenExist');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ciOpenMissing');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'covNearPrompt');

    // Quick commands to open generated files (CSV/MD/JSON)
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openWeakCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openNearCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openGroupsCsv');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openJbGroupsMd');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchQuick', 'openJbVerify');

    // License status path
    await vscode.commands.executeCommand('mcpRulesAssistant.licenseStatus');

    // Enable chat append and run once
    await vscode.commands.executeCommand('mcpRulesAssistant._test_chatSetEnabled', true);
    const ok = await vscode.commands.executeCommand('mcpRulesAssistant.chatAppendSummary', 'unit summary');
    assert.ok(ok === true, 'chat append should return true when enabled');

    // NL history add/clear
    await vscode.commands.executeCommand('mcpRulesAssistant._test_nlHistory', 'add', 'hello');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_nlHistory', 'clear');

    // Open status (should exist after panel actions)
    await vscode.commands.executeCommand('mcpRulesAssistant.openStatus');

    // Open memory read path
    await vscode.commands.executeCommand('mcpRulesAssistant.openMemory');

    // Ensure fake calls contain multiple tool calls
    const calls = (await vscode.commands.executeCommand('mcpRulesAssistant._test_getFakeCalls')) as any[];
    assert.ok(Array.isArray(calls) && calls.length > 0, 'expected fake tool calls recorded');
  });
});

