import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, it } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const builtinSkillsPath = fileURLToPath(new URL('../../personal-assistant/assets/skills/', import.meta.url));

it('anchors Dreaming to 03:00 in ownerTimezone under TZ=UTC, gates proactive_nightly with <updated-formal-memory>, and drives logical-clock schedules with observation sync', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-proactive-clock-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'probe.mjs'), `import { appendFileSync } from 'node:fs';
export const name = 'proactive-clock-probe';
export const inject = ['llm'];
export function apply(ctx) {
  const dreamSteps = new Map();
  let nightlyStep = 0;
  ctx.on('llm/stream', async function* (o) {
    appendFileSync(process.env.DSH_HOME + '/llm-calls.jsonl', JSON.stringify({
      sessionId: o.sessionId,
      system: o.system,
      messages: o.messages,
    }) + '\\n');
    if (String(o.sessionId).startsWith('dreaming-')) {
      const n = dreamSteps.get(o.sessionId) || 0;
      dreamSteps.set(o.sessionId, n + 1);
      const all = o.messages.map(m => (m.content || []).filter(b => b.type === 'text').map(b => b.text).join('')).join('\\n');
      const stageMatch = all.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/);
      const stage = stageMatch ? stageMatch[1] : '';
      const calls = [
        ['read', { file_path: stage + '/MEMORY.md' }],
        ['write', {
          file_path: stage + '/MEMORY.md',
          content: '# MEMORY\\n\\n- Boundary: keep marathon training background-only; never propose task cards for it.\\n- Active Goal: Q4 Architecture Review.\\n',
        }],
        ['bash', {
          description: 'Commit nightly memory consolidation',
          command: 'git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m consolidation',
        }],
      ];
      const call = calls[n];
      if (call) {
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'dream-' + n, name: call[0], arguments: JSON.stringify(call[1]) } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Consolidated nightly memory.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    if (o.sessionId !== 'pa-root') {
      const lastMsg = JSON.stringify(o.messages.at(-1) ?? '');
      const blocked = lastMsg.includes('rm -rf');
      yield {
        type: 'block-end',
        index: 0,
        block: {
          type: 'text',
          text: JSON.stringify({
            outcome: blocked ? 'deny' : 'allow',
            risk_level: blocked ? 'high' : 'low',
            user_authorization: 'high',
            rationale: blocked ? 'Destructive shell command' : 'Safe proactive schedule',
          }),
        },
      };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    const hasNightlyWake = o.messages.some(m => JSON.stringify(m.content).includes('<proactive-nightly-wake local_time='));
    if (hasNightlyWake) {
      nightlyStep++;
      if (nightlyStep === 1) {
        yield {
          type: 'block-end',
          index: 0,
          block: {
            type: 'tool-call',
            id: 'nightly-sched-1',
            name: 'schedule_create',
            arguments: JSON.stringify({
              title: 'Morning brief',
              prompt: 'Deliver prepared Q4 architecture brief.',
              at: '2027-03-16T09:00:00+08:00',
            }),
          },
        };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      if (nightlyStep === 2) {
        yield {
          type: 'block-end',
          index: 0,
          block: {
            type: 'tool-call',
            id: 'nightly-bash-blocked',
            name: 'bash',
            arguments: JSON.stringify({
              command: 'rm -rf /tmp/never-run-this',
              description: 'Verify unattended denial does not hang',
            }),
          },
        };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      if (nightlyStep === 3) {
        yield {
          type: 'block-end',
          index: 0,
          block: {
            type: 'tool-call',
            id: 'nightly-notes-1',
            name: 'notes',
            arguments: JSON.stringify({
              content: '[Pending Morning Brief]\\n- Deliver Q4 architecture checkpoints at 09:00.',
            }),
          },
        };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Prepared morning brief silently.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Acknowledged.' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test', contextWindow: 128000 }] } } } },
      { insert: [{ id: 'proactive-clock-probe', name: join(home, 'probe.mjs') }] },
    ]);
    client = new RuntimeClient({
      home,
      cwd: home,
      env: { TZ: 'UTC', NANO_TEST_KEY: 'fixture' },
      onLog: text => { logs += text; },
    });
    registerNoopTaskHosts(client);
    client.rpc.handle('product.task_execution.ack', () => null);

    let syncCalls = 0;
    client.rpc.handle('product.proactive.sync_observations', async () => {
      syncCalls++;
      return {
        synced_count: 2,
        unread_conversations: [{ conversation_id: 'grp-q4', title: 'Q4 架构评审群', count: 2 }],
      };
    });
    client.rpc.handle('product.call', async value => {
      const call = value as { method: string; args: Record<string, unknown> };
      if (call.method === 'memory.sources.refresh') {
        await client!.rpc.request('knowledge.sources.sync', {
          agentId: 'pa',
          snapshot: { revision: '1', allowed: ['dm-owner'], excluded: [] },
        });
        return { refreshed: true };
      }
      if (call.method === 'schedule.history') {
        return client!.rpc.request('schedule.command', { agentId: 'pa', sessionId: 'pa-root', action: 'history', args: { id: String(call.args.id) } });
      }
      return { status: 'ok' };
    });

    const day1Afternoon = Date.parse('2027-03-15T14:00:00+08:00');
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

    // Daytime owner conversation at 14:00 +08:00 (06:00 UTC) with enough material for consolidation.
    await client.rpc.request('session.submit', {
      sessionId: 'pa-root',
      inputId: 'day1-msg',
      mode: 'followup',
      content: [{ type: 'text', text: 'Tomorrow we review the Q4 architecture; keep marathon notes background-only. '.repeat(180) }],
      source: { kind: 'human', actorId: 'owner', channel: 'web', messageId: 'day1-msg' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'pa-root', inputId: 'day1-msg' }) as { terminal?: unknown }).terminal).toBeTruthy();

    // Advancing 2 hours to 16:00 +08:00 on day 1 MUST NOT run automatic Dreaming during the daytime!
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-15T16:00:00+08:00'), settle: true });
    const factsAfternoon = await client.rpc.request('knowledge.facts', {}) as { reviews: { kind: string; status: string }[] };
    expect(factsAfternoon.reviews).toEqual([]);

    // Advance to 03:05 +08:00 (19:05 UTC previous UTC date!) -> Dreaming runs under Asia/Shanghai 03:00 anchor!
    const night305 = Date.parse('2027-03-16T03:05:00+08:00');
    await client.rpc.request('runtime.clock.advance', { nowMs: night305, settle: true });
    const factsAfterNight = await client.rpc.request('knowledge.facts', {}) as { reviews: { kind: string; status: string; endedAt?: number }[] };
    expect(factsAfterNight.reviews).toEqual([expect.objectContaining({ kind: 'dreaming', status: 'completed', endedAt: night305 })]);
    expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toContain('keep marathon training background-only');

    // Advancing later in the same natural day (e.g. 04:00 +08:00) must NOT run a second Dreaming cycle!
    await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-16T04:00:00+08:00'), settle: true });
    const factsSameNight = await client.rpc.request('knowledge.facts', {}) as { reviews: unknown[] };
    expect(factsSameNight.reviews).toHaveLength(1);

    // Submit proactive_nightly -> admitted because Dreaming completed for this 03:00 slot, inlines <updated-formal-memory>, creates 09:00 schedule & writes notes without hanging on unattended approval!
    const nightlySubmit = await client.rpc.request('session.submit', {
      sessionId: 'pa-root',
      inputId: 'nightly-1',
      mode: 'followup',
      onlyIfIdle: true,
      content: [{ type: 'text', text: '<proactive-nightly-wake local_time="2027-03-16T04:00:00+08:00" quiet_minutes="840" quiet_hours="true">\nguidance: test\n</proactive-nightly-wake>' }],
      source: { kind: 'system', actorId: 'pa', channel: 'proactive_nightly', messageId: 'nightly-1' },
    }) as { accepted: boolean };
    expect(nightlySubmit.accepted).toBe(true);
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'pa-root', inputId: 'nightly-1' }) as { terminal?: unknown }).terminal, { timeout: 10_000 }).toBeTruthy();

    const activeJobs = await client.rpc.request('schedule.command', { agentId: 'pa', action: 'jobs' }) as { id: string; enabled: boolean; name: string }[];
    expect(activeJobs).toHaveLength(1);
    expect(activeJobs[0]).toMatchObject({ enabled: true, name: 'Morning brief' });

    // Advance logical clock to 09:05 +08:00 -> fires the 09:00 one-shot schedule, awaits product.proactive.sync_observations, injects unread hint & persistent notes, and marks one-shot schedule inactive with receipt!
    const morning905 = Date.parse('2027-03-16T09:05:00+08:00');
    const clockResult = await client.rpc.request('runtime.clock.advance', { nowMs: morning905, settle: true }) as { nowMs: number };
    expect(clockResult.nowMs).toBe(morning905);
    expect(syncCalls).toBeGreaterThanOrEqual(1);

    const jobsAfterMorning = await client.rpc.request('schedule.command', { agentId: 'pa', action: 'jobs' }) as { id: string; enabled: boolean }[];
    expect(jobsAfterMorning[0]?.enabled).toBe(false);
    const history = await client.rpc.request('schedule.command', {
      agentId: 'pa',
      sessionId: 'pa-root',
      action: 'history',
      args: { id: activeJobs[0]!.id },
    }) as { records: { deliveredAt: string }[] };
    expect(history.records).toHaveLength(1);
    expect(history.records[0]?.deliveredAt).toBe(new Date(morning905).toISOString());

    const rawCalls = (await readFile(join(home, 'llm-calls.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const paCalls = rawCalls.filter(call => call.sessionId === 'pa-root');
    const nightlyCall = paCalls.find(call => JSON.stringify(call.messages).includes('<proactive-nightly-wake local_time='));
    expect(JSON.stringify(nightlyCall.messages)).toContain('<updated-formal-memory>');
    expect(JSON.stringify(nightlyCall.messages)).toContain('keep marathon training background-only');

    const morningCall = paCalls.at(-1);
    expect(JSON.stringify(morningCall.messages)).toContain('Fresh observation sync completed before this scheduled check');
    expect(JSON.stringify(morningCall.messages)).toContain('Q4 架构评审群');
    expect(JSON.stringify(morningCall.system) + JSON.stringify(morningCall.messages)).toContain('[Pending Morning Brief]');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);
