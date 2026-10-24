import { createServer } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { Context } from '@deepseek-ai/cordis';
import type { AuthorizationRequest } from '@deepseek-ai/dsh-authorization';
import { NativeModelSetup } from '../src/model-setup.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('configures a real empty DSH through settings and credentials, probes native HTTP and restores routes after failure and cold restart', async () => {
  const calls: { url?: string; authorization?: string }[] = [];
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw);
    calls.push({ url: req.url, authorization: req.headers.authorization });
    if (body.model === 'failure') { res.writeHead(401, { 'content-type': 'application/json' }); res.end(JSON.stringify({ error: { message: 'sensitive-upstream-body', type: 'authentication_error' } })); return; }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    for (const delta of [{ content: 'READY' }, {}]) res.write(`data: ${JSON.stringify({ id: 'probe', object: 'chat.completion.chunk', created: 1, model: body.model, choices: [{ index: 0, delta, finish_reason: delta.content ? null : 'stop' }] })}\n\n`);
    res.end('data: [DONE]\n\n');
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const home = await mkdtemp(join(tmpdir(), 'nano-native-setup-'));
  let client: RuntimeClient | undefined;
  const baseURL = `http://127.0.0.1:${(server.address() as { port: number }).port}/v1`;
  const providers = { 'nano-fixture': { api: 'openai-completions', baseURL, models: [{ id: 'test' }], retryPolicy: { mode: 'normal', maxRetries: 0 } } };
  try {
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: {} } }]);
    const start = async (routes: unknown) => {
      client = new RuntimeClient({ home, cwd: home });
      await client.rpc.request('initialize', { protocol: 1, agents: [], bindings: [], providers: routes });
    };
    await start({});
    const catalog = await client!.rpc.request('model.setup.catalog', {}) as { provider: string; models: string[] }[];
    expect(catalog.find(item => item.provider === 'openai-codex')?.models.length).toBeGreaterThan(0);
    expect(await client!.rpc.request('model.setup.test', { id: 'setup', providers, provider: 'nano-fixture', model: 'test', api_key: 'local-fixture-secret' })).toEqual({});
    expect(await client!.rpc.request('update.prepare', { operationId: 'model-transaction' })).toEqual({ ready: false });
    await client!.rpc.request('model.setup.finish', { commit: true });
    expect(calls.at(-1)).toEqual({ url: '/v1/chat/completions', authorization: 'Bearer local-fixture-secret' });
    const saved = await client!.rpc.request('model.setup.credential', {provider: 'nano-fixture'});
    expect(saved).toEqual({record: {kind: 'api-key', key: 'local-fixture-secret'}});
    await client!.rpc.request('model.setup.stage', {id: 'edit', providers, provider: 'nano-fixture', api_key: 'rotated-fixture-secret'});
    expect(await client!.rpc.request('model.setup.credential', {provider: 'nano-fixture'})).toEqual({record: {kind: 'api-key', key: 'rotated-fixture-secret'}});
    await client!.rpc.request('model.setup.finish', {commit: false});
    expect(await client!.rpc.request('model.setup.credential', {provider: 'nano-fixture'})).toEqual(saved);

    const failed = { ...providers, 'nano-failure': { ...providers['nano-fixture'], models: [{ id: 'failure' }] } };
    await expect(client!.rpc.request('model.setup.test', { id: 'failure', providers: failed, provider: 'nano-failure', model: 'failure', api_key: 'bad-secret' })).rejects.toThrow('Model connection verification failed');
    // The failed route was removed, so another attempt at the same new route is admitted.
    await expect(client!.rpc.request('model.setup.test', { id: 'failure2', providers: failed, provider: 'nano-failure', model: 'failure', api_key: 'bad-secret' })).rejects.toThrow('Model connection verification failed');
    await client!.shutdown(); client = undefined;
    await start(providers);
    await client!.rpc.request('configuration.apply', { agentId: 'test-agent', revision: '1', provider: 'nano-fixture', model: 'test', workspace: home, features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false } });
    const binding = { sessionId: 'setup-persisted', agentId: 'test-agent', revision: '1', ownerId: 'owner', cwd: home };
    await client!.rpc.request('session.ensure', binding);
    await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: 'message', mode: 'followup', content: [{ type: 'text', text: 'Reply READY' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'message' } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: 'message' }) as { terminal?: unknown }).terminal).toBeTruthy();
    expect(calls.at(-1)?.authorization).toBe('Bearer local-fixture-secret');
    await client!.rpc.request('model.setup.stage', {id: 'edit-commit', providers, provider: 'nano-fixture', api_key: 'rotated-fixture-secret'});
    await client!.rpc.request('model.setup.finish', {commit: true});
    await client!.rpc.request('session.submit', {sessionId: binding.sessionId, inputId: 'after-edit', mode: 'followup', content: [{type: 'text', text: 'Reply READY again'}], source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: 'after-edit'}});
    await expect.poll(async () => (await client!.rpc.request('session.lookup', {sessionId: binding.sessionId, inputId: 'after-edit'}) as {terminal?: unknown}).terminal).toBeTruthy();
    expect(calls.at(-1)?.authorization).toBe('Bearer rotated-fixture-secret');
    await client!.rpc.request('model.setup.stage', {id: 'remove', providers: {}, provider: 'nano-fixture'});
    expect(await client!.rpc.request('model.setup.credential', {provider: 'nano-fixture'})).toEqual({record: null});
    await client!.rpc.request('model.setup.finish', {commit: false});
    expect(await client!.rpc.request('model.setup.credential', {provider: 'nano-fixture'})).toEqual({record: {kind: 'api-key', key: 'rotated-fixture-secret'}});

    await client!.shutdown(); client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);

it('chooses only device-code OAuth, exposes notices and cancels without installing a route', async () => {
  const handlers = new Map<string, (value: unknown) => unknown>();
  const notices: unknown[] = [];
  const maps: unknown[] = [];
  let selected: string | undefined;
  const ctx = {
    effect: () => {},
    settings: { mutate: async (_ns: string, ops: unknown) => { maps.push(ops); } },
    llm: { discoverModels: async () => [{ id: 'catalog-model' }] },
    authorization: { begin: async (request: AuthorizationRequest) => {
      expect(request.method).toBe('oauth');
      selected = await request.interaction.prompt({ kind: 'select', message: 'Method', options: [{ id: 'browser', label: 'Browser' }, { id: 'device_code', label: 'Device' }] });
      request.interaction.notify({ message: 'Authorize', code: 'TEST-CODE', url: 'https://issuer.test/device' });
      await new Promise<void>(resolve => request.signal!.addEventListener('abort', () => resolve(), { once: true }));
      return { status: 'cancelled' };
    } },
  } as unknown as Context;
  new NativeModelSetup(ctx, { handle: (method, handler) => { handlers.set(method, handler); return () => {}; }, notify: (_method, value) => { notices.push(value); } });
  const task = handlers.get('model.setup.test')!({ id: 'oauth', providers: { 'openai-codex': {} }, provider: 'openai-codex', model: 'catalog-model', login: true });
  await expect.poll(() => selected).toBe('device_code');
  expect(notices).toContainEqual({ id: 'oauth', state: 'waiting', message: 'Authorize', code: 'TEST-CODE', url: 'https://issuer.test/device' });
  handlers.get('model.setup.cancel')!({});
  expect(await task).toEqual({ cancelled: true });
  expect(maps).toEqual([[{ op: 'set', path: ['providers'], value: {} }]]);
});
