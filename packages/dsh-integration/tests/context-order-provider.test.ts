import { createServer } from 'node:http';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

type Message = { id: string; source: { kind: string; [key: string]: unknown }; content: { type: string; text?: string }[] };
type Event = { type: string; data: any };
type Request = { raw: string; method?: string; path?: string; root: string; session: string };

const text = (message: Message) => message.content.filter(part => part.type === 'text').map(part => part.text).join('');
const body = (request: Request) => JSON.parse(request.raw);
// The provider moves its ephemeral cache hint to the newest message and may
// encode a sole text block as a string. Compare every retained payload/role
// while ignoring only that transport hint and equivalent string shorthand.
const wireMessages = (request: Request) => body(request).messages.map((message: any) => ({
  ...message, content: typeof message.content === 'string' ? [{ type: 'text', text: message.content }]
    : message.content.map(({ cache_control: _cache, ...block }: any) => block),
}));
// Anthropic does not serialize DSH message IDs/sources. Wire assertions use only
// the bytes actually received by HTTP; native events separately prove identity.
const position = (request: Request, value: string) => {
  const escaped = JSON.stringify(value).slice(1, -1);
  expect(request.raw.split(escaped), value).toHaveLength(2);
  return request.raw.indexOf(escaped);
};
const users = (events: Event[]) => events.filter(event => event.type === 'user/message').map(event => event.data as Message);
const bySource = (messages: Message[], kind: string) => messages.filter(message => message.source.kind === kind);

it('orders native environment updates on Anthropic HTTP wire without rewriting retained history after restart/configuration change', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-context-order-wire-'));
  const requests: Request[] = [];
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(Buffer.from(chunk));
    requests.push({ raw: Buffer.concat(chunks).toString('utf8'), method: req.method, path: req.url,
      root: String(req.headers['x-session-id']), session: String(req.headers['x-agent-session-id']) });
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(
      `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    emit('message_start', { message: { id: 'wire-fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 20, output_tokens: 0 } } });
    emit('content_block_start', { index: 0, content_block: { type: 'text', text: `WIRE_ANSWER_${requests.length}` } });
    emit('content_block_stop', { index: 0 });
    emit('message_delta', { delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 4 } });
    emit('message_stop', {});
    res.end();
  });
  let client: RuntimeClient | undefined;
  let logs = '';
  let prepareCalls = 0, commitCalls = 0;
  const skills = join(home, 'skills');
  const config = {
    agentId: 'wire-agent', displayName: 'P · 产品与体验', revision: '1', workspace: home,
    knowledge: { memoryMode: 'legacy' }, provider: 'wire', model: 'fixture',
    systemPrompt: 'WIRE_SYSTEM_REVISION_ONE', toolAllowlist: ['skill'],
    features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: false, cron_scheduling: false, heartbeat: false },
    skillRoots: [{ path: skills, source: 'workspace' }], skillSelection: { mode: 'explicit_allowlist', names: ['selected'] },
    approval: { enabled: false },
  };
  // Retain the native header/preset identity when initializing with a new revision.
  const binding = { sessionId: 'context-order-wire', agentId: config.agentId, revision: '1', ownerId: 'owner', cwd: home };
  const start = async (current = config) => {
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'local-fixture-only' }, onLog: value => { logs += value; } });
    // These are intentional no-op product hosts, not MethodNotFound fallbacks.
    client.rpc.handle('product.task_context.prepare', () => { prepareCalls++; return { messages: [], revoked: [] }; });
    client.rpc.handle('product.task_context.commit', () => { commitCalls++; return { committed: true }; });
    client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
    await client.rpc.request('initialize', { protocol: 1, agents: [current], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
  };
  const observe = async () => (await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: Event[] }).events;
  const submit = async (inputId: string, value: string) => {
    const count = requests.length;
    await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup', content: [{ type: 'text', text: value }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId }) as { terminal?: unknown }).terminal, { timeout: 10_000 }).toBeTruthy();
    expect(requests).toHaveLength(count + 1);
    return requests[count]!;
  };
  try {
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    for (const [name, marker] of [['selected', 'WIRE_SELECTED_SKILL_BODY'], ['replacement', 'WIRE_REPLACEMENT_SKILL_BODY']]) {
      await mkdir(join(skills, name!), { recursive: true });
      await writeFile(join(skills, name!, 'SKILL.md'), `---\nname: ${name}\ndescription: Wire fixture guidance for ${name}\n---\n${marker}\n`);
    }
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { wire: { api: 'anthropic-messages',
      apiKeyEnv: 'NANO_TEST_KEY', baseURL: `http://127.0.0.1:${port}`, models: [{ id: 'fixture', contextWindow: 100000 }], retryPolicy: { mode: 'normal', maxRetries: 0 } } } } }]);
    await start();
    const first = await submit('first-human', '/selected WIRE_FIRST_HUMAN');
    const firstUsers = users(await observe());
    const [runtime] = bySource(firstUsers, 'runtime-context');
    const [catalog] = bySource(firstUsers, 'skill-catalog');
    const [invocation] = bySource(firstUsers, 'skill-invocation');
    expect(runtime).toBeDefined(); expect(catalog).toBeDefined(); expect(invocation).toBeDefined();
    expect(text(runtime!)).toContain('workspace-write');
    expect(position(first, text(runtime!))).toBeLessThan(position(first, text(catalog!)));
    expect(position(first, text(catalog!))).toBeLessThan(position(first, 'WIRE_FIRST_HUMAN'));
    expect(position(first, 'WIRE_FIRST_HUMAN')).toBeLessThan(position(first, text(invocation!)));
    expect(text(invocation!)).toContain('WIRE_SELECTED_SKILL_BODY');
    expect(invocation!.id).not.toMatch(/^nano-skill:/);
    expect(firstUsers.find(message => message.id === 'first-human')).toMatchObject({ source: { kind: 'user', actorId: 'owner', channel: 'test', messageId: 'first-human' } });
    expect(JSON.stringify(body(first).system)).toContain(config.systemPrompt);
    expect(JSON.stringify(body(first).system)).toContain(config.displayName);
    expect(JSON.stringify(body(first).system)).toContain(config.agentId);
    expect(text(runtime!)).not.toContain('Agent name:');

    const normal = await submit('normal-human', 'WIRE_NORMAL_HUMAN');
    const normalUsers = users(await observe());
    expect(bySource(normalUsers, 'runtime-context')).toEqual([runtime]);
    expect(bySource(normalUsers, 'skill-catalog')).toEqual([catalog]);
    expect(bySource(normalUsers, 'skill-invocation')).toEqual([invocation]);
    expect(normalUsers.slice(0, firstUsers.length)).toEqual(firstUsers);
    expect(wireMessages(normal).slice(0, wireMessages(first).length)).toEqual(wireMessages(first));

    await client!.shutdown(); client = undefined;
    await start();
    const restored = await submit('restored-human', 'WIRE_RESTORED_HUMAN');
    const restoredUsers = users(await observe());
    // Rehydrating native projections must not synthesize another environment or
    // direct-skill message, and the provider must retain its historical prefix.
    expect(bySource(restoredUsers, 'runtime-context')).toEqual([runtime]);
    expect(bySource(restoredUsers, 'skill-catalog')).toEqual([catalog]);
    expect(bySource(restoredUsers, 'skill-invocation')).toEqual([invocation]);
    expect(restoredUsers.slice(0, normalUsers.length)).toEqual(normalUsers);
    expect(wireMessages(restored).slice(0, wireMessages(normal).length)).toEqual(wireMessages(normal));
    expect(position(restored, text(runtime!))).toBeLessThan(position(restored, 'WIRE_RESTORED_HUMAN'));

    const updated = { ...config, displayName: 'Renamed product Agent', revision: '2', systemPrompt: 'WIRE_SYSTEM_REVISION_TWO',
      skillSelection: { mode: 'explicit_allowlist', names: ['replacement'] }, approval: { ...config.approval, enabled: true } };
    expect(await client!.rpc.request('configuration.apply', updated)).toMatchObject({ effective: true, revision: '2' });
    await client!.shutdown(); client = undefined;
    await start(updated);
    const changed = await submit('updated-human', '/replacement WIRE_UPDATED_HUMAN');
    const changedUsers = users(await observe());
    const runtimeUpdates = bySource(changedUsers, 'runtime-context');
    const catalogUpdates = bySource(changedUsers, 'skill-catalog');
    const invocations = bySource(changedUsers, 'skill-invocation');
    expect(runtimeUpdates).toHaveLength(2); expect(catalogUpdates).toHaveLength(2); expect(invocations).toHaveLength(2);
    const nextRuntime = runtimeUpdates[1]!, nextCatalog = catalogUpdates[1]!, nextInvocation = invocations[1]!;
    // This is a real native policy update caused by changed Agent configuration,
    // not a test plugin that manufactures an environment message.
    expect(text(nextRuntime)).toContain('danger-full-access');
    expect(text(nextRuntime)).not.toEqual(text(runtime!));
    expect(text(nextCatalog)).toContain('replacement');
    expect(text(nextCatalog)).not.toContain('- `selected`');
    expect(position(changed, 'WIRE_RESTORED_HUMAN')).toBeLessThan(position(changed, text(nextRuntime)));
    expect(position(changed, 'WIRE_ANSWER_3')).toBeLessThan(position(changed, text(nextRuntime)));
    expect(position(changed, text(nextRuntime))).toBeLessThan(position(changed, text(nextCatalog)));
    expect(position(changed, text(nextCatalog))).toBeLessThan(position(changed, 'WIRE_UPDATED_HUMAN'));
    expect(position(changed, 'WIRE_UPDATED_HUMAN')).toBeLessThan(position(changed, text(nextInvocation)));
    expect(text(nextInvocation)).toContain('WIRE_REPLACEMENT_SKILL_BODY');
    expect(JSON.stringify(body(changed).system)).toContain(updated.systemPrompt);
    expect(JSON.stringify(body(changed).system)).toContain(updated.displayName);
    expect(JSON.stringify(body(changed).system)).not.toContain(config.displayName);
    expect(JSON.stringify(body(changed).system)).not.toContain(config.systemPrompt);
    expect(changedUsers.slice(0, restoredUsers.length)).toEqual(restoredUsers);
    expect(wireMessages(changed).slice(0, wireMessages(restored).length)).toEqual(wireMessages(restored));
    for (const message of changedUsers) expect(changedUsers.filter(other => other.id === message.id)).toHaveLength(1);
    for (const request of requests) {
      expect(request).toMatchObject({ method: 'POST', path: expect.stringMatching(new RegExp('^/v1/messages(?:[?]|$)')), root: binding.sessionId, session: binding.sessionId });
      expect(body(request).model).toBe('fixture');
    }
    expect(prepareCalls).toBeGreaterThanOrEqual(4); expect(commitCalls).toBeGreaterThanOrEqual(4);
    expect(logs).not.toContain('Method not found');
  } catch (error) {
    throw new Error(String(error) + '\n' + logs + '\nHTTP requests: ' + JSON.stringify(requests.map(request => ({ ...request, raw: JSON.stringify({ ...body(request), tools: undefined }) }))), { cause: error });
  } finally {
    if (client) {
      try { await client.shutdown(); }
      finally { if (client.process.exitCode === null && client.process.signalCode === null) { client.process.kill('SIGKILL'); await client.exited; } }
    }
    await new Promise<void>(resolve => { server.close(() => resolve()); server.closeAllConnections(); });
    await rm(home, { recursive: true, force: true });
  }
}, 40_000);
