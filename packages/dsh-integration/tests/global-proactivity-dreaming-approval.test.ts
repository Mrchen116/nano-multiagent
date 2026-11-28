import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { allowsProactiveCareSkill } from '../src/capabilities.js';
import { MemoryDocuments } from '../src/knowledge/memory-documents.js';

const builtinSkillsPath = fileURLToPath(new URL('../../personal-assistant/assets/skills/', import.meta.url));
const fs = new LocalFileSystem(new Context(), { cwd: process.cwd(), diffBasisMaxBytes: 10485760 });

describe('Global Agent proactivity memory tiers, skill gating, and ROLE.md approval evidence', () => {
  it('separates global_expert and single_thread_expert formal memory rules and gates nano-proactive-care by effective proactive_planning', async () => {
    const dirSingle = await mkdtemp(join(tmpdir(), 'nano-mem-single-'));
    const dirGlobal = await mkdtemp(join(tmpdir(), 'nano-mem-global-'));
    let singleDocs: MemoryDocuments | undefined;
    let globalDocs: MemoryDocuments | undefined;
    try {
      singleDocs = await MemoryDocuments.open(dirSingle, 'single_thread_expert', fs);
      expect(await readFile(join(singleDocs.root, 'MEMORY.md'), 'utf8')).not.toContain('## 主动性与介入偏好');
      expect(await singleDocs.consolidationIssues()).toEqual([]);

      await mkdir(join(singleDocs.root, 'knowledge'), { recursive: true });
      await writeFile(join(singleDocs.root, 'knowledge', 'proactivity-signals.md'), '# Signals\n- item\n', 'utf8');
      expect(await singleDocs.consolidationIssues()).toEqual([
        expect.objectContaining({
          path: 'knowledge/proactivity-signals.md',
          reason: expect.stringContaining('only supported for personal assistant and global expert'),
        }),
      ]);

      globalDocs = await MemoryDocuments.open(dirGlobal, 'global_expert', fs);
      expect(await readFile(join(globalDocs.root, 'MEMORY.md'), 'utf8')).toContain('## 主动性与介入偏好');
      expect(await globalDocs.consolidationIssues()).toEqual([]);

      await mkdir(join(globalDocs.root, 'entities'), { recursive: true });
      await writeFile(join(globalDocs.root, 'entities', 'bob.md'), '# Bob\n\nPrefers concise bullet summaries.\n', 'utf8');
      await writeFile(
        join(globalDocs.root, 'MEMORY.md'),
        [
          '# Expert memory',
          '',
          '## 主动性与介入偏好',
          '### 免打扰禁区',
          '- 与 Bob 私聊中的临时脚本排查不主动建待拍板卡（协作偏好见 [Bob](entities/bob.md)）。',
          '',
          '## Topics',
          '',
          'No topics saved yet.',
          '',
        ].join('\n'),
        'utf8',
      );
      expect(await globalDocs.consolidationIssues()).toEqual([]);

      const baseGlobal = { agentId: 'q', revision: '1', workspace: dirGlobal, mode: 'global' as const, provider: 'fixture', model: 'test' };
      expect(allowsProactiveCareSkill(baseGlobal, false)).toBe(true);
      expect(allowsProactiveCareSkill(baseGlobal, true)).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, mode: 'single_thread' }, false)).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, features: { task_graph: true, proactive_planning: false } }, false)).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, features: { task_graph: false } }, false)).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, toolAllowlist: ['read'] }, false)).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, toolAllowlist: ['task_graph'], skillSelection: { mode: 'explicit_allowlist', names: ['other'] } }, false)).toBe(true);
      expect(
        allowsProactiveCareSkill(
          { ...baseGlobal, toolAllowlist: ['task_graph'], features: { task_graph: true, proactive_planning: true }, skillSelection: { mode: 'explicit_allowlist', names: ['other'] } },
          false,
        ),
      ).toBe(false);
      expect(allowsProactiveCareSkill({ ...baseGlobal, toolAllowlist: ['task_graph'], skillSelection: { mode: 'explicit_denylist', names: ['nano-proactive-care'] } }, false)).toBe(false);
    } finally {
      await singleDocs?.close();
      await globalDocs?.close();
      await rm(dirSingle, { recursive: true, force: true });
      await rm(dirGlobal, { recursive: true, force: true });
    }
  });

  it('runs stateless pendingTaskContext Dreaming for global_expert without sourcesPending deadlock, supplies ROLE.md to NanoApproval, and keeps single_thread_expert Dreaming clean', async () => {
    const home = await mkdtemp(join(tmpdir(), 'nano-global-proactivity-rt-'));
    const wsGlobal = join(home, 'ws-global');
    const wsSingle = join(home, 'ws-single');
    await mkdir(join(wsGlobal, '.nanoassistant'), { recursive: true });
    await mkdir(join(wsSingle, '.nanoassistant'), { recursive: true });
    await writeFile(
      join(wsGlobal, '.nanoassistant', 'ROLE.md'),
      '你是研发团队发版质量负责人，负责监控 #研发群 (c_rdgrp1) 构建回归异常并挂 proposed 待拍板卡。',
      'utf8',
    );
    let client: RuntimeClient | undefined;
    let logs = '';

    try {
      const signalsPathJson = JSON.stringify(join(wsGlobal, '.nanoassistant', 'memory', 'knowledge', 'proactivity-signals.md'));
      await writeFile(
        join(home, 'probe.mjs'),
        `import { appendFileSync } from 'node:fs';
export const name = 'global-proactivity-probe';
export const inject = ['llm'];
export function apply(ctx) {
  const steps = new Map();
  ctx.on('llm/stream', async function* (o) {
    const sessionId = String(o.sessionId || '');
    const msgText = JSON.stringify(o.messages || []);
    appendFileSync(process.env.DSH_HOME + '/calls.jsonl', JSON.stringify({ sessionId, msgText }) + '\\n');
    const step = steps.get(sessionId) || 0;
    steps.set(sessionId, step + 1);

    if (sessionId.startsWith('dreaming-')) {
      const all = (o.messages || []).map(m => (m.content || []).filter(b => b.type === 'text').map(b => b.text).join('')).join('\\n');
      const stageMatch = all.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/);
      if (stageMatch) {
        const stage = stageMatch[1];
        const isGlobal = all.includes('<bound_administrator>');
        const calls = isGlobal
          ? [
              ['write', { file_path: stage + '/entities/bob.md', content: '# Bob\\n\\n临时脚本问题习惯直接给命令行排查步骤。\\n' }],
              ['write', { file_path: stage + '/knowledge/proactivity-signals.md', content: '# 主动性隐式信号观察池\\n\\n- **Bob 1v1 临时脚本跟进卡**（seen: 1，2027-03-16，未采纳待拍板卡 msg-bob-1）\\n' }],
              ['read', { file_path: stage + '/MEMORY.md' }],
              ['write', { file_path: stage + '/MEMORY.md', content: '# Expert memory\\n\\n## 主动性与介入偏好\\n\\n### 积极盯紧与提前备料\\n- 发版回归异常主动在 #研发群 挂待拍板卡（协作约定见 [Bob](entities/bob.md)）。\\n\\n## Topics\\n\\nNo topics saved yet.\\n' }],
              ['bash', { description: 'Commit global expert memory', command: 'git add -- MEMORY.md entities knowledge && git -c user.name=Nano -c user.email=memory@localhost commit -m global-dream' }],
            ]
          : [
              ['read', { file_path: stage + '/MEMORY.md' }],
              ['write', { file_path: stage + '/MEMORY.md', content: '# Expert memory\\n\\n## Topics\\n\\n- Single-thread troubleshooting note.\\n' }],
              ['bash', { description: 'Commit single_thread_expert memory', command: 'git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m single-dream' }],
            ];
        const call = calls[step];
        if (call) {
          yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'dr-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
          yield { type: 'finish', reason: { kind: 'tool-calls' } };
          return;
        }
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Dreaming complete.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    if (sessionId === 'q-root') {
      const lastText = ((o.messages || []).findLast(m => m.role === 'user')?.content || []).map(b => b.text || '').join('');
      if (lastText.includes('<proactive-nightly-wake') && step === 1) {
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'q-read-sig', name: 'read', arguments: JSON.stringify({ file_path: ${signalsPathJson} }) } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      if (lastText.includes('<proactive-nightly-wake') && step === 2) {
        yield {
          type: 'block-end',
          index: 0,
          block: {
            type: 'tool-call',
            id: 'q-propose-card',
            name: 'task_graph',
            arguments: JSON.stringify({ action: 'create', target: 'c_rdgrp1', title: '修复夜间冒烟回归失败', status: 'proposed', proposed_for_user_id: 'u_alice1', request_key: 'role-duty-1' }),
          },
        };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
        return;
      }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Silent nightly check complete.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    if (sessionId === 's-root') {
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Single thread reply.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }

    yield { type: 'block-end', index: 0, block: { type: 'text', text: JSON.stringify({ outcome: 'allow', risk_level: 'low', user_authorization: 'high', rationale: 'Authorized by standing ROLE.md agreement' }) } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`,
        'utf8',
      );

      await prepareProfile(home, [
        { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test', contextWindow: 128000 }] } } } },
        { insert: [{ id: 'global-proactivity-probe', name: join(home, 'probe.mjs') }] },
      ]);

      client = new RuntimeClient({ home, cwd: home, env: { TZ: 'UTC', NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });

      const wsGlobalReal = await realpath(wsGlobal);
      const wsSingleReal = await realpath(wsSingle);
      const taskGraphCalls: Record<string, unknown>[] = [];
      client.rpc.handle('knowledge.role.workspace', value => ({
        workspace: (value as { agentId: string }).agentId === 'q' ? wsGlobalReal : wsSingleReal,
      }));
      client.rpc.handle('product.task_context.prepare', () => ({ messages: [], revoked: [] }));
      client.rpc.handle('product.task_context.commit', () => ({ confirmed: [] }));
      client.rpc.handle('product.task_execution.snapshot', () => ({ agentId: 'q', active: [] }));
      client.rpc.handle('product.task_execution.ack', () => null);
      client.rpc.handle('product.proactive.sync_observations', () => ({ synced_count: 0, unread_conversations: [] }));
      client.rpc.handle('product.call', async value => {
        const call = value as { agentId: string; method: string; args: Record<string, unknown> };
        if (call.method === 'memory.sources.refresh') {
          if (call.agentId === 'q' && call.args.includePendingTaskContext === true) {
            return {
              synchronized: true,
              pendingTaskContext: [{
                messageId: 'msg-bob-1',
                conversationId: 'conv-raw-bob-dm-0001',
                conversationRef: 'c_bobdm1',
                timeMs: Date.parse('2027-03-15T16:00:00+08:00'),
                text: 'Task update from its fixed conversation.\n{"kind":"task_graph","conversation_id":"c_bobdm1","previous_status":"proposed","status":"closed","actor":{"type":"user","id":"u_bob001"}}',
              }],
            };
          }
          return { synchronized: true };
        }
        if (call.method === 'memory.conversations') return { messages: [{ id: 'msg-bob-1', content: 'closed proposed card' }] };
        if (call.method === 'task_graph') {
          taskGraphCalls.push(call.args);
          return { ok: true, result: { graph_id: 'tg_rd1', node_id: 'n1' } };
        }
        return { status: 'ok' };
      });

      const qBinding = { sessionId: 'q-root', agentId: 'q', ownerId: 'u_admin1', revision: '1', cwd: wsGlobal };
      const sBinding = { sessionId: 's-root', agentId: 's', ownerId: 'u_admin1', revision: '1', cwd: wsSingle, conversationId: 'conv-single' };
      const qConfig = {
        agentId: 'q', revision: '1', workspace: wsGlobal, mode: 'global' as const, provider: 'fixture', model: 'test',
        skillRoots: [{ path: builtinSkillsPath, source: 'builtin' as const }],
        toolAllowlist: ['read', 'grep', 'conversations', 'task_graph', 'skill'],
        features: { intelligent_ui: false, task_graph: true, proactive_planning: true, cron_scheduling: true, dreaming: true, memory_curation: true, heartbeat: false },
        approval: { ...approvalDefaults, globalRoot: home },
        knowledge: { memoryMode: 'document' as const },
      };
      const sConfig = {
        agentId: 's', revision: '1', workspace: wsSingle, mode: 'single_thread' as const, provider: 'fixture', model: 'test',
        skillRoots: [{ path: builtinSkillsPath, source: 'builtin' as const }],
        toolAllowlist: ['read', 'conversations', 'task_graph', 'skill'],
        features: { intelligent_ui: false, task_graph: true, cron_scheduling: false, dreaming: true, memory_curation: true, heartbeat: false },
        approval: { ...approvalDefaults, globalRoot: home },
        knowledge: { memoryMode: 'document' as const },
      };

      await client.rpc.request('initialize', {
        protocol: 1,
        ownerTimezone: 'Asia/Shanghai',
        initialLogicalNowMs: Date.parse('2027-03-15T11:00:00+08:00'),
        agents: [qConfig, sConfig],
        bindings: [qBinding, sBinding],
      });
      await client.rpc.request('session.ensure', qBinding);
      await client.rpc.request('session.ensure', sBinding);

      // Establish the window's model-visible memory snapshot before Dreaming updates it.
      await client.rpc.request('session.submit', {
        sessionId: 'q-root', inputId: 'q-initial', mode: 'followup',
        content: [{ type: 'text', text: 'Check the current release notes.' }],
        source: { kind: 'human', actorId: 'u_admin1', channel: 'web', messageId: 'q-initial' },
      });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'q-root', inputId: 'q-initial' }) as { terminal?: unknown }).terminal).toBeTruthy();

      const qCapsBefore = await client.rpc.request('session.capabilities', { sessionId: 'q-root' }) as { prompt: unknown };
      const sCaps = await client.rpc.request('session.capabilities', { sessionId: 's-root' }) as { prompt: unknown };
      expect(JSON.stringify(qCapsBefore.prompt)).toContain('nano-proactive-care');
      expect(JSON.stringify(sCaps.prompt)).not.toContain('nano-proactive-care');

      await client.rpc.request('session.submit', {
        sessionId: 's-root', inputId: 's-msg-1', mode: 'followup',
        content: [{ type: 'text', text: 'Check single-thread note.' }],
        source: { kind: 'human', actorId: 'u_admin1', channel: 'web', messageId: 's-msg-1' },
      });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 's-root', inputId: 's-msg-1' }) as { terminal?: unknown }).terminal).toBeTruthy();

      await client.rpc.request('runtime.clock.advance', { nowMs: Date.parse('2027-03-16T03:05:00+08:00'), settle: true });
      const facts = await client.rpc.request('knowledge.facts', {}) as { reviews: { agentId: string; status: string }[] };
      expect(facts.reviews.filter(r => r.status === 'completed').map(r => r.agentId).sort()).toEqual(['q', 's']);

      await client.rpc.request('session.submit', {
        sessionId: 'q-root', inputId: 'q-nightly-1', onlyIfIdle: true, mode: 'followup',
        content: [{ type: 'text', text: '<proactive-nightly-wake local_time="2027-03-16T03:20:00+08:00" quiet_minutes="45" quiet_hours="true">\nguidance: nightly\n</proactive-nightly-wake>' }],
        source: { kind: 'system', actorId: 'u_admin1', channel: 'proactive_nightly', messageId: 'q-nightly-1' },
      });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'q-root', inputId: 'q-nightly-1' }) as { terminal?: unknown }).terminal).toBeTruthy();

      expect(taskGraphCalls).toEqual([expect.objectContaining({ action: 'create', target: 'c_rdgrp1', status: 'proposed', proposed_for_user_id: 'u_alice1' })]);

      const qObserved = await client.rpc.request('session.observe', { sessionId: 'q-root' }) as { events: any[] };
      const sigReadResult = qObserved.events.find(e => e.type === 'tool/result' && e.data.message.toolCallId === 'q-read-sig');
      expect(sigReadResult?.data.message.isError).toBe(true);
      expect(JSON.stringify(sigReadResult?.data.message.content)).toContain('proactivity-signals.md is an offline Dreaming observation pool');

      const qCapsAfter = await client.rpc.request('session.capabilities', { sessionId: 'q-root' }) as { prompt: unknown };
      expect(JSON.stringify(qCapsAfter.prompt)).toBe(JSON.stringify(qCapsBefore.prompt));

      const allCalls = (await readFile(join(home, 'calls.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      expect(allCalls.find(c => c.sessionId === 'q-root' && c.msgText.includes('q-nightly-1'))?.msgText).toContain('<updated-formal-memory');

      const globalDreamCall = allCalls.find(c => c.sessionId.startsWith('dreaming-') && c.msgText.includes('<bound_administrator>'));
      expect(globalDreamCall?.msgText).toContain('<bound_administrator>u_admin1</bound_administrator>');
      expect(globalDreamCall?.msgText).toContain('conversationId: c_bobdm1');
      expect(globalDreamCall?.msgText).not.toContain('conv-raw-bob-dm-0001');

      const approvalCall = allCalls.find(c => !c.sessionId.startsWith('dreaming-') && c.sessionId !== 'q-root' && c.sessionId !== 's-root');
      expect(approvalCall?.msgText).toContain('.nanoassistant/ROLE.md');
      expect(approvalCall?.msgText).toContain('role_agreement');
      expect(approvalCall?.msgText).toContain('发版质量负责人');
    } catch (error) {
      throw new Error(`${String(error)}\n${logs}`, { cause: error });
    } finally {
      await client?.shutdown();
      await rm(home, { recursive: true, force: true });
    }
  }, 45_000);
});
