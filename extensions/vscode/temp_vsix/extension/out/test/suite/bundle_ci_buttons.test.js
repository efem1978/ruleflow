"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('VS Code bundle CI buttons', () => {
    test('bundle includes ci buttons ids', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        const outJs = path.resolve(ext.extensionPath, 'out', 'extension.js');
        const js = fs.readFileSync(outJs, 'utf-8');
        ['btnCiSave', 'btnCiGen', 'btnCiPreview', 'btnCiOpen', 'btnCiValidate', 'btnInsertRules']
            .forEach(id => assert.ok(js.includes(id), 'Missing id in bundle: ' + id));
    });
});
//# sourceMappingURL=bundle_ci_buttons.test.js.map