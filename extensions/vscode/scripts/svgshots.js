#!/usr/bin/env node
const sharp = require('sharp');
const path = require('path');
const fs = require('fs');
async function shot(svg, png) {
  const src = path.resolve(__dirname, '..', 'images', svg);
  const out = path.resolve(__dirname, '..', 'images', png);
  await sharp(src).resize(1280, 720, { fit: 'contain', background: { r:11, g:15, b:26, alpha:1 } }).png().toFile(out);
  console.log('[svgshots] wrote', out);
}
(async()=>{
  await shot('screenshot1.svg', 'screenshot1.png');
  try {
    await shot('screenshot2.svg', 'screenshot2.png');
  } catch (e) {
    console.warn('[svgshots] fallback: copy screenshot1.png to screenshot2.png due to:', String(e).slice(0,120));
    const fs = require('fs');
    const p1 = path.resolve(__dirname, '..', 'images', 'screenshot1.png');
    const p2 = path.resolve(__dirname, '..', 'images', 'screenshot2.png');
    fs.copyFileSync(p1, p2);
  }
})().catch(e=>{ console.error(e); process.exit(1); });
