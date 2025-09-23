import * as vscode from 'vscode';
import { LanguageModelChatMessage, LanguageModelChatMessageRole } from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { spawn, ChildProcessWithoutNullStreams, execFile } from 'child_process';

// Workspace root lock (user-selected project root for strict isolation)
let __lockedRoot: string | null = null;

// Helper to generate CSP nonce for webview inline scripts
function getNonce(): string {
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let text = '';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

// ---- Workspace helpers (multi-root aware, Occam's razor) ----
function getWorkspaceRoot(): string | undefined {
  try {
    if (__lockedRoot) return __lockedRoot;
    const ed = vscode.window.activeTextEditor;
    if (ed) {
      const folder = vscode.workspace.getWorkspaceFolder(ed.document.uri);
      if (folder) return folder.uri.fsPath;
    }
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  } catch {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }
}

function getWorkspaceLabel(): string {
  try {
    if (__lockedRoot) {
      try { return path.basename(__lockedRoot); } catch {}
    }
    const ed = vscode.window.activeTextEditor;
    if (ed) {
      const folder = vscode.workspace.getWorkspaceFolder(ed.document.uri);
      if (folder) return folder.name;
    }
    const ws0 = vscode.workspace.workspaceFolders?.[0];
    return ws0?.name || '\u5f53\u524d\u5de5\u4f5c\u533a';
  } catch {
    return '\u5f53\u524d\u5de5\u4f5c\u533a';
  }
}

// Prefer project venv python for all direct CLI calls
function resolveProjectPython(): string {
  try {
    const ws = getWorkspaceRoot() || process.cwd();
    const venvPy = process.platform === 'win32'
      ? path.join(ws, '.mcp', 'venv', 'Scripts', 'python.exe')
      : path.join(ws, '.mcp', 'venv', 'bin', 'python');
    if (fs.existsSync(venvPy)) return venvPy;
    const envBin = (process.env.MCP_PYTHON_BIN || '').trim();
    if (envBin) return envBin;
  } catch { /* ignore */ }
  return process.platform === 'win32' ? 'python' : 'python3';
}

class McpClient {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private seq = 0;
  private pending = new Map<number, (res: any) => void>();
  private fakeMode = ((process.env.RULEFLOW_TEST_FAKE || '').trim() === '1');
  private fakeCalls: { method: string; name?: string; params?: any; args?: any }[] = [];
  private hb: NodeJS.Timeout | null = null;
  private connected = false;
  private lastStartAt = 0;
  private restarting = false;
  private failureCount = 0;
  private lastFailureAt = 0;
  private autoPrepared = false;
  private outBuf = '';

  private updateFakeMode() {
    try {
      if ((process.env.RULEFLOW_TEST_FAKE || '').trim() === '1') { this.fakeMode = true; return; }
      const ws = getWorkspaceRoot() || process.cwd();
      const p = path.join(ws, '.mcp', 'dashboard', 'fake_mode');
      if (fs.existsSync(p)) this.fakeMode = true;
    } catch { /* ignore */ }
  }

  start(context: vscode.ExtensionContext) {
    this.updateFakeMode();
    if (this.proc || this.fakeMode) return;
    // \u5c3d\u91cf\u4e0d\u5f71\u54cd\u6027\u80fd\uff1a\u6309\u9700\u542f\u52a8\uff0c\u9762\u677f\u6253\u5f00\u6216\u9996\u6b21\u8bf7\u6c42\u65f6\u624d\u542f\u52a8
    const ws = getWorkspaceRoot() || process.cwd();
    // 1) \u4f18\u5148\u4f7f\u7528\u5de5\u4f5c\u533a\u5185 .mcp/venv \u7684 Python\uff08\u771f\u6b63\u5f00\u7bb1\u5373\u7528\uff09
    const venvPy = process.platform === 'win32'
      ? path.join(ws, '.mcp', 'venv', 'Scripts', 'python.exe')
      : path.join(ws, '.mcp', 'venv', 'bin', 'python');
    let pyBin = venvPy;
    if (!fs.existsSync(venvPy)) {
      // 2) \u5176\u6b21\u4f7f\u7528\u73af\u5883\u53d8\u91cf MCP_PYTHON_BIN
      if (process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim()) {
        pyBin = process.env.MCP_PYTHON_BIN.trim();
      } else {
        // 2.5) \u5168\u90e8\u56de\u9000\uff1a\u7528\u6237\u4e3b\u76ee\u5f55 ~/.mcp/venv\uff08\u7ed9\u6240\u6709\u9879\u76ee\u590d\u7528\uff09
        let decided = false;
        try {
          const home = os.homedir();
          const globalPy = process.platform === 'win32'
            ? path.join(home, '.mcp', 'venv', 'Scripts', 'python.exe')
            : path.join(home, '.mcp', 'venv', 'bin', 'python');
          if (fs.existsSync(globalPy)) { pyBin = globalPy; decided = true; }
        } catch {}
        if (!decided) {
          try {
            const repoRoot = path.resolve(context.extensionUri.fsPath, '..', '..');
            const repoPy = process.platform === 'win32'
              ? path.join(repoRoot, '.mcp', 'venv', 'Scripts', 'python.exe')
              : path.join(repoRoot, '.mcp', 'venv', 'bin', 'python');
            if (fs.existsSync(repoPy)) { pyBin = repoPy; decided = true; }
          } catch {}
        }
        if (!decided) {
          pyBin = (process.platform === 'win32' ? 'python' : 'python3');
        }
      }
    }
    this.lastStartAt = Date.now();
    // 为后端进程注入 venv 的 PATH，避免其子进程解析到系统 python/工具
    const venvBinForPath = process.platform === 'win32'
      ? path.join(ws, '.mcp', 'venv', 'Scripts')
      : path.join(ws, '.mcp', 'venv', 'bin');
    const envForServer = { ...process.env } as NodeJS.ProcessEnv;
    try {
      const oldPath = String(process.env.PATH || '');
      envForServer.PATH = (fs.existsSync(venvBinForPath) ? (venvBinForPath + path.delimiter) : '') + oldPath;
      envForServer.PYTHONUNBUFFERED = '1';
      envForServer.PYTHONIOENCODING = 'utf-8';
    } catch { /* ignore */ }
    envForServer.MCP_PROJECT_ROOT = ws;
    envForServer.MCP_STRICT_ISOLATION = '1';
    this.proc = spawn(pyBin, ['-m', 'mcp_rules_assistant.cli', 'start'], {
      cwd: ws,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: envForServer,
    });
    // log to .mcp/dashboard/server.log for troubleshooting
    try {
      const logDir = path.join(ws, '.mcp', 'dashboard');
      fs.mkdirSync(logDir, { recursive: true });
      const logFile = path.join(logDir, 'server.log');
      const append = (line: string) => { try { fs.appendFileSync(logFile, line + '\n'); } catch {} };
      append(`[spawn] ${new Date().toISOString()} ${pyBin} -m mcp_rules_assistant.cli start`);
      this.proc.stderr.setEncoding('utf8');
      this.proc.stderr.on('data', async (chunk: string) => {
        chunk.split(/\r?\n/).forEach((ln: string) => { if (ln.trim()) append('[stderr] ' + ln); });
        // 自愈：缺少 mcp_rules_assistant 时自动创建 venv 并安装本地包
        try {
          if (!this.autoPrepared && /No module named .*mcp_rules_assistant/.test(String(chunk || ''))) {
            this.autoPrepared = true;
            const venvDir = path.join(ws, '.mcp', 'venv');
            const vpy = process.platform === 'win32' ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python');
            const run = (cmd: string, args: string[]) => new Promise<void>((resolve) => {
              try { const p = spawn(cmd, args, { cwd: ws }); p.on('close', () => resolve()); p.on('error', () => resolve()); } catch { resolve(); }
            });
            if (!fs.existsSync(venvDir)) {
              await run(pyBin, ['-m', 'venv', venvDir]);
            }
            if (fs.existsSync(vpy)) {
              await run(vpy, ['-m', 'pip', 'install', '-U', 'pip', 'setuptools', 'wheel']);
              // 优先从当前工作区安装（适配在容器/工作区内开发的场景）；若非源码仓库则回退到 PyPI 包
              const wsPyProject = path.join(ws, 'pyproject.toml');
              const wsSetupPy = path.join(ws, 'setup.py');
              if (fs.existsSync(wsPyProject) || fs.existsSync(wsSetupPy)) {
                append('[autoprep] installing server from workspace (editable)');
                await run(vpy, ['-m', 'pip', 'install', '-e', ws]);
              } else {
                append('[autoprep] installing server from PyPI package');
                await run(vpy, ['-m', 'pip', 'install', 'mcp-rules-assistant']);
              }
              vscode.window.showInformationMessage('MCP 服务器已自动安装到 .mcp/venv，正在尝试重新连接…');
              try { this.proc?.kill(); } catch {}
            }
          }
        } catch { /* ignore */ }
      });
    } catch { /* ignore logging errors */ }
    this.proc.on('error', (err) => {
      vscode.window.showErrorMessage(`MCP Server \u542f\u52a8\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Python\uff1a${String(err)}\u3002\u53ef\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf MCP_PYTHON_BIN \u6307\u5b9a\u89e3\u91ca\u5668\u3002`);
    });
    this.proc.on('close', (code) => {
      const early = (Date.now() - this.lastStartAt) < 1500; // early exit likely due to reload/pipe close
      const willRetry = !this.restarting;
      // \u5ef6\u8fdf\u63d0\u793a\uff1a\u7ed9\u81ea\u52a8\u91cd\u542f\u4e00\u4e2a\u7a97\u53e3\uff0c\u82e5\u5df2\u6062\u590d\u5219\u4e0d\u6253\u6270
      const maybeWarn = () => {
        if (code !== 0 && !this.connected) {
          vscode.window.showWarningMessage(`MCP Server \u9000\u51fa\uff08\u4ee3\u7801 ${code}\uff09\u3002\u90e8\u5206\u529f\u80fd\u53ef\u80fd\u4e0d\u53ef\u7528\u3002\u6b63\u5728\u5c1d\u8bd5\u81ea\u52a8\u6062\u590d\u2026`);
        }
      };
      this.connected = false;
      try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', false); } catch {}
      // try to restart on unexpected close (debounced by caller)
      this.proc = null;
      // \u5931\u8d25\u8ba1\u6570\u4e0e\u81ea\u52a8\u964d\u7ea7\u4e3a\u6f14\u793a\u6a21\u5f0f\uff08fake\uff09\uff0c\u907f\u514d\u7a7a\u767d\u9762\u677f
      const now = Date.now();
      this.failureCount = (now - this.lastFailureAt <= 5000) ? (this.failureCount + 1) : 1;
      this.lastFailureAt = now;
      if (this.failureCount >= 2) {
        try {
          const path = require('path'); const fs = require('fs');
          const dash = path.join(ws, '.mcp', 'dashboard');
          fs.mkdirSync(dash, { recursive: true });
          fs.writeFileSync(path.join(dash, 'fake_mode'), '1');
          this.fakeMode = true;
          vscode.window.showInformationMessage('MCP \u65e0\u6cd5\u542f\u52a8\uff0c\u5df2\u81ea\u52a8\u5207\u6362\u4e3a\u6f14\u793a\u6a21\u5f0f\uff08fake\uff09\u3002\u53ef\u7a0d\u540e\u51c6\u5907\u73af\u5883\u540e\u518d\u8bd5\u3002');
        } catch { /* ignore */ }
      }
      if (willRetry) {
        this.restarting = true;
        setTimeout(() => {
          try { this.start(context); } finally { this.restarting = false; }
        }, early ? 400 : 800);
        setTimeout(maybeWarn, 1600);
      } else {
        setTimeout(maybeWarn, 800);
      }
    });
    this.proc.stdout.setEncoding('utf8');
    this.proc.stdout.on('data', (chunk: string) => {
      try {
        this.outBuf += String(chunk || '');
        let idx = this.outBuf.indexOf('\n');
        while (idx >= 0) {
          // Extract one full line (strip trailing CR if present)
          let line = this.outBuf.slice(0, idx);
          this.outBuf = this.outBuf.slice(idx + 1);
          if (line.endsWith('\r')) line = line.slice(0, -1);
          if (line.trim()) {
            try {
              const msg = JSON.parse(line);
              if (msg.id !== undefined && this.pending.has(msg.id)) {
                const cb = this.pending.get(msg.id)!;
                this.pending.delete(msg.id);
                cb(msg.result ?? msg.error);
              }
            } catch {
              // ignore malformed line; do not drop buffer already advanced for this line
            }
          }
          idx = this.outBuf.indexOf('\n');
        }
        // guard against unbounded buffer growth (if no newline ever arrives)
        if (this.outBuf.length > 1_000_000) {
          this.outBuf = this.outBuf.slice(-10000);
        }
      } catch {
        // ignore
      }
    });
    // heartbeat ping
    if (this.hb) { clearInterval(this.hb); this.hb = null; }
    this.hb = setInterval(async () => {
      try {
        const res = await this.request('ping', {});
        const ok = !!(res && (res.ok !== false));
        if (ok !== this.connected) {
          this.connected = ok;
          try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', ok); } catch {}
        }
      } catch {
        this.connected = false;
        try { vscode.commands.executeCommand('setContext', 'ruleflow.mcpConnected', false); } catch {}
        // attempt a light restart
        if (!this.proc) {
          try { this.start(context); } catch {}
        }
      }
    }, 5000);
  }

  request(method: string, params?: any): Promise<any> {
    this.updateFakeMode();
    if (this.fakeMode) {
      return this._fakeRequest(method, params || {});
    }
    if (!this.proc) throw new Error('MCP server not started');
    const id = ++this.seq;
    const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
    return new Promise(resolve => {
      this.pending.set(id, resolve);
      this.proc!.stdin.write(payload, 'utf8');
    });
  }

  private async _fakeRequest(method: string, params: any): Promise<any> {
    try {
      // \u8bb0\u5f55\u8c03\u7528\u4f9b\u6d4b\u8bd5\u65ad\u8a00
      try { this.fakeCalls.push({ method, name: (params && params.name) || undefined, params, args: (params && (params.arguments ?? params)) }); } catch {}
      const ws = getWorkspaceRoot() || process.cwd();
      const fsApi = vscode.workspace.fs;
      const fileToString = async (u: vscode.Uri) => {
        try { const b = await fsApi.readFile(u); return Buffer.from(b).toString('utf-8'); } catch { return ''; }
      };
      if (method === 'resources/list') {
        const items: any[] = [];
        // sentinels to toggle off some resources
        let noTree = false, noRules = false;
        try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/notree')); noTree = true; } catch {}
        try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/norules')); noRules = true; } catch {}
        if (!noRules) {
          items.push({ uri: `rules://project/x/compiled`, name: 'Compiled project rules' });
          items.push({ uri: `rules://project/x/compiled.json`, name: 'Compiled rules (JSON)' });
          items.push({ uri: `rules://project/x/suggestions`, name: 'Rule suggestions' });
        }
        items.push({ uri: `coverage://project/x/summary`, name: 'Coverage summary' });
        items.push({ uri: `coverage://project/x/groups`, name: 'Coverage groups' });
        if (!noTree) items.push({ uri: `coverage://project/x/tree`, name: 'Coverage tree' });
        items.push({ uri: `coverage://project/x/near`, name: 'Coverage near' });
        items.push({ uri: `memory://x/rollup`, name: 'Last 20 turns & summary' });
        items.push({ uri: `progress://x/plan`, name: 'Project plan' });
        try { await fsApi.stat(vscode.Uri.file(ws + '/.github/workflows/ci.yml')); items.push({ uri: `ci://project/x/workflow`, name: 'CI workflow (YAML)' }); } catch {}
        return { resources: items };
      }
      if (method === 'resources/read') {
        const uri = String((params || {}).uri || '');
        if (uri.endsWith('/compiled')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_compiled.md');
          const text = await fileToString(u) || 'Rules (fake compiled)';
          return { mimeType: 'text/markdown', text };
        }
        if (uri.endsWith('/compiled.json')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_compiled.json');
          const fallback = JSON.stringify({ conflicts: [{ key: 'coverage.min_module', from: 0.9, to: 0.95 }], suggestions: [{ key: 'security.secrets_scan', action: 'enable' }, { key: 'ci.vscode_required', action: 'enable' }] });
          const text = await fileToString(u) || fallback;
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/suggestions')) {
          const u = vscode.Uri.file(ws + '/.mcp/rules_suggestions.md');
          const text = await fileToString(u) || 'No suggestions (fake)';
          return { mimeType: 'text/markdown', text };
        }
        if (uri.endsWith('/summary')) {
          let bad = false; try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/coverage_bad')); bad = true; } catch {}
          if (bad) {
            const text = JSON.stringify({ ok: false, message: 'coverage not available' });
            return { mimeType: 'application/json', text };
          }
          const weakCsv = await fileToString(vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv'));
          const weak = (weakCsv && weakCsv.includes('\n')) ? weakCsv.split('\n').slice(1).filter(Boolean).map((line) => ({ file: (line.split(',')[0] || 'file.py') })) : [];
          const text = JSON.stringify({ ok: true, weak });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/groups')) {
          const text = JSON.stringify({ ok: true, groups: [{ prefix: 'mod', coverage: 0.97, threshold: 0.95, weak_count: 0, files_count: 1 }] });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/tree')) {
          const text = JSON.stringify({ ok: true, tree: { name: '/', children: { mod: { name: 'mod', children: {} } } } });
          return { mimeType: 'application/json', text };
        }
        if (uri.endsWith('/near')) {
          const text = JSON.stringify({ ok: true, near: [] });
          return { mimeType: 'application/json', text };
        }
        if (uri.startsWith('ci://')) {
          const y = await fileToString(vscode.Uri.file(ws + '/.github/workflows/ci.yml')) || 'name: CI\n';
          return { mimeType: 'text/yaml', text: y };
        }
        if (uri.startsWith('memory://')) {
          const text = JSON.stringify({ turns: [], summary: 'fake summary', links: [] });
          return { mimeType: 'application/json', text };
        }
        if (uri.startsWith('progress://')) {
          const text = '# Plan\n- \u72b6\u6001: in_progress\n- \u5f53\u524d\u6b65\u9aa4: test';
          return { mimeType: 'text/markdown', text };
        }
        return { mimeType: 'text/plain', text: '' };
      }
      if (method === 'tools/call') {
        const name = String((params || {}).name || '');
        if (name === 'coverage.near') {
          let empty = false; try { await fsApi.stat(vscode.Uri.file(ws + '/.mcp/dashboard/near_empty')); empty = true; } catch {}
          if (empty) return { near: [] };
          return { near: [{ file: 'mod.py', coverage: 0.961, threshold: 0.95 }] };
        }
        if (name === 'ci.generate') {
          const u = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await fsApi.createDirectory(vscode.Uri.file(ws + '/.github/workflows')); } catch {}
          await fsApi.writeFile(u, Buffer.from('name: CI\n', 'utf-8'));
          return { ok: true, path: '.github/workflows/ci.yml' };
        }
        if (name === 'ci.validate') {
          try { await fsApi.stat(vscode.Uri.file(ws + '/.github/workflows/ci.yml')); return { ok: true, checks: { workflow: true } }; } catch { return { ok: false, checks: { workflow: false } }; }
        }
        if (name === 'rules.onboard') {
          return { scenario: 'personal', complexity: 'small', devMode: 'tdd', thresholds: { min_module: 0.9, min_core: 0.95 } };
        }
        if (name === 'plan.set') {
          const status = (params && params.status) || 'in_progress';
          const current = (params && params.current) || 'step';
          const u = vscode.Uri.file(ws + '/.mcp/plan.md');
          const md = Buffer.from(`# Plan\n- \u72b6\u6001: ${status}\n- \u5f53\u524d\u6b65\u9aa4: ${current}\n`, 'utf-8');
          try { await fsApi.createDirectory(vscode.Uri.file(ws + '/.mcp')); } catch {}
          await fsApi.writeFile(u, md);
          return { ok: true };
        }
        if (name === 'config.get') {
          return { ok: true, config: {} };
        }
        if (name === 'config.update' || name === 'rules.enforce' || name === 'git.install_hooks' || name === 'rules.ingest' || name === 'env.prepare' || name === 'compliance.commitment' || name === 'ide.scaffold' || name === 'license.verify') {
          return { ok: true, path: name === 'compliance.commitment' ? '.mcp/compliance.md' : undefined };
        }
        if (name === 'nl.command') {
          return { parsed: { tool: '' } };
        }
      }
      return {};
    } catch {
      return {};
    }
  }

  // test helpers (exposed via commands)
  public _testGetFakeCalls(): { method: string; name?: string; params?: any; args?: any }[] {
    return Array.from(this.fakeCalls);
  }
  public _testClearFakeCalls(): void {
    this.fakeCalls = [];
  }
}

const client = new McpClient();
function memAllowed(): boolean {
  try { if ((client as any).fakeMode) return true; } catch {}
  const v = String(process.env.RULEFLOW_ALLOW_MEMORY_APPEND || '').trim().toLowerCase();
  return ['1','true','on','yes','y'].includes(v);
}
// ---- test hooks (non-public commands register below) ----
let __testWebviewHandler: ((msg: any) => Promise<void> | void) | null = null;
let __testPanelHandler: ((msg: any) => Promise<void> | void) | null = null;
let __panelReadyResolve: (() => void) | null = null;
let __panelReady: Promise<void> | null = null;
let __panelInFlightResolve: (() => void) | null = null;
let __panelInFlight: Promise<void> | null = null;
const __ready2Resolvers = new Map<string, () => void>();
const __ready2Promises = new Map<string, Promise<void>>();

async function handleOpenMessage(msg: any) {
  if (msg && msg.t === 'open' && msg.path) {
    try {
      const wsRoot = getWorkspaceRoot() || '';
      let filePath = String(msg.path);
      if (!filePath.match(/^\w:\\|^\//)) {
        filePath = path.join(wsRoot, filePath);
      }
      if (wsRoot && !String(filePath).startsWith(wsRoot)) {
        vscode.window.showErrorMessage('\u65e0\u6cd5\u6253\u5f00\u6587\u4ef6\uff1a\u4e0d\u5728\u5f53\u524d\u5de5\u4f5c\u533a\u5185');
        return;
      }
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
      const editor = await vscode.window.showTextDocument(doc, { preview: false });
      const line = Math.max(0, (msg.line || 1) - 1);
      const pos = new vscode.Position(line, 0);
      editor.selection = new vscode.Selection(pos, pos);
      editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
    } catch (e:any) {
      vscode.window.showErrorMessage('\u65e0\u6cd5\u6253\u5f00\u6587\u4ef6\uff1a' + String(e));
    }
  }
}

let __activated = false; // \u9632\u91cd\u590d\u6fc0\u6d3b\uff08\u6d4b\u8bd5/\u591a\u6b21\u521d\u59cb\u5316\u573a\u666f\uff09

export function activate(context: vscode.ExtensionContext) {
  console.log('[MCP Rules Assistant] Extension activation started');
  if (__activated) {
    // \u907f\u514d\u91cd\u590d\u6ce8\u518c\u547d\u4ee4\u5bfc\u81f4 "command ... already exists"
    console.log('[MCP Rules Assistant] Already activated, skipping');
    return;
  }
  __activated = true;
  
  // Create output channel for the extension
  const outputChannel = vscode.window.createOutputChannel('MCP Rules Assistant');
  outputChannel.appendLine('MCP Rules Assistant extension activated');
  context.subscriptions.push(outputChannel);
  // Only attempt remote auto-install from UI side; skip when already in remote (workspace host)
  try { if (!vscode.env.remoteName) { autoInstallToRemote(context); } } catch {}
  
  console.log('[MCP Rules Assistant] Extension activated successfully');
  // \u6062\u590d\u9501\u5b9a\u6839\u76ee\u5f55\uff08\u82e5\u5b58\u5728\uff09\uff0c\u4f18\u5148\u4f7f\u7528\u6b64\u524d\u7528\u6237\u9009\u62e9\u7684\u9879\u76ee\u6839
  try {
    const saved = context.workspaceState.get<string>('ruleflow.lockRoot') || '';
    if (saved && saved.trim()) { __lockedRoot = saved.trim(); }
    else {
      const w0 = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (w0) {
        const prefs = path.join(w0, '.mcp', 'dashboard', 'ui_prefs.json');
        try { const txt = fs.readFileSync(prefs, 'utf8'); const obj = JSON.parse(txt||'{}'); if (obj && typeof obj.projectRoot==='string' && obj.projectRoot) __lockedRoot = obj.projectRoot; } catch {}
      }
    }
  } catch {}

  // \u5728\u72b6\u6001\u680f\u653e\u4e00\u4e2a\u5feb\u6377\u5165\u53e3\uff0c\u70b9\u51fb\u5373\u53ef\u6253\u5f00\u9762\u677f
  const sb = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  sb.text = 'RuleFlow';
  sb.tooltip = 'Quick Actions';
  sb.command = 'mcpRulesAssistant.quickActions';
  sb.show();
  context.subscriptions.push(sb);

  // Ensure MCP backend starts early so the status bar and commands are responsive
  try { client.start(context); } catch {}

  // \u8f7b\u91cf\u72b6\u6001\u680f\u5237\u65b0\uff1a\u4ece coverage.report \u83b7\u53d6\u6458\u8981\u5e76\u66f4\u65b0\u72b6\u6001\u663e\u793a
  const updateStatusBar = async () => {
    try {
      client.start(context);
      const rep = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
      if (rep && rep.ok) {
        const w = Array.isArray(rep.weak) ? rep.weak.length : 0;
        const n = Array.isArray(rep.near) ? rep.near.length : 0;
        sb.text = `RuleFlow $(check) w${w}/n${n}`;
        const g = Array.isArray(rep.groups) ? rep.groups.length : 0;
        const mm = typeof rep.min_module === 'number' ? `${(rep.min_module*100).toFixed(0)}%` : '-';
        sb.tooltip = `Coverage: weak=${w}, near=${n}, groups=${g}, min_module=${mm}`;
      } else {
        sb.text = 'RuleFlow $(alert)';
        sb.tooltip = 'Coverage not available. Run tests to produce coverage.xml';
      }
    } catch {
      sb.text = 'RuleFlow';
      sb.tooltip = 'Open RuleFlow Panel';
    }
  };
  // \u4fdd\u5b88\u6a21\u5f0f\uff1a\u4e0d\u81ea\u52a8\u89e6\u53d1\u4efb\u4f55\u540e\u7aef\u8c03\u7528\uff1b\u72b6\u6001\u680f\u4ec5\u663e\u793a\u5165\u53e3

  // \u5feb\u6377\u547d\u4ee4\uff1a\u5feb\u901f\u6253\u5f00\u8ba1\u5212\u4e0e\u8bb0\u5fc6\u6587\u4ef6
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openPlan', async () => {
    const ws = getWorkspaceRoot();
    if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
    const uri = vscode.Uri.file(ws + '/.mcp/plan.md');
    try {
      await vscode.workspace.fs.stat(uri);
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch {
      vscode.window.showInformationMessage('.mcp/plan.md not found');
    }
  }));

  // Conversational, panel-free commands (beginner-first)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.oneClickSetup', async () => { await oneClickSetup(context); }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.newbieGuide', async () => { await newbieGuide(context); }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.ask', async () => { await askCommand(context); }));
  // \u4e3b\u52a8\u52a0\u8f7d\u8986\u76d6\u7387\uff1a\u8c03\u7528 MCP \u5de5\u5177 coverage.report\uff0c\u5e76\u7ed9\u51fa\u6458\u8981\u63d0\u793a
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.loadCoverage', async () => {
    try { client.start(context); } catch {}
    try {
      const res = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
      const weak = Array.isArray(res?.weak) ? res.weak.length : 0;
      const near = Array.isArray(res?.near) ? res.near.length : 0;
      const groups = Array.isArray(res?.groups) ? res.groups.length : 0;
      const mm = typeof res?.min_module === 'number' ? res.min_module : undefined;
      if (res && res.ok) {
        vscode.window.showInformationMessage(`Coverage loaded: weak=${weak}, near=${near}, groups=${groups}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : ''));
        try { await updateStatusBar(); } catch {}
        try { if (memAllowed()) {
          const content = `Coverage loaded: weak=${weak}, near=${near}, groups=${groups}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : '');
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } } catch {}
      } else {
        const msg = (res && (res.message || res.error)) || 'coverage.xml not found or unavailable';
        vscode.window.showWarningMessage(`Coverage not available: ${String(msg)}`);
        try { if (memAllowed()) {
          const content = `Coverage not available: ${String(msg)}`;
          await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'loadCoverage' } } });
        } } catch {}
      }
    } catch (e:any) {
      vscode.window.showErrorMessage(`Load Coverage failed: ${String(e)}`);
    }
  }));

  // \u5feb\u901f\u52a8\u4f5c\uff08\u72b6\u6001\u680f\u5165\u53e3\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.quickActions', async () => {
    try { client.start(context); } catch {}
    const choice = await vscode.window.showQuickPick([
      'Open Panel',
      'Backend Doctor',
      'Load Coverage',
      'Open Plan',
      'Open Status',
      'Ingest Rules (Quick)',
      'Status Update',
      'Generate CI',
      'Validate CI',
      'Install Hooks',
      'Natural Command',
    ], { placeHolder: 'RuleFlow Quick Actions' });
    if (!choice) return;
    if (choice === 'Open Panel') { await vscode.commands.executeCommand('mcpRulesAssistant.openPanel'); return; }
    if (choice === 'Backend Doctor') { await vscode.commands.executeCommand('mcpRulesAssistant.backendDoctor'); return; }
    if (choice === 'Load Coverage') { await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage'); return; }
    if (choice === 'Open Plan') { await vscode.commands.executeCommand('mcpRulesAssistant.openPlan'); return; }
    if (choice === 'Open Status') { await vscode.commands.executeCommand('mcpRulesAssistant.openStatus'); return; }
    if (choice === 'Ingest Rules (Quick)') { await vscode.commands.executeCommand('mcpRulesAssistant.ingestQuick'); return; }
    if (choice === 'Status Update') { await vscode.commands.executeCommand('mcpRulesAssistant.statusUpdate'); return; }
    if (choice === 'Generate CI') { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI \u5df2\u751f\u6210'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI generated', meta: { source: 'vscode', action: 'ci.generate' } } }); } } catch {} return; }
    if (choice === 'Validate CI') { await client.request('tools/call', { name: 'ci.validate', arguments: {} }); vscode.window.showInformationMessage('CI \u6821\u9a8c\u5b8c\u6210'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI validated', meta: { source: 'vscode', action: 'ci.validate' } } }); } } catch {} return; }
    if (choice === 'Install Hooks') { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('Git hooks \u5df2\u5b89\u88c5'); try { if (memAllowed()) { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Git hooks installed', meta: { source: 'vscode', action: 'git.install_hooks' } } }); } } catch {} return; }
    if (choice === 'Natural Command') { await vscode.commands.executeCommand('mcpRulesAssistant.nlCommand'); return; }
  }));

  // \u72b6\u6001\u5237\u65b0\uff08\u663e\u793a\u6458\u8981 + \u5237\u65b0\u72b6\u6001\u680f\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.statusUpdate', async () => {
    try {
      client.start(context);
      const pyBin = resolveProjectPython();
      const cwd = getWorkspaceRoot() || process.cwd();
      const { execFile } = require('child_process');
      const venvBin = process.platform === 'win32' ? path.join(cwd, '.mcp', 'venv', 'Scripts') : path.join(cwd, '.mcp', 'venv', 'bin');
      const env = { ...process.env } as NodeJS.ProcessEnv;
      try {
        const oldPath = String(process.env.PATH || '');
        env.PATH = (fs.existsSync(venvBin) ? (venvBin + path.delimiter) : '') + oldPath;
        env.PYTHONUNBUFFERED = '1';
        env.PYTHONIOENCODING = 'utf-8';
      } catch {}
      execFile(pyBin, ['-m', 'mcp_rules_assistant.cli', 'status-update', '--json'], { cwd, env }, async (err: any, stdout: string, stderr: string) => {
        if (err) { vscode.window.showErrorMessage('\u72b6\u6001\u5237\u65b0\u5931\u8d25\uff1a' + String(err)); return; }
        try {
          const data = JSON.parse(stdout || '{}');
          const cov = data.coverage || {}; const w = (cov.weak||[]).length || 0; const n = (cov.near||[]).length || 0; const mm = cov.min_module;
          vscode.window.showInformationMessage(`Status: weak=${w}, near=${n}` + (mm !== undefined ? `, min_module=${(mm*100).toFixed(0)}%` : ''));
          try { await updateStatusBar(); } catch {}
        } catch { vscode.window.showInformationMessage('\u72b6\u6001\u5df2\u5237\u65b0'); }
      });
    } catch (e:any) { vscode.window.showErrorMessage('\u72b6\u6001\u5237\u65b0\u5931\u8d25\uff1a' + String(e)); }
  }));

  // \u5feb\u901f\u6444\u53d6\uff08\u9ed8\u8ba4 README.md, docs/\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.ingestQuick', async () => {
    try { client.start(context); } catch {}
    try { await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: ['README.md', 'docs/'] } }); vscode.window.showInformationMessage('\u89c4\u5219\u6444\u53d6\u5b8c\u6210'); } catch (e:any) { vscode.window.showErrorMessage('\u89c4\u5219\u6444\u53d6\u5931\u8d25\uff1a' + String(e)); }
  }));

  // \u6253\u5f00\u72b6\u6001\u6587\u4ef6
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openStatus', async () => {
    try {
      const ws = getWorkspaceRoot(); if (!ws) { vscode.window.showWarningMessage('No workspace'); return; }
      const uri = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch { vscode.window.showInformationMessage('status.json not found'); }
  }));

  // \u8ba1\u5212\u8bbe\u7f6e\uff08status/current/next \u4e09\u9879\u4efb\u610f\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.planSet', async () => {
    try { client.start(context); } catch {}
    const status = await vscode.window.showQuickPick(['in_progress', 'done', 'planned', 'skip (no change)'], { placeHolder: 'status' });
    let stVal: string|undefined = undefined; if (status && !status.startsWith('skip')) stVal = status;
    const current = await vscode.window.showInputBox({ placeHolder: 'current (\u53ef\u7559\u7a7a\u4e0d\u53d8)' });
    const next = await vscode.window.showInputBox({ placeHolder: 'next (\u53ef\u7559\u7a7a\u4e0d\u53d8)' });
    const args: any = {}; if (stVal) args.status = stVal; if (current) args.current = current; if (next) args.next = next;
    await client.request('tools/call', { name: 'plan.set', arguments: args });
    vscode.window.showInformationMessage('Plan updated');
    try {
      const content = `Plan set: ${['status', 'current', 'next'].map(k=> (args[k]!==undefined? `${k}=${args[k]}` : '')).filter(Boolean).join(', ')}`;
      await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'plan.set' } } });
    } catch {}
  }));

  // \u8bb0\u5fc6\uff1a\u8ffd\u52a0\u9009\u4e2d\u5185\u5bb9
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.memoryAppendSelection', async () => {
    try { client.start(context); } catch {}
    const ed = vscode.window.activeTextEditor;
    let text = '';
    if (ed) { text = ed.document.getText(ed.selection); }
    if (!text) { text = await vscode.window.showInputBox({ placeHolder: '\u8f93\u5165\u8981\u8ffd\u52a0\u5230\u8bb0\u5fc6\u7684\u6587\u672c' }) || ''; }
    if (!text) { vscode.window.showWarningMessage('\u65e0\u5185\u5bb9\u53ef\u8ffd\u52a0'); return; }
    await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'user', content: text } });
    vscode.window.showInformationMessage('\u5df2\u8ffd\u52a0\u5230\u8bb0\u5fc6');
  }));

  // \u53d7\u63a7\u5199\u5165\uff1a\u5f53\u524d\u6587\u4ef6\u6216\u8f93\u5165\u8def\u5f84 + \u5185\u5bb9\uff1b\u652f\u6301 dry-run/strict \u9009\u9879
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.fsApplyPatch', async () => {
    try { client.start(context); } catch {}
    const ed = vscode.window.activeTextEditor;
    const ws = getWorkspaceRoot() || process.cwd();
    const modeTop = await vscode.window.showQuickPick(['single file', 'multi files (dry-run)'], { placeHolder: '\u6a21\u5f0f\u9009\u62e9 / Mode' });
    if (!modeTop) return;
    if (modeTop.startsWith('single')) {
      let defaultPath = '';
      if (ed) {
        const p = ed.document.uri.fsPath;
        if (p && p.startsWith(ws)) defaultPath = p.substring(ws.length+1).replace(/\\\\/g,'/');
      }
      const path = await vscode.window.showInputBox({ placeHolder: '\u76f8\u5bf9\u8def\u5f84\uff08\u4f8b\u5982 src/app.py\uff09', value: defaultPath });
      if (!path) { vscode.window.showWarningMessage('\u8def\u5f84\u4e3a\u7a7a'); return; }
      let content = ed ? ed.document.getText(ed.selection) : '';
      if (!content) { content = await vscode.window.showInputBox({ placeHolder: '\u5199\u5165\u5185\u5bb9\uff08\u7559\u7a7a\u5219\u53d6\u6d88\uff09' }) || ''; }
      if (!content) { vscode.window.showWarningMessage('\u5185\u5bb9\u4e3a\u7a7a'); return; }
      const mode = await vscode.window.showQuickPick(['dry-run', 'write (runChecks=strict)', 'write (runChecks=on, strict=off)'], { placeHolder: '\u6a21\u5f0f' });
      if (!mode) return;
      const dryRun = mode === 'dry-run'; const strict = mode.includes('strict'); const runChecks = !mode.includes('strict') ? true : true;
      const files = [{ path, content }];
      const out = await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files, runChecks, strict, dryRun } });
      vscode.window.showInformationMessage('fs.apply_patch: ' + (out && out.ok ? 'OK' : 'Done'));
      try {
        const contentSum = `fs.apply_patch: ${dryRun ? 'dry-run' : 'write'}, files=${files.length}, strict=${strict}`;
        await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: contentSum, meta: { source: 'vscode', action: 'fs.apply_patch', dryRun, strict, files: files.length } } });
      } catch {}
      return;
    }
    // Multi files (dry-run) with simple diff preview
    const nStr = await vscode.window.showInputBox({ placeHolder: '\u8f93\u5165\u6587\u4ef6\u6570\u91cf(1-10)', value: '2' });
    const n = Math.max(1, Math.min(10, parseInt(nStr || '2', 10) || 2));
    const items: { path: string, content: string }[] = [];
    for (let i=1; i<=n; i++) {
      const p = await vscode.window.showInputBox({ placeHolder: `\u7b2c ${i} \u4e2a\u76f8\u5bf9\u8def\u5f84`, value: i===1 && ed && ed.document.uri.fsPath.startsWith(ws) ? ed.document.uri.fsPath.substring(ws.length+1).replace(/\\\\/g,'/') : '' });
      if (!p) break;
      let c = ed ? ed.document.getText(ed.selection) : '';
      if (!c) { c = await vscode.window.showInputBox({ placeHolder: `\u7b2c ${i} \u4e2a\u6587\u4ef6\u5185\u5bb9\uff08\u7559\u7a7a\u53d6\u6d88\u672c\u6b21\u591a\u6587\u4ef6\uff09` }) || ''; }
      if (!c) { vscode.window.showWarningMessage('\u5185\u5bb9\u4e3a\u7a7a\uff0c\u5df2\u53d6\u6d88'); break; }
      items.push({ path: p, content: c });
    }
    if (!items.length) { vscode.window.showWarningMessage('\u672a\u6536\u96c6\u5230\u6587\u4ef6'); return; }
    const out = await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files: items, runChecks: true, strict: true, dryRun: true } });
    try {
      const previewLines: string[] = [];
      previewLines.push('# Guarded Write (dry-run) preview');
      const fsApi = vscode.workspace.fs;
      for (const it of items) {
        previewLines.push('--- ' + it.path);
        try {
          const uri = vscode.Uri.file((ws ? (ws + '/' + it.path) : it.path));
          const buf = await fsApi.readFile(uri);
          const cur = Buffer.from(buf).toString('utf-8');
          previewLines.push('@@ current length=' + cur.length + ' new length=' + it.content.length);
          const headOld = (cur || '').split(/\r?\n/).slice(0,3).join('\n');
          const headNew = (it.content || '').split(/\r?\n/).slice(0,3).join('\n');
          previewLines.push('- ' + headOld.replace(/\n/g, '\n- '));
          previewLines.push('+ ' + headNew.replace(/\n/g, '\n+ '));
        } catch {
          previewLines.push('@@ new file (length=' + it.content.length + ')');
          const headNew = (it.content || '').split(/\r?\n/).slice(0,3).join('\n');
          previewLines.push('+ ' + headNew.replace(/\n/g, '\n+ '));
        }
      }
      const doc = await vscode.workspace.openTextDocument({ language: 'markdown', content: previewLines.join('\n') });
      await vscode.window.showTextDocument(doc, { preview: true });
      vscode.window.showInformationMessage('fs.apply_patch (multi dry-run): ' + (out && out.ok ? 'OK' : 'Done'));
      try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: `fs.apply_patch: dry-run multi, files=${items.length}`, meta: { source: 'vscode', action: 'fs.apply_patch', dryRun: true, files: items.length } } }); } catch {}
    } catch (e:any) {
      vscode.window.showErrorMessage('\u9884\u89c8\u5931\u8d25\uff1a' + String(e));
    }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.openMemory', async () => {
    const ws = getWorkspaceRoot();
    if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
    const uri = vscode.Uri.file(ws + '/.mcp/memory.json');
    try {
      await vscode.workspace.fs.stat(uri);
      // Guard against symlink/out-of-workspace and hardlink targets leaking memory across projects
      try {
        const l = fs.lstatSync(uri.fsPath);
        const mcpDir = path.resolve(ws, '.mcp');
        let real = uri.fsPath;
        if (l.isSymbolicLink()) {
          real = fs.realpathSync(uri.fsPath);
        }
        const inside = real.startsWith(mcpDir + path.sep) || real === mcpDir;
        if (!inside) {
          vscode.window.showErrorMessage('\u51fa\u4e8e\u9694\u79bb\u5b89\u5168\uff0c\u5df2\u62d2\u7edd\u6253\u5f00\u4f4d\u4e8e\u5de5\u4f5c\u533a\u4e4b\u5916\u7684\u8bb0\u5fc6\u6587\u4ef6');
          return;
        }
        // Detect hardlink count > 1 and warn/abort (conservative default)
        const st = fs.statSync(real);
        const isHardLinked = (st.nlink && st.nlink > 1);
        if (isHardLinked && String(process.env.MCP_MEMORY_TRUST_HARDLINK || '').trim().toLowerCase() !== '1') {
          vscode.window.showWarningMessage('\u68c0\u6d4b\u5230 memory.json \u53ef\u80fd\u4e3a\u786c\u94fe\u63a5\uff1b\u4e3a\u9632\u8de8\u9879\u76ee\u5171\u4eab\uff0c\u9ed8\u8ba4\u4e0d\u6253\u5f00\uff08\u8bbe\u7f6e MCP_MEMORY_TRUST_HARDLINK=1 \u53ef\u653e\u5bbd\uff09\u3002');
          return;
        }
      } catch { /* ignore and continue best-effort */ }
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
    } catch {
      vscode.window.showInformationMessage('.mcp/memory.json not found');
    }
  }));

  const disposable = vscode.commands.registerCommand('mcpRulesAssistant.openPanel', async () => {
    // If we are not in a remote window but there is a Dev Container config,
    // reopen in container automatically to finish one-click installation.
    try {
      if (!vscode.env.remoteName) {
        const ws = getWorkspaceRoot();
        if (ws) {
          const dc1 = path.join(ws, '.devcontainer', 'devcontainer.json');
          const dc2 = path.join(ws, '.devcontainer.json');
          if (fs.existsSync(dc1) || fs.existsSync(dc2)) {
            vscode.window.setStatusBarMessage('检测到 Dev Container 配置，正在在容器中重开窗口以完成一键安装…', 3000);
            try { await vscode.commands.executeCommand('devcontainers.reopenInContainer'); return; } catch {}
            try { await vscode.commands.executeCommand('remote-containers.reopenInContainer'); return; } catch {}
          }
        }
      }
    } catch {}
    // 先渲染一个最小占位以避免空白，并提供快速修复入口
    const renderFallback = (msg: string) => `
      <html><body style="font-family:-apple-system,Segoe UI,Arial;">
      <style>
        body.simple .adv{display:none;} body.advanced #simpleBar{display:none;}
        #modeBar{display:flex;gap:6px;align-items:center;margin:6px 0;}
        #modeBar button{padding:4px 8px;}
      </style>
      <h2>RuleFlow \u9762\u677f</h2>
      <div id="modeBar"><span>\u663e\u793a\u6a21\u5f0f\uff1a</span> <button id="btnModeSimple" title="\u4ec5\u5c55\u793a\u5e38\u7528\u64cd\u4f5c\uff1b\u4e0d\u4f1a\u81ea\u52a8\u4fee\u6539\u6587\u4ef6\u6216\u914d\u7f6e">\u65b0\u624b\u6a21\u5f0f</button> <button id="btnModeAdvanced" title="\u5c55\u793a\u5168\u90e8\u529f\u80fd\uff1b\u6bcf\u9879\u64cd\u4f5c\u90fd\u9700\u8981\u4f60\u786e\u8ba4\u540e\u624d\u6267\u884c">\u9ad8\u7ea7\u6a21\u5f0f</button></div>
      <div id="simpleBar" style="border:1px solid #ddd; padding:8px; background:#f9fbff;">
        <div style="color:#666; font-size:12px;">${msg || '\u6b63\u5728\u8fde\u63a5 MCP \u2026'}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
          <button id="btnRetry" title="\u91cd\u65b0\u5c1d\u8bd5\u8fde\u63a5 MCP \u540e\u7aef\uff08\u5b89\u5168\uff0c\u53ea\u8fdb\u884c\u63e1\u624b/\u5065\u5eb7\u68c0\u67e5\uff09">\u91cd\u8bd5\u8fde\u63a5</button>
          <button id="btnEnableFake" title="\u5199\u5165 .mcp/dashboard/fake_mode \u4ee5\u542f\u7528\u79bb\u7ebf\u6f14\u793a\uff1b\u53ef\u968f\u65f6\u5220\u9664\u8be5\u6587\u4ef6\u6062\u590d">\u5207\u6362\u4e3a\u6f14\u793a\u6a21\u5f0f</button>
          <button id="btnOpenLog" title="\u6253\u5f00 .mcp/dashboard/server.log \u65e5\u5fd7\u7528\u4e8e\u6392\u67e5\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 server.log</button>
        </div>
      </div>
      <script>
        const vscode = acquireVsCodeApi();
        (function(){
          const apply=(m)=>{ try{document.body.classList.remove('simple','advanced');document.body.classList.add(m);}catch{} try{vscode.setState&&vscode.setState({uiMode:m});}catch{} };
          const st=(vscode.getState&&vscode.getState())||{}; apply((st&&st.uiMode)||'simple');
          const s=document.getElementById('btnModeSimple'); const a=document.getElementById('btnModeAdvanced');
          if(s) s.onclick=()=>apply('simple'); if(a) a.onclick=()=>apply('advanced');
          const r=document.getElementById('btnRetry'); if(r) r.onclick=()=>vscode.postMessage({t:'retryConnect'});
          const f=document.getElementById('btnEnableFake'); if(f) f.onclick=()=>vscode.postMessage({t:'enableFake'});
          const l=document.getElementById('btnOpenLog'); if(l) l.onclick=()=>vscode.postMessage({t:'openServerLog'});
      })();
      </script>
      </body></html>`;
    const panel = vscode.window.createWebviewPanel(
      'mcpRulesAssistant',
      'RuleFlow: Rules & Memory',
      vscode.ViewColumn.Beside,
      { 
        enableScripts: true, 
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri],
        enableCommandUris: true
      }
    );
    // Only attempt remote auto-install when executing on UI side
    try { if (!vscode.env.remoteName) { autoInstallToRemote(context); } } catch {}
    // Early message queue to avoid losing clicks before full handler is ready
    const __preMsgs: any[] = [];
    if (!(panel as any).__earlyHandlerInstalled) {
      (panel as any).__earlyHandlerInstalled = true;
      panel.webview.onDidReceiveMessage(async (msg) => {
        // If full handler already set up, do nothing here
        if ((panel as any).__fullHandlerReady) return;
        try { __preMsgs.push(msg); } catch {}
      });
    }
    const csp = panel.webview.cspSource;
    const nonce = getNonce();
    const __fallbackHtml = `
      <html>
        <head>
          <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${csp} data:; style-src ${csp} 'unsafe-inline'; script-src ${csp} 'nonce-${nonce}'; font-src ${csp} data:">
        </head>
        <body style="font-family:-apple-system,Segoe UI,Arial;">
          <style>
            body.simple .adv{display:none;} body.advanced #simpleBar{display:none;}
            #modeBar{display:flex;gap:6px;align-items:center;margin:6px 0;}
            #modeBar button{padding:4px 8px;}
          </style>
          <h2>RuleFlow \u9762\u677f</h2>
          <div id="modeBar"><span>\u663e\u793a\u6a21\u5f0f\uff1a</span> <button id="btnModeSimple" title="\u4ec5\u5c55\u793a\u5e38\u7528\u64cd\u4f5c\uff1b\u4e0d\u4f1a\u81ea\u52a8\u4fee\u6539\u6587\u4ef6\u6216\u914d\u7f6e">\u65b0\u624b\u6a21\u5f0f</button> <button id="btnModeAdvanced" title="\u5c55\u793a\u5168\u90e8\u529f\u80fd\uff1b\u6bcf\u9879\u64cd\u4f5c\u90fd\u9700\u8981\u4f60\u786e\u8ba4\u540e\u624d\u6267\u884c">\u9ad8\u7ea7\u6a21\u5f0f</button></div>
          <div id="simpleBar" style="border:1px solid #ddd; padding:8px; background:#f9fbff;">
            <div style="color:#666; font-size:12px;">\u6b63\u5728\u8fde\u63a5 MCP \u2026</div>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
              <button id="btnRetry" title="\u91cd\u65b0\u5c1d\u8bd5\u8fde\u63a5 MCP \u540e\u7aef\uff08\u5b89\u5168\uff0c\u53ea\u8fdb\u884c\u63e1\u624b/\u5065\u5eb7\u68c0\u67e5\uff09">\u91cd\u8bd5\u8fde\u63a5</button>
              <button id="btnEnableFake" title="\u5199\u5165 .mcp/dashboard/fake_mode \u4ee5\u542f\u7528\u79bb\u7ebf\u6f14\u793a\uff1b\u53ef\u968f\u65f6\u5220\u9664\u8be5\u6587\u4ef6\u6062\u590d">\u5207\u6362\u4e3a\u6f14\u793a\u6a21\u5f0f</button>
              <button id="btnOpenLog" title="\u6253\u5f00 .mcp/dashboard/server.log \u65e5\u5fd7\u7528\u4e8e\u6392\u67e5\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 server.log</button>
            </div>
          </div>
          <script nonce="${nonce}">
            const vscode = acquireVsCodeApi();
            (function(){
              const apply=(m)=>{ try{document.body.classList.remove('simple','advanced');document.body.classList.add(m);}catch{} try{vscode.setState&&vscode.setState({uiMode:m});}catch{} };
              const st=(vscode.getState&&vscode.getState())||{}; apply((st&&st.uiMode)||'simple');
              const s=document.getElementById('btnModeSimple'); const a=document.getElementById('btnModeAdvanced');
              if(s) s.onclick=()=>apply('simple'); if(a) a.onclick=()=>apply('advanced');
              const r=document.getElementById('btnRetry'); if(r) r.onclick=()=>vscode.postMessage({t:'retryConnect'});
              const f=document.getElementById('btnEnableFake'); if(f) f.onclick=()=>vscode.postMessage({t:'enableFake'});
              const l=document.getElementById('btnOpenLog'); if(l) l.onclick=()=>vscode.postMessage({t:'openServerLog'});
            })();
          </script>
        </body>
      </html>`;
    panel.webview.html = __fallbackHtml;
    // \u6309\u9700\u542f\u52a8\u540e\u7aef Python \u670d\u52a1\u5668
    try { client.start(context); } catch {}
    // make postMessage safe after dispose
    let __panelDisposed = false;
    const __origPost = panel.webview.postMessage.bind(panel.webview);
    (panel.webview as any).postMessage = (msg: any) => {
      try {
        if (__panelDisposed) return Promise.resolve(false);
        const r = __origPost(msg);
        try { (r as any).then(()=>{}, ()=>{}); } catch {}
        return r;
      } catch { return Promise.resolve(false); }
    };
    panel.onDidDispose(() => { __panelDisposed = true; try { __testPanelHandler = null as any; } catch {} });
    __panelReady = new Promise<void>((res) => { __panelReadyResolve = res; });

    /* c8 ignore start */
    const render = (csp: string, nonceVal: string, md: string, toolsListHtml: string, sugg: string = '') => `
      <html>
      <head>
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${csp} data:; style-src ${csp} 'unsafe-inline'; script-src ${csp} 'nonce-${nonceVal}'; font-src ${csp} data:; connect-src ${csp}; frame-src 'none';">
        <script nonce="${nonceVal}" src="@@PANEL_BOOTSTRAP@@" defer></script>
      </head>
      <body class="simple" style="font-family: -apple-system,Segoe UI,Arial;">
        <style>
          body.simple .adv { display: none; }
          body.simple #simpleBar { display: block; }
          body.advanced #simpleBar { display: none; }
          body.advanced .adv { display: block; }
          /* Additional styles */
          #modeBar { display:flex; gap:6px; align-items:center; margin:6px 0; }
          #modeBar button { padding:4px 8px; }
          #simpleBar button { padding:6px 10px; margin:2px 4px; }
          .hint { color:#666; font-size:12px; }
        </style>
        <h2 id="hdrTitle">MCP \u89c4\u5219\u4e0e\u4e0a\u4e0b\u6587\u52a9\u624b</h2>
        <p id="pConnected">\u5df2\u8fde\u63a5\u5230 Python MCP Server\uff08\u6700\u5c0f\u534f\u8bae\uff09\u3002\u9ed8\u8ba4\u5feb\u901f\u5185\u73af\uff1a\u4fdd\u5b58\u8f7b\u3001\u63a8\u9001\u91cd\u3002</p>
        <div id="modeBar">
          <span id="lblDisplayMode" class="hint">\u663e\u793a\u6a21\u5f0f\uff1a</span>
          <button id="btnModeSimple" title="\u4ec5\u5c55\u793a\u5e38\u7528\u64cd\u4f5c\uff1b\u4e0d\u4f1a\u81ea\u52a8\u4fee\u6539\u6587\u4ef6\u6216\u914d\u7f6e">\u65b0\u624b\u6a21\u5f0f</button>
          <button id="btnModeAdvanced" title="\u5c55\u793a\u5168\u90e8\u529f\u80fd\uff1b\u6bcf\u9879\u64cd\u4f5c\u90fd\u9700\u8981\u4f60\u786e\u8ba4\u540e\u624d\u6267\u884c">\u9ad8\u7ea7\u6a21\u5f0f</button>
          <button id="btnLang" title="\u5207\u6362\u4e2d/\u82f1\u6587\u754c\u9762\u6807\u7b7e">\u4e2d\u6587/English</button>
          <button id="btnReloadPanel" title="\u91cd\u8f7d\u9762\u677f\uff08\u91cd\u65b0\u6e32\u67d3\u5e76\u63e1\u624b\uff09">\u91cd\u8f7d\u9762\u677f</button>
          <button id="btnDiagTop" title="\u6536\u96c6\u524d\u7aef\u9519\u8bef\u3001\u73af\u5883\u4e0e\u5ba1\u8ba1\u4fe1\u606f\uff08\u5199\u5165 .mcp/dashboard/panel_diag.json\uff09">\u8bca\u65ad</button>
        </div>
        <div id="ticker" style="height:auto; background:#f6f6f6; border:1px solid #ddd; padding:4px 8px; margin:6px 0;">
          <span id="tickerText" style="display:inline-block; white-space:nowrap; font-size:12px; color:#333;"></span>
        </div>
        <div id="proj" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b id="lblCurProject">\u5f53\u524d\u9879\u76ee:</b> <span id="curProject">(\u68c0\u6d4b\u4e2d)</span>
          <button id="btnSelectProject" title="\u5728\u5f53\u524d IDE \u7a97\u53e3\u5185\u9009\u62e9/\u5207\u6362\u9879\u76ee\u6839\uff1b\u6240\u6709\u8bfb\u5199\u9650\u5b9a\u5728\u6240\u9009\u9879\u76ee\u7684 .mcp/ \u76ee\u5f55">\u9009\u62e9/\u5207\u6362\u9879\u76ee\u2026</button>
        </div>
        <div id="lic" style="padding:4px 6px; border:1px solid #ddd; background:#fafafa; margin:6px 0; display:flex; align-items:center; gap:8px;">
          <b>License:</b> <span id="licText">(loading)</span>
          <button id="btnLicVerify" title="\u6821\u9a8c\u8bb8\u53ef\u72b6\u6001\uff08\u672c\u5730\u53ea\u8bfb\uff0c\u4e0d\u51fa\u7f51\uff09">Verify</button>
          <button id="btnLicActivate" title="\u4ece\u672c\u5730\u6587\u4ef6\u6fc0\u6d3b\u8bb8\u53ef\uff08\u4ec5\u5199\u5165\u8bb8\u53ef\u914d\u7f6e\uff0c\u4e0d\u6539\u6e90\u7801\uff09">Activate\u2026</button>
        </div>
        <pre id="licDetail" style="white-space:pre-wrap; display:none; font-size:11px; color:#555; background:#f7f7f7; padding:4px;"></pre>
        <div id="info" style="margin:6px 0; color:#d33;"></div>
        <div id="simpleBar" style="margin:10px 0; padding:8px; border:1px solid #ddd; background:#f9fbff;">
          <div id="hintQuick" class="hint">\u4e09\u6b65\u4e0a\u624b\uff1a</div>
          <div>
            <button id="btnSimpleInstall" title="\u4e3a\u5f53\u524d\u9879\u76ee\u521b\u5efa .mcp/venv \u5e76\u5b89\u88c5\u57fa\u7840\u5de5\u5177\u94fe\uff08ruff/black/mypy/pytest\uff09">1) \u51c6\u5907\u5e76\u5b89\u88c5\u73af\u5883</button>
            <button id="btnSimpleCoverage" title="\u8bfb\u53d6 coverage.xml \u6c47\u603b\u5f31\u9879/\u5206\u7ec4/\u8fd1\u9608\u503c\u5e76\u8f93\u51fa\u5230 .mcp/dashboard">2) \u52a0\u8f7d\u8986\u76d6\u7387</button>
            <button id="btnSimplePlan" title="\u6253\u5f00 .mcp/plan.md\uff08\u9879\u76ee\u4efb\u52a1\u4e0e\u8fdb\u5ea6\u7684\u552f\u4e00\u6743\u5a01\u6765\u6e90\uff09">3) \u6253\u5f00\u8ba1\u5212</button>
          </div>
          <div>
            <button id="btnSimpleIngest" title="\u5c06 README/docs \u8f6c\u6362\u4e3a\u89c4\u5219\uff08\u5199\u5165 .mcp/rules_*\uff09\uff0c\u4e0d\u6539\u73b0\u6709\u6e90\u7801">\u6444\u53d6\u89c4\u5219\uff08README.md, docs/\uff09</button>
            <button id="btnSimpleStatus" title="\u5237\u65b0\u72b6\u6001\u5e76\u5199\u5165 .mcp/dashboard/status.json\uff08\u53ea\u8bfb\u6e90\u7801\uff09">\u5237\u65b0\u72b6\u6001</button>
          </div>
          <div class="hint">\u9047\u5230\u95ee\u9898 \u2192 \u70b9\u51fb\u201c\u5237\u65b0\u72b6\u6001\u201d\uff0c\u6216\u5207\u6362\u5230\u201c\u9ad8\u7ea7\u6a21\u5f0f\u201d\u67e5\u770b\u66f4\u591a\u529f\u80fd\u3002</div>
        </div>
        <div class="adv" style="margin:8px 0;">
          <input id="nlInput" placeholder="\u81ea\u7136\u8bed\u8a00\u6307\u4ee4\uff1a\u5982 \u6444\u53d6\u89c4\u5219 README.md, docs/ / \u52a0\u8f7d\u8986\u76d6\u7387 / \u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6" style="width:65%;" title="\u5728\u6b64\u8f93\u5165\u4e2d\u6587\u6216\u82f1\u6587\u6307\u4ee4\uff0c\u6309\u201c\u6267\u884c\u201d\u6309\u94ae\u8fd0\u884c\uff1b\u793a\u4f8b\u53ef\u70b9\u51fb\u4e0b\u65b9\u5feb\u901f\u586b\u5145" />
          <button id="nlSend" title="\u6267\u884c\u8f93\u5165\u6846\u4e2d\u7684\u81ea\u7136\u8bed\u8a00\u6307\u4ee4\uff0c\u4ec5\u4f5c\u7528\u4e8e\u5f53\u524d\u9879\u76ee">\u6267\u884c</button>
          <button id="nlExamples" title="\u63d2\u5165\u5e38\u7528\u6307\u4ee4\u793a\u4f8b\u5230\u8f93\u5165\u6846\uff0c\u4e0d\u4f1a\u76f4\u63a5\u6267\u884c">\u8303\u4f8b</button>
          <button id="nlClear" title="\u6e05\u7a7a\u9762\u677f\u4e2d\u7684\u5386\u53f2\u663e\u793a\uff08\u4ec5 UI\uff0c\u4e0d\u5199\u78c1\u76d8\uff09">\u6e05\u7a7a\u5386\u53f2</button>
          <button id="btnStatusUpdate" title="\u5237\u65b0\u72b6\u6001\u6458\u8981\u5e76\u66f4\u65b0 .mcp/dashboard/status.json">\u5237\u65b0\u72b6\u6001</button>
          <span style="margin-left:6px;">\u8fd1\u9608\u503c%:</span>
          <input id="nearPct" value="3" style="width:40px;" title="\u663e\u793a\u8986\u76d6\u7387\u8ddd\u79bb\u9608\u503c\u2264\u8be5\u767e\u5206\u6bd4\u7684\u6587\u4ef6\uff08\u9ed8\u8ba43%\uff09" />
          <button id="btnCovNearInline" title="\u5728\u9762\u677f\u5185\u663e\u793a\u201c\u8fd1\u9608\u503c\u201d\u6587\u4ef6\uff08\u4ec5 UI \u8fc7\u6ee4\uff09">\u663e\u793a\u8fd1\u9608\u503c</button>
          <button id="btnIdeScaffold" title="\u751f\u6210\u5f53\u524d IDE \u7684\u6700\u5c0f\u914d\u7f6e/\u811a\u672c\uff08\u4ec5\u5199\u5165\u9879\u76ee\u5185\u914d\u7f6e\u76ee\u5f55\uff09">\u751f\u6210 IDE \u96c6\u6210\u914d\u7f6e</button>
          <button id="btnCompliance" title="\u751f\u6210\u5408\u89c4\u627f\u8bfa\u6587\u6863\uff08\u5199\u5165 .mcp/compliance.md\uff09">\u751f\u6210\u5408\u89c4\u627f\u8bfa</button>
          <button id="btnOpenCompliance" title="\u6253\u5f00\u5408\u89c4\u627f\u8bfa\u6587\u6863\uff08\u53ea\u8bfb\uff09">\u6253\u5f00\u5408\u89c4\u627f\u8bfa</button>
          <button id="btnOpenIdeDir" title="\u6253\u5f00 IDE \u76f8\u5173\u76ee\u5f55\uff08\u5982 .vscode/\uff0c\u53ea\u8bfb\uff09">\u6253\u5f00 IDE \u76ee\u5f55</button>
          <button id="btnEvents" title="\u663e\u793a\u8fd1\u671f\u4e8b\u4ef6\uff08\u53ea\u8bfb .mcp/dashboard/cmd_events.jsonl\uff09">\u4e8b\u4ef6\u5386\u53f2</button>
          <button id="btnAudit" title="\u663e\u793a\u5b89\u5168\u5ba1\u8ba1\uff08\u53ea\u8bfb .mcp/dashboard/security_audit.jsonl\uff09">\u5b89\u5168\u5ba1\u8ba1</button>
          <button id="btnInfo" title="\u663e\u793a\u72b6\u6001\u6458\u8981\u4fe1\u606f\uff08\u53ea\u8bfb .mcp/dashboard/status.json\uff09">\u72b6\u6001\u6458\u8981 Info</button>
          <button id="btnCopyEvents" title="\u590d\u5236\u4e8b\u4ef6\u5185\u5bb9\u5230\u526a\u8d34\u677f\uff08\u4ec5 UI\uff0c\u4e0d\u5199\u78c1\u76d8\uff09">\u590d\u5236\u4e8b\u4ef6</button>
          <button id="btnCopyInfo" title="\u590d\u5236\u72b6\u6001\u6458\u8981\u5230\u526a\u8d34\u677f\uff08\u4ec5 UI\uff0c\u4e0d\u5199\u78c1\u76d8\uff09">\u590d\u5236\u6458\u8981</button>
          <button id="btnOpenStatusFile" title="\u6253\u5f00 .mcp/dashboard/status.json\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 status.json</button>
          <button id="btnOpenEventsFile" title="\u6253\u5f00 .mcp/dashboard/cmd_events.jsonl\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 events</button>
          <button id="btnOpenAuditFile" title="\u6253\u5f00 .mcp/dashboard/security_audit.jsonl\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 audit</button>
        </div>
        <div id="nlExamplesBox" class="adv" style="display:none; margin:4px 0 10px 0;">
          <span style="opacity:.8">\u5feb\u901f\u8303\u4f8b\uff1a</span>
          <button data-nl="\u6444\u53d6\u89c4\u5219 README.md, docs/">\u6444\u53d6\u89c4\u5219</button>
          <button data-nl="\u52a0\u8f7d\u8986\u76d6\u7387">\u52a0\u8f7d\u8986\u76d6\u7387</button>
          <button data-nl="\u4ec5\u770b\u8fd1\u9608\u503c 3">\u4ec5\u770b\u8fd1\u9608\u503c</button>
          <button data-nl="\u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6">\u5f00\u542f\u8bb0\u5fc6</button>
          <button data-nl="\u751f\u6210 CI">\u751f\u6210 CI</button>
          <button data-nl="\u6821\u9a8c CI">\u6821\u9a8c CI</button>
          <button data-nl="\u89c4\u5219 \u6458\u8981">\u89c4\u5219\u6458\u8981</button>
        </div>
        <div id="nlCatalog" style="margin:6px 0;">
          <fieldset style="border:1px solid #ddd; padding:6px;">
            <legend>\u81ea\u7136\u8bed\u8a00\u547d\u4ee4\u793a\u4f8b\uff08\u70b9\u51fb\u5373\u6267\u884c\uff09</legend>
            <div class="hint">\u89e6\u53d1\u8bcd\uff1a\u6444\u53d6\u89c4\u5219 / \u52a0\u8f7d\u8986\u76d6\u7387 / \u8fd1\u9608\u503c / \u6253\u5f00\u8ba1\u5212 / \u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6 / \u751f\u6210 CI / \u6821\u9a8c CI / \u5b89\u88c5\u94a9\u5b50</div>
            <div style="margin-top:6px;"><b>\u89c4\u5219</b>\uff1a
              <button data-nl="\u6444\u53d6\u89c4\u5219 README.md, docs/">\u6444\u53d6\u89c4\u5219 README.md, docs/</button>
              <button data-nl="\u8f7d\u5165\u7f16\u8bd1\u89c4\u5219">\u8f7d\u5165\u7f16\u8bd1\u89c4\u5219</button>
              <button data-nl="\u6821\u9a8c \u89c4\u5219">\u6821\u9a8c \u89c4\u5219</button>
            </div>
            <div style="margin-top:6px;"><b>\u8986\u76d6\u7387</b>\uff1a
              <button data-nl="\u52a0\u8f7d\u8986\u76d6\u7387">\u52a0\u8f7d\u8986\u76d6\u7387</button>
              <button data-nl="\u4ec5\u770b\u5f31\u9879">\u4ec5\u770b\u5f31\u9879</button>
              <button data-nl="\u4ec5\u770b\u8fd1\u9608\u503c 3">\u4ec5\u770b\u8fd1\u9608\u503c 3</button>
            </div>
            <div style="margin-top:6px;"><b>\u8ba1\u5212\u4e0e\u8bb0\u5fc6</b>\uff1a
              <button data-nl="\u6253\u5f00 \u8ba1\u5212">\u6253\u5f00 \u8ba1\u5212</button>
              <button data-nl="\u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6">\u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6</button>
            </div>
            <div style="margin-top:6px;"><b>CI</b>\uff1a
              <button data-nl="\u751f\u6210 CI">\u751f\u6210 CI</button>
              <button data-nl="\u6821\u9a8c CI">\u6821\u9a8c CI</button>
              <button data-nl="\u5b89\u88c5 \u94a9\u5b50">\u5b89\u88c5 \u94a9\u5b50</button>
            </div>
          </fieldset>
        </div>
        <div>
          <h4 style="margin:8px 0 4px;">\u6700\u8fd1\u6307\u4ee4</h4>
          <ul id="nlHistory" style="padding-left:18px;"></ul>
        </div>
        <div style="margin:8px 0;">
          <fieldset style="border:1px solid #ddd; padding:6px;">
            <legend>\u5de5\u4f5c\u6d41\u5e38\u7528\u64cd\u4f5c</legend>
            <button id="btnLoad" title="\u4ece .mcp/rules_compiled.* \u8bfb\u53d6\u5e76\u5c55\u793a\u7f16\u8bd1\u540e\u7684\u89c4\u5219\uff08\u53ea\u8bfb\uff09">\u8f7d\u5165\u7f16\u8bd1\u89c4\u5219 / Load Rules</button>
            <button id="btnIngest" title="\u5c06 README\u3001docs \u7b49\u6587\u6863\u8f6c\u6362\u4e3a\u89c4\u5219\uff08\u5199\u5165 .mcp/rules_*\uff09">\u6444\u53d6\u89c4\u5219 / Ingest</button>
            <button id="btnValidate" title="\u91cd\u65b0\u7f16\u8bd1\u5e76\u6821\u9a8c\u89c4\u5219\uff0c\u8f93\u51fa\u51b2\u7a81\u4e0e\u5efa\u8bae\uff08\u53ea\u8bfb\u5c55\u793a\uff09">\u6821\u9a8c\u89c4\u5219 / Validate</button>
            <button id="btnHooks" title="\u5b89\u88c5 pre-commit/commit-msg/pre-push \u94a9\u5b50\uff08\u4fbf\u4e8e\u5728\u63d0\u4ea4\u524d\u81ea\u52a8\u68c0\u67e5\uff09">\u5b89\u88c5\u94a9\u5b50 / Install Hooks</button>
            <button id="btnLoadSugg" title="\u8bfb\u53d6\u5e76\u5c55\u793a\u89c4\u5219\u5efa\u8bae\uff08\u51b2\u7a81\u4e0e\u4f18\u5316\u63d0\u793a\uff09">\u8f7d\u5165\u5efa\u8bae / Load Suggestions</button>
            <button id="btnCoverage" title="\u8bfb\u53d6 coverage.xml \u5e76\u751f\u6210\u8584\u5f31/\u5206\u7ec4/\u8fd1\u9608\u503c\u6458\u8981\uff08\u53ea\u8bfb\uff09">\u52a0\u8f7d\u8986\u76d6\u7387 / Load Coverage</button>
            <button id="btnShowWeak" title="\u53ea\u663e\u793a\u4f4e\u4e8e\u9608\u503c\u7684\u8584\u5f31\u6587\u4ef6\uff08\u66f4\u6613\u805a\u7126\u95ee\u9898\uff09">\u4ec5\u770b\u5f31\u9879 / Show Weak</button>
            <button id="btnCovTree" title="\u6309\u76ee\u5f55\u5c55\u793a\u8584\u5f31\u6587\u4ef6\uff08\u5c42\u7ea7\u6d4f\u89c8\uff0c\u4fbf\u4e8e\u5b9a\u4f4d\uff09">\u52a0\u8f7d\u76ee\u5f55\u6811 / Load Weak Tree</button>
            <button id="btnCovNear" title="\u663e\u793a\u8ddd\u79bb\u9608\u503c\u5f88\u8fd1\uff08\u9ed8\u8ba4\u22643%\uff09\u4f46\u5c1a\u672a\u8dcc\u7834\u7684\u6587\u4ef6\uff08\u5feb\u901f\u8865\u9f50\uff09">\u4ec5\u770b\u8fd1\u9608\u503c / Show Near</button>
            <button id="btnCovExport" title="\u5bfc\u51fa CSV/JSON \u62a5\u8868\u5230 .mcp/dashboard\uff08\u4f9b\u5ba1\u9605\u4e0e\u5f52\u6863\uff09">\u5bfc\u51fa\u8986\u76d6\u7387\u62a5\u8868 / Export Coverage</button>
            <button id="btnPrepareEnvDry" title="\u9884\u89c8\u5c06\u8981\u521b\u5efa\u7684\u865a\u62df\u73af\u5883\u4e0e\u5b89\u88c5\u7684\u5de5\u5177\u94fe\uff08\u4e0d\u505a\u4efb\u4f55\u6539\u52a8\uff09">\u51c6\u5907\u73af\u5883(\u9884\u89c8) / Prepare Env (dry-run)</button>
            <button id="btnPrepareEnvInstall" title="\u521b\u5efa .mcp/venv \u5e76\u5b89\u88c5 ruff/black/mypy/pytest \u7b49\u57fa\u7840\u5de5\u5177">\u51c6\u5907\u5e76\u5b89\u88c5\u73af\u5883 / Prepare & Install</button>
          </fieldset>
        </div>
        <div class="adv" style="margin:8px 0;">
          <button id="btnOpenUserGuide" title="\u6253\u5f00\u4e0a\u624b\u6587\u6863\uff08\u53ea\u8bfb\uff09\uff0c\u5305\u542b\u5e38\u89c1\u6d41\u7a0b\u4e0e\u622a\u56fe\u793a\u4f8b">\u6253\u5f00\u7528\u6237\u4e0a\u624b / Open User Guide</button>
          <button id="btnOpenIdeSupport" title="\u6253\u5f00 IDE \u96c6\u6210\u8bf4\u660e\uff08\u53ea\u8bfb\uff09\uff0c\u5305\u542b VS Code/Cursor/JetBrains \u7684\u6700\u5c0f\u914d\u7f6e">\u6253\u5f00 IDE \u652f\u6301 / Open IDE Support</button>
        </div>
        <div class="adv">
          <h3 id="hdrTools">\u53ef\u7528\u5de5\u5177\uff08\u793a\u4f8b\uff09</h3>
          <ul>${toolsListHtml}</ul>
        </div>
        <div class="adv">
          <h3 id="hdrCompiled">\u9879\u76ee\u89c4\u5219\uff08\u7f16\u8bd1\u7248\uff09</h3>
          <pre id="rules" style="white-space:pre-wrap; background:#1112; padding:8px;">${md || '\u6682\u65e0\u5185\u5bb9 / No content'}</pre>
        </div>
        <div class="adv">
          <h3 id="hdrConflictsNav">\u51b2\u7a81\u5b9a\u4f4d\uff08\u53ef\u70b9\u51fb\u8df3\u8f6c\uff09</h3>
          <ul id="conflicts"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrConflictsSugg">\u51b2\u7a81\u4e0e\u5efa\u8bae\uff08Conflicts & Suggestions\uff09</h3>
          <pre id="sugg" style="white-space:pre-wrap; background:#1111; padding:8px;">${sugg || '\u6682\u65e0\u5efa\u8bae / No suggestions'}</pre>
        </div>
        <div class="adv">
          <h3 id="hdrOnboard">\u89c4\u5219\u5f15\u5bfc\uff08Onboard\uff09</h3>
          <div style="margin:6px 0;">
            <button id="btnOnboardPreview" title="\u9884\u89c8\u63a8\u8350\u7684\u89c4\u5219\u4e0e\u9608\u503c\uff08\u53ea\u8bfb\u5c55\u793a\uff0c\u4e0d\u505a\u4fee\u6539\uff09">\u9884\u89c8\u63a8\u8350 / Preview</button>
            <button id="btnOnboardApply" title="\u4e00\u952e\u91c7\u7eb3\u63a8\u8350\uff08\u4ec5\u5199\u5165 .mcp/assistant.yaml \u6216\u76f8\u5173\u914d\u7f6e\uff0c\u4e0d\u6539\u6e90\u7801\uff09">\u4e00\u952e\u91c7\u7eb3 / Apply</button>
          </div>
          <pre id="onboardSummary" style="white-space:pre-wrap; background:#f7f7f7; padding:8px; font-size:12px; color:#333;">\uff08\u70b9\u51fb\u201c\u9884\u89c8\u63a8\u8350\u201d\u67e5\u770b\u5c06\u542f\u7528\u7684\u89c4\u5219\u6458\u8981\uff09</pre>
        </div>
        <div class="adv">
          <h3 id="hdrChat">Chat\uff08\u53ef\u9009\uff09</h3>
          <div style="margin:6px 0;">
            <button id="btnChatEnable" title="\u542f\u7528\u201c\u5bf9\u8bdd\u6458\u8981\u8ffd\u52a0\u201d\u529f\u80fd\uff08\u9ed8\u8ba4\u4ecd\u4e0d\u5199\u8bb0\u5fc6\uff0c\u9664\u975e\u663e\u5f0f\u5141\u8bb8\uff09">\u542f\u7528\u8ffd\u52a0\u6458\u8981 / Enable</button>
            <button id="btnChatDisable" title="\u7981\u7528\u201c\u5bf9\u8bdd\u6458\u8981\u8ffd\u52a0\u201d\u529f\u80fd">\u7981\u7528 / Disable</button>
            <button id="btnChatPreview" title="\u9884\u89c8\u5c06\u8981\u8ffd\u52a0\u7684\u6458\u8981\u5185\u5bb9\uff08\u53ea\u8bfb\uff09">\u9884\u89c8\u6458\u8981 / Preview</button>
          </div>
          <pre id="chatPreview" style="white-space:pre-wrap; background:#f7f7f7; padding:8px; font-size:12px; color:#666;">\uff08\u9ed8\u8ba4\u5173\u95ed\uff1b\u542f\u7528\u540e\uff0c\u6bcf\u8f6e\u5bf9\u8bdd\u53ef\u8ffd\u52a0\u201c\u4e0a\u4e00\u8f6e\u95ee\u7b54\u6458\u8981\u201d\u81f3\u8bb0\u5fc6\u3002\u65e0\u9065\u6d4b\uff0c\u4e0d\u51fa\u7f51\u3002\uff09</pre>
        </div>
        <div class="adv">
          <h3 id="hdrCovGroups">\u8986\u76d6\u7387\u5206\u7ec4</h3>
          <ul id="covGroups"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrWeakTop">\u8986\u76d6\u7387\u8584\u5f31\uff08Top 20\uff09</h3>
          <input id="covFilter" placeholder="\u8fc7\u6ee4\u6587\u4ef6\u540d\u5173\u952e\u8bcd..." title="\u5728\u8584\u5f31\u5217\u8868\u4e2d\u8fc7\u6ee4\u5305\u542b\u8be5\u5173\u952e\u8bcd\u7684\u6587\u4ef6\u540d" />
          <button id="btnCovFilter" title="\u5e94\u7528\u4e0a\u65b9\u7684\u6587\u4ef6\u540d\u5173\u952e\u8bcd\u8fc7\u6ee4\uff08\u4ec5 UI\uff09">\u8fc7\u6ee4</button>
          <button id="btnOpenWeakCsv" title="\u67e5\u770b\u8584\u5f31\u6587\u4ef6 TopN \u7684 CSV">\u6253\u5f00 weak_top.csv</button>
          <button id="btnOpenNearCsv" title="\u67e5\u770b\u8fd1\u9608\u503c\u6587\u4ef6 TopN \u7684 CSV">\u6253\u5f00 near_top.csv</button>
          <button id="btnOpenGroupsCsv" title="\u67e5\u770b\u8986\u76d6\u7387\u5206\u7ec4\u805a\u5408\u7684 CSV">\u6253\u5f00 groups.csv</button>
          <button id="btnOpenGroupsMd" title="\u4e3a JetBrains UI \u9884\u89c8\u7684\u5206\u7ec4\u6458\u8981">\u6253\u5f00 jb_groups.md</button>
          <ul id="covWeak"></ul>
          <h4 id="hdrCsvPreview">CSV \u9884\u89c8</h4>
          <pre id="csvPreview" style="white-space:pre-wrap; background:#f7f7f7; padding:4px; font-size:11px;"></pre>
          <div>
            <label id="lblCsvSwitch">\u5207\u6362\u9884\u89c8\uff1a</label>
            <select id="csvSelect" title="\u9009\u62e9\u8981\u9884\u89c8\u7684 CSV \u62a5\u8868">
              <option value="weak_top.csv">weak_top.csv</option>
              <option value="near_top.csv">near_top.csv</option>
              <option value="groups.csv">groups.csv</option>
            </select>
            <button id="btnCsvReload" title="\u91cd\u65b0\u6e32\u67d3\u4e0a\u9762\u9009\u62e9\u7684 CSV \u62a5\u8868\u5934\u90e8">\u91cd\u65b0\u52a0\u8f7d\u9884\u89c8</button>
        </div>
        </div>
        <div class="adv">
          <h3 id="hdrCovTree">\u8986\u76d6\u7387\u76ee\u5f55\u6811\uff08\u5f31\u9879\uff09</h3>
          <ul id="covTree"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrRecent">\u6700\u8fd1\u8bb0\u5fc6\u4e0e\u8ba1\u5212</h3>
          <pre id="memory" style="white-space:pre-wrap; background:#1102; padding:8px;">\uff08\u70b9\u51fb\u201c\u52a0\u8f7d\u8bb0\u5fc6 / \u52a0\u8f7d\u8ba1\u5212 / \u4e8b\u4ef6\u5386\u53f2\u201d\u83b7\u53d6\uff09</pre>
          <pre id="plan" style="white-space:pre-wrap; background:#1101; padding:8px;"></pre>
          <h4 id="hdrEvents">\u4e8b\u4ef6\u5386\u53f2\uff08\u6700\u8fd1\uff09</h4>
          <pre id="events" style="white-space:pre-wrap; background:#0211; padding:8px;"></pre>
          <h4 id="hdrAudit">\u5b89\u5168\u5ba1\u8ba1\uff08\u6700\u8fd1\uff09</h4>
          <pre id="audit" style="white-space:pre-wrap; background:#0211; padding:8px;"></pre>
          <h4 id="hdrStatus">\u72b6\u6001\u6458\u8981\uff08\u6700\u8fd1\uff09</h4>
          <pre id="infolist" style="white-space:pre-wrap; background:#1021; padding:8px;"></pre>
        </div>
        <div class="adv">
          <h3 id="hdrTasksPending">\u5269\u4f59\u4efb\u52a1\uff08\u6765\u81ea .mcp/plan.md\uff09</h3>
          <ul id="tasksPending"></ul>
          <h3 id="hdrTasksDone">\u5df2\u5b8c\u6210</h3>
          <ul id="tasksDone"></ul>
        </div>
        <div class="adv">
          <h3 id="hdrCI">CI \u914d\u7f6e\uff08hadolint / semgrep / mutation\uff09</h3>
          <label><input type="checkbox" id="ciHadolint"> \u542f\u7528 hadolint</label><br/>
          \u955c\u50cf: <input id="ciHadolintImage" style="width:260px" placeholder="hadolint/hadolint:latest"/>
          \u53c2\u6570: <input id="ciHadolintArgs" style="width:260px" placeholder="--ignore DL3008"/><br/>
          semgrep \u89c4\u5219: <input id="ciSemgrepConfig" style="width:180px" placeholder="auto / p/ci"/>
          <div style="margin-top:4px;">
            <label><input type="checkbox" id="ciMutGateStrict"> \u4e25\u683c\u6a21\u5f0f\u53d8\u5f02\u95e8\u7981\uff08strict \u6216\u663e\u5f0f\u5f00\u542f\uff09</label>
          </div>
          <div style="margin-top:4px;">
            <label><input type="checkbox" id="execChecksDelegate"> checks \u59d4\u6258\u81f3\u7edf\u4e00 runner\uff08process.run_cmd\uff09</label>
          </div>
          <button id="btnCiSave" title="\u4fdd\u5b58 CI \u914d\u7f6e\u5230\u9879\u76ee\uff08\u5199\u5165 .github/workflows \u6216\u914d\u7f6e\u6587\u4ef6\uff09">\u4fdd\u5b58 CI \u914d\u7f6e</button>
          <button id="btnCiGen" title="\u751f\u6210 CI \u5de5\u4f5c\u6d41\u6587\u4ef6\uff08\u5199\u5165 .github/workflows\uff09">\u751f\u6210 CI</button>
          <button id="btnCiPreview" title="\u5728\u9762\u677f\u5185\u9884\u89c8 CI \u5185\u5bb9\uff08\u53ea\u8bfb\uff09">\u9884\u89c8 CI</button>
          <button id="btnCiOpen" title="\u6253\u5f00 CI \u5de5\u4f5c\u6d41\u6587\u4ef6\uff08\u53ea\u8bfb\uff09">\u6253\u5f00 CI \u6587\u4ef6</button>
          <button id="btnInsertRules" title="\u63d2\u5165 .semgrep.yml / .hadolint.yaml \u793a\u4f8b\u89c4\u5219\uff08\u4fbf\u4e8e\u5feb\u901f\u542f\u7528\u57fa\u7840\u68c0\u67e5\uff09">\u63d2\u5165\u793a\u4f8b\u89c4\u5219</button>
          <span id="ciStatus" style="margin-left:8px;color:#888;"></span>
          <div style="margin-top:6px;">
            <h4>CI \u9884\u89c8\uff08\u5185\u8054\uff09</h4>
            <pre id="ciPreviewBox" style="white-space:pre-wrap; background:#f1f1f1; padding:6px; max-height:200px; overflow:auto;"></pre>
            <h4>CI \u6821\u9a8c\u7ed3\u679c</h4>
            <ul id="ciChecks"></ul>
          </div>
        </div>
        <script nonce="${nonceVal}" defer>
          const vscode = acquireVsCodeApi();
          // Collect front-end errors for diagnostics
          try {
            window.__panelErrors = [];
            window.addEventListener('error', (e) => {
              try { window.__panelErrors.push('error: ' + (e.message||'') + ' @ ' + (e.filename||'') + ':' + (e.lineno||'') + ':' + (e.colno||'')); } catch {}
            });
            window.addEventListener('unhandledrejection', (e) => {
              try { window.__panelErrors.push('unhandledrejection: ' + String(e.reason||'')); } catch {}
            });
          } catch {}
          try { vscode.postMessage({ t: 'ready' }); } catch {}
          try { vscode.postMessage({ t: 'handshake' }); } catch {}
          // ---- UI mode (simple/advanced) ----
          (function(){
            try {
              const state = (vscode.getState && vscode.getState()) || {};
              let mode = (state && state.uiMode) || (typeof localStorage !== 'undefined' ? localStorage.getItem('ruleflow.uiMode') : '') || 'simple';
              const apply = (m) => {
                try { document.body.classList.remove('simple','advanced'); document.body.classList.add(m); } catch {}
                try { vscode.setState && vscode.setState({ ...(state||{}), uiMode: m }); } catch {}
                try { localStorage && localStorage.setItem('ruleflow.uiMode', m); } catch {}
              };
              const applyLang = (lang) => {
                const zh = lang === 'zh';
                const set = (id, text, title) => { try { const el = document.getElementById(id); if (el && text!==undefined) el.textContent = text; if (el && title!==undefined) el.title = title; } catch {} };
                set('hdrTitle', zh ? 'MCP \u89c4\u5219\u4e0e\u4e0a\u4e0b\u6587\u52a9\u624b' : 'MCP Rules & Context Assistant');
                set('pConnected', zh ? '\u5df2\u8fde\u63a5\u5230 Python MCP Server\uff08\u6700\u5c0f\u534f\u8bae\uff09\u3002\u9ed8\u8ba4\u5feb\u901f\u5185\u73af\uff1a\u4fdd\u5b58\u8f7b\u3001\u63a8\u9001\u91cd\u3002' : 'Connected to Python MCP Server (minimal protocol). Fast inner loop: light save, gated push.');
                set('lblDisplayMode', zh ? '\u663e\u793a\u6a21\u5f0f\uff1a' : 'Display mode:');
                set('lblCurProject', zh ? '\u5f53\u524d\u9879\u76ee:' : 'Project:');
                set('hintQuick', zh ? '\u4e09\u6b65\u4e0a\u624b\uff1a' : 'Quick start:');
                set('btnModeSimple', zh ? '\u65b0\u624b\u6a21\u5f0f' : 'Simple', zh ? '\u4ec5\u5c55\u793a\u5e38\u7528\u64cd\u4f5c\uff1b\u4e0d\u4f1a\u81ea\u52a8\u4fee\u6539\u6587\u4ef6\u6216\u914d\u7f6e' : 'Show common actions only; no writes');
                set('btnModeAdvanced', zh ? '\u9ad8\u7ea7\u6a21\u5f0f' : 'Advanced', zh ? '\u5c55\u793a\u5168\u90e8\u529f\u80fd\uff1b\u6bcf\u9879\u64cd\u4f5c\u90fd\u9700\u8981\u4f60\u786e\u8ba4\u540e\u624d\u6267\u884c' : 'Show all features; confirm before actions');
                set('btnLang', zh ? '\u4e2d\u6587/English' : 'English/\u4e2d\u6587', zh ? '\u5207\u6362\u4e2d/\u82f1\u6587\u754c\u9762\u6807\u7b7e' : 'Toggle Chinese/English labels');
                set('btnSimpleInstall', zh ? '1) \u51c6\u5907\u5e76\u5b89\u88c5\u73af\u5883' : '1) Prepare & Install Env', zh ? '\u4e3a\u5f53\u524d\u9879\u76ee\u521b\u5efa .mcp/venv \u5e76\u5b89\u88c5\u57fa\u7840\u5de5\u5177\u94fe\uff08ruff/black/mypy/pytest\uff09' : 'Create .mcp/venv and install basics');
                set('btnSimpleCoverage', zh ? '2) \u52a0\u8f7d\u8986\u76d6\u7387' : '2) Load Coverage', zh ? '\u8bfb\u53d6 coverage.xml \u6c47\u603b\u5f31\u9879/\u5206\u7ec4/\u8fd1\u9608\u503c\u5e76\u8f93\u51fa\u5230 .mcp/dashboard' : 'Read coverage.xml and summarize');
                set('btnSimplePlan', zh ? '3) \u6253\u5f00\u8ba1\u5212' : '3) Open Plan', zh ? '\u6253\u5f00 .mcp/plan.md\uff08\u9879\u76ee\u4efb\u52a1\u4e0e\u8fdb\u5ea6\u7684\u552f\u4e00\u6743\u5a01\u6765\u6e90\uff09' : 'Open .mcp/plan.md');
                set('btnSimpleIngest', zh ? '\u6444\u53d6\u89c4\u5219\uff08README.md, docs/\uff09' : 'Ingest Rules (README.md, docs/)', zh ? '\u5c06 README/docs \u8f6c\u6362\u4e3a\u89c4\u5219\uff08\u5199\u5165 .mcp/rules_*\uff09\uff0c\u4e0d\u6539\u73b0\u6709\u6e90\u7801' : 'Convert README/docs to rules into .mcp');
                set('btnSimpleStatus', zh ? '\u5237\u65b0\u72b6\u6001' : 'Refresh Status', zh ? '\u5237\u65b0\u72b6\u6001\u5e76\u5199\u5165 .mcp/dashboard/status.json\uff08\u53ea\u8bfb\u6e90\u7801\uff09' : 'Refresh status and write dashboard');
                set('nlSend', zh ? '\u6267\u884c' : 'Run', zh ? '\u6267\u884c\u8f93\u5165\u6846\u4e2d\u7684\u81ea\u7136\u8bed\u8a00\u6307\u4ee4\uff0c\u4ec5\u4f5c\u7528\u4e8e\u5f53\u524d\u9879\u76ee' : 'Run natural-language command');
                set('nlExamples', zh ? '\u8303\u4f8b' : 'Examples');
                set('nlClear', zh ? '\u6e05\u7a7a\u5386\u53f2' : 'Clear');
                set('btnIdeScaffold', zh ? '\u751f\u6210 IDE \u96c6\u6210\u914d\u7f6e' : 'Generate IDE Scaffold');
                set('btnCompliance', zh ? '\u751f\u6210\u5408\u89c4\u627f\u8bfa' : 'Gen Compliance');
                set('btnOpenCompliance', zh ? '\u6253\u5f00\u5408\u89c4\u627f\u8bfa' : 'Open Compliance');
                set('btnOpenIdeDir', zh ? '\u6253\u5f00 IDE \u76ee\u5f55' : 'Open IDE Dir');
                set('btnReloadPanel', zh ? '\u91cd\u8f7d\u9762\u677f' : 'Reload Panel', zh ? '\u91cd\u8f7d\u9762\u677f\uff08\u91cd\u65b0\u6e32\u67d3\u5e76\u63e1\u624b\uff09' : 'Reload panel (re-render & handshake)');
                set('btnEvents', zh ? '\u4e8b\u4ef6\u5386\u53f2' : 'Events', zh ? '\u663e\u793a\u8fd1\u671f\u4e8b\u4ef6\uff08\u53ea\u8bfb .mcp/dashboard/cmd_events.jsonl\uff09' : 'Show recent events');
                set('btnAudit', zh ? '\u5b89\u5168\u5ba1\u8ba1' : 'Security Audit', zh ? '\u663e\u793a\u5b89\u5168\u5ba1\u8ba1\uff08\u53ea\u8bfb .mcp/dashboard/security_audit.jsonl\uff09' : 'Show security audit');
                set('btnInfo', zh ? '\u72b6\u6001\u6458\u8981 Info' : 'Status Info');
                set('btnDiag', zh ? '\u8bca\u65ad' : 'Diagnostics', zh ? '\u6536\u96c6\u524d\u7aef\u9519\u8bef\u3001\u73af\u5883\u4e0e\u5ba1\u8ba1\u4fe1\u606f\u5230 .mcp/dashboard/panel_diag.json' : 'Collect front-end errors and audit report');
                // Section headings
                set('hdrTools', zh ? '\u53ef\u7528\u5de5\u5177\uff08\u793a\u4f8b\uff09' : 'Available Tools (samples)');
                set('hdrCompiled', zh ? '\u9879\u76ee\u89c4\u5219\uff08\u7f16\u8bd1\u7248\uff09' : 'Compiled Project Rules');
                set('hdrConflictsNav', zh ? '\u51b2\u7a81\u5b9a\u4f4d\uff08\u53ef\u70b9\u51fb\u8df3\u8f6c\uff09' : 'Conflicts (click to open)');
                set('hdrConflictsSugg', zh ? '\u51b2\u7a81\u4e0e\u5efa\u8bae\uff08Conflicts & Suggestions\uff09' : 'Conflicts & Suggestions');
                set('hdrOnboard', zh ? '\u89c4\u5219\u5f15\u5bfc\uff08Onboard\uff09' : 'Rules Onboarding');
                set('hdrChat', zh ? 'Chat\uff08\u53ef\u9009\uff09' : 'Chat (optional)');
                set('hdrCovGroups', zh ? '\u8986\u76d6\u7387\u5206\u7ec4' : 'Coverage Groups');
                set('hdrWeakTop', zh ? '\u8986\u76d6\u7387\u8584\u5f31\uff08Top 20\uff09' : 'Weak Coverage (Top 20)');
                set('hdrCsvPreview', zh ? 'CSV \u9884\u89c8' : 'CSV Preview');
                set('lblCsvSwitch', zh ? '\u5207\u6362\u9884\u89c8\uff1a' : 'Switch preview:');
                set('hdrCovTree', zh ? '\u8986\u76d6\u7387\u76ee\u5f55\u6811\uff08\u5f31\u9879\uff09' : 'Coverage Tree (weak)');
                set('hdrRecent', zh ? '\u6700\u8fd1\u8bb0\u5fc6\u4e0e\u8ba1\u5212' : 'Recent Memory & Plan');
                set('hdrEvents', zh ? '\u4e8b\u4ef6\u5386\u53f2\uff08\u6700\u8fd1\uff09' : 'Recent Events');
                set('hdrAudit', zh ? '\u5b89\u5168\u5ba1\u8ba1\uff08\u6700\u8fd1\uff09' : 'Security Audit (recent)');
                set('hdrStatus', zh ? '\u72b6\u6001\u6458\u8981\uff08\u6700\u8fd1\uff09' : 'Status Summary (recent)');
                set('hdrTasksPending', zh ? '\u5269\u4f59\u4efb\u52a1\uff08\u6765\u81ea .mcp/plan.md\uff09' : 'Pending Tasks (from .mcp/plan.md)');
                set('hdrTasksDone', zh ? '\u5df2\u5b8c\u6210' : 'Done');
                set('hdrCI', zh ? 'CI \u914d\u7f6e\uff08hadolint / semgrep / mutation\uff09' : 'CI Config (hadolint / semgrep / mutation)');
                // Placeholders
                try { const ip = document.getElementById('nlInput'); if (ip) ip.placeholder = zh ? '\u81ea\u7136\u8bed\u8a00\u6307\u4ee4\uff1a\u5982 \u6444\u53d6\u89c4\u5219 README.md, docs/ / \u52a0\u8f7d\u8986\u76d6\u7387 / \u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6' : 'NL command: e.g. Ingest README.md, docs/ / Load Coverage / Enable memory'; } catch {}
                try { window.applyLang = applyLang; } catch {}
              };
              apply(mode);
              const btnS = document.getElementById('btnModeSimple');
              const btnA = document.getElementById('btnModeAdvanced');
              if (btnS) btnS.onclick = () => apply('simple');
              if (btnA) btnA.onclick = () => apply('advanced');
              const btnL = document.getElementById('btnLang');
              if (btnL) btnL.onclick = () => {
                try {
                  const st = (vscode.getState && vscode.getState()) || {};
                  const cur = (st && st.lang) || (typeof localStorage !== 'undefined' ? localStorage.getItem('ruleflow.lang') : '') || 'zh';
                  const next = (String(cur) === 'zh') ? 'en' : 'zh';
                  if (vscode.setState) vscode.setState({ ...(st||{}), lang: next });
                  try { localStorage && localStorage.setItem('ruleflow.lang', next); } catch {}
                  vscode.postMessage({ t: 'info', text: (next==='zh' ? '\u5df2\u5207\u6362\u5230\u4e2d\u6587' : 'Switched to English') });
                  applyLang(next);
                  // persist to workspace (shared across windows)
                  try { vscode.postMessage({ t: 'lang.set', value: next }); } catch {}
                } catch {}
              };
              try {
                const st = (vscode.getState && vscode.getState()) || {};
                const savedLang = (st && st.lang) || (typeof localStorage !== 'undefined' ? localStorage.getItem('ruleflow.lang') : '') || 'zh';
                applyLang(String(savedLang));
                // ask extension to override from workspace if present
                try { vscode.postMessage({ t: 'lang.get' }); } catch {}
              } catch {}
            } catch {}
          })();

          // ---- Helpers ----
          const tryCommandFallback = (cmdUri) => {
            try {
              const a = document.createElement('a');
              a.href = cmdUri;
              a.style.display = 'none';
              document.body.appendChild(a);
              setTimeout(()=>{ try { a.click(); } catch {} try { a.remove(); } catch {} }, 80);
            } catch {}
          };

          // ---- Beginner quick actions ----
          // 带命令兜底：消息通道异常时改走 command: URI
          try {
            const el = document.getElementById('btnSimpleInstall');
            if (el) el.onclick = () => { try { vscode.postMessage({ t: 'prepareEnvInstall' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.envPrepareInstall'); } catch {} };
          } catch {}
          try {
            const el = document.getElementById('btnSimpleCoverage');
            if (el) el.onclick = () => { try { vscode.postMessage({ t: 'coverage' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.loadCoverage'); } catch {} };
          } catch {}
          try {
            const el = document.getElementById('btnSimplePlan');
            if (el) el.onclick = () => { try { vscode.postMessage({ t: 'open', path: '.mcp/plan.md', line: 1 }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.openPlan'); } catch {} };
          } catch {}
          try {
            const el = document.getElementById('btnSimpleIngest');
            if (el) el.onclick = () => { try { vscode.postMessage({ t: 'ingestRules' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.ingestQuick'); } catch {} };
          } catch {}
          try {
            const el = document.getElementById('btnSimpleStatus');
            if (el) el.onclick = () => { try { vscode.postMessage({ t: 'statusUpdate' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.statusUpdate'); } catch {} };
          } catch {}
          // Event delegation fallback: ensure clicks still work even if nodes are re-rendered
          try {
            const clickMap = {
              'btnLicVerify': { t: 'licenseVerify' },
              'btnLicActivate': { t: 'licenseActivate' },
              // 这些按钮已带 command: 兜底，避免在此处拦截默认行为
              // 'btnSimpleInstall': { t: 'prepareEnvInstall' },
              // 'btnSimpleCoverage': { t: 'coverage' },
              // 'btnSimplePlan': { t: 'open', path: '.mcp/plan.md', line: 1 },
              // 'btnSimpleIngest': { t: 'ingestRules' },
              // 'btnSimpleStatus': { t: 'statusUpdate' },
              'btnEvents': { t: 'eventsLoad' },
              'btnAudit': { t: 'auditLoad' },
              'btnInfo': { t: 'statusInfo' },
            };
            document.addEventListener('click', (ev) => {
              try {
                const el = ev.target;
                if (!el || !el.id) return;
                const m = clickMap[el.id];
                // Post a generic click event for diagnostics
                try { vscode.postMessage({ t: 'panel.click', id: el.id }); } catch {}
                if (m) { ev.preventDefault(); vscode.postMessage(m); }
              } catch {}
            }, true);
          } catch {}
          try { const el = document.getElementById('btnLoad'); if (el) el.onclick = () => vscode.postMessage({ t: 'loadRules' }); } catch {}
          try { const el = document.getElementById('btnStatusUpdate'); if (el) el.onclick = () => { try { vscode.postMessage({ t: 'statusUpdate' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.statusUpdate'); } catch {} }; } catch {}
          try { const el = document.getElementById('btnSelectProject'); if (el) el.onclick = () => vscode.postMessage({ t: 'selectProject' }); } catch {}
          try { const el = document.getElementById('btnIngest'); if (el) el.onclick = () => vscode.postMessage({ t: 'ingestRules' }); } catch {}
          try { const el = document.getElementById('btnValidate'); if (el) el.onclick = () => vscode.postMessage({ t: 'validateRules' }); } catch {}
          // \u9884\u89c8\u5e76\u56de\u5199\u95e8\u7981\uff08rules.resolve\uff09
          const btnResolve = document.createElement('button'); btnResolve.id = 'btnRulesResolve'; btnResolve.textContent = '\u9884\u89c8\u5e76\u5e94\u7528\u95e8\u7981';
          const anchor = document.getElementById('btnValidate');
          if (anchor && anchor.parentElement) { anchor.parentElement.insertBefore(btnResolve, anchor.nextSibling); }
          btnResolve.onclick = () => vscode.postMessage({ t: 'rulesResolvePreview' });
          try { const el = document.getElementById('btnHooks'); if (el) el.onclick = () => vscode.postMessage({ t: 'installHooks' }); } catch {}
          try { const el = document.getElementById('btnLoadSugg'); if (el) el.onclick = () => vscode.postMessage({ t: 'loadSugg' }); } catch {}
          try { const el = document.getElementById('btnCoverage'); if (el) el.onclick = () => { try { vscode.postMessage({ t: 'coverage' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.loadCoverage'); } catch {} }; } catch {}
          try { const el = document.getElementById('btnCovTree'); if (el) el.onclick = () => vscode.postMessage({ t: 'coverageTree' }); } catch {}
          try { const el = document.getElementById('btnOpenWeakCsv'); if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/weak_top.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenNearCsv'); if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/near_top.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenGroupsCsv'); if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/groups.csv', line: 1 }); } catch {}
          try { const el = document.getElementById('btnOpenGroupsMd'); if (el) el.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/jb_groups.md', line: 1 }); } catch {}
          try { const el = document.getElementById('btnCovExport'); if (el) el.onclick = () => vscode.postMessage({ t: 'covExport' }); } catch {}
          document.getElementById('btnCopyCsvPreview').onclick = async () => {
            try {
              const el = document.getElementById('csvPreview');
              const text = (el && el.textContent) ? String(el.textContent) : '';
              if (text && navigator.clipboard) {
                await navigator.clipboard.writeText(text);
                vscode.postMessage({ t: 'info', text: '\u5df2\u590d\u5236 CSV \u9884\u89c8\u5230\u526a\u8d34\u677f' });
              }
            } catch {}
          };
          document.getElementById('btnCsvReload').onclick = () => {
            try {
              const sel = document.getElementById('csvSelect');
              const which = sel && sel.value ? sel.value : 'weak_top.csv';
              vscode.postMessage({ t: 'csvPreviewPick', which });
            } catch {}
          };
          const btnMd = document.createElement('button'); btnMd.id = 'btnCopyCsvAsMd'; btnMd.textContent = '\u590d\u5236\u4e3a Markdown \u8868\u683c';
          const weakBox = document.getElementById('covWeak');
          if (weakBox) { weakBox.parentElement?.insertBefore(btnMd, weakBox.nextSibling); }
          btnMd.onclick = async () => {
            try {
              const el = document.getElementById('csvPreview');
              const text = (el && el.textContent) ? String(el.textContent) : '';
              const lines = text.split('\\n').filter(Boolean);
              if (lines.length >= 2) {
                var head = lines[0] || '';
                if (head.startsWith('[')) {
                  var idx = head.indexOf(']');
                  if (idx > 0) head = head.substring(idx + 1).trim();
                }
                const data = lines.slice(1);
                const cols = (head.split(',').map(s=>s.trim()));
                const tbl = [
                  '| ' + cols.join(' | ') + ' |',
                  '| ' + cols.map(()=> '---').join(' | ') + ' |',
                  ...data.map(row => '| ' + row.split(',').map(s=>s.trim()).join(' | ') + ' |')
                ].join('\n');
                if (navigator.clipboard) {
                  await navigator.clipboard.writeText(tbl);
                  vscode.postMessage({ t: 'info', text: '\u5df2\u590d\u5236 Markdown \u8868\u683c\u5230\u526a\u8d34\u677f' });
                }
              }
            } catch {}
          };
          document.getElementById('btnIdeScaffold').onclick = () => vscode.postMessage({ t: 'ideScaffold' });
          document.getElementById('btnCompliance').onclick = () => vscode.postMessage({ t: 'compliance' });
          document.getElementById('btnOpenCompliance').onclick = () => vscode.postMessage({ t: 'openCompliance' });
          document.getElementById('btnOpenIdeDir').onclick = () => vscode.postMessage({ t: 'openIdeDir' });
          (document.getElementById('btnEvents')).onclick = () => vscode.postMessage({ t: 'eventsLoad' });
          document.getElementById('btnAudit').onclick = () => vscode.postMessage({ t: 'auditLoad' });
          const btnReload = document.getElementById('btnReloadPanel'); if (btnReload) btnReload.onclick = () => { try { vscode.postMessage({ t: 'panel.reload' }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.openPanel'); } catch {} };
          const btnDiagTop = document.getElementById('btnDiagTop'); if (btnDiagTop) btnDiagTop.onclick = () => { try { const errs = window.__panelErrors || []; vscode.postMessage({ t: 'panelDiagRequest', errors: errs }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.panelDiag'); } catch {} };
          const btnDiag = document.createElement('button'); btnDiag.id='btnDiag'; btnDiag.textContent='\u8bca\u65ad'; btnDiag.title='\u6536\u96c6\u524d\u7aef\u9519\u8bef\u3001\u73af\u5883\u4e0e\u5ba1\u8ba1\u4fe1\u606f\u5230 .mcp/dashboard/panel_diag.json';
          const advBar = document.querySelector('div.adv'); if (advBar) advBar.insertBefore(btnDiag, advBar.firstChild);
          btnDiag.onclick = () => { try { const errs = window.__panelErrors || []; vscode.postMessage({ t: 'panelDiagRequest', errors: errs }); } catch {} try { tryCommandFallback('command:mcpRulesAssistant.panelDiag'); } catch {} };
          const btnUG = document.getElementById('btnOpenUserGuide');
          if (btnUG) btnUG.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/USER_GUIDE.md' });
          const btnIS = document.getElementById('btnOpenIdeSupport');
          if (btnIS) btnIS.onclick = () => vscode.postMessage({ t: 'open', path: 'docs/IDE_SUPPORT.md' });
          document.getElementById('btnPrepareEnvInstall').onclick = () => vscode.postMessage({ t: 'prepareEnvInstall' });
          document.getElementById('btnOnboardPreview').onclick = () => vscode.postMessage({ t: 'onboardPreview' });
          document.getElementById('btnOnboardApply').onclick = () => vscode.postMessage({ t: 'onboardApply' });
          document.getElementById('btnChatEnable').onclick = () => vscode.postMessage({ t: 'chatEnable' });
          document.getElementById('btnChatDisable').onclick = () => vscode.postMessage({ t: 'chatDisable' });
          document.getElementById('btnChatPreview').onclick = () => vscode.postMessage({ t: 'chatPreview' });
          (document.getElementById('btnEvents')).onclick = () => vscode.postMessage({ t: 'eventsLoad' });
          document.getElementById('btnInfo').onclick = () => vscode.postMessage({ t: 'statusInfo' });
          document.getElementById('btnCopyEvents').onclick = async () => {
            try { const el = document.getElementById('events'); const t = (el && el.textContent) || ''; if (navigator.clipboard) { await navigator.clipboard.writeText(String(t)); vscode.postMessage({ t: 'info', text: '\u5df2\u590d\u5236\u4e8b\u4ef6\u5386\u53f2' }); } } catch {}
          };
          (document.getElementById('btnCopyInfo')).onclick = async () => {
            try { const el = document.getElementById('infolist'); const t = (el && el.textContent) || ''; if (navigator.clipboard) { await navigator.clipboard.writeText(String(t)); vscode.postMessage({ t: 'info', text: '\u5df2\u590d\u5236\u72b6\u6001\u6458\u8981' }); } } catch {}
          };
          (document.getElementById('btnOpenStatusFile')).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/status.json', line: 1 });
          (document.getElementById('btnOpenEventsFile')).onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/cmd_events.jsonl', line: 1 });
          const _btnAuditFile = document.getElementById('btnOpenAuditFile');
          if (_btnAuditFile) _btnAuditFile.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/dashboard/security_audit.jsonl', line: 1 });
          (document.getElementById('btnShowWeak')).onclick = () => {
            const all = window.__weakAll || [];
            const ulw = document.getElementById('covWeak');
            if (!ulw) return;
            while (ulw.firstChild) { ulw.removeChild(ulw.firstChild); }
            (all || []).forEach((w) => {
              const li = document.createElement('li');
              const a = document.createElement('a'); a.href = '#';
              a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% — ' + w.file;
              a.addEventListener('click', (ev)=>{ ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
              li.appendChild(a); ulw.appendChild(li);
            });
            const inf = document.getElementById('info'); if (inf) inf.textContent = '\u5f53\u524d\u89c6\u56fe\uff1a\u5f31\u9879';
          };
          (document.getElementById('btnCovNear')).onclick = async () => {
            const last = window.__nearPct || 3;
            // \u901a\u8fc7\u6269\u5c55\u4fa7\u83b7\u53d6\u8f93\u5165\u4e0e\u6570\u636e
            vscode.postMessage({ t: 'covNearPrompt', last });
          };
          (document.getElementById('btnCovNearInline')).onclick = () => {
            const ip = document.getElementById('nearPct');
            const v = parseInt((ip && ip.value) || '3', 10) || 3;
            window.__nearPct = v;
            try { vscode.setState && vscode.setState({ nearPct: v }); } catch {}
            try { localStorage.setItem('ruleflow.nearPct', String(v)); } catch {}
            try { vscode.postMessage({ t: 'saveNearPct', v }); } catch {}
            vscode.postMessage({ t: 'covNearPrompt', last: v });
          };
          const memBtn = document.createElement('button');
          memBtn.id = 'btnMemory'; memBtn.textContent = '\u52a0\u8f7d\u8bb0\u5fc6 / Load Memory';
          const planBtn = document.createElement('button');
          planBtn.id = 'btnPlan'; planBtn.textContent = '\u52a0\u8f7d\u8ba1\u5212 / Load Plan';
          const bar = document.querySelector('div[style*="margin:8px 0;"]');
          if (bar) { 
            bar.appendChild(memBtn); 
            bar.appendChild(planBtn);
            const btnOpenPlan = document.createElement('button'); btnOpenPlan.textContent = '\u5728\u7f16\u8f91\u5668\u6253\u5f00\u8ba1\u5212';
            const btnOpenMemory = document.createElement('button'); btnOpenMemory.textContent = '\u5728\u7f16\u8f91\u5668\u6253\u5f00\u8bb0\u5fc6';
            btnOpenPlan.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/plan.md', line: 1 });
            btnOpenMemory.onclick = () => vscode.postMessage({ t: 'open', path: '.mcp/memory.json', line: 1 });
            bar.appendChild(btnOpenPlan); bar.appendChild(btnOpenMemory);
          }
          memBtn.onclick = () => vscode.postMessage({ t: 'memory' });
          planBtn.onclick = () => vscode.postMessage({ t: 'plan' });
          // \u8bfb\u53d6 CI \u914d\u7f6e
          vscode.postMessage({ t: 'ciFetch' });
          vscode.postMessage({ t: 'ciCheck' });
          // \u7ed1\u5b9a CI \u64cd\u4f5c\u6309\u94ae
          (document.getElementById('btnCiSave')).onclick = () => {
            const had = document.getElementById('ciHadolint').checked;
            const img = document.getElementById('ciHadolintImage').value;
            const args = document.getElementById('ciHadolintArgs').value;
            const sem = document.getElementById('ciSemgrepConfig').value;
            const mutStrict = document.getElementById('ciMutGateStrict').checked;
            const execChecks = document.getElementById('execChecksDelegate').checked;
            vscode.postMessage({ t: 'ciSave', data: { hadolint: had, hadolint_image: img, hadolint_args: args, semgrep_config: sem, mutation_gate_strict: mutStrict, execution: { checks_delegate_run_cmd: execChecks } } });
          };
          (document.getElementById('btnCiGen')).onclick = () => vscode.postMessage({ t: 'ciGen' });
          (document.getElementById('btnCiPreview')).onclick = () => vscode.postMessage({ t: 'ciPreviewInline' });
          (document.getElementById('btnCiOpen')).onclick = () => vscode.postMessage({ t: 'ciOpen' });
          (document.getElementById('btnCiValidate')).onclick = () => vscode.postMessage({ t: 'ciValidate' });
          (document.getElementById('btnInsertRules')).onclick = () => vscode.postMessage({ t: 'insertSamples' });
          (document.getElementById('btnPrepareEnvDry')).onclick = () => vscode.postMessage({ t: 'prepareEnvDry' });
          const runNL = () => {
            const ip = document.getElementById('nlInput');
            const txt = (ip && ip.value || '').trim();
            if (!txt) return;
            vscode.postMessage({ t: 'nl', text: txt });
          };
          (document.getElementById('nlSend')).onclick = runNL;
          document.getElementById('nlInput').addEventListener('keydown', (ev) => { if (ev.key === 'Enter') runNL(); });
          (document.getElementById('nlExamples')).onclick = () => {
            const box = document.getElementById('nlExamplesBox'); if (!box) return;
            box.style.display = box.style.display === 'none' ? '' : 'none';
          };
          document.querySelectorAll('#nlExamplesBox button, #nlCatalog button').forEach((b)=>{
            b.addEventListener('click', ()=>{ const t=b.getAttribute('data-nl')||''; document.getElementById('nlInput').value=t; runNL(); });
          });
          const btnLicV = document.getElementById('btnLicVerify');
          const btnLicA = document.getElementById('btnLicActivate');
          if (btnLicV) btnLicV.onclick = () => vscode.postMessage({ t: 'licenseVerify' });
          if (btnLicA) btnLicA.onclick = () => vscode.postMessage({ t: 'licenseActivate' });
          const btnClr = document.getElementById('nlClear');
          if (btnClr) btnClr.onclick = () => { vscode.postMessage({ t: 'nlClearHistory' }); };
          vscode.postMessage({ t: 'nlFetchHistory' });

          // \u521d\u59cb\u5316 nearPct \u503c
          try {
            const st = vscode.getState && vscode.getState();
            const saved = (st && st.nearPct) || Number(localStorage.getItem('ruleflow.nearPct')||'0') || 0;
            if (saved) { window.__nearPct = saved; const ip = document.getElementById('nearPct'); if (ip) ip.value = String(saved); }
          } catch {}

          window.addEventListener('message', (e) => {
            const msg = e.data || {};
            if (msg.t === 'setLang') {
              try { const v = String(msg.value||'zh'); window.__ruleflowLang=v; } catch {}
              try { const applyLangFn = window.applyLang || null; if (applyLangFn) applyLangFn(window.__ruleflowLang); } catch {}
            }
            const setTicker = () => {
              const t = document.getElementById('tickerText');
              if (!t) return;
              const weakAll = window.__weakAll || [];
              const nearAll = window.__near || [];
              const topWeak = (weakAll || []).slice(0, 3).map((w)=> (w.coverage*100).toFixed(1) + '% ' + w.file);
              const topNear = (nearAll || []).slice(0, 3).map((n)=> (n.coverage*100).toFixed(1) + '% ' + n.file);
              const parts = [
                '\u5f31\u9879 ' + String(weakAll.length),
                '\u8fd1\u9608\u503c ' + String(nearAll.length),
                topWeak.length ? ('Top\u5f31\u9879: ' + topWeak.join(' | ')) : '',
                topNear.length ? ('Top\u8fd1\u9608\u503c: ' + topNear.join(' | ')) : ''
              ].filter(Boolean);
              t.textContent = parts.join('  ·  ');
            };
            if (msg.t === 'info') {
              const inf = document.getElementById('info');
              let text = String(msg.text || '');
              try {
                const lang = String(window.__ruleflowLang || 'zh');
                if (lang === 'en') {
                  const map = {
                    '\u672a\u627e\u5230\u8986\u76d6\u7387\u8d44\u6e90': 'No coverage resources found',
                    '\u8986\u76d6\u7387\u6458\u8981\u4e0d\u53ef\u7528': 'Coverage summary unavailable',
                    '\u72b6\u6001\u5df2\u5237\u65b0': 'Status refreshed',
                    '\u672a\u627e\u5230\u4e8b\u4ef6\u5386\u53f2': 'No event history found',
                    '\u672a\u627e\u5230\u7f16\u8bd1\u89c4\u5219': 'Compiled rules not found',
                    '\u68c0\u6d4b\u5230': 'Detected',
                    '\u5904\u89c4\u5219\u51b2\u7a81': 'rule conflicts',
                    '\u5efa\u8bae\u6570': 'suggestions',
                    'Onboard \u9884\u89c8\u5b8c\u6210': 'Onboard preview completed',
                    '\u76ee\u5f55\u6811\u4e0d\u53ef\u7528': 'Coverage tree unavailable',
                    '\u5df2\u5199\u5165\u8bca\u65ad': 'Diagnostics written',
                    '\u5df2\u5207\u6362\u5230\u4e2d\u6587': 'Switched to Chinese',
                    '\u8fd1\u9608\u503c\u6587\u4ef6': 'Near-threshold files',
                    '\u5f31\u9879': 'Weak items'
                  };
                  Object.keys(map).forEach(function(k){
                    try {
                      text = text.split(k).join(map[k]);
                    } catch (e) {}
                  });
                }
              } catch {}
              if (inf) inf.textContent = text;
              try { if (String(text).indexOf('handshake_ok') !== -1) { (window as any).__ruleflowHandshakeOk = true; } } catch {}
            }
            if (msg.t === 'rules') {
              document.getElementById('rules').textContent = msg.md || '\u6682\u65e0\u5185\u5bb9';
            }
            if (msg.t === 'tasks') {
              const pend = msg.pending || [];
              const done = msg.done || [];
              const up = document.getElementById('tasksPending');
              const ud = document.getElementById('tasksDone');
              if (up) { while (up.firstChild) { up.removeChild(up.firstChild); } pend.forEach((t)=>{ const li=document.createElement('li'); li.textContent=t; up.appendChild(li); }); }
              if (ud) { while (ud.firstChild) { ud.removeChild(ud.firstChild); } done.forEach((t)=>{ const li=document.createElement('li'); li.textContent=t; ud.appendChild(li); }); }
              const inf = document.getElementById('info');
              if (inf) inf.textContent = '\u4efb\u52a1\uff1a\u5269\u4f59 ' + String(pend.length) + '\uff0c\u5b8c\u6210 ' + String(done.length);
            }
            if (msg.t === 'sugg') {
              document.getElementById('sugg').textContent = msg.md || '\u6682\u65e0\u5efa\u8bae';
            }
            if (msg.t === 'covWeakAll') {
              window.__weakAll = msg.items || [];
              // \u81ea\u52a8\u6784\u5efa\u76ee\u5f55\u6811\uff08\u5f31\u9879\u6587\u4ef6\uff09
              const tree = document.getElementById('covTree');
              if (tree) {
                const all = window.__weakAll || [];
                // \u6784\u5efa prefix -> children \u7684\u6d45\u6811\uff08\u524d 3 \u5c42\uff09
                const root = {};
                (all || []).forEach((w) => {
                  const parts = String(w.file||'').split('/').slice(0, 3);
                  let node = root;
                  parts.forEach((p, i) => {
                    if (!p) return;
                    node.children = node.children || {};
                    node.children[p] = node.children[p] || {};
                    node = node.children[p];
                  });
                  node.files = node.files || [];
                  node.files.push(w);
                });
                const renderNode = (node, name, depth) => {
                  const li = document.createElement('li');
                  const title = document.createElement('span');
                  title.textContent = name;
                  title.style.cursor = 'pointer';
                  li.appendChild(title);
                  const weakFiles = (node.files||[]);
                  if (weakFiles.length) {
                    title.style.color = '#d33';
                    const ulFiles = document.createElement('ul');
                    weakFiles.forEach((w) => {
                      const lif = document.createElement('li');
                      const a = document.createElement('a'); a.href = '#'; a.style.color = '#d33';
                      a.textContent = (w.coverage*100).toFixed(1) + '% — ' + w.file;
                      a.onclick = (ev)=>{ ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); };
                      lif.appendChild(a); ulFiles.appendChild(lif);
                    });
                    li.appendChild(ulFiles);
                    title.onclick = () => {
                      const vis = ulFiles._collapsed;
                      ulFiles._collapsed = false;
                      ulFiles.style.display = vis ? '' : 'none';
                    };
                  }
                  if (node.children) {
                    const ul = document.createElement('ul');
                    ul._collapsed = false;
                    Object.keys(node.children).sort().forEach((k)=>{
                      ul.appendChild(renderNode(node.children[k], k, depth+1));
                    });
                    li.appendChild(ul);
                    title.onclick = () => {
                      const vis = ul._collapsed;
                      ul._collapsed = !vis;
                      ul.style.display = vis ? '' : 'none';
                    };
                  }
                  return li;
                };
                while (tree.firstChild) { tree.removeChild(tree.firstChild); }
                const ulRoot = document.createElement('ul');
                Object.keys(root.children||{}).sort().forEach((k)=>{
                  ulRoot.appendChild(renderNode(root.children[k], k, 0));
                });
                tree.appendChild(ulRoot);
              }
              // \u66f4\u65b0\u4fe1\u606f\u6761\uff08\u5f31\u9879/\u8fd1\u9608\u503c\u6570\u91cf\uff09
              const w = (msg.items || []).length;
              const n = (window.__near || []).length || 0;
              const inf = document.getElementById('info');
              if (inf) {
                const s = '\u5f31\u9879 ' + w + ' \u4e2a' + (n ? ('\uff1b\u8fd1\u9608\u503c ' + n + ' \u4e2a') : '');
                inf.textContent = s;
              }
            }
            if (msg.t === 'ci') {
              const cfg = msg.config || {}; const ci = cfg.ci || {};
              document.getElementById('ciHadolint').checked = !!ci.hadolint;
              document.getElementById('ciHadolintImage').value = ci.hadolint_image || '';
              document.getElementById('ciHadolintArgs').value = ci.hadolint_args || '';
              document.getElementById('ciSemgrepConfig').value = ci.semgrep_config || '';
              document.getElementById('ciMutGateStrict').checked = !!ci.mutation_gate_strict;
              try {
                const ex = cfg.execution || {};
                document.getElementById('execChecksDelegate').checked = !!ex.checks_delegate_run_cmd;
              } catch {}
              try {
                const perf = cfg.performance || {};
                const strict = String(perf.mode || '').toLowerCase() === 'strict' || !!ci.mutation_gate_strict;
                // Update status bar hint
                globalThis.__ruleflowStrict = strict;
                /* status bar is updated by extension host */
              } catch {}
            }
            if (msg.t === 'ciStatus') {
              const el = document.getElementById('ciStatus');
              if (el) el.textContent = msg.exist ? 'CI: \u5df2\u751f\u6210' : 'CI: \u672a\u751f\u6210';
              if (el) el.style.color = msg.exist ? '#2a2' : '#d33';
              try { vscode.postMessage({ t: 'ready2', topic: 'ciStatusReady' }); } catch {}
            }
            if (msg.t === 'ciPreviewContent') {
              const pv = document.getElementById('ciPreviewBox');
              if (pv) pv.textContent = msg.text || '';
              try { vscode.postMessage({ t: 'ready2', topic: 'ciPreviewReady' }); } catch {}
            }
            if (msg.t === 'ciChecks') {
              const ul = document.getElementById('ciChecks');
              if (ul) {
                while (ul.firstChild) { ul.removeChild(ul.firstChild); }
                const checks = msg.checks || {};
                const labels = { exists: '\u6587\u4ef6\u5b58\u5728', has_precommit: 'Pre-commit \u626b\u63cf', has_hadolint: 'Hadolint \u68c0\u67e5', has_semgrep: 'Semgrep \u626b\u63cf', has_tests: 'Pytest + \u8986\u76d6\u7387', has_bandit: 'Bandit \u626b\u63cf' };
                Object.keys(labels).forEach((k) => {
                  const li = document.createElement('li');
                  li.textContent = labels[k] + '：' + (checks[k] ? '✔' : '✘');
                  li.style.color = checks[k] ? '#2a2' : '#d33';
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'covGroups') {
              const ul = document.getElementById('covGroups');
              if (ul) {
                while (ul.firstChild) { ul.removeChild(ul.firstChild); }
                (msg.items || []).forEach((g) => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.textContent = String(g.prefix) + ': ' + (g.coverage*100).toFixed(1) + '% < ' + Math.round((g.threshold||0)*100) + '% \u2014 \u5f31\u9879 ' + g.weak_count + '/' + g.files_count;
                  a.style.color = (g.coverage < g.threshold) ? '#d33' : '#2a2';
                  a.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    const all = window.__weakAll || [];
                    const filtered = g.prefix === 'other' ? all : all.filter((w)=> (w.file||'').startsWith(g.prefix));
                    const ulw = document.getElementById('covWeak');
                    if (ulw) {
                      while (ulw.firstChild) { ulw.removeChild(ulw.firstChild); }
                      (filtered || []).forEach((w) => {
                        const li2 = document.createElement('li');
                        const a2 = document.createElement('a');
                        a2.href = '#';
                        a2.textContent = (w.coverage*100).toFixed(1) + '% — ' + w.file;
                        a2.style.color = '#d33';
                        a2.addEventListener('click', (ev2) => { ev2.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                        li2.appendChild(a2);
                        ulw.appendChild(li2);
                      });
                    }
                  });
                  li.appendChild(a);
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'suggestIngest') {
              const bar = document.querySelector('div[style*="margin:8px 0;"]');
              if (bar && !document.getElementById('btnQuickIngest')) {
                const qi = document.createElement('button');
                qi.id = 'btnQuickIngest';
                qi.textContent = '\u5feb\u901f\u6444\u53d6 / Quick Ingest';
                (qi).onclick = () => vscode.postMessage({ t: 'ingestRules' });
                bar.appendChild(qi);
              }
            }
            if (msg.t === 'covNear') {
              window.__near = msg.items || [];
              const n = (msg.items || []).length;
              const w = (window.__weakAll || []).length || 0;
              const s = (w ? ('\u5f31\u9879 ' + w + ' \u4e2a\uff1b') : '') + '\u8fd1\u9608\u503c ' + n + ' \u4e2a\uff08\u22643%\uff09';
              const inf = document.getElementById('info'); if (inf) inf.textContent = s;
              setTicker();
            }
            if (msg.t === 'covTreeData') {
              const container = document.getElementById('covTree');
              if (container) {
                while (container.firstChild) { container.removeChild(container.firstChild); }
                const renderNode = (node) => {
                  const li = document.createElement('li');
                  const title = document.createElement('span');
                  title.textContent = String(node.name || '');
                  title.style.cursor = 'pointer';
                  li.appendChild(title);
                  const files = node.files || [];
                  if (files.length) {
                    const uf = document.createElement('ul');
                    files.forEach((w) => {
                      const lif = document.createElement('li');
                      const a = document.createElement('a');
                      a.href = '#'; a.style.color = '#d33';
                      a.textContent = ((w.coverage||0)*100).toFixed(1) + '% \u2014 ' + w.file;
                      a.addEventListener('click', (ev) => { ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                      lif.appendChild(a); uf.appendChild(lif);
                    });
                    li.appendChild(uf);
                  }
                  const children = node.children || {};
                  const keys = Object.keys(children);
                  if (keys.length) {
                    const ul2 = document.createElement('ul');
                    keys.sort().forEach((k) => ul2.appendChild(renderNode(children[k])));
                    li.appendChild(ul2);
                  }
                  return li;
                };
                const ulRoot = document.createElement('ul');
                const tree = msg.tree || { children: {} };
                Object.keys(tree.children || {}).sort().forEach((k) => ulRoot.appendChild(renderNode(tree.children[k])));
                container.appendChild(ulRoot);
              }
            }
            if (msg.t === 'conflicts') {
              const ul = document.getElementById('conflicts');
              if (ul) {
                while (ul.firstChild) { ul.removeChild(ul.firstChild); }
                (msg.items || []).forEach((c) => {
                  const li = document.createElement('li');
                  const key = c.key;
                  const sources = c.sources || [];
                  li.textContent = key + ': ';
                  sources.forEach((s, i) => {
                    const a = document.createElement('a');
                    a.href = '#';
                    a.textContent = (s.file || '') + ':' + (s.line || 1);
                    a.addEventListener('click', (ev) => {
                      ev.preventDefault();
                      vscode.postMessage({ t: 'open', path: s.file, line: s.line });
                    });
                    li.appendChild(a);
                    if (i < sources.length - 1) li.appendChild(document.createTextNode(' | '));
                  });
                  ul.appendChild(li);
                });
              }
            }
            if (msg.t === 'covWeak') {
              const ul = document.getElementById('covWeak');
              if (ul) {
                while (ul.firstChild) { ul.removeChild(ul.firstChild); }
                (msg.items || []).forEach((w) => {
                  const li = document.createElement('li');
                  const a = document.createElement('a');
                  a.href = '#';
                  a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% \u2014 ' + w.file;
                  a.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    vscode.postMessage({ t: 'open', path: w.file, line: 1 });
                  });
                  li.appendChild(a);
                  ul.appendChild(li);
                });
                const filterBtn = document.getElementById('btnCovFilter');
                const filterInput = document.getElementById('covFilter');
                if (filterBtn && filterInput) {
                  filterBtn.onclick = () => {
                    const kw = (filterInput.value || '').toLowerCase();
                    const all = window.__weakAll || [];
                    const filtered = kw ? all.filter((w)=> String(w.file||'').toLowerCase().includes(kw)) : all;
                    // \u76f4\u63a5\u91cd\u7ed8\u5217\u8868\uff08\u4e0d\u4f9d\u8d56\u6269\u5c55\u6d88\u606f\uff09
                    while (ul.firstChild) { ul.removeChild(ul.firstChild); }
                    (filtered || []).forEach((w) => {
                      const li = document.createElement('li');
                      const a = document.createElement('a');
                      a.href = '#';
                      a.textContent = (w.coverage*100).toFixed(1) + '% < ' + Math.round((w.threshold||0)*100) + '% \u2014 ' + w.file;
                      a.addEventListener('click', (ev) => { ev.preventDefault(); vscode.postMessage({ t: 'open', path: w.file, line: 1 }); });
                      li.appendChild(a);
                      ul.appendChild(li);
                    });
                  };
                }
                // store for ticker
                window.__weakAll = msg.items || [];
                setTicker();
              }
            }
            if (msg.t === 'memory') {
              document.getElementById('memory').textContent = msg.text || '';
            }
            if (msg.t === 'events') {
              const el = document.getElementById('events');
              if (el) el.textContent = String(msg.text || '');
            }
            if (msg.t === 'plan') {
              document.getElementById('plan').textContent = msg.text || '';
            }
            if (msg.t === 'infoList') {
              const pre = document.getElementById('infolist');
              pre.textContent = (Array.isArray(msg.items) ? msg.items : []).join('\n');
            }
            if (msg.t === 'ci') {
              const cfg = msg.config || {}; const ci = cfg.ci || {};
              document.getElementById('ciHadolint').checked = !!ci.hadolint;
              document.getElementById('ciHadolintImage').value = ci.hadolint_image || '';
              document.getElementById('ciHadolintArgs').value = ci.hadolint_args || '';
              document.getElementById('ciSemgrepConfig').value = ci.semgrep_config || '';
            }
            if (msg.t === 'ciStatus') {
              const el = document.getElementById('ciStatus');
              if (el) el.textContent = msg.exist ? 'CI: \u5df2\u751f\u6210' : 'CI: \u672a\u751f\u6210';
              if (el) el.style.color = msg.exist ? '#2a2' : '#d33';
            }
            if (msg.t === 'license') {
              const L = msg.license || {}; const el = document.getElementById('licText');
              const ok = !!L.ok; const activated = !!L.activated; const sig = !!L.signature_ok; const dateok = !!L.date_ok; const exp = L.expires || '';
              let label = 'Missing'; let color = '#d33';
              if (activated && !ok) { label = 'Invalid'; }
              if (activated && ok && !dateok) { label = 'Expired'; }
              if (activated && ok && dateok) { label = 'Valid'; color = '#2a2'; }
              if (el) { el.textContent = label + (exp ? (' (expires ' + exp + ')') : ''); try { el.style.color = color; } catch {} }
              const det = document.getElementById('licDetail');
              if (det) { try { det.textContent = JSON.stringify(L, null, 2); det.style.display = 'block'; } catch { try { det.textContent=''; det.style.display='none'; } catch {} } }
            }
            try { vscode.postMessage({ t: 'ready2', topic: String(msg.t||'any') }); } catch {}
        });
        </script>
      </body></html>`;
    /* c8 ignore stop */

    try {
      client.start(context);
      await client.request('initialize', {});
      const tools = await client.request('tools/list', {});
      const list = (tools.tools || []).map((t: any) => `<li><code>${t.name}</code> \u2014 ${t.description}</li>`).join('');
      const csp = panel.webview.cspSource;
      const scriptUri = panel.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'media', 'panel_bootstrap.js'));
      let html = render(csp, nonce, '', list);
      html = html.replace('@@PANEL_BOOTSTRAP@@', String(scriptUri));
      panel.webview.html = html;
      // Apply persisted language preference from workspace (shared across windows)
      try {
        const ws = getWorkspaceRoot();
        if (ws) {
          const uri = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
          let lang = 'zh';
          try {
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            const obj = JSON.parse(text || '{}');
            if (obj && typeof obj.lang === 'string' && obj.lang) lang = obj.lang;
          } catch { /* missing is fine */ }
          try { panel.webview.postMessage({ t: 'setLang', value: lang }); } catch {}
        }
      } catch { /* ignore */ }
      try {
        panel.webview.postMessage({ t: 'project', name: getWorkspaceLabel() });
        const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
        panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
        // \u7f3a\u5c11\u5de5\u5177\u6216 venv \u65f6\uff0c\u63d0\u793a\u4e00\u952e\u51c6\u5907\u73af\u5883
        const toolsMap = (diag && (diag as any).tools) || {};
        const missing: string[] = [];
        ['pytest', 'pre-commit', 'ruff', 'mypy', 'bandit'].forEach(k => { if (!toolsMap[k]) missing.push(k); });
        let venvMissing = false;
        try {
          const ws = getWorkspaceRoot();
          if (ws) {
            const uri = vscode.Uri.file(ws + '/.mcp/venv');
            await vscode.workspace.fs.stat(uri).then(()=>{}, ()=>{ venvMissing = true; });
          }
        } catch { venvMissing = true; }
        if ((venvMissing || missing.length) && (process.env.RULEFLOW_TEST_FAKE || '') !== '1') {
          panel.webview.postMessage({ t: 'info', text: `\u68c0\u6d4b\u5230\u5f00\u53d1\u73af\u5883\u4e0d\u5b8c\u6574\uff08venv: ${venvMissing ? '\u7f3a\u5931' : '\u5b58\u5728'}\uff1b\u7f3a\u5c11\u5de5\u5177: ${missing.join(', ') || '\u65e0'}\uff09\u3002\u5efa\u8bae\u70b9\u51fb\u201c\u51c6\u5907\u5e76\u5b89\u88c5\u73af\u5883\u201d\u3002` });
          const pick = await vscode.window.showInformationMessage('\u68c0\u6d4b\u5230\u7f3a\u5c11\u5f00\u53d1\u73af\u5883\uff0c\u662f\u5426\u4e00\u952e\u521b\u5efa\u5e76\u5b89\u88c5\u57fa\u7840\u5de5\u5177\uff1f', '\u7acb\u5373\u521b\u5efa', '\u7a0d\u540e');
          if (pick === '\u7acb\u5373\u521b\u5efa') {
            try {
              await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
              vscode.window.showInformationMessage('\u5df2\u521b\u5efa\u5e76\u5b89\u88c5\u57fa\u7840\u73af\u5883 (.mcp/venv)\u3002');
            } catch (e:any) {
              vscode.window.showErrorMessage('\u521b\u5efa\u73af\u5883\u5931\u8d25\uff1a' + String(e));
            }
          }
        }
      } catch {}
    } catch (e: any) {
      panel.webview.html = renderFallback('\u8fde\u63a5 MCP \u5931\u8d25\uff1a' + String(e));
    }

    const __panelDispatch = async (msg: any) => {
      // mark in-flight for tests to await idle
      try { __panelInFlight = new Promise<void>((res)=>{ __panelInFlightResolve = res; }); } catch {}
      try {
        __testWebviewHandler = async (m:any) => { await handleOpenMessage(m); };
        if (msg.t === 'retryConnect') {
          try { client.start(context); } catch {}
          vscode.window.setStatusBarMessage('\u6b63\u5728\u5c1d\u8bd5\u91cd\u65b0\u8fde\u63a5 MCP\u2026', 2000);
        }
        else if (msg.t === 'enableFake') {
          try {
            const ws = getWorkspaceRoot() || process.cwd();
            const dash = path.join(ws, '.mcp', 'dashboard');
            fs.mkdirSync(dash, { recursive: true });
            fs.writeFileSync(path.join(dash, 'fake_mode'), '1');
            vscode.window.showInformationMessage('\u5df2\u5207\u6362\u4e3a\u6f14\u793a\u6a21\u5f0f\uff08fake\uff09\u3002');
            (client as any).fakeMode = true; // best-effort
            await vscode.commands.executeCommand('mcpRulesAssistant.openPanel');
            return;
          } catch (e:any) {
            vscode.window.showErrorMessage('\u5207\u6362\u6f14\u793a\u6a21\u5f0f\u5931\u8d25\uff1a' + String(e));
          }
        }
        else if (msg.t === 'handshake') {
          try { panel.webview.postMessage({ t: 'info', text: 'Webview \u5df2\u8fde\u63a5\uff08handshake_ok\uff09' }); } catch {}
        }
        else if (msg.t === 'panel.click') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/dashboard/panel_clicks.jsonl');
            const enc = new TextEncoder();
            const line = JSON.stringify({ time: new Date().toISOString(), id: String(msg.id||''), type: 'panel.click' }) + '\n';
            try {
              let old = '';
              try { const b = await vscode.workspace.fs.readFile(p); old = Buffer.from(b).toString('utf8'); } catch {}
              await vscode.workspace.fs.writeFile(p, enc.encode(old + line));
            } catch { await vscode.workspace.fs.writeFile(p, enc.encode(line)); }
          } catch {}
        }
        else if (msg.t === 'openServerLog') {
          try {
            const ws = getWorkspaceRoot();
            if (!ws) { vscode.window.showInformationMessage('No workspace'); return; }
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/server.log');
            await vscode.workspace.fs.stat(uri);
            const doc = await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch { vscode.window.showInformationMessage('\u672a\u627e\u5230 .mcp/dashboard/server.log'); }
        }
        else if (msg.t === 'panelDiagRequest') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const errs = Array.isArray(msg.errors) ? (msg.errors as any[]).slice(-100) : [];
            const diag: any = { time: new Date().toISOString(), workspace: ws, strict: String(process.env.MCP_STRICT_ISOLATION||''), projectRootEnv: String(process.env.MCP_PROJECT_ROOT||'') };
            try { const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant'); diag.version = (ext && (ext.packageJSON as any).version) || ''; } catch {}
            try { diag.env = await client.request('tools/call', { name: 'env.diagnose', arguments: {} }); } catch {}
            try { diag.audit = await client.request('tools/call', { name: 'security.audit_report', arguments: {} }); } catch {}
            try {
              const uriE = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
              const data = await vscode.workspace.fs.readFile(uriE);
              const text = Buffer.from(data).toString('utf8');
              const lines = text.split(/\r?\n/).filter(Boolean); diag.events_tail = lines.slice(-120);
            } catch {}
            diag.frontend_errors = errs;
            const outUri = vscode.Uri.file(ws + '/.mcp/dashboard/panel_diag.json');
            const enc = new TextEncoder();
            await vscode.workspace.fs.writeFile(outUri, enc.encode(JSON.stringify(diag, null, 2)));
            try { const doc = await vscode.workspace.openTextDocument(outUri); await vscode.window.showTextDocument(doc, { preview: false }); } catch {}
            panel.webview.postMessage({ t: 'info', text: '\u5df2\u5199\u5165\u8bca\u65ad\uff1a.mcp/dashboard/panel_diag.json' });
          } catch (e:any) {
            vscode.window.showWarningMessage('\u751f\u6210\u8bca\u65ad\u5931\u8d25\uff1a' + String(e));
          }
        }
        else if (msg.t === 'lang.set') {
          try {
            const lang = String(msg.value || 'zh');
            const ws = getWorkspaceRoot(); if (!ws) return;
            const dash = vscode.Uri.file(ws + '/.mcp/dashboard');
            try { await vscode.workspace.fs.createDirectory(dash); } catch {}
            const p = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
            const enc = new TextEncoder();
            await vscode.workspace.fs.writeFile(p, enc.encode(JSON.stringify({ lang }, null, 2)));
          } catch {}
        }
        else if (msg.t === 'lang.get') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
            const data = await vscode.workspace.fs.readFile(p);
            const text = Buffer.from(data).toString('utf8');
            const obj = JSON.parse(text || '{}');
            const lang = (obj && typeof obj.lang === 'string' && obj.lang) ? obj.lang : 'zh';
            panel.webview.postMessage({ t: 'setLang', value: lang });
          } catch {
            panel.webview.postMessage({ t: 'setLang', value: 'zh' });
          }
        }
        else if (msg.t === 'statusUpdate') {
          // Use the same interpreter resolution as commands, and ensure venv bin is on PATH
          const cwd = getWorkspaceRoot() || process.cwd();
          const pyBin = resolveProjectPython();
          const venvBin = process.platform === 'win32'
            ? path.join(cwd, '.mcp', 'venv', 'Scripts')
            : path.join(cwd, '.mcp', 'venv', 'bin');
          const env = { ...process.env } as NodeJS.ProcessEnv;
          try {
            const oldPath = String(process.env.PATH || '');
            env.PATH = (fs.existsSync(venvBin) ? (venvBin + path.delimiter) : '') + oldPath;
          } catch { /* ignore PATH injection errors */ }
          execFile(pyBin, ['-m', 'mcp_rules_assistant.cli', 'status-update', '--json'], { cwd, env }, (err: any, stdout: string, stderr: string) => {
            if (err) {
              vscode.window.showErrorMessage('\u72b6\u6001\u5237\u65b0\u5931\u8d25\uff1a' + String(err));
              return;
            }
            try {
              const data = JSON.parse(stdout || '{}');
              panel.webview.postMessage({ t: 'info', text: '\u72b6\u6001\u5df2\u5237\u65b0\u3002\u5f31\u9879\uff1a' + (((data.coverage||{}).weak||[]).length || 0) });
              const tk = (data.tasks||{});
              panel.webview.postMessage({ t: 'tasks', pending: tk.pending || [], done: tk.done || [] });
            } catch (e) {
              vscode.window.showInformationMessage('\u72b6\u6001\u5df2\u5237\u65b0');
            }
          });
          return;
        }
        if (msg.t === 'loadRules') {
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (!compiledUri) {
            panel.webview.postMessage({ t: 'rules', md: '\u672a\u627e\u5230\u89c4\u5219\u8d44\u6e90\uff0c\u8bf7\u5148\u201c\u6444\u53d6\u89c4\u5219\u201d' });
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u7f16\u8bd1\u89c4\u5219\uff0c\u8bf7\u70b9\u51fb\u201c\u6444\u53d6\u89c4\u5219 / Ingest\u201d\u8fdb\u884c\u6444\u53d6\u3002' });
            panel.webview.postMessage({ t: 'suggestIngest' });
            return;
          }
          const res = await client.request('resources/read', { uri: compiledUri });
          panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            const data = JSON.parse(compiled.text || '{}');
            panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
            try {
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              if (n > 0) {
                panel.webview.postMessage({ t: 'info', text: `\u68c0\u6d4b\u5230 ${n} \u5904\u89c4\u5219\u51b2\u7a81\uff0c\u5df2\u5728\u4e0b\u65b9\u5217\u51fa\u3002\u5efa\u8bae\u6570\uff1a${m}` });
              } else {
                panel.webview.postMessage({ t: 'info', text: `\u672a\u68c0\u6d4b\u5230\u89c4\u5219\u51b2\u7a81\u3002\u5efa\u8bae\u6570\uff1a${m}` });
              }
            } catch {}
          }
        } else if (msg.t === 'rulesResolvePreview') {
          try {
            const resList = await client.request('resources/list', {});
            const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
            if (!jsonUri) { vscode.window.showWarningMessage('\u672a\u627e\u5230\u7f16\u8bd1\u89c4\u5219\uff0c\u8bf7\u5148\u6444\u53d6\u89c4\u5219'); return; }
            const compiled = await client.request('resources/read', { uri: jsonUri });
            const data = JSON.parse(compiled.text || '{}');
            const pol = data.policy || {};
            const minMod = pol['coverage.min_module'];
            const minCore = pol['coverage.min_core'];
            const wantHadolint = !!(pol['container.required'] || pol['container.policy.baseline']);
            const wantSemgrep = !!pol['security.sast_strict'];
            const conflicts = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
            const sugg = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
            const lines: string[] = [];
            if (typeof minMod === 'number') lines.push(`coverage.min_module = ${(minMod*100).toFixed(0)}%`);
            if (typeof minCore === 'number') lines.push(`coverage.min_core = ${(minCore*100).toFixed(0)}%`);
            if (wantHadolint) lines.push('ci.hadolint = true');
            if (wantSemgrep) lines.push('ci.semgrep_config = auto');
            lines.push(`conflicts = ${conflicts}; suggestions = ${sugg}`);
            const confirm = await vscode.window.showInformationMessage('\u5c06\u5e94\u7528\u4ee5\u4e0b\u95e8\u7981\u5230\u914d\u7f6e:\n' + lines.join('\n'), { modal: true }, '\u5e94\u7528', '\u53d6\u6d88');
            if (confirm === '\u5e94\u7528') {
              const out = await client.request('tools/call', { name: 'rules.resolve', arguments: {} });
              const changed = out && out.changed;
              const enforced = (out && out.enforced) || [];
              const summary = `\u95e8\u7981\u5df2\u5e94\u7528\uff1a${changed? '\u914d\u7f6e\u5df2\u66f4\u65b0' : '\u65e0\u53d8\u5316'}\uff1b` + (Array.isArray(enforced)? enforced.join(', ') : '');
              vscode.window.showInformationMessage(summary);
              try { panel.webview.postMessage({ t: 'info', text: summary }); } catch {}
            }
          } catch (e:any) {
            vscode.window.showErrorMessage('\u9884\u89c8\u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'coverage') {
          // Quick combined report for toast summary
          let weakCount = 0, groupsCount = 0, nearCount = 0; let minModule: number | undefined = undefined;
          try {
            const rep = await client.request('tools/call', { name: 'coverage.report', arguments: {} });
            if (rep && rep.ok) {
              weakCount = Array.isArray(rep.weak) ? rep.weak.length : 0;
              groupsCount = Array.isArray(rep.groups) ? rep.groups.length : 0;
              nearCount = Array.isArray(rep.near) ? rep.near.length : 0;
              if (typeof rep.min_module === 'number') minModule = rep.min_module;
            }
          } catch {}
          const resList = await client.request('resources/list', {});
          const covUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/summary'))?.uri;
          const groupsUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/groups'))?.uri;
          const treeUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/tree'))?.uri;
          const nearUri = (resList.resources || []).find((r:any)=> String(r.uri||'').endsWith('/near'))?.uri;
          if (!covUri) {
            vscode.window.showWarningMessage('\u672a\u627e\u5230\u8986\u76d6\u7387\u8d44\u6e90\uff0c\u8bf7\u5148\u5728\u63a8\u9001/CI \u751f\u6210 coverage.xml');
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u8986\u76d6\u7387\u8d44\u6e90\uff0c\u8bf7\u5148\u8fd0\u884c pytest \u751f\u6210 coverage.xml\uff08\u6216\u5728 CI \u63a8\u9001\u751f\u6210\uff09\u3002' });
            return;
          }
          const res = await client.request('resources/read', { uri: covUri });
          const data = JSON.parse(res.text || '{}');
          if (!data.ok) {
            vscode.window.showWarningMessage(data.message || '\u672a\u627e\u5230 coverage.xml\uff0c\u8bf7\u5148\u5728\u63a8\u9001/CI \u751f\u6210');
            panel.webview.postMessage({ t: 'info', text: data.message || '\u8986\u76d6\u7387\u6458\u8981\u4e0d\u53ef\u7528\uff0c\u8bf7\u751f\u6210 coverage.xml' });
          } else {
            panel.webview.postMessage({ t: 'covWeakAll', items: data.weak || [] });
            panel.webview.postMessage({ t: 'covWeak', items: data.weak || [] });
            const wcnt = (data.weak || []).length;
            panel.webview.postMessage({ t: 'info', text: `\u5f31\u9879 ${wcnt} \u4e2a` });
          }
          if (groupsUri) {
            const gres = await client.request('resources/read', { uri: groupsUri });
            const gdata = JSON.parse(gres.text || '{}');
            if (gdata.ok) {
              panel.webview.postMessage({ t: 'covGroups', items: gdata.groups || [] });
            }
          }
          if (treeUri) {
            try {
              const tres = await client.request('resources/read', { uri: treeUri });
              const tdata = JSON.parse((tres as any).text || '{}');
              if (tdata.ok) {
                panel.webview.postMessage({ t: 'covTreeData', tree: tdata.tree || { name: '/', children: {} } });
              }
            } catch {}
          }
          if (nearUri) {
            try {
              const nres = await client.request('resources/read', { uri: nearUri });
              const ndata = JSON.parse((nres as any).text || '{}');
              if (ndata.ok) {
                const items = ndata.near || [];
                panel.webview.postMessage({ t: 'covNear', items });
                const n = Array.isArray(items) ? items.length : 0;
                panel.webview.postMessage({ t: 'info', text: `\u8fd1\u9608\u503c\u6587\u4ef6\uff1a${n} \u4e2a\uff08\u22643%\uff09` });
              }
            } catch {}
          }
          // Toast summary for panel action (align with VS Code command behavior)
          try {
            const parts: string[] = [`weak=${weakCount}`, `near=${nearCount}`, `groups=${groupsCount}`];
            if (typeof minModule === 'number') parts.push(`min_module=${(minModule*100).toFixed(0)}%`);
            vscode.window.showInformationMessage('Coverage loaded: ' + parts.join(', '));
            try { await updateStatusBar(); } catch {}
            try {
              const content = 'Coverage loaded: ' + parts.join(', ');
              if (memAllowed()) {
                await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'panel.coverage' } } });
              }
            } catch {}
          } catch {}
        } else if (msg.t === 'panel.reload') {
          try {
            client.start(context);
            try { await client.request('initialize', {}); } catch {}
            const tools = await client.request('tools/list', {});
            const list = (tools.tools || []).map((t: any) => `<li><code>${t.name}</code> — ${t.description}</li>`).join('');
            const nonce2 = getNonce();
            {
              const scriptUri2 = panel.webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'media', 'panel_bootstrap.js'));
              let html2 = render(csp, nonce2, '', list);
              html2 = html2.replace('@@PANEL_BOOTSTRAP@@', String(scriptUri2));
              panel.webview.html = html2;
            }
            // re-apply workspace language preference after reload
            try {
              const ws = getWorkspaceRoot();
              if (ws) {
                const uri = vscode.Uri.file(ws + '/.mcp/dashboard/ui_prefs.json');
                try {
                  const data = await vscode.workspace.fs.readFile(uri);
                  const text = Buffer.from(data).toString('utf8');
                  const obj = JSON.parse(text || '{}');
                  const lang = (obj && typeof obj.lang === 'string' && obj.lang) ? obj.lang : 'zh';
                  try { panel.webview.postMessage({ t: 'setLang', value: lang }); } catch {}
                } catch { /* ignore */ }
              }
            } catch {}
            vscode.window.setStatusBarMessage('Panel reloaded', 2000);
          } catch (e:any) {
            vscode.window.showWarningMessage('\u91cd\u8f7d\u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'coverageTree') {
          const resList = await client.request('resources/list', {});
          const treeUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/tree'))?.uri;
          if (!treeUri) {
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u76ee\u5f55\u6811\u8d44\u6e90\uff0c\u8bf7\u5148\u751f\u6210 coverage.xml \u6216\u70b9\u51fb\u201c\u52a0\u8f7d\u8986\u76d6\u7387\u201d\u3002' });
            return;
          }
          const tres = await client.request('resources/read', { uri: treeUri });
          try {
            const data = JSON.parse((tres as any).text || '{}');
            if (!data.ok) {
              panel.webview.postMessage({ t: 'info', text: '\u76ee\u5f55\u6811\u4e0d\u53ef\u7528\uff0c\u8bf7\u5148\u751f\u6210 coverage.xml\u3002' });
              return;
            }
            panel.webview.postMessage({ t: 'covTreeData', tree: data.tree || { name: '/', children: {} } });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '\u89e3\u6790\u76ee\u5f55\u6811\u5931\u8d25\u3002' });
          }
        } else if (msg.t === 'ingestRules') {
          const pathsInput = await vscode.window.showInputBox({
            title: '\u8f93\u5165\u8981\u6444\u53d6\u7684\u6587\u4ef6\u6216\u76ee\u5f55\uff08\u9017\u53f7\u5206\u9694\uff09',
            placeHolder: '\u5982\uff1arules.md, docs/rules',
          });
          if (!pathsInput) return;
          const paths = pathsInput.split(',').map(s => s.trim()).filter(Boolean);
          await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } });
          vscode.window.setStatusBarMessage('\u89c4\u5219\u6444\u53d6\u5b8c\u6210', 3000);
          // \u81ea\u52a8\u5237\u65b0
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (compiledUri) {
            const res = await client.request('resources/read', { uri: compiledUri });
            panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          }
          if (suggUri) {
            const sug = await client.request('resources/read', { uri: suggUri });
            panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
          }
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            try {
              const data = JSON.parse(((compiled as any).text) || '{}');
              panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              panel.webview.postMessage({ t: 'info', text: (n > 0) ? `\u68c0\u6d4b\u5230 ${n} \u5904\u89c4\u5219\u51b2\u7a81\uff0c\u5df2\u5728\u4e0b\u65b9\u5217\u51fa\u3002\u5efa\u8bae\u6570\uff1a${m}` : `\u672a\u68c0\u6d4b\u5230\u89c4\u5219\u51b2\u7a81\u3002\u5efa\u8bae\u6570\uff1a${m}` });
            } catch {
              panel.webview.postMessage({ t: 'info', text: '\u89e3\u6790\u89c4\u5219 JSON \u5931\u8d25\u3002' });
            }
          }
        } else if (msg.t === 'validateRules') {
          await client.request('tools/call', { name: 'rules.validate', arguments: {} });
          vscode.window.setStatusBarMessage('\u89c4\u5219\u6821\u9a8c\u5b8c\u6210', 3000);
          const resList = await client.request('resources/list', {});
          const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          const jsonUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled.json'))?.uri;
          if (compiledUri) {
            const res = await client.request('resources/read', { uri: compiledUri });
            panel.webview.postMessage({ t: 'rules', md: res.text || '' });
          }
          if (suggUri) {
            const sug = await client.request('resources/read', { uri: suggUri });
            panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
          }
          if (jsonUri) {
            const compiled = await client.request('resources/read', { uri: jsonUri });
            try {
              const data = JSON.parse(((compiled as any).text) || '{}');
              panel.webview.postMessage({ t: 'conflicts', items: data.conflicts || [] });
              const n = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
              const m = Array.isArray(data.suggestions) ? data.suggestions.length : 0;
              panel.webview.postMessage({ t: 'info', text: (n > 0) ? `\u68c0\u6d4b\u5230 ${n} \u5904\u89c4\u5219\u51b2\u7a81\uff0c\u5df2\u5728\u4e0b\u65b9\u5217\u51fa\u3002\u5efa\u8bae\u6570\uff1a${m}` : `\u672a\u68c0\u6d4b\u5230\u89c4\u5219\u51b2\u7a81\u3002\u5efa\u8bae\u6570\uff1a${m}` });
            } catch {
              panel.webview.postMessage({ t: 'info', text: '\u89e3\u6790\u89c4\u5219 JSON \u5931\u8d25\u3002' });
            }
          }
        } else if (msg.t === 'covExport') {
          try {
            const out = await client.request('tools/call', { name: 'coverage.export', arguments: {} });
            vscode.window.showInformationMessage('Coverage \u5bfc\u51fa\u5b8c\u6210: ' + (out.out_dir || ''));
            // \u9884\u89c8 weak_top.csv \u524d 3 \u884c
            const ws = getWorkspaceRoot();
            if (ws) {
              const uri = vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv');
              try {
                const data = await vscode.workspace.fs.readFile(uri);
                const text = Buffer.from(data).toString('utf8');
                const raw = text.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw.length >= 1) {
                  const outLines: string[] = [];
                  outLines.push(raw[0]); // header: file,coverage,threshold,delta
                  for (const row of raw.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 4) {
                      const file = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const delt = Number(parts[3]||0)*100;
                      outLines.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                    } else {
                      outLines.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'weak_top.csv', head: outLines });
                }
              } catch {}
              // \u9884\u89c8 near_top.csv \u524d 3 \u884c
              try {
                const uri2 = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
                const data2 = await vscode.workspace.fs.readFile(uri2);
                const text2 = Buffer.from(data2).toString('utf8');
                const raw2 = text2.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw2.length >= 1) {
                  const out2: string[] = [];
                  out2.push(raw2[0]); // header: file,coverage,threshold,delta_up
                  for (const row of raw2.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 4) {
                      const file = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const delt = Number(parts[3]||0)*100;
                      out2.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                    } else {
                      out2.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'near_top.csv', head: out2 });
                }
              } catch {}
              // \u9884\u89c8 groups.csv \u524d 3 \u884c
              try {
                const uri3 = vscode.Uri.file(ws + '/.mcp/dashboard/groups.csv');
                const data3 = await vscode.workspace.fs.readFile(uri3);
                const text3 = Buffer.from(data3).toString('utf8');
                const raw3 = text3.split(/\r?\n/).slice(0, 4).filter(Boolean);
                if (raw3.length >= 1) {
                  const out3: string[] = [];
                  out3.push(raw3[0]); // header: prefix,coverage,threshold,weak_count,files_count
                  for (const row of raw3.slice(1)) {
                    const parts = row.split(',');
                    if (parts.length >= 5) {
                      const pref = parts[0];
                      const cov = Number(parts[1]||0)*100;
                      const thr = Number(parts[2]||0)*100;
                      const wc = parts[3];
                      const fc = parts[4];
                      out3.push(`${pref},${cov.toFixed(1)}%,${Math.round(thr)}%,${wc},${fc}`);
                    } else {
                      out3.push(row);
                    }
                  }
                  panel.webview.postMessage({ t: 'csvPreview', which: 'groups.csv', head: out3 });
                }
              } catch {}
            }
          } catch (e:any) {
            vscode.window.showWarningMessage('Coverage \u5bfc\u51fa\u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'csvPreviewPick') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const which = String(msg.which || 'weak_top.csv');
            const path = ws + '/.mcp/dashboard/' + which;
            const uri = vscode.Uri.file(path);
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            const raw = text.split(/\r?\n/).slice(0, 4).filter(Boolean);
            const out: string[] = [];
            if (raw.length >= 1) {
              out.push(raw[0]);
              for (const row of raw.slice(1)) {
                const parts = row.split(',');
                if (which === 'weak_top.csv' || which === 'near_top.csv') {
                  if (parts.length >= 4) {
                    const file = parts[0];
                    const cov = Number(parts[1]||0)*100;
                    const thr = Number(parts[2]||0)*100;
                    const delt = Number(parts[3]||0)*100;
                    out.push(`${file},${cov.toFixed(1)}%,${Math.round(thr)}%,${delt.toFixed(1)}%`);
                  } else { out.push(row); }
                } else if (which === 'groups.csv') {
                  if (parts.length >= 5) {
                    const pref = parts[0];
                    const cov = Number(parts[1]||0)*100;
                    const thr = Number(parts[2]||0)*100;
                    const wc = parts[3];
                    const fc = parts[4];
                    out.push(`${pref},${cov.toFixed(1)}%,${Math.round(thr)}%,${wc},${fc}`);
                  } else { out.push(row); }
                } else { out.push(row); }
              }
            }
            panel.webview.postMessage({ t: 'csvPreview', which, head: out });
          } catch (e:any) {
            vscode.window.showWarningMessage('\u8bfb\u53d6 CSV \u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'loadSugg') {
          const resList = await client.request('resources/list', {});
          const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
          if (!suggUri) {
            panel.webview.postMessage({ t: 'sugg', md: '\u672a\u627e\u5230\u5efa\u8bae\u8d44\u6e90\uff0c\u8bf7\u5148\u201c\u6444\u53d6\u89c4\u5219\u201d\u6216\u201c\u6821\u9a8c\u89c4\u5219\u201d' });
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u89c4\u5219\u5efa\u8bae\uff0c\u8bf7\u70b9\u51fb\u201c\u6444\u53d6\u89c4\u5219 / Ingest\u201d\u8fdb\u884c\u6444\u53d6\u3002' });
            panel.webview.postMessage({ t: 'suggestIngest' });
            return;
          }
          const sug = await client.request('resources/read', { uri: suggUri });
          panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
        } else if (msg.t === 'panel.click') {
          // Fallback router for generic button clicks from the webview
          // Expected: msg.action is a semantic key; gracefully degrade to Quick Actions when missing
          try {
            const a = String((msg && msg.action) || '').toLowerCase();
            if (!a) { await vscode.commands.executeCommand('mcpRulesAssistant.quickActions'); return; }
            if (a === 'openpanel' || a === 'panel') { await vscode.commands.executeCommand('mcpRulesAssistant.openPanel'); return; }
            if (a === 'quick' || a === 'quickactions') { await vscode.commands.executeCommand('mcpRulesAssistant.quickActions'); return; }
            if (a === 'coverage' || a === 'loadcoverage') { await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage'); return; }
            if (a === 'status' || a === 'statusupdate') { await vscode.commands.executeCommand('mcpRulesAssistant.statusUpdate'); return; }
            if (a === 'ingest' || a === 'ingestquick') { await vscode.commands.executeCommand('mcpRulesAssistant.ingestQuick'); return; }
            if (a === 'openplan') { await vscode.commands.executeCommand('mcpRulesAssistant.openPlan'); return; }
            if (a === 'openstatus') { await vscode.commands.executeCommand('mcpRulesAssistant.openStatus'); return; }
            if (a === 'doctor' || a === 'backenddoctor') { await vscode.commands.executeCommand('mcpRulesAssistant.backendDoctor'); return; }
            if (a === 'env.prepare' || a === 'prepareenv' || a === 'prepareenvinstall') { await vscode.commands.executeCommand('mcpRulesAssistant.envPrepareInstall'); return; }
            if (a === 'ci.generate') { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI 已生成'); return; }
            if (a === 'ci.validate') { await client.request('tools/call', { name: 'ci.validate', arguments: {} }); vscode.window.showInformationMessage('CI 校验完成'); return; }
            if (a === 'installhooks' || a === 'git.install_hooks') { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('钩子安装完成'); return; }
            // Default: open Quick Actions
            await vscode.commands.executeCommand('mcpRulesAssistant.quickActions');
          } catch (e:any) {
            vscode.window.showWarningMessage('操作执行失败：' + String(e));
          }
        } else if (msg.t === 'installHooks') {
          await client.request('tools/call', { name: 'git.install_hooks', arguments: {} });
          vscode.window.setStatusBarMessage('\u94a9\u5b50\u5b89\u88c5\u5b8c\u6210', 3000);
          try {
            await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Git hooks installed', meta: { source: 'vscode', action: 'git.install_hooks' } } });
          } catch {}
        } else if (msg.t === 'memory') {
          const resList = await client.request('resources/list', {});
          const memUri = (resList.resources || []).find((r: any) => String(r.uri || '').startsWith('memory://'))?.uri;
          if (!memUri) { panel.webview.postMessage({ t: 'memory', text: '\u65e0\u8bb0\u5fc6\u8d44\u6e90' }); return; }
          const res = await client.request('resources/read', { uri: memUri });
          panel.webview.postMessage({ t: 'memory', text: res.text || '' });
        } else if (msg.t === 'plan') {
          const resList = await client.request('resources/list', {});
          const planUri = (resList.resources || []).find((r: any) => String(r.uri || '').startsWith('progress://'))?.uri;
          if (!planUri) { panel.webview.postMessage({ t: 'plan', text: '\u65e0\u8ba1\u5212\u8d44\u6e90' }); return; }
          const res = await client.request('resources/read', { uri: planUri });
          panel.webview.postMessage({ t: 'plan', text: res.text || '' });
          const act = await vscode.window.showQuickPick(['\u6807\u8bb0\u8fdb\u884c\u4e2d / In progress', '\u6807\u8bb0\u5b8c\u6210 / Done', '\u4ec5\u67e5\u770b / View'], { title: '\u8ba1\u5212\u64cd\u4f5c' });
          if (act && act.startsWith('\u6807\u8bb0\u8fdb\u884c\u4e2d')) {
            const cur = await vscode.window.showInputBox({ title: '\u5f53\u524d\u6b65\u9aa4 / Current step', placeHolder: '\u4f8b\u5982\uff1a\u5b9e\u73b0 MCP \u534f\u8bae\u65b9\u6cd5' });
            if (cur) await client.request('tools/call', { name: 'plan.set', arguments: { status: 'in_progress', current: cur } });
            const res2 = await client.request('resources/read', { uri: planUri });
            panel.webview.postMessage({ t: 'plan', text: res2.text || '' });
          } else if (act && act.startsWith('\u6807\u8bb0\u5b8c\u6210')) {
            await client.request('tools/call', { name: 'plan.set', arguments: { status: 'done' } });
            const res2 = await client.request('resources/read', { uri: planUri });
            panel.webview.postMessage({ t: 'plan', text: res2.text || '' });
          }
        } else if (msg.t === 'ciFetch') {
          const cfg = await client.request('tools/call', { name: 'config.get', arguments: {} });
          panel.webview.postMessage({ t: 'ci', config: cfg.config || {} });
          vscode.window.setStatusBarMessage('\u5df2\u52a0\u8f7d CI \u914d\u7f6e', 2000);
        } else if (msg.t === 'ciCheck') {
          try {
          const ws = getWorkspaceRoot();
          if (!ws) throw new Error('no workspace');
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          await vscode.workspace.fs.stat(target);
          panel.webview.postMessage({ t: 'ciStatus', exist: true });
          } catch {
            panel.webview.postMessage({ t: 'ciStatus', exist: false });
          }
        } else if (msg.t === 'ciSave') {
          const data = msg.data || {};
          await client.request('tools/call', { name: 'config.update', arguments: { data } });
          vscode.window.setStatusBarMessage('CI \u914d\u7f6e\u5df2\u4fdd\u5b58', 2000);
        } else if (msg.t === 'ciGen') {
          const out = await client.request('tools/call', { name: 'ci.generate', arguments: {} });
          vscode.window.showInformationMessage('\u5df2\u751f\u6210 CI: ' + (out.path || ''));        
          vscode.commands.executeCommand('workbench.action.files.refresh');
          panel.webview.postMessage({ t: 'ciCheck' });
          try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI generated', meta: { source: 'vscode', action: 'ci.generate', path: out && out.path } } }); } catch {}
        } else if (msg.t === 'ciValidate') {
          const res = await client.request('tools/call', { name: 'ci.validate', arguments: {} });
          panel.webview.postMessage({ t: 'ciChecks', checks: (res.checks || {}) });
          try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'CI validated', meta: { source: 'vscode', action: 'ci.validate', ok: res && res.ok } } }); } catch {}
        } else if (msg.t === 'ciPreviewInline') {
          const resList = await client.request('resources/list', {});
          const ciUri = (resList.resources || []).find((r:any)=> String(r.uri||'').startsWith('ci://'))?.uri;
          if (!ciUri) { panel.webview.postMessage({ t: 'ciPreviewContent', text: '\uff08\u672a\u751f\u6210 CI\uff09' }); return; }
          const res = await client.request('resources/read', { uri: ciUri });
          panel.webview.postMessage({ t: 'ciPreviewContent', text: res.text || '' });
        } else if (msg.t === 'ciOpen') {
          const ws = getWorkspaceRoot(); if (!ws) return;
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try {
            await vscode.workspace.fs.stat(target);
            const doc = await vscode.workspace.openTextDocument(target);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch {
            vscode.window.showWarningMessage('CI \u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u5148\u751f\u6210');
          }
        } else if (msg.t === 'ciPreview') {
          const resList = await client.request('resources/list', {});
          const ciUri = (resList.resources || []).find((r:any)=> String(r.uri||'').startsWith('ci://'))?.uri;
          if (!ciUri) { vscode.window.showWarningMessage('\u672a\u627e\u5230 CI \u8d44\u6e90'); return; }
          const res = await client.request('resources/read', { uri: ciUri });
          const doc = await vscode.workspace.openTextDocument({ language: 'yaml', content: res.text || '' });
          await vscode.window.showTextDocument(doc, { preview: true });
        } else if (msg.t === 'ciOpen') {
          const ws = getWorkspaceRoot(); if (!ws) return;
          const target = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try {
            await vscode.workspace.fs.stat(target);
            const doc = await vscode.workspace.openTextDocument(target);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch {
            vscode.window.showWarningMessage('CI \u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u5148\u751f\u6210');
          }
        } else if (msg.t === 'ideScaffold') {
          const pick = await vscode.window.showQuickPick([
            { label: 'VS Code', val: 'vscode' },
            { label: 'Cursor', val: 'cursor' },
            { label: 'JetBrains', val: 'jetbrains' },
            { label: 'Neovim', val: 'neovim' },
          ], { title: '\u9009\u62e9 IDE' });
          if (!pick) return;
          const out = await client.request('tools/call', { name: 'ide.scaffold', arguments: { editor: pick.val } });
          vscode.window.showInformationMessage('\u5df2\u751f\u6210 IDE \u96c6\u6210\u914d\u7f6e: ' + JSON.stringify(out.files || []));
        } else if (msg.t === 'compliance') {
          const out = await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } });
          vscode.window.showInformationMessage('\u5df2\u751f\u6210\u5408\u89c4\u627f\u8bfa: ' + (out.path || '.mcp/compliance.md'));
        } else if (msg.t === 'openCompliance') {
          try {
            // ensure file exists, then open
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/compliance.md');
            try { await vscode.workspace.fs.stat(p); }
            catch { await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } }); }
            const doc = await vscode.workspace.openTextDocument(p);
            await vscode.window.showTextDocument(doc, { preview: false });
          } catch (e:any) {
            vscode.window.showWarningMessage('\u65e0\u6cd5\u6253\u5f00\u5408\u89c4\u627f\u8bfa\uff1a' + String(e));
          }
        } else if (msg.t === 'openIdeDir') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) return;
            const p = vscode.Uri.file(ws + '/.mcp/ide');
            await vscode.commands.executeCommand('revealFileInOS', p);
          } catch (e:any) {
            vscode.window.showWarningMessage('\u65e0\u6cd5\u6253\u5f00 IDE \u76ee\u5f55\uff1a' + String(e));
          }
        } else if (msg.t === 'eventsLoad') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            panel.webview.postMessage({ t: 'events', text });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u4e8b\u4ef6\u5386\u53f2' });
          }
        } else if (msg.t === 'auditLoad') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/security_audit.jsonl');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            panel.webview.postMessage({ t: 'audit', text });
          } catch {
            panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u5b89\u5168\u5ba1\u8ba1\uff08security_audit.jsonl\uff09' });
          }
        } else if (msg.t === 'statusInfo') {
          try {
            const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
            const uri = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
            const data = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(data).toString('utf8');
            try {
              const obj = JSON.parse(text || '{}');
              const info = Array.isArray(obj.info) ? obj.info : [];
              const lines = info.map((it:any) => {
                if (it && typeof it === 'object') { return `${it.time || ''}  ${it.text || ''}`; }
                return String(it);
              });
              panel.webview.postMessage({ t: 'infoList', items: lines });
            } catch { panel.webview.postMessage({ t: 'info', text: '\u72b6\u6001\u6458\u8981\u89e3\u6790\u5931\u8d25' }); }
          } catch { panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230 status.json' }); }
    } else if (msg.t === 'insertSamples') {
          const semgrep = `rules:\n  - id: py-no-eval\n    message: \"Avoid eval() — security risk\"\n    languages: [python]\n    severity: ERROR\n    pattern: eval(...)\n\n  - id: py-no-exec\n    message: \"Avoid exec() — security risk\"\n    languages: [python]\n    severity: ERROR\n    pattern: exec(...)\n`;
          const hadolint = `ignored:\n  - DL3008\n  - DL3059\n\noverrides:\n  DL3007: warning\n`;
          await client.request('tools/call', { name: 'fs.apply_patch', arguments: { files: [
            { path: '.semgrep.yml', content: semgrep },
            { path: '.hadolint.yaml', content: hadolint }
          ] } });
          vscode.window.setStatusBarMessage('\u5df2\u63d2\u5165\u793a\u4f8b\u89c4\u5219\uff08.semgrep.yml / .hadolint.yaml\uff09', 3000);
        } else if (msg.t === 'prepareEnvDry') {
          try {
            const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: false, install: false } });
            vscode.window.showInformationMessage('env.prepare \u8ba1\u5212: ' + JSON.stringify(out.plan || out));
          // \u4e25\u683c\u9694\u79bb\uff1a\u9ed8\u8ba4\u4e0d\u5199\u5165\u4efb\u4f55\u4e0a\u4e0b\u6587\u8bb0\u5fc6\uff08\u9700\u663e\u5f0f\u5141\u8bb8\uff09
          // if (process.env.RULEFLOW_ALLOW_MEMORY_APPEND === '1') {
          //   try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'env.prepare dry-run', meta: { source: 'vscode', action: 'env.prepare', create: false, install: false } } }); } catch {}
          // }
          } catch (e:any) {
            vscode.window.showErrorMessage('env.prepare \u6267\u884c\u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'prepareEnvInstall') {
          try {
            // 首选通过后端工具执行
            const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
            const msgInfo = (out && (out as any).ok) ? ('\u5df2\u521b\u5efa\u5e76\u5b89\u88c5\uff1a' + String((out as any).venv || '')) : '\u6267\u884c\u5931\u8d25';
            vscode.window.showInformationMessage('env.prepare: ' + msgInfo);
          } catch (e1:any) {
            // 兜底：直接在扩展侧创建 venv 并安装基础内容（最佳努力）
            try {
              const ws = getWorkspaceRoot() || process.cwd();
              const venvDir = path.join(ws, '.mcp', 'venv');
              const creator = (process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim())
                ? process.env.MCP_PYTHON_BIN.trim()
                : (process.platform === 'win32' ? 'python' : 'python3');
              await new Promise<void>((resolve) => {
                try { const p = spawn(creator, ['-m', 'venv', venvDir], { cwd: ws }); p.on('close', ()=>resolve()); p.on('error', ()=>resolve()); } catch { resolve(); }
              });
              const vpy = process.platform === 'win32' ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python');
              const run = (args: string[]) => new Promise<void>((resolve)=>{
                try { const p = spawn(vpy, args, { cwd: ws }); p.on('close', ()=>resolve()); p.on('error', ()=>resolve()); } catch { resolve(); }
              });
              if (fs.existsSync(vpy)) {
                await run(['-m', 'pip', 'install', '-U', 'pip', 'setuptools', 'wheel']);
                // 优先从工作区安装本地包
                const hasLocal = fs.existsSync(path.join(ws, 'pyproject.toml')) || fs.existsSync(path.join(ws, 'setup.py'));
                if (hasLocal) await run(['-m', 'pip', 'install', '-e', ws]);
                vscode.window.showInformationMessage('已创建并安装基础环境 (.mcp/venv)');
              } else {
                vscode.window.showWarningMessage('已尝试创建 .mcp/venv，但未检测到解释器');
              }
            } catch (e2:any) {
              vscode.window.showErrorMessage('env.prepare 兜底失败：' + String(e2));
            }
          }
        } else if (msg.t === 'selectProject') {
          const folders = vscode.workspace.workspaceFolders || [];
          if (!folders.length) { vscode.window.showWarningMessage('\u672a\u627e\u5230\u5de5\u4f5c\u533a'); return; }
          const pick = await vscode.window.showQuickPick(folders.map(f=>({ label: f.name, description: f.uri.fsPath })), { title: '\u9009\u62e9\u9879\u76ee\u6839\u76ee\u5f55' });
          if (!pick) return;
          try {
            __lockedRoot = pick.description;
            await context.workspaceState.update('ruleflow.lockRoot', __lockedRoot);
            // \u5199\u5165 ui_prefs.json \u4ee5\u5171\u4eab\u9009\u62e9
            try {
              const dash = path.join(__lockedRoot, '.mcp', 'dashboard');
              fs.mkdirSync(dash, { recursive: true });
              const up = path.join(dash, 'ui_prefs.json');
              let obj: any = {}; try { obj = JSON.parse(fs.readFileSync(up, 'utf8')||'{}'); } catch {}
              obj.projectRoot = __lockedRoot; fs.writeFileSync(up, JSON.stringify(obj, null, 2));
            } catch {}
            // \u91cd\u542f\u540e\u7aef\u4ee5\u5e94\u7528\u65b0\u7684 MCP_PROJECT_ROOT
            try { (client as any).proc?.kill(); (client as any).proc=null; } catch {}
            try { client.start(context); } catch {}
            panel.webview.postMessage({ t: 'project', name: pick.label });
            panel.webview.postMessage({ t: 'info', text: '\u5df2\u5207\u6362\u81f3\u9879\u76ee\uff1a' + pick.label });
          } catch (e:any) {
            vscode.window.showErrorMessage('\u5207\u6362\u9879\u76ee\u5931\u8d25\uff1a' + String(e));
          }
        }
        else if (msg.t === 'onboardPreview') {
          try {
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { apply: false } });
            const ob = out || {};
            const lines: string[] = [];
            if (typeof ob.summary === 'string' && ob.summary) lines.push(String(ob.summary));
            try {
              const p = ob.profile || {};
              const cov = p.coverage || {}; const sec = p.security || {}; const cont = p.container || {}; const lic = p.license || {}; const ci = p.ci || {};
              lines.push('\u2014 coverage.min_module=' + (cov.min_module!==undefined? String(cov.min_module):'-'));
              lines.push('\u2014 security: secrets_scan=' + String(!!sec.secrets_scan) + ', sast_strict=' + String(!!sec.sast_strict));
              lines.push('\u2014 container: baseline=' + String(!!cont.baseline) + ', required=' + String(!!cont.required));
              lines.push('\u2014 license.required=' + String(!!lic.required));
              if (ci && (ci.hadolint || ci.semgrep_config)) {
                lines.push('\u2014 ci: hadolint=' + String(!!ci.hadolint) + (ci.semgrep_config? (', semgrep_config=' + String(ci.semgrep_config)) : ''));
              }
            } catch {}
            panel.webview.postMessage({ t: 'onboardShow', text: lines.join('\n') });
            panel.webview.postMessage({ t: 'info', text: 'Onboard \u9884\u89c8\u5b8c\u6210' });
          } catch (e:any) {
            panel.webview.postMessage({ t: 'info', text: 'Onboard \u9884\u89c8\u5931\u8d25\uff1a' + String(e) });
          }
        } else if (msg.t === 'onboardApply') {
          try {
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { apply: true } });
            vscode.window.showInformationMessage('Onboard \u5df2\u91c7\u7eb3\uff1a' + JSON.stringify({ applied: out && out.applied }));
            try { await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content: 'Onboard applied', meta: { source: 'vscode', action: 'rules.onboard' } } }); } catch {}
          } catch (e:any) {
            vscode.window.showErrorMessage('Onboard \u91c7\u7eb3\u5931\u8d25\uff1a' + String(e));
          }
        } else if (msg.t === 'chatEnable') {
          await context.workspaceState.update('ruleflow.chat.appendEnabled', true);
          panel.webview.postMessage({ t: 'chatShow', text: 'Chat \u8ffd\u52a0\u6458\u8981\uff1a\u5df2\u542f\u7528\uff08\u9ed8\u8ba4\u6458\u8981\u77ed\u5c0f\uff0c\u4e0d\u542b\u6e90\u7801/\u4e2a\u4eba\u4fe1\u606f\uff09' });
        } else if (msg.t === 'chatDisable') {
          await context.workspaceState.update('ruleflow.chat.appendEnabled', false);
          panel.webview.postMessage({ t: 'chatShow', text: 'Chat \u8ffd\u52a0\u6458\u8981\uff1a\u5df2\u7981\u7528' });
        } else if (msg.t === 'chatPreview') {
          const enabled = !!context.workspaceState.get('ruleflow.chat.appendEnabled');
          const demo = 'Chat: \u8fd9\u91cc\u5c06\u663e\u793a\u4e0a\u4e00\u8f6e\u95ee\u7b54\u7684\u7b80\u8981\u6458\u8981\uff08\u793a\u4f8b\uff09';
          panel.webview.postMessage({ t: 'chatShow', text: (enabled ? '\uff08\u542f\u7528\uff09' : '\uff08\u7981\u7528\uff09') + ' ' + demo });
        }
      } catch (e: any) {
        vscode.window.showErrorMessage('\u64cd\u4f5c\u5931\u8d25\uff1a' + String(e));
      } finally {
        try { if (__panelInFlightResolve) { __panelInFlightResolve(); } } catch {}
        __panelInFlightResolve = null;
        __panelInFlight = null;
      }
    };
    // 统一的消息处理器 - 处理所有webview消息
    panel.webview.onDidReceiveMessage(async (msg) => { 
      // Mark full handler ready and flush any early queued messages once
      if (!(panel as any).__fullHandlerReady) {
        (panel as any).__fullHandlerReady = true;
        try {
          if (Array.isArray(__preMsgs) && __preMsgs.length) {
            const queued = __preMsgs.splice(0, __preMsgs.length);
            for (const m of queued) {
              try {
                console.log('[MCP Rules Assistant] (flush) Webview message received:', JSON.stringify(m));
                await __panelDispatch(m);
                await handleOpenMessage(m);
              } catch {}
            }
          }
        } catch {}
      }
      console.log('[MCP Rules Assistant] Webview message received:', JSON.stringify(msg));
      // 记录关键操作到 .mcp/dashboard/cmd_events.jsonl 便于诊断
      try {
        const ws = getWorkspaceRoot();
        if (ws) {
          const uriE = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
          const enc = new TextEncoder();
          const line = JSON.stringify({ time: new Date().toISOString(), kind: 'panel.msg', t: String(msg && msg.t || ''), ok: true }) + '\n';
          try {
            let old = '';
            try { const b = await vscode.workspace.fs.readFile(uriE); old = Buffer.from(b).toString('utf8'); } catch {}
            await vscode.workspace.fs.writeFile(uriE, enc.encode(old + line));
          } catch {
            await vscode.workspace.fs.writeFile(uriE, enc.encode(line));
          }
        }
      } catch {}
      
      // 处理面板调度消息
      await __panelDispatch(msg);
      
      // 处理打开文件消息
      await handleOpenMessage(msg);
      
      // 处理ready消息
      if (msg && msg.t === 'ready') { try { if (__panelReadyResolve) { __panelReadyResolve(); __panelReadyResolve = null; } } catch {} }
      if (msg && msg.t === 'ready2') {
        try {
          const key = String((msg.topic||'any'));
          const r = __ready2Resolvers.get(key) || __ready2Resolvers.get('any');
          if (r) r();
        } catch {}
      }
      if (msg && msg.t === 'nl') {
        try {
          const text = String(msg.text || '').trim();
          if (!text) return;
          const res = await client.request('tools/call', { name: 'nl.command', arguments: { text } });
          const mapped = (res && (res as any).parsed && (res as any).parsed.tool) || '';
          // \u7b80\u6613\u8c03\u5ea6\uff1a\u6839\u636e\u6620\u5c04\u8c03\u7528\u5e38\u7528\u5de5\u5177
          const lower = text.toLowerCase();
          const runIngest = async () => {
            // \u7c97\u7565\u63d0\u53d6\u53ef\u80fd\u7684\u8def\u5f84
            const cand = text.split(/[\uff0c,\s]+/).filter(s => /[./]/.test(s));
            const paths = cand.filter(p => !/\u6444\u53d6|\u89c4\u5219|ingest|load|\u8f7d\u5165|\u52a0\u8f7d/.test(p));
            const final = paths.length ? paths : (await vscode.window.showInputBox({ title: '\u8f93\u5165\u8981\u6444\u53d6\u7684\u6587\u4ef6\u6216\u76ee\u5f55\uff08\u9017\u53f7\u5206\u9694\uff09' }))?.split(',').map(s=>s.trim()).filter(Boolean) || [];
            if (!final.length) return;
            await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: final } });
            panel.webview.postMessage({ t: 'info', text: '\u89c4\u5219\u6444\u53d6\u5b8c\u6210\uff1a' + final.join(', ') });
          };
          const runCoverage = async () => {
            const resList = await client.request('resources/list', {});
            const summaryUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/summary'))?.uri;
            if (!summaryUri) { panel.webview.postMessage({ t: 'info', text: '\u672a\u627e\u5230\u8986\u76d6\u7387\u8d44\u6e90\uff0c\u8bf7\u5148\u751f\u6210 coverage.xml\u3002' }); return; }
            const r = await client.request('resources/read', { uri: summaryUri });
            try { const data = JSON.parse((r as any).text || '{}'); panel.webview.postMessage({ t: 'covWeakAll', items: data.weak || [] }); } catch {}
          };
          const runNear = async () => {
            const pct = 0.03;
            const r = await client.request('tools/call', { name: 'coverage.near', arguments: { within: pct, top: 50 } });
            const items = (r && (r as any).near) ? (r as any).near : [];
            panel.webview.postMessage({ t: 'covNearDisplay', items, pct: 3 });
          };
          const runLoadRules = async () => {
            const resList = await client.request('resources/list', {});
            const compiledUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/compiled'))?.uri;
            const suggUri = (resList.resources || []).find((r: any) => String(r.uri || '').endsWith('/suggestions'))?.uri;
            if (compiledUri) {
              const res = await client.request('resources/read', { uri: compiledUri });
              panel.webview.postMessage({ t: 'rules', md: res.text || '' });
            }
            if (suggUri) {
              const sug = await client.request('resources/read', { uri: suggUri });
              panel.webview.postMessage({ t: 'sugg', md: sug.text || '' });
            }
          };
          const runToggleMemory = async () => {
            const on = !/(\u5173\u95ed|disable)/.test(text);
            await client.request('tools/call', { name: 'memory.toggle_auto', arguments: { on } });
            panel.webview.postMessage({ t: 'info', text: on ? '\u5df2\u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6' : '\u5df2\u5173\u95ed\u6eda\u52a8\u8bb0\u5fc6' });
          };
          const runMemorySnapshot = async () => {
            const snap = await client.request('tools/call', { name: 'memory.snapshot', arguments: {} });
            panel.webview.postMessage({ t: 'memory', text: JSON.stringify(snap || {}, null, 2) });
          };
          const runCiGen = async () => { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '\u5df2\u751f\u6210 CI' }); };
          const runCiValidate = async () => { const v = await client.request('tools/call', { name: 'ci.validate', arguments: {} }); panel.webview.postMessage({ t: 'info', text: 'CI \u6821\u9a8c\u5b8c\u6210' }); };
          const runCiAutofix = async () => { await client.request('tools/call', { name: 'ci.autofix', arguments: {} }); panel.webview.postMessage({ t: 'info', text: 'CI \u5df2\u81ea\u4fee\u590d' }); };
          const runInstallHooks = async () => { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '\u94a9\u5b50\u5b89\u88c5\u5b8c\u6210' }); };
          const runEnforce = async () => { await client.request('tools/call', { name: 'rules.enforce', arguments: {} }); panel.webview.postMessage({ t: 'info', text: '\u5df2\u5e94\u7528\u95e8\u7981\u7b56\u7565\u5230\u914d\u7f6e' }); };
          const runRulesOnboard = async () => {
            const pick = await vscode.window.showQuickPick([
              { label: '\u4e2a\u4eba / personal', val: 'personal' },
              { label: '\u4e13\u4e1a / pro', val: 'pro' },
              { label: '\u4f01\u4e1a / enterprise', val: 'enterprise' },
              { label: '\u673a\u6784 / institution', val: 'institution' },
            ], { title: '\u9009\u62e9\u5e94\u7528\u573a\u666f / Scenario' });
            if (!pick) return;
            const pickC = await vscode.window.showQuickPick([
              { label: '\u5c0f / small', val: 'small' },
              { label: '\u4e2d / medium', val: 'medium' },
              { label: '\u5927 / large', val: 'large' },
            ], { title: '\u9009\u62e9\u590d\u6742\u5ea6 / Complexity' });
            if (!pickC) return;
            const pickM = await vscode.window.showQuickPick([
              { label: 'TDD', val: 'tdd' },
              { label: 'BDD', val: 'bdd' },
              { label: '\u6587\u6863\u9a71\u52a8 / doc', val: 'doc' },
              { label: '\u539f\u578b / spike', val: 'spike' },
            ], { title: '\u9009\u62e9\u5f00\u53d1\u6a21\u5f0f / Dev Mode' });
            if (!pickM) return;
            const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { scenario: pick.val, complexity: pickC.val, devMode: pickM.val, apply: true } });
            vscode.window.showInformationMessage('\u5df2\u5e94\u7528\u89c4\u5219\u6863\uff1a' + JSON.stringify(out));
          };
          const runPrepareEnv = async () => { const out = await client.request('tools/call', { name: 'env.prepare', arguments: { create: false, install: false } }); vscode.window.showInformationMessage('env.prepare \u8ba1\u5212: ' + JSON.stringify(out.plan || out)); };

          if (mapped === 'rules.ingest') await runIngest();
          else if (mapped === 'coverage.near') await runNear();
          else if (mapped === 'resources.read') { if (/\u8986\u76d6\u7387|coverage/.test(lower)) await runCoverage(); else await runLoadRules(); }
          else if (mapped === 'memory.toggle_auto') await runToggleMemory();
          else if (mapped === 'memory.snapshot') await runMemorySnapshot();
          else if (mapped === 'ci.generate') await runCiGen();
          else if (mapped === 'ci.validate') await runCiValidate();
          else if (mapped === 'ci.autofix') await runCiAutofix();
          else if (mapped === 'git.install_hooks') await runInstallHooks();
          else if (mapped === 'rules.validate') { await client.request('tools/call', { name: 'rules.validate', arguments: {} }); await runLoadRules(); }
          else if (mapped === 'rules.enforce') await runEnforce();
          else if (mapped === 'env.prepare') await runPrepareEnv();

          vscode.window.setStatusBarMessage('\u5df2\u6267\u884c\uff1a' + (mapped || 'nl.command'), 3000);
          panel.webview.postMessage({ t: 'info', text: '\u5df2\u6267\u884c\uff1a' + (text || '') });
          // \u8bf7\u6c42\u5237\u65b0\u5386\u53f2
          vscode.commands.executeCommand('setContext', 'ruleflow.lastNL', text);
          panel.webview.postMessage({ t: 'nlRunOk', text });
          const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
          const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
          await context.workspaceState.update('ruleflow.nl.history', nh);
          panel.webview.postMessage({ t: 'nlHistory', items: nh });
        } catch (e:any) {
          vscode.window.showWarningMessage('\u81ea\u7136\u8bed\u8a00\u6267\u884c\u5931\u8d25\uff1a' + String(e));
          panel.webview.postMessage({ t: 'info', text: '\u81ea\u7136\u8bed\u8a00\u6267\u884c\u5931\u8d25' });
        }
      }
      // Webview \u8bf7\u6c42\u201c\u8fd1\u9608\u503c\u201d\u4ea4\u4e92\uff1a\u6269\u5c55\u4fa7\u5f39\u51fa\u8f93\u5165\u6846\u5e76\u8ba1\u7b97
      if (msg && msg.t === 'covNearPrompt') {
        try {
          const last = Number(msg.last || 3) || 3;
          const val = await vscode.window.showInputBox({ title: '\u8fd1\u9608\u503c\u7a97\u53e3\uff08\u767e\u5206\u6bd4\uff09', value: String(last), prompt: '\u5355\u4f4d %\uff081\u201310\uff09\uff0c\u4f8b\u5982 3 \u8868\u793a \u22643%' });
          if (!val) { return; }
          const pct = Math.max(1, Math.min(10, parseFloat(val))) || 3;
          const top = 50;
          const res = await client.request('tools/call', { name: 'coverage.near', arguments: { within: pct/100.0, top } });
          const items = (res && (res as any).near) ? (res as any).near : [];
          panel.webview.postMessage({ t: 'covNearDisplay', items, pct, top });
        } catch (e:any) {
          vscode.window.showWarningMessage('\u83b7\u53d6\u8fd1\u9608\u503c\u5931\u8d25\uff1a' + String(e));
        }
      }
      if (msg && msg.t === 'nlClearHistory') {
        try {
          await context.workspaceState.update('ruleflow.nl.history', []);
          panel.webview.postMessage({ t: 'nlHistory', items: [] });
          panel.webview.postMessage({ t: 'info', text: '\u5df2\u6e05\u7a7a\u81ea\u7136\u8bed\u8a00\u5386\u53f2' });
        } catch {}
      }
      if (msg && msg.t === 'nlFetchHistory') {
        try {
          const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
          panel.webview.postMessage({ t: 'nlHistory', items: h });
        } catch {}
      }
      if (msg && msg.t === 'licenseVerify') {
        try {
          const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
          panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
          panel.webview.postMessage({ t: 'info', text: 'License \u5df2\u6821\u9a8c' });
        } catch (e:any) {
          vscode.window.showWarningMessage('License \u6821\u9a8c\u5931\u8d25\uff1a' + String(e));
        }
      }
      if (msg && msg.t === 'licenseActivate') {
        try {
          const files = await vscode.window.showOpenDialog({ title: '\u9009\u62e9 License JSON \u6587\u4ef6', canSelectMany: false, filters: { 'JSON': ['json'], 'All Files': ['*'] } });
          if (!files || !files.length) return;
          const p = files[0].fsPath;
          await client.request('tools/call', { name: 'license.activate', arguments: { path: p } });
          const diag = await client.request('tools/call', { name: 'env.diagnose', arguments: {} });
          panel.webview.postMessage({ t: 'license', license: (diag && (diag as any).license) || {} });
          panel.webview.postMessage({ t: 'info', text: 'License \u5df2\u6fc0\u6d3b' });
        } catch (e:any) {
          vscode.window.showWarningMessage('License \u6fc0\u6d3b\u5931\u8d25\uff1a' + String(e));
        }
      }
    });
  });
  // \u6ce8\uff1aquickActions \u547d\u4ee4\u5df2\u5728\u4e0a\u6587\u6ce8\u518c\uff1b\u6b64\u5904\u91cd\u590d\u6ce8\u518c\u5df2\u79fb\u9664\u4ee5\u907f\u514d\u6d4b\u8bd5\u4e2d\u91cd\u590d\u6fc0\u6d3b\u5bfc\u81f4\u51b2\u7a81

  // \u8bb8\u53ef\u72b6\u6001\uff08\u53ea\u8bfb\uff09\uff1a\u8c03\u7528 license.verify \u5e76\u5c55\u793a\u7ed3\u679c
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseStatus', async () => {
    try { client.start(context); } catch {}
    try {
      const out = await client.request('tools/call', { name: 'license.verify', arguments: {} });
      vscode.window.showInformationMessage('License: ' + JSON.stringify(out));
    } catch (e:any) {
      vscode.window.showErrorMessage('License verify failed: ' + String(e));
    }
  }));

  context.subscriptions.push(disposable);

  // --- test-only helper commands (not contributed) ---
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_openPanelLite', async () => {
    const panel = vscode.window.createWebviewPanel('mcpRulesAssistantTest', 'RuleFlow Test Panel', vscode.ViewColumn.Beside, { enableScripts: true });
    panel.webview.html = '<html><body><h3>Test Panel</h3></body></html>';
    panel.webview.onDidReceiveMessage(async (msg) => { await handleOpenMessage(msg); });
    __testWebviewHandler = async (m:any) => { await handleOpenMessage(m); };
    return true;
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitReady', async () => {
    try {
      const p = __panelReady;
      if (!p) return true;
      let done = false;
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p.then(()=>{ done = true; }), t]);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitIdle', async () => {
    try {
      const p = __panelInFlight;
      if (!p) return true;
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p, t]);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_waitReady2', async (topic?: string) => {
    try {
      const key = String(topic||'any');
      let p = __ready2Promises.get(key);
      if (!p) {
        p = new Promise<void>((res)=>{ __ready2Resolvers.set(key, res); });
        __ready2Promises.set(key, p);
      }
      const t = new Promise<void>((res)=>setTimeout(res, 2500));
      await Promise.race([p, t]);
      __ready2Promises.delete(key);
      __ready2Resolvers.delete(key);
      return true;
    } catch { return true; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_simulateWebviewMessage', async (msg:any) => {
    if (__testWebviewHandler) { await __testWebviewHandler(msg); }
    return true;
  }));

  // test-only: get/clear fake tool calls (when fake mode is on)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_getFakeCalls', async () => {
    try { return (client as any)._testGetFakeCalls ? (client as any)._testGetFakeCalls() : []; } catch { return []; }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_clearFakeCalls', async () => {
    try { if ((client as any)._testClearFakeCalls) (client as any)._testClearFakeCalls(); return true; } catch { return false; }
  }));
  // test-only: set chat append enabled flag
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_chatSetEnabled', async (on?: boolean) => {
    try { await context.workspaceState.update('ruleflow.chat.appendEnabled', !!on); return true; } catch { return false; }
  }));

  // Public: append last chat summary into memory (optional; guarded by enable flag)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.chatAppendSummary', async (text?: string) => {
    try { client.start(context); } catch {}
    try {
      const enabled = !!context.workspaceState.get('ruleflow.chat.appendEnabled');
      if (!enabled) { vscode.window.showInformationMessage('Chat \u8ffd\u52a0\u6458\u8981\u672a\u542f\u7528'); return true; }
      let summary = (typeof text === 'string' && text.trim()) ? String(text).trim() : '';
      if (!summary) {
        summary = await vscode.window.showInputBox({ placeHolder: '\u8f93\u5165\u8981\u8ffd\u52a0\u7684\u4e0a\u4e00\u8f6e\u95ee\u7b54\u6458\u8981' }) || '';
      }
      if (!summary) { return false; }
      const content = 'ChatSummary: ' + summary;
      await client.request('tools/call', { name: 'memory.append_turn', arguments: { role: 'assistant', content, meta: { source: 'vscode', action: 'chat.append' } } });
      vscode.window.showInformationMessage('\u5df2\u8ffd\u52a0 Chat \u6458\u8981');
      return true;
    } catch (e:any) {
      vscode.window.showErrorMessage('Chat \u6458\u8981\u8ffd\u52a0\u5931\u8d25\uff1a' + String(e));
      return false;
    }
  }));

  // test-only: \u76f4\u63a5\u89e6\u53d1\u90e8\u5206 quick actions\uff08\u4e0d\u4f9d\u8d56\u540e\u7aef\u4e0e\u771f\u5b9e webview \u4e8b\u4ef6\uff09\uff0c\u4fbf\u4e8e\u5728\u65e0 Python \u7684\u73af\u5883\u8986\u76d6 UI \u5206\u652f
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_dispatchQuick', async (which: string) => {
    try {
      switch (which) {
        case 'openWeakCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/weak_top.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openNearCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openGroupsCsv': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/groups.csv');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openJbGroupsMd': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/jb_groups.md');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openJbVerify': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/jb_verify.json');
          await vscode.workspace.fs.stat(u);
          const d = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(d, { preview: false });
          break;
        }
        case 'openIdeDir': {
          const ws = getWorkspaceRoot(); if (!ws) throw new Error('no workspace');
          const uri = vscode.Uri.file(ws + '/.mcp/ide');
          // ensure directory exists or silently skip
          try { await vscode.workspace.fs.createDirectory(uri); } catch {}
          // reveal directory by opening a dummy README if present in subtree, else no-op
          // (\u907f\u514d\u989d\u5916\u590d\u6742\u5ea6\uff1a\u4e0d\u5f3a\u5236\u521b\u5efa\u6587\u4ef6)
          break;
        }
        default:
          // no-op
          break;
      }
      return true;
    } catch (e:any) {
      // \u548c\u771f\u5b9e\u5206\u652f\u4fdd\u6301\u4e00\u81f4\uff1a\u82e5\u4e0d\u5b58\u5728\u5219\u9759\u9ed8\u6216\u4ee5\u4fe1\u606f\u63d0\u793a\uff0c\u8fd9\u91cc\u7edf\u4e00\u4e0d\u629b\u5f02\u5e38
      return false;
    }
  }));

  // test-only: \u6a21\u62df Panel \u6d88\u606f\u5206\u652f\uff08\u65e0\u540e\u7aef\uff09\uff0c\u8986\u76d6\u90e8\u5206 onDidReceiveMessage \u7684\u5178\u578b\u8def\u5f84
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_dispatchPanel', async (which: string) => {
    try {
      const ws = getWorkspaceRoot() || process.cwd();
      const dash = vscode.Uri.file(ws + '/.mcp/dashboard');
      try { await vscode.workspace.fs.createDirectory(dash); } catch {}
      switch (which) {
        case 'statusUpdate': {
          const u = vscode.Uri.file(ws + '/.mcp/dashboard/status.json');
          const data = Buffer.from(JSON.stringify({ plan: { status: 'in_progress', current: 'test' }, coverage: { weak: [] }, tasks: { pending: [], done: [] } }, null, 2), 'utf-8');
          await vscode.workspace.fs.writeFile(u, data);
          vscode.window.showInformationMessage('test: status updated');
          break;
        }
        case 'ideScaffold': {
          const ide = vscode.Uri.file(ws + '/.mcp/ide');
          await vscode.workspace.fs.createDirectory(ide);
          vscode.window.showInformationMessage('test: ide scaffold created');
          break;
        }
        case 'compliance': {
          const u = vscode.Uri.file(ws + '/.mcp/compliance.md');
          await vscode.workspace.fs.writeFile(u, Buffer.from('# Compliance Commitment\n', 'utf-8'));
          vscode.window.showInformationMessage('test: compliance.md written');
          break;
        }
        case 'openCompliance': {
          const u = vscode.Uri.file(ws + '/.mcp/compliance.md');
          try { await vscode.workspace.fs.stat(u); } catch { await vscode.workspace.fs.writeFile(u, Buffer.from('# Compliance Commitment\n', 'utf-8')); }
          const doc = await vscode.workspace.openTextDocument(u);
          await vscode.window.showTextDocument(doc, { preview: false });
          break;
        }
        case 'ciOpenExist': {
          const yml = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await vscode.workspace.fs.stat(yml); } catch {
            await vscode.workspace.fs.createDirectory(vscode.Uri.file(ws + '/.github/workflows'));
            await vscode.workspace.fs.writeFile(yml, Buffer.from('name: CI\n', 'utf-8'));
          }
          const doc = await vscode.workspace.openTextDocument(yml);
          await vscode.window.showTextDocument(doc, { preview: false });
          break;
        }
        case 'ciOpenMissing': {
          const yml = vscode.Uri.file(ws + '/.github/workflows/ci.yml');
          try { await vscode.workspace.fs.delete(yml, { recursive: false }); } catch {}
          // simulate missing path by attempting stat and swallowing
          try { await vscode.workspace.fs.stat(yml); } catch {}
          vscode.window.showInformationMessage('test: ci.yml missing (simulated)');
          break;
        }
        case 'covNearPrompt': {
          const near = vscode.Uri.file(ws + '/.mcp/dashboard/near_top.csv');
          try { await vscode.workspace.fs.stat(near); } catch { await vscode.workspace.fs.writeFile(near, Buffer.from('file,coverage,threshold\n', 'utf-8')); }
          vscode.window.showInformationMessage('test: covNearPrompt simulated');
          break;
        }
        default:
          break;
      }
      return true;
    } catch {
      return false;
    }
  }));

  // test-only: \u76f4\u63a5\u5411 panel \u6d88\u606f\u5904\u7406\u5668\u53d1\u9001\u6d88\u606f\uff08\u9700\u8981\u5148\u6253\u5f00 openPanel \u521b\u5efa\u9762\u677f\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_sendPanelMessage', async (msg: any) => {
    if (__testPanelHandler) { await __testPanelHandler(msg); return true; }
    return false;
  }));

  // test-only: NL \u5386\u53f2 add/clear\uff08\u4e0d\u4f9d\u8d56\u540e\u7aef\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant._test_nlHistory', async (op: 'add'|'clear', text?: string) => {
    if (op === 'add') {
      const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
      const t = (text || 'hello').trim();
      const nh = [t, ...h.filter(x=>x!==t)].slice(0, 10);
      await context.workspaceState.update('ruleflow.nl.history', nh);
      return nh.length;
    }
    if (op === 'clear') {
      await context.workspaceState.update('ruleflow.nl.history', []);
      return 0;
    }
    return -1;
  }));

  // \u8f7b\u91cf\u4fdd\u5b58\u62e6\u622a\uff1a\u4e0d\u505a\u91cd\u64cd\u4f5c\uff0c\u4ec5\u540e\u7eed\u53ef\u6269\u5c55\uff08\u4fdd\u6301\u6027\u80fd\uff09
  context.subscriptions.push(vscode.workspace.onWillSaveTextDocument(async (_e) => {
    // \u9884\u7559\uff1a\u53ef\u5728\u6b64\u505a\u6539\u52a8\u6587\u4ef6 lint \u7684\u89e6\u53d1\u6216\u7edf\u8ba1\uff0c\u65e0\u963b\u585e
  }));

  // \u8f6f\u62e6\u622a\uff1a\u63d0\u4ea4\uff08\u8fd0\u884c pre-commit commit \u9636\u6bb5\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.commit', async () => {
    try {
      const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!ws) { vscode.window.showWarningMessage('\u672a\u627e\u5230\u5de5\u4f5c\u533a'); return; }
      const msg = await vscode.window.showInputBox({ title: '\u63d0\u4ea4\u8bf4\u660e / Commit message' });
      if (msg === undefined) return;
      // \u5148\u8fd0\u884c pre-commit commit \u9636\u6bb5
      await runShell('pre-commit', ['run', '--hook-stage', 'commit', '--all-files'], ws);
      await runShell('git', ['add', '-A'], ws);
      await runShell('git', ['commit', '-m', msg || 'chore: commit via mcp'], ws);
      vscode.window.setStatusBarMessage('\u63d0\u4ea4\u5b8c\u6210\uff08commit checks \u901a\u8fc7\uff09', 3000);
    } catch (e: any) {
      vscode.window.showErrorMessage('\u63d0\u4ea4\u5931\u8d25\uff1a' + String(e));
    }
  }));

  // \u8f6f\u62e6\u622a\uff1a\u63a8\u9001\uff08\u89e6\u53d1 pre-push \u94a9\u5b50\uff0c\u8dd1\u91cd\u578b\u95e8\u7981\uff09
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.push', async () => {
    try {
      const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!ws) { vscode.window.showWarningMessage('\u672a\u627e\u5230\u5de5\u4f5c\u533a'); return; }
      await runShell('git', ['push'], ws);
      vscode.window.setStatusBarMessage('\u63a8\u9001\u5b8c\u6210\uff08push gates \u901a\u8fc7\uff09', 3000);
    } catch (e: any) {
      vscode.window.showErrorMessage('\u63a8\u9001\u5931\u8d25\uff1a' + String(e));
    }
  }));

  // \u81ea\u7136\u8bed\u8a00\u547d\u4ee4\uff1a\u5728\u8f93\u5165\u6846\u4e2d\u8f93\u5165\u201c\u6444\u53d6\u89c4\u5219/\u5f00\u542f\u8bb0\u5fc6\u201d\u7b49\u77ed\u8bed
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.nlCommand', async () => {
    try {
      client.start(context);
      const text = await vscode.window.showInputBox({
        title: 'RuleFlow \u81ea\u7136\u8bed\u8a00\u547d\u4ee4',
        placeHolder: '\u4f8b\u5982\uff1a\u6444\u53d6\u89c4\u5219 README.md, docs/ \u6216 \u5f00\u542f\u6eda\u52a8\u8bb0\u5fc6'
      });
      if (!text) return;
      const res = await client.request('tools/call', { name: 'nl.command', arguments: { text } });
      const tool = (res && (res as any).parsed && (res as any).parsed.tool) || 'nl.command';
      const lower = (text || '').toLowerCase();
      // Route common tools to concrete actions for true one-command behavior
      const runLoadCoverage = async () => {
        await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage');
      };
      const runIngestRules = async () => {
        // Try to parse simple CSV paths from input, else default to README.md, docs/
        const m = text.split(/\u6444\u53d6\u89c4\u5219|ingest rules|\u89c4\u5219|ingest/i).slice(-1)[0] || '';
        let paths = m.split(/[,\uff0c]/).map(s=>s.trim()).filter(Boolean);
        if (paths.length === 0) paths = ['README.md', 'docs/'];
        await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } });
        vscode.window.showInformationMessage('\u89c4\u5219\u6444\u53d6\u5b8c\u6210');
      };
      const runCiGenerate = async () => {
        const out = await client.request('tools/call', { name: 'ci.generate', arguments: {} });
        vscode.window.showInformationMessage('CI \u5df2\u751f\u6210: ' + (out && out.path ? String(out.path) : ''));        
      };
      const runCiValidate = async () => {
        const out = await client.request('tools/call', { name: 'ci.validate', arguments: {} });
        vscode.window.showInformationMessage('CI \u6821\u9a8c\u5b8c\u6210');
      };
      const runInstallHooks = async () => {
        await client.request('tools/call', { name: 'git.install_hooks', arguments: {} });
        vscode.window.showInformationMessage('Git hooks \u5df2\u5b89\u88c5');
      };
      const runEnvPrepare = async () => {
        const choice = await vscode.window.showQuickPick(['\u9884\u89c8 / Dry-run', '\u521b\u5efa\u5e76\u5b89\u88c5 / Create+Install'], { title: '\u51c6\u5907\u73af\u5883' });
        if (!choice) return;
        const args = choice.startsWith('\u9884\u89c8') ? { create: false, install: false } : { create: true, install: true };
        const out = await client.request('tools/call', { name: 'env.prepare', arguments: args });
        vscode.window.showInformationMessage('\u73af\u5883\u51c6\u5907: ' + (out && out.ok ? 'OK' : 'Done'));
      };
      const runRulesEnforce = async () => {
        const out = await client.request('tools/call', { name: 'rules.enforce', arguments: {} });
        vscode.window.showInformationMessage('Enforce: ' + (out && out.changed ? '\u914d\u7f6e\u5df2\u66f4\u65b0' : '\u65e0\u53d8\u5316'));
      };
      const runCompliance = async () => {
        const out = await client.request('tools/call', { name: 'compliance.commitment', arguments: { write: true } });
        vscode.window.showInformationMessage('\u5408\u89c4\u627f\u8bfa\u5df2\u751f\u6210');
      };
      // Dispatch
      if (tool === 'coverage.report' || /\u52a0\u8f7d\u8986\u76d6\u7387|load coverage/.test(lower)) {
        await runLoadCoverage();
      } else if (tool === 'rules.ingest' || /\u6444\u53d6\u89c4\u5219|ingest rules/.test(lower)) {
        await runIngestRules();
      } else if (tool === 'ci.generate' || /\u751f\u6210 ci|\u751f\u6210ci|generate ci/.test(lower)) {
        await runCiGenerate();
      } else if (tool === 'ci.validate' || /\u6821\u9a8c ci|validate ci/.test(lower)) {
        await runCiValidate();
      } else if (tool === 'git.install_hooks' || /\u5b89\u88c5\u94a9\u5b50|install hooks/.test(lower)) {
        await runInstallHooks();
      } else if (tool === 'env.prepare' || /\u51c6\u5907\u73af\u5883|prepare env/.test(lower)) {
        await runEnvPrepare();
      } else if (tool === 'rules.enforce' || /\u5e94\u7528\u95e8\u7981|\u751f\u6210\u95e8\u7981|enforce/.test(lower)) {
        await runRulesEnforce();
      } else if (tool === 'compliance.commitment' || /\u5408\u89c4\u627f\u8bfa|compliance/.test(lower)) {
        await runCompliance();
      } else if (tool === 'plan.set' || /\u8ba1\u5212\s*\u8bbe\u7f6e|plan set|\u8ba1\u5212[:\uff1a]/.test(lower)) {
        const mSt = /\u72b6\u6001\s*[:=]\s*(\u8fdb\u884c\u4e2d|in_progress|\u5b8c\u6210|done|planned)/i.exec(text);
        const stMap: any = { '\u8fdb\u884c\u4e2d':'in_progress', '\u5b8c\u6210':'done' };
        const status = mSt ? (stMap[mSt[1]] || mSt[1]) : undefined;
        const mCur = /\u5f53\u524d(\u6b65\u9aa4)?\s*[:=]\s*([^;\uff0c]+)/i.exec(text);
        const current = mCur ? mCur[2].trim() : undefined;
        const mNext = /(\u4e0b\u4e00\u6b65|next)\s*[:=]\s*([^;\uff0c]+)/i.exec(text);
        const next = mNext ? mNext[2].trim() : undefined;
        const args:any = {}; if (status) args.status = status; if (current) args.current = current; if (next) args.next = next;
        if (Object.keys(args).length === 0) {
          await vscode.commands.executeCommand('mcpRulesAssistant.planSet');
        } else {
          await client.request('tools/call', { name: 'plan.set', arguments: args });
          vscode.window.showInformationMessage('Plan updated');
        }
      } else if (tool === 'fs.apply_patch' || /\u53d7\u63a7\u5199\u5165|guarded write/.test(lower)) {
        await vscode.commands.executeCommand('mcpRulesAssistant.fsApplyPatch');
      } else if (tool === 'rules.onboard' || /\u521d\u59cb\u5316\u89c4\u5219|\u89c4\u5219\u5f15\u5bfc|setup rules|questionnaire/.test(lower)) {
        await client.request('tools/call', { name: 'rules.onboard', arguments: {} });
        vscode.window.showInformationMessage('\u5df2\u6267\u884c\u89c4\u5219\u5f15\u5bfc\uff08\u9ed8\u8ba4\u53c2\u6570\uff09');
      } else {
        vscode.window.showInformationMessage('\u5df2\u6267\u884c\uff1a' + tool);
      }
      
      // \u5b58\u5386\u53f2
      const h = context.workspaceState.get<string[]>('ruleflow.nl.history') || [];
      const nh = [text, ...h.filter(x=>x!==text)].slice(0, 10);
      await context.workspaceState.update('ruleflow.nl.history', nh);
    } catch (e: any) {
      vscode.window.showErrorMessage('\u6267\u884c\u81ea\u7136\u8bed\u8a00\u547d\u4ee4\u5931\u8d25\uff1a' + String(e));
    }
  }));

  // License: Activate (choose file and call tool)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseActivate', async () => {
    try {
      client.start(context);
      const pick = await vscode.window.showOpenDialog({ canSelectMany: false, openLabel: '\u9009\u62e9\u8bb8\u53ef\u6587\u4ef6 (JSON)' });
      if (!pick || !pick[0]) { return; }
      const path = pick[0].fsPath;
      await client.request('tools/call', { name: 'license.activate', arguments: { path } });
      vscode.window.showInformationMessage('License \u5df2\u6fc0\u6d3b');
    } catch (e:any) {
      vscode.window.showErrorMessage('\u6fc0\u6d3b\u5931\u8d25\uff1a' + String(e));
    }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.licenseVerify', async () => {
    try {
      client.start(context);
      const res = await client.request('tools/call', { name: 'license.verify', arguments: {} });
      const lic = res && (res.license || res);
      let msg = '\u672a\u627e\u5230\u8bb8\u53ef';
      try {
        const exp = lic && lic.expires; const ok = lic && lic.ok;
        if (exp) {
          const days = Math.ceil((new Date(exp).getTime() - Date.now()) / (1000*3600*24));
          msg = `许可状态：${ok? '\u6709\u6548' : '\u65e0\u6548'}；到期：${exp}（剩余 ${days} 天）`;
        }
      } catch {}
      vscode.window.showInformationMessage(msg);
    } catch (e:any) {
      vscode.window.showErrorMessage('\u6821\u9a8c\u5931\u8d25\uff1a' + String(e));
    }
  }));

  // Backend Doctor: ensure venv/server ready and clear fake mode if needed
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.backendDoctor', async () => {
    try {
      // Try to start backend first (may trigger autoprep)
      try { client.start(context); } catch {}
      const sleep = (ms:number)=>new Promise(r=>setTimeout(r, ms));
      await sleep(300);
      const ws = getWorkspaceRoot() || process.cwd();
      const venvPy = process.platform === 'win32'
        ? path.join(ws, '.mcp', 'venv', 'Scripts', 'python.exe')
        : path.join(ws, '.mcp', 'venv', 'bin', 'python');
      const ensureVenv = async () => {
        if (!fs.existsSync(venvPy)) {
          await new Promise<void>((resolve)=>{
            try {
              const creator = (process.env.MCP_PYTHON_BIN && process.env.MCP_PYTHON_BIN.trim())
                ? process.env.MCP_PYTHON_BIN.trim()
                : (process.platform === 'win32' ? 'python' : 'python3');
              const p = spawn(creator, ['-m', 'venv', path.join(ws, '.mcp', 'venv')], { cwd: ws });
              p.on('close', ()=>resolve()); p.on('error', ()=>resolve());
            } catch { resolve(); }
          });
        }
      };
      await ensureVenv();
      const py = fs.existsSync(venvPy) ? venvPy : (process.platform==='win32' ? 'python' : 'python3');
      const run = (args: string[]) => new Promise<{code:number, out:string, err:string}>((resolve)=>{
        try {
          const venvBinForPath = process.platform === 'win32'
            ? path.join(ws, '.mcp', 'venv', 'Scripts')
            : path.join(ws, '.mcp', 'venv', 'bin');
          const env = { ...process.env } as NodeJS.ProcessEnv;
          try {
            const oldPath = String(process.env.PATH || '');
            env.PATH = (fs.existsSync(venvBinForPath) ? (venvBinForPath + path.delimiter) : '') + oldPath;
            env.PYTHONUNBUFFERED = '1';
            env.PYTHONIOENCODING = 'utf-8';
          } catch {}
          const p = spawn(py, args, { cwd: ws, env });
          let out = '', err = '';
          p.stdout.on('data', d=> out += String(d||''));
          p.stderr.on('data', d=> err += String(d||''));
          p.on('close', (code)=> resolve({code: code??1, out, err}));
          p.on('error', ()=> resolve({code: 1, out:'', err:'spawn error'}));
        } catch { resolve({code:1, out:'', err:'spawn exception'}); }
      });
      // Run doctor (auto-fix, clear fake)
      const res = await run(['-m', 'mcp_rules_assistant.cli', 'doctor', '--fix', '--clear-fake']);
      if (res.code === 0 && res.out.trim()) {
        try {
          const obj = JSON.parse(res.out.trim());
          const ok = !!obj.ok;
          vscode.window.showInformationMessage(`Backend Doctor ${ok? 'OK' : 'issues found'} — actions: ${(obj.actions||[]).join(', ')}`);
        } catch {
          vscode.window.showInformationMessage('Backend Doctor completed.');
        }
      } else {
        vscode.window.showWarningMessage('Backend Doctor encountered issues: ' + (res.err||'unknown'));
      }
      // Restart backend after fixes
      try { client.start(context); } catch {}
    } catch (e:any) {
      vscode.window.showErrorMessage('Backend Doctor failed: ' + String(e));
    }
  }));

  // Prepare environment (create venv + install basics) — fallback command for webview
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.envPrepareInstall', async () => {
    try {
      client.start(context);
      await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
      vscode.window.showInformationMessage('已创建并安装基础环境 (.mcp/venv)');
    } catch (e:any) {
      vscode.window.showErrorMessage('env.prepare 执行失败：' + String(e));
    }
  }));

  // Panel diagnostics fallback command — generate diagnostics without relying on webview message transport
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.panelDiag', async () => {
    try {
      client.start(context);
      const ws = getWorkspaceRoot();
      if (!ws) { vscode.window.showWarningMessage('No workspace'); return; }
      const diag: any = { time: new Date().toISOString(), workspace: ws, strict: String(process.env.MCP_STRICT_ISOLATION||''), projectRootEnv: String(process.env.MCP_PROJECT_ROOT||'') };
      try { const ext = vscode.extensions.getExtension('ruleflow.mcp-rules-assistant'); diag.version = (ext && (ext.packageJSON as any).version) || ''; } catch {}
      try { diag.env = await client.request('tools/call', { name: 'env.diagnose', arguments: {} }); } catch {}
      try { diag.audit = await client.request('tools/call', { name: 'security.audit_report', arguments: {} }); } catch {}
      try {
        const uriE = vscode.Uri.file(ws + '/.mcp/dashboard/cmd_events.jsonl');
        const data = await vscode.workspace.fs.readFile(uriE);
        const text = Buffer.from(data).toString('utf8');
        const lines = text.split(/\r?\n/).filter(Boolean); diag.events_tail = lines.slice(-120);
      } catch {}
      const outUri = vscode.Uri.file(ws + '/.mcp/dashboard/panel_diag.json');
      const enc = new TextEncoder();
      await vscode.workspace.fs.writeFile(outUri, enc.encode(JSON.stringify(diag, null, 2)));
      try { const doc = await vscode.workspace.openTextDocument(outUri); await vscode.window.showTextDocument(doc, { preview: false }); } catch {}
      vscode.window.showInformationMessage('已写入诊断：.mcp/dashboard/panel_diag.json');
    } catch (e:any) {
      vscode.window.showErrorMessage('生成诊断失败：' + String(e));
    }
  }));

  // Force re-install to remote (Dev Container/SSH/WSL)
  context.subscriptions.push(vscode.commands.registerCommand('mcpRulesAssistant.installRemote', async () => {
    try { await context.workspaceState.update('ruleflow.autoInstallRemoteTried', false); } catch {}
    try {
      const ok = await autoInstallToRemote(context);
      if (!ok) {
        vscode.window.showWarningMessage('安装到远程失败或未触发（可能当前不在远程窗口）。');
      }
    } catch (e:any) {
      vscode.window.showErrorMessage('安装到远程失败：' + String(e));
    }
  }));
}

export function deactivate() {}

async function runShell(cmd: string, args: string[], cwd?: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { cwd, shell: process.platform === 'win32' });
    let stderr = '';
    p.stderr.on('data', d => stderr += d.toString());
    p.on('close', (code) => {
      if (code === 0) resolve(); else reject(new Error(stderr || `${cmd} exited with ${code}`));
    });
  });
}

// --- Auto-install helper: ensure this extension is installed in remote (Dev Container/SSH) ---
async function autoInstallToRemote(context: vscode.ExtensionContext): Promise<boolean> {
  try {
    // Only meaningful when connected to a remote workspace (e.g. dev-container)
    if (!vscode.env.remoteName) return false;

    // Avoid repeated attempts in this window
    const tried = !!context.workspaceState.get('ruleflow.autoInstallRemoteTried');
    if (tried) return false;
    await context.workspaceState.update('ruleflow.autoInstallRemoteTried', true);

    const ws = getWorkspaceRoot();
    if (!ws) return false;

    // 1) Locate a VSIX we can use:
    //    a) Prefer a prebuilt artifact in the workspace (extensions/artifacts/*.vsix)
    //    b) Otherwise, try to package from the installed extension folder (extRoot)
    const extRoot = context.extensionUri.fsPath;

    const listVsixInDir = (dir: string): string | null => {
      try {
        const files = fs.readdirSync(dir).filter(f => /mcp-rules-assistant-.*\.vsix$/i.test(f));
        if (!files.length) return null;
        // pick the newest by mtime
        let best = files[0];
        let bestT = 0;
        for (const f of files) {
          const st = fs.statSync(path.join(dir, f));
          const t = st.mtimeMs || 0;
          if (t > bestT) { bestT = t; best = f; }
        }
        return path.join(dir, best);
      } catch { return null; }
    };

    // a) Workspace artifact folder
    let vsixPath = listVsixInDir(path.join(ws, 'extensions', 'artifacts'));

    // b) Installed extension folder
    const listVsixInExtRoot = () => listVsixInDir(extRoot);
    if (!vsixPath) {
      vsixPath = listVsixInExtRoot();
    }
    if (!vsixPath) {
      try {
        // Try "npm run package" (uses @vscode/vsce) in the extension folder
        await runShell(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'package'], extRoot);
        vsixPath = listVsixInExtRoot();
      } catch (e) {
        // Best-effort fallback to npx vsce
        try {
          await runShell(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['-y', 'vsce', 'package', '--no-dependencies'], extRoot);
          vsixPath = listVsixInExtRoot();
        } catch {}
      }
    }
    if (!vsixPath || !fs.existsSync(vsixPath)) {
      // Fallback: install from Marketplace by extension identifier (requires network)
      try {
        await vscode.commands.executeCommand('workbench.extensions.installExtension', 'ruleflow.mcp-rules-assistant');
        vscode.window.showInformationMessage('已从 Marketplace 自动安装到容器，正在重载窗口以启用扩展…');
        try { await vscode.commands.executeCommand('workbench.action.reloadWindow'); } catch {}
        return true;
      } catch (e:any) {
        vscode.window.showWarningMessage('无法自动打包 VSIX，且从 Marketplace 安装失败：' + String(e));
        return false;
      }
    }

    // 2) Copy VSIX into remote workspace path: .mcp/ide/
    const remoteRoot = vscode.workspace.workspaceFolders?.[0]?.uri;
    if (!remoteRoot) return false;
    const remoteIdeDir = vscode.Uri.joinPath(remoteRoot, '.mcp', 'ide');
    try { await vscode.workspace.fs.createDirectory(remoteIdeDir); } catch {}
    const remoteVsix = vscode.Uri.joinPath(remoteIdeDir, path.basename(vsixPath));
    try {
      const data = fs.readFileSync(vsixPath);
      await vscode.workspace.fs.writeFile(remoteVsix, data);
    } catch (e:any) {
      vscode.window.showWarningMessage('写入容器 VSIX 失败：' + String(e));
      return false;
    }

    // 3) Install the VSIX into remote extension host
    try {
      await vscode.commands.executeCommand('workbench.extensions.installExtension', remoteVsix);
      // Reload to activate remote side
      vscode.window.showInformationMessage('已自动安装到容器，正在重载窗口以启用扩展…');
      try { await vscode.commands.executeCommand('workbench.action.reloadWindow'); } catch {}
      return true;
    } catch (e:any) {
      vscode.window.showWarningMessage('自动安装到容器失败：' + String(e));
      return false;
    }
  } catch { return false; }
}

// ---- Beginner-first conversational guides (no panel) ----
async function oneClickSetup(context: vscode.ExtensionContext): Promise<void> {
  try {
    client.start(context);
    const ws = getWorkspaceRoot() || process.cwd();
    // 1) Prepare environment (venv + basics)
    try {
      await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } });
      vscode.window.showInformationMessage('环境已准备（.mcp/venv 已就绪）。');
    } catch (e:any) {
      vscode.window.showWarningMessage('准备环境出现问题：' + String(e));
    }
    // 2) Ingest rules (best-effort default)
    try {
      const defaultPaths: string[] = [];
      try { if (require('fs').existsSync(require('path').join(ws, 'README.md'))) defaultPaths.push('README.md'); } catch {}
      try { if (require('fs').existsSync(require('path').join(ws, 'docs'))) defaultPaths.push('docs/'); } catch {}
      const paths = defaultPaths.length ? defaultPaths : ['README.md'];
      await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } });
      vscode.window.showInformationMessage('已摄取规则：' + paths.join(', '));
    } catch (e:any) {
      vscode.window.showWarningMessage('摄取规则失败：' + String(e));
    }
    // 3) Minimal gate: config/CI suggestion + status update
    try {
      await client.request('tools/call', { name: 'ci.generate', arguments: {} });
    } catch {}
    try { await vscode.commands.executeCommand('mcpRulesAssistant.statusUpdate'); } catch {}
    vscode.window.showInformationMessage('一键设置完成。建议：运行测试以生成 coverage.xml 后再查看弱项与 near 列表。');
  } catch (e:any) {
    vscode.window.showErrorMessage('一键设置失败：' + String(e));
  }
}

async function newbieGuide(context: vscode.ExtensionContext): Promise<void> {
  try {
    client.start(context);
    // Step 1: Scenario/Complexity/Dev Mode
    const pickScenario = await vscode.window.showQuickPick([
      { label: '个人 / Personal', val: 'personal' },
      { label: '专业 / Pro', val: 'pro' },
      { label: '企业 / Enterprise', val: 'enterprise' },
      { label: '机构 / Institution', val: 'institution' },
    ], { title: '选择应用场景 / Scenario' });
    if (!pickScenario) return;
    const pickComplexity = await vscode.window.showQuickPick([
      { label: '简 / Small', val: 'small' },
      { label: '中 / Medium', val: 'medium' },
      { label: '大 / Large', val: 'large' },
    ], { title: '选择复杂度 / Complexity' });
    if (!pickComplexity) return;
    const pickMode = await vscode.window.showQuickPick([
      { label: 'TDD（测试先行）', val: 'tdd' },
      { label: '标准 / Standard', val: 'standard' },
      { label: '严格 / Strict', val: 'strict' },
    ], { title: '选择开发模式 / Dev Mode' });
    if (!pickMode) return;
    // Apply thresholds
    try {
      const out = await client.request('tools/call', { name: 'rules.onboard', arguments: { scenario: pickScenario.val, complexity: pickComplexity.val, devMode: pickMode.val, apply: true } });
      vscode.window.showInformationMessage('已应用规则引导（Onboard）。');
    } catch (e:any) {
      vscode.window.showWarningMessage('规则引导失败：' + String(e));
    }
    // Step 2: Prepare environment
    const prep = await vscode.window.showQuickPick(['创建并安装 / Create+Install', '跳过 / Skip'], { title: '准备环境 / Prepare Environment' });
    if (prep && prep.startsWith('创建')) {
      try { await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } }); vscode.window.showInformationMessage('已准备环境。'); } catch (e:any) { vscode.window.showWarningMessage('准备环境失败：' + String(e)); }
    }
    // Step 3: Ingest rules
    const ingest = await vscode.window.showQuickPick(['快速摄取（README.md, docs/）', '自定义路径', '跳过'], { title: '摄取规则 / Ingest Rules' });
    if (ingest && ingest.startsWith('快速')) {
      try { await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: ['README.md', 'docs/'] } }); vscode.window.showInformationMessage('规则摄取完成。'); } catch (e:any) { vscode.window.showWarningMessage('摄取失败：' + String(e)); }
    } else if (ingest && ingest.startsWith('自定义')) {
      const ip = await vscode.window.showInputBox({ title: '输入要摄取的文件或目录（逗号分隔）', placeHolder: 'rules.md, docs/rules' });
      if (ip) {
        const paths = ip.split(',').map(s=>s.trim()).filter(Boolean);
        try { await client.request('tools/call', { name: 'rules.ingest', arguments: { paths } }); vscode.window.showInformationMessage('规则摄取完成。'); } catch (e:any) { vscode.window.showWarningMessage('摄取失败：' + String(e)); }
      }
    }
    // Step 4: Minimal gate / CI
    const ci = await vscode.window.showQuickPick(['生成 CI', '安装钩子', '两者都做', '跳过'], { title: '持续集成与钩子 / CI & Hooks' });
    try {
      if (ci === '生成 CI' || ci === '两者都做') { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI 已生成。'); }
      if (ci === '安装钩子' || ci === '两者都做') { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('Git hooks 已安装。'); }
    } catch (e:any) { vscode.window.showWarningMessage('CI/Hooks 步骤遇到问题：' + String(e)); }
    // Finish
    vscode.window.showInformationMessage('向导完成。建议：运行测试生成 coverage.xml，然后使用“Load Coverage”查看薄弱点。');
  } catch (e:any) {
    vscode.window.showErrorMessage('向导失败：' + String(e));
  }
}

async function askCommand(context: vscode.ExtensionContext): Promise<void> {
  try {
    client.start(context);
    const text = await vscode.window.showInputBox({ title: '自然语言指令 / Natural Command', placeHolder: '例如：摄取规则 README.md, docs/ / 加载覆盖率 / 生成 CI / 安装钩子' });
    if (!text) return;
    // Delegate to server-side NL mapping first
    try {
      const res = await client.request('tools/call', { name: 'nl.command', arguments: { text } });
      const tool = (res && (res.parsed && res.parsed.tool)) || '';
      if (tool) { vscode.window.showInformationMessage('已执行：' + tool); return; }
    } catch {}
    // Lightweight local mapping fallback
    const lower = text.toLowerCase();
    if (/摄取|ingest/.test(lower)) { await client.request('tools/call', { name: 'rules.ingest', arguments: { paths: ['README.md','docs/'] } }); vscode.window.showInformationMessage('规则摄取完成。'); return; }
    if (/覆盖率|coverage|load coverage/.test(lower)) { await vscode.commands.executeCommand('mcpRulesAssistant.loadCoverage'); return; }
    if (/ci/.test(lower) && /生成|generate/.test(lower)) { await client.request('tools/call', { name: 'ci.generate', arguments: {} }); vscode.window.showInformationMessage('CI 已生成。'); return; }
    if (/钩子|hooks|install hooks/.test(lower)) { await client.request('tools/call', { name: 'git.install_hooks', arguments: {} }); vscode.window.showInformationMessage('Git hooks 已安装。'); return; }
    if (/准备|prepare|env/.test(lower)) { await client.request('tools/call', { name: 'env.prepare', arguments: { create: true, install: true } }); vscode.window.showInformationMessage('环境已准备。'); return; }
    vscode.window.showInformationMessage('已记录你的指令：' + text);
  } catch (e:any) {
    vscode.window.showErrorMessage('执行自然语言指令失败：' + String(e));
  }
}
