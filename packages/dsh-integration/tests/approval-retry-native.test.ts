import { expect, it } from 'vitest';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { writeSyntheticContextEvidence } from './synthetic-context-evidence.js';

it('recovers at the real review seams without native always retries, duplicate tools or evidence drift, and reopens observe audit', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-review-retry-'));
  let client: RuntimeClient | undefined; let logs = '';
  const cases = [
    { id: 'cc-finish', rules: 'nano', failures: ['SERVER'], categories: ['service', 'allow'] },
    { id: 'cc-exhaust', rules: 'nano', failures: ['SERVER', 'SERVER', 'SERVER'], categories: ['service', 'service', 'service'] },
    { id: 'cc-mixed', rules: 'nano', failures: ['invalid', 'SERVER'], categories: ['invalid', 'service', 'allow'] },
    { id: 'cc-stage', rules: 'nano', failures: ['stage-deny', 'SERVER'], categories: ['service', 'allow'] },
    { id: 'guardian-finish', rules: 'codex', failures: ['SERVER'], categories: ['service', 'allow'] },
    { id: 'guardian-exhaust', rules: 'codex', failures: ['SERVER', 'SERVER', 'SERVER'], categories: ['service', 'service', 'service'] },
    { id: 'guardian-stream', rules: 'codex', seam: 'stream', failures: ['TRANSPORT', 'TIMEOUT'], categories: ['transport', 'timeout', 'allow'] },
    { id: 'guardian-preparation', rules: 'codex', seam: 'preparation', failures: ['SERVER', 'SERVER', 'SERVER'], categories: ['service', 'service', 'service'] },
    { id: 'guardian-mixed', rules: 'codex', failures: ['SERVER', 'invalid', 'invalid'], categories: ['service', 'invalid', 'invalid'] },
    { id: 'guardian-auth', rules: 'codex', failures: ['AUTH'], categories: ['auth'] },
    { id: 'guardian-cancel-preparation', rules: 'codex', seam: 'preparation', failures: [], categories: ['cancel'], cancel: 'preparation' },
    { id: 'cc-cancel-active', rules: 'nano', failures: [], categories: ['cancel'], cancel: 'active' },
    { id: 'cc-cancel-backoff', rules: 'nano', failures: ['SERVER'], categories: ['service'], cancel: 'backoff' },
    { id: 'unattended-explicit', rules: 'nano', failures: ['SERVER', 'SERVER', 'SERVER'], categories: ['service', 'service', 'service'], fallback: 'allow' },
  ];
  try {
    await writeFile(join(home, 'fixture.mjs'), `
import {appendFile} from 'node:fs/promises';
import {LlmError} from '${import.meta.resolve('@deepseek-ai/dsh-llm')}';
export const name='retry-fixture';export const inject=['llm','tools','agents'];
export function apply(ctx){
 const cases=${JSON.stringify(cases)};const steps=new Set();const requests=new Map();const effects=new Map();let active;let reviewerSession;
 const log=(file,row)=>appendFile(process.env.DSH_HOME+'/'+file,JSON.stringify(row)+'\\n');
 ctx.on('agent/disposed',({agent})=>{for(const event of agent.session.snapshotEvents())if(event.type==='llm/retry')void log('native-retries.jsonl',event);});
 ctx.tools.register({name:'fixture_effect',description:'record one mutation',parameters:{type:'object',properties:{scenario:{type:'string'}},required:['scenario']},output:{schema:{},render:(_a,v)=>[{type:'text',text:v}]},async execute(args){effects.set(args.scenario,(effects.get(args.scenario)||0)+1);await log('effects.jsonl',args);return 'executed';}});
 ctx.on('agent/request',async({agent,signal},next)=>{
  if(agent.id.startsWith('nano-codex-'))reviewerSession=agent.id;
   if(agent.id.startsWith('nano-codex-')&&active.seam==='preparation'){
   const n=requests.get(active.id)||0;requests.set(active.id,n+1);
   await log('requests.jsonl',{scenario:active.id,seam:'preparation',sessionId:agent.id,effects:effects.get(active.id)||0});
   if(active.cancel==='preparation'){await new Promise(resolve=>signal.addEventListener('abort',resolve,{once:true}));signal.throwIfAborted();}
   const code=active.failures[n];if(code)throw new LlmError('failure must not become owner evidence',code,{status:503});
  }
  return next();
 },{prepend:true});
 ctx.on('llm/stream',async function*(o){
  if(o.model==='review'){
   const n=requests.get(active.id)||0;requests.set(active.id,n+1);
   await log('requests.jsonl',{scenario:active.id,sessionId:reviewerSession||active.id,callId:active.id+'-tool',ordinal:n+1,seam:active.seam||'finish',model:o.model,provider:o.provider,system:o.system,messages:o.messages,tools:o.tools,options:{reasoningEffort:o.reasoningEffort,maxTokens:o.maxTokens,temperature:o.temperature,toolChoice:o.toolChoice},effects:effects.get(active.id)||0});
   const code=active.failures[n];
   yield{type:'usage',usage:{inputTokens:11+n,outputTokens:3}};
   if(active.cancel==='active'){await new Promise(resolve=>o.signal.addEventListener('abort',resolve,{once:true}));}
   if(code&&code!=='invalid'&&code!=='stage-deny'){
    if(active.seam==='stream')throw new LlmError('failure must not become owner evidence',code,{status:503});
    yield{type:'finish',reason:{kind:'error',failure:{code,message:'failure must not become owner evidence',status:503}}};return;
   }
   const text=code==='invalid'?'malformed':code==='stage-deny'?'<block>yes</block><reason>need full review</reason>':active.rules==='nano'?'<block>no</block>':JSON.stringify({outcome:'allow',risk_level:'low',user_authorization:'high',rationale:'authorized exact action'});
   yield{type:'block-end',index:0,block:{type:'text',text}};yield{type:'finish',reason:{kind:'stop'}};return;
  }
  const human=o.messages.findLast(m=>m.role==='user'&&m.source?.kind?.startsWith('nano-'));
  if(!steps.has(human.id)){
   steps.add(human.id);active=cases.find(c=>c.id===human.content[0].text);reviewerSession=undefined;
   yield{type:'block-end',index:0,block:{type:'tool-call',id:active.id+'-tool',name:'fixture_effect',arguments:JSON.stringify({scenario:active.id})}};
   yield{type:'finish',reason:{kind:'tool-calls'}};return;
  }
  await log('main-results.jsonl',{scenario:active.id,messages:o.messages});
  yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: {
      api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', retryPolicy: { mode: 'always', backoff: { initialDelayMs: 1 } },
      models: [{ id: 'main', contextWindow: 100000 }, { id: 'review', contextWindow: 100000, reasoningEfforts: { low: 'low' } }],
    } } } }, { insert: [{ id: 'retry-fixture', name: join(home, 'fixture.mjs') }] }]);
    const agents = cases.map(c => ({ agentId: c.id, revision: '1', mode: 'global', provider: 'fixture', model: 'main',
      approval: { ...approvalDefaults, rules: c.rules, globalRoot: home, unattendedFallback: c.fallback ?? 'deny', reviewer: { provider: 'fixture', model: 'review' } } }));
    const bindings = cases.map(c => ({ sessionId: c.id, agentId: c.id, revision: '1', ownerId: 'owner', cwd: home }));
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings: [] });
    const observed = new Map<string, any[]>();
    for (const c of cases) {
      await client.rpc.request('session.ensure', bindings.find(b => b.sessionId === c.id));
      await client.rpc.request('session.submit', { sessionId: c.id, inputId: c.id, mode: 'followup', content: [{ type: 'text', text: c.id }],
        source: c.fallback ? { kind: 'system', channel: 'heartbeat', messageId: c.id } : { kind: 'human', actorId: 'owner', channel: 'test', messageId: c.id } });
      if (c.cancel) {
        await expect.poll(async () => (await readFile(join(home, 'requests.jsonl'), 'utf8')).includes(`"scenario":"${c.id}"`)).toBe(true);
        await client.rpc.request('session.cancel', { sessionId: c.id });
      }
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: c.id, inputId: c.id }) as any).terminal, { timeout: 10000 }).toBeTruthy();
      if (c.cancel) await expect.poll(async () => (await client!.rpc.request('session.observe', { sessionId: c.id }) as any).approvals.some((a: any) => a.source === 'classifier_cancel')).toBe(true);
      const observation: any = await client.rpc.request('session.observe', { sessionId: c.id });
      observed.set(c.id, observation.approvals);
      const audit = observation.approvals.find((a: any) => a.retry);
      expect(audit, c.id).toMatchObject({ callId: c.id + '-tool', total: 0, consecutive: 0 });
      expect(audit.retry.attempts.map((a: any) => a.category), c.id).toEqual(c.categories);
      expect(audit.retry.extraUsed).toBe(c.categories.length - 1);
      if (c.cancel) expect(audit).toMatchObject({ source: 'classifier_cancel', decision: 'cancel', retry: { finalCategory: 'cancel' } });
      expect(observation.events.filter((e: any) => e.type === 'tool/call')).toHaveLength(1);
      if (c.id === 'cc-stage') expect(audit.retry.attempts[0].children.map((s: any) => s.stage)).toEqual([1, 2]);
      if (c.seam !== 'preparation') expect(audit.retry.attempts.every((a: any) => a.children.some((child: any) => child.usage?.inputTokens >= 11))).toBe(true);
      else expect(audit.retry.attempts.every((a: any) => !('usage' in a))).toBe(true);
      if (c.fallback) expect(observation.approvals.at(-1)).toMatchObject({ source: 'unattended', decision: 'allow' });
    }
    const lines = async (name: string) => (await readFile(join(home, name), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const requests = await lines('requests.jsonl');
    for (const c of cases) {
      const actual = requests.filter(r => r.scenario === c.id);
      expect(actual, c.id).toHaveLength(c.categories.length + (c.id === 'cc-stage' ? 1 : 0));
      expect(actual.every(r => r.effects === 0)).toBe(true);
      const inputs = actual.filter(r => r.messages);
      expect(JSON.stringify(inputs)).not.toContain('failure must not become owner evidence');
      if (c.rules === 'nano' && c.id !== 'cc-stage') expect(new Set(inputs.map(r => JSON.stringify(r.messages))).size).toBe(1);
      if (c.rules === 'codex') {
        for (const input of inputs) expect(input.tools?.map((tool: any) => tool.name).sort(), c.id).toEqual(['guardian_list', 'guardian_read', 'guardian_stat']);
        const texts = inputs.map(r => r.messages.findLast((m: any) => m.role === 'user').content);
        expect(new Set(texts.map(x => JSON.stringify(x))).size).toBeLessThanOrEqual(1);
      }
    }
    const effectRows = await lines('effects.jsonl');
    expect(effectRows.map(r => r.scenario)).toEqual(cases.filter(c => c.categories.at(-1) === 'allow' || c.fallback).map(c => c.id));
    await expect(readFile(join(home, 'native-retries.jsonl'), 'utf8')).rejects.toThrow();
    const main = await lines('main-results.jsonl');
    expect(main.filter(r => r.scenario.endsWith('exhaust')).every(r => JSON.stringify(r.messages).includes('Automatic reviewer unavailable'))).toBe(true);
    const ids = [...observed.values()].flat().filter(a => a.retry).map(a => a.retry.reviewId);
    expect(new Set(ids).size).toBe(cases.length);
    await client.shutdown(); client = undefined;
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents, bindings });
    for (const c of cases) {
      const reopened: any = await client.rpc.request('session.observe', { sessionId: c.id });
      expect(reopened.approvals).toEqual(observed.get(c.id));
    }
    // Optional synthetic acceptance artifact; normal regression runs leave no files.
    if (process.env.NANO_REVIEW_EVIDENCE_PATH) await writeSyntheticContextEvidence(process.env.NANO_REVIEW_EVIDENCE_PATH, {
      seam: 'isolated RuntimeClient; synthetic llm stream/native preparation; provider retryPolicy=always; NOT provider wire or live product data',
      syntheticOnly: true, schemaVersion: 2,
      fixtureSourceSha256: createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'),
      productImplementation: process.env.NANO_REVIEW_IMPLEMENTATION_VERSION ?? 'unrecorded',
      scenarios: cases.map(c => ({ id: c.id, requests: requests.filter(r => r.scenario === c.id).length,
        effects: effectRows.filter(r => r.scenario === c.id).length,
        requestsBeforeEffect: requests.filter(r => r.scenario === c.id).map(r => r.effects), approvals: observed.get(c.id),
        inputSnapshots: requests.filter(r => r.scenario === c.id && r.messages).map(r => ({
          model: r.model, provider: r.provider, sessionId: r.sessionId, callId: r.callId, requestOrdinal: r.ordinal,
          systemSha256: createHash('sha256').update(r.system ?? '').digest('hex'),
          messagesSha256: createHash('sha256').update(JSON.stringify(r.messages)).digest('hex'),
          // Null top-level system is meaningful: Guardian may deliver policy in messages.
          composition: { system: r.system ?? null, messages: r.messages, tools: r.tools ?? [], options: r.options },
          userContent: r.messages.findLast((m: any) => m.role === 'user')?.content,
        })),
        finalToolResultMessage: main.find(r => r.scenario === c.id)?.messages.findLast((m: any) => m.role === 'tool'),
        finalToolResult: main.find(r => r.scenario === c.id)?.messages.findLast((m: any) => m.role === 'tool')?.content,
      })), reopenedObserveIdentical: true,
    });
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client) await client.shutdown(); await rm(home, { recursive: true, force: true }); }
}, 60000);
