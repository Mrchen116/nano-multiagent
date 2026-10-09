import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('launches the official profile and cold-recovers a durably accepted input', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-dsh-profile-'));
  const workspace = join(home, 'workspace');
  let client: RuntimeClient | undefined;
  let logs = '';
  const config = {
    protocol: 1,
    agents: [{ agentId: 'test', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash' }],
    bindings: [],
  };
  const binding = { sessionId: 'nano-test-session', agentId: 'test', revision: '1', ownerId: 'test-owner', cwd: workspace };
  try {
    await prepareProfile(home);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    expect(await client.rpc.request('initialize', config)).toMatchObject({ protocol: 1, version: '0.2.1-alpha.1' });
    await client.rpc.request('session.ensure', binding);
    const input = { sessionId: binding.sessionId, inputId: 'stable-input', mode: 'inject',
      content: [{ type: 'text', text: 'retained without waking' }],
      source: { kind: 'system', actorId: 'test-owner', channel: 'test', messageId: 'upstream-1' } };
    expect(await client.rpc.request('session.submit', input)).toMatchObject({ accepted: true, pending: true, durable: true });
    // A crash after the durable ACK preserves the pending inbox entry.
    client.process.kill('SIGKILL');
    await client.exited;
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', config);
    await client.rpc.request('session.ensure', binding);
    expect(await client.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: input.inputId })).toMatchObject({ accepted: true, pending: true });
    await client.rpc.request('session.submit', input);
    const result = await client.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: { type: string; data: { inserted?: { id: string }[] } }[] };
    expect(result.events.flatMap(event => event.data.inserted ?? []).filter(message => message.id === input.inputId)).toHaveLength(1);
    await client.shutdown();
    // Native owner disposal cancels pending work; that cancellation must survive.
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', config);
    await client.rpc.request('session.ensure', binding);
    expect(await client.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: input.inputId })).toMatchObject({
      accepted: true, pending: false, terminal: { kind: 'cancelled-before-consumption' },
    });
    await client.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\nRuntime stderr:\n${logs}`, { cause: error });
  } finally {
    if (client && client.process.exitCode === null) { client.process.kill('SIGKILL'); await client.exited; }
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);


it('emits liveness from a real running native Agent while the model is silent', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-liveness-'));
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'quiet.mjs'), `export const name='quiet'; export const inject=['llm']; export function apply(ctx){ctx.on('llm/stream',async function*(o){await new Promise(resolve=>{const timer=setTimeout(resolve,60000);o.signal.addEventListener('abort',()=>{clearTimeout(timer);resolve();},{once:true});});o.signal.throwIfAborted();yield{type:'finish',reason:{kind:'stop'}};});}`);
    await prepareProfile(home, [{insert:[{id:'quiet',name:join(home,'quiet.mjs')}]}]);
    client = new RuntimeClient({home,cwd:home});
    const notifications: {method: string; data: unknown}[] = [];
    client.rpc.onNotification((method,data)=>notifications.push({method,data}));
    await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}],bindings:[]});
    await client.rpc.request('session.ensure',{sessionId:'quiet',agentId:'a',revision:'1',ownerId:'owner',cwd:home});
    await client.rpc.request('session.submit',{sessionId:'quiet',inputId:'input',mode:'followup',content:[{type:'text',text:'Wait'}],source:{kind:'human',actorId:'owner',channel:'test',messageId:'input'}});
    await expect.poll(()=>notifications.filter(item=>item.method==='session.liveness'),{timeout:20000}).toEqual([{method:'session.liveness',data:{sessionId:'quiet'}}]);
    expect(await client.rpc.request('session.observe',{sessionId:'quiet'})).toMatchObject({status:'running'});
    await client.shutdown(); client=undefined;
  } finally {
    if(client){client.process.kill('SIGKILL');await client.exited;}
    await rm(home,{recursive:true,force:true});
  }
},30000);
