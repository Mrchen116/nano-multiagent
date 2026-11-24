// ZIPs contain regular files only. Recreate the locked pnpm graph with local user junctions.
import { readFileSync, readdirSync, mkdirSync, symlinkSync, linkSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [action, stage, final, runtime, app] = process.argv.slice(2);
function link(directory, name, target) {
  const path = join(directory, name);
  mkdirSync(dirname(path), { recursive: true });
  symlinkSync(resolve(target), path, 'junction');
}
function mirror(source, dest) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(source, { withFileTypes: true })) {
    if (entry.isDirectory()) mirror(join(source, entry.name), join(dest, entry.name));
    else linkSync(join(source, entry.name), join(dest, entry.name));
  }
}
if (action === 'runtime') {
  const edges = JSON.parse(readFileSync(join(stage, 'dependencies.json'), 'utf8'));
  for (const [path, target] of Object.entries(edges)) link(stage, path, join(final, target));
} else if (action === 'version') {
  mirror(app, stage);
  link(stage, 'runtime', runtime);
  const edges = JSON.parse(readFileSync(join(app, 'workspaces.json'), 'utf8'));
  for (const [path, target] of Object.entries(edges)) link(stage, path, join(final, target));
} else if (action === 'verify') {
  const at = createRequire(join(stage, 'apps/node/lib/cli.js'));
  await import(pathToFileURL(at.resolve('@nano/dsh-integration/client')).href);
  const dsh = createRequire(at.resolve('@nano/dsh-integration/client'));
  for (const name of ['@deepseek-ai/dsh', '@deepseek-ai/dsh-base']) dsh.resolve(name + '/package.json');
  await import(pathToFileURL(at.resolve('@nano/personal-assistant')).href);
} else {
  throw new Error('Unknown layout operation');
}
