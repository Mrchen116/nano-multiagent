import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir, homedir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { NodeConfiguration } from '../src/configuration.js';

it('preserves default versus empty selections and ordered local/global Skill roots', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-node-config-'));
  try {
    const path = join(home, 'node.json');
    await writeFile(path, JSON.stringify({ node: {}, agents: [], llm: { default_model: 'test', providers: [{ name: 'test', models: [{ name: 'test' }] }] } }));
    const config = await NodeConfiguration.read(path);
    const agent = { agent_id: 'a', workspace_root: home };
    expect(config.runtime(agent).toolAllowlist).toBeUndefined();
    expect(config.runtime({ ...agent, tool_allowlist: [], skills: [], skills_selection_mode: 'explicit_allowlist' })).toMatchObject({ toolAllowlist: [], skillSelection: { mode: 'explicit_allowlist', names: [] } });
    expect(config.runtime({ ...agent, skills: ['one'] }).skillSelection).toEqual({ mode: 'explicit_allowlist', names: ['one'] });
    expect(config.runtime(agent).skillRoots).toEqual([
      ...['.nanoassistant', '.claude', '.codex'].map(dir => ({ path: join(home, dir, 'skills'), source: 'workspace' })),
      ...['.nanoassistant', '.agents'].map(dir => ({ path: join(homedir(), dir, 'skills'), source: 'global' })),
      ...['.claude', '.codex'].map(dir => ({ path: join(homedir(), dir, 'skills'), source: 'compat' })),
    ]);
  } finally { await rm(home, { recursive: true, force: true }); }
});
