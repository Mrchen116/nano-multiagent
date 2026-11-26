import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const builtinSkillsPath = fileURLToPath(new URL('../../personal-assistant/assets/skills/', import.meta.url));

it('runs pure-click pendingTaskContext Dreaming with repair gate, blocks foreground reads of proactivity-signals.md, deduplicates across nights, and rolls back after 3 failed structure repairs', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-proactive-dreaming-feedback-'));
  let client: RuntimeClient | undefined;
  let logs = '';

  try {
    await writeFile(join(home, 'probe.mjs'), `import { appendFileSync } from 'node:fs';
export const name = 'proactive-feedback-probe';
export const inject = ['llm'];
export function apply(ctx) {
  const dreamSteps = new Map();
  const paSteps = new Map();
  let dreamRunNumber = 0;
  const runIndexBySession = new Map();

  ctx.on('llm/stream', async function* (o) {
    appendFileSync(process.env.DSH_HOME + '/llm-calls.jsonl', JSON.stringify({
      sessionId: o.sessionId,
      messages: o.messages,
    }) + '\\n');

    if (String(o.sessionId).startsWith('dreaming-')) {
      if (!runIndexBySession.has(o.sessionId)) {
        dreamRunNumber++;
        runIndexBySession.set(o.sessionId, dreamRunNumber);
      }
      const runNo = runIndexBySession.get(o.sessionId);
      const step = dreamSteps.get(o.sessionId) || 0;
      dreamSteps.set(o.sessionId, step + 1);
      const all = o.messages.map(m => (m.content || []).filter(b => b.type === 'text').map(b => b.text).join('')).join('\\n');
      const stage = all.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/)[1];

      if (runNo === 1) {
        // Night 1: Pure click (no chat messages). Verify conversations cutoff works, trigger 1 structure-gate repair, then write valid MEMORY.md + seen=1 signal!
        const calls = [
          ['conversations', { action: 'read', target: 'dm-owner', limit: 5 }],
          ['read', { file_path: stage + '/MEMORY.md' }],
          ['write', {
            file_path: stage + '/knowledge/proactivity-signals.md',
            content: '# 主动性隐式信号观察池\\n\\n- **体脂打卡提醒**（seen: 1，2027-03-15，未采纳待拍板卡 msg-reject-1）\\n',
          }],
          // Deliberately omit proactive section & illegally reference proactivity-signals.md on first commit!
          ['write', {
            file_path: stage + '/MEMORY.md',
            content: '# Personal memory\\n\\nSee [signals](knowledge/proactivity-signals.md).\\n',
          }],
          ['bash', {
            description: 'Commit invalid first draft to test consolidationIssues repair loop',
            command: 'git add -- MEMORY.md knowledge && git -c user.name=Nano -c user.email=memory@localhost commit -m invalid-draft',
          }],
          undefined, // Finish turn -> host checks consolidationIssues and sends repair attempt 1 of 3!
          ['write', {
            file_path: stage + '/MEMORY.md',
            content: '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n暂无已确认的主动性偏好。\\n\\n## Topics\\n\\nNo topics saved yet.\\n',
          }],
          ['bash', {
            description: 'Commit repaired MEMORY.md while keeping seen=1 only in proactivity-signals.md',
            command: 'git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m repaired-night1',
          }],
        ];
        const call = calls[step];
        if (call) {
          yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'd1-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
          yield { type: 'finish', reason: { kind: 'tool-calls' } };
          return;
        }
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Night 1 recorded seen=1 in signal pool.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
        return;
      }

      if (runNo === 2) {
        // Night 2: Day 2 injected msg-reject-1 into session + explicit rule in chat. Verify inline <proactivity_signals> and promote to MEMORY.md!
        const calls = [
          ['read', { file_path: stage + '/MEMORY.md' }],
          ['read', { file_path: stage + '/knowledge/proactivity-signals.md' }],
          ['write', {
            file_path: stage + '/knowledge/proactivity-signals.md',
            content: '# 主动性隐式信号观察池\\n\\n暂无待观察的单次信号。\\n',
          }],
          ['write', {
            file_path: stage + '/MEMORY.md',
            content: '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n### 免打扰禁区\\n- 体脂与健身打卡类事项不主动建立任务卡或提醒。\\n\\n## Topics\\n\\nNo topics saved yet.\\n',
          }],
          ['bash', {
            description: 'Promote boundary to MEMORY.md and clear signal pool',
            command: 'git add -- MEMORY.md knowledge && git -c user.name=Nano -c user.email=memory@localhost commit -m night2-promote',
          }],
        ];
        const call = calls[step];
        if (call) {
          yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'd2-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
          yield { type: 'finish', reason: { kind: 'tool-calls' } };
          return;
        }
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Night 2 promoted boundary.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
        return;
      }

      // Night 3: Commit structurally invalid MEMORY.md and refuse to repair across all 3 attempts -> verify Git rollback!
      if (step === 0) {
        yield {
          type: 'block-end',
          index: 0,
          block: {
            type: 'tool-call',
            id: 'd3-corrupt',
            name: 'bash',
            arguments: JSON.stringify({
              description: 'Commit structurally invalid PA MEMORY.md without proactive section',
              command: "printf '%s' '# Broken PA memory without proactive section\\n' > MEMORY.md && git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m broken-night3",
            }),
          },
        };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Refusing to repair.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    if (o.sessionId === 'pa-root') {
      const lastUser = o.messages.findLast(m => m.role === 'user' && m.source?.actorId === 'owner');
      const key = lastUser?.id || 'default';
      const n = paSteps.get(key) || 0;
      paSteps.set(key, n + 1);
      const text = lastUser?.content?.find(b => b.type === 'text')?.text || '';
      if (text.startsWith('try-read-signals')) {
        const signalsFile = process.env.DSH_HOME + '/.nanoassistant/memory/knowledge/proactivity-signals.md';
        const memoryRoot = process.env.DSH_HOME + '/.nanoassistant/memory';
        const memoryFile = memoryRoot + '/MEMORY.md';
        const calls = [
          ['read', { file_path: signalsFile }],
          ['grep', { path: signalsFile, pattern: '体脂' }],
          ['grep', { path: memoryRoot, pattern: '体脂' }],
          ['read', { file_path: memoryFile }],
        ];
        if (n < calls.length) {
          yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'fg-' + n, name: calls[n][0], arguments: JSON.stringify(calls[n][1]) } };
          yield { type: 'finish', reason: { kind: 'tool-calls' } };
          return;
        }
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Foreground turn finished.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    yield { type: 'block-end', index: 0, block: { type: 'text', text: JSON.stringify({ outcome: 'allow', risk_level: 'low', user_authorization: 'high', rationale: 'ok' }) } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);

    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test', contextWindow: 128000 }] } } } },
      { insert: [{ id: 'proactive-feedback-probe', name: join(home, 'probe.mjs') }] },
    ]);

    client = new RuntimeClient({
      home,
      cwd: home,
      env: { TZ: 'UTC', NANO_TEST_KEY: 'fixture' },
      onLog: text => { logs += text; },
    });

    const day1Start = Date.parse('2027-03-15T10:00:00+08:00');
    const clickTime = Date.parse('2027-03-15T18:20:00+08:00');
    let unconsumedPending = [
      {
        messageId: 'msg-reject-1',
        conversationId: 'dm-owner',
        timeMs: clickTime,
        text: 'Task update from its fixed conversation.\n{"kind":"task_graph","previous_status":"proposed","status":"closed","actor":{"type":"user","id":"owner"},"content":"Owner：[体脂打卡提醒](/tasks/tg_1?scope=n1&node=n1)，未采纳（已关闭）"}',
      },
    ];
    let injectOnNextStep = false;
    const refreshArgsLog: Record<string, unknown>[] = [];
    const memoryConversationCutoffs: { cutoff: number; afterTime: number }[] = [];

    // Register custom task_context host so Day 2 injects msg-reject-1 into the live PA session.
    client.rpc.handle('product.task_context.prepare', () => {
      if (!injectOnNextStep) return { messages: [], revoked: [] };
      injectOnNextStep = false;
      return {
        revoked: [],
        messages: [
          {
            inputId: 'msg-reject-1',
            conversationId: 'dm-owner',
            content: [{ type: 'text', text: unconsumedPending[0]?.text ?? 'rejected card' }],
          },
        ],
      };
    });
    client.rpc.handle('product.task_context.commit', () => ({ confirmed: [] }));
    client.rpc.handle('product.task_execution.snapshot', () => ({ agentId: 'pa', active: [] }));
    client.rpc.handle('product.task_execution.ack', () => null);
    client.rpc.handle('product.proactive.sync_observations', () => ({ synced_count: 0, unread_conversations: [] }));

    client.rpc.handle('product.call', async value => {
      const call = value as { method: string; args: Record<string, unknown> };
      if (call.method === 'memory.sources.refresh') {
        refreshArgsLog.push(call.args);
        await client!.rpc.request('knowledge.sources.sync', {
          agentId: 'pa',
          snapshot: { revision: '1', allowed: ['dm-owner'], excluded: [] },
        });
        return call.args.includePendingTaskContext === true
          ? { synchronized: true, pendingTaskContext: unconsumedPending }
          : { synchronized: true };
      }
      if (call.method === 'memory.conversations') {
        const cutoff = Number(call.args.cutoff);
        const afterTime = Number(call.args.afterTime);
        if (afterTime > cutoff) throw new Error(`Invalid cutoff window: afterTime ${afterTime} > cutoff ${cutoff}`);
        memoryConversationCutoffs.push({ cutoff, afterTime });
        return { messages: [{ id: 'msg-reject-1', content: '未采纳（已关闭）' }] };
      }
      return { status: 'ok' };
    });

    const binding = { sessionId: 'pa-root', agentId: 'pa', ownerId: 'owner', revision: '1', cwd: home };
    const paConfig = {
      agentId: 'pa',
      revision: '1',
      workspace: home,
      mode: 'global',
      provider: 'fixture',
      model: 'test',
      personal: { bindingId: 'b-pa', ownerId: 'owner', conversationId: 'dm-owner', epoch: 1 },
      skillRoots: [{ path: builtinSkillsPath, source: 'builtin' as const }],
      toolAllowlist: ['read', 'grep', 'conversations'],
      features: {
        intelligent_ui: false,
        task_graph: true,
        proactive_planning: true,
        cron_scheduling: true,
        dreaming: true,
        memory_curation: true,
        heartbeat: false,
      },
      approval: { ...approvalDefaults, globalRoot: home },
      knowledge: { memoryMode: 'document' as const },
    };

    await client.rpc.request('initialize', {
      protocol: 1,
      ownerTimezone: 'Asia/Shanghai',
      initialLogicalNowMs: day1Start,
      agents: [paConfig],
      bindings: [binding],
    });
    await client.rpc.request('session.ensure', binding);

    // Night 1 (03:05 Day 2): ZERO chat turns occurred on Day 1, only unconsumed pendingTaskContext!
    const night1 = Date.parse('2027-03-16T03:05:00+08:00');
    await client.rpc.request('runtime.clock.advance', { nowMs: night1, settle: true });

    const reviewsAfterNight1 = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviewsAfterNight1).toEqual([expect.objectContaining({ status: 'completed' })]);
    // One initial pre-fetch refresh with includePendingTaskContext: true, followed by two {} verifyCurrent checks (initial + 1 repair).
    expect(refreshArgsLog).toEqual([{ includePendingTaskContext: true }, {}, {}]);
    expect(memoryConversationCutoffs).toHaveLength(1);
    expect(memoryConversationCutoffs[0]!.cutoff).toBeGreaterThanOrEqual(clickTime);
    expect(await readFile(join(home, '.nanoassistant/memory/knowledge/proactivity-signals.md'), 'utf8')).toContain('seen: 1');
    expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('暂无已确认的主动性偏好。');

    // Day 2 daytime: PA foreground attempts to read/grep proactivity-signals.md -> blocked! Meanwhile msg-reject-1 is injected into pa-root via TaskContextDriver!
    unconsumedPending = [];
    injectOnNextStep = true;
    await client.rpc.request('session.submit', {
      sessionId: 'pa-root',
      inputId: 'day2-fg',
      mode: 'followup',
      content: [{ type: 'text', text: 'try-read-signals: 以后体脂和健身打卡都不要建任务卡了。' }],
      source: { kind: 'human', actorId: 'owner', channel: 'web', messageId: 'day2-fg' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'pa-root', inputId: 'day2-fg' }) as { terminal?: unknown }).terminal).toBeTruthy();

    const paObserved = await client.rpc.request('session.observe', { sessionId: 'pa-root' }) as { events: any[] };
    const fgReadSignals = paObserved.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'fg-0');
    const fgGrepSignals = paObserved.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'fg-1');
    const fgDirGrepMemory = paObserved.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'fg-2');
    const fgReadMemory = paObserved.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'fg-3');
    expect(fgReadSignals?.data.message.isError).toBe(true);
    expect(JSON.stringify(fgReadSignals?.data.message.content)).toContain('proactivity-signals.md is an offline Dreaming observation pool');
    expect(fgGrepSignals?.data.message.isError).toBe(true);
    expect(fgDirGrepMemory?.data.message.isError).not.toBe(true);
    expect(JSON.stringify(fgDirGrepMemory?.data.message.content)).not.toContain('proactivity-signals.md');
    expect(JSON.stringify(fgDirGrepMemory?.data.message.content)).not.toContain('seen: 1');
    expect(fgReadMemory?.data.message.isError).not.toBe(true);
    // Confirm msg-reject-1 was injected into pa-root session events on Day 2:
    expect(paObserved.events.some(e => e.type === 'user/message' && e.data.id === 'msg-reject-1' && e.data.source?.channel === 'task-context')).toBe(true);

    // Night 2 (03:05 Day 3): Dreaming runs! Verify msg-reject-1 is deduplicated (NOT in Main Agent trajectory) and <proactivity_signals> IS inlined!
    const night2 = Date.parse('2027-03-17T03:05:00+08:00');
    await client.rpc.request('runtime.clock.advance', { nowMs: night2, settle: true });
    const reviewsAfterNight2 = (await client.rpc.request('knowledge.facts', {}) as { reviews: { id: string; childSessionId: string; status: string }[] }).reviews;
    expect(reviewsAfterNight2).toHaveLength(2);
    expect(reviewsAfterNight2.every(r => r.status === 'completed')).toBe(true);
    const validMemoryAfterNight2 = await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8');
    expect(validMemoryAfterNight2).toContain('### 免打扰禁区');
    expect(validMemoryAfterNight2).toContain('体脂与健身打卡类事项不主动建立任务卡或提醒');

    const rawCalls = (await readFile(join(home, 'llm-calls.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const night2FirstCall = rawCalls.find(call => call.sessionId === reviewsAfterNight2[1]?.childSessionId);
    const night2InputText = JSON.stringify(night2FirstCall?.messages ?? []);
    expect(night2InputText).toContain('<proactivity_signals>');
    expect(night2InputText).toContain('seen: 1');
    expect(night2InputText).not.toContain('messageId: \\"msg-reject-1\\"');

    // Day 3 + Night 3: Trigger 3 failed consolidationIssues repair attempts -> verify Git rollback restores Night 2's valid MEMORY.md!
    await client.rpc.request('session.submit', {
      sessionId: 'pa-root',
      inputId: 'day3-msg',
      mode: 'followup',
      content: [{ type: 'text', text: 'Day 3 ordinary chat message for rollback verification.' }],
      source: { kind: 'human', actorId: 'owner', channel: 'web', messageId: 'day3-msg' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'pa-root', inputId: 'day3-msg' }) as { terminal?: unknown }).terminal).toBeTruthy();

    const night3 = Date.parse('2027-03-18T03:05:00+08:00');
    await client.rpc.request('runtime.clock.advance', { nowMs: night3, settle: true });
    const reviewsAfterNight3 = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string; summary?: string }[] }).reviews;
    expect(reviewsAfterNight3).toHaveLength(3);
    expect(reviewsAfterNight3.map(r => r.status)).toContain('failed');
    expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toBe(validMemoryAfterNight2);
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 45_000);
