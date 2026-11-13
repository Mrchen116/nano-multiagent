import { mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';
import { workDescendants } from './helpers/work-history.js';

type Audit = { callId: string; source: string; reviewer?: { model: string } };
type Action = { name: string; args: Record<string, unknown> };

async function fixture(home: string, cwd: string) {
  const plugin = join(home, 'fixture.mjs');
  await writeFile(plugin, String.raw`
import { appendFile } from 'node:fs/promises';
export const name = 'file-approval-fixture';
export const inject = ['llm', 'tools'];
export function apply(ctx) {
  const seen = new Set();
  ctx.on('tools/pre-execute', (exec, next) => exec.arguments.file_path === 'blocked.txt'
    ? { kind:'deny', reason:'Host restriction' } : next());
  ctx.on('llm/stream', async function*(options) {
    const messages = options.messages.flatMap(message => message.content);
    let text = 'done';
    if (options.model.startsWith('review')) {
      const input = messages.findLast(block => block.type === 'text' && block.text.includes('<planned_action>')).text;
      const action = JSON.parse(input.split('<planned_action>')[1].split('</planned_action>')[0]);
      await appendFile(process.env.DSH_HOME + '/reviews', JSON.stringify({ model: options.model, action, input }) + '\n');
      text = JSON.stringify({ outcome:'deny', risk_level:'high', rationale:'Fixture requires review' });
    } else {
      const message = options.messages.findLast(item => item.role === 'user' && item.content.some(
        block => block.type === 'text' && block.text.includes('FIXTURE_ACTION:')));
      const raw = message?.content.find(block => block.type === 'text' && block.text.includes('FIXTURE_ACTION:')).text;
      if (message && !seen.has(message.id)) {
        seen.add(message.id);
        const action = JSON.parse(raw.slice(raw.indexOf('FIXTURE_ACTION:') + 'FIXTURE_ACTION:'.length));
        yield { type:'block-end', index:0, block:{ type:'tool-call', id:message.id+'-action',
          name:action.name, arguments:JSON.stringify(action.args) } };
        yield { type:'finish', reason:{kind:'tool-calls'} };
        return;
      }
    }
    yield { type:'block-end', index:0, block:{type:'text', text} };
    yield { type:'finish', reason:{kind:'stop'} };
  });
}
`);
  await prepareProfile(home, [
    { id:'llm-pi-ai', config:{ providers:{ fixture:{
      api:'openai-completions', baseURL:'http://127.0.0.1:9', apiKeyEnv:'NANO_TEST_KEY',
      models:['main', 'review-before', 'review-after'].map(id => ({ id, contextWindow:100000 })),
    } } } },
    { insert:[{ id:'file-approval-fixture', name:plugin }] },
  ]);
  const binding = { sessionId:'root', agentId:'agent', revision:'1', ownerId:'owner', cwd };
  return async (approval: Partial<typeof approvalDefaults> & { reviewer?: { provider:string; model:string } } = {}, revision = binding.revision) => {
    const client = new RuntimeClient({ home, cwd, env:{ NANO_TEST_KEY:'fixture' } });
    registerNoopTaskHosts(client);
    try {
      await client.rpc.request('initialize', { protocol:1, agents:[{
        agentId:binding.agentId, revision, mode:'global', workspace:cwd,
        provider:'fixture', model:'main', toolAllowlist:['read', 'edit', 'write', 'bash', 'subagent', 'send_message'],
        approval:{ ...approvalDefaults, globalRoot:home, reviewer:{ provider:'fixture', model:'review-before' }, ...approval },
      }], bindings:[binding] });
      await client.rpc.request('session.ensure', binding);
      return client;
    } catch (error) {
      await client.shutdown();
      throw error;
    }
  };
}

const message = (action: Action) => 'FIXTURE_ACTION:' + JSON.stringify(action);
const write = (file_path: string): Action => ({ name:'write', args:{ file_path, content:'proof' } });
async function submit(client: RuntimeClient, id: string, action: Action, instruction = '') {
  await client.rpc.request('session.submit', { sessionId:'root', inputId:id, mode:'followup',
    content:[{ type:'text', text:instruction + message(action) }],
    source:{ kind:'human', actorId:'owner', channel:'test', messageId:id } });
  await expect.poll(async () => (await client.rpc.request('session.lookup', { sessionId:'root', inputId:id }) as { terminal?: unknown }).terminal,
    { timeout:8000 }).toBeTruthy();
}

it('executes native Codex file tools in the workspace and temp, and sends other effects to the model', async () => {
  const home = await mkdtemp(join(homedir(), '.nano-file-approval-'));
  const temp = await mkdtemp('/tmp/nano-file-approval-');
  const cwd = join(home, 'workspace');
  let client: RuntimeClient | undefined;
  try {
    await mkdir(cwd);
    await writeFile(join(home, 'outside.txt'), 'outside');
    await writeFile(join(temp, 'AGENTS.md'), 'protected');
    await symlink(join(home, 'outside.txt'), join(temp, 'escape.txt'));
    await mkdir(join(home, 'elsewhere', 'nested'), { recursive:true });
    await symlink(join(home, 'elsewhere', 'nested'), join(temp, 'jump'));
    const tempFile = join(temp, 'temporary.txt');
    const canonicalTempFile = join(await realpath(temp), 'temporary.txt');
    const start = await fixture(home, cwd);
    client = await start();
    await submit(client, 'workspace-write', write('local.txt'));
    await submit(client, 'temp-write', write(tempFile));
    await submit(client, 'temp-read', { name:'read', args:{ file_path:tempFile } });
    await submit(client, 'temp-edit', { name:'edit', args:{ file_path:canonicalTempFile, old_string:'proof', new_string:'edited' } });
    await submit(client, 'outside', write(join(home, 'outside.txt')));
    await submit(client, 'protected', write(join(temp, 'AGENTS.md')));
    await submit(client, 'protected-alias', write(join(temp, 'aGeNtS.mD')));
    await submit(client, 'escape', write(join(temp, 'escape.txt')));
    await submit(client, 'parent-traversal', write(temp + '/jump/../created.txt'));
    await submit(client, 'blocked', write('blocked.txt'));
    await submit(client, 'bash', { name:'bash', args:{ command:'printf hello' } });

    expect(await readFile(join(cwd, 'local.txt'), 'utf8')).toBe('proof');
    expect(await readFile(tempFile, 'utf8')).toBe('edited');
    expect(await readFile(join(home, 'outside.txt'), 'utf8')).toBe('outside');
    expect(await readFile(join(temp, 'AGENTS.md'), 'utf8')).toBe('protected');
    await expect(readFile(join(home, 'elsewhere', 'created.txt'))).rejects.toMatchObject({ code:'ENOENT' });
    await expect(readFile(join(cwd, 'blocked.txt'))).rejects.toMatchObject({ code:'ENOENT' });
    const { approvals } = await client.rpc.request('session.observe', { sessionId:'root' }) as { approvals: Audit[] };
    expect(approvals.map(({ source }) => source)).toEqual([
      'workspace_file', 'workspace_file', 'safe_tool', 'workspace_file',
      'classifier_block', 'classifier_block', 'classifier_block', 'classifier_block', 'classifier_block', 'classifier_block',
    ]);
    const reviews = (await readFile(join(home, 'reviews'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(reviews.map(({ action }) => action.name)).toEqual(['write', 'write', 'write', 'write', 'write', 'bash']);

    await client.shutdown();
    client = await start({ environment:['The workspace contains shared fixtures.'] });
    await submit(client, 'custom-environment', write('shared.txt'));
    await expect(readFile(join(cwd, 'shared.txt'))).rejects.toMatchObject({ code:'ENOENT' });
    const updated = await client.rpc.request('session.observe', { sessionId:'root' }) as { approvals:Audit[] };
    expect(updated.approvals.at(-1)).toMatchObject({ source:'classifier_block' });
  } finally {
    if (client) await client.shutdown();
    await rm(home, { recursive:true, force:true });
    await rm(temp, { recursive:true, force:true });
  }
}, 30_000);

it('uses current approval in both directions when the same child resumes after restart', async () => {
  const home = await mkdtemp(join(homedir(), '.nano-child-approval-'));
  const cwd = join(home, 'workspace');
  let client: RuntimeClient | undefined;
  try {
    await mkdir(cwd);
    const start = await fixture(home, cwd);
    client = await start();
    const childAction = write(join(home, 'outside.txt'));
    await submit(client, 'delegate', { name:'subagent', args:{
      prompt:message(childAction), description:'Original delegated fixture', run_in_background:true,
    } }, 'ORIGINAL_OWNER_SCOPE: isolated fixture files. ');
    const children = () => workDescendants(client!.rpc, { sessionId:'root' }) as Promise<{ id:string; events:{ type:string }[] }[]>;
    await expect.poll(async () => (await children())[0]?.events.filter(event => event.type === 'turn/end').length,
      { timeout:8000 }).toBe(1);
    const childId = (await children())[0]!.id;
    const resume = async (id: string, turns: number, action: Action) => {
      await submit(client!, id, { name:'send_message', args:{ agent_id:childId, message:message(action) } });
      await expect.poll(async () => (await children()).find(child => child.id === childId)?.events.filter(event => event.type === 'turn/end').length,
        { timeout:8000 }).toBe(turns);
    };
    await expect(readFile(join(home, 'outside.txt'))).rejects.toMatchObject({ code:'ENOENT' });
    await client.shutdown();
    client = await start({ dangerouslySkipPermissions:true });
    await resume('skip', 2, childAction);
    expect(await readFile(join(home, 'outside.txt'), 'utf8')).toBe('proof');

    await client.shutdown();
    client = await start({ reviewer:{ provider:'fixture', model:'review-after' } }, '2');
    await resume('review', 3, write(join(home, 'still-blocked.txt')));
    await expect(readFile(join(home, 'still-blocked.txt'))).rejects.toMatchObject({ code:'ENOENT' });
    const reviews = (await readFile(join(home, 'reviews'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    expect(reviews.map(({ model }) => model)).toEqual(['review-before', 'review-after']);
    expect(reviews[1].input).toContain('still-blocked.txt');
    expect(reviews[1].input).toContain('ORIGINAL_OWNER_SCOPE');
  } finally {
    if (client) await client.shutdown();
    await rm(home, { recursive:true, force:true });
  }
}, 40_000);
