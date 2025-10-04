"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const assert = require("assert");
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
suite('Bundle contains multi-files guarded write UI', () => {
    test('multi files (dry-run) string exists', async () => {
        const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant');
        assert.ok(ext, 'Extension not found');
        const outJs = path.resolve(ext.extensionPath, 'out', 'extension.js');
        const js = fs.readFileSync(outJs, 'utf-8');
        assert.ok(js.toLowerCase().includes('multi files (dry-run)'), 'Expected multi files (dry-run) UI string');
    });
});
//# sourceMappingURL=bundle_fs_multi_diff.test.js.map