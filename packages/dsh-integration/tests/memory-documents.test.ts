import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
import { execFileSync } from 'node:child_process';
import { rename, symlink, mkdtemp, mkdir, readFile, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import { MemoryDocuments } from '../src/knowledge/memory-documents.js';

const fs = new LocalFileSystem(new Context(), { cwd: process.cwd(), diffBasisMaxBytes: 10485760 });
const cleanups: Array<() => Promise<void>> = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });
async function library() {
  const workspace = await mkdtemp(join(tmpdir(), 'nano-documents-'));
  cleanups.push(() => rm(workspace, { recursive: true, force: true }));
  const documents = await MemoryDocuments.open(workspace, 'personal', fs);
  cleanups.push(() => documents.close());
  return { documents, workspace, root: documents.root };
}

describe('current document memory', () => {
  it('uses saved memory during initial source refresh and after a new conversation', async () => {
    const { documents } = await library();
    documents.markSourcesPending();
    expect((await documents.context()).entry).toContain('Personal');
    await documents.syncSources({ revision: '1', allowed: ['first-chat'], excluded: [] });
    expect((await documents.context()).entry).toContain('Personal');
    await documents.syncSources({ revision: '2', allowed: ['first-chat', 'new-chat'], excluded: [] });
    expect((await documents.context()).entry).toContain('Personal');
    const before = (await documents.versions())['MEMORY.md']!;
    await documents.apply({ operationId: 'dreaming-save', path: 'MEMORY.md', beforeHash: before, content: 'Updated key memory.' });
    expect((await documents.context()).entry).toBe('Updated key memory.');
    expect(await documents.context()).not.toHaveProperty('exclusions');
  });

  it('ignores retired forgetting registries without changing saved memory', async () => {
    const {documents, workspace} = await library();
    const entry = (await documents.context()).entry;
    await documents.close();
    const statePath = join(workspace, '.nanoassistant/maintenance/documents.json');
    const state = JSON.parse(await readFile(statePath, 'utf8'));
    state.exclusions = [{requestRef:'old-request',paths:['MEMORY.md'],sources:['old-chat']}];
    await writeFile(statePath, JSON.stringify(state));
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs);
    cleanups.push(() => reopened.close());
    expect((await reopened.context()).entry).toBe(entry);
    expect(await reopened.context()).not.toHaveProperty('exclusions');
    expect(await reopened.status()).not.toHaveProperty('exclusions');
    await reopened.syncSources({revision:'current',allowed:['old-chat'],excluded:[]});
    expect(JSON.parse(await readFile(statePath,'utf8'))).not.toHaveProperty('exclusions');
  });

  it.each(['workspace-write', 'read-only'] as const)('uses the trusted owner root without widening %s for initialization and publication', async mode => {
    const workspace = await mkdtemp(join(tmpdir(), 'nano-document-policy-'));
    const workspaceRoot = await realpath(workspace);
    cleanups.push(() => rm(workspace, { recursive: true, force: true }));
    const guarded: FileSystem = new LocalFileSystem(new Context(), { cwd: process.cwd(), diffBasisMaxBytes: 10485760 });
    Object.defineProperty(guarded, 'sandboxMode', { get: () => mode });
    const write = guarded.writeText.bind(guarded);
    const writes = vi.spyOn(guarded, 'writeText').mockImplementation((target, content, intent, signal, policy) => {
      expect(policy).toEqual({ mode, workspaceRoot });
      if (policy!.mode === 'read-only') throw new Error('Read-only memory backend');
      return write(target, content, intent, signal, policy);
    });
    if (mode === 'read-only') {
      await expect(MemoryDocuments.open(workspace, 'expert', guarded)).rejects.toThrow('Read-only memory backend');
      await expect(readFile(join(workspace, '.nanoassistant/memory/MEMORY.md'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
      return;
    }
    const documents = await MemoryDocuments.open(workspace, 'expert', guarded);
    cleanups.push(() => documents.close());
    await expect(documents.apply({ operationId: 'scope', path: 'knowledge/scope.md', beforeHash: null, content: 'Owner-scoped publication.' })).resolves.toMatchObject({ saved: true });
    expect(writes).toHaveBeenCalledTimes(2);
  });

  it('keeps current memory readable after a document change and reopening', async () => {
    const { documents, workspace, root } = await library();
    await mkdir(join(root, 'knowledge'), { recursive: true });
    await writeFile(join(root, 'knowledge/preferences.md'), 'Private updates only.');
    await documents.refresh();
    const versions = await documents.versions();
    await documents.checkpoint(versions, 0);
    expect((await documents.context()).entry).toContain('Personal');
    await writeFile(join(root, 'knowledge/preferences.md'), 'Ask before any update.');
    await documents.invalidate('knowledge/preferences.md');
    expect((await documents.context()).entry).toContain('Personal');
    await documents.close();
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs);
    cleanups.push(() => reopened.close());
    expect((await reopened.context()).entry).toContain('Personal');
    await expect(reopened.checkpoint(versions, 0)).rejects.toThrow(/changed/);
  });

  it('applies a planned file once, preserves a third version, and reports Git separately', async () => {
    const { documents, root } = await library();
    const first = await documents.apply({ operationId: 'run:page', path: 'knowledge/preference.md', beforeHash: null, content: 'Private only.' });
    expect(first).toMatchObject({ saved: true, versionRecorded: true });
    expect(await documents.apply({ operationId: 'run:page', path: 'knowledge/preference.md', beforeHash: null, content: 'Private only.' })).toEqual(first);
    await writeFile(join(root, 'knowledge/preference.md'), 'Human correction.');
    const conflict = await documents.apply({ operationId: 'run:conflict', path: 'knowledge/preference.md', beforeHash: first.afterHash, content: 'Old automatic conclusion.' });
    expect(conflict).toMatchObject({ saved: false, versionRecorded: false });
    expect(await readFile(join(root, 'knowledge/preference.md'), 'utf8')).toBe('Human correction.');
    await rm(join(root, '.git'), { recursive: true });
    const saved = await documents.apply({ operationId: 'run:no-git', path: 'knowledge/other.md', beforeHash: null, content: 'Still readable.' });
    expect(saved).toMatchObject({ saved: true, versionRecorded: false });
    expect(await readFile(join(root, 'knowledge/other.md'), 'utf8')).toBe('Still readable.');
  });

  it('keeps foreground memory readable while background source checks reject stale checkpoints', async () => {
    const { documents, workspace } = await library();
    const versions = await documents.versions();
    await documents.checkpoint(versions, 0);
    await documents.syncSources({ revision: '1', allowed: ['conversation-a'], excluded: [] });
    const allowed = await documents.status();
    await documents.checkpoint(await documents.versions(), allowed.generation);
    await documents.syncSources({ revision: '1', allowed: [], excluded: ['conversation-a'] });
    const revoked = await documents.status();
    expect(revoked.generation).toBeGreaterThan(allowed.generation);
    expect((await documents.context()).entry).toContain('Personal');
    await expect(documents.checkpoint(versions, allowed.generation)).rejects.toThrow(/generation/);
    await documents.close();
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs);
    cleanups.push(() => reopened.close());
    expect((await reopened.context()).entry).toContain('Personal');
    await reopened.syncSources({ revision: '1', allowed: [], excluded: ['conversation-a'] });
    expect((await reopened.status()).generation).toBe(revoked.generation);
  });
});

it('recovers a committed file after a lost write receipt without writing its bytes again', async () => {
  const { documents, workspace, root } = await library();
  const operation={operationId:'lost-receipt',path:'knowledge/recovery.md',beforeHash:null,content:'Saved before the interruption.'};
  const original=fs.writeText.bind(fs);let writes=0;
  const { vi }=await import('vitest');
  const fault=vi.spyOn(fs,'writeText').mockImplementation(async(...args)=>{
    writes++;const result=await original(...args);if(writes===1)throw new Error('Crash after atomic publication, before receipt');return result;
  });
  try {
    expect(await documents.apply(operation)).toMatchObject({saved:false});
    expect(await readFile(join(root,operation.path),'utf8')).toBe(operation.content);
    await documents.close();
    const recovered=await MemoryDocuments.open(workspace,'personal',fs);cleanups.push(()=>recovered.close());
    expect(await recovered.apply(operation)).toMatchObject({saved:true,versionRecorded:true});
    expect(writes).toBe(1);
    await writeFile(join(root,operation.path),'New human correction.');
    await recovered.apply(operation);
    expect(await readFile(join(root,operation.path),'utf8')).toBe('New human correction.');
  } finally {fault.mockRestore();}
});

it('retains verified unrelated pages for scoped edits but invalidates all pages after source revocation', async () => {
  const {documents} = await library();
  await documents.apply({operationId:'a',path:'knowledge/a.md',beforeHash:null,content:'A'});
  await documents.apply({operationId:'b',path:'knowledge/b.md',beforeHash:null,content:'B'});
  await documents.checkpoint(await documents.versions(),0);
  await documents.apply({operationId:'edit-a',path:'knowledge/a.md',beforeHash:(await documents.versions())['knowledge/a.md']!,content:'Corrected A'});
  const versions=await documents.versions();
  expect(documents.unverifiedPaths(versions,0)).toEqual(['knowledge/a.md']);
  await documents.syncSources({revision:'revoked',allowed:[],excluded:['source']});
  expect(documents.unverifiedPaths(versions,(await documents.status()).generation)).toEqual(Object.keys(versions));
});

describe('native Git batch observation', () => {
  const git = (cwd: string, ...args: string[]) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
  const commit = (root: string) => {
    git(root, 'add', '-A');
    git(root, '-c', 'user.name=Memory test', '-c', 'user.email=memory@test.local', 'commit', '-qm', 'Organize memory');
    return git(root, 'rev-parse', 'HEAD');
  };
  const signal = () => new AbortController().signal;

  it('observes native additions, edits, moves and deletions without advancing verification', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, 'old.md'), 'Move this knowledge.');
    await writeFile(join(root, 'remove.md'), 'Obsolete knowledge.');
    commit(root);
    const before = await documents.observeBatch(await documents.versions(), 'setup');
    await documents.finalizeBatch(before.versions, 0, before.receipts, signal());
    await rename(join(root, 'old.md'), join(root, 'moved.md'));
    await rm(join(root, 'remove.md'));
    await writeFile(join(root, 'new page.md'), 'New knowledge.');
    await writeFile(join(root, 'MEMORY.md'), '# Updated memory\n');
    const pending = await documents.observeBatch(before.versions, 'native');
    expect(pending.receipts).toHaveLength(5);
    expect(pending.receipts.every(receipt => receipt.saved && !receipt.versionRecorded)).toBe(true);
    expect(pending.receipts.filter(receipt => receipt.afterHash === null).map(receipt => receipt.path)).toEqual(['old.md', 'remove.md']);
    expect((await documents.gitChanges()).every(change => change.supported)).toBe(true);
    expect((await documents.finalizeBatch(pending.versions, 0, pending.receipts, signal())).changes).toHaveLength(5);
    const head = commit(root);
    const observed = await documents.observeBatch(before.versions, 'native');
    expect(observed.receipts.every(receipt => receipt.saved && receipt.versionRecorded && receipt.commit === head)).toBe(true);
    expect(await documents.needsVerification()).toBe(true);
    const finalized = await documents.finalizeBatch(observed.versions, 0, observed.receipts, signal());
    expect(finalized.changes).toEqual([]);
    expect(await documents.needsVerification()).toBe(false);
    expect((await documents.observeBatch(observed.versions, 'no-change')).receipts).toEqual([]);
  });

  it('settles earlier uncommitted receipts when a later run only commits existing files',async()=>{
    const {documents,root}=await library();const initial=await documents.versions();
    await writeFile(join(root,'pending.md'),'Retained after failure.');
    const first=await documents.observeBatch(initial,'failed');
    expect(first.receipts[0]?.versionRecorded).toBe(false);
    const head=commit(root);
    const resumed=await documents.observeBatch(first.versions,'retry');
    expect(resumed.receipts).toEqual([]);
    expect((await documents.status()).receipts.find(receipt=>receipt.operationId==='failed:pending.md')).toMatchObject({versionRecorded:true,commit:head});
  });

  it('returns dirty invalid paths for the same Agent to repair before validating the clean repository',async()=>{
    const {documents,root}=await library();const initial=await documents.versions();
    await rm(join(root,'MEMORY.md'));await writeFile(join(root,'scratch.txt'),'Temporary scratch.');
    const observed=await documents.observeBatch(initial,'repair');
    expect((await documents.finalizeBatch(observed.versions,0,observed.receipts,signal())).changes).toEqual(expect.arrayContaining([expect.objectContaining({path:'MEMORY.md'}),expect.objectContaining({path:'scratch.txt',supported:false})]));
  });

  it('records already committed results after cancellation or source revocation, retaining all files', async () => {
    const {documents, root, workspace} = await library();
    const allowed = await documents.syncSources({revision:'1', allowed:['chat-a'], excluded:[]});
    const before = await documents.versions();
    await writeFile(join(root, 'saved.md'), 'Saved evidence.');
    const head = commit(root);
    await writeFile(join(root, 'pending.md'), 'Uncommitted evidence.');
    await documents.syncSources({revision:'2', allowed:[], excluded:['chat-a']});
    const observed = await documents.observeBatch(before, 'interrupted');
    expect(observed.receipts).toEqual(expect.arrayContaining([
      expect.objectContaining({path:'saved.md', saved:true, versionRecorded:true, commit:head}),
      expect.objectContaining({path:'pending.md', saved:true, versionRecorded:false}),
    ]));
    await expect(documents.finalizeBatch(observed.versions, allowed.generation, observed.receipts, signal())).rejects.toThrow(/generation/);
    const cancelled = new AbortController(); cancelled.abort();
    await expect(documents.finalizeBatch(observed.versions, (await documents.status()).generation, observed.receipts, cancelled.signal)).rejects.toThrow();
    await documents.close();
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs); cleanups.push(() => reopened.close());
    expect((await reopened.status()).receipts).toEqual(expect.arrayContaining(observed.receipts));
    expect(await readFile(join(root, 'pending.md'), 'utf8')).toBe('Uncommitted evidence.');
    expect(await reopened.needsVerification()).toBe(true);
  });

  it('reports untracked files despite Git configuration and accepts staged rename as add/delete', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, 'old.md'), 'Knowledge.'); commit(root);
    git(root, 'config', 'status.showUntrackedFiles', 'no');
    await rename(join(root, 'old.md'), join(root, 'new.md'));
    git(root, 'add', '-A');
    await writeFile(join(root, 'manual.txt'), 'Unsupported.');
    expect(await documents.gitChanges()).toEqual([
      {path:'new.md', status:'A ', supported:true},
      {path:'old.md', status:'D ', supported:true},
      {path:'manual.txt', status:'??', supported:false},
    ]);
  });

  it.each(['text', 'hidden', 'symlink', 'missing-entry', 'oversized-entry'])('rejects committed invalid repository shape: %s', async kind => {
    const {documents, root} = await library();
    const before = await documents.versions();
    if (kind === 'text') await writeFile(join(root, 'manual.txt'), 'Not a document.');
    if (kind === 'hidden') await writeFile(join(root, '.hidden.md'), 'Hidden document.');
    if (kind === 'symlink') await symlink('MEMORY.md', join(root, 'alias.md'));
    if (kind === 'missing-entry') await rm(join(root, 'MEMORY.md'));
    if (kind === 'oversized-entry') await writeFile(join(root, 'MEMORY.md'), 'x'.repeat(8001));
    commit(root);
    const observed = await documents.observeBatch(before, kind);
    expect(await documents.gitChanges()).toEqual([]);
    await expect(documents.finalizeBatch(observed.versions, 0, observed.receipts, signal())).rejects.toThrow(/document|MEMORY.md/);
  });

  it('does not mistake a clean Git conversion for matching actual document bytes', async () => {
    const {documents, root} = await library();
    const before = await documents.versions();
    git(root, 'config', 'core.autocrlf', 'true');
    await writeFile(join(root, 'windows.md'), 'Line one.\r\nLine two.\r\n');
    commit(root);
    const observed = await documents.observeBatch(before, 'converted');
    expect(await documents.gitChanges()).toEqual([]);
    expect(observed.receipts[0]).toMatchObject({saved:true, versionRecorded:false});
    await expect(documents.finalizeBatch(observed.versions, 0, observed.receipts, signal())).rejects.toThrow(/Git version/);
  });

  it('allows an unchanged preexisting oversized entry while checking other updates', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, 'MEMORY.md'), 'x'.repeat(8001)); commit(root);
    const before = (await documents.observeBatch(await documents.versions(), 'preexisting')).versions;
    await writeFile(join(root, 'body.md'), 'Verified update.'); commit(root);
    const observed = await documents.observeBatch(before, 'body-only');
    expect((await documents.finalizeBatch(observed.versions, 0, observed.receipts, signal())).changes).toEqual([]);
  });
});
