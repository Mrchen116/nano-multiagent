import { createServer } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';
import { workDescendants } from './helpers/work-history.js';

it('keeps live parent and nested turns on the same step while their model connection is down', async () => {
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
  const observeRoot = async () => await client!.rpc.request('session.observe', { sessionId: 'root' }) as {
    status: string;
    events: { type: string; data: any }[];
  };
  const observeAll = async () => {
    const root = await observeRoot();
    const descendants = await workDescendants(client!.rpc, { sessionId: 'root' });
    return new Map([['root', root.events], ...descendants.map(({ id, events }) => [id, events] as const)]);
  };
  const submit = async (inputId: string) => client!.rpc.request('session.submit', {
    sessionId: 'root', inputId, mode: 'followup',
    content: [{ type: 'text', text: inputId }],
    source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId },
  });
  try {
    await listen(0);
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: {
      api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY',
      models: [{ id: 'fixture', contextWindow: 100000 }],
      retryPolicy: { mode: 'normal', maxRetries: 1, backoff: { initialDelayMs: 5, maxDelayMs: 5, jitterRatio: 0 } },
    } } } }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    const config = { agentId: 'a', revision: '1', mode: 'global', workspace: home, provider: 'fixture', model: 'fixture',
      toolAllowlist: ['subagent'], features: { dreaming: false }, approval: { dangerouslySkipPermissions: true } };
    const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const pid = client.process.pid;
    await submit('Start nested work');
    await expect.poll(() => parked.size, { timeout: 7000 }).toBe(3);
    const sessions = [...parked];
    await close();

    const retryEvents = (events: Awaited<ReturnType<typeof observeRoot>>['events']) => events.filter(event => event.type === 'llm/retry');
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => retryEvents(all.get(id) ?? []).map(event => event.data.mode));
    }, { timeout: 3000 }).toEqual(sessions.map(() => ['normal', 'always']));
    expect((await observeRoot()).status).toBe('running');
    for (const events of (await observeAll()).values()) {
      expect(events.filter(event => event.type === 'turn/end')).toHaveLength(0);
    }

    // Air's local LLM proxy can answer while its upstream connection is still down.
    phase = 'proxy-offline';
    await listen(port);
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => retryEvents(all.get(id) ?? []).map(event => event.data.mode));
    }, { timeout: 8000 }).toEqual(sessions.map(() => ['normal', 'always', 'always']));
    for (const events of (await observeAll()).values()) {
      const [normal, connection, proxy] = retryEvents(events);
      expect(connection?.data).toMatchObject({ turn: normal?.data.turn, step: normal?.data.step, retry: 1, delayMs: 5000 });
      expect(proxy?.data).toMatchObject({ turn: normal?.data.turn, step: normal?.data.step, retry: 2, delayMs: 10000 });
    }

    phase = 'recovered';
    await expect.poll(async () => {
      const all = await observeAll();
      return sessions.map(id => all.get(id)?.find(event => event.type === 'turn/end' && event.data.turn === 1)?.data.reason.kind);
    }, { timeout: 13000 }).toEqual(sessions.map(() => 'completed'));
    expect(client.process.pid).toBe(pid);
    for (const id of ['root', child!]) {
      const result = recovered.get(id)?.flatMap(message => message.content)
        .filter(block => block.type === 'tool_result' && block.tool_use_id === `delegate-${id}`);
      expect(result).toHaveLength(1);
    }

    await expect.poll(async () => (await observeRoot()).status).toBe('idle');
    await close();
    const previousRetries = retryEvents((await observeRoot()).events).length;
    await submit('Cancel during connection wait');
    await expect.poll(async () => retryEvents((await observeRoot()).events).slice(previousRetries)
      .map(event => event.data.mode)).toEqual(['always']);
    await client.rpc.request('session.cancel', { sessionId: 'root' });
    const cancelled = (await observeRoot()).events.filter(event => event.type === 'turn/end').at(-1);
    expect(cancelled?.data.reason.kind).toBe('aborted');

    await listen(port);
    for (const failure of ['incomplete', 'server-error'] as const) {
      phase = failure;
      const previousRetries = retryEvents((await observeRoot()).events).length;
      await submit(failure);
      await expect.poll(async () => (await client!.rpc.request('session.lookup', {
        sessionId: 'root', inputId: failure,
      }) as any).terminal?.kind).toBe('error');
      expect(retryEvents((await observeRoot()).events).slice(previousRetries).map(event => event.data.mode))
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
}, 35000);
