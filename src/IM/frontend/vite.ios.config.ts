import { fileURLToPath } from 'node:url';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/** Local WKWebView assets; no Web app shell, login code or prompt generator. */
export default defineConfig({
  root: fileURLToPath(new URL('./src/ios-interactive', import.meta.url)),
  base: './',
  plugins: [react(), {
    name: 'ios-resource-bridge',
    transformIndexHtml: {order: 'post', handler: html => html.replace(/ type="module"/g, '').replace(/ crossorigin/g, '').replace('<script ', '<script defer ')},
    resolveId(source, importer) {
      if (source.endsWith('base-path') && importer?.includes('/open-intelligent-ui/')) {
        return fileURLToPath(new URL('./src/ios-interactive/resources.ts', import.meta.url));
      }
    },
    transform(code, id) {
      if (id.endsWith('/open-intelligent-ui/components/map/basemap.ts')) {
        return 'import nativeWorkerSource from "maplibre-gl/dist/maplibre-gl-worker.mjs?raw";\nconst nativeWorkerURL = URL.createObjectURL(new Blob([nativeWorkerSource], {type: "text/javascript"}));\n' +
          code.replace('lib.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString());', 'lib.setWorkerUrl(nativeWorkerURL);');
      }
    },
    generateBundle() {
      const notices = new Map<string, string>();
      for (const id of this.getModuleIds()) {
        if (!id.includes('/node_modules/')) continue;
        let directory = dirname(id.split('?')[0]);
        while (directory.includes('/node_modules/')) {
          const manifest = join(directory, 'package.json');
          if (existsSync(manifest)) {
            const pkg = JSON.parse(readFileSync(manifest, 'utf8'));
            if (!pkg.name) {directory = dirname(directory); continue;}
            const license = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'license', 'license.txt'].find(name => existsSync(join(directory, name)));
            if (license) notices.set(`${pkg.name}@${pkg.version}`, readFileSync(join(directory, license), 'utf8'));
            break;
          }
          directory = dirname(directory);
        }
      }
      const upstream = readFileSync(fileURLToPath(new URL('./src/features/chat/interactive/open-intelligent-ui/LICENSE', import.meta.url)), 'utf8');
      this.emitFile({type: 'asset', fileName: 'LICENSES.txt', source: `Open Intelligent UI\n${upstream}\n` +
        [...notices].sort(([a], [b]) => a.localeCompare(b)).map(([name, license]) => `\n${name}\n${license}\n`).join('')});
    },
  }],
  build: {
    outDir: fileURLToPath(new URL('../ios/NanoIM/Resources/IntelligentUI', import.meta.url)),
    emptyOutDir: true,
    // Fonts and dynamic icons remain offline and do not require file-origin fetches.
    assetsInlineLimit: Infinity,
    modulePreload: false,
    rollupOptions: {output: {format: 'iife', inlineDynamicImports: true}},
  },
});
