import { mkdtemp, readFile, rm, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { RuntimeClient, prepareProfile } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('gates the real outbound tools, allows one explicitly requested clipboard read, and reviews a write once', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-computer-host-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const inputs = ['ordinary', 'off', 'worker', 'describe', 'clipboard', 'unrelated', 'write'];
  const evidence = join(home, 'requests.jsonl');
  try {
    // Replace only the final OS clipboard operation. No fixture action can read a real pasteboard.
    await writeFile(
      join(home, 'probe.mjs'),
      `import {appendFile} from 'node:fs/promises';
import {openMcp} from ${JSON.stringify(new URL('../lib/computer/mcp.js', import.meta.url).href)};
import {workerReportBridge} from ${JSON.stringify(new URL('../lib/local-workers/report-bridge.js', import.meta.url).href)};
import {DesktopBackend} from ${JSON.stringify(new URL('../lib/computer/desktop.js', import.meta.url).href)};
const prepare=DesktopBackend.prototype.prepare;
DesktopBackend.prototype.prepare=async function(action,...args){
  const prepared=await prepare.call(this,action,...args);
  if(action==='read_clipboard')prepared.run=async()=>{
    await appendFile(process.env.DSH_HOME+'/os-reads','1');
    return [{type:'text',text:'SYNTHETIC-CLIPBOARD'}];
  };
  return prepared;
};
export const name='nano-computer-probe';export const inject=['llm','tools'];
export function apply(ctx){
 const counts=new Map();
 ctx.tools.register({name:'fixture_worker',output:{schema:{type:'string'},render:(_,v)=>[{type:'text',text:v}]},description:'Exercise the host-owned worker transport',parameters:{type:'object',properties:{}},execute:async(_,exec)=>{
   const {agent,signal}=exec;
   const computer=ctx.get('nanoComputer');
   const release=await computer.bindWorker(agent,'fixture-worker','worker-short',signal);
   const bridge=await workerReportBridge(async()=>{},(args,sig)=>computer.callWorker(agent,'fixture-worker',args,sig));
   try {
     const mcp=await openMcp(bridge.computer.command,bridge.computer.args,bridge.computer.env);
     try {
       const result=await mcp.call('computer_use',{surface:'desktop',action:'read_clipboard'},signal);
       await appendFile(process.env.DSH_HOME+'/worker-result',JSON.stringify(result));
     } finally {await mcp.close();}
   } catch(error){await appendFile(process.env.DSH_HOME+'/worker-result',String(error));throw error;}
   finally{release();await bridge.close();}
   return 'Delivered to worker';
 }});
 ctx.on('llm/stream',async function*(o){
   const human=o.messages.findLast(m=>m.role==='user' && m.source?.kind==='user' && 'actorId' in m.source);
   await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({session:o.sessionId,system:o.system,tools:o.tools,messages:o.messages})+'\\n');
   if(o.system){yield {type:'block-end',index:0,block:{type:'text',text:'{"risk":"high","decision":"deny","reason":"Synthetic denial"}'}};
     yield {type:'finish',reason:{kind:'stop'}};return;}
   const id=human?.id, step=counts.get(id)??0;counts.set(id,step+1);
   const actions={describe:[{surface:'desktop',action:'describe'}],worker:[{fixture:true},{surface:'desktop',action:'read_clipboard'}],clipboard:[{surface:'desktop',action:'read_clipboard'},{surface:'desktop',action:'read_clipboard'}],
     unrelated:[{surface:'desktop',action:'read_clipboard'}],write:[{surface:'browser',action:'open',input:{mode:'isolated',url:'https://example.org/'}}]};
   const action=actions[id]?.[step];
   if(action){yield {type:'block-end',index:0,block:{type:'tool-call',id:id+'-'+step,name:action.fixture?'fixture_worker':'computer_use',arguments:JSON.stringify(action.fixture?{}:action)}};yield {type:'finish',reason:{kind:'tool-calls'}};return;}
   yield {type:'block-end',index:0,block:{type:'text',text:'Done'}};yield {type:'finish',reason:{kind:'stop'}};
 });
}`,
    );
    await prepareProfile(home, [
      {
        id: 'llm-pi-ai',
        config: {
          providers: {
            fixture: {
              api: 'openai-completions',
              baseURL: 'http://127.0.0.1:9',
              apiKeyEnv: 'NANO_TEST_KEY',
              models: [{ id: 'fixture' }],
            },
          },
        },
      },
      { insert: [{ id: 'computer-probe', name: join(home, 'probe.mjs') }] },
    ]);
    client = new RuntimeClient({
      home,
      cwd: home,
      env: { NANO_TEST_KEY: 'test' },
      onLog: (line) => {
        logs += line;
      },
    });
    registerNoopTaskHosts(client);
    const consumed = new Set<string>();
    client.rpc.handle('product.call', (value) => {
      const call = value as { method: string; args: { id: string } };
      if (call.method !== 'computer.claim') throw new Error('Unexpected call ' + call.method);
      if (consumed.has(call.args.id)) return false;
      consumed.add(call.args.id);
      return true;
    });
    const agents = inputs.map((id) => ({
      agentId: id,
      revision: '1',
      provider: 'fixture',
      model: 'fixture',
      knowledge: { memoryMode: 'legacy' },
      ...(id === 'ordinary'
        ? {}
        : {
            toolAllowlist:
              id === 'off' ? ['read'] : id === 'worker' ? ['fixture_worker', 'computer_use'] : ['read', 'computer_use'],
          }),
      approval: { ...approvalDefaults, rules: 'dsh', globalRoot: home, dangerouslySkipPermissions: id === 'worker' },
    }));
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    for (const agentId of inputs) {
      await client.rpc.request('session.ensure', {
        sessionId: agentId,
        agentId,
        ownerId: 'owner',
        revision: '1',
        cwd: home,
      });
      const text = ['clipboard', 'worker'].includes(agentId)
        ? '把我刚复制的内容整理一下'
        : agentId === 'write'
          ? 'Open https://example.org/ in an isolated profile'
          : 'Do an ordinary task';
      await client.rpc.request('session.submit', {
        sessionId: agentId,
        inputId: agentId,
        mode: 'followup',
        content: [{ type: 'text', text }],
        source: {
          kind: 'human',
          actorId: 'owner',
          channel: 'test',
          messageId: agentId,
          computerOwnerRequest: agentId + '-short',
          directHumanText: text,
        },
      });
      await expect
        .poll(
          async () => (await client!.rpc.request('session.lookup', { sessionId: agentId, inputId: agentId })).terminal,
          { timeout: 12000 },
        )
        .toBeTruthy();
    }
    const requests = (await readFile(evidence, 'utf8'))
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line));
    const hasTool = (row: { tools?: Array<{ name: string }> }) =>
      row.tools?.some((t) => t.name === 'computer_use') ?? false;
    const first = (id: string) => requests.find((r) => r.session === id && !r.system);
    expect(hasTool(first('ordinary'))).toBe(false);
    expect(hasTool(first('describe'))).toBe(true);
    expect(first('describe').tools.filter((tool: { name: string }) => tool.name !== 'computer_use')).toEqual(
      first('off').tools,
    );
    expect(await readFile(join(home, 'worker-result'), 'utf8')).toContain('SYNTHETIC-CLIPBOARD');
    const transcript = (id: string) => JSON.stringify(requests.filter((r) => r.session === id && !r.system).at(-1));
    expect(transcript('describe')).toContain('list_windows');
    expect(transcript('clipboard')).toContain('SYNTHETIC-CLIPBOARD');
    expect(transcript('clipboard')).toContain('already consumed');
    expect(transcript('worker')).toContain('already consumed');
    expect(transcript('unrelated')).toContain('requires a direct owner request');
    expect(await readFile(join(home, 'os-reads'), 'utf8')).toBe('11');
    const reviews = requests.filter((r) => r.system);
    expect(reviews).toHaveLength(1);
    expect(JSON.stringify(reviews)).toContain('host_observation');
    if (process.env.NANO_COMPUTER_EVIDENCE) {
      await mkdir(process.env.NANO_COMPUTER_EVIDENCE, { recursive: true });
      await copyFile(evidence, join(process.env.NANO_COMPUTER_EVIDENCE, 'requests.jsonl'));
    }
  } catch (error) {
    throw new Error(String(error) + '\n' + logs.slice(-4500));
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);

it('bounds a computer assignment by the original surface and target', async () => {
  const { computerScope, scopeAllows } = await import('../src/computer/scope.js');
  const request = '请打开 https://example.org 检查订单';
  const scope = computerScope(request, false);
  expect(scopeAllows(request, scope, 'browser', 'open', { url: 'https://example.org/orders' })).toBe(true);
  expect(scopeAllows(request, scope, 'browser', 'navigate', { url: 'https://example.net' })).toBe(false);
  expect(scopeAllows(request, scope, 'desktop', 'bind', { app: 'com.apple.TextEdit' })).toBe(false);
  expect(
    scopeAllows('把我刚复制的内容整理一下', computerScope('', true), 'browser', 'open', { url: 'https://example.org' }),
  ).toBe(false);
  expect(
    scopeAllows('请在 TextEdit 窗口输入草稿', computerScope('请在 TextEdit 窗口输入草稿', false), 'desktop', 'bind', {
      app: 'com.apple.Notes',
    }),
  ).toBe(false);
});
