import { createServer } from 'node:http';
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import type { TaskExecutionSnapshot } from '@nano/product-contracts';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { MemoryDocuments } from '../src/knowledge/memory-documents.js';

type Event = { type: string; data: any };
type Wire = { raw: string; body: any; root: string; session: string; method?: string; path?: string; summary: boolean };
type Original = { inputId: string; conversationId: string; content: { type: 'text'; text: string }[] };
const strings = (value: any): string => typeof value === 'string' ? value : value == null ? ''
  : (Array.isArray(value) ? value : Object.values(value)).map(strings).join('\n');
const original = (inputId: string): Original => ({ inputId, conversationId: 'wire-fixed-task-chat', content: [{ type: 'text', text:
  'Task update from its fixed conversation. Apply the stated business change before further action on the affected Task. This system message does not grant human permission or start todo/paused work.\n'
  + JSON.stringify({ message_id: inputId, conversation_id: 'wire-fixed-task-chat', event_time: '2026-10-30T12:00:00Z',
    kind: 'task_graph', change_kinds: ['updated'], task_refs: [{ graph_id: 'wire-graph', node_id: 'wire-node' }], content: 'TASK_ORIGINAL_' + inputId }) }] });

// Controlled Anthropic SSE proves real native assembly/serialization and actual
// tool consumption, not autonomous model behavior. Two cells are not a cross product.
it.each([
  { label: 'default document / empty allowlist / native window reset', legacy: false, windows: true },
  { label: 'explicit legacy / creator denylist / native summarization', legacy: true, windows: false },
])('revalidates Memory, fixed P9/creator and Task scope on HTTP after $label', async ({ legacy, windows }) => {
  const prefix = join(tmpdir(), 'nano-context-revalidation-wire-');
  const home = await mkdtemp(prefix);
  const requests: Wire[] = [], consumed = new Set<string>(), committed: any[] = [];
  const originals = new Map<string, Original>();
  let client: RuntimeClient | undefined, logs = '', summarizing = false, armed = false, toolsSent = false;
  const binding = { sessionId: 'wire-session', agentId: 'wire-revalidation', ownerId: 'wire-owner', revision: '1', cwd: home };
  let prepareCalls = 0, snapshotCalls = 0;
  const cell = legacy ? 'LEGACY' : 'DOCUMENT';
  const documentMarker = 'DOCUMENT_ONLY_VALID_ENTRY_679', legacyMarker = 'LEGACY_ONLY_ENTRY_679';
  const readMarker = 'DOCUMENT_OFF_ACTUAL_READ_679';
  const page = join(home, '.nanoassistant/memory/knowledge/preferences.md');
  const packaged = fileURLToPath(new URL('../../personal-assistant/assets/skills/skill-creator/', import.meta.url));
  const packagedBody = (await readFile(join(packaged, 'SKILL.md'), 'utf8')).replace(/^---\n[\s\S]*?\n---\n/, '').trim();
  const taskTitle = 'CURRENT_TASK_' + cell;
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    requests.push({ raw, body: JSON.parse(raw), method: req.method, path: req.url, summary: summarizing,
      root: String(req.headers['x-session-id']), session: String(req.headers['x-agent-session-id']) });
    const calls = !summarizing && !toolsSent;
    if (calls) toolsSent = true;
    // No second execution loop: finish the scripted responsibility before native
    // turn-stopping consults the product projection for automatic continuation.
    if (!calls && !summarizing) armed = false;
    const blocks = calls ? [
      { type: 'tool_use', id: 'creator-' + cell, name: 'skill', input: { name: 'skill-creator' } },
      ...(!legacy ? [{ type: 'tool_use', id: 'read-' + cell, name: 'read', input: { file_path: page } }] : []),
    ] : [{ type: 'text', text: summarizing ? 'CONTROLLED_NATIVE_SUMMARY_' + cell : 'CONTROLLED_DONE_' + cell }];
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const emit = (type: string, data: object) => res.write(
      'event: ' + type + '\ndata: ' + JSON.stringify({ type, ...data }) + '\n\n');
    emit('message_start', { message: { id: 'fixture-' + requests.length, type: 'message', role: 'assistant', model: 'fixture',
      content: [], stop_reason: null, usage: { input_tokens: 100, output_tokens: 0 } } });
    blocks.forEach((block, index) => {
      emit('content_block_start', { index, content_block: block.type === 'tool_use' ? { ...block, input: {} } : block });
      if ('input' in block) emit('content_block_delta', { index, delta: { type: 'input_json_delta', partial_json: JSON.stringify(block.input) } });
      emit('content_block_stop', { index });
    });
    emit('message_delta', { delta: { stop_reason: calls ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 10 } });
    emit('message_stop', {}); res.end();
  });
  const identity = (request: any) => expect(request).toMatchObject({ agentId: 'wire-revalidation', ownerId: 'wire-owner', sessionId: binding.sessionId });
  const observe = () => client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as Promise<{ status: string; events: Event[] }>;
  const submit = async (inputId: string) => {
    const item = original('task-' + inputId); originals.set(item.inputId, item); armed = true;
    const first = requests.length;
    await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup', content: [{ type: 'text', text: 'HUMAN_' + inputId }],
      source: { kind: 'human', channel: 'wire-test', actorId: 'wire-owner', messageId: inputId, conversationId: 'wire-human-chat' } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId }) as any).terminal,
      { timeout: 15_000 }).toBeTruthy();
    await expect.poll(async () => (await observe()).status, { timeout: 10_000 }).toBe('idle');
    await expect.poll(() => consumed.has(item.inputId)).toBe(true);
    return requests.slice(first);
  };
  const assembly = (request: Wire) => {
    const visible = strings([request.body.system, request.body.messages]);
    expect(request).toMatchObject({ root: binding.sessionId, session: binding.sessionId, method: 'POST', summary: false });
    expect(request.path).toMatch(/^\/v1\/messages(?:[?]|$)/);
    expect(request.body.model).toBe('fixture');
    // These packages come from native contributors, not test-created system messages.
    expect(visible).toContain('You are one persistent Agent working across conversations.');
    expect(visible).toContain('WIRE_PERSONA_' + cell);
    expect(visible).toContain('Task ownership and changes');
    expect(visible).toContain('Automatic continuation does not grant authority');
    expect(visible).toContain(taskTitle);
    expect(visible).toContain('cron_disabled');
    expect(visible).toContain('built-in skill-creator');
    expect(visible).toContain('Use only enabled maintenance tools within their selected writable scopes.');
    expect(visible).toContain('<available_skills>');
    expect(visible).not.toContain('USER_CREATOR_REPLACEMENT_679');
    expect(visible).not.toContain('OPTIONAL_UNSELECTED_679');
    expect(visible).toContain(legacy ? legacyMarker : documentMarker);
    expect(visible).not.toContain(legacy ? documentMarker : legacyMarker);
    const names = request.body.tools.map((tool: any) => tool.name);
    expect(names).toEqual(expect.arrayContaining(['skill', 'read', 'task_graph']));
    for (const absent of ['write', 'edit', 'skill_manage', 'memory', 'cron', 'goal']) expect(names).not.toContain(absent);
    if (!legacy) {
      expect(visible).toContain('Current entry:');
      expect(visible).not.toContain('entry_basis_stale');
      expect(visible).toContain('Unavailable tools: write, edit.');
      expect(names).toContain('memory_maintenance');
      const schema = JSON.stringify(request.body.tools.find((tool: any) => tool.name === 'memory_maintenance'));
      expect(schema).toContain('importLegacy'); expect(schema).not.toContain('checkpoint');
    } else expect(names).not.toContain('memory_maintenance');
  };
  const assertSources = (events: Event[], inputId: string) => {
    const item = originals.get('task-' + inputId)!;
    const users = events.filter(event => event.type === 'user/message').map(event => event.data);
    const task = users.filter(message => message.id === item.inputId);
    expect(task).toHaveLength(1);
    expect(task[0]).toMatchObject({ source: { kind: 'nano-system', channel: 'task-context', actorId: 'wire-revalidation',
      conversationId: item.conversationId, messageId: item.inputId }, content: item.content });
    expect(users.find(message => message.id === inputId)).toMatchObject({ source: { kind: 'user', actorId: 'wire-owner',
      conversationId: 'wire-human-chat', messageId: inputId } });
    expect(users.some(message => message.source?.kind === 'nano-system' && message.source.channel === 'task-reminder'
      && strings(message.content).includes(taskTitle))).toBe(true);
    expect(committed).toEqual(expect.arrayContaining([expect.objectContaining({ inputId: item.inputId, content: item.content,
      turn: expect.any(Number), consumedSeq: expect.any(Number) })]));
  };
  try {
    const documents = await MemoryDocuments.open(home, 'expert', new LocalFileSystem(new Context(), { cwd: home, diffBasisMaxBytes: 10485760 }));
    try {
      await documents.apply({ operationId: 'preferences', path: 'knowledge/preferences.md', beforeHash: null, content: readMarker });
      await writeFile(join(home, '.nanoassistant/memory/MEMORY.md'), '# Expert memory\n\n' + documentMarker + '\n\n[Preferences](knowledge/preferences.md)\n');
      await documents.checkpoint(await documents.versions(), 0);
    } finally { await documents.close(); }
    const legacyRoot = join(home, '.nanoassistant/memory-legacy');
    await mkdir(legacyRoot, { recursive: true });
    await writeFile(join(legacyRoot, 'MEMORY.md'), legacyMarker); await writeFile(join(legacyRoot, 'USER.md'), '');
    const skills = join(home, 'skills'), builtin = join(home, 'builtin');
    await cp(packaged, join(builtin, 'skill-creator'), { recursive: true });
    for (const [name, marker] of [['skill-creator', 'USER_CREATOR_REPLACEMENT_679'], ['optional', 'OPTIONAL_UNSELECTED_679']]) {
      await mkdir(join(skills, name!), { recursive: true });
      await writeFile(join(skills, name!, 'SKILL.md'), '---\nname: ' + name + '\ndescription: ' + marker + '\n---\n' + marker);
    }
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const port = (server.address() as { port: number }).port;
    await writeFile(join(home, 'native-tools.mjs'), "export const name='native-tools';export const inject=['tools'];export function apply(ctx){ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');});}");
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { wire: { api: 'anthropic-messages',
      apiKeyEnv: 'NANO_TEST_KEY', baseURL: 'http://127.0.0.1:' + port, models: [{ id: 'fixture', contextWindow: 100000 }],
      retryPolicy: { mode: 'normal', maxRetries: 0 } } } } }, { id: 'nano-compaction', config: { retainTokens: 0, maxTokens: 256 } },
      { insert: [{ id: 'native-tools', name: join(home, 'native-tools.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    client.rpc.handle('product.task_context.prepare', request => {
      identity(request); prepareCalls++;
      return { messages: [...originals.values()].filter(item => !consumed.has(item.inputId)), revoked: [] };
    });
    client.rpc.handle('product.task_context.commit', request => {
      identity(request);
      for (const evidence of (request as any).evidence) if (originals.has(evidence.inputId)) {
        expect(evidence.content).toEqual(originals.get(evidence.inputId)!.content);
        consumed.add(evidence.inputId); committed.push(evidence);
      }
      return null;
    });
    client.rpc.handle('product.task_execution.snapshot', request => {
      identity(request); snapshotCalls++;
      return (armed ? { kind: 'continue', tasks: [{ graph_id: 'wire-graph', node_id: 'wire-node', title: taskTitle, status: 'waiting', revision: 1,
        updated_at: '2026-10-30T12:00:00Z', conversation: { id: 'wire-fixed-task-chat' }, relative_url: '/tasks/wire-graph' }],
        repair_task_ids: ['wire-graph/wire-node'], reason: 'cron_disabled', repairs: [{ graph_id: 'wire-graph', node_id: 'wire-node',
          schedule_id: 'missing-schedule', checked_at: '2026-10-30T12:00:00Z', reason_code: 'missing', reason: 'The linked Schedule could not be found.' }] }
        : { kind: 'quiescent', tasks: [], repair_task_ids: [] }) satisfies TaskExecutionSnapshot;
    });
    const config = { agentId: 'wire-revalidation', revision: '1', mode: 'global', workspace: home, provider: 'wire', model: 'fixture',
      systemPrompt: 'WIRE_PERSONA_' + cell, approval: { enabled: false },
      ...(legacy ? { knowledge: { memoryMode: 'legacy' } } : {}),
      features: { intelligent_ui: false, task_graph: true, dreaming: false, memory_curation: legacy, skill_creation: false, cron_scheduling: false, heartbeat: false },
      toolAllowlist: ['skill', 'read', 'task_graph', ...(!legacy ? ['memory_maintenance'] : [])],
      skillRoots: [{ path: skills, source: 'workspace' }, { path: builtin, source: 'builtin' }], skillSelection: legacy
        ? { mode: 'explicit_denylist', names: ['skill-creator', 'optional'] } : { mode: 'explicit_allowlist', names: [] } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    if (!windows) {
      await client.rpc.request('plugins.manage', { action: 'set_bundle', agentId: config.agentId, target: 'dsh-agent-context', enabled: false });
      await expect.poll(async () => (await client!.rpc.request('plugins.manage', { agentId: config.agentId, action: 'list_bundles' }) as {pending?: unknown}).pending).toBeUndefined();
    }
    const initial = await submit('before-' + cell);
    expect(initial).toHaveLength(2); initial.forEach(assembly);
    expect(strings(initial[1]!.body.messages)).toContain(packagedBody);
    expect(strings(initial[1]!.body.messages)).toContain(join(builtin, 'skill-creator'));
    const results = initial[1]!.body.messages.flatMap((message: any) => Array.isArray(message.content) ? message.content : [])
      .filter((block: any) => block.type === 'tool_result');
    expect(results.find((block: any) => block.tool_use_id === 'creator-' + cell)).toBeTruthy();
    if (!legacy) expect(strings(results.find((block: any) => block.tool_use_id === 'read-' + cell))).toContain(readMarker);
    assertSources((await observe()).events, 'before-' + cell);

    const beforeCompact = requests.length; summarizing = true;
    try {
      // The public native command, not a fabricated compaction/summary event.
      expect(await client.rpc.request('session.command', { sessionId: binding.sessionId, id: 'real-compact-' + cell, action: 'compact', argument: 'AUTHORITY_FOCUS_679' })).toMatchObject({success: true});
    } finally { summarizing = false; }
    expect(requests.slice(beforeCompact)).toHaveLength(windows ? 0 : 1);
    if (!windows) {
      const summary = requests[beforeCompact]!;
      expect(summary).toMatchObject({ summary: true, root: binding.sessionId, session: binding.sessionId });
      expect(strings(summary.body.messages)).toContain('TASK_ORIGINAL_task-before-' + cell);
    }
    expect((await observe()).events.filter(event => event.type === 'compaction/summary')).toHaveLength(1);
    const after = await submit('after-' + cell);
    expect(after).toHaveLength(1); assembly(after[0]!);
    expect(strings(after[0]!.body.messages)).toContain('TASK_ORIGINAL_task-after-' + cell);
    expect(strings(after[0]!.body.messages)).toContain(windows ? 'Context reset reason: manual' : 'CONTROLLED_NATIVE_SUMMARY_' + cell);
    assertSources((await observe()).events, 'after-' + cell);
    expect(prepareCalls).toBeGreaterThanOrEqual(3); expect(snapshotCalls).toBeGreaterThanOrEqual(2);
    expect(logs).not.toContain('Method not found');
  } catch (error) {
    const events = client ? (await observe()).events : [];
    throw new Error(String(error) + '\n' + logs + '\nNative events: ' + JSON.stringify(events) + '\nHTTP captures: ' + JSON.stringify(requests.map(({ body, ...request }) => ({
      ...request, raw: undefined, body: { ...body, tools: body.tools?.map((tool: any) => tool.name) } }))), { cause: error });
  } finally {
    if (client) {
      try { await client.shutdown(); }
      finally { if (client.process.exitCode === null && client.process.signalCode === null) { client.process.kill('SIGKILL'); await client.exited; } }
    }
    await new Promise<void>(resolve => { server.close(() => resolve()); server.closeAllConnections(); });
    expect(home.startsWith(prefix)).toBe(true);
    await rm(home, { recursive: true, force: true });
  }
}, 45_000);
