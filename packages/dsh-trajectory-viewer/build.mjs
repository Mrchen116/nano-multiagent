import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, 'dist');
const version = '0.2.2-rc.5';
const modules = new Map();
// Published /client entries are registration bundles, not ES modules. Copy
// these unchanged; only the shell and singleton modules enter esbuild.
function visit(id) {
  id = id.replace(/\/client$/, '');
  if (modules.has(id)) return;
  const packagePath = require.resolve(`${id}/package.json`);
  const directory = path.dirname(packagePath);
  const metadata = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
  if (id !== '@nano/trajectory-ui' && metadata.version !== version) throw new Error(`Native viewer version mismatch: ${id}`);
  const clientExport = metadata.exports?.['./client'];
  const clientEntryRel = typeof clientExport === 'string'
    ? clientExport
    : (clientExport?.browser ?? clientExport?.default ?? './lib/client.js');
  const clientEntry = path.join(directory, clientEntryRel);
  const source = fs.readFileSync(clientEntry, 'utf8');
  const external = [...new Set([...source.matchAll(/require\("([^"]+)"\)/g)]
    .map(match => match[1]).filter(name => !name.includes('${')))];
  modules.set(id, { directory, metadata, external, clientEntry });
  for (const dependency of external) {
    if (dependency.startsWith('@deepseek-ai/') && dependency.endsWith('/client')) visit(dependency);
  }
}
for (const name of ['modules', 'connection', 'ui-renderer', 'ui-conversation', 'ui-session',
  'ui-attachment', 'locale', 'ui-theme']) visit(`@deepseek-ai/dsh-client-${name}`);
for (const name of ['api-session-controller', 'api-gateway', 'typert-registry']) visit(`@deepseek-ai/dsh-${name}`);
visit('@nano/trajectory-ui');
fs.rmSync(path.join(dist, 'plugins', '@deepseek-ai', 'dsh-client-ui-trajectory'), { recursive: true, force: true });
fs.mkdirSync(dist, { recursive: true });
const manifest = { rev: version, modules: [], plugins: [] };
for (const [id, { directory, metadata, external, clientEntry }] of modules) {
  const destination = path.join(dist, 'plugins', id);
  fs.mkdirSync(destination, { recursive: true });
  fs.copyFileSync(clientEntry, path.join(destination, 'client.js'));
  for (const file of fs.readdirSync(path.join(directory, 'lib'))) {
    if (/^client.*\.js$/.test(file) && file !== 'client.js' && file !== 'client.browser.js' && !file.startsWith('client.node.')) {
      fs.copyFileSync(path.join(directory, 'lib', file), path.join(destination, file));
    }
  }
  manifest.modules.push({ id, url: `plugins/??${id}/client.js&rev=${version}`, rev: version,
    inject: metadata.dsh?.client?.inject ?? [], external });
}
fs.writeFileSync(path.join(dist, 'manifest.json'), JSON.stringify(manifest));
const result = await build({
  absWorkingDir: root, entryPoints: ['src/boot.jsx'], outdir: dist, bundle: true,
  format: 'esm', platform: 'browser', splitting: true, minify: true, metafile: true,
  define: { 'process.env.NODE_ENV': '"production"', '__NANO_TRAJECTORY_MANIFEST__': JSON.stringify(manifest) },
  loader: { '.woff2': 'file', '.woff': 'file', '.ttf': 'file', '.css': 'css' },
  logLevel: 'info',
});

// Discover static dependencies at build time, before the iframe downloads boot.js.
// Registration bundles are preloaded, but still executed unchanged by the loader.
const preloads = manifest.modules.map(entry => `<link rel="preload" as="script" href="./${entry.url.replace('plugins/??', 'plugins/').replace('&rev=', '?rev=')}" crossorigin="anonymous">`);
const staticFiles = new Set();
function preloadImports(file) {
  for (const dependency of result.metafile.outputs[file]?.imports ?? []) {
    if (dependency.external || dependency.kind !== 'import-statement' || staticFiles.has(dependency.path)) continue;
    staticFiles.add(dependency.path);
    preloadImports(dependency.path);
  }
}
const entry = Object.keys(result.metafile.outputs).find(file => file.endsWith('/boot.js'));
preloadImports(entry);
for (const file of staticFiles) preloads.push(`<link rel="modulepreload" href="./${path.basename(file)}" crossorigin="anonymous">`);
fs.writeFileSync(path.join(dist, 'index.html'), fs.readFileSync(path.join(root, 'index.html'), 'utf8').replace('</head>', preloads.join('\n') + '\n</head>'));
