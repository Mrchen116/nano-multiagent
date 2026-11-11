import { mkdtemp, mkdir, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { initializeRoleDocument, roleDocument } from '../src/knowledge/role-document.js';

const fs = new LocalFileSystem(new Context(), { cwd: process.cwd(), diffBasisMaxBytes: 10485760 });

it('shares one role file and guards stale settings drafts against ordinary file changes', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-role-'));
  try {
    const workspace = await realpath(dir);
    const path = join(workspace, '.nanoassistant/ROLE.md');
    expect(await roleDocument(fs, workspace)).toEqual({ content: '', version: null });
    await expect(readFile(path)).rejects.toMatchObject({ code: 'ENOENT' });
    const initialized = await roleDocument(fs, workspace, undefined, true);
    expect(initialized).toMatchObject({ content: '', version: expect.any(String) });
    expect(await readFile(path, 'utf8')).toContain('ask the user');
    if ('error' in initialized) throw new Error(initialized.error);
    const saved = await roleDocument(fs, workspace, { content: 'Coordinate long-term project delivery.', version: initialized.version });
    expect(saved).toMatchObject({ content: 'Coordinate long-term project delivery.', version: expect.any(String) });
    if ('error' in saved) throw new Error(saved.error);
    await writeFile(path, 'Owner confirmed this change in chat.');
    expect(await roleDocument(fs, workspace, { content: 'Stale draft', version: saved.version })).toEqual({ error: 'role_conflict' });
    const current = await roleDocument(fs, workspace);
    if ('error' in current) throw new Error(current.error);
    expect(current.content).toBe('Owner confirmed this change in chat.');
    expect(await roleDocument(fs, workspace, { content: '💡'.repeat(1001), version: current.version })).toEqual({ error: 'role_too_long' });
    expect(await roleDocument(fs, workspace, { content: '', version: current.version })).toMatchObject({ content: '' });
    expect(await readFile(path, 'utf8')).toContain('ask the user');
    const oversizedBlank = ' '.repeat(2001);
    await writeFile(path, oversizedBlank);
    expect(await roleDocument(fs, workspace)).toMatchObject({ content: oversizedBlank, version: expect.any(String) });
  } finally { await rm(dir, { recursive: true, force: true }); }
});

it('does not follow a role file or private-directory symlink', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-role-alias-'));
  try {
    const workspace = await realpath(dir);
    const privateRoot = join(workspace, '.nanoassistant');
    const target = join(workspace, 'target.md');
    await writeFile(target, 'Original unrelated file');
    await mkdir(privateRoot);
    await symlink(target, join(privateRoot, 'ROLE.md'));
    expect(await roleDocument(fs, workspace)).toEqual({ error: 'role_unavailable' });
    await rm(privateRoot, { recursive: true });
    await symlink(workspace, privateRoot);
    expect(await roleDocument(fs, workspace, { content: 'Do not follow', version: null })).toEqual({ error: 'role_unavailable' });
    expect(await readFile(target, 'utf8')).toBe('Original unrelated file');
  } finally { await rm(dir, { recursive: true, force: true }); }
});

it('saves the creation role, resumes an identical draft and preserves later edits', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-initial-role-'));
  try {
    const workspace = await realpath(dir);
    expect(await initializeRoleDocument(fs, workspace, 'Initial agreement')).toMatchObject({content: 'Initial agreement'});
    expect(await initializeRoleDocument(fs, workspace, 'Initial agreement')).toMatchObject({content: 'Initial agreement'});
    await writeFile(join(workspace, '.nanoassistant/ROLE.md'), 'Later confirmed agreement');
    expect(await initializeRoleDocument(fs, workspace, 'Initial agreement')).toEqual({error: 'role_conflict'});
    expect(await roleDocument(fs, workspace)).toMatchObject({content: 'Later confirmed agreement'});
    expect(await initializeRoleDocument(fs, workspace, '💡'.repeat(1001))).toEqual({error: 'role_too_long'});
  } finally { await rm(dir, {recursive: true, force: true}); }
});

it('persists initial ROLE through native configuration preparation and preserves later edits on apply', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-role-prepare-'));
  let client: RuntimeClient | undefined;
  try {
    const workspace = await realpath(home);
    await prepareProfile(home);
    client = new RuntimeClient({home, cwd: home});
    await client.rpc.request('initialize', {protocol: 1, agents: [], bindings: []});
    const config = {agentId: 'created', workspace, revision: '1', mode: 'global', provider: 'deepseek-official', model: 'deepseek-flash', features: {dreaming: false, task_graph: false, intelligent_ui: false, memory_curation: false, skill_creation: false, heartbeat: false, cron_scheduling: false}};
    const intent = {operationId: 'create-role', fingerprint: 'creation', config, initialRole: 'Coordinate deliveries.\nWorkers implement.'};
    { const result = await client.rpc.request('configuration.prepare', intent); expect(result, JSON.stringify(result)).toMatchObject({ready: true}); }
    const path = join(workspace, '.nanoassistant/ROLE.md');
    expect(await readFile(path, 'utf8')).toBe(intent.initialRole);
    { const result = await client.rpc.request('configuration.prepare', intent); expect(result, JSON.stringify(result)).toMatchObject({ready: true}); }
    await writeFile(path, 'Later role from the user');
    expect(await client.rpc.request('configuration.prepare', intent)).toMatchObject({ready: false, error_code: 'role_conflict'});
    expect(await client.rpc.request('configuration.apply', {...config, operationId: intent.operationId, fingerprint: intent.fingerprint})).toMatchObject({effective: true});
    expect(await readFile(path, 'utf8')).toBe('Later role from the user');
  } finally { await client?.shutdown(); await rm(home, {recursive: true, force: true}); }
}, 30000);
