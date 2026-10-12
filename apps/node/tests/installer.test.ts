import { mkdtemp, mkdir, readFile, writeFile, chmod, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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
