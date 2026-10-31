import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each(['unread-write', 'failed-read-write', 'normal-stop', 'missing-index', 'model-error', 'cancelled'])(
  'accepts only valid normally completed staging after %s', async mode => {
    const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
    const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-incomplete-'));
    let client: InstanceType<typeof RuntimeClient> | undefined;
    await writeFile(join(home, 'fixture.mjs'), `
import { appendFileSync } from 'node:fs';
export const name = 'incomplete-fixture';
export const inject = ['llm', 'agents'];
export function apply(ctx) {
  const steps = new Map();
  ctx.on('llm/stream', async function* (request) {
    appendFileSync(process.env.DSH_HOME + '/requests.jsonl', JSON.stringify(request) + '\\n');
    const step = steps.get(request.sessionId) || 0;
    steps.set(request.sessionId, step + 1);
    let call;
    if (request.sessionId.startsWith('dreaming-')) {
      const text = request.messages.flatMap(m => m.content || []).filter(b => b.type === 'text').map(b => b.text).join('\\n');
      const stage = text.match(/Editable copy: (.+?)\\. Only edit/)[1];
      const write = ['write', { file_path: stage + '/MEMORY.md', content: 'Unsupported overwrite' }];
      const mode = ${JSON.stringify(mode)};
      if (step === 2 && ['model-error', 'cancelled'].includes(mode)) {
        if (mode === 'cancelled') ctx.agents.get(request.sessionId).cancel({kind:'hook',reason:'Fixture cancellation'});
        throw new Error('Fixture model failure');
      }
      const calls = ${JSON.stringify(mode)} === 'unread-write' ? [write]
        : mode === 'failed-read-write' ? [['read', { file_path: stage + '/missing.md' }], write]
        : mode === 'missing-index' ? [['write', {file_path: stage + '/knowledge/new.md', content: 'Staged lesson without navigation update'}]]
        : ['model-error', 'cancelled'].includes(mode) ? [['read', {file_path: stage + '/MEMORY.md'}], write] : [];
      call = calls[step];
    } else {
      const input = request.messages.findLast(m => m.role === 'user' && m.source?.actorId === 'owner');
      const text = input?.content.find(b => b.type === 'text')?.text;
      if (['before', 'maintain', 'after'].includes(text) && !request.messages.some(m => m.role === 'tool' && m.toolCallId === text))
        call = ['memory_maintenance', text === 'maintain' ? { action: 'run', request_ref: text } : { action: 'status' }];
      if (call) call.push(text);
    }
    if (call) {
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: call[2] || 'attempt-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
    } else {
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Stopped.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
    }
  });
}`);
    try {
      await prepareProfile(home, [
        { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test' }] } } } },
        { insert: [{ id: 'incomplete-fixture', name: join(home, 'fixture.mjs') }] },
      ]);
      client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' } });
      registerNoopTaskHosts(client);
      const binding = { sessionId: 'root', agentId: 'a', ownerId: 'owner', cwd: home, revision: '1' };
      await client.rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'a', workspace: home, revision: '1', provider: 'fixture', model: 'test', features: { dreaming: false }, toolAllowlist: ['read', 'write', 'edit', 'memory_maintenance'], knowledge: { dreaming: { maxInputTokens: 24000 } } }], bindings: [binding] });
      await client.rpc.request('session.ensure', binding);
      const submit = async (id: string) => {
        await client!.rpc.request('session.submit', { sessionId: 'root', inputId: id, mode: 'followup', content: [{ type: 'text', text: id }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id } });
        await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'root', inputId: id }) as { terminal?: unknown }).terminal, { timeout: 15000 }).toBeTruthy();
      };
      await submit('experience-one'); await submit('experience-two'); await submit('before');
      const original = await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8');
      await submit('maintain'); await submit('after');
      const facts = await client.rpc.request('knowledge.facts', {}) as { reviews: Array<{ status: string; summary: string }> };
      expect(facts.reviews).toHaveLength(1);
      const failed = ['missing-index', 'model-error', 'cancelled'].includes(mode);
      expect(facts.reviews[0]).toMatchObject({ status: failed ? 'failed' : 'completed' });
      if (failed) {
        expect(facts.reviews[0]!.summary).toContain(mode === 'missing-index' ? 'Synchronize MEMORY.md' : 'did not complete');
        expect(facts.reviews[0]!.summary).toContain('未推进处理游标');
      }
      await expect(readFile(join(home, '.nanoassistant/memory/knowledge/new.md'))).rejects.toMatchObject({code:'ENOENT'});
      expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toBe(original);
      const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      const latest = requests.filter(request => request.sessionId === 'root').at(-1);
      const status = (id: string) => JSON.parse(latest.messages.find((message: any) => message.role === 'tool' && message.toolCallId === id).content.filter((block: any) => block.type === 'text').map((block: any) => block.text).join('\n'));
      expect(status('before').sourcesPending).toBe(false);
      expect(status('before').maintenance.backlog).toMatchObject({ state: 'pending', scope: 'frozen_sources' });
      expect(status('before').maintenance.backlog.global.pending).toBe(true);
      if (failed) {
        expect(status('after').maintenance.streams).toEqual(status('before').maintenance.streams);
      } else {
        expect(status('after').maintenance.streams).not.toEqual(status('before').maintenance.streams);
      }
      const maintenance = requests.filter(request => request.sessionId.startsWith('dreaming-'));
      expect(JSON.stringify(maintenance[0].messages)).toContain('experience-one');
      if (['unread-write', 'failed-read-write'].includes(mode)) expect(maintenance.at(-1).messages.some((message: any) => message.role === 'tool' && message.isError)).toBe(true);
      await client.shutdown(); client = undefined;
    } finally {
      if (client) { client.process.kill('SIGKILL'); await client.exited; }
      await rm(home, { recursive: true, force: true });
    }
  }, 25000,
);
