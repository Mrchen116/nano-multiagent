import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it } from 'vitest';
import { PersonalMemoryStore, type PersonalMemoryChange } from '../src/knowledge/personal-memory.js';

const homes: string[] = [];
afterEach(async () => { await Promise.all(homes.map(home => rm(home, { recursive: true, force: true }))); homes.length = 0; });
async function fixture() {
  const home = await mkdtemp(join(tmpdir(), 'nano-personal-memory-')); homes.push(home);
  const store = new PersonalMemoryStore(home, { ownerId: 'owner', agentId: 'pa', bindingId: 'binding' });
  const root = join(home, '.nanoassistant/memory');
  return { home, root, store };
}
const source = (id: string) => ({ id, kind: 'im_message', authorId: 'owner', subjectRef: 'owner', verified: true });
const context = (id = 'message-1') => ({ sessionId: 'session', sources: [source(id)] });
const add = (key: string, content: string, sourceId = 'message-1'): PersonalMemoryChange => ({ action: 'upsert', idempotency_key: key, target: 'user', kind: 'preference', subject_ref: 'owner', domain: 'travel', content, certainty: 'explicit', source_refs: [sourceId] });

it('keeps structured records authoritative, bounded projections and body-free idempotent receipts', async () => {
  const { store, root } = await fixture();
  const first = await store.execute(add('a', 'Avoid red-eye flights'), context());
  expect(first).toMatchObject({ success: true, revision: 1 });
  expect(await store.execute(add('a', 'Avoid red-eye flights'), context())).toEqual(first);
  await expect(store.execute(add('a', 'changed payload'), context())).rejects.toThrow('Idempotency');
  await store.execute(add('b', 'Long preference '.repeat(300), 'message-2'), context('message-2'));
  await writeFile(join(root, 'USER.md'), 'tampered projection');
  const snapshot = await store.snapshot();
  expect(snapshot.records).toHaveLength(2);
  expect([...snapshot.projections.user].length).toBeLessThanOrEqual(1375);
  expect(snapshot.projections.user).not.toContain('tampered');
  expect(await readFile(join(root, 'USER.md'), 'utf8')).toBe(snapshot.projections.user);
  expect(JSON.stringify(JSON.parse(await readFile(join(root, 'records.json'), 'utf8')).receipts)).not.toContain('Avoid red-eye');
});

it('serializes concurrent writes and refuses stale record or maintenance scope revisions', async () => {
  const { store } = await fixture();
  await Promise.all([store.execute(add('a', 'First'), context()), store.execute(add('b', 'Second', 'message-2'), context('message-2'))]);
  const snapshot = await store.snapshot(); expect(snapshot.revision).toBe(2); expect(snapshot.records).toHaveLength(2);
  const record = snapshot.records.find(record => record.content === 'First')!;
  await store.execute({ ...add('c', 'Corrected', 'correction'), id: record.id, expected_revision: record.revision }, context('correction'));
  await expect(store.execute({ ...add('d', 'Stale', 'maintenance'), id: record.id, expected_revision: record.revision }, context('maintenance'))).rejects.toThrow('revision');
  await expect(store.execute(add('e', 'Stale append'), { ...context(), expectedScopeRevision: snapshot.revision })).rejects.toThrow('revision');
  expect((await store.snapshot()).records.find(item => item.id === record.id)?.content).toBe('Corrected');
});

it('forgets bodies, fences old inputs durably and prevents source/content and receipt replay', async () => {
  const { store, home, root } = await fixture();
  await store.execute(add('a', 'Secret preference'), context());
  const record = (await store.snapshot()).records[0]!;
  const forget: PersonalMemoryChange = { action: 'forget', id: record.id, expected_revision: record.revision, idempotency_key: 'forget' };
  expect(await store.execute(forget, context('forget-message'))).toMatchObject({ status: 'pending', cleanup: { records: 'complete', contexts: 'pending', history: 'pending', notes: 'pending' } });
  const restarted = new PersonalMemoryStore(home, { ownerId: 'owner', agentId: 'pa', bindingId: 'binding' });
  expect((await restarted.snapshot()).pendingForgets).toHaveLength(1);
  expect(await readFile(join(root, 'records.json'), 'utf8')).not.toContain('Secret preference');
  expect(await readFile(join(root, 'USER.md'), 'utf8')).not.toContain('Secret preference');
  await expect(restarted.execute(add('new', 'Different interpretation'), context())).rejects.toThrow('forgotten');
  await expect(restarted.execute(add('new2', 'Secret preference', 'new-source'), context('new-source'))).rejects.toThrow('forgotten');
  expect(await restarted.execute(add('a', 'Secret preference'), context())).toMatchObject({ status: 'invalidated' });
  expect(await restarted.completeForget('forget', { contexts: true, history: true, notes: false })).toMatchObject({ status: 'pending' });
  expect(await restarted.completeForget('forget', { contexts: true, history: true, notes: true })).toMatchObject({ status: 'complete' });
  expect(await restarted.execute(forget, context('forget-message'))).toMatchObject({ status: 'complete' });
  const snapshot = await restarted.snapshot(); expect(snapshot.pendingForgets).toHaveLength(0); expect(snapshot.forgetFence?.revision).toBe(2);
});

it('requires explicit migration, preserves legacy backup and migrates only once', async () => {
  const { store, root } = await fixture();
  await mkdir(root, { recursive: true });
  const legacy = 'Older preference\n<!-- source: {"session_id":"old"} -->\n§\nSecond preference';
  await writeFile(join(root, 'USER.md'), legacy);
  expect((await store.snapshot()).mode).toBe('legacy');
  await expect(store.execute(add('a', 'Do not silently migrate'), context())).rejects.toThrow('migration');
  const migrate: PersonalMemoryChange = { action: 'migrate', idempotency_key: 'migration' };
  await store.execute(migrate, context());
  const snapshot = await store.snapshot(); expect(snapshot.records).toHaveLength(2);
  expect(snapshot.records.every(record => record.source_refs.every(ref => ref.verified === false))).toBe(true);
  expect(await readFile(join(root, 'legacy-backup/USER.md'), 'utf8')).toBe(legacy);
  await store.execute(migrate, context()); await store.execute({ ...migrate, idempotency_key: 'migration-retry' }, context());
  expect((await store.snapshot()).records).toEqual(snapshot.records);
});

it('rejects cross-owner binding and unverified writes; searches only current matching facts', async () => {
  const { store, home } = await fixture();
  await expect(store.execute(add('bad', 'Unverified'), { sessionId: 'session', sources: [{ ...source('message-1'), verified: false }] })).rejects.toThrow('verified');
  await store.execute(add('a', 'Travel by train'), context());
  await store.execute({ ...add('b', 'Old travel', 'old'), valid_until: '2020-01-01T00:00:00Z' }, context('old'));
  const search = await store.execute({ action: 'search', domain: 'travel', query: 'travel', limit: 1 }, context());
  expect(search).toMatchObject({ records: [{ content: 'Travel by train' }], next_cursor: null });
  const other = new PersonalMemoryStore(home, { ownerId: 'other', agentId: 'pa', bindingId: 'binding' });
  await expect(other.snapshot()).rejects.toThrow('scope');
  await expect(new PersonalMemoryStore(home, { ownerId: 'owner', agentId: 'pa', bindingId: 'replacement' }).snapshot()).rejects.toThrow('scope');
});

it('maps legacy updates only to unique records and retracts without selecting first substring', async () => {
  const { store } = await fixture();
  await store.execute(add('a', 'Travel preference A'), context());
  await store.execute(add('b', 'Travel preference B', 'second'), context('second'));
  await expect(store.execute({ action: 'replace', target: 'user', old_text: 'Travel preference', content: 'Ambiguous', idempotency_key: 'bad' }, context())).rejects.toThrow('uniquely');
  await store.execute({ action: 'replace', target: 'user', old_text: 'preference A', content: 'Updated A', idempotency_key: 'replace' }, context('correction'));
  await store.execute({ action: 'remove', target: 'user', old_text: 'preference B', idempotency_key: 'remove' }, context());
  expect((await store.snapshot()).records.filter(record => record.status === 'active').map(record => record.content)).toEqual(['Updated A']);
});

it('retains committed authority on projection failure and completes projection cleanup on retry', async () => {
  const { store, root } = await fixture();
  await store.execute(add('initial', 'Initial'), context());
  await rm(join(root, 'USER.md'));
  await mkdir(join(root, 'USER.md'));
  const change = add('a', 'Saved despite blocked projection');
  expect(await store.execute(change, context())).toMatchObject({ projection: 'pending' });
  expect((await store.snapshot()).records).toHaveLength(2);
  await rm(join(root, 'USER.md'), { recursive: true });
  expect(await store.execute(change, context())).toMatchObject({ projection: 'complete' });
  expect((await store.snapshot()).records).toHaveLength(2);
});

it('leaves legacy files intact after interrupted migration and recovers without duplicate records', async () => {
  const { store, root } = await fixture();
  await mkdir(join(root, 'legacy-backup'), { recursive: true });
  await writeFile(join(root, 'USER.md'), 'Legacy owner preference');
  await writeFile(join(root, 'MEMORY.md'), 'Legacy environment');
  // A real filesystem failure on the second backup occurs before authority commits.
  await mkdir(join(root, 'legacy-backup/MEMORY.md'));
  const change: PersonalMemoryChange = { action: 'migrate', idempotency_key: 'migration' };
  await expect(store.execute(change, context())).rejects.toThrow();
  await expect(readFile(join(root, 'records.json'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
  expect(await readFile(join(root, 'USER.md'), 'utf8')).toBe('Legacy owner preference');
  expect(await readFile(join(root, 'MEMORY.md'), 'utf8')).toBe('Legacy environment');
  await rm(join(root, 'legacy-backup/MEMORY.md'), { recursive: true });
  await store.execute(change, context());
  expect((await store.snapshot()).records).toHaveLength(2);
});

it('forgets previous corrected versions and permits purging a retracted record', async () => {
  const { store, root } = await fixture();
  await store.execute(add('a', 'Original private fact'), context());
  const original = (await store.snapshot()).records[0]!;
  await store.execute({ ...add('b', 'Corrected private fact', 'correction'), id: original.id, expected_revision: 1 }, context('correction'));
  await store.execute({ action: 'retract', id: original.id, expected_revision: 2, idempotency_key: 'retract' }, context());
  await store.execute({ action: 'forget', id: original.id, expected_revision: 3, idempotency_key: 'forget' }, context());
  const persisted = await readFile(join(root, 'records.json'), 'utf8');
  expect(persisted).not.toContain('Original private fact'); expect(persisted).not.toContain('Corrected private fact');
  await expect(store.execute(add('replay', 'Original private fact', 'new'), context('new'))).rejects.toThrow('forgotten');
  await expect(store.execute(add('source-replay', 'Other summary'), context())).rejects.toThrow('forgotten');
  expect(await store.execute({ action: 'get', id: original.id }, context())).toMatchObject({ records: [] });
});

it('uses revision-bound pagination and excludes future and retracted facts from search and projections', async () => {
  const { store } = await fixture();
  await store.execute(add('a', 'Alpha'), context());
  await store.execute(add('b', 'Beta', 'b'), context('b'));
  await store.execute({ ...add('future', 'Future', 'future'), valid_from: '2999-01-01T00:00:00Z' }, context('future'));
  const first = await store.search({ action: 'search', limit: 1 });
  const second = await store.search({ action: 'search', limit: 1, cursor: first.next_cursor! });
  expect(first.records[0]!.id).not.toBe(second.records[0]!.id); expect(second.next_cursor).toBeNull();
  const record = first.records[0]!;
  await store.execute({ action: 'retract', id: record.id, expected_revision: record.revision, idempotency_key: 'retract' }, context());
  await expect(store.search({ action: 'search', cursor: first.next_cursor! })).rejects.toThrow('revision');
  expect((await store.search({ action: 'search' })).records).toHaveLength(1);
  expect((await store.snapshot()).projections.user).not.toContain('Future');
  expect((await store.snapshot()).projections.user).not.toContain(record.content);
});

it('forgets the selected fact and its duplicates while preserving other facts from the same message', async () => {
  const { store } = await fixture();
  await store.execute(add('a', 'Forget this fact'), context());
  await store.execute(add('b', 'Keep this unrelated fact'), context());
  await store.execute(add('duplicate', 'Forget this fact', 'duplicate-source'), context('duplicate-source'));
  const selected = (await store.snapshot()).records.find(record => record.content === 'Forget this fact')!;
  await store.execute({ action: 'forget', id: selected.id, expected_revision: 1, idempotency_key: 'forget' }, context());
  expect((await store.search({ action: 'search' })).records.map(record => record.content)).toEqual(['Keep this unrelated fact']);
});
