"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const path = require("path");
const fs = require("fs");
suite('CI open branches (test-only)', () => {
    test('ciOpenExist opens ci.yml', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        assert.ok(ws, 'workspace required');
        const yml = path.resolve(ws, '.github/workflows/ci.yml');
        if (!fs.existsSync(path.dirname(yml)))
            fs.mkdirSync(path.dirname(yml), { recursive: true });
        fs.writeFileSync(yml, 'name: CI\n', 'utf-8');
        await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ciOpenExist');
    });
    test('ciOpenMissing does not throw', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        await ext.activate();
        await vscode.commands.executeCommand('mcpRulesAssistant._test_dispatchPanel', 'ciOpenMissing');
    });
});
//# sourceMappingURL=ci_open_branch.test.js.map