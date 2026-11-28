import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmod, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';

const publisher = fileURLToPath(new URL('../../../scripts/publish-node-release.mjs', import.meta.url));

async function fixture(failure = '') {
  const directory = await mkdtemp(join(tmpdir(), 'nano-publish-'));
  const bin = join(directory, 'bin');
  const isolatedPublisher = join(directory, 'publisher.mjs');
  await writeFile(isolatedPublisher, await readFile(publisher));
  await mkdir(bin);
  const version = 'a'.repeat(40);
  const releaseVersion = '0.2.0';
  const downloadUrl = `https://github.com/Mrchen116/nano-multiagent/releases/download/v${releaseVersion}/nano-node.tgz`;
  const payload = join(directory, 'payload');
  await mkdir(payload);
  await writeFile(join(payload, '.nano-release.json'), JSON.stringify({source_commit: version, updater_protocol: 1, data_epoch: 1}));
  execFileSync('tar', ['-czf', join(directory, 'nano-node.tgz'), '-C', payload, '.']);
  const bytes = await readFile(join(directory, 'nano-node.tgz'));
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  const candidate = { version, source_commit: version, updater_protocol: 1, data_epoch: 1, sha256, package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0', download_url: `https://github.com/Mrchen116/nano-multiagent/releases/download/node-${version}/nano-node.tgz` };
  await writeFile(join(directory, 'nano-node.tgz'), bytes);
  await writeFile(join(directory, 'manifest.candidate.json'), JSON.stringify(candidate));
  await writeFile(join(directory, 'manifest.json'), 'previous verified manifest');
  // Child-command fixtures exercise the publishing entrypoint without GitHub writes.
  const prelude = `#!${process.execPath}\nconst fs=require('node:fs'); const args=process.argv.slice(2); const dir=${JSON.stringify(directory)};\n`;
  const helpers = {
    git: `if(process.cwd()!==fs.realpathSync(dir)) process.exit(4); if(args[0]==='rev-parse') console.log('${version}');`,
    gh: `if(args[0]==='repo') console.log('PUBLIC'); else {
      if(fs.existsSync(dir+'/uploaded')) process.exit(1);
      if(args[0]!=='release'||args[1]!=='create'||args[2]!=='v${releaseVersion}'||args[args.indexOf('--title')+1]!=='Nano Node v${releaseVersion}'||args[args.indexOf('--target')+1]!=='${version}') process.exit(2);
      fs.writeFileSync(dir+'/notes', args[args.indexOf('--notes')+1]);
      fs.copyFileSync(args[3], dir+'/uploaded');
      fs.mkdirSync(dir+'/uploads');
      for (const path of args.slice(3, args.indexOf('--repo'))) fs.copyFileSync(path, dir+'/uploads/'+require('node:path').basename(path));
    }`,
    curl: `const assetUrl=args.find(arg=>arg.startsWith(${JSON.stringify(downloadUrl.slice(0, downloadUrl.lastIndexOf('/') + 1))}));
      if(args[0]!=='--disable'||args.includes('--header')||args.includes('--user')||!assetUrl) process.exit(3);
      if(${JSON.stringify(failure)}==='download') process.exit(22);
      const bytes=fs.readFileSync(dir+'/uploads/'+require('node:path').basename(assetUrl));
      fs.writeFileSync(args[args.indexOf('-o')+1], ${JSON.stringify(failure)}==='checksum'?'wrong package':bytes);`,
  };
  for (const [name, source] of Object.entries(helpers)) {
    await writeFile(join(bin, name), prelude + source);
    await chmod(join(bin, name), 0o700);
  }
  const run = (release = releaseVersion, changes = '- 改进节点连接', upgradeNotes = '无需额外操作', macMode?: string) =>
    spawnSync(process.execPath, [isolatedPublisher, directory], { cwd: directory, encoding: 'utf8',
      env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, RELEASE_VERSION: release,
        MACOS_DISTRIBUTION: macMode, MACOS_SIGNING_IDENTITY: undefined, MACOS_NOTARY_PROFILE: undefined,
        RELEASE_CHANGES: changes, RELEASE_UPGRADE_NOTES: upgradeNotes } });
  return { directory, candidate, bytes, run, published: { ...candidate, version: releaseVersion, source_commit: version, download_url: downloadUrl } };
}

it('promotes only the same uploaded and anonymously verified bytes, without overwriting a release', async () => {
  const f = await fixture();
  try {
    const result = f.run();
    expect(result.status, result.stderr).toBe(0);
    expect(await readFile(join(f.directory, 'uploaded'))).toEqual(f.bytes);
    expect(await readFile(join(f.directory, 'notes'), 'utf8')).toBe([
      '## 本版变化', '- 改进节点连接', '## 升级说明', '无需额外操作', '## 安装包与校验',
      `- 安装包 [nano-node.tgz](${f.published.download_url})\n- 源码提交 [\`${f.published.source_commit}\`](https://github.com/Mrchen116/nano-multiagent/commit/${f.published.source_commit})\n- SHA-256 \`${f.candidate.sha256}\``,
    ].join('\n\n'));
    expect(JSON.parse(await readFile(join(f.directory, 'manifest.json'), 'utf8'))).toEqual(f.published);
    const published = await readFile(join(f.directory, 'manifest.json'), 'utf8');
    expect(f.run().status).not.toBe(0);
    expect(await readFile(join(f.directory, 'uploaded'))).toEqual(f.bytes);
    expect(await readFile(join(f.directory, 'manifest.json'), 'utf8')).toBe(published);
  } finally { await rm(f.directory, { recursive: true, force: true }); }
});

// Build all four release manifests so the test reaches the unified publication
// entrypoint with both Windows installers and only fixture GitHub binaries.
async function platformMaterials(f: Awaited<ReturnType<typeof fixture>>, macMode: string | undefined) {
  const base = new URL('.', f.published.download_url).href;
  for (const platform of ['win32-x64', 'desktop-win32-x64', 'desktop-darwin-arm64']) {
    const lightweight = platform === 'win32-x64';
    const mac = platform === 'desktop-darwin-arm64';
    const sub = join(f.directory, lightweight ? 'windows' : platform);
    await mkdir(sub);
    const asset = async (name: string, content: string) => {
      await writeFile(join(sub, name), content);
      return {name, download_url: base + name, size: Buffer.byteLength(content), sha256: createHash('sha256').update(content).digest('hex')};
    };
    const platformFlags = lightweight ? {launcher_protocol: 1} : {shell_protocol: 2};
    const common = {version: f.published.version, source_commit: f.published.source_commit, updater_protocol: 1, data_epoch: 1, ...platformFlags};
    const payload = (kind: string) => lightweight ? `windows-${kind}-x64.zip` : `desktop-${kind}-${platform.slice(8)}.tar.gz`;
    const descriptor = await asset(lightweight ? 'windows-x64.json' : platform + '.json', JSON.stringify({
      ...common, runtime: await asset(payload('runtime'), 'runtime'), app: await asset(payload('app'), 'app'),
    }));
    const installer = await asset(mac ? 'Crewden-Desktop-arm64.dmg' : lightweight ? 'Crewden-Setup-x64.exe' : 'Crewden-Desktop-Setup-x64.exe', 'installer');
    await writeFile(join(sub, `manifest.${platform}.json`), JSON.stringify({...common, ...descriptor, installer, package: descriptor.name,
      platform, node_major: 24, pnpm_version: '11.7.0', ...(mac ? {macos_distribution: macMode} : {})}));
  }
}

it.each([
  ['unnotarized', undefined, '未经 Apple 公证'],
  ['developer-id-notarized', 'developer-id-notarized', '已通过 Apple 公证'],
] as const)('includes the correct Mac disclosure in a unified %s release', async (artifactMode, selectedMode, disclosure) => {
  const f = await fixture();
  try {
    await platformMaterials(f, artifactMode);
    const result = f.run(undefined, undefined, undefined, selectedMode);
    expect(result.status, result.stderr).toBe(0);
    const notes = await readFile(join(f.directory, 'notes'), 'utf8');
    expect(notes.split('\n').find(line => line.includes('Crewden-Desktop-arm64.dmg'))).toContain(disclosure);
    for (const name of ['manifest.json', 'manifest.win32-x64.json', 'manifest.desktop-win32-x64.json', 'manifest.desktop-darwin-arm64.json']) {
      const promoted = JSON.parse(await readFile(join(f.directory, name), 'utf8'));
      expect(promoted.version).toBe(f.published.version);
      if (name.startsWith('manifest.desktop-')) {
        expect(promoted.shell_protocol).toBe(2);
        expect(promoted.release_notes).toBe('- 改进节点连接');
      }
    }
  } finally { await rm(f.directory, {recursive: true, force: true}); }
});

it.each([
  ['unsigned-test', undefined], [undefined, 'developer-id-notarized'],
  ['unnotarized', 'developer-id-notarized'], ['developer-id-notarized', undefined],
] as const)('rejects a %s artifact for the selected release mode before uploading', async (artifactMode, selectedMode) => {
  const f = await fixture();
  try {
    await platformMaterials(f, artifactMode);
    const result = f.run(undefined, undefined, undefined, selectedMode);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('macOS release requires the verified');
    await expect(readFile(join(f.directory, 'uploaded'))).rejects.toThrow();
  } finally { await rm(f.directory, {recursive: true, force: true}); }
});

it.each([[' ', '无需额外操作'], ['- 改进节点连接', '']])('requires both release note sections before uploading', async (changes, upgradeNotes) => {
  const f = await fixture();
  try {
    const result = f.run(undefined, changes, upgradeNotes);
    expect(result.stderr).toContain('RELEASE_CHANGES and RELEASE_UPGRADE_NOTES are required');
    expect(result.status).not.toBe(0);
    await expect(readFile(join(f.directory, 'uploaded'))).rejects.toThrow();
  } finally { await rm(f.directory, { recursive: true, force: true }); }
});

it.each(['download', 'checksum'])('keeps the prior IM manifest after anonymous %s failure', async (failure) => {
  const f = await fixture(failure);
  try {
    expect(f.run().status).not.toBe(0);
    expect(await readFile(join(f.directory, 'manifest.json'), 'utf8')).toBe('previous verified manifest');
    expect(await readFile(join(f.directory, 'uploaded'))).toEqual(f.bytes);
  } finally { await rm(f.directory, { recursive: true, force: true }); }
});


it.each(['', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'v1.2.3', '01.2.3', '1.2'])('rejects missing or invalid explicit version %s before uploading', async (version) => {
  const f = await fixture();
  try {
    const result = f.run(version);
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('RELEASE_VERSION');
    await expect(readFile(join(f.directory, 'uploaded'))).rejects.toThrow();
    expect(await readFile(join(f.directory, 'manifest.json'), 'utf8')).toBe('previous verified manifest');
  } finally { await rm(f.directory, { recursive: true, force: true }); }
});

it('loads self-hosted managed release manifests deterministically from desktop-defaults.json or .nano-release.json', async () => {
  const { loadNodeRelease } = await import('../src/release.js');
  const root = await mkdtemp(join(tmpdir(), 'nano-self-hosted-rel-'));
  const desktopHome = join(root, 'desktop');
  const sha = '9'.repeat(64);
  const versionRoot = join(desktopHome, 'versions', sha);
  const privateBase = 'http://10.24.8.15:9000/releases/v1.5.0/';
  try {
    await mkdir(versionRoot, { recursive: true });
    const manifest = {
      version: '1.5.0',
      source_commit: 'a'.repeat(40),
      release_base_url: privateBase,
      sha256: sha,
      package: 'desktop-win32-x64.json',
      platform: 'desktop-win32-x64',
      size: 512,
      shell_protocol: 1,
      node_major: 24,
      pnpm_version: '11.7.0',
      updater_protocol: 1,
      data_epoch: 1,
      download_url: privateBase + 'desktop-win32-x64.json',
      installer: {
        download_url: privateBase + 'Crewden-Desktop-Setup-x64.exe',
        sha256: 'b'.repeat(64),
        size: 10240,
      },
    };
    await writeFile(join(versionRoot, '.release-manifest.json'), JSON.stringify(manifest));
    await writeFile(
      join(versionRoot, '.nano-release.json'),
      JSON.stringify({ source_commit: 'a'.repeat(40), updater_protocol: 1, data_epoch: 1, shell_protocol: 1 }),
    );
    // Without desktop-defaults.json or trusted_release_base_url, self-hosted manifest is rejected.
    await expect(loadNodeRelease(versionRoot)).rejects.toThrow('Invalid installed release manifest');

    // Writing <desktopHome>/desktop-defaults.json deterministically authorizes the private HTTP base via path layout.
    await writeFile(
      join(desktopHome, 'desktop-defaults.json'),
      JSON.stringify({
        default_im_origin: 'http://10.24.8.15:8011',
        trusted_release_base_url: 'http://10.24.8.15:9000/releases',
        allow_private_http_release_base: true,
      }),
    );
    expect(await loadNodeRelease(versionRoot)).toMatchObject({
      kind: 'managed',
      platform: 'desktop-win32-x64',
      version: '1.5.0',
      sha256: sha,
      shell_protocol: 1,
    });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
