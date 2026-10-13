import { spawnSync } from 'node:child_process';
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
  await mkdir(bin);
  const version = 'a'.repeat(40);
  const releaseVersion = '0.2.0';
  const downloadUrl = `https://github.com/Mrchen116/nano-multiagent/releases/download/v${releaseVersion}/nano-node.tgz`;
  const bytes = Buffer.from('one built package');
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  const candidate = { version, sha256, package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0', download_url: `https://github.com/Mrchen116/nano-multiagent/releases/download/node-${version}/nano-node.tgz` };
  await writeFile(join(directory, 'nano-node.tgz'), bytes);
  await writeFile(join(directory, 'manifest.candidate.json'), JSON.stringify(candidate));
  await writeFile(join(directory, 'manifest.json'), 'previous verified manifest');
  // Child-command fixtures exercise the publishing entrypoint without GitHub writes.
  const prelude = `#!${process.execPath}\nconst fs=require('node:fs'); const args=process.argv.slice(2); const dir=${JSON.stringify(directory)};\n`;
  const helpers = {
    git: `if(args[0]==='rev-parse') console.log('${version}');`,
    gh: `if(args[0]==='repo') console.log('PUBLIC'); else {
      if(fs.existsSync(dir+'/uploaded')) process.exit(1);
      if(args[0]!=='release'||args[1]!=='create'||args[2]!=='v${releaseVersion}'||args[args.indexOf('--title')+1]!=='Nano Node v${releaseVersion}'||args[args.indexOf('--target')+1]!=='${version}') process.exit(2);
      fs.copyFileSync(args[3], dir+'/uploaded');
    }`,
    curl: `if(args[0]!=='--disable'||args.includes('--header')||args.includes('--user')||!args.includes(${JSON.stringify(downloadUrl)})) process.exit(3);
      if(${JSON.stringify(failure)}==='download') process.exit(22);
      const bytes=fs.readFileSync(dir+'/uploaded');
      fs.writeFileSync(args[args.indexOf('-o')+1], ${JSON.stringify(failure)}==='checksum'?'wrong package':bytes);`,
  };
  for (const [name, source] of Object.entries(helpers)) {
    await writeFile(join(bin, name), prelude + source);
    await chmod(join(bin, name), 0o700);
  }
  const run = (release = releaseVersion) => spawnSync(process.execPath, [publisher, directory], { encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, RELEASE_VERSION: release } });
  return { directory, candidate, bytes, run, published: { ...candidate, version: releaseVersion, source_commit: version, download_url: downloadUrl } };
}

it('promotes only the same uploaded and anonymously verified bytes, without overwriting a release', async () => {
  const f = await fixture();
  try {
    const result = f.run();
    expect(result.status, result.stderr).toBe(0);
    expect(await readFile(join(f.directory, 'uploaded'))).toEqual(f.bytes);
    expect(JSON.parse(await readFile(join(f.directory, 'manifest.json'), 'utf8'))).toEqual(f.published);
    const published = await readFile(join(f.directory, 'manifest.json'), 'utf8');
    expect(f.run().status).not.toBe(0);
    expect(await readFile(join(f.directory, 'uploaded'))).toEqual(f.bytes);
    expect(await readFile(join(f.directory, 'manifest.json'), 'utf8')).toBe(published);
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
