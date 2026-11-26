// Recreate the locked pnpm graph across macOS and Windows using directory symlinks/junctions and hardlinks.
import { readFileSync, readdirSync, mkdirSync, symlinkSync, linkSync, copyFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [action, stage, final, runtime, app] = process.argv.slice(2);
const linkType = process.platform === 'win32' ? 'junction' : 'dir';

function link(directory, name, target) {
  const path = join(directory, name);
  mkdirSync(dirname(path), { recursive: true });
  symlinkSync(resolve(target), path, linkType);
}

function mirror(source, dest) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(source, { withFileTypes: true })) {
    const srcPath = join(source, entry.name);
    const dstPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      mirror(srcPath, dstPath);
    } else {
      try {
        linkSync(srcPath, dstPath);
      } catch {
        copyFileSync(srcPath, dstPath);
      }
    }
  }
}

if (action === 'runtime') {
  const edges = JSON.parse(readFileSync(join(stage, 'dependencies.json'), 'utf8'));
  for (const [path, target] of Object.entries(edges)) {
    link(stage, path, join(final, target));
  }
} else if (action === 'version') {
  mirror(app, stage);
  link(stage, 'runtime', runtime);
  const edges = JSON.parse(readFileSync(join(app, 'workspaces.json'), 'utf8'));
  for (const [path, target] of Object.entries(edges)) {
    link(stage, path, join(final, target));
  }
} else if (action === 'verify') {
  const at = createRequire(join(stage, 'apps/node/lib/cli.js'));
  await import(pathToFileURL(at.resolve('@nano/dsh-integration/client')).href);
  const dsh = createRequire(at.resolve('@nano/dsh-integration/client'));
  for (const name of ['@deepseek-ai/dsh', '@deepseek-ai/dsh-base']) {
    dsh.resolve(name + '/package.json');
  }
  await import(pathToFileURL(at.resolve('@nano/personal-assistant')).href);
} else {
  throw new Error('Unknown layout operation');
}
