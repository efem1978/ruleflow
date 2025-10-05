import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Plan message branches (fake — stabilized)', () => {
  test('mark in progress and done', async () => {
    process.env.RULEFLOW_TEST_FAKE = '1';
    const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
    assert.ok(ext, 'Extension not found');
    await ext!.activate();
    await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
    await vscode.commands.executeCommand('mcpRulesAssistant._test_waitReady');
    const origPick = (vscode.window as any).showQuickPick;
    const origInput = (vscode.window as any).showInputBox;
    try {
      // 标记进行中 + 输入当前步骤
      (vscode.window as any).showQuickPick = async () => '标记进行中 / In progress';
      (vscode.window as any).showInputBox = async () => 'step-1';
      await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'plan' });
      // 标记完成
      (vscode.window as any).showQuickPick = async () => '标记完成 / Done';
      await vscode.commands.executeCommand('mcpRulesAssistant._test_sendPanelMessage', { t: 'plan' });
    } finally {
      (vscode.window as any).showQuickPick = origPick;
      (vscode.window as any).showInputBox = origInput;
    }
  });
});
