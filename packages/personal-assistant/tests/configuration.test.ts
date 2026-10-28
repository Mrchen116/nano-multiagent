import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { canonicalAgentConfiguration, agentConfigurationFingerprint } from '@nano/product-contracts';
import { ConfigurationOperations } from '../src/configuration.js';

it('recovers a persisted configuration after runtime failure without losing the optimistic operation identity', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-config-'));
  let current = canonicalAgentConfiguration({ agent_id: 'a', workspace_root: directory, custom_prompt: 'old' });
  const next = { ...current, custom_prompt: 'new', features: { task_graph: false } };
  const intent = { operation_id: 'op', expected_previous_fingerprint: agentConfigurationFingerprint(current), candidate_fingerprint: agentConfigurationFingerprint(next), agent: next };
  let fail = true; let applied = 0; let persisted = 0; let prepared = 0; let released = 0;
  const options = { current: () => current, resolve: async (candidate: typeof current) => candidate,
    prepare: async () => { prepared++; return {ready: true}; },
    release: async () => { released++; },
    persist: async (candidate: typeof current) => { expect(prepared).toBe(1); current = candidate; persisted++; },
    apply: async () => { if (fail) throw new Error('runtime disconnected'); applied++; },
  };
  let operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), options);
  try {
    await expect(operations.handle('apply', intent)).rejects.toThrow('runtime disconnected');
    expect(operations.status('op').status).toBe('pending');
    expect(operations.pending()).toEqual([{intent, candidate: next}]);
    expect(released).toBe(0);
    expect(operations.busy).toBe(true);
    await operations.close(); fail = false;
    operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), options);
    await operations.recover();
    expect(operations.status('op').status).toBe('applied');
    expect(operations.busy).toBe(false);
    expect(await operations.handle('apply', intent)).toMatchObject({ status: 'applied' });
    expect([persisted, applied, prepared, released]).toEqual([1, 1, 2, 1]);
    expect(await operations.handle('apply', { ...intent, candidate_fingerprint: 'different' })).toMatchObject({ error_code: 'operation_id_reused' });
    expect(await operations.handle('apply', { ...intent, operation_id: 'stale', agent: { ...next, custom_prompt: 'third' }, candidate_fingerprint: agentConfigurationFingerprint({ ...next, custom_prompt: 'third' }) })).toMatchObject({ error_code: 'operation_conflict' });
  } finally { await operations.close(); await rm(directory, { recursive: true, force: true }); }
});

it('preserves explicit empty selections and heartbeat clearing while matching canonical fingerprints', () => {
  const value = canonicalAgentConfiguration({ agent_id: 'a', display_name: '中文', skills: [], skills_selection_mode: 'explicit_allowlist', heartbeat_json: '{}' });
  expect(agentConfigurationFingerprint(value)).toBe('befc497550c85b75ccca1e003a02d61b05aaaf4ce86a3d0fece726af4118c088');
  expect(value.skills).toEqual([]); expect(value.skills_selection_mode).toBe('explicit_allowlist');
  expect(value.heartbeat_json).toBe('{}');
  expect(agentConfigurationFingerprint(value)).toBe(agentConfigurationFingerprint({ ...value, heartbeat_json: null }));
});

it('applies another Agent configuration while one Agent waits for its running turn', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-config-independent-'));
  const records = new Map<string, ReturnType<typeof canonicalAgentConfiguration>>();
  let release!: () => void; const busy = new Promise<void>(resolve => { release = resolve; });
  let entered!: () => void; const waiting = new Promise<void>(resolve => { entered = resolve; });
  const operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), {
    current: id => records.get(id), resolve: async candidate => candidate,
    persist: async candidate => { records.set(candidate.agent_id, candidate); },
    apply: async candidate => { if (candidate.agent_id === 'a') { entered(); await busy; } },
  });
  const create = (id: string) => { const agent = canonicalAgentConfiguration({ agent_id: id }); return operations.handle('create', {
    operation_id: id, agent, candidate_fingerprint: agentConfigurationFingerprint(agent), expected_previous_fingerprint: null,
  }); };
  const a = create('a');
  try {
    await waiting;
    const b = create('b');
    const state = await Promise.race([b, new Promise(resolve => setTimeout(() => resolve({ status: 'blocked' }), 100))]);
    expect(state).toMatchObject({ status: 'applied' });
  } finally { release(); await a; await operations.close(); await rm(directory, { recursive: true, force: true }); }
});


it('recovers a pre-strategy pending receipt without changing its fingerprint or inherited mode', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-config-legacy-'));
  const {approval_mode: _mode, ...legacy} = canonicalAgentConfiguration({agent_id: 'a', workspace_root: directory, custom_prompt: 'old'});
  const candidate = {...legacy, custom_prompt: 'new'};
  const hash = (value: unknown) => createHash('sha256').update(sortedJsonAscii(value)).digest('hex');
  const intent = {operation_id: 'legacy', candidate_fingerprint: hash(candidate), expected_previous_fingerprint: hash(legacy), agent: candidate};
  const path = join(directory, 'ops.sqlite3');
  const db = new DatabaseSync(path);
  db.exec('CREATE TABLE operations(id TEXT PRIMARY KEY, receipt TEXT NOT NULL)');
  db.prepare('INSERT INTO operations VALUES(?,?)').run('legacy', JSON.stringify({kind: 'apply', intent, candidate, status: 'pending'}));
  db.close();
  let current = canonicalAgentConfiguration(legacy);
  let applied: unknown;
  const ops = new ConfigurationOperations(path, {
    current: () => current, resolve: async value => value,
    persist: async value => { current = canonicalAgentConfiguration(value); },
    apply: async value => { applied = canonicalAgentConfiguration(value); },
  });
  try {
    await ops.recover();
    expect(ops.status('legacy')).toMatchObject({status: 'applied', candidate_fingerprint: intent.candidate_fingerprint});
    expect(applied).toMatchObject({custom_prompt: 'new', approval_mode: null});
    expect(current.approval_mode).toBeNull();
  } finally { await ops.close(); await rm(directory, {recursive: true, force: true}); }
});

it('rejects capability changes before persistence and preserves structured reasons on replay', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-config-prepare-'));
  const current = canonicalAgentConfiguration({ agent_id: 'a', features: { heartbeat: true } });
  const candidate = { ...current, features: { heartbeat: false } };
  let persisted = false;
  const blocks = [{ code: 'capability_busy' as const, target: { kind: 'feature' as const, name: 'heartbeat' } }];
  const operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), {
    current: () => current, resolve: async value => value,
    prepare: async () => ({ ready: false, error_code: 'capability_in_use', message: 'Heartbeat is active', blocks }),
    persist: async () => { persisted = true; }, apply: async () => { throw new Error('Must not apply'); },
  });
  const intent = { operation_id: 'blocked', candidate_fingerprint: agentConfigurationFingerprint(candidate), expected_previous_fingerprint: agentConfigurationFingerprint(current), agent: candidate };
  try {
    expect(await operations.handle('apply', intent)).toMatchObject({status: 'rejected', error_code: 'capability_in_use', blocks});
    expect(persisted).toBe(false);
    expect(await operations.handle('apply', intent)).toMatchObject({status: 'rejected', blocks});
  } finally { await operations.close(); await rm(directory, { recursive: true, force: true }); }
});
