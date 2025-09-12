#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
function parseWorkspaceFromArgs(raw) {
  if (!raw) return null;
  const parts = String(raw).split(',').map(s=>s.trim()).filter(Boolean);
  if (!parts.length) return null;
  const last = parts[parts.length - 1];
  if (last.startsWith('/')) return last;
  return null;
}
function rimraf(p) {
  try {
    if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
  } catch {}
}
function ensureDir(p) {
  try { fs.mkdirSync(p, { recursive: true }); } catch {}
}
function main() {
  const raw = process.env.MCP_VSCODE_TEST_ARGS || '';
  const ws = parseWorkspaceFromArgs(raw) || path.resolve(process.cwd(), '.test-fixture');
  ensureDir(ws);
  // clean noisy dirs
  rimraf(path.join(ws, '.mcp'));
  rimraf(path.join(ws, '.github'));
  // recreate minimal dirs
  ensureDir(path.join(ws, '.mcp', 'dashboard'));
  ensureDir(path.join(ws, '.github', 'workflows'));
  // fake mode sentinel to avoid backend
  try { fs.writeFileSync(path.join(ws, '.mcp', 'dashboard', 'fake_mode'), '1'); } catch {}
  // ensure README exists for smoke test
  try {
    const readme = path.join(ws, 'README.md');
    if (!fs.existsSync(readme)) fs.writeFileSync(readme, '# Fixture README\n', 'utf-8');
  } catch {}
  console.log('[prep-workspace] workspace =', ws);
}
main();
