import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const builtinSkillsPath = fileURLToPath(new URL('../../personal-assistant/assets/skills/', import.meta.url));

it('deduplicates <updated-formal-memory> and <proactive-policy> within a window and enforces Dreaming minSourceTokens, agent-task non-bypass, maxDeferDays, and silent-vacation cycle advancement', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-memory-capacity-gating-'));
  let client: RuntimeClient | undefined;
  let logs = '';

  try {
    await writeFile(join(home, 'probe.mjs'), `import { appendFileSync } from 'node:fs';
export const name = 'capacity-gating-probe';
export const inject = ['llm'];
export function apply(ctx) {
  const dreamSteps = new Map();
  let dreamRunCount = 0;
  const runNoBySession = new Map();

  ctx.on('llm/stream', async function* (o) {
    appendFileSync(process.env.DSH_HOME + '/llm-calls.jsonl', JSON.stringify({
      sessionId: o.sessionId,
      system: o.system,
      messages: o.messages,
    }) + '\\n');

    if (String(o.sessionId).startsWith('dreaming-')) {
      if (!runNoBySession.has(o.sessionId)) {
        dreamRunCount++;
        runNoBySession.set(o.sessionId, dreamRunCount);
      }
      const runNo = runNoBySession.get(o.sessionId);
      const step = dreamSteps.get(o.sessionId) || 0;
      dreamSteps.set(o.sessionId, step + 1);
      const all = o.messages.map(m => (m.content || []).filter(b => b.type === 'text').map(b => b.text).join('')).join('\\n');
      const stage = all.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/)[1];

      if (runNo === 1) {
        // Night 1 (initial seed bypass): First attempt violates 2,000-char proactive section cap -> repair splits playbook into knowledge/proactivity-policy.md!
        const oversizedProactive = '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n### 积极盯紧与提前备料\\n- ' + '细则'.repeat(1050) + '\\n\\n## Topics\\n\\n- Owner: 林默（偏好简洁结论先行）。\\n';
        const validEntry = '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n### 积极盯紧与提前备料\\n- 跨天待办与晨报巡检（详见 [主动策略细则](knowledge/proactivity-policy.md)）。\\n\\n### 触达时机与汇总方式\\n- 22:00–08:30 静默，09:00 合并晨报。\\n\\n## Topics\\n\\n- Owner: 林默（偏好简洁结论先行）。\\n';
        const policyDoc = '# 主动策略细则\\n\\n- 晨报合并待拍板卡与当日最高优事项，单条不超过 5 点。\\n';
        const calls = [
          ['read', { file_path: stage + '/MEMORY.md' }],
          ['write', { file_path: stage + '/MEMORY.md', content: oversizedProactive }],
          ['bash', {
            description: 'Commit oversized proactive section to verify <= 2000 repair gate',
            command: 'git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m oversized-proactive',
          }],
          undefined, // Trigger host consolidationIssues repair attempt 1 of 3
          ['write', { file_path: stage + '/knowledge/proactivity-policy.md', content: policyDoc }],
          ['write', { file_path: stage + '/MEMORY.md', content: validEntry }],
          ['bash', {
            description: 'Commit split MEMORY.md and proactivity-policy.md',
            command: 'git add -- MEMORY.md knowledge/proactivity-policy.md && git -c user.name=Nano -c user.email=memory@localhost commit -m split-proactive-policy',
          }],
        ];
        const call = calls[step];
        if (call) {
          yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'dr1-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
          yield { type: 'finish', reason: { kind: 'tool-calls' } };
          return;
        }
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Night 1 initial seed consolidated with policy split.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
        return;
      }

      // Run 2 (maxDeferDays flush) & Run 3 (human task-context bypass): update MEMORY.md cleanly
      const calls = [
        ['read', { file_path: stage + '/MEMORY.md' }],
        ['write', {
          file_path: stage + '/MEMORY.md',
          content: '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n### 积极盯紧与提前备料\\n- 跨天待办与晨报巡检（详见 [主动策略细则](knowledge/proactivity-policy.md)）。\\n\\n### 触达时机与汇总方式\\n- 22:00–08:30 静默，09:00 合并晨报。\\n\\n## Topics\\n\\n- Owner: 林默（偏好简洁结论先行；批次 #' + runNo + ' 已合入）。\\n',
        }],
        ['bash', {
          description: 'Commit consolidated update',
          command: 'git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m run-' + runNo,
        }],
      ];
      const call = calls[step];
      if (call) {
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'drN-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Consolidated run ' + runNo } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'OK.' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);

    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test', contextWindow: 128000 }] } } } },
      { insert: [{ id: 'capacity-gating-probe', name: join(home, 'probe.mjs') }] },
    ]);

    client = new RuntimeClient({
      home,
      cwd: home,
      env: { TZ: 'UTC', NANO_TEST_KEY: 'fixture' },
      onLog: text => { logs += text; },
    });

    registerNoopTaskHosts(client);
    client.rpc.handle('product.task_execution.ack', () => null);
    client.rpc.handle('product.proactive.sync_observations', () => ({ synced_count: 0, unread_conversations: [] }));

    let unconsumedPending: Array<{ messageId: string; conversationId: string; timeMs: number; text: string }> = [];
    client.rpc.handle('product.call', async value => {
      const call = value as { method: string; args: Record<string, unknown> };
      if (call.method === 'memory.sources.refresh') {
        await client!.rpc.request('knowledge.sources.sync', {
          agentId: 'pa',
          snapshot: { revision: '1', allowed: ['dm-owner'], excluded: [] },
        });
        return call.args.includePendingTaskContext === true
          ? { synchronized: true, pendingTaskContext: unconsumedPending }
          : { synchronized: true };
      }
      return { status: 'ok' };
    });

    const day1Afternoon = Date.parse('2027-03-15T15:00:00+08:00');
    const binding = { sessionId: 'pa-root', agentId: 'pa', ownerId: 'owner', revision: '1', cwd: home };
    const paConfig = {
      agentId: 'pa',
      revision: '1',
      workspace: home,
      mode: 'global' as const,
      provider: 'fixture',
      model: 'test',
      personal: { bindingId: 'b-pa', ownerId: 'owner', conversationId: 'dm-owner', epoch: 1 },
      skillRoots: [{ path: builtinSkillsPath, source: 'builtin' as const }],
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
      initialLogicalNowMs: day1Afternoon,
      agents: [paConfig],
      bindings: [binding],
    });
    await client.rpc.request('session.ensure', binding);

    const submitTurn = async (id: string, text: string, channel: 'web' | 'proactive_review' | 'proactive_nightly') => {
      const res = await client!.rpc.request('session.submit', {
        sessionId: 'pa-root',
        inputId: id,
        mode: 'followup',
        ...(channel === 'web' ? {} : { onlyIfIdle: true }),
        content: [{ type: 'text', text }],
        source: channel === 'web'
          ? { kind: 'human', actorId: 'owner', channel: 'web', messageId: id }
          : { kind: 'system', actorId: 'pa', channel, messageId: id },
      }) as { accepted: boolean; busy?: boolean };
      expect(res.accepted).toBe(true);
      await expect.poll(
        async () => (await client!.rpc.request('session.lookup', { sessionId: 'pa-root', inputId: id }) as { terminal?: unknown }).terminal,
        { timeout: 10_000 },
      ).toBeTruthy();
    };

    // 1. First turn of a fresh window as proactive_review must not duplicate initial MEMORY.md snapshot (F2),
    // and Day 1 short onboarding turn (< 600 tokens) -> Night 1 (2027-03-16 03:05) bypasses minSourceTokens because MEMORY.md is still initial seed!
    const initialSeedEntry = await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8');
    await submitTurn('day1-first-wake', '<proactive-review-wake local_time="2027-03-15T15:01:00+08:00" quiet_minutes="15" quiet_hours="false">\nguidance: initial wake\n</proactive-review-wake>', 'proactive_review');
    await submitTurn('day1-short', '我是林默，以后汇报结论先行。', 'web');
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-16T03:05:00+08:00'), settle: true });
    let reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(1);
    expect(reviews[0]?.status).toBe('completed');
    expect(await readFile(join(home, '.nanoassistant/memory/knowledge/proactivity-policy.md'), 'utf8')).toContain('晨报合并待拍板卡');

    // 2. Night 1 proactive_nightly receives <updated-formal-memory> AND <proactive-policy> once.
    await submitTurn('night1-wake', '<proactive-nightly-wake local_time="2027-03-16T03:25:00+08:00" quiet_minutes="745" quiet_hours="true">\nguidance: nightly\n</proactive-nightly-wake>', 'proactive_nightly');

    // 3. Day 2 daytime: short chat (< 600 tokens) + proactive_review wakes in the SAME window -> zero duplicate tags, prefix unchanged, and withdrawal/revert supersedes once (F1)!
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-16T10:00:00+08:00'), settle: true });
    await submitTurn('day2-short', '收到，下午还有个短会。', 'web');
    await submitTurn('day2-review-1', '<proactive-review-wake local_time="2027-03-16T10:15:00+08:00" quiet_minutes="15" quiet_hours="false">\nguidance: review 1\n</proactive-review-wake>', 'proactive_review');

    const memRoot = join(home, '.nanoassistant/memory');
    const night1Entry = await readFile(join(memRoot, 'MEMORY.md'), 'utf8');
    await writeFile(join(memRoot, 'knowledge/proactivity-policy.md'), '# 主动策略细则\n\n- 晨报合并待拍板卡与当日最高优事项，单条不超过 3 点。\n');
    execFileSync('git', ['add', '--', 'knowledge/proactivity-policy.md'], { cwd: memRoot });
    execFileSync('git', ['-c', 'user.name=Nano', '-c', 'user.email=memory@localhost', 'commit', '-qm', 'update-policy'], { cwd: memRoot });

    await submitTurn('day2-review-2', '<proactive-review-wake local_time="2027-03-16T10:30:00+08:00" quiet_minutes="30" quiet_hours="false">\nguidance: review 2\n</proactive-review-wake>', 'proactive_review');
    await submitTurn('day2-review-3', '<proactive-review-wake local_time="2027-03-16T10:45:00+08:00" quiet_minutes="45" quiet_hours="false">\nguidance: review 3\n</proactive-review-wake>', 'proactive_review');

    // Simulate reverting MEMORY.md to window-initial M0 and deleting proactivity-policy.md inside the SAME window (F1):
    await rm(join(memRoot, 'knowledge/proactivity-policy.md'));
    await writeFile(join(memRoot, 'MEMORY.md'), initialSeedEntry);
    execFileSync('git', ['add', '-A'], { cwd: memRoot });
    execFileSync('git', ['-c', 'user.name=Nano', '-c', 'user.email=memory@localhost', 'commit', '-qm', 'revert-entry-and-delete-policy'], { cwd: memRoot });
    await submitTurn('day2-review-4', '<proactive-review-wake local_time="2027-03-16T11:00:00+08:00" quiet_minutes="60" quiet_hours="false">\nguidance: review 4\n</proactive-review-wake>', 'proactive_review');
    await submitTurn('day2-review-5', '<proactive-review-wake local_time="2027-03-16T11:15:00+08:00" quiet_minutes="75" quiet_hours="false">\nguidance: review 5\n</proactive-review-wake>', 'proactive_review');

    // Restore non-seed MEMORY.md and policy before Night 2 so Night 2 tests non-seed minSourceTokens deferral!
    await writeFile(join(memRoot, 'MEMORY.md'), night1Entry);
    await writeFile(join(memRoot, 'knowledge/proactivity-policy.md'), '# 主动策略细则\n\n- 晨报合并待拍板卡与当日最高优事项，单条不超过 3 点。\n');
    execFileSync('git', ['add', '-A'], { cwd: memRoot });
    execFileSync('git', ['-c', 'user.name=Nano', '-c', 'user.email=memory@localhost', 'commit', '-qm', 'restore-post-f1-check'], { cwd: memRoot });

    const rootCalls = (await readFile(join(home, 'llm-calls.jsonl'), 'utf8'))
      .trim()
      .split('\n')
      .map(line => JSON.parse(line))
      .filter(call => call.sessionId === 'pa-root');
    // Prefix invariance: system prompt + messages[0] (initial runtime-context snapshot) are byte-identical across all pa-root turns!
    const firstSystem = JSON.stringify(rootCalls[0]!.system);
    const firstSnapshot = JSON.stringify(rootCalls[0]!.messages[0]);
    for (const call of rootCalls) {
      expect(JSON.stringify(call.system)).toBe(firstSystem);
      expect(JSON.stringify(call.messages[0])).toBe(firstSnapshot);
    }
    const lastMessages = rootCalls.at(-1)!.messages as Array<{ id?: string; content: Array<{ type: string; text?: string }> }>;
    const textOf = (id: string) => lastMessages.find(m => m.id === id)?.content.map(b => b.text ?? '').join('\n') ?? '';
    expect(textOf('day1-first-wake')).not.toContain('<updated-formal-memory');
    expect(textOf('day1-first-wake')).not.toContain('<proactive-policy>');
    expect(textOf('night1-wake')).toContain('<updated-formal-memory complete="true">');
    expect(textOf('night1-wake')).toContain('<proactive-policy>');
    expect(textOf('day2-review-1')).not.toContain('<updated-formal-memory');
    expect(textOf('day2-review-1')).not.toContain('<proactive-policy>');
    expect(textOf('day2-review-2')).not.toContain('<updated-formal-memory');
    expect(textOf('day2-review-2')).toContain('单条不超过 3 点');
    expect(textOf('day2-review-3')).not.toContain('<proactive-policy>');
    expect(textOf('day2-review-4')).toContain('No topics saved yet.');
    expect(textOf('day2-review-4')).toContain('<proactive-policy>\n(none)\n</proactive-policy>');
    expect(textOf('day2-review-5')).not.toContain('<updated-formal-memory');
    expect(textOf('day2-review-5')).not.toContain('<proactive-policy>');

    // 4. Night 2 (2027-03-17 03:05) + Agent-authored task-context (actor.type === "agent"): MUST NOT bypass minSourceTokens!
    unconsumedPending = [{
      messageId: 'msg-agent-self-1',
      conversationId: 'dm-owner',
      timeMs: Date.parse('2027-03-16T10:16:00+08:00'),
      text: 'Task update from its fixed conversation.\n{"kind":"task_graph","status":"proposed","actor":{"type":"agent","id":"pa"},"content":"PA created candidate card"}',
    }];
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-17T03:05:00+08:00'), settle: true });
    reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(1); // Deferred! Zero Dreaming runs on Night 2!

    // Verify Night 2 proactive_nightly IS unblocked immediately because deferred_below_min_volume advanced lastCompletedCycle!
    await submitTurn('night2-wake', '<proactive-nightly-wake local_time="2027-03-17T03:25:00+08:00" quiet_minutes="1000" quiet_hours="true">\nguidance: night 2\n</proactive-nightly-wake>', 'proactive_nightly');

    // 5. Night 3 (2027-03-18 03:05, daysBetween=2 < 3): still defers!
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-18T03:05:00+08:00'), settle: true });
    reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(1);

    // 6. Night 4 (2027-03-19 03:05, daysBetween=3 >= maxDeferDays=3): flushes accumulated short chat automatically!
    unconsumedPending = [];
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-19T03:05:00+08:00'), settle: true });
    reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(2);
    expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('批次 #2 已合入');

    // 7. Four completely silent days (2027-03-20 .. 2027-03-23) advance lastConsolidatedCycle on no_eligible_increment,
    // so a single short greeting on 2027-03-23 afternoon STILL defers on 2027-03-24 03:05!
    for (const day of ['2027-03-20', '2027-03-21', '2027-03-22', '2027-03-23']) {
      await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse(`${day}T03:05:00+08:00`), settle: true });
    }
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-23T14:00:00+08:00'), settle: true });
    await submitTurn('post-vacation-hi', '早！', 'web');
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-24T03:05:00+08:00'), settle: true });
    reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(2); // Deferred cleanly instead of firing onstale lastConsolidatedCycle!

    // 8. Human task-context click (actor.type === "user") bypasses minSourceTokens immediately on the next night!
    unconsumedPending = [{
      messageId: 'msg-human-approve-1',
      conversationId: 'dm-owner',
      timeMs: Date.parse('2027-03-24T16:00:00+08:00'),
      text: 'Task update from its fixed conversation.\n{"kind":"task_graph","previous_status":"proposed","status":"todo","actor":{"type":"user","id":"owner"},"content":"Owner approved card"}',
    }];
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-25T03:05:00+08:00'), settle: true });
    reviews = (await client.rpc.request('knowledge.facts', {}) as { reviews: { status: string }[] }).reviews;
    expect(reviews).toHaveLength(3);
    expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('批次 #3 已合入');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);
