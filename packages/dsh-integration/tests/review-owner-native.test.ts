import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('isolates real native cached/fork/new owners from concurrent main and hand-built CC HTTP streams', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-owner-http-'));
  const records: { name: string; session: string; root: string; time: number; status: number }[] = [];
  const waiting = new Map<string, () => void>();
  const counts = new Map<string, number>();
  function response(res: ServerResponse, name: string, ordinal: number) {
    if ((name === 'A' || name === 'B') && !ordinal) {
      res.writeHead(name === 'A' ? 429 : 503, { 'content-type': 'application/json', 'request-id': `id-${name}`, 'retry-after': name === 'A' ? '2' : 'invalid' });
      res.end(JSON.stringify({ type: 'error', error: { type: 'overloaded_error', message: 'fixture overload' } })); return;
    }
    res.writeHead(200, { 'content-type': 'text/event-stream', 'request-id': `id-${name}` });
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    emit('message_start', { message: { id: 'fixture', role: 'assistant', type: 'message', model: 'review', content: [], usage: { input_tokens: name === 'C' ? 30 : name === 'D' ? 40 : 20, output_tokens: 0 } } });
    emit('content_block_start', { index: 0, content_block: { type: 'text', text: name === 'D' ? '<block>no</block>' : '{"outcome":"allow"}' } });
    emit('content_block_stop', { index: 0 }); emit('message_delta', { delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 5 } }); emit('message_stop', {}); res.end();
  }
  const server = createServer(async (req, res) => {
    let text = ''; for await (const chunk of req) text += chunk;
    const body = JSON.parse(text);
    const last = [...body.messages].reverse().find((message: any) => JSON.stringify(message.content).includes('OWNER_CASE_'));
    const name = JSON.stringify(last?.content).match(/OWNER_CASE_([A-Z0-9]+)/)?.[1] ?? 'UNKNOWN';
    const ordinal = counts.get(name) ?? 0; counts.set(name, ordinal + 1);
    records.push({ name, session: String(req.headers['x-agent-session-id']), root: String(req.headers['x-session-id']), time: Date.now(), status: !ordinal && name === 'A' ? 429 : !ordinal && name === 'B' ? 503 : 200 });
    if (['A', 'B', 'C', 'D', 'M'].includes(name) && !ordinal) {
      waiting.set(name, () => response(res, name, ordinal));
      if (waiting.size === 5) for (const release of waiting.values()) release();
    } else response(res, name, ordinal);
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  let client: RuntimeClient | undefined; let logs = '';
  try {
    const recoveryUrl = new URL('../lib/policy/recovery.js', import.meta.url).href;
    const classifierUrl = new URL('../lib/policy/classifier.js', import.meta.url).href;
    await writeFile(join(home, 'fixture.mjs'), `
import {writeFile} from 'node:fs/promises';
import {ReviewRecovery} from '${recoveryUrl}';
import {classify} from '${classifierUrl}';
import {createUserMessage,ReasoningEffortId} from '${import.meta.resolve('@deepseek-ai/dsh-llm')}';
import {SessionId} from '${import.meta.resolve('@deepseek-ai/dsh-session')}';
export const name='owner-fixture';export const inject=['llm','tools','agents','codexApproval','nanoApproval'];
export function apply(ctx){
 const started=new Set();
 ctx.on('llm/stream',async function*(o,next){
  if(o.model==='driver'){
   if(!started.has(o.sessionId)){started.add(o.sessionId);yield{type:'block-end',index:0,block:{type:'tool-call',id:'orchestrate',name:'fixture_run',arguments:'{}'}};yield{type:'finish',reason:{kind:'tool-calls'}};}
   else{yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};}return;
  }yield* next();
 });
 ctx.tools.register({name:'fixture_run',description:'Run ownership matrix',parameters:{type:'object',properties:{}},output:{schema:{},render:(_a,v)=>[{type:'text',text:v}]},async execute(_args,exec){
  const route={provider:'fixture',model:'review'};const results={};
  const config={agentId:'a',revision:'1',provider:'fixture',model:'driver',mode:'global',approval:${JSON.stringify({ ...approvalDefaults, globalRoot: home, rules: 'codex' })}};
  const handles=[];
  for(const id of ['idle','parallel','other'])handles.push(await ctx.agents.create({sessionId:SessionId(id),meta:{cwd:process.env.DSH_HOME},agentOptions:{provider:'fixture',model:'driver'}}));
  const parent=id=>handles.find(h=>h.agent.id===id).agent;
  const request=(name,id,signal=exec.signal)=>({exec:{...exec,agent:parent(id),callId:name,name:'effect',arguments:{marker:'OWNER_CASE_'+name},signal},config,sources:ctx.nanoApproval.sources,inherited:[],reviewer:route});
  const run=async(name,id,signal)=>{const req=request(name,id,signal);const recovery=new ReviewRecovery(req.exec.signal,name,'codex',route);results[name]={trace:recovery.trace};try{results[name]={result:await ctx.codexApproval.review({...req,recovery})};}catch(error){results[name]={error:error.category??String(error)};}finally{results[name].trace=recovery.finish('test','test');}};
  await run('I','idle');await run('P','parallel');
  const cancelB=new AbortController();
  const b=run('B','parallel',cancelB.signal);
  // B enters first and owns the warmed trunk; A must be a real native seeded fork.
  const a=run('A','parallel');const c=run('C','other');
  const main=await ctx.agents.create({sessionId:SessionId('main-http'),meta:{cwd:process.env.DSH_HOME},agentOptions:{provider:'fixture',model:'main',reasoningEffort:ReasoningEffortId('low')},setup:scope=>{scope.tools.restrict({allow:[]});scope.systemPrompt.section({name:'fixture-main',order:0,text:'Reply once with fixture text',complete:true,interpolate:false});scope.on('system-prompt/assemble',async(_a,_c,next)=>({...await next(),contexts:[],tools:[]}),{prepend:true});scope.on('agent/request',async(_p,next)=>({...await next(),provider:'fixture',model:'main',reasoningEffort:ReasoningEffortId('low')}),{prepend:true});}});handles.push(main);
  const d=(async()=>{const req=request('D','parallel');req.exec.agent=main.agent;req.config={...config,approval:{...config.approval,rules:'nano'}};const recovery=new ReviewRecovery(exec.signal,'D','nano',route);try{results.D={result:await classify(ctx,{...req,recovery})};}finally{results.D.trace=recovery.finish('test','test');}})();
  main.agent.followup(createUserMessage({content:[{type:'text',text:'OWNER_CASE_M'}],source:{kind:'user'}}));
  // Cancel B only after its real typed failure reaches the action retry/backoff trace.
  const deadline=Date.now()+5000;
  while(results.B.trace.attempts[0]?.status!==503){
   if(Date.now()>deadline)break;await new Promise(resolve=>setTimeout(resolve,5));
  }
  cancelB.abort();
  await Promise.all([a,b,c,d,main.agent.whenIdle()]);
  await run('C2','other');
  const idleOwner=[...ctx.codexApproval.owners.values()].find(owner=>owner.handle.agent.id===results.I.result.metadata.sessionId);
  idleOwner.handle.agent.followup(createUserMessage({content:[{type:'text',text:'OWNER_CASE_IDLEFORBIDDEN'}],source:{kind:'user'}}));await idleOwner.handle.agent.whenIdle();
  results.ownerCountBefore=ctx.codexApproval.owners.size;
  for(const handle of handles){await ctx.codexApproval.release(handle.agent.id);await handle.dispose();}
  results.ownerCountAfter=ctx.codexApproval.owners.size;
  await writeFile(process.env.DSH_HOME+'/result.json',JSON.stringify(results));return 'done';
 }});
}`);
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'FIXTURE_KEY', models: ['driver', 'main', 'review'].map(id => ({ id, contextWindow: 100000, reasoningEfforts: { low: 'low' } })) } } } }, { insert: [{ id: 'owner-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { FIXTURE_KEY: 'fixture' }, onLog: text => logs += text });
    const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'driver', mode: 'global', approval: { ...approvalDefaults, globalRoot: home, rules: 'nano', alwaysAllowTools: ['fixture_run'] } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    await client.rpc.request('session.ensure', { sessionId: 'parent', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home });
    await client.rpc.request('session.submit', { sessionId: 'parent', inputId: 'request', mode: 'followup', content: [{ type: 'text', text: 'Run native ownership matrix' }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'request' } });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'parent', inputId: 'request' }) as any).terminal, { timeout: 20000 }).toBeTruthy();
    const result = JSON.parse(await readFile(join(home, 'result.json'), 'utf8'));
    expect(result.A.trace).toMatchObject({ retriesUsed: 1, attempts: [{ status: 429, retryAfterKnown: true }, { outcome: 'verdict' }] });
    expect(result.B.trace.attempts[0]).toMatchObject({ status: 503, retryAfterKnown: false });
    expect(result.B.error).toBeTruthy(); expect(result.B.result).toBeUndefined();
    expect(records.filter(row => row.name === 'B')).toHaveLength(1);
    const a = records.filter(row => row.name === 'A'); expect(a).toHaveLength(2); expect(a[1]!.time - a[0]!.time).toBeGreaterThanOrEqual(1950); expect(a[0]!.session).not.toBe(a[1]!.session);
    for (const name of ['A', 'B', 'C', 'D']) for (const attempt of result[name].trace.attempts) for (const request of attempt.requests) expect(request.requestId).toBe(`id-${name}`);
    expect(result.C.trace.knownUsage).toEqual([expect.objectContaining({ inputTokens: 30 })]);
    expect(result.D.trace.knownUsage).toEqual([expect.objectContaining({ inputTokens: 40 })]);
    expect(result.C2.result.metadata.sessionId).toBe(result.C.result.metadata.sessionId);
    expect(result.C2.trace.reviewId).not.toBe(result.C.trace.reviewId);
    expect(records.find(row => row.name === 'D')?.session).toBe('main-http');
    expect(records.find(row => row.name === 'D')?.session).toBe(records.find(row => row.name === 'M')?.session);
    expect(new Set(['A', 'B', 'C'].map(name => records.find(row => row.name === name)?.session)).size).toBe(3);
    expect(records.some(row => row.name === 'IDLEFORBIDDEN')).toBe(false);
    expect(records.filter(row => row.name === 'M')).toHaveLength(1);
    expect(result.ownerCountBefore).toBeGreaterThanOrEqual(2); expect(result.ownerCountAfter).toBe(0);
  } catch (error) {
    const events = client ? await client.rpc.request('session.observe', { sessionId: 'parent' }).then((value: any) => value.events.filter((event: any) => ['tool/result', 'turn/end'].includes(event.type))).catch(() => null) : null;
    const mainEvents = client ? await client.rpc.request('session.observe', { sessionId: 'main-http' }).then((value: any) => value.events).catch(() => null) : null;
    throw new Error(`${String(error)}\n${logs}\n${JSON.stringify(records)}\n${JSON.stringify(events)}\n${JSON.stringify(mainEvents)}`, { cause: error });
  } finally {
    if (client) await client.shutdown(); server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    // This target is the exact mkdtemp allocation owned by the test.
    await rm(home, { recursive: true, force: true });
  }
}, 30000);
