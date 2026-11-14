import { createServer } from 'node:http';
import { createServer as createTcpServer } from 'node:net';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';
import { workDescendants } from './helpers/work-history.js';

type ModelApi = 'anthropic-messages' | 'openai-completions' | 'openai-responses';

function configureProvider(home: string, baseURL: string, api: ModelApi, observer?: string, streamIdleTimeoutMs?: number) {
  return prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: {
    api, baseURL, apiKeyEnv: 'NANO_TEST_KEY', streamIdleTimeoutMs,
    models: [{ id: 'fixture', contextWindow: 100000 }],
    retryPolicy: { mode: 'normal', maxRetries: 1, backoff: { initialDelayMs: 5, maxDelayMs: 5, jitterRatio: 0 } },
  } } } }, ...(observer ? [{ insert: [{ id: 'connection-observer', name: observer }] }] : [])]);
}

async function ensureRoot(client: RuntimeClient, home: string, toolAllowlist: string[] = []) {
  registerNoopTaskHosts(client);
  const config = { agentId: 'a', revision: '1', mode: 'global', workspace: home, provider: 'fixture', model: 'fixture',
    toolAllowlist, features: { dreaming: false }, approval: { dangerouslySkipPermissions: true } };
  const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
  await client.rpc.request('session.ensure', binding);
}

async function observeRoot(client: RuntimeClient) {
  return await client.rpc.request('session.observe', { sessionId: 'root' }) as {
    status: string;
    events: { type: string; data: any }[];
  };
}

function submit(client: RuntimeClient, inputId: string) {
  return client.rpc.request('session.submit', {
    sessionId: 'root', inputId, mode: 'followup',
    content: [{ type: 'text', text: inputId }],
    source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId },
  });
}

it.each(['closed', 'stalled'] as const)('keeps parent and nested turns through %s connections and resumes original work', async fault => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-connection-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  let phase: 'delegate' | 'proxy-offline' | 'recovered' | 'incomplete' | 'server-error' = 'delegate';
  let child: string | undefined;
  let rootDelegated = false;
  const parked = new Set<string>();
  const recovered = new Map<string, any[]>();
  const server = createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const { messages } = JSON.parse(raw);
    const session = String(req.headers['x-agent-session-id']);
    const firstChild = session !== 'root' && child === undefined;
    if (firstChild) child = session;
    const delegate = phase === 'delegate' && (firstChild || (session === 'root' && !rootDelegated));
    if (delegate && session === 'root') rootDelegated = true;
    if (phase === 'delegate' && !delegate) {
      parked.add(session);
      if (session !== 'root') {
        res.writeHead(200, { 'content-type': 'text/event-stream' });
        res.write(`event: message_start\ndata: ${JSON.stringify({ type: 'message_start', message: {
          id: 'unfinished', type: 'message', role: 'assistant', model: 'fixture', content: [],
          stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 },
        } })}\n\n`);
        res.write(`event: content_block_start\ndata: ${JSON.stringify({ type: 'content_block_start', index: 0,
          content_block: { type: 'tool_use', id: 'unfinished', name: 'subagent', input: {} },
        })}\n\n`);
      }
      return;
    }
    if (phase === 'proxy-offline' || phase === 'server-error') {
      const error = phase === 'proxy-offline'
        ? { type: 'upstream_connection_error', message: 'ConnectError: controlled offline route' }
        : { type: 'upstream_http_error', message: 'Upstream service error' };
      res.writeHead(502, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error }));
      return;
    }
    if (phase === 'recovered' && !recovered.has(session)) recovered.set(session, messages);
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({type, ...data})}\n\n`);
    emit('message_start', { message: { id: 'fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
    if (phase === 'incomplete') { res.end(); return; }
    const block = delegate
      ? { type: 'tool_use', id: `delegate-${session}`, name: 'subagent', input: {} }
      : { type: 'text', text: 'Completed original work.' };
    emit('content_block_start', { index: 0, content_block: block });
    if (delegate) emit('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify({
      prompt: `Complete delegated work from ${session}`, description: 'fixture delegation', run_in_background: true,
    }) } });
    emit('content_block_stop', { index: 0 });
    emit('message_delta', { delta: { stop_reason: delegate ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
    emit('message_stop', {});
    res.end();
  });
  const listen = (port: number) => new Promise<void>(resolve => server.listen(port, '127.0.0.1', resolve));
  const close = () => new Promise<void>(resolve => {
    server.close(() => resolve());
    server.closeAllConnections();
  });
  const observeAll = async () => {
    const root = await observeRoot(client!);
    const descendants = await workDescendants(client!.rpc, { sessionId: 'root' });
    return new Map([['root', root.events], ...descendants.map(({ id, events }) => [id, events] as const)]);
  };
  try {
    await listen(0);
    const port = (server.address() as { port: number }).port;
    await configureProvider(home, `http://127.0.0.1:${port}/v1`, 'anthropic-messages', undefined, 1500);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await ensureRoot(client, home, ['subagent']);
    const pid = client.process.pid;
    await submit(client, 'Start nested work');
    await expect.poll(() => parked.size, { timeout: 7000 }).toBe(3);
    const sessions = [...parked];
    if (fault === 'closed') await close();
    else {
      // Suspend only this isolated DSH process while all three model streams are pending.
      client.process.kill('SIGSTOP');
      await new Promise(resolve => setTimeout(resolve, 1800));
      client.process.kill('SIGCONT');
    }

    const retryEvents = (events: Awaited<ReturnType<typeof observeRoot>>['events']) => events.filter(event => event.type === 'llm/retry');
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => retryEvents(all.get(id) ?? []).map(event => event.data.mode));
    }, { timeout: 5000 }).toEqual(sessions.map(() => ['always']));
    if (fault === 'stalled') {
      await expect.poll(async () => {
        const all = await observeAll();
        return sessions.map(id => retryEvents(all.get(id) ?? []).map(event => event.data.failure.code));
      }, { timeout: 9000 }).toEqual(sessions.map(() => ['TIMEOUT', 'TIMEOUT']));
    }
    expect((await observeRoot(client!)).status).toBe('running');
    for (const events of (await observeAll()).values()) {
      expect(events.filter(event => event.type === 'turn/end')).toHaveLength(0);
    }

    // Air's local LLM proxy can answer while its upstream connection is still down.
    phase = 'proxy-offline';
    if (fault === 'closed') await listen(port);
    const expectedRetries = fault === 'stalled' ? 3 : 2;
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => retryEvents(all.get(id) ?? []).map(event => event.data.mode));
    }, { timeout: 14000 }).toEqual(sessions.map(() => Array(expectedRetries).fill('always')));
    for (const events of (await observeAll()).values()) {
      const retries = retryEvents(events);
      const first = retries[0]!.data;
      for (const [index, retry] of retries.entries()) {
        expect(retry.data).toMatchObject({ turn: first.turn, step: first.step, retry: index + 1, delayMs: 5000 * 2 ** index });
      }
    }

    phase = 'recovered';
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => all.get(id)?.find(event => event.type === 'turn/end' && event.data.turn === 1)?.data.reason.kind);
    }, { timeout: 24000 }).toEqual(sessions.map(() => 'completed'));
    expect(client.process.pid).toBe(pid);
    for (const events of (await observeAll()).values()) {
      expect(events.filter(event => event.type === 'tool/call' && event.data.callId === 'unfinished')).toHaveLength(0);
    }
    for (const id of ['root', child!]) {
      const result = recovered.get(id)?.flatMap(message => message.content)
        .filter(block => block.type === 'tool_result' && block.tool_use_id === `delegate-${id}`);
      expect(result).toHaveLength(1);
    }

    await expect.poll(async () => (await observeRoot(client!)).status).toBe('idle');
    await close();
    const previousRetries = retryEvents((await observeRoot(client!)).events).length;
    await submit(client, 'Cancel during connection wait');
    await expect.poll(async () => retryEvents((await observeRoot(client!)).events).slice(previousRetries)
      .map(event => event.data.mode)).toEqual(['always']);
    await client.rpc.request('session.cancel', { sessionId: 'root' });
    const cancelled = (await observeRoot(client!)).events.filter(event => event.type === 'turn/end').at(-1);
    expect(cancelled?.data.reason.kind).toBe('aborted');

    await listen(port);
    for (const failure of ['incomplete', 'server-error'] as const) {
      phase = failure;
      const previousRetries = retryEvents((await observeRoot(client!)).events).length;
      await submit(client, failure);
      await expect.poll(async () => (await client!.rpc.request('session.lookup', {
        sessionId: 'root', inputId: failure,
      }) as any).terminal?.kind).toBe('error');
      expect(retryEvents((await observeRoot(client!)).events).slice(previousRetries).map(event => event.data.mode))
        .toEqual(['normal']);
    }
    await client.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${error}\n${logs}`, { cause: error });
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await close();
    await rm(home, { recursive: true, force: true });
  }
}, 65000);

it.each(['openai-completions', 'openai-responses'] as const)('waits for a typed upstream 502 on %s', async api => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-proxy-'));
  let client: RuntimeClient | undefined;
  const server = createServer(async (req, res) => {
    for await (const _ of req) {}
    res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: { type: 'upstream_connection_error', message: 'ConnectTimeout: upstream is unreachable' } }));
  });
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    await configureProvider(home, `http://127.0.0.1:${port}/v1`, api);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    await ensureRoot(client, home);
    await submit(client, 'Wait for the proxy upstream');
    await expect.poll(async () => {
      const { events } = await observeRoot(client!);
      return events.find(event => event.type === 'llm/retry')?.data;
    }).toMatchObject({ mode: 'always', retry: 1 });
    await client.rpc.request('session.cancel', { sessionId: 'root' });
    await client.shutdown();
    client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 15000);

it('waits when the TLS peer closes before the connection is established', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-tls-'));
  let client: RuntimeClient | undefined;
  const server = createTcpServer(socket => socket.once('data', () => socket.end()));
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    await configureProvider(home, `https://127.0.0.1:${port}/v1`, 'anthropic-messages');
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    await ensureRoot(client, home);
    await submit(client, 'Wait for TLS');
    await expect.poll(async () => {
      const { events } = await observeRoot(client!);
      return events.find(event => event.type === 'llm/retry')?.data;
    }).toMatchObject({ mode: 'always', retry: 1 });
    await client.rpc.request('session.cancel', { sessionId: 'root' });
    await client.shutdown();
    client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 15000);

it('keeps Dreaming on its original step through connection loss and permits cancellation', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-connection-'));
  let client: RuntimeClient | undefined;
  let inputId = 'experience';
  let phase: 'offline' | 'recovered' | 'server-error' = 'offline';
  const children = new Map<string, string>();
  const server = createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const { messages } = JSON.parse(raw);
    const session = String(req.headers['x-agent-session-id']);
    const blocks = messages.flatMap((message: any) => Array.isArray(message.content) ? message.content : []);
    const hasResult = (id: string) => blocks.some((block: any) => block.type === 'tool_result' && block.tool_use_id === id);
    let call: { name: string; input: object; id: string } | undefined;
    if (session === 'root') {
      if (inputId !== 'experience' && !hasResult(inputId)) {
        call = { name: 'memory_maintenance', input: { action: 'run', request_ref: inputId }, id: inputId };
      }
    } else {
      children.set(inputId, session);
      if (inputId === 'maintain' && !hasResult('save-once')) {
        call = { name: 'bash', id: 'save-once', input: {
          description: 'Save and commit a lesson before the connection fails',
          command: "printf 'Remember once\\n' >> recovery.md && git add -- recovery.md && git -c user.name=Nano -c user.email=memory@localhost commit -m recovery",
        } };
      } else if (phase !== 'recovered') {
        res.writeHead(502, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ error: phase === 'offline'
          ? { type: 'upstream_connection_error', message: inputId === 'cancel-maintain' ? 'ConnectError: controlled cancel route' : 'ConnectError: controlled offline route' }
          : { type: 'upstream_http_error', message: 'Upstream service error' } }));
        return;
      }
    }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    emit('message_start', { message: { id: 'fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
    emit('content_block_start', { index: 0, content_block: call
      ? { type: 'tool_use', id: call.id, name: call.name, input: {} }
      : { type: 'text', text: 'Completed original work.' } });
    if (call) emit('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(call.input) } });
    emit('content_block_stop', { index: 0 });
    emit('message_delta', { delta: { stop_reason: call ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 5 } });
    emit('message_stop', {});
    res.end();
  });
  const observeChild = async () => ({ events: (await readFile(join(home, 'events.jsonl'), 'utf8'))
    .trim().split('\n').map(line => JSON.parse(line)).filter(row => row.sessionId === children.get(inputId)).map(row => row.event) as Awaited<ReturnType<typeof observeRoot>>['events'] });
  const reviews = async () => (await client!.rpc.request('knowledge.facts', {}) as any).reviews;
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const observer = join(home, 'observer.mjs');
    await writeFile(observer, `import {appendFileSync} from 'node:fs';
export const inject = ['agents'];
export function apply(ctx) { ctx.on('session/event', (session, event) => {
  appendFileSync(process.env.DSH_HOME+'/events.jsonl', JSON.stringify({sessionId:session.id,event})+'\\n');
  if (event.type === 'llm/retry' && event.data.failure.message.includes('controlled cancel route')) {
    setTimeout(() => ctx.agents.get(session.id)?.cancel({kind:'hook',reason:'test cancellation'}), 100);
  }
}); }`);
    await configureProvider(home, `http://127.0.0.1:${(server.address() as { port: number }).port}/v1`, 'anthropic-messages', observer);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
    await ensureRoot(client, home, ['memory_maintenance']);
    await submit(client, inputId);
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId }) as any).terminal?.kind).toBe('completed');
    inputId = 'maintain';
    await submit(client, inputId);
    await expect.poll(() => children.has(inputId)).toBe(true);
    await expect.poll(async () => (await observeChild()).events.filter(e => e.type === 'llm/retry').map(e => e.data.mode), { timeout: 8000 }).toEqual(['always', 'always']);
    const waiting = await observeChild();
    const retries = waiting.events.filter(e => e.type === 'llm/retry');
    expect(retries.map(e => e.data)).toEqual([
      expect.objectContaining({ turn: 1, step: 2, retry: 1, delayMs: 5000 }),
      expect.objectContaining({ turn: 1, step: 2, retry: 2, delayMs: 10000 }),
    ]);
    expect(waiting.events.filter(e => e.type === 'turn/end')).toHaveLength(0);
    phase = 'recovered';
    await expect.poll(async () => (await reviews()).map((r: any) => r.status), { timeout: 13000 }).toEqual(['completed']);
    expect(await readFile(join(home, '.nanoassistant/memory/recovery.md'), 'utf8')).toBe('Remember once\n');
    await expect.poll(async () => (await observeRoot(client!)).status).toBe('idle');

    inputId = 'cancel-maintain'; phase = 'offline';
    await submit(client, inputId);
    await expect.poll(() => children.has(inputId)).toBe(true);
    await expect.poll(async () => (await observeChild()).events.find(e => e.type === 'llm/retry')?.data.mode).toBe('always');
    await expect.poll(async () => (await observeChild()).events.find(e => e.type === 'turn/end')?.data.reason.kind).toBe('aborted');
    await expect.poll(async () => (await observeRoot(client!)).status).toBe('idle');

    inputId = 'server-error'; phase = 'server-error';
    await submit(client, inputId);
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId }) as any).terminal).toBeTruthy();
    expect((await reviews()).find((r: any) => r.childSessionId === children.get(inputId))?.status).toBe('failed');
    await client.shutdown(); client = undefined;
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 35000);
