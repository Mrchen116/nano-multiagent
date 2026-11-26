/** Upload one built candidate, verify it anonymously, then promote its IM manifest.
 *
 * Inputs: RELEASE_VERSION=X.Y.Z, RELEASE_CHANGES and RELEASE_UPGRADE_NOTES.
 * Usage: node scripts/publish-node-release.mjs [candidate-directory]
 * Run from the clean source checkout matching the candidate, with release-authorized gh.
 * Existing Release tags are never updated; deployment is a separate operation.
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream, existsSync } from 'node:fs';
import { mkdtemp, readFile, rename, rm, stat, writeFile } from 'node:fs/promises';
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
const base = `https://github.com/${repository}/releases/download/${tag}/`;
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
if (candidate.version !== revision || !/^[a-f0-9]{40}$/.test(revision)
  || !/^[a-f0-9]{64}$/.test(candidate.sha256) || candidate.package !== 'nano-node.tgz'
  || candidate.node_major !== 24 || candidate.pnpm_version !== '11.7.0'
  || candidate.download_url !== `https://github.com/${repository}/releases/download/node-${revision}/nano-node.tgz`)
  throw new Error('Candidate manifest must match this checkout and the fixed public Release asset');
const manifest = { ...candidate, version, source_commit: revision,
  download_url: base + 'nano-node.tgz' };
execFileSync('git', ['diff', '--quiet', 'HEAD', '--'], { cwd: root });
const archive = join(directory, candidate.package);
if (hash(await readFile(archive)) !== candidate.sha256) throw new Error('Candidate package checksum does not match');
const metadata = JSON.parse(execFileSync('tar', ['-xOf', archive, './.nano-release.json'], {encoding: 'utf8'}));
if (metadata.source_commit !== revision || metadata.updater_protocol !== 1 || metadata.data_epoch !== 1
    || candidate.source_commit !== revision || candidate.updater_protocol !== 1 || candidate.data_epoch !== 1)
  throw new Error('Candidate package metadata does not match the source and updater protocol');

async function checksum(path) {
  const digest = createHash('sha256');
  for await (const chunk of createReadStream(path)) digest.update(chunk);
  return digest.digest('hex');
}

// Windows lightweight node metadata already names the formal version because its descriptor is itself hashed.
const windowsName = 'manifest.win32-x64.json';
const windowsDirectory = join(directory, 'windows');
const windowsPath = join(windowsDirectory, windowsName);
const windows = existsSync(windowsPath) ? JSON.parse(await readFile(windowsPath, 'utf8')) : null;
if (!windows && existsSync(join(root, 'scripts/build-windows-installer.ps1')))
  throw new Error('The selected source requires its matching Windows build');
const extraAssets = [];
const promotedManifests = [];
if (windows) {
  if (windows.package !== 'windows-x64.json' || windows.platform !== 'win32-x64'
      || windows.version !== version || windows.source_commit !== revision
      || windows.updater_protocol !== 1 || windows.data_epoch !== 1
      || windows.node_major !== 24 || windows.pnpm_version !== '11.7.0'
      || windows.download_url !== base + windows.package || windows.installer?.download_url !== base + 'Crewden-Setup-x64.exe')
    throw new Error('Windows candidate does not match the requested release');
  const descriptor = JSON.parse(await readFile(join(windowsDirectory, windows.package), 'utf8'));
  if (descriptor.version !== version || descriptor.source_commit !== revision || descriptor.launcher_protocol !== 1
      || descriptor.updater_protocol !== 1 || descriptor.data_epoch !== 1
      || descriptor.runtime?.name !== 'windows-runtime-x64.zip' || descriptor.app?.name !== 'windows-app-x64.zip')
    throw new Error('Windows descriptor has an incompatible source or asset layout');
  for (const [name, asset] of [[windows.package, windows], ['Crewden-Setup-x64.exe', windows.installer],
      [descriptor.runtime.name, descriptor.runtime], [descriptor.app.name, descriptor.app]]) {
    const path = join(windowsDirectory, name);
    if ((await stat(path)).size !== asset.size || await checksum(path) !== asset.sha256)
      throw new Error(`Windows asset failed size or SHA-256 verification: ${name}`);
    extraAssets.push({name, path, url: base + name, sha256: asset.sha256});
  }
  promotedManifests.push({name: windowsName, payload: windows});
}

const desktopSpecs = [
  {
    platform: 'desktop-darwin-arm64',
    subdir: 'desktop-darwin-arm64',
    manifestName: 'manifest.desktop-darwin-arm64.json',
    descriptorName: 'desktop-darwin-arm64.json',
    installerName: 'Crewden-Desktop-arm64.dmg',
    runtimeName: 'desktop-runtime-darwin-arm64.tar.gz',
    appName: 'desktop-app-darwin-arm64.tar.gz',
    scriptGate: 'scripts/package-macos-desktop.py',
  },
  {
    platform: 'desktop-win32-x64',
    subdir: 'desktop-win32-x64',
    manifestName: 'manifest.desktop-win32-x64.json',
    descriptorName: 'desktop-win32-x64.json',
    installerName: 'Crewden-Desktop-Setup-x64.exe',
    runtimeName: 'desktop-runtime-win32-x64.tar.gz',
    appName: 'desktop-app-win32-x64.tar.gz',
    scriptGate: 'scripts/build-desktop-windows.ps1',
  },
];

for (const spec of desktopSpecs) {
  const sub = join(directory, spec.subdir);
  const mPath = join(sub, spec.manifestName);
  const dm = existsSync(mPath) ? JSON.parse(await readFile(mPath, 'utf8')) : null;
  if (!dm && existsSync(join(root, spec.scriptGate)))
    throw new Error(`The selected source requires its matching Desktop build (${spec.platform})`);
  if (!dm) continue;
  if (dm.package !== spec.descriptorName || dm.platform !== spec.platform
      || dm.version !== version || dm.source_commit !== revision
      || dm.updater_protocol !== 1 || dm.data_epoch !== 1 || dm.shell_protocol !== 1
      || dm.node_major !== 24 || dm.pnpm_version !== '11.7.0'
      || dm.download_url !== base + dm.package || dm.installer?.download_url !== base + spec.installerName)
    throw new Error(`Desktop candidate (${spec.platform}) does not match the requested release`);
  const descriptor = JSON.parse(await readFile(join(sub, dm.package), 'utf8'));
  if (descriptor.version !== version || descriptor.source_commit !== revision
      || descriptor.updater_protocol !== 1 || descriptor.data_epoch !== 1 || descriptor.shell_protocol !== 1
      || descriptor.runtime?.name !== spec.runtimeName || descriptor.app?.name !== spec.appName)
    throw new Error(`Desktop descriptor (${spec.platform}) has an incompatible source or asset layout`);
  for (const [name, asset] of [[dm.package, dm], [spec.installerName, dm.installer],
      [descriptor.runtime.name, descriptor.runtime], [descriptor.app.name, descriptor.app]]) {
    const path = join(sub, name);
    if ((await stat(path)).size !== asset.size || await checksum(path) !== asset.sha256)
      throw new Error(`Desktop asset failed size or SHA-256 verification: ${name}`);
    extraAssets.push({name, path, url: base + name, sha256: asset.sha256});
  }
  promotedManifests.push({name: spec.manifestName, payload: dm});
}

const visibility = execFileSync('gh', ['repo', 'view', repository, '--json', 'visibility', '--jq', '.visibility'], { encoding: 'utf8' }).trim();
if (visibility !== 'PUBLIC') throw new Error('Installer releases require a public repository');
const notes = [
  '## 本版变化', changes,
  '## 升级说明', upgradeNotes,
  '## 安装包与校验', [
    `- 安装包 [${candidate.package}](${manifest.download_url})`,
    `- 源码提交 [\`${revision}\`](https://github.com/${repository}/commit/${revision})`,
    `- SHA-256 \`${candidate.sha256}\``,
    ...extraAssets.map(({name, url, sha256}) => `- [${name}](${url}) SHA-256 \`${sha256}\``),
  ].join('\n'),
].join('\n\n');
// gh release create fails if this tag already has a Release; never use upload --clobber.
execFileSync('gh', ['release', 'create', tag, archive, ...extraAssets.map(asset => asset.path), '--repo', repository, '--target', revision,
  '--title', `Nano Node v${version}`, '--notes', notes, '--latest=false'], { stdio: 'inherit' });
const temporary = await mkdtemp(join(directory, '.verify-'));
try {
  // Disable curl config so publisher credentials cannot mask anonymous access failures.
  for (const asset of [{name: candidate.package, url: manifest.download_url, sha256: candidate.sha256}, ...extraAssets]) {
    const downloaded = join(temporary, asset.name);
    execFileSync('curl', ['--disable', '--fail', '--location', '--silent', '--show-error', '--retry', '2',
      '--proto', '=https', '--proto-redir', '=https', asset.url, '-o', downloaded], { stdio: 'inherit' });
    if (await checksum(downloaded) !== asset.sha256)
      throw new Error(`Anonymous Release download checksum does not match: ${asset.name}`);
  }
  const verified = join(temporary, 'manifest.json');
  await writeFile(verified, JSON.stringify(manifest, null, 2) + '\n');
  await rename(verified, join(directory, 'manifest.json'));
  for (const item of promotedManifests) {
    await writeFile(join(temporary, item.name), JSON.stringify(item.payload, null, 2) + '\n');
    await rename(join(temporary, item.name), join(directory, item.name));
  }
  console.log(`Verified IM manifest ready: ${join(directory, 'manifest.json')}`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
