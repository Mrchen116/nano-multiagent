import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { copyFile, mkdir, readdir, readFile, rename, stat, writeFile, chmod } from 'node:fs/promises';
import { join, isAbsolute } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { Context } from '@deepseek-ai/cordis';
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl';
import { LocalAttachmentStore, commitPreparedImageFile } from '@deepseek-ai/dsh-attachment-local';
import { CREDENTIALS_FILENAME, parseCredentialsDocument } from '@deepseek-ai/dsh-credentials-local';
import { Storage } from '@deepseek-ai/dsh-storage';
import * as StorageJson from '@deepseek-ai/dsh-storage-json';
import { DomainFacility, type DomainSpec, type Domain } from '@deepseek-ai/dsh-storage-domain';
import { SessionId, type SessionEvent, type SessionHeader } from '@deepseek-ai/dsh-session';
import type { SessionHandle } from '@deepseek-ai/dsh-session-persistence';
import type { FileAttachmentRef, ImageAttachmentRef } from '@deepseek-ai/dsh-attachment';
import { scheduleDomain } from '@deepseek-ai/dsh-schedule';
import { historyDomain } from './history.js';
import { descendantDomain } from './descendants.js';
import { knowledgeDomain } from './knowledge/state.js';
import { workflowDomain } from './workflow/state.js';
import { modelDomain } from './model-policy.js';
import { modelRunsDomain } from './model-fallback.js';
import { toolViewsDomain } from './tool-presentation.js';
import { trajectoryRunsDomain } from './trajectory-runs.js';
import { trajectorySourcesDomain } from './trajectory-attachments.js';
import { approvalDomain } from './policy/audit.js';

const domains: DomainSpec[] = [historyDomain, descendantDomain, knowledgeDomain, workflowDomain,
  modelDomain, modelRunsDomain, toolViewsDomain, trajectoryRunsDomain, trajectorySourcesDomain, approvalDomain];
const PAGE_SIZE = 256;
const STAGING = '.agent-runtime-migration';
export const RUNTIME_LAYOUT_MARKER = 'agent-runtime-layout.json';
const encode = (value: string) => Buffer.from(value).toString('base64url');
const decode = (value: string) => Buffer.from(value, 'base64url').toString();
const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const scheduleKey = (agentId: string) => createHash('sha256').update(agentId).digest('hex');

export interface RuntimeMigrationConfig {
  nodeId: string;
  ownerId: string;
  home: string;
  agents: { agentId: string; partitionKey?: string }[];
  /** Deployment operator attests that Node, old hosts and automatic restart are stopped. */
  stopped: true;
  /** Previously recorded process IDs provide an additional live-process refusal. */
  stoppedPids?: number[];
}
interface Partition { agentId: string; key: string; home: string; sourceHome: string }
interface SessionUnit { sourceHome: string; agentId: string; id: string; header: SessionHeader; inheritedEventCount: number; eventCount: number; digest: string }
interface DomainUnit { sourceHome: string; agentId: string; domain: string; table: string; key: string; value: unknown; schedule?: boolean }
interface FileUnit { sourceHome: string; agentId: string; relative: string; digest: string }
export interface RuntimeMigrationPlan {
  version: 1;
  nodeId: string;
  sourceDigest: string;
  partitions: Partition[];
  sessions: SessionUnit[];
  records: DomainUnit[];
  exports: FileUnit[];
  blockers: string[];
  preservedProductFiles: { path: string; digest: string }[];
}
interface MigrationState { version: 1; sourceDigest: string; completed: string[] }
interface LayoutMarker { version: 1; nodeId: string; sourceDigest: string; completedAt: string; partitions: {agentId: string; key: string; home: string}[] }

async function exists(path: string) { try { await stat(path); return true; } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false; throw error; } }
async function names(path: string) { return await exists(path) ? (await readdir(path)).sort() : []; }
async function hashFile(path: string) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
}
async function atomicJson(path: string, value: unknown) {
  await mkdir(join(path, '..'), {recursive: true, mode: 0o700});
  await writeFile(`${path}.tmp`, JSON.stringify(value, null, 2) + '\n', {mode: 0o600, flush: true});
  await rename(`${path}.tmp`, path);
}
function assertStopped(config: RuntimeMigrationConfig) {
  if (config.stopped !== true) throw new Error('Migration requires confirmed stopped Node, DSH hosts and automatic restart');
  if (!isAbsolute(config.home) || !config.nodeId || !config.ownerId) throw new Error('Absolute home, nodeId and ownerId are required');
  for (const pid of config.stoppedPids ?? []) {
    if (!Number.isSafeInteger(pid) || pid <= 0) throw new Error('Invalid stopped process ID');
    try { process.kill(pid, 0); } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ESRCH') continue; throw error; }
    throw new Error(`Source process ${pid} is still alive`);
  }
}

/** Open only persistence facilities without Agent creation or execution recovery.
 *
 * Args:
 *   home: Explicit source or staging home.
 *   storageRoot: Domain root, overridden for per-Agent Schedule owners.
 * Returns:
 *   Public persistence facilities and their teardown function.
 */
export async function openMigrationStorage(home: string, storageRoot = join(home, 'storages')) {
  const ctx = new Context();
  const storage = ctx.plugin(Storage); await storage.await();
  const json = ctx.plugin(StorageJson, {root: storageRoot}); await json.await();
  let facility!: DomainFacility;
  const domain = ctx.inject(['storage', 'storage.backend.json'], child => { facility = new DomainFacility(child, {backend: 'json'}); });
  await domain.await();
  const sessions = new JsonlSessionPersistence(ctx, {root: join(home, 'sessions')});
  const attachments = new LocalAttachmentStore(ctx, {dshHome: home});
  return {sessions, attachments, domain: facility, async close() {
    await facility.closeAll();
    await ctx.fiber.dispose();
  }};
}
type MigrationStorage = Awaited<ReturnType<typeof openMigrationStorage>>;

async function sessionSummary(handle: SessionHandle, visit?: (events: readonly SessionEvent[]) => Promise<void>) {
  const hash = createHash('sha256').update(JSON.stringify([handle.header, handle.inheritedEventCount]));
  let count = 0;
  for (;;) {
    const {events} = await handle.read(count, PAGE_SIZE);
    if (!events.length) break;
    for (const event of events) hash.update(JSON.stringify(event) + '\n');
    await visit?.(events); count += events.length;
  }
  return {eventCount: count, digest: hash.digest('hex')};
}

function attachmentRefs(value: unknown): (ImageAttachmentRef | FileAttachmentRef)[] {
  if (!value || typeof value !== 'object') return [];
  if (Array.isArray(value)) return value.flatMap(attachmentRefs);
  const object = value as Record<string, unknown>;
  if ((object.type === 'image' || object.type === 'file') && object.attachment && typeof object.attachment === 'object')
    return [object.attachment as ImageAttachmentRef | FileAttachmentRef];
  return Object.values(object).flatMap(attachmentRefs);
}
async function transferAttachments(events: readonly SessionEvent[], source: MigrationStorage, target?: MigrationStorage) {
  for (const ref of attachmentRefs(events)) {
    if ('mediaType' in ref) {
      const image = await source.attachments.readImage(ref);
      if (target) {
        // Already-normalized bytes must keep the original reference and dimensions.
        await commitPreparedImageFile(target.attachments.root, {ref, data: image.data});
        await target.attachments.readImage(ref);
      }
    } else if (target) {
      const saved = await target.attachments.saveFileStream({data: source.attachments.readFileStream(ref), name: ref.name});
      if (saved.attachmentId !== ref.attachmentId || saved.bytes !== ref.bytes || saved.name !== ref.name) throw new Error('Attachment identity changed');
    } else for await (const _ of source.attachments.readFileStream(ref)) { /* Public reader verifies every byte. */ }
  }
}

function partitionList(config: RuntimeMigrationConfig): Partition[] {
  const seen = new Set<string>(); const agents = new Set<string>();
  return config.agents.map(item => {
    const key = item.partitionKey ?? `agent:${item.agentId}`;
    if (!item.agentId || agents.has(item.agentId) || seen.has(key) || key !== `agent:${item.agentId}` && !/^personal:[^:]+:[1-9]\d*$/.test(key)) throw new Error('Invalid or duplicate Agent partition');
    agents.add(item.agentId); seen.add(key);
    return {agentId: item.agentId, key, home: join(config.home, 'agents', encode(key)),
      sourceHome: key.startsWith('personal:') ? join(config.home, 'pa', encode(key)) : config.home};
  });
}

async function sourceFiles(config: RuntimeMigrationConfig, partitions: Partition[]) {
  const paths: {path: string; digest: string}[] = [];
  async function walk(path: string) {
    if (!await exists(path)) return;
    const info = await stat(path);
    if (info.isDirectory()) for (const name of await names(path)) await walk(join(path, name));
    else paths.push({path, digest: await hashFile(path)});
  }
  for (const home of new Set([config.home, ...partitions.map(p => p.sourceHome)]))
    for (const name of ['sessions', 'storages', 'schedules', 'exports', CREDENTIALS_FILENAME, '.env']) await walk(join(home, name));
  for (const name of ['node.sqlite3', 'global.sqlite3', 'node.sqlite3-wal', 'global.sqlite3-wal']) await walk(join(config.home, name));
  return paths;
}

/** Build an offline ownership plan from every saved binding and native lineage.
 *
 * Args:
 *   config: Stopped source and verified product Agent identities.
 * Returns:
 *   A reviewable plan; unknown or conflicting ownership appears as blockers.
 */
export async function planRuntimeMigration(config: RuntimeMigrationConfig): Promise<RuntimeMigrationPlan> {
  assertStopped(config);
  if (!await exists(config.home)) throw new Error('Source home does not exist');
  const partitions = partitionList(config), blockers: string[] = [];
  const initialFiles = await sourceFiles(config, partitions);
  const owners = new Map<string, string>(), knownAgents = new Set(partitions.map(p => p.agentId));
  const claim = (sessionId: string, agentId: string) => {
    if (!knownAgents.has(agentId)) { blockers.push(`Unknown product Agent ${agentId} for session ${sessionId}`); return false; }
    const existing = owners.get(sessionId);
    if (existing && existing !== agentId) { blockers.push(`Conflicting ownership of session ${sessionId}: ${existing}, ${agentId}`); return false; }
    if (existing) return false;
    owners.set(sessionId, agentId); return true;
  };
  const dbPath = join(config.home, 'node.sqlite3');
  if (await exists(dbPath)) {
    const db = new DatabaseSync(dbPath, {readOnly: true});
    try {
      const owner = db.prepare('SELECT owner_id FROM node_owner').get() as {owner_id: string} | undefined;
      if (owner?.owner_id !== config.ownerId) blockers.push('NodeStore owner does not match migration owner');
      for (const row of db.prepare('SELECT session_id,agent_id,binding FROM sessions').all() as {session_id: string; agent_id: string; binding: string}[]) {
        const binding = JSON.parse(row.binding) as {ownerId: string; sessionId: string; agentId: string};
        if (binding.ownerId !== config.ownerId || binding.sessionId !== row.session_id || binding.agentId !== row.agent_id) blockers.push(`Invalid NodeStore binding ${row.session_id}`);
        else claim(row.session_id, row.agent_id);
      }
    } finally { db.close(); }
  }
  for (const name of await names(join(config.home, 'pa'))) if (!partitions.some(p => p.sourceHome === join(config.home, 'pa', name))) blockers.push(`Unmapped personal home ${name}`);
  const sessions: SessionUnit[] = [], records: DomainUnit[] = [], exports: FileUnit[] = [];
  const pendingRecords: Omit<DomainUnit, 'agentId'>[] = [], edges: [string, string][] = [];
  const sourceHomes = [...new Set([config.home, ...partitions.map(p => p.sourceHome)])];
  for (const home of sourceHomes) {
    const storage = await openMigrationStorage(home);
    try {
      const personal = partitions.find(p => p.sourceHome === home && p.key.startsWith('personal:'));
      for (const {header} of await storage.sessions.list()) {
        if (sessions.some(s => s.id === header.id)) blockers.push(`Session ${header.id} exists in multiple source homes`);
        if (personal) claim(header.id, personal.agentId);
        if (header.parentSession) edges.push([header.parentSession, header.id]);
        const handle = await storage.sessions.open(header.id, 'read');
        try {
          const summary = await sessionSummary(handle, async events => {
            await transferAttachments(events, storage);
            for (const event of events) if (event.seq >= handle.inheritedEventCount && event.type === 'subagent/catalog') edges.push([header.id, event.data.childId]);
          });
          sessions.push({sourceHome: home, id: header.id, agentId: '', header, inheritedEventCount: handle.inheritedEventCount, ...summary});
        } finally { await handle.close(); }
      }
      for (const name of await names(join(home, 'storages'))) {
        const unit = name.replace(/\.json$/, '');
        // Upstream documents this domain as entirely derivable from native logs.
        if (!domains.some(spec => spec.name === unit) && unit !== 'session_projcache') blockers.push(`Unsupported durable domain ${home}/storages/${name}`);
      }
      for (const spec of domains) {
        const domain = await storage.domain.open(spec);
        try {
          for (const table of Object.keys(spec.tables ?? {})) for (const [key, value] of domain.table(table).entries())
            pendingRecords.push({sourceHome: home, domain: spec.name, table, key, value});
        } finally { await domain.close(); }
      }
    } finally { await storage.close(); }
  }
  let changed = true;
  while (changed) { changed = false; for (const [parent, child] of edges) { const owner = owners.get(parent); if (owner) changed = claim(child, owner) || changed; } }
  for (const unit of sessions) {
    const owner = owners.get(unit.id);
    if (!owner) blockers.push(`Unowned session ${unit.id}`);
    else {
      unit.agentId = owner;
      if (partitions.find(p => p.agentId === owner)?.sourceHome !== unit.sourceHome) blockers.push(`Session ${unit.id} is in the wrong source home`);
    }
  }
  for (const record of pendingRecords) {
    const value = record.value as Record<string, unknown>;
    let sessionId: string | undefined;
    let agentId: string | undefined;
    const decoded = decode(record.key);
    if (record.domain === 'nano_approval') sessionId = record.key;
    else if (record.domain === 'nano_tool_views' || record.domain === 'nano_trajectory_sources') sessionId = (JSON.parse(decoded) as string[])[0];
    else if (record.domain === 'nano_knowledge' && record.table === 'counters') sessionId = decoded.replace(/:(memory|skills):iterations$/, '');
    else if (record.domain === 'nano_history' && record.table === 'overrides' || record.domain === 'nano_model' && record.table === 'sessions') sessionId = decoded;
    else sessionId = String(value.rootSessionId ?? value.rootId ?? value.parentSessionId ?? value.sessionId ?? value.source ?? '');
    if (typeof value.agentId === 'string') agentId = value.agentId;
    const fromSession = sessionId ? owners.get(sessionId) : undefined;
    if (agentId && fromSession && agentId !== fromSession) blockers.push(`Conflicting record ${record.domain}/${record.table}/${record.key}`);
    agentId ??= fromSession;
    if (!agentId || !knownAgents.has(agentId)) blockers.push(`Unowned record ${record.domain}/${record.table}/${record.key}`);
    else if (partitions.find(p => p.agentId === agentId)?.sourceHome !== record.sourceHome) blockers.push(`Record ${record.domain}/${record.key} is in the wrong source home`);
    else records.push({...record, agentId});
  }
  for (const home of sourceHomes) {
    for (const name of await names(join(home, 'schedules'))) {
      const partition = partitions.find(p => p.sourceHome === home && scheduleKey(p.agentId) === name);
      if (!partition) { blockers.push(`Unowned schedule directory ${home}/schedules/${name}`); continue; }
      for (const unit of await names(join(home, 'schedules', name)))
        if (unit.replace(/\.json$/, '') !== scheduleDomain.name) blockers.push(`Unsupported Schedule storage ${home}/schedules/${name}/${unit}`);
      const storage = await openMigrationStorage(home, join(home, 'schedules', name));
      try {
        const domain = await storage.domain.open(scheduleDomain);
        for (const [key, value] of domain.table('tasks').entries()) {
          if (owners.get(value.sessionId) !== partition.agentId) blockers.push(`Schedule ${key} refers to a foreign or unknown session`);
          records.push({sourceHome: home, agentId: partition.agentId, domain: scheduleDomain.name, table: 'tasks', key, value, schedule: true});
        }
        await domain.close();
      } finally { await storage.close(); }
    }
    for (const name of await names(join(home, 'exports'))) {
      const id = decode(name.replace(/\.jsonl(?:\.tmp|\.live)?$/, ''));
      const agentId = owners.get(id);
      if (!agentId || !/\.jsonl(?:\.tmp|\.live)?$/.test(name)) blockers.push(`Unowned export ${home}/exports/${name}`);
      else exports.push({sourceHome: home, agentId, relative: join('exports', name), digest: await hashFile(join(home, 'exports', name))});
    }
  }
  const finalFiles = await sourceFiles(config, partitions);
  if (digest(initialFiles) !== digest(finalFiles)) blockers.push('Source changed while planning; stop all writers and take a new snapshot');
  return {version: 1, nodeId: config.nodeId, sourceDigest: digest({files: finalFiles, ownerId: config.ownerId, partitions}),
    partitions, sessions, records, exports, blockers: [...new Set(blockers)],
    preservedProductFiles: finalFiles.filter(file => /\/(node|global)\.sqlite3(?:-wal)?$/.test(file.path))};
}

function stagingHome(config: RuntimeMigrationConfig, partition: Partition) { return join(config.home, STAGING, 'agents', encode(partition.key)); }
async function loadState(config: RuntimeMigrationConfig, plan: RuntimeMigrationPlan): Promise<MigrationState> {
  const path = join(config.home, STAGING, 'state.json');
  if (await exists(path)) {
    const state = JSON.parse(await readFile(path, 'utf8')) as MigrationState;
    if (state.version !== 1 || state.sourceDigest !== plan.sourceDigest) throw new Error('Source snapshot differs from the staged migration; preserve staging and investigate');
    return state;
  }
  return {version: 1, sourceDigest: plan.sourceDigest, completed: []};
}
function requireClean(plan: RuntimeMigrationPlan) {
  if (plan.blockers.length) throw new Error(`Migration blocked:\n${plan.blockers.join('\n')}`);
}
async function marker(config: RuntimeMigrationConfig): Promise<LayoutMarker | undefined> {
  const path = join(config.home, RUNTIME_LAYOUT_MARKER);
  return await exists(path) ? JSON.parse(await readFile(path, 'utf8')) as LayoutMarker : undefined;
}
async function targetHome(config: RuntimeMigrationConfig, partition: Partition) {
  return await exists(stagingHome(config, partition)) ? stagingHome(config, partition) : partition.home;
}

async function copySession(unit: SessionUnit, source: MigrationStorage, target: MigrationStorage) {
  const input = await source.sessions.open(SessionId(unit.id), 'read');
  let output: SessionHandle | undefined;
  try {
    await sessionSummary(input, events => transferAttachments(events, source, target));
    const prior = await target.sessions.stat(SessionId(unit.id));
    output = prior ? await target.sessions.open(SessionId(unit.id), 'write') : await target.sessions.create(input.header,
      input.header.isSeeded ? {inheritedEventCount: input.inheritedEventCount} : undefined);
    // The public decoder refuses a seeded log without its inherited boundary.
    // Materialize that prefix and marker in one atomic first append so a killed
    // migration never leaves an unreadable, partially copied fork to resume.
    if (!prior && input.header.isSeeded) await output.append((await input.read(0, input.inheritedEventCount + 1)).events);
    if (digest([output.header, output.inheritedEventCount]) !== digest([input.header, input.inheritedEventCount])) throw new Error(`Target session metadata mismatch: ${unit.id}`);
    let copied = 0;
    for (;;) {
      const {events} = await output.read(copied, PAGE_SIZE);
      if (!events.length) break;
      const expected = await input.read(copied, events.length);
      if (digest(events) !== digest(expected.events)) throw new Error(`Target session prefix mismatch: ${unit.id}`);
      copied += events.length;
    }
    for (;;) {
      const {events} = await input.read(copied, PAGE_SIZE);
      if (!events.length) break;
      await output.append(events); copied += events.length;
    }
    await output.flush();
    if ((await sessionSummary(output)).digest !== unit.digest) throw new Error(`Copied session verification failed: ${unit.id}`);
  } finally { await output?.close(); await input.close(); }
}

async function copyCredentials(sourceHome: string, target: string) {
  await mkdir(target, {recursive: true, mode: 0o700});
  for (const name of [CREDENTIALS_FILENAME, '.env']) {
    const source = join(sourceHome, name);
    if (!await exists(source)) continue;
    if (name === CREDENTIALS_FILENAME) parseCredentialsDocument(await readFile(source, 'utf8'), source);
    await copyFile(source, join(target, name));
    await chmod(join(target, name), (await stat(source)).mode & 0o777);
  }
}

/** Copy into resumable staging; never replace source data or publish the layout marker.
 *
 * Args:
 *   config: The same stopped source snapshot used for planning.
 * Returns:
 *   Counts of fully copied units; run verify to publish the new layout.
 */
export async function applyRuntimeMigration(config: RuntimeMigrationConfig) {
  if (await marker(config)) return verifyRuntimeMigration(config);
  const plan = await planRuntimeMigration(config); requireClean(plan);
  const state = await loadState(config, plan), statePath = join(config.home, STAGING, 'state.json');
  await atomicJson(statePath, state);
  const complete = async (key: string) => {
    if (!state.completed.includes(key)) { state.completed.push(key); await atomicJson(statePath, state); }
  };
  for (const partition of plan.partitions) {
    if (await exists(partition.home) && !await exists(stagingHome(config, partition))) {
      // A verify interrupted after promotion is resumed by verify, never by writing into a published home.
      throw new Error('A partition is already promoted; run verify to finish the interrupted cutover');
    }
    const home = stagingHome(config, partition); await mkdir(home, {recursive: true, mode: 0o700});
    const source = await openMigrationStorage(partition.sourceHome), target = await openMigrationStorage(home);
    try {
      for (const unit of plan.sessions.filter(unit => unit.agentId === partition.agentId)) {
        await copySession(unit, source, target); await complete(`session:${unit.id}`);
      }
      for (const spec of domains) {
        const domain = await target.domain.open(spec);
        try {
          for (const unit of plan.records.filter(unit => !unit.schedule && unit.agentId === partition.agentId && unit.domain === spec.name)) {
            const table = domain.table(unit.table), existing = table.get(unit.key);
            if (existing !== undefined && digest(existing) !== digest(unit.value)) throw new Error(`Conflicting target record ${unit.domain}/${unit.key}`);
            if (existing === undefined) await table.put(unit.key, unit.value);
          }
        } finally { await domain.close(); }
      }
    } finally { await target.close(); await source.close(); }
    const schedule = await openMigrationStorage(home, join(home, 'schedules', scheduleKey(partition.agentId)));
    try {
      const domain = await schedule.domain.open(scheduleDomain);
      for (const unit of plan.records.filter(unit => unit.schedule && unit.agentId === partition.agentId)) {
        const table = domain.table('tasks'), existing = table.get(unit.key as never);
        if (existing !== undefined && digest(existing) !== digest(unit.value)) throw new Error(`Conflicting target schedule ${unit.key}`);
        if (existing === undefined) await table.put(unit.key as never, unit.value as never);
      }
      await domain.close();
    } finally { await schedule.close(); }
    for (const file of plan.exports.filter(file => file.agentId === partition.agentId)) {
      const path = join(home, file.relative); await mkdir(join(path, '..'), {recursive: true, mode: 0o700});
      await copyFile(join(file.sourceHome, file.relative), path);
    }
    await complete(`partition:${partition.key}`);
  }
  await copyCredentials(config.home, join(config.home, STAGING, 'control'));
  await complete('control');
  return {phase: 'applied', sourceDigest: plan.sourceDigest, sessions: plan.sessions.length, records: plan.records.length, completed: state.completed.length};
}

async function verifyRecords(domain: Domain<DomainSpec>, units: DomainUnit[]) {
  const expected = new Map(units.map(unit => [JSON.stringify([unit.table, unit.key]), digest(unit.value)]));
  for (const table of new Set([...units.map(unit => unit.table), ...Object.keys(domains.find(spec => spec.name === domain.name)?.tables ?? {tasks: true})])) {
    for (const [key, value] of domain.table(table).entries()) {
      const id = JSON.stringify([table, key]);
      if (expected.get(id) !== digest(value)) throw new Error(`Missing, foreign or changed record ${domain.name}/${table}/${key}`);
      expected.delete(id);
    }
  }
  if (expected.size) throw new Error(`Missing records in ${domain.name}`);
}

async function verifyTargetInventory(home: string, partition: Partition, plan: RuntimeMigrationPlan) {
  for (const name of await names(join(home, 'storages')))
    if (!domains.some(spec => spec.name === name.replace(/\.json$/, ''))) throw new Error(`Unexpected target domain ${name}`);
  for (const name of await names(join(home, 'schedules')))
    if (name !== scheduleKey(partition.agentId)) throw new Error(`Foreign schedule owner in ${partition.agentId}`);
  const expectedExports = plan.exports.filter(file => file.agentId === partition.agentId).map(file => file.relative).sort();
  const actualExports = (await names(join(home, 'exports'))).map(name => join('exports', name));
  if (digest(expectedExports) !== digest(actualExports)) throw new Error(`Missing or foreign exports in ${partition.agentId}`);
}

/** Reconcile complete contents before atomically publishing the layout marker.
 *
 * Args:
 *   config: The stopped source used for the migration.
 * Returns:
 *   Verified session/domain counts and the published layout marker path.
 */
export async function verifyRuntimeMigration(config: RuntimeMigrationConfig) {
  const plan = await planRuntimeMigration(config); requireClean(plan);
  const state = await loadState(config, plan), previous = await marker(config);
  if (previous && (previous.version !== 1 || previous.nodeId !== config.nodeId || previous.sourceDigest !== plan.sourceDigest)) throw new Error('Completed marker does not match this source snapshot');
  if (!state.completed.includes('control')) throw new Error('Apply is incomplete');
  for (const partition of plan.partitions) {
    if (!state.completed.includes(`partition:${partition.key}`)) throw new Error(`Apply is incomplete for ${partition.agentId}`);
    const home = await targetHome(config, partition), target = await openMigrationStorage(home);
    try {
      await verifyTargetInventory(home, partition, plan);
      const units = plan.sessions.filter(unit => unit.agentId === partition.agentId);
      if (digest((await target.sessions.list()).map(item => item.header.id).sort()) !== digest(units.map(unit => unit.id).sort())) throw new Error(`Missing or foreign sessions in ${partition.agentId}`);
      for (const unit of units) {
        const handle = await target.sessions.open(SessionId(unit.id), 'read');
        try {
          const summary = await sessionSummary(handle, events => transferAttachments(events, target));
          if (summary.digest !== unit.digest || summary.eventCount !== unit.eventCount) throw new Error(`Session verification failed: ${unit.id}`);
        } finally { await handle.close(); }
      }
      for (const spec of domains) {
        const domain = await target.domain.open(spec);
        try { await verifyRecords(domain, plan.records.filter(unit => !unit.schedule && unit.agentId === partition.agentId && unit.domain === spec.name)); }
        finally { await domain.close(); }
      }
      for (const name of [CREDENTIALS_FILENAME, '.env']) if (await exists(join(home, name))) throw new Error(`Agent ${partition.agentId} has an unexpected credential authority`);
    } finally { await target.close(); }
    const schedules = await openMigrationStorage(home, join(home, 'schedules', scheduleKey(partition.agentId)));
    try {
      const domain = await schedules.domain.open(scheduleDomain);
      try { await verifyRecords(domain as Domain<DomainSpec>, plan.records.filter(unit => unit.schedule && unit.agentId === partition.agentId)); }
      finally { await domain.close(); }
    } finally { await schedules.close(); }
    for (const file of plan.exports.filter(file => file.agentId === partition.agentId))
      if (await hashFile(join(home, file.relative)) !== file.digest) throw new Error(`History export changed: ${file.relative}`);
  }
  const control = await exists(join(config.home, STAGING, 'control')) ? join(config.home, STAGING, 'control') : join(config.home, 'control');
  for (const name of [CREDENTIALS_FILENAME, '.env']) {
    const source = join(config.home, name), target = join(control, name);
    if (await exists(source) !== await exists(target) || await exists(source) && (await hashFile(source) !== await hashFile(target))) throw new Error('Control credentials do not match the source authority');
  }
  if (plan.sourceDigest !== (await planRuntimeMigration(config)).sourceDigest) throw new Error('Source changed during verification');
  if (!previous) {
    await mkdir(join(config.home, 'agents'), {recursive: true, mode: 0o700});
    for (const partition of plan.partitions) {
      const staged = stagingHome(config, partition);
      if (await exists(staged)) {
        if (await exists(partition.home)) throw new Error(`Refusing to replace existing target ${partition.home}`);
        await rename(staged, partition.home);
      }
    }
    if (await exists(join(config.home, STAGING, 'control'))) {
      if (await exists(join(config.home, 'control'))) throw new Error('Refusing to replace an existing control home');
      await rename(join(config.home, STAGING, 'control'), join(config.home, 'control'));
    }
    const completed: LayoutMarker = {version: 1, nodeId: config.nodeId, sourceDigest: plan.sourceDigest,
      completedAt: new Date().toISOString(), partitions: plan.partitions.map(({agentId, key, home}) => ({agentId, key, home}))};
    await atomicJson(join(config.home, RUNTIME_LAYOUT_MARKER), completed);
  }
  return {phase: 'verified', sourceDigest: plan.sourceDigest, sessions: plan.sessions.length, records: plan.records.length,
    preservedProductFiles: plan.preservedProductFiles, marker: join(config.home, RUNTIME_LAYOUT_MARKER)};
}
