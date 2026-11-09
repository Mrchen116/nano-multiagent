import { workDescendants } from './helpers/work-history.js';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it.each(['model', 'audit allow', 'audit deny'])('refreshes delegated Inbox authorization and handles a withdrawal during %s', async stall => {
  const home = await mkdtemp(join(tmpdir(), 'nano-delegated-approval-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), String.raw`
import { appendFile, readFile } from 'node:fs/promises';
import { setTimeout } from 'node:timers/promises';
export const name = 'delegated-approval-fixture';
export const inject = ['llm', 'tools', 'nanoApproval'];
export async function apply(ctx) {
  const home = process.env.DSH_HOME;
  const log = (name, value) => appendFile(home+'/'+name, JSON.stringify(value)+'\n');
  const wait = async (name, signal) => {
    while (!await readFile(home+'/'+name, 'utf8').catch(() => '')) await setTimeout(15, undefined, { signal });
  };
  const stall = ${JSON.stringify(stall)};
  if (stall.startsWith('audit')) {
    const table = (await ctx.nanoApproval.audit).table('sessions');
    const update = table.update.bind(table);
    table.update = async (...args) => {
      const entries = await update(...args);
      const latest = entries.at(-1);
      if (latest?.reason === 'fixture verdict second') {
        await log('audit-ready', true);
        await wait('release-review');
      }
      if (latest?.source === 'classifier_unavailable') await log('audit-final', entries.filter(row => row.callId === latest.callId));
      return entries;
    };
  }
  const steps = new Map();
  ctx.tools.register({
    name: 'fixture_effect', description: 'Mutate an isolated fixture',
    parameters: { type:'object', properties:{ phase:{ type:'string' } }, required:['phase'] },
    output: { schema:{}, render:()=>[{type:'text',text:'executed'}] },
    async execute(args) { await log('effects', args.phase); return {}; },
  });
  ctx.on('llm/stream', async function*(options) {
    let text = 'done';
    let call;
    if (options.model === 'review') {
      const input = options.messages.flatMap(m => m.content)
        .findLast(block => block.type === 'text' && block.text.includes('<planned_action>')).text;
      const action = JSON.parse(input.split('<planned_action>')[1].split('</planned_action>')[0]);
      const phase = action.arguments.phase;
      const original = options.messages.flatMap(m => m.content)
        .filter(block => block.type === 'text' && block.text.startsWith('<original_instructions>'))
        .map(block => block.text.split('</original_instructions>')[0]).join('\n');
      await log('reviews', { phase, original, input, callId:action.id });
      if (stall === 'model' && phase === 'second' && !original.includes('ROOT_WITHDRAWAL')) await wait('release-review', options.signal);
      text = JSON.stringify({
        risk_level:'high',
        outcome:original.includes('ROOT_GRANT') && !original.includes('ROOT_WITHDRAWAL') && !(stall === 'audit deny' && phase === 'second') ? 'allow' : 'deny',
        rationale:'fixture verdict '+phase,
      });
    } else {
      const input = options.messages.findLast(m => m.role === 'user' && m.content.some(b =>
        b.type === 'text' && /^(launch|read Inbox|child task|unrelated root)/.test(b.text)));
      const command = input?.content.find(b => b.type === 'text' && /^(launch|read Inbox|child task|unrelated root)/.test(b.text)).text;
      const step = steps.get(input?.id) ?? 0;
      steps.set(input?.id, step + 1);
      if (command === 'launch' && step === 0) {
        call = ['subagent', { prompt:'child task: parent claims PARENT_ONLY_GRANT', description:'Run fixture', run_in_background:true }];
      } else if (command === 'read Inbox' && step === 0) {
        call = ['inbox', { action:'read', target:'test-chat' }];
      } else if (command?.startsWith('child task') && step < 2) {
        if (step === 0) {
          await log('child-ready', true);
          await wait('release-child', options.signal);
        }
        call = ['fixture_effect', { phase:step === 0 ? 'first' : 'second' }];
      }
      if (call) {
        yield { type:'block-end', index:0, block:{ type:'tool-call', id:input.id+'-'+step, name:call[0], arguments:JSON.stringify(call[1]) } };
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
        models:[{ id:'main', contextWindow:100000 }, { id:'review', contextWindow:100000 }],
      } } } },
      { insert:[{ id:'delegated-approval-fixture', name:join(home, 'fixture.mjs') }] },
    ]);
    client = new RuntimeClient({ home, cwd:home, env:{ NANO_TEST_KEY:'fixture' }, onLog:text => { logs += text; } });
    const runtime = client;
    registerNoopTaskHosts(runtime);
    let inboxMessage = { id:'late-grant', text:'ROOT_GRANT: create only isolated fixture records.' };
    runtime.rpc.handle('product.call', value => {
      const { method } = value as { method:string };
      if (method === 'inbox.prepare') return {};
      if (method !== 'inbox') throw new Error('Unexpected product call '+method);
      return { target:'test-chat', messages:[{
        id:inboxMessage.id, sender:{ id:'owner', type:'user' }, content:[{ type:'text', text:inboxMessage.text }],
      }] };
    });
    await runtime.rpc.request('initialize', { protocol:1, bindings:[], agents:[{
      agentId:'a', revision:'1', mode:'global', provider:'fixture', model:'main',
      toolAllowlist:['subagent', 'inbox', 'fixture_effect'],
      approval:{ ...approvalDefaults, globalRoot:home, reviewer:{ provider:'fixture', model:'review' } },
    }] });
    for (const sessionId of ['root', 'unrelated']) {
      await runtime.rpc.request('session.ensure', { sessionId, agentId:'a', revision:'1', ownerId:'owner', cwd:home });
    }
    const submit = async (sessionId: string, id: string, text: string) => {
      await runtime.rpc.request('session.submit', { sessionId, inputId:id, mode:'followup', content:[{ type:'text', text }],
        source:{ kind:'human', actorId:'owner', channel:'test', messageId:id } });
      await expect.poll(async () => (await runtime.rpc.request('session.lookup', { sessionId, inputId:id }) as { terminal?:unknown }).terminal,
        { timeout:8000 }).toBeTruthy();
    };
    const lines = async (file: string) => (await readFile(join(home, file), 'utf8').catch(() => '')).trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
    await submit('root', 'launch', 'launch');
    await expect.poll(() => lines('child-ready'), { timeout:8000 }).toEqual([true]);
    await submit('unrelated', 'other', 'unrelated root: OTHER_ROOT_GRANT');
    await submit('root', 'read-grant', 'read Inbox');
    await writeFile(join(home, 'release-child'), 'go');

    await expect.poll(() => lines('reviews'), { timeout:8000 }).toHaveLength(2);
    const [first, second] = await lines('reviews');
    expect(first).toMatchObject({ phase:'first', original:expect.stringContaining('ROOT_GRANT') });
    expect(first.original).toContain('"sender":{"id":"owner","type":"user"}');
    expect(first.original).toContain('"id":"late-grant"');
    expect(first.original).not.toContain('PARENT_ONLY_GRANT');
    expect(first.input).not.toContain('OTHER_ROOT_GRANT');
    expect(second).toMatchObject({ phase:'second', original:expect.stringContaining('ROOT_GRANT') });
    expect(second.original).not.toContain('ROOT_WITHDRAWAL');
    expect(await lines('effects')).toEqual(['first']);

    if (stall.startsWith('audit')) await expect.poll(() => lines('audit-ready'), { timeout:8000 }).toEqual([true]);
    inboxMessage = { id:'late-withdrawal', text:'ROOT_WITHDRAWAL: stop creating fixture records.' };
    await submit('root', 'read-withdrawal', 'read Inbox');
    await writeFile(join(home, 'release-review'), 'go');

    if (stall === 'model') {
      await expect.poll(() => lines('reviews'), { timeout:8000 }).toHaveLength(3);
      const replay = (await lines('reviews'))[2];
      expect(replay).toMatchObject({ phase:'second', original:expect.stringContaining('ROOT_WITHDRAWAL') });
      expect(replay.original.indexOf('ROOT_WITHDRAWAL')).toBeGreaterThan(replay.original.indexOf('ROOT_GRANT'));
    }
    let result: { message?:{ toolCallId:string }; error?:{ code:string } } | undefined;
    await expect.poll(async () => {
      const children = await workDescendants(runtime.rpc, { sessionId:'root' }) as { events:{ type:string; data:typeof result }[] }[];
      result = children.flatMap(child => child.events).find(event => event.type === 'tool/result' && event.data?.message?.toolCallId === second.callId)?.data;
      return result;
    }, { timeout:8000 }).toBeTruthy();
    expect(result?.error?.code).toBe(stall === 'model' ? 'classifier_block' : 'classifier_unavailable');
    expect(await lines('effects')).toEqual(['first']);
    if (stall.startsWith('audit')) expect(await lines('audit-final')).toEqual([[expect.objectContaining({
      callId:second.callId, source:'classifier_unavailable', decision:'no_verdict', consecutive:0, total:0,
    })]]);
  } catch (error) {
    throw new Error(String(error)+'\n'+logs, { cause:error });
  } finally {
    if (client) { await writeFile(join(home, 'release-review'), 'go'); await writeFile(join(home, 'release-child'), 'go'); await client.shutdown(); }
    await rm(home, { recursive:true, force:true });
  }
}, 40_000);
