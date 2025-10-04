"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = run;
const path = require("path");
const Mocha = require("mocha");
const fs = require("fs");
function run() {
    // 使用 TDD 界面以支持 `suite`/`test` 语法
    const timeoutEnv = process.env.MCP_VSCODE_TEST_TIMEOUT_MS;
    const timeoutMs = (() => {
        if (timeoutEnv && /^\d+$/.test(timeoutEnv))
            return parseInt(timeoutEnv, 10);
        return 120000; // extend default to reduce flakiness in headless/container
    })();
    const mocha = new Mocha({ ui: 'tdd', color: true, timeout: timeoutMs });
    const testsRoot = path.resolve(__dirname);
    return new Promise((resolve, reject) => {
        fs.readdir(testsRoot, (err, files) => {
            if (err) {
                return reject(err);
            }
            files.filter(f => f.endsWith('.test.js')).forEach(f => mocha.addFile(path.resolve(testsRoot, f)));
            try {
                mocha.run((failures) => {
                    if (failures > 0) {
                        reject(new Error(`${failures} tests failed.`));
                    }
                    else {
                        resolve();
                    }
                });
            }
            catch (err) {
                reject(err);
            }
        });
    });
}
//# sourceMappingURL=index.js.map