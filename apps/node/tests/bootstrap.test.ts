import { mkdtemp, readFile, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { bootstrapNode } from '../src/bootstrap.js';

it('keeps a fresh installation dormant and preserves its identity and files on rerun', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-bootstrap-'));
  vi.stubEnv('NANO_INSTALL_ROOT', root);
  vi.stubEnv('NANO_INSTALL_AUTOSTART', '0');
  try {
    const first = await bootstrapNode('https://nano.example/setup');
    expect(first.value).toMatchObject({ agents: [], node: { user_id: '' }, im_service: { url: 'https://nano.example', token: '' }, llm: { default_model: '', providers: [] } });
    expect(first.path.startsWith(root)).toBe(true);
    expect((await stat(first.path)).mode & 0o777).toBe(0o600);
    const before = await readFile(first.path, 'utf8');
    const again = await bootstrapNode('https://nano.example');
    expect(again.value.node.node_id).toBe(first.value.node.node_id);
    expect(await readFile(first.path, 'utf8')).toBe(before);
    const other = await bootstrapNode('https://other.example');
    expect(other.path).not.toBe(first.path);
    expect(other.value.node.node_id).not.toBe(first.value.node.node_id);
    await expect(bootstrapNode('https://other.example', first.path)).rejects.toThrow('another IM service');
    expect(await readFile(first.path, 'utf8')).toBe(before);
  } finally { vi.unstubAllEnvs(); await rm(root, { recursive: true, force: true }); }
});
