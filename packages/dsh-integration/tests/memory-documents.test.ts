import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, writeFile, rm, realpath } from 'node:fs/promises';
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

describe('Agent-initiated Git batches', () => {
  const git = (cwd: string, ...args: string[]) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
  const signal = () => new AbortController().signal;

  it('publishes multiple documents before recording one Agent-initiated commit', async () => {
    const {documents, root} = await library();
    const before = git(root, 'rev-parse', 'HEAD');
    const initial = await documents.versions();
    const receipts = [
      await documents.apply({operationId:'body', path:'knowledge/example with spaces.md', beforeHash:null, content:'Useful experience.\n'}, 0, signal(), {recordVersion:false}),
      await documents.apply({operationId:'entry', path:'MEMORY.md', beforeHash:initial['MEMORY.md']!, content:'# Key memory\n'}, 0, signal(), {recordVersion:false}),
    ];
    expect(receipts).toEqual(receipts.map(receipt => ({...receipt, saved:true, versionRecorded:false})));
    expect(git(root, 'rev-parse', 'HEAD')).toBe(before);

    const versions = await documents.versions();
    expect((await documents.finalizeBatch(initial, 0, receipts, signal())).changes).toHaveLength(2);
    await expect(documents.commitBatch('Stale file versions', initial, 0, signal())).rejects.toThrow('Document versions changed');
    expect(await documents.needsVerification()).toBe(true);
    const {commit} = await documents.commitBatch('Consolidate verified memory', versions, 0, signal());
    expect(commit).toBe(git(root, 'rev-parse', 'HEAD'));
    expect(git(root, 'rev-parse', 'HEAD^')).toBe(before);
    expect(git(root, 'show', '--format=', '--name-only', 'HEAD').split('\n')).toEqual(['MEMORY.md', 'knowledge/example with spaces.md']);

    const finalized = await documents.finalizeBatch(versions, 0, receipts, signal());
    expect(finalized.changes).toEqual([]);
    expect(finalized.receipts).toEqual(receipts.map(receipt => ({...receipt, versionRecorded:true, commit})));
    expect(await documents.needsVerification()).toBe(false);
    expect(await documents.commitBatch('Nothing left to commit', versions, 0, signal())).toEqual({});
    expect(git(root, 'rev-parse', 'HEAD')).toBe(commit);
  });

  it('explicitly reports untracked files and refuses to take an unrelated staged path', async () => {
    const {documents, root} = await library();
    const before = git(root, 'rev-parse', 'HEAD');
    git(root, 'config', 'status.showUntrackedFiles', 'no');
    await documents.apply({operationId:'new', path:'new.md', beforeHash:null, content:'New evidence.'}, 0, signal(), {recordVersion:false});
    await writeFile(join(root, 'manual.txt'), 'Do not commit this file.');
    expect(git(root, 'status', '--porcelain')).toBe('');
    expect(await documents.gitChanges()).toEqual([
      {path:'manual.txt', status:'??', supported:false},
      {path:'new.md', status:'??', supported:true},
    ]);
    git(root, 'add', '--', 'manual.txt');
    await expect(documents.commitBatch('Memory only', await documents.versions(), 0, signal())).rejects.toThrow('cannot be safely committed');
    expect(git(root, 'diff', '--cached', '--name-only')).toBe('manual.txt');
    expect(git(root, 'rev-parse', 'HEAD')).toBe(before);
    expect(await readFile(join(root, 'manual.txt'), 'utf8')).toBe('Do not commit this file.');
  });

  it('clears a staged-only difference without an empty commit when the verified file matches HEAD', async () => {
    const {documents, root} = await library();
    const before = git(root, 'rev-parse', 'HEAD');
    const entry = join(root, 'MEMORY.md');
    const original = await readFile(entry, 'utf8');
    const versions = await documents.versions();
    await writeFile(entry, 'An earlier staged draft.');
    git(root, 'add', '--', 'MEMORY.md');
    await writeFile(entry, original);
    expect(await documents.needsVerification()).toBe(false);
    expect(await documents.gitChanges()).toEqual([{path:'MEMORY.md', status:'MM', supported:true}]);
    expect(await documents.commitBatch('No content difference', versions, 0, signal())).toEqual({});
    expect(await documents.gitChanges()).toEqual([]);
    expect(git(root, 'rev-parse', 'HEAD')).toBe(before);
  });

  it('commits the exact verified Markdown bytes when Git would normalize line endings', async () => {
    const {documents, root} = await library();
    const path = 'windows.md';
    const content = 'Line one.\r\nLine two.\r\n';
    git(root, 'config', 'core.autocrlf', 'true');
    await writeFile(join(root, path), content);
    const versions = {...await documents.versions(), [path]: createHash('sha256').update(content).digest('hex')};
    const {commit} = await documents.commitBatch('Keep verified Markdown', versions, 0, signal());
    expect(commit).toBe(git(root, 'rev-parse', 'HEAD'));
    expect(execFileSync('git', ['show', `HEAD:${path}`], {cwd:root,encoding:'utf8'})).toBe(content);
    expect(await documents.gitChanges()).toEqual([]);
  });

  it('repairs the ordinary index after an already committed new document', async () => {
    const {documents, root} = await library();
    const path = 'knowledge/new.md';
    await documents.apply({operationId:'recorded', path, beforeHash:null, content:'Already committed.'});
    const head = git(root, 'rev-parse', 'HEAD');
    // Equivalent to interruption after updating HEAD with the private index.
    git(root, 'rm', '--cached', '--', path);
    expect(git(root, 'status', '--porcelain', '--untracked-files=all').split('\n')).toEqual([`D  ${path}`, `?? ${path}`]);
    expect(await documents.commitBatch('Reconcile the memory index', await documents.versions(), 0, signal())).toEqual({});
    expect(await documents.gitChanges()).toEqual([]);
    expect(git(root, 'rev-parse', 'HEAD')).toBe(head);
    expect(await readFile(join(root, path), 'utf8')).toBe('Already committed.');
  });

  it('refuses to commit live changes based on source eligibility revoked after publication', async () => {
    const {documents, root} = await library();
    const before = git(root, 'rev-parse', 'HEAD');
    const allowed = await documents.syncSources({revision:'1', allowed:['chat-a'], excluded:[]});
    const receipt = await documents.apply({operationId:'published', path:'draft.md', beforeHash:null, content:'Scoped evidence.'}, allowed.generation, signal(), {recordVersion:false});
    const versions = await documents.versions();
    await documents.syncSources({revision:'2', allowed:[], excluded:['chat-a']});
    await expect(documents.commitBatch('Stale sources', versions, allowed.generation, signal())).rejects.toThrow(/generation/);
    await expect(documents.finalizeBatch(versions, allowed.generation, [receipt], signal())).rejects.toThrow(/generation/);
    expect(git(root, 'rev-parse', 'HEAD')).toBe(before);
    expect(await readFile(join(root, 'draft.md'), 'utf8')).toBe('Scoped evidence.');
    expect(await documents.gitChanges()).toEqual([{path:'draft.md', status:'??', supported:true}]);
  });
});
