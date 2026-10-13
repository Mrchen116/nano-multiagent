import { mkdtemp, mkdir, readFile, writeFile, chmod, rm, access, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { expect, it } from 'vitest';

it('retries interrupted runtime extraction without accepting a partial node executable', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-installer-'));
  try {
    const bin = join(home, 'bin'); await mkdir(bin);
    const script = (await readFile(new URL('../../im-server/assets/install.sh', import.meta.url), 'utf8')).split('export PATH=')[0]!.replace('__NANO_ORIGIN__', "'https://im.test'") + '\n"$NANO_NODE" --version\n"$NANO_NODE_DIR/bin/npm" --version\n';
    const path = join(home, 'runtime.sh'); await writeFile(path, script);
    const helpers: Record<string, string> = {
      node: 'exit 1', npm: 'exit 1',
      curl: 'while [ "$1" != "-o" ]; do shift; done; shift; case "$1" in *node-sums) echo "fixture node-v24.0.0-$(uname -s | tr A-Z a-z)-$(uname -m | sed s/x86_64/x64/).tar.gz" > "$1";; *) echo archive > "$1";; esac',
      shasum: 'echo "fixture $3"',
      tar: 'while [ "$1" != "-C" ]; do shift; done; shift; dest="$1/node-v24.0.0-$(uname -s | tr A-Z a-z)-$(uname -m | sed s/x86_64/x64/)"; mkdir -p "$dest/bin"; printf "#!/bin/sh\\nexit 0\\n" > "$dest/bin/node"; chmod +x "$dest/bin/node"; if [ ! -f "$NANO_INSTALL_ROOT/extraction-attempted" ]; then touch "$NANO_INSTALL_ROOT/extraction-attempted"; exit 1; fi; cp "$dest/bin/node" "$dest/bin/npm"',
    };
    for (const [name, content] of Object.entries(helpers)) { await writeFile(join(bin, name), `#!/bin/sh\n${content}\n`); await chmod(join(bin, name), 0o700); }
    const env = {...process.env, PATH: `${bin}:/usr/bin:/bin`, NANO_INSTALL_ROOT: join(home, 'nano')};
    const first = spawnSync('/bin/bash', [path], {env, encoding: 'utf8'});
    expect(first.status).not.toBe(0);
    expect(first.stderr).toContain('Run the same command');
    const second = spawnSync('/bin/bash', [path], {env, encoding: 'utf8'});
    expect(second.status, second.stderr).toBe(0);
    await access(join(env.NANO_INSTALL_ROOT, 'extraction-attempted'));
  } finally { await rm(home, {recursive: true, force: true}); }
});


async function releaseFixture(version = '0.2.0') {
  const home = await mkdtemp(join(tmpdir(), 'nano-release-install-'));
  const root = join(home, 'nano');
  const bin = join(home, 'bin');
  const payload = join(home, 'payload');
  await mkdir(bin);
  await mkdir(join(payload, 'apps/node/lib'), { recursive: true });
  await writeFile(join(payload, 'apps/node/lib/cli.js'), 'require("node:fs").appendFileSync(process.env.NANO_INSTALL_ROOT+"/setup-calls", JSON.stringify(process.argv.slice(2))+"\\n")');
  await mkdir(join(root, 'tooling/node_modules/pnpm/bin'), { recursive: true });
  await writeFile(join(root, 'tooling/node_modules/pnpm/bin/pnpm.cjs'), '');
  await mkdir(join(root, 'releases/previous'), { recursive: true });
  await writeFile(join(root, 'releases/previous/.installed'), 'old version');
  await writeFile(join(root, 'config.yaml'), 'node_id: retained\ntoken: retained\n');
  const archive = join(home, 'package.tgz');
  expect(spawnSync('tar', ['-czf', archive, '-C', payload, '.']).status).toBe(0);
  const sha256 = createHash('sha256').update(await readFile(archive)).digest('hex');
  const url = `https://github.com/Mrchen116/nano-multiagent/releases/download/${version.length === 40 ? `node-${version}` : `v${version}`}/nano-node.tgz`;
  const manifest = { version, source_commit: 'a'.repeat(40), sha256, download_url: url, package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0' };
  await writeFile(join(home, 'manifest.json'), JSON.stringify(manifest));
  // Only this test process replaces curl. Production accepts no download-source override.
  await writeFile(join(bin, 'curl'), `#!${process.execPath}
const fs = require('node:fs');
const args = process.argv.slice(2), url = args.find(x => x.startsWith('https://'));
fs.appendFileSync(${JSON.stringify(join(home, 'downloads'))}, url+'\\n');
const output = args[args.indexOf('-o')+1];
if (url === 'https://im.test/install/manifest.json') fs.copyFileSync(${JSON.stringify(join(home, 'manifest.json'))}, output);
else if (url === ${JSON.stringify(url)}) {
  if (fs.existsSync(${JSON.stringify(join(home, 'fail-download'))})) process.exit(22);
  fs.copyFileSync(${JSON.stringify(archive)}, output);
} else process.exit(99);
`);
  await chmod(join(bin, 'curl'), 0o700);
  const script = join(home, 'install.sh');
  await writeFile(script, (await readFile(new URL('../../im-server/assets/install.sh', import.meta.url), 'utf8')).replace('__NANO_ORIGIN__', "'https://im.test'"));
  const run = () => spawnSync('/bin/bash', [script], { encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, NANO_INSTALL_ROOT: root } });
  return { home, root, archive, manifest, run };
}

it.each(['0.2.0', 'a'.repeat(40)])('downloads pinned version %s and preserves existing files on reinstall', async (version) => {
  const f = await releaseFixture(version);
  try {
    const first = f.run();
    expect(first.status, first.stderr).toBe(0);
    const again = f.run();
    expect(again.status, again.stderr).toBe(0);
    expect((await readFile(join(f.home, 'downloads'), 'utf8')).split('\n').filter(Boolean)).toEqual([
      'https://im.test/install/manifest.json', f.manifest.download_url, 'https://im.test/install/manifest.json',
    ]);
    expect(await readFile(join(f.root, 'config.yaml'), 'utf8')).toBe('node_id: retained\ntoken: retained\n');
    expect(await readFile(join(f.root, 'releases/previous/.installed'), 'utf8')).toBe('old version');
    expect(await readdir(join(f.root, 'downloads'))).toEqual([]);
    expect(await readFile(join(f.root, 'setup-calls'), 'utf8')).toContain('["setup","--im-service-url","https://im.test"]');
  } finally { await rm(f.home, { recursive: true, force: true }); }
});

it.each(['checksum', 'download', 'manifest'])('preserves the old installation when %s verification fails', async (failure) => {
  const f = await releaseFixture();
  try {
    if (failure === 'checksum') await writeFile(f.archive, 'damaged bytes');
    if (failure === 'download') await writeFile(join(f.home, 'fail-download'), '');
    if (failure === 'manifest') await writeFile(join(f.home, 'manifest.json'), JSON.stringify({ ...f.manifest, download_url: 'https://attacker.test/nano-node.tgz' }));
    const result = f.run();
    expect(result.status).not.toBe(0);
    expect(result.stderr).toMatch(/retry|again/i);
    expect(await readdir(join(f.root, 'releases'))).toEqual(['previous']);
    expect(await readFile(join(f.root, 'config.yaml'), 'utf8')).toBe('node_id: retained\ntoken: retained\n');
    expect(await readdir(join(f.root, 'downloads'))).toEqual([]);
    await expect(access(join(f.root, 'setup-calls'))).rejects.toThrow();
    const downloads = await readFile(join(f.home, 'downloads'), 'utf8');
    expect(downloads).not.toContain('/latest/');
    expect(downloads).not.toContain('https://im.test/install/nano-node.tgz');
  } finally { await rm(f.home, { recursive: true, force: true }); }
});
