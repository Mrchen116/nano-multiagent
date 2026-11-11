import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { canonicalAgentConfiguration, agentConfigurationFingerprint } from '@nano/product-contracts';
import { ConfigurationOperations } from '../src/configuration.js';

it('recovers a persisted configuration after runtime failure without losing the optimistic operation identity', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-config-'));
  let current = canonicalAgentConfiguration({ agent_id: 'a', workspace_root: directory, display_name: 'old' });
  const next = { ...current, display_name: 'new', features: { task_graph: false } };
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
    expect(await operations.handle('apply', { ...intent, operation_id: 'stale', agent: { ...next, display_name: 'third' }, candidate_fingerprint: agentConfigurationFingerprint({ ...next, display_name: 'third' }) })).toMatchObject({ error_code: 'operation_conflict' });
  } finally { await operations.close(); await rm(directory, { recursive: true, force: true }); }
});

it('preserves explicit empty selections and heartbeat clearing while matching canonical fingerprints', () => {
  const value = canonicalAgentConfiguration({ agent_id: 'a', display_name: '中文', skills: [], skills_selection_mode: 'explicit_allowlist', heartbeat_json: '{}' });
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
  const {approval_mode: _mode, ...legacy} = canonicalAgentConfiguration({agent_id: 'a', workspace_root: directory, display_name: 'old'});
  const candidate = {...legacy, display_name: 'new'};
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
    expect(applied).toMatchObject({display_name: 'new', approval_mode: null});
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


it('preserves initial ROLE as a creation intent through restart and rejects changed retry identities or later apply', async () => {
  const directory=await mkdtemp(join(tmpdir(),'nano-create-role-'));
  const candidate=canonicalAgentConfiguration({agent_id:'new',workspace_root:directory});
  const intent={operation_id:'create-role',expected_previous_fingerprint:null,candidate_fingerprint:agentConfigurationFingerprint(candidate),agent:candidate,initial_role:'Help the owner design products.'};
  let current:typeof candidate|undefined;
  let failPersist=true;
  const seen:string[]=[];
  const options={current:()=>current,resolve:async (value:typeof candidate)=>value,
    prepare:async (_value:typeof candidate,operation:{initial_role?:string})=>{seen.push(operation.initial_role!);return {ready:true};},
    persist:async (value:typeof candidate)=>{if(failPersist)throw new Error('disk unavailable');current=value;},apply:async()=>{},
  };
  let operations=new ConfigurationOperations(join(directory,'ops.sqlite3'),options);
  try {
    await expect(operations.handle('create',intent)).rejects.toThrow('disk unavailable');
    expect(operations.status(intent.operation_id).status).toBe('pending');
    await operations.close();failPersist=false;
    operations=new ConfigurationOperations(join(directory,'ops.sqlite3'),options);
    expect(await operations.handle('create',{...intent,initial_role:'Different role'})).toMatchObject({status:'rejected',error_code:'operation_id_reused'});
    await operations.recover();
    expect(seen).toEqual([intent.initial_role,intent.initial_role]);
    expect(operations.status(intent.operation_id)).toMatchObject({status:'applied',agent:candidate});
    expect(current).not.toHaveProperty('initial_role');
    expect(await operations.handle('apply',{...intent,operation_id:'edit',expected_previous_fingerprint:intent.candidate_fingerprint})).toMatchObject({status:'rejected',error_code:'invalid_agent_config'});
    expect(await operations.handle('create',{...intent,operation_id:'too-long',initial_role:'😀'.repeat(1001)})).toMatchObject({status:'rejected',error_code:'invalid_agent_config'});
  } finally {await operations.close();await rm(directory,{recursive:true,force:true});}
});

it('keeps creation pending when the initial-role write succeeds but the runtime preparation reply is lost', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-role-reply-lost-'));
  const role = join(directory, 'ROLE.md');
  const candidate = canonicalAgentConfiguration({agent_id: 'new', workspace_root: directory});
  const intent = {operation_id: 'lost-reply', expected_previous_fingerprint: null, candidate_fingerprint: agentConfigurationFingerprint(candidate), agent: candidate, initial_role: 'Coordinate releases.'};
  let current: typeof candidate | undefined;
  let first = true;
  const operations = new ConfigurationOperations(join(directory, 'ops.sqlite3'), {
    current: () => current, resolve: async value => value,
    prepare: async (_candidate, operation) => {
      if (first) { first = false; await writeFile(role, operation.initial_role!); throw new Error('Connection closed; operation outcome may be unknown'); }
      expect(await readFile(role, 'utf8')).toBe(operation.initial_role);
      return {ready: true};
    },
    persist: async value => { current = value; }, apply: async () => {},
  });
  try {
    await expect(operations.handle('create', intent)).rejects.toThrow('outcome may be unknown');
    expect(operations.status(intent.operation_id)).toMatchObject({status: 'pending'});
    expect(current).toBeUndefined();
    expect(await operations.handle('create', intent)).toMatchObject({status: 'applied', agent: candidate});
    expect(await readFile(role, 'utf8')).toBe(intent.initial_role);
  } finally { await operations.close(); await rm(directory, {recursive: true, force: true}); }
});
