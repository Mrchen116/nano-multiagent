import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import { ApprovalSources } from '../src/policy/sources.js';
import type { SessionDeletionPlan } from '../src/agent-deletion.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { childProbe, nativeChildren } from './helpers/native-child-probe.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('classifies nano-runtime-* subagents.prompt inputs as system_source rather than direct-parent or human', async () => {
  const initial = { id: 'm-init', role: 'user', content: [{ type: 'text', text: 'Original delegated task' }], source: { kind: 'user' } };
  const recovery = {
    id: 'm-rec',
    role: 'user',
    content: [{ type: 'text', text: 'The execution runtime was interrupted and has recovered.' }],
    source: { kind: 'user', rpcId: 'nano-runtime-recovery:child-1:12' },
  };
  const scheduleChange = {
    id: 'm-sched',
    role: 'user',
    content: [{ type: 'text', text: 'Schedule deleted by the user.' }],
    source: { kind: 'user', rpcId: 'nano-runtime-schedule-change:schedule-deleted:1' },
  };
  const wdChange = {
    id: 'm-wd',
    role: 'user',
    content: [{ type: 'text', text: 'The working directory changed.' }],
    source: { kind: 'working-directory' },
  };
  const events = [
    { seq: 0, type: 'subagent/descriptor', data: { version: 3, mode: 'continuable', provider: 'spawn', label: 'worker' } },
    { seq: 1, type: 'user/message', data: initial },
    { seq: 2, type: 'user/message', data: recovery },
    { seq: 3, type: 'user/message', data: scheduleChange },
    { seq: 4, type: 'user/message', data: wdChange },
  ];
  const child = {
    id: 'child-1',
    session: { header: { origin: 'subagent', parentSession: 'root' }, isOwnSeq: () => true, snapshotEvents: () => events, deriveMessages: () => [initial, recovery, scheduleChange, wdChange] },
  } as unknown as Agent;
  const sources = new ApprovalSources();
  expect(sources.humanInputs(child)).toEqual([]);
  const history = await sources.history(child);
  expect(history.find(row => row.user === 'Original delegated task')?.origin).toEqual({ kind: 'direct-parent' });
  expect(history.find(row => String(row.user).includes('interrupted and has recovered'))?.origin).toEqual({
    kind: 'nano-system',
    channel: 'runtime-recovery',
    messageId: 'nano-runtime-recovery:child-1:12',
  });
  expect(history.find(row => String(row.user).includes('Schedule deleted'))?.origin).toEqual({
    kind: 'nano-system',
    channel: 'schedule-change',
    messageId: 'nano-runtime-schedule-change:schedule-deleted:1',
  });
  const pending = { name: 'bash', callId: 'c1', arguments: { command: 'echo ok' } } as ToolExecution;
  const transcript = await sources.transcript(child, pending, []);
  expect(transcript).toContain('[SYSTEM NOTIFICATION - NOT USER INPUT]');
  expect(transcript).not.toContain('Agent lead sent a message:');
  expect(transcript).not.toContain('[UNCLASSIFIED SOURCE');
});

it('keeps TaskContextDriver stoppingSessions active across new_context turn-stopping rollover and isolates Workflow workChildren from InterruptedWork and send_message', async () => {
  const home = await mkdtemp(join(tmpdir(), 'turn-stopping-and-wf-guard-'));
  const workspace = join(home, 'workspace');
  let client: RuntimeClient | undefined;
  let logs = '';
  let prepareCalls = 0;
  try {
    await mkdir(workspace, { recursive: true });
    await writeFile(join(home, 'fixture.mjs'), `import { writeFile } from 'node:fs/promises';
export const name = 'rollover-wf-fixture';
export const inject = ['llm', 'agents'];
export function apply(ctx) {
  const seen = new Set();
  ctx.on('llm/stream', async function*(options) {
    const agent = ctx.agents.get(options.sessionId);
    const user = options.messages.findLast(m => m.role === 'user');
    const txt = JSON.stringify(user?.content ?? []);
    if (agent.id === 'root' && txt.includes('TRIGGER_NEW_CONTEXT') && !seen.has('nc')) {
      seen.add('nc');
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'nc-1', name: 'new_context', arguments: JSON.stringify({ summary: 'carry forward summary' }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (agent.id === 'root' && txt.includes('TRIGGER_WORKFLOW') && !seen.has('wf')) {
      seen.add('wf');
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'wf-1', name: 'workflow', arguments: JSON.stringify({ script: "const r = await agent('Run workflow step', { label: 'wf-step-1' }); return r;", meta: { name: 'single-step', description: 'One step' } }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (agent.id === 'root' && txt.includes('SEND_TO_WF_STEP:') && !seen.has('send-wf')) {
      seen.add('send-wf');
      const targetName = /SEND_TO_WF_STEP:([^"\\s]+)/.exec(txt)[1];
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'send-wf-1', name: 'send_message', arguments: JSON.stringify({ agent: targetName, message: 'unauthorized direct poke' }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (agent.id !== 'root') {
      await writeFile(process.env.DSH_HOME + '/wf-child-id', agent.id);
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'step-ok' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
    await prepareProfile(home, [{ insert: [{ id: 'rollover-wf-fixture', name: join(home, 'fixture.mjs') }] }]);
    const config = {
      agentId: 'a',
      revision: '1',
      mode: 'global',
      workspace,
      provider: 'deepseek-official',
      model: 'deepseek-flash',
      toolAllowlist: ['workflow', 'send_message', 'inbox', 'conversations'],
      features: { cron_scheduling: false, task_graph: false, heartbeat: false, dreaming: false },
      approval: { dangerouslySkipPermissions: true },
    };
    const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: workspace };
    client = new RuntimeClient({ home, cwd: workspace, onLog: text => { logs += text; } });
    client.rpc.handle('product.task_context.prepare', () => {
      prepareCalls++;
      return { messages: [], revoked: [] };
    });
    client.rpc.handle('product.task_context.commit', () => null);
    client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);

    // 1. new_context rollover runs in agent/turn-stopping: must NOT trigger an extra product.task_context.prepare!
    prepareCalls = 0;
    await client.rpc.request('session.submit', {
      sessionId: 'root',
      inputId: 'turn-nc',
      mode: 'followup',
      content: [{ type: 'text', text: 'TRIGGER_NEW_CONTEXT' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'turn-nc' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: 'turn-nc' }) as { terminal?: { kind: string } }).terminal?.kind).toBe('completed');
    // Exactly 2 real steps ran (step 1 calling new_context, step 2 final text); turn-stopping rollover must add 0 extra prepare calls.
    expect(prepareCalls).toBe(2);

    // 2. Workflow step child is blocked from direct send_message({ agent }) both by catalog name and sessionId.
    await client.rpc.request('session.submit', {
      sessionId: 'root',
      inputId: 'turn-wf',
      mode: 'followup',
      content: [{ type: 'text', text: 'TRIGGER_WORKFLOW' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'turn-wf' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: 'turn-wf' }) as { terminal?: { kind: string } }).terminal?.kind, { timeout: 15_000 }).toBe('completed');
    await expect.poll(async () => ((await client!.rpc.request('workflow.read', { sessionId: 'root' })) as { state?: string }[])[0]?.state, { timeout: 15_000 }).toBe('completed');
    const wfChildId = await readFile(join(home, 'wf-child-id'), 'utf8');
    await client.rpc.request('session.submit', {
      sessionId: 'root',
      inputId: 'turn-send-wf',
      mode: 'followup',
      content: [{ type: 'text', text: `SEND_TO_WF_STEP:${wfChildId}` }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'turn-send-wf' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: 'turn-send-wf' }) as { terminal?: { kind: string } }).terminal?.kind).toBe('completed');
    const obs = await client.rpc.request('session.observe', { sessionId: 'root' }) as { events: { type: string; data: any }[] };
    const blockedSend = obs.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'send-wf-1');
    expect(blockedSend?.data.message.isError).toBe(true);
    expect(JSON.stringify(blockedSend?.data.message.content)).toContain('Invalid public message');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);

it('recovers an interrupted continuable child inside SubagentManager without fabricating a parent lead prefix, forks without parentSession, and enforces R2-R1 schedule_ended', async () => {
  const home = await mkdtemp(join(tmpdir(), 'recovery-fork-cron-'));
  const workspace = join(home, 'workspace');
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await mkdir(workspace, { recursive: true });
    await writeFile(join(home, 'fixture.mjs'), `import { appendFile, writeFile, access } from 'node:fs/promises';
export const name = 'recovery-fixture';
export const inject = ['llm', 'agents', 'sessions'];
export function apply(ctx) {
  let hungOnce = false;
  ctx.on('llm/stream', async function*(options) {
    const agent = ctx.agents.get(options.sessionId);
    await appendFile(process.env.DSH_HOME + '/wire.jsonl', JSON.stringify({ id: agent.id, model: options.model, messages: options.messages }) + '\\n');
    const alreadyDelegated = options.messages.some(m => m.role === 'assistant' && m.content?.some(b => b.type === 'tool-call' && b.name === 'delegate_worker'));
    if (agent.id === 'root' && !alreadyDelegated) {
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'spawn-1', name: 'delegate_worker', arguments: JSON.stringify({ action: 'start', label: 'Interruptible worker', message: 'Start long child task' }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (agent.id !== 'root' && !await access(process.env.DSH_HOME + '/recovered-flag').then(() => true, () => false) && !hungOnce) {
      hungOnce = true;
      const rootSession = ctx.sessions.get('root');
      if (rootSession) await ctx.sessions.flush(rootSession);
      await ctx.sessions.flush(agent.session);
      await writeFile(process.env.DSH_HOME + '/child-running', agent.id);
      await new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }));
      return;
    }
    if (agent.id !== 'root' && !options.messages.some(m => m.role === 'tool')) {
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'reply-parent', name: 'send_message', arguments: JSON.stringify({ agent: 'lead', message: 'Recovered child finished cleanly' }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'completed' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
    await prepareProfile(home, [{ insert: [childProbe, { id: 'recovery-fixture', name: join(home, 'fixture.mjs') }] }], { agentDeletion: true });
    const config = {
      agentId: 'a',
      revision: '1',
      mode: 'global',
      workspace,
      provider: 'deepseek-official',
      model: 'deepseek-flash',
      toolAllowlist: ['subagent', 'send_message', 'inbox', 'conversations', 'schedule_create', 'schedule_update'],
      features: { cron_scheduling: true, task_graph: false, heartbeat: false, dreaming: false },
      approval: { dangerouslySkipPermissions: true },
    };
    const binding = { sessionId: 'root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: workspace };
    const start = async () => {
      client = new RuntimeClient({ home, cwd: workspace, onLog: text => { logs += text; } });
      registerNoopTaskHosts(client);
      await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
    };

    await start();
    await client!.rpc.request('session.submit', {
      sessionId: 'root',
      inputId: 'kickoff',
      mode: 'followup',
      content: [{ type: 'text', text: 'Run worker' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'kickoff' },
    });
    await expect.poll(() => readFile(join(home, 'child-running'), 'utf8').catch(() => '')).not.toBe('');
    const childId = await readFile(join(home, 'child-running'), 'utf8');

    // Verify R2-R1 schedule_ended and v2 rrule creation before restart.
    const rruleTask = await client!.rpc.request('schedule.command', {
      agentId: 'a',
      sessionId: 'root',
      action: 'create',
      args: { title: 'RRULE check', prompt: 'Ping', rrule: 'DTSTART:20261201T090000Z\nRRULE:FREQ=DAILY;COUNT=2' },
    }) as { id: string; kind: string };
    expect(rruleTask.kind).toBe('rrule');
    await client!.rpc.request('schedule.command', { agentId: 'a', sessionId: 'root', action: 'delete', args: { id: rruleTask.id } });

    const oneShot = await client!.rpc.request('schedule.command', {
      agentId: 'a',
      sessionId: 'root',
      action: 'create',
      args: { title: 'One-shot', prompt: 'Fire once', after_seconds: 1 },
    }) as { id: string; kind: 'after'; title: string; prompt: string; afterSeconds: number; scheduledAt: string };
    await expect.poll(async () => {
      const cat = await client!.rpc.request('schedule.command', { agentId: 'a', action: 'catalog' }) as { id: string; status: string }[];
      return cat.find(entry => entry.id === oneShot.id)?.status;
    }, { timeout: 6000 }).toBe('inactive');
    const endedUpdate = await client!.rpc.request('schedule.command', {
      agentId: 'a',
      sessionId: 'root',
      action: 'update',
      args: { id: oneShot.id, expected: oneShot, title: 'Too late without new timing' },
    });
    expect(endedUpdate).toEqual({ id: oneShot.id, updated: false, code: 'schedule_ended' });

    // Simulate process crash while child turn is mid-flight, then cold-recover.
    await writeFile(join(home, 'recovered-flag'), 'yes');
    client!.process.kill('SIGKILL');
    await client!.exited;
    client = undefined;

    await start();
    await expect.poll(async () => {
      const children = await nativeChildren(home);
      const target = children.find(c => c.id === childId);
      return target?.events.filter((e: { type: string }) => e.type === 'turn/end').length ?? 0;
    }, { timeout: 15_000 }).toBeGreaterThanOrEqual(1);

    const wire = (await readFile(join(home, 'wire.jsonl'), 'utf8')).trim().split('\n').map(l => JSON.parse(l));
    const recoveredTurn = wire.findLast(row => row.id === childId);
    expect(JSON.stringify(recoveredTurn.messages)).toContain('The execution runtime was interrupted and has recovered.');
    expect(JSON.stringify(recoveredTurn.messages)).not.toContain('Agent lead sent a message:');

    const children = await nativeChildren(home);
    const childResults = children.find(c => c.id === childId)!.events.filter((e: any) => e.type === 'tool/result');
    expect(childResults.length).toBeGreaterThan(0);
    expect(childResults[0].data.message.isError).not.toBe(true);

    // Ordinary session.fork omits header.parentSession while remaining owned for deletion.
    const rootObserved = await client!.rpc.request('session.observe', { sessionId: 'root' }) as { events: { type: string; data: any }[] };
    const assistantMsg = rootObserved.events.findLast(e => e.type === 'assistant/message')!;
    const forked = await client!.rpc.request('session.fork', {
      sessionId: 'root',
      messageId: assistantMsg.data.message.id,
      operationId: 'fork-op-1',
    }) as { sessionId: string };

    await client!.rpc.request('agent.disable', { agentId: 'a', revision: 2 });
    const plan = await client!.rpc.request('agent.deletion.plan', { agentId: 'a', revision: 2, operationId: 'del-a' }) as SessionDeletionPlan;
    expect(plan.sessionIds).toEqual(expect.arrayContaining(['root', childId, forked.sessionId]));
    const forkHeader = plan.entries.find(e => e.header.id === forked.sessionId)!.header;
    expect(forkHeader.parentSession).toBeUndefined();
    expect(forkHeader.isSeeded).toBe(true);
    expect(forkHeader.origin).not.toBe('subagent');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client && client.process.exitCode === null) {
      client.process.kill('SIGKILL');
      await client.exited;
    }
    await rm(home, { recursive: true, force: true });
  }
}, 45_000);
