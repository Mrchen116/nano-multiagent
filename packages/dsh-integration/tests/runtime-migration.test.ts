import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, writeFile, readFile, rm, cp, rename } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { afterEach, expect, it } from 'vitest';
import { SESSION_FORMAT_VERSION, SessionId, SessionLogOffset, SessionSeq, buildForkSeed, type SessionEvent } from '@deepseek-ai/dsh-session';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { scheduleDomain } from '@deepseek-ai/dsh-schedule';
import { historyDomain } from '../src/history.js';
import { knowledgeDomain } from '../src/knowledge/state.js';
import { workflowDomain } from '../src/workflow/state.js';
import { approvalDomain } from '../src/policy/audit.js';
import { modelDomain } from '../src/model-policy.js';
import { modelRunsDomain } from '../src/model-fallback.js';
import { toolViewsDomain } from '../src/tool-presentation.js';
import { trajectoryRunsDomain } from '../src/trajectory-runs.js';
import { trajectorySourcesDomain } from '../src/trajectory-attachments.js';
import { descendantDomain } from '../src/descendants.js';
import { planRuntimeMigration, applyRuntimeMigration, verifyRuntimeMigration, openMigrationStorage, RUNTIME_LAYOUT_MARKER, type RuntimeMigrationConfig } from '../src/runtime-migration.js';

const homes: string[] = [];
afterEach(async () => { for (const home of homes.splice(0)) await rm(home, {recursive: true, force: true}); });
const encode = (value: string) => Buffer.from(value).toString('base64url');
const hash = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');

async function fixture() {
  const home = await mkdtemp(join(tmpdir(), 'nano-partition-migration-')); homes.push(home);
  const config: RuntimeMigrationConfig = {home, nodeId: 'node', ownerId: 'owner', stopped: true,
    agents: [{agentId: 'a'}, {agentId: 'b'}, {agentId: 'pa', partitionKey: 'personal:binding:2'}]};
  const db = new DatabaseSync(join(home, 'node.sqlite3'));
  db.exec(`CREATE TABLE node_owner(owner_id TEXT); INSERT INTO node_owner VALUES('owner');
    CREATE TABLE sessions(session_id TEXT,agent_id TEXT,binding TEXT);
    CREATE TABLE inputs(input_id TEXT,accepted INTEGER,terminal TEXT);
    INSERT INTO inputs VALUES('old-input',0,NULL);`);
  for (const [sessionId, agentId] of [['a-current', 'a'], ['a-old', 'a'], ['b-current', 'b'], ['pa-current', 'pa']])
    db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(sessionId, agentId, JSON.stringify({sessionId, agentId, ownerId: 'owner', conversationId: sessionId, revision: '1', cwd: '/unchanged/workspace'}));
  db.close();
  const inbox = new DatabaseSync(join(home, 'global.sqlite3'));
  inbox.exec(`CREATE TABLE work_checkpoint(agent_id TEXT,processed INTEGER,acked INTEGER);
    INSERT INTO work_checkpoint VALUES('a',29,17); CREATE TABLE tasks(id TEXT,state TEXT); INSERT INTO tasks VALUES('task-a','waiting');`); inbox.close();
  const storage = await openMigrationStorage(home);
  const file = await storage.attachments.saveFile({data: Buffer.from('attachment evidence'), name: 'evidence.txt'});
  const image = await storage.attachments.saveImage({mediaType: 'image/png', data: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAIAAACwpMoFAAABNklEQVR4nO3ZwQmAMBQFwVRjY5ZtB9qD2ILkILgZ+PdJ2OMb235N33He08f9xh2rfXg1V+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrvjj4/mvj+B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx37cFxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx117cNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBx1x4cdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNy1B8ddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdx+RTJHLcoVInQAAAABJRU5ErkJggg==', 'base64')});
  const events = [
    {type: 'user/message', seq: 0, time: 1, surfaceOp: 'append', data: createUserMessage({content: [{type: 'file', attachment: file}, {type: 'image', attachment: image}], source: {kind: 'user'}})},
    {type: 'subagent/catalog', seq: 1, time: 2, data: {version: 0, childId: SessionId('a-child'), childCreatedAt: 2, mode: 'one-shot'}},
  ] as SessionEvent[];
  async function seed(id: string, body: SessionEvent[] = [], parentSession?: string, inherited = 0) {
    const handle = await storage.sessions.create({id: SessionId(id), version: SESSION_FORMAT_VERSION, createdAt: 1,
      cwd: '/unchanged/workspace', isSeeded: inherited > 0, ...(parentSession ? {parentSession: SessionId(parentSession)} : {})}, inherited ? {inheritedEventCount: SessionLogOffset(inherited)} : undefined);
    await handle.append(body); await handle.flush(); await handle.close();
  }
  await seed('a-current', events); await seed('a-old'); await seed('b-current'); await seed('a-child');
  await seed('a-fork', buildForkSeed(events, SessionSeq(1)), 'a-old', 2);
  const history = await storage.domain.open(historyDomain);
  await history.table('snapshots').put(encode('a-old:1'), {sessionId: 'a-old', turn: 1, config: {agentId: 'a', revision: '1'} as never}); await history.close();
  const knowledge = await storage.domain.open(knowledgeDomain);
  await knowledge.table('counters').put(encode('a-old:memory:iterations'), {memory: 3, skills: 2});
  await knowledge.table('reviews').put(encode('review'), {id: 'review', agentId: 'a', rootSessionId: 'a-old', kind: 'memory', turn: 1, status: 'running', at: 3}); await knowledge.close();
  const workflow = await storage.domain.open(workflowDomain);
  await workflow.table('runs').put(encode('workflow'), {id: 'workflow', parentSessionId: 'a-current', state: 'paused', calls: []} as never); await workflow.close();
  const approval = await storage.domain.open(approvalDomain);
  await approval.table('delegated').put('b-current', {epoch: 'epoch', entries: [{kept: true}]}); await approval.close();
  const models = await storage.domain.open(modelDomain);
  await models.table('sessions').put(encode('a-old'), {revision: 'old', sticky: {provider: 'provider', model: 'model'}}); await models.close();
  const modelRuns = await storage.domain.open(modelRunsDomain);
  await modelRuns.table('runs').put(encode('run-a'), {id: 'run-a', sessionId: 'a-current', revision: '1', turn: 1, inputs: ['input'], attempts: [], state: 'switching'}); await modelRuns.close();
  const tools = await storage.domain.open(toolViewsDomain);
  await tools.table('calls').put(encode(JSON.stringify(['a-old', 'call'])), {callId: 'call', delegationKind: 'background'}); await tools.close();
  const runs = await storage.domain.open(trajectoryRunsDomain);
  await runs.table('runs').put(encode('child-run'), {runId: 'child-run', parentSessionId: 'a-current', sessionId: 'a-child', provider: 'fork', kind: 'tool', delegation: 'background', startedAt: 1, state: 'running'}); await runs.close();
  const sources = await storage.domain.open(trajectorySourcesDomain);
  await sources.table('sources').put(encode(JSON.stringify(['a-current', image.attachmentId])), [{kind: 'workspace', path: 'unchanged.png'}]); await sources.close();
  const descendants = await storage.domain.open(descendantDomain);
  await descendants.table('sessions').put(encode('a-current'), {rootId: 'a-current', cursor: 1, children: [], active: false}); await descendants.close();
  await storage.close();
  const schedules = await openMigrationStorage(home, join(home, 'schedules', hash('a')));
  const schedule = await schedules.domain.open(scheduleDomain);
  await schedule.table('tasks').put('schedule-a' as never, {sessionId: SessionId('a-old'), record: {id: 'schedule-a', title: 'Reminder', prompt: 'Keep this', kind: 'at', scheduledAt: '2030-01-01T00:00:00.000Z'}, status: 'active', lastDelivery: {scheduledAt: '2026-01-01T00:00:00.000Z', deliveredAt: '2026-01-01T00:00:01.000Z', messageId: 'receipt-a'}, deliveryHistory: {earlierRecordsUnavailable: false, records: [{scheduledAt: '2026-01-01T00:00:00.000Z', deliveredAt: '2026-01-01T00:00:01.000Z', messageId: 'receipt-a'}]}} as never);
  await schedule.close(); await schedules.close();
  const pa = await openMigrationStorage(join(home, 'pa', encode('personal:binding:2')));
  const personal = await pa.sessions.create({id: SessionId('pa-current'), version: SESSION_FORMAT_VERSION, createdAt: 1, isSeeded: false}); await personal.flush(); await personal.close(); await pa.close();
  await mkdir(join(home, 'exports')); await writeFile(join(home, 'exports', `${encode('a-old')}.jsonl`), 'prior readable export\n');
  await writeFile(join(home, '.credentials.yaml'), 'version: 1\nrefs:\n  NANO_FIXTURE_KEY: fixture-credential\nrecords: {}\n', {mode: 0o600});
  return {config, home, events};
}

it('splits old roots, native descendants, fork prefixes, attachments and business domains while preserving product journals', async () => {
  const {config, home} = await fixture();
  const product = await Promise.all(['node.sqlite3', 'global.sqlite3'].map(name => readFile(join(home, name))));
  const plan = await planRuntimeMigration(config);
  expect(plan.blockers).toEqual([]);
  expect(plan.sessions.filter(s => s.agentId === 'a').map(s => s.id).sort()).toEqual(['a-child', 'a-current', 'a-fork', 'a-old']);
  await applyRuntimeMigration(config); await verifyRuntimeMigration(config);
  expect(await Promise.all(['node.sqlite3', 'global.sqlite3'].map(name => readFile(join(home, name))))).toEqual(product);
  const target = await openMigrationStorage(join(home, 'agents', encode('agent:a')));
  expect((await target.sessions.list()).map(s => s.header.id)).not.toContain('b-current');
  const fork = await target.sessions.open(SessionId('a-fork'), 'read'); expect(fork.inheritedEventCount).toBe(2); await fork.close();
  const workflow = await target.domain.open(workflowDomain); expect(workflow.table('runs').get(encode('workflow'))?.state).toBe('paused'); await workflow.close(); await target.close();
  const completed = await readFile(join(home, RUNTIME_LAYOUT_MARKER), 'utf8');
  await applyRuntimeMigration(config); await verifyRuntimeMigration(config);
  expect(await readFile(join(home, RUNTIME_LAYOUT_MARKER), 'utf8')).toBe(completed);
});

it('resumes an interrupted native prefix without appending duplicate events and permits restoring the untouched source backup', async () => {
  const {config, home} = await fixture();
  const backup = await mkdtemp(join(tmpdir(), 'nano-migration-backup-')); homes.push(backup); await cp(home, backup, {recursive: true});
  const staged = await openMigrationStorage(join(home, '.agent-runtime-migration', 'agents', encode('agent:a')));
  const source = await openMigrationStorage(home), reader = await source.sessions.open(SessionId('a-current'), 'read');
  const writer = await staged.sessions.create(reader.header); await writer.append((await reader.read(0, 1)).events); await writer.close(); await reader.close(); await source.close(); await staged.close();
  await applyRuntimeMigration(config); await verifyRuntimeMigration(config);
  // A post-verify retry of a partially promoted cutover still checks every record.
  await rename(join(home, RUNTIME_LAYOUT_MARKER), join(home, 'saved-marker.json'));
  await verifyRuntimeMigration(config);
  const restored = {...config, home: backup};
  const restoredPlan = await planRuntimeMigration(restored); expect(restoredPlan.blockers).toEqual([]); expect(restoredPlan.sessions).toHaveLength(6);
  await applyRuntimeMigration(restored); await verifyRuntimeMigration(restored);
});

it('blocks unknown ownership, source drift, live process evidence and target contamination', async () => {
  const {config, home} = await fixture();
  await expect(planRuntimeMigration({...config, stoppedPids: [process.pid]})).rejects.toThrow('still alive');
  const unknown = await openMigrationStorage(home);
  const handle = await unknown.sessions.create({id: SessionId('unknown'), version: SESSION_FORMAT_VERSION, createdAt: 1, isSeeded: false}); await handle.flush(); await handle.close(); await unknown.close();
  expect((await planRuntimeMigration(config)).blockers).toContain('Unowned session unknown');
  await expect(applyRuntimeMigration(config)).rejects.toThrow('Unowned session unknown');
  const db = new DatabaseSync(join(home, 'node.sqlite3'));
  db.prepare('INSERT INTO sessions VALUES(?,?,?)').run('unknown', 'a', JSON.stringify({sessionId: 'unknown', agentId: 'a', ownerId: 'owner'})); db.close();
  await applyRuntimeMigration(config);
  const target = await openMigrationStorage(join(home, '.agent-runtime-migration', 'agents', encode('agent:a')));
  const foreign = await target.sessions.create({id: SessionId('foreign'), version: SESSION_FORMAT_VERSION, createdAt: 1, isSeeded: false}); await foreign.flush(); await foreign.close(); await target.close();
  await expect(verifyRuntimeMigration(config)).rejects.toThrow('foreign sessions');
  await writeFile(join(home, '.env'), 'NEW_SOURCE_VALUE=changed\n');
  await expect(applyRuntimeMigration(config)).rejects.toThrow('Source snapshot differs');
});

it('refuses conflicting native lineage and unknown durable domains instead of choosing an owner', async () => {
  const {config, home} = await fixture();
  const db = new DatabaseSync(join(home, 'node.sqlite3'));
  db.prepare('INSERT INTO sessions VALUES(?,?,?)').run('a-child', 'b', JSON.stringify({sessionId: 'a-child', agentId: 'b', ownerId: 'owner'})); db.close();
  await mkdir(join(home, 'storages', 'unknown_plugin_domain'));
  const plan = await planRuntimeMigration(config);
  expect(plan.blockers).toContain('Conflicting ownership of session a-child: b, a');
  expect(plan.blockers.some(value => value.includes('Unsupported durable domain'))).toBe(true);
  await expect(applyRuntimeMigration(config)).rejects.toThrow('Migration blocked');
  await expect(readFile(join(home, RUNTIME_LAYOUT_MARKER))).rejects.toMatchObject({code: 'ENOENT'});
});
