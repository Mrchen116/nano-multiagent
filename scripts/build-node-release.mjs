/** Build the installable Node payload from an explicit runtime allowlist. */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = join(root, 'dist/node-release');
await mkdir(output, { recursive: true });
const stage = await mkdtemp(join(output, '.stage-'));
async function copy(relative) {
  await mkdir(dirname(join(stage, relative)), { recursive: true });
  await cp(join(root, relative), join(stage, relative), { dereference: false });
}
try {
  for (const file of ['package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml']) await copy(file);
  for (const area of ['apps', 'packages']) {
    for (const entry of await readdir(join(root, area), { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const base = `${area}/${entry.name}`;
      try { await copy(`${base}/package.json`); }
      catch (error) { if (error.code === 'ENOENT') continue; throw error; }
      // Only compiler outputs belong in the payload; never copy a checkout or node_modules.
      async function compiled(relative) {
        for (const item of await readdir(join(root, relative), { withFileTypes: true })) {
          if (item.isDirectory()) await compiled(`${relative}/${item.name}`);
          else if (item.isFile() && /\.(js|ts|map|sql)$/.test(item.name)) await copy(`${relative}/${item.name}`);
        }
      }
      try { await compiled(`${base}/lib`); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  }
  const assets = execFileSync('git', ['ls-files', '-z', '--', 'packages/dsh-integration/assets', 'packages/dsh-integration/cordis.patch.yml', 'packages/personal-assistant/assets'], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
  for (const file of assets) await copy(file);
  await readFile(join(stage, 'apps/node/lib/cli.js'));
  const archive = join(output, 'nano-node.tgz');
  execFileSync('tar', ['-czf', archive, '-C', stage, '.']);
  const sha256 = createHash('sha256').update(await readFile(archive)).digest('hex');
  const revision = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
  await writeFile(join(output, 'manifest.json'), JSON.stringify({ version: revision, sha256, package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0' }, null, 2) + '\n');
  console.log(`Node installer package ready: ${revision} (${sha256.slice(0, 12)})`);
} finally {
  await rm(stage, { recursive: true, force: true });
}
