// Build the design-only native component demonstration into a temporary directory.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
let root = here;
while (!fs.existsSync(path.join(root, 'pnpm-workspace.yaml'))) root = path.dirname(root);
const require = createRequire(path.join(root, 'packages/dsh-trajectory-viewer/package.json'));
const { build } = require('esbuild');
const out = '/tmp/feat589-native-prototype';
fs.mkdirSync(out, { recursive: true });
fs.copyFileSync(path.join(here, 'prototype.html'), path.join(out, 'prototype.html'));
await build({
  stdin: { contents: fs.readFileSync(path.join(here, 'prototype-native.jsx'), 'utf8'),
    resolveDir: path.join(root, 'packages/dsh-trajectory-viewer/src'), loader: 'jsx' },
  bundle: true, format: 'esm', platform: 'browser', outfile: path.join(out, 'prototype-native.js'),
  minify: true, define: { 'process.env.NODE_ENV': '"production"' },
  loader: { '.woff2': 'file', '.woff': 'file', '.ttf': 'file' },
});
console.log(out);
