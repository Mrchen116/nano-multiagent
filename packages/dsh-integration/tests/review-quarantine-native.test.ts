import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('quarantines an actual native Guardian with an uncooperative late stream and never executes its grant', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-native-quarantine-'));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    await writeFile(join(home, 'fixture.mjs'), `
import {appendFile,writeFile,readFile} from 'node:fs/promises';
export const name='quarantine-fixture';export const inject=['llm','tools','codexApproval'];
export function apply(ctx){
 const turns=new Set();let reviews=0;
 ctx.on('agent/disposed',async({agent})=>{if(String(agent.id).startsWith('nano-codex-'))await writeFile(process.env.DSH_HOME+'/drained','disposed');});
 ctx.tools.register({name:'fixture_effect',description:'Record actual side effect',parameters:{type:'object',properties:{marker:{type:'string'}}},output:{schema:{},render:(_a,v)=>[{type:'text',text:v}]},async execute(args){await appendFile(process.env.DSH_HOME+'/effects',args.marker+'\\n');return 'done';}});
 ctx.on('llm/stream',async function*(o){
  if(o.model==='review'){
   await appendFile(process.env.DSH_HOME+'/reviews','started\\n');
   if(++reviews===1){
    // Deliberately ignore AbortSignal and delay iterator.return, while still using
    // the real native Agent/whenIdle/dispose and the production five-second cleanup.
    await new Promise(resolve=>setTimeout(resolve,12000));
    await writeFile(process.env.DSH_HOME+'/late','late allow');
   }
   yield{type:'block-end',index:0,block:{type:'text',text:'{"outcome":"allow"}'}};yield{type:'finish',reason:{kind:'stop'}};return;
  }
  const human=o.messages.findLast(message=>message.role==='user'&&message.source?.kind==='nano-human');
  const marker=human.content[0].text;
  if(!turns.has(human.id)){turns.add(human.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:marker,name:'fixture_effect',arguments:JSON.stringify({marker})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
  yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 100000 }, { id: 'review', contextWindow: 100000, reasoningEfforts: { low: 'low' } }] } } } }, { insert: [{ id: 'quarantine-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: value => logs += value });
    const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'main', mode: 'global', approval: { ...approvalDefaults, globalRoot: home, rules: 'codex', reviewer: { provider: 'fixture', model: 'review' } } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    await client.rpc.request('session.ensure', { sessionId: 'parent', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
    const submit = async (id: string) => client!.rpc.request('session.submit', { sessionId: 'parent', inputId: id, mode: 'followup', content: [{ type: 'text', text: id }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id } });
    const terminal = async (id: string) => (await client!.rpc.request('session.lookup', { sessionId: 'parent', inputId: id }) as any).terminal;
    const observe = async () => await client!.rpc.request('session.observe', { sessionId: 'parent' }) as any;
    await submit('first');
    await expect.poll(() => readFile(join(home, 'reviews'), 'utf8').catch(() => ''), { timeout: 10000 }).toBe('started\n');
    await client.rpc.request('session.cancel', { sessionId: 'parent' });
    await expect.poll(() => terminal('first'), { timeout: 10000 }).toBeTruthy();
    expect((await observe()).approvals.find((row: any) => row.callId === 'first')).toMatchObject({ decision: 'cancelled', recovery: { finalRoute: 'cancel', retriesUsed: 0 } });
    await submit('during-quarantine');
    await expect.poll(() => terminal('during-quarantine'), { timeout: 5000 }).toBeTruthy();
    const rejected = (await observe()).approvals.find((row: any) => row.callId === 'during-quarantine' && row.recovery);
    expect(rejected).toMatchObject({ decision: 'no_verdict', recovery: { terminalReason: 'cleanup_unavailable' } });
    expect(await readFile(join(home, 'reviews'), 'utf8')).toBe('started\n');
    await expect.poll(() => readFile(join(home, 'late'), 'utf8').catch(() => ''), { timeout: 10000 }).toBe('late allow');
    // Wait on actual native disposal, not the fixture's earlier late-result marker.
    await expect.poll(() => readFile(join(home, 'drained'), 'utf8').catch(() => ''), { timeout: 5000 }).toBe('disposed');
    await submit('after-drain');
    await expect.poll(() => terminal('after-drain'), { timeout: 10000 }).toBeTruthy();
    expect(await readFile(join(home, 'effects'), 'utf8')).toBe('after-drain\n');
    expect((await observe()).approvals.filter((row: any) => ['first', 'during-quarantine'].includes(row.callId)).every((row: any) => row.decision !== 'allow')).toBe(true);
  } catch (error) {
    const events = client ? await client.rpc.request('session.observe', { sessionId: 'parent' }).catch(() => null) : null;
    throw new Error(`${String(error)}\n${logs}\n${JSON.stringify(events)}`, { cause: error });
  } finally {
    if (client) await client.shutdown();
    // The exact temporary allocation belongs to this test, never the parent checkout.
    await rm(home, { recursive: true, force: true });
  }
}, 35000);
