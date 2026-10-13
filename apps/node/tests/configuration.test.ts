import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir, homedir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { canonicalAgentConfiguration } from '@nano/product-contracts';
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

it('persists the local Workflow guideline without losing other Agent fields', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-guideline-'));
  try {
    const path = join(home, 'node.json');
    await writeFile(path, JSON.stringify({node: {}, agents: [{agent_id: 'a', workspace_root: home, custom_local: 'keep'}], llm: {default_model: 'test', providers: [{name: 'test', models: [{name: 'test'}]}]}}));
    const config = await NodeConfiguration.read(path);
    expect((await config.setWorkflowGuideline('a', 'large')).workflow?.sizeGuideline).toBe('large');
    const restored = await NodeConfiguration.read(path);
    expect(restored.value.agents[0]?.custom_local).toBe('keep');
    expect(restored.runtime(restored.value.agents[0]!).workflow?.sizeGuideline).toBe('large');
  } finally { await rm(home, {recursive: true, force: true}); }
});

it.each([false, true])('uses the advertised workspace base for creation and config reload (custom base: %s)', async customBase => {
  const home = await mkdtemp(join(tmpdir(), 'nano-workspace-'));
  try {
    const path = join(home, 'node.json');
    const ownerRoot = join(home, 'owner');
    const base = customBase ? join(home, 'custom') : join(ownerRoot, 'workspaces');
    await writeFile(path, JSON.stringify({
      node: customBase ? { workspace_base: base } : {},
      gateway: { environment: { NANO_OWNER_CONFIG_ROOT: ownerRoot } },
      agents: [{ agent_id: 'existing' }],
      llm: { default_model: 'test', providers: [{ name: 'test', models: [{ name: 'test' }] }] },
    }));
    const config = await NodeConfiguration.read(path);
    expect(config.current('existing')?.workspace_root).toBe(join(base, 'existing'));
    const template = config.defaultWorkspace('{agent_id}');
    expect(template).toBe(join(base, '{agent_id}'));
    const created = await config.resolve(canonicalAgentConfiguration({ agent_id: 'new' }), true);
    expect(created.workspace_root).toBe(template.replace('{agent_id}', 'new'));
    await config.persist(created);
    expect((await NodeConfiguration.read(path)).current('new')?.workspace_root).toBe(created.workspace_root);
    const explicit = await config.resolve(canonicalAgentConfiguration({ agent_id: 'explicit', workspace_root: join(home, 'explicit') }), true);
    expect(explicit.workspace_root).toBe(join(home, 'explicit'));
  } finally { await rm(home, { recursive: true, force: true }); }
});

it('resolves identical upstream IDs through stable service-specific references', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-ids-'));
  try {
    const path = join(home, 'node.json');
    await writeFile(path, JSON.stringify({node: {}, agents: [], llm: {default_model: 'service-a/shared', tool_approval_model: 'service-b/shared', providers: [
      {name: 'service-a', models: [{name: 'service-a/shared', id: 'shared'}]},
      {name: 'service-b', models: [{name: 'service-b/shared', id: 'shared'}]},
    ]}}));
    const config = await NodeConfiguration.read(path);
    expect(config.runtime({agent_id: 'a', workspace_root: home, model_fallbacks: ['service-b/shared']})).toMatchObject({
      provider: 'service-a', model: 'shared', modelFallbacks: [{provider: 'service-b', model: 'shared'}], approval: {reviewer: {provider: 'service-b', model: 'shared'}},
    });
  } finally { await rm(home, {recursive: true, force: true}); }
});

it('serializes Agent saves against model removal and rejects stale model edits', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-race-'));
  try {
    const path = join(home, 'node.json');
    const llm = {default_model: 'base', providers: [{name: 'p', models: [{name: 'base'}, {name: 'extra'}]}]};
    await writeFile(path, JSON.stringify({node: {}, agents: [], llm}));
    const config = await NodeConfiguration.read(path);
    const next = {...llm, providers: [{name: 'p', models: [{name: 'base'}]}]};
    const agent = canonicalAgentConfiguration({agent_id: 'new', workspace_root: home, default_model: 'extra'});
    const saved = config.persist(agent);
    await expect(config.persistModels(next, config.modelRevision)).rejects.toThrow(/new/);
    await saved;
    expect(config.runtime(config.value.agents[0]!)).toMatchObject({model: 'extra'});
    await config.persist({...agent, default_model: 'base'});
    const revision = config.modelRevision;
    await config.persistModels(next, revision);
    await expect(config.persistModels(llm, revision)).rejects.toThrow(/changed/);
    // An Agent validated before removal must still be checked when its queued write runs.
    await expect(config.persist(agent)).rejects.toThrow(/extra/);
    expect((await NodeConfiguration.read(path)).current('new')?.default_model).toBe('base');
  } finally { await rm(home, {recursive: true, force: true}); }
});

 it('preserves explicit disabled Skill names in the runtime configuration', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-skill-denylist-'));
  try {
    const path = join(home, 'config.json');
    await writeFile(path, JSON.stringify({ node: {}, agents: [], llm: { default_model: 'test', providers: [{ name: 'test', models: [{ name: 'test' }] }] } }));
    const config = await NodeConfiguration.read(path);
    const runtime = config.runtime({agent_id: 'a', workspace_root: home, skills_selection_mode: 'explicit_denylist', skills: ['blocked']});
    expect(runtime.skillSelection).toEqual({mode: 'explicit_denylist', names: ['blocked']});
  } finally { await rm(home, {recursive: true, force: true}); }
});
