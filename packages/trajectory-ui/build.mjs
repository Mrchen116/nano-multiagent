import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const root = path.dirname(fileURLToPath(import.meta.url));
const id = '@nano/trajectory-ui';
// Match the official browser module table: React and DSH service/registry
// identities must be shared with the host; pure value helpers may be bundled.
const external = [
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client',
  '@deepseek-ai/cordis', '@deepseek-ai/dsh-client-store',
  '@deepseek-ai/dsh-client-ui-primitives', '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-conversation/client',
];
const result = await build({
  absWorkingDir: root, entryPoints: ['src/client/index.ts'], outfile: 'lib/client.js',
  bundle: true, format: 'cjs', platform: 'browser', external, write: false,
  // This CSS is loaded beside the separately built host: short local class names collide.
  minifyWhitespace: true, minifySyntax: true, minifyIdentifiers: false, define: { 'process.env.NODE_ENV': '"production"' },
  legalComments: 'inline', logLevel: 'info',
});
const script = result.outputFiles.find(file => file.path.endsWith('.js')).text;
const css = result.outputFiles.find(file => file.path.endsWith('.css'))?.text ?? '';
const license = fs.readFileSync(path.join(root, 'LICENSE'), 'utf8');
fs.mkdirSync(path.join(root, 'lib'), { recursive: true });
// The published /client ABI is a loader registration, not an ESM module.
const prefix = `/*! Derived from DeepSeek DSH trajectory UI. ${license} */\n`;
fs.writeFileSync(path.join(root, 'lib/client.js'), prefix + `window.__ModuleLoader__.load({id:${JSON.stringify(id)},factory(require){
const module={exports:{}};const exports=module.exports;
if(!document.querySelector('style[data-plugin="@nano/trajectory-ui"]')){
const style=document.createElement('style');style.dataset.plugin=${JSON.stringify(id)};style.textContent=${JSON.stringify(css)};document.head.appendChild(style);
}
${script}
return module.exports;
}});\n`);
await build({ absWorkingDir: root, entryPoints: ['src/index.ts'], outfile: 'lib/index.js', format: 'esm' });
