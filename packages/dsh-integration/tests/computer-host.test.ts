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
  const inputs = ['ordinary', 'describe', 'clipboard', 'unrelated', 'write'];
  const evidence = join(home, 'requests.jsonl');
  try {
    // Replace only the final OS clipboard operation. No fixture action can read a real pasteboard.
    await writeFile(
      join(home, 'probe.mjs'),
      `import {appendFile} from 'node:fs/promises';
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
export const name='nano-computer-probe';export const inject=['llm'];
export function apply(ctx){
 const counts=new Map();
 ctx.on('llm/stream',async function*(o){
   const human=o.messages.findLast(m=>m.role==='user' && m.source?.kind==='user' && 'actorId' in m.source);
   await appendFile(process.env.DSH_HOME+'/requests.jsonl',JSON.stringify({session:o.sessionId,system:o.system,tools:o.tools,messages:o.messages})+'\\n');
   if(o.system){yield {type:'block-end',index:0,block:{type:'text',text:'{"risk":"high","decision":"deny","reason":"Synthetic denial"}'}};
     yield {type:'finish',reason:{kind:'stop'}};return;}
   const id=human?.id, step=counts.get(id)??0;counts.set(id,step+1);
   const actions={describe:[{surface:'desktop',action:'describe'}],clipboard:[{surface:'desktop',action:'read_clipboard'},{surface:'desktop',action:'read_clipboard'}],
     unrelated:[{surface:'desktop',action:'read_clipboard'}],write:[{surface:'browser',action:'open',input:{mode:'isolated',url:'https://example.org/'}}]};
   const action=actions[id]?.[step];
   if(action){yield {type:'block-end',index:0,block:{type:'tool-call',id:id+'-'+step,name:'computer_use',arguments:JSON.stringify(action)}};yield {type:'finish',reason:{kind:'tool-calls'}};return;}
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
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'test' } });
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
      ...(id === 'ordinary' ? {} : { toolAllowlist: ['computer_use'] }),
      approval: { ...approvalDefaults, rules: 'dsh', globalRoot: home },
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
      const text =
        agentId === 'clipboard'
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
          computerOwnerRequest: true,
          directHumanText: text,
        },
      });
      await expect
        .poll(
          async () => (await client!.rpc.request('session.lookup', { sessionId: agentId, inputId: agentId })).terminal,
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
    const transcript = (id: string) => JSON.stringify(requests.filter((r) => r.session === id && !r.system).at(-1));
    expect(transcript('describe')).toContain('list_windows');
    expect(transcript('clipboard')).toContain('SYNTHETIC-CLIPBOARD');
    expect(transcript('clipboard')).toContain('already consumed');
    expect(transcript('unrelated')).toContain('requires a direct owner request');
    expect(await readFile(join(home, 'os-reads'), 'utf8')).toBe('1');
    const reviews = requests.filter((r) => r.system);
    expect(reviews).toHaveLength(1);
    expect(JSON.stringify(reviews)).toContain('host_observation');
    if (process.env.NANO_COMPUTER_EVIDENCE) {
      await mkdir(process.env.NANO_COMPUTER_EVIDENCE, { recursive: true });
      await copyFile(evidence, join(process.env.NANO_COMPUTER_EVIDENCE, 'requests.jsonl'));
    }
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 60_000);
