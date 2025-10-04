#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
async function main() {
  const sharp = require('sharp');
  const root = path.resolve(__dirname, '..');
  const src = path.join(root, 'images', 'icon.svg');
  const out = path.join(root, 'images', 'icon-128.png');
  if (!fs.existsSync(src)) {
    console.error('[svg2png] missing', src);
    process.exit(1);
  }
  await sharp(src).resize(128, 128, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toFile(out);
  console.log('[svg2png] wrote', out);
}
main().catch(e => { console.error(e); process.exit(1); });
