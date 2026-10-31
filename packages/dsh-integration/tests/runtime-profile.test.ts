import { mkdtemp, rm, writeFile, readFile, readlink, symlink, unlink, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('refreshes retained profile links and cold-recovers a durably accepted input', async () => {
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
    const modules = join(home, 'profiles', 'nano', 'node_modules');
    const links = [join(modules, '@nano', 'dsh-integration'), join(modules, '@deepseek-ai', 'dsh-base')];
    const targets = await Promise.all(links.map(path => readlink(path)));
    const previous = join(home, 'previous-install');
    await mkdir(previous);
    // A retained checkout and a deleted checkout must both be refreshed.
    for (const [i, path] of links.entries()) {
      await unlink(path);
      await symlink(i === 0 ? previous : join(home, 'deleted-install'), path, 'dir');
    }
    const retained = join(home, 'session-state.txt');
    await writeFile(retained, 'persistent session state');
    await prepareProfile(home);
    expect(await Promise.all(links.map(path => readlink(path)))).toEqual(targets);
    expect(await readFile(retained, 'utf8')).toBe('persistent session state');
    await prepareProfile(home);
    expect(await Promise.all(links.map(path => readlink(path)))).toEqual(targets);
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
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
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', config);
    await client.rpc.request('session.ensure', binding);
    expect(await client.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: input.inputId })).toMatchObject({ accepted: true, pending: true });
    await client.rpc.request('session.submit', input);
    const result = await client.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: { type: string; data: { inserted?: { id: string }[] } }[] };
    expect(result.events.flatMap(event => event.data.inserted ?? []).filter(message => message.id === input.inputId)).toHaveLength(1);
    await client.shutdown();
    // Native owner disposal cancels pending work; that cancellation must survive.
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
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
    registerNoopTaskHosts(client);
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


it.each(['file', 'directory'])('preserves a non-symlink %s at a managed profile entry', async kind => {
  const home = await mkdtemp(join(tmpdir(), 'nano-profile-conflict-'));
  try {
    await prepareProfile(home);
    const entry = join(home, 'profiles', 'nano', 'node_modules', '@nano', 'dsh-integration');
    await unlink(entry);
    if (kind === 'directory') await mkdir(entry);
    const retained = kind === 'directory' ? join(entry, 'keep.txt') : entry;
    await writeFile(retained, 'owner content');
    await expect(prepareProfile(home)).rejects.toThrow();
    expect(await readFile(retained, 'utf8')).toBe('owner content');
  } finally { await rm(home, {recursive:true, force:true}); }
});
