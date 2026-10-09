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
  let fail = true; let applied = 0; let persisted = 0;
  const options = { current: () => current, resolve: async (candidate: typeof current) => candidate,
    persist: async (candidate: typeof current) => { current = candidate; persisted++; },
    apply: async () => { if (fail) throw new Error('runtime disconnected'); applied++; },
  };
  let operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), options);
  try {
    await expect(operations.handle('apply', intent)).rejects.toThrow('runtime disconnected');
    expect(operations.status('op').status).toBe('pending');
    await operations.close(); fail = false;
    operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), options);
    await operations.recover();
    expect(operations.status('op').status).toBe('applied');
    expect(await operations.handle('apply', intent)).toMatchObject({ status: 'applied' });
    expect([persisted, applied]).toEqual([1, 1]);
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
