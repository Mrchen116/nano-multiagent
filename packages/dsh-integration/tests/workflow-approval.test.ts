import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it.each(['workflow', 'subagent'])('%s children keep delegated permissions without human approval cards', async kind => {
  const home = await mkdtemp(join(tmpdir(), 'nano-child-approval-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `
import { appendFile } from 'node:fs/promises';
export const name = 'child-approval';
export const inject = ['llm', 'tools'];
export function apply(ctx) {
  for (const name of ['fixture_effect', 'fixture_native_ask']) ctx.tools.register({
    name, description: 'Mutate a fixture', parameters: {type:'object',properties:{scenario:{type:'string'}},required:['scenario']},
    output: {schema:{},render:()=>[{type:'text',text:'executed'}]},
    execute: async args => { await appendFile(process.env.DSH_HOME+'/effects', args.scenario+'\\n'); return {}; },
  });
  ctx.on('tools/pre-execute', (exec, next) => exec.name === 'fixture_native_ask' ? {kind:'ask',reason:'Native approval required'} : next());
  const seen = new Set();
  ctx.on('llm/stream', async function*(o) {
    if (o.system) {
      const text = o.messages[0].content[0].text;
      const pending = JSON.parse(text.split('\\n').find(line=>line.startsWith('{"pending_action"'))).pending_action;
      const scenario = pending.arguments.scenario;
      yield {type:'block-end',index:0,block:{type:'text',text:scenario==='allow'?'<block>no</block>':scenario==='fault'?'invalid verdict':'<block>yes</block><reason>scope missing</reason>'}};
      yield {type:'finish',reason:{kind:'stop'}}; return;
    }
    const input = o.messages.findLast(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&/^(launch|CHILD) /.test(b.text)));
    const [action, scenario] = input.content.find(b=>b.type==='text'&&/^(launch|CHILD) /.test(b.text)).text.split(' ');
    if (!seen.has(input.id)) {
      seen.add(input.id);
      const child = action === 'CHILD';
      const name = child ? scenario==='ask'?'fixture_native_ask':'fixture_effect' : '${kind}';
      const args = child ? {scenario} : '${kind}'==='workflow'
        ? {meta:{name:'approval-'+scenario,description:'approval'},script:'return await agent("CHILD '+scenario+'");'}
        : {prompt:'CHILD '+scenario,description:'Permission child',run_in_background:false};
      yield {type:'block-end',index:0,block:{type:'tool-call',id:input.id+'-call',name,arguments:JSON.stringify(args)}};
      yield {type:'finish',reason:{kind:'tool-calls'}}; return;
    }
    const result = o.messages.findLast(m=>m.role==='tool');
    yield {type:'block-end',index:0,block:{type:'text',text:JSON.stringify(result?.content??'done')}};
    yield {type:'finish',reason:{kind:'stop'}};
  });
}`);
    await prepareProfile(home, [{ insert: [{ id: 'child-approval', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    const requests: any[] = [];
    client.rpc.onNotification((method, value) => {
      if (method !== 'approval.request') return;
      requests.push(value);
      // Settle an unexpected card so the assertion exposes the regression without hanging.
      void client!.rpc.request('approval.answer', { requestId: (value as any).requestId, decision: 'rejected' });
    });
    await client.rpc.request('initialize', { protocol: 1, agents: [{
      agentId: 'a', revision: '1', mode: 'single_thread', provider: 'deepseek-official', model: 'deepseek-flash',
      toolAllowlist: [kind, 'fixture_effect', 'fixture_native_ask'],
      approval: { ...approvalDefaults, globalRoot: home, denyLimit: 1, unattendedFallback: 'allow', alwaysAllowTools: [kind] },
    }], bindings: [] });
    for (const scenario of ['deny', 'fault', 'ask', 'allow']) {
      const sessionId = 'root-' + scenario;
      await client.rpc.request('session.ensure', { sessionId, agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId, inputId: scenario, mode: 'followup', content: [{ type: 'text', text: 'launch '+scenario }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: scenario } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId, inputId: scenario }) as any).terminal, { timeout: 10000 }).toBeTruthy();
      const descendants = async () => await client!.rpc.request('session.descendants', { sessionId }) as any[];
      await expect.poll(async () => (await descendants())[0]?.events.some((event: any) => event.type === 'turn/end'), { timeout: 10000 }).toBe(true);
      const child = (await descendants())[0];
      expect(requests, `${kind}/${scenario} must not emit approval cards`).toEqual([]);
      expect(child.events.filter((event: any) => event.type === 'approval/policy').at(-1)?.data.policy).toBe('never');
      const effect = child.events.find((event: any) => event.type === 'tool/result');
      expect(effect?.data.message.isError ?? false).toBe(scenario !== 'allow');
      if (scenario === 'deny') expect(JSON.stringify(effect)).toContain('scope missing');
      if (scenario === 'fault') expect(JSON.stringify(effect)).toContain('Automatic reviewer unavailable');
    }
    expect(await readFile(join(home, 'effects'), 'utf8')).toBe('allow\n');
    await client.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${error}\n${logs}`, { cause: error }); }
  finally { if (client) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30000);
