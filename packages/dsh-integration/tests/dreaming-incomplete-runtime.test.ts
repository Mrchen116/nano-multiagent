import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import {stripContextItemId} from 'dsh-agent-context';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each(['unread-write', 'failed-read-write', 'normal-stop', 'committed-non-markdown', 'body-only', 'legacy-oversized-index', 'oversized-index', 'model-error', 'cancelled', 'missing-entry'])(
  'checks actual direct edits and source progress after %s', async mode => {
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
      const stage = text.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/)[1];
      const write = ['write', { file_path: stage + '/MEMORY.md', content: 'Unsupported overwrite' }];
      const mode = ${JSON.stringify(mode)};
      if (step === 2 && ['model-error', 'cancelled'].includes(mode)) {
        if (mode === 'cancelled') ctx.agents.get(request.sessionId).cancel({kind:'hook',reason:'Fixture cancellation'});
        throw new Error('Fixture model failure');
      }
      const calls = mode === 'missing-entry'
        ? [['bash', {description:'Commit deletion of the root entry',command:'git rm -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m "Remove entry" && git status --porcelain'}, 'commit-deletion']]
        : mode === 'unread-write' ? [write]
        : mode === 'failed-read-write' ? [['read', { file_path: stage + '/missing.md' }], write]
        : ['body-only', 'legacy-oversized-index', 'oversized-index'].includes(mode) ? [
            ['read', {file_path: stage + '/MEMORY.md'}],
            ['write', {file_path: stage + '/knowledge/new.md', content: 'A detail that belongs only on the topic page.'}],
            ...(mode === 'body-only' ? [['write', {file_path: stage + '/knowledge/second.md', content: 'Another related detail.'}]] : []),
            ...(mode === 'oversized-index' ? [['write', {file_path: stage + '/MEMORY.md', content: '记'.repeat(8001)}]] : []),
          ]
        : ['model-error', 'cancelled'].includes(mode) ? [['read', {file_path: stage + '/MEMORY.md'}], write] : [];
      call = calls[step];
      const status = request.messages.findLast(message => message.source?.channel === 'dreaming-git-status');
      if (status && !request.messages.some(message => message.toolCallId === 'batch-commit')) {
        const second = stage + '/knowledge/second.md';
        if (mode === 'body-only' && !request.messages.some(message => message.toolCallId === 'read-published')) {
          call = ['read', {file_path: second}, 'read-published'];
        } else if (mode === 'body-only' && !request.messages.some(message => message.toolCallId === 'update-published')) {
          call = ['write', {file_path: second, content: 'Updated detail after status feedback.'}, 'update-published'];
        } else if (mode === 'missing-entry') {
          call = ['bash', {description:'Restore and commit the root entry',command:"printf '%s' '# Restored entry' > MEMORY.md && git add -- MEMORY.md && git -c user.name=Nano -c user.email=memory@localhost commit -m 'Restore entry'"}, 'batch-commit'];
        } else if (mode === 'committed-non-markdown') {
          call = ['bash', {description:'Remove the unsupported committed file',command:'git rm -- .gitignore && git -c user.name=Nano -c user.email=memory@localhost commit -m "Remove unsupported file"'}, 'batch-commit'];
        } else {
          call = ['bash', {description:'Commit the related memory batch',command:'git add -- . && git -c user.name=Nano -c user.email=memory@localhost commit -m "Consolidate related memories"'}, 'batch-commit'];
        }
      }
    } else {
      const input = request.messages.findLast(m => m.role === 'user' && m.source?.actorId === 'owner');
      const text = input?.content.find(b => b.type === 'text')?.text;
      if (['before', 'maintain', 'after','repair'].includes(text) && !request.messages.some(m => m.role === 'tool' && m.toolCallId === text))
        call = ['memory_maintenance', ['maintain','repair'].includes(text) ? { action: 'run', request_ref: text } : { action: 'status' }];
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
      const progressPath = join(home, 'storages/nano_dreaming/owners/YQ.json');
      const beforeProgress = JSON.parse(await readFile(progressPath, 'utf8')).record.streams;
      const entry = join(home, '.nanoassistant/memory/MEMORY.md');
      if (mode === 'legacy-oversized-index') await writeFile(entry, '# Existing key memory\n' + 'Old detailed note.\n'.repeat(500));
      if (mode === 'committed-non-markdown') {
        const cwd = join(home, '.nanoassistant/memory');
        await writeFile(join(cwd, '.gitignore'), 'scratch.txt');
        execFileSync('git', ['add', '--', '.gitignore'], {cwd});
        execFileSync('git', ['-c', 'user.name=Nano', '-c', 'user.email=memory@localhost', 'commit', '-m', 'Seed unsupported file'], {cwd});
        expect(execFileSync('git', ['status','--porcelain'], {cwd,encoding:'utf8'})).toBe('');
      }
      const original = await readFile(entry, 'utf8');
      await submit('maintain'); await submit('after');
      const facts = await client.rpc.request('knowledge.facts', {}) as { reviews: Array<{ status: string; summary: string }> };
      expect(facts.reviews).toHaveLength(1);
      const failed = ['model-error', 'cancelled'].includes(mode);
      expect(facts.reviews[0]).toMatchObject({ status: failed ? 'partial' : 'completed' });
      if (failed) {
        expect(facts.reviews[0]!.summary).toContain('did not complete');
        expect(facts.reviews[0]!.summary).toContain('整理进度未推进');
      }
      const body = readFile(join(home, '.nanoassistant/memory/knowledge/new.md'), 'utf8');
      if (['body-only', 'legacy-oversized-index', 'oversized-index'].includes(mode)) {
        await expect(body).resolves.toBe('A detail that belongs only on the topic page.');
      } else {
        await expect(body).rejects.toMatchObject({code:'ENOENT'});
      }
      expect(await readFile(entry, 'utf8')).toBe(mode==='missing-entry'?'# Restored entry':mode==='oversized-index'?'记'.repeat(8001):['model-error','cancelled'].includes(mode)?'Unsupported overwrite':original);
      const requests = (await readFile(join(home, 'requests.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      const latest = requests.filter(request => request.sessionId === 'root').at(-1);
      const status = (id: string) => JSON.parse(stripContextItemId(latest.messages.find((message: any) => message.role === 'tool' && message.toolCallId === id).content).filter(block => block.type === 'text').map(block => block.text).join('\n'));
      expect(status('before').sourcesPending).toBe(false);
      expect(status('before').maintenance.backlog).toMatchObject({ state: 'pending', scope: 'frozen_sources' });
      expect(status('before').maintenance.backlog.global.pending).toBe(true);
      const afterProgress = JSON.parse(await readFile(progressPath, 'utf8')).record.streams;
      if (failed) expect(afterProgress).toEqual(beforeProgress);
      else expect(afterProgress).not.toEqual(beforeProgress);
      for (const id of ['before', 'after']) {
        const result = status(id);
        for (const key of ['generation', 'sources', 'backupRoot']) expect(result).not.toHaveProperty(key);
        for (const key of ['protocol', 'streams', 'seen', 'rotation', 'integrated', 'retryAt', 'failures']) expect(result.maintenance).not.toHaveProperty(key);
        expect(result.maintenance.backlog.global).not.toHaveProperty('ranges');
        expect(result.maintenance.backlog.global.units).toBeGreaterThanOrEqual(0);
      }
      const maintenance = requests.filter(request => request.sessionId.startsWith('dreaming-'));
      const material=maintenance[0].messages.flatMap((m:any)=>m.content??[]).map((b:any)=>b.text??'').join('');
      expect(material).toContain('experience-one');
      expect(material).not.toContain('Existing pages awaiting verification');
      if (mode === 'committed-non-markdown') {
        const memory = join(home, '.nanoassistant/memory');
        expect(new Set(maintenance.map(request => request.sessionId)).size).toBe(1);
        const feedback = maintenance.flatMap(request => request.messages).find(message => message.source?.channel === 'dreaming-git-status');
        expect(feedback?.content[0].text).toContain('{"path":".gitignore","reason":"Expected a regular Markdown file"}');
        expect(execFileSync('git', ['status','--porcelain'], {cwd:memory,encoding:'utf8'})).toBe('');
        expect(execFileSync('git', ['log','-1','--format=%s'], {cwd:memory,encoding:'utf8'}).trim()).toBe('Remove unsupported file');
      }
      if (mode === 'body-only') {
        const memory = join(home, '.nanoassistant/memory');
        const feedback = maintenance.filter(request => request.messages.some((message: any) => message.source?.channel === 'dreaming-git-status'));
        expect(feedback).not.toHaveLength(0);
        expect(feedback[0].sessionId).toBe(maintenance[0].sessionId);
        expect(JSON.stringify(feedback[0].messages)).toContain('knowledge/second.md');
        expect(await readFile(join(memory,'knowledge/second.md'),'utf8')).toBe('Updated detail after status feedback.');
        expect(execFileSync('git', ['status', '--porcelain'], {cwd:memory,encoding:'utf8'})).toBe('');
        expect(execFileSync('git', ['rev-list', '--count', 'HEAD'], {cwd:memory,encoding:'utf8'}).trim()).toBe('2');
        expect(execFileSync('git', ['log', '-1', '--format=%s'], {cwd:memory,encoding:'utf8'}).trim()).toBe('Consolidate related memories');
        expect(execFileSync('git', ['diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'], {cwd:memory,encoding:'utf8'}).trim().split('\n'))
          .toEqual(['knowledge/new.md', 'knowledge/second.md']);
      }
      if (['unread-write', 'failed-read-write'].includes(mode)) expect(maintenance.at(-1).messages.some((message: any) => message.role === 'tool' && message.isError)).toBe(true);
      if (mode === 'missing-entry') {
        const memory = join(home, '.nanoassistant/memory');
        expect(new Set(maintenance.map(request => request.sessionId)).size).toBe(1);
        const feedback = maintenance.flatMap(request => request.messages).find(message => message.source?.channel === 'dreaming-git-status');
        const issues = JSON.parse(feedback.content[0].text.split('\n')[1]);
        expect(issues).toEqual([{path:'MEMORY.md',reason:'MEMORY.md is missing from the repository root'}]);
        const git = (...args: string[]) => execFileSync('git', args, {cwd:memory,encoding:'utf8'}).trim();
        expect(git('diff-tree', '--no-commit-id', '--name-status', '-r', 'HEAD^')).toBe('D\tMEMORY.md');
        expect(git('show', 'HEAD:MEMORY.md')).toBe('# Restored entry');
        expect(git('status','--porcelain')).toBe('');
      }
      await client.shutdown(); client = undefined;
    } finally {
      if (client) { client.process.kill('SIGKILL'); await client.exited; }
      await rm(home, { recursive: true, force: true });
    }
  }, 25000,
);
