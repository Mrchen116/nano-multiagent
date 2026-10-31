import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
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
