/** Upload one built candidate, verify it anonymously, then promote its IM manifest.
 *
 * Inputs: RELEASE_VERSION=X.Y.Z, RELEASE_CHANGES and RELEASE_UPGRADE_NOTES.
 * Usage: node scripts/publish-node-release.mjs [candidate-directory]
 * Run from the clean source checkout matching the candidate, with release-authorized gh.
 * Existing Release tags are never updated; deployment is a separate operation.
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

// The workflow keeps this publisher outside the selected source checkout.
const root = process.cwd();
const directory = resolve(process.argv[2] ?? join(root, 'dist/node-release'));
const repository = 'Mrchen116/nano-multiagent';
const version = process.env.RELEASE_VERSION;
if (!version || !/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/.test(version))
  throw new Error('RELEASE_VERSION must be an explicit X.Y.Z version (without v prefix)');
const changes = process.env.RELEASE_CHANGES?.trim();
const upgradeNotes = process.env.RELEASE_UPGRADE_NOTES?.trim();
if (!changes || !upgradeNotes) throw new Error('RELEASE_CHANGES and RELEASE_UPGRADE_NOTES are required');
const candidate = JSON.parse(await readFile(join(directory, 'manifest.candidate.json'), 'utf8'));
const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const tag = `v${version}`;
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
if (candidate.version !== revision || !/^[a-f0-9]{40}$/.test(revision)
  || !/^[a-f0-9]{64}$/.test(candidate.sha256) || candidate.package !== 'nano-node.tgz'
  || candidate.node_major !== 24 || candidate.pnpm_version !== '11.7.0'
  || candidate.download_url !== `https://github.com/${repository}/releases/download/node-${revision}/nano-node.tgz`)
  throw new Error('Candidate manifest must match this checkout and the fixed public Release asset');
const manifest = { ...candidate, version, source_commit: revision,
  download_url: `https://github.com/${repository}/releases/download/${tag}/nano-node.tgz` };
execFileSync('git', ['diff', '--quiet', 'HEAD', '--'], { cwd: root });
const archive = join(directory, candidate.package);
if (hash(await readFile(archive)) !== candidate.sha256) throw new Error('Candidate package checksum does not match');
const metadata = JSON.parse(execFileSync('tar', ['-xOf', archive, './.nano-release.json'], {encoding: 'utf8'}));
if (metadata.source_commit !== revision || metadata.updater_protocol !== 1 || metadata.data_epoch !== 1
    || candidate.source_commit !== revision || candidate.updater_protocol !== 1 || candidate.data_epoch !== 1)
  throw new Error('Candidate package metadata does not match the source and updater protocol');
const visibility = execFileSync('gh', ['repo', 'view', repository, '--json', 'visibility', '--jq', '.visibility'], { encoding: 'utf8' }).trim();
if (visibility !== 'PUBLIC') throw new Error('Installer releases require a public repository');
const notes = [
  '## 本版变化', changes,
  '## 升级说明', upgradeNotes,
  '## 安装包与校验', [
    `- 安装包 [${candidate.package}](${manifest.download_url})`,
    `- 源码提交 [\`${revision}\`](https://github.com/${repository}/commit/${revision})`,
    `- SHA-256 \`${candidate.sha256}\``,
  ].join('\n'),
].join('\n\n');
// gh release create fails if this tag already has a Release; never use upload --clobber.
execFileSync('gh', ['release', 'create', tag, archive, '--repo', repository, '--target', revision,
  '--title', `Nano Node v${version}`, '--notes', notes, '--latest=false'], { stdio: 'inherit' });
const temporary = await mkdtemp(join(directory, '.verify-'));
try {
  const downloaded = join(temporary, 'nano-node.tgz');
  // Disable curl config so publisher credentials cannot mask anonymous access failures.
  execFileSync('curl', ['--disable', '--fail', '--location', '--silent', '--show-error', '--retry', '2',
    '--proto', '=https', '--proto-redir', '=https', manifest.download_url, '-o', downloaded], { stdio: 'inherit' });
  if (hash(await readFile(downloaded)) !== candidate.sha256) throw new Error('Anonymous Release download checksum does not match; IM manifest was not promoted');
  const verified = join(temporary, 'manifest.json');
  await writeFile(verified, JSON.stringify(manifest, null, 2) + '\n');
  await rename(verified, join(directory, 'manifest.json'));
  console.log(`Verified IM manifest ready: ${join(directory, 'manifest.json')}`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
