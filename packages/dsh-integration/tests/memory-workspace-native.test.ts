import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('initializes default document memory in the configured owner workspace outside the runtime cwd', async () => {
  // OS temporary roots are writable even outside the runtime workspace; use the checkout to exercise the boundary.
  const root = await mkdtemp(join(process.cwd(), '.test-memory-workspace-'));
  const home = join(root, 'runtime'); const workspace = join(root, 'owner');
  let client: RuntimeClient | undefined;
  try {
    await mkdir(workspace);
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test' }] } } } }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'a', workspace, revision: '1', provider: 'fixture', model: 'test', features: { dreaming: false, memory_curation: false, skill_creation: false } }], bindings: [] });
    await expect(client.rpc.request('knowledge.sources.pending', { agentId: 'a' })).resolves.toEqual({ pending: true });
    expect(await readFile(join(workspace, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('# Expert memory');
    await expect(readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
    await client.shutdown(); client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await rm(root, { recursive: true, force: true });
  }
}, 15000);
