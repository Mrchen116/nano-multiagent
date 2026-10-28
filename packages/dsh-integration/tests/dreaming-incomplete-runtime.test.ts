import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';

it.each(['unread', 'partial-batch', 'failed-read', 'normal-stop'])(
  'does not publish or advance Dreaming after %s evidence', async mode => {
    const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
    const home = await mkdtemp(join(tmpdir(), 'nano-dreaming-incomplete-'));
    let client: InstanceType<typeof RuntimeClient> | undefined;
    await writeFile(join(home, 'fixture.mjs'), `
import { appendFileSync } from 'node:fs';
export const name = 'incomplete-fixture';
export const inject = ['llm'];
export function apply(ctx) {
  const steps = new Map();
  ctx.on('llm/stream', async function* (request) {
    appendFileSync(process.env.DSH_HOME + '/requests.jsonl', JSON.stringify(request) + '\\n');
    const step = steps.get(request.sessionId) || 0;
    steps.set(request.sessionId, step + 1);
    let call;
    if (request.sessionId.startsWith('dreaming-')) {
      const text = request.messages.flatMap(m => m.content || []).filter(b => b.type === 'text').map(b => b.text).join('\\n');
      const units = JSON.parse(text.match(/File list \\(data\\):\\n([^\\n]+)/)[1]);
      const finish = ['finish', { units: units.map(u => ({ id: u.id, outcome: 'no_change', outputs: [] })) }];
      const calls = ${JSON.stringify(mode)} === 'unread' ? [finish]
        : ${JSON.stringify(mode)} === 'partial-batch' ? [['read', { file_path: units[0].path }], finish]
        : ${JSON.stringify(mode)} === 'failed-read' ? [['read', { file_path: units[0].path + '.missing' }], finish] : [];
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
      const binding = { sessionId: 'root', agentId: 'a', ownerId: 'owner', cwd: home, revision: '1' };
      await client.rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'a', workspace: home, revision: '1', provider: 'fixture', model: 'test', features: { dreaming: false }, toolAllowlist: ['read', 'write', 'edit', 'memory_maintenance'], knowledge: { dreaming: { maxRunMs: 10000 } } }], bindings: [binding] });
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
      expect(facts.reviews[0]).toMatchObject({ status: 'failed' });
      expect(facts.reviews[0]!.summary).toContain('without a complete, read-verified finish');
      expect(facts.reviews[0]!.summary).toContain('未推进处理游标');
      expect(await readFile(join(home, '.nanoassistant/memory/MEMORY.md'), 'utf8')).toBe(original);
      const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      const latest = requests.filter(request => request.sessionId === 'root').at(-1);
      const status = (id: string) => JSON.parse(latest.messages.find((message: any) => message.role === 'tool' && message.toolCallId === id).content.filter((block: any) => block.type === 'text').map((block: any) => block.text).join('\n'));
      expect(status('before').sourcesPending).toBe(false);
      expect(status('before').maintenance.backlog).toMatchObject({ state: 'pending', scope: 'next_bounded_batch' });
      expect(status('before').maintenance.backlog.units).toBeGreaterThan(0);
      expect(status('after').maintenance.backlog.state).toBe('pending');
      expect(status('after').maintenance.streams).toEqual(status('before').maintenance.streams);
      const maintenance = requests.filter(request => request.sessionId.startsWith('dreaming-'));
      const inputs = JSON.parse(maintenance[0].messages.flatMap((message: any) => message.content || []).filter((block: any) => block.type === 'text').map((block: any) => block.text).join('\n').match(/File list \(data\):\n([^\n]+)/)[1]);
      expect(inputs.length).toBeGreaterThan(1);
      if (mode !== 'normal-stop') expect(maintenance.at(-1).messages.some((message: any) => message.role === 'tool' && message.isError)).toBe(true);
      await client.shutdown(); client = undefined;
    } finally {
      if (client) { client.process.kill('SIGKILL'); await client.exited; }
      await rm(home, { recursive: true, force: true });
    }
  }, 25000,
);
