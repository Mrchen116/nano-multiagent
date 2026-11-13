import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
import { execFileSync } from 'node:child_process';
import { rename, symlink, mkdtemp, mkdir, readFile, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
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
    await mkdir(dirname(statePath), {recursive:true});
    const state = {generation:0, receipts:{}, basis:{generation:0, versions:{}},
      exclusions:[{requestRef:'old-request',paths:['MEMORY.md'],sources:['old-chat']}]};
    await writeFile(statePath, JSON.stringify(state));
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs);
    cleanups.push(() => reopened.close());
    expect((await reopened.context()).entry).toBe(entry);
    expect(await reopened.context()).not.toHaveProperty('exclusions');
    expect(await reopened.status()).not.toHaveProperty('exclusions');
    await reopened.syncSources({revision:'current',allowed:['old-chat'],excluded:[]});
    expect(JSON.parse(await readFile(statePath,'utf8'))).not.toHaveProperty('exclusions');
    expect(JSON.parse(await readFile(statePath,'utf8'))).not.toHaveProperty('basis');
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
    expect((await documents.context()).entry).toContain('Personal');
    await writeFile(join(root, 'knowledge/preferences.md'), 'Ask before any update.');
    await documents.invalidate('knowledge/preferences.md');
    expect((await documents.context()).entry).toContain('Personal');
    await documents.close();
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs);
    cleanups.push(() => reopened.close());
    expect((await reopened.context()).entry).toContain('Personal');
    expect(await readFile(join(root, 'knowledge/preferences.md'), 'utf8')).toBe('Ask before any update.');
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

  it('keeps foreground memory readable and persists source revocation', async () => {
    const { documents, workspace } = await library();
    await documents.syncSources({ revision: '1', allowed: ['conversation-a'], excluded: [] });
    const allowed = await documents.status();
    await documents.syncSources({ revision: '1', allowed: [], excluded: ['conversation-a'] });
    const revoked = await documents.status();
    expect(revoked.generation).toBeGreaterThan(allowed.generation);
    expect((await documents.context()).entry).toContain('Personal');
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

describe('native Git batch observation', () => {
  const git = (cwd: string, ...args: string[]) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
  const commit = (root: string) => {
    git(root, 'add', '-A');
    git(root, '-c', 'user.name=Memory test', '-c', 'user.email=memory@test.local', 'commit', '-qm', 'Organize memory');
    return git(root, 'rev-parse', 'HEAD');
  };

  it('observes native additions, edits, moves and deletions with separate file and Git receipts', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, 'old.md'), 'Move this knowledge.');
    await writeFile(join(root, 'remove.md'), 'Obsolete knowledge.');
    commit(root);
    const before = await documents.observeBatch(await documents.versions(), 'setup');
    await rename(join(root, 'old.md'), join(root, 'moved.md'));
    await rm(join(root, 'remove.md'));
    await writeFile(join(root, 'new page.md'), 'New knowledge.');
    await writeFile(join(root, 'MEMORY.md'), '# Updated memory\n');
    const pending = await documents.observeBatch(before.versions, 'native');
    expect(pending.receipts).toHaveLength(5);
    expect(pending.receipts.every(receipt => receipt.saved && !receipt.versionRecorded)).toBe(true);
    expect(pending.receipts.filter(receipt => receipt.afterHash === null).map(receipt => receipt.path)).toEqual(['old.md', 'remove.md']);
    expect((await documents.gitChanges()).every(change => change.supported)).toBe(true);
    expect(await documents.repositoryIssues()).toHaveLength(5);
    const head = commit(root);
    const observed = await documents.observeBatch(before.versions, 'native');
    expect(observed.receipts.every(receipt => receipt.saved && receipt.versionRecorded && receipt.commit === head)).toBe(true);
    expect(await documents.repositoryIssues()).toEqual([]);
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
    const {documents,root}=await library();
    await rm(join(root,'MEMORY.md'));await writeFile(join(root,'scratch.txt'),'Temporary scratch.');
    expect(await documents.repositoryIssues()).toEqual(expect.arrayContaining([
      expect.objectContaining({path:'MEMORY.md',reason:'Uncommitted change'}),
      {path:'scratch.txt',reason:'Expected a regular Markdown file'},
    ]));
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
    await documents.close();
    const reopened = await MemoryDocuments.open(workspace, 'personal', fs); cleanups.push(() => reopened.close());
    expect((await reopened.status()).receipts).toEqual(expect.arrayContaining(observed.receipts));
    expect(await readFile(join(root, 'pending.md'), 'utf8')).toBe('Uncommitted evidence.');
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

  it('reports committed or ignored files and symlinks by path', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, '.gitignore'), 'scratch.txt');
    await symlink('MEMORY.md', join(root, 'alias.md'));
    commit(root);
    await writeFile(join(root, 'scratch.txt'), 'Ignored, but still in the memory repository.');
    expect(await documents.gitChanges()).toEqual([]);
    expect(await documents.repositoryIssues()).toEqual(expect.arrayContaining(
      ['.gitignore', 'alias.md', 'scratch.txt'].map(path => ({path,reason:'Expected a regular Markdown file'})),
    ));
  });

  it.each(['directory', 'symlink'])('reports a root entry replaced by a %s', async kind => {
    const {documents, root} = await library();
    const entry = join(root, 'MEMORY.md');
    await rm(entry);
    if (kind === 'directory') await mkdir(entry);
    else await symlink('other.md', entry);
    expect(await documents.repositoryIssues()).toContainEqual({path:'MEMORY.md',reason:'MEMORY.md must be a regular file'});
    expect(await documents.versions()).not.toHaveProperty('MEMORY.md');
  });

  it('rejects ignored memory pages and committed hidden documents even when Git is clean', async () => {
    const {documents, root} = await library();
    await writeFile(join(root, '.git/info/exclude'), 'ignored.md\n');
    await writeFile(join(root, 'ignored.md'), 'Not recorded in Git.');
    await mkdir(join(root, '.hidden'));
    await writeFile(join(root, '.hidden/page.md'), 'Outside the supported memory layout.');
    commit(root);
    expect(await documents.gitChanges()).toEqual([]);
    expect(await documents.repositoryIssues()).toEqual(expect.arrayContaining([
      {path:'ignored.md',reason:'Ignored Markdown file is not recorded in Git'},
      {path:'.hidden',reason:'Expected a regular Markdown file'},
    ]));
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
    expect(await documents.repositoryIssues()).toEqual([]);
  });

});
