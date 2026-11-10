import { mkdtemp, mkdir, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import { expect, it } from 'vitest';
import { roleDocument } from '../src/knowledge/role-document.js';

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
