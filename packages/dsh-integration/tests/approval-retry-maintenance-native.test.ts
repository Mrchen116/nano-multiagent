import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

type Row = Record<string, any>;
function respond(res: ServerResponse, text: string, tool?: { name: string; input: Row }) {
  res.writeHead(200, { 'content-type': 'text/event-stream' });
  const emit = (type: string, data: Row) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
  emit('message_start', { message: { id: 'fixture', type: 'message', role: 'assistant', model: 'fixture', content: [], stop_reason: null, usage: { input_tokens: 7, output_tokens: 0 } } });
  emit('content_block_start', { index: 0, content_block: tool ? { type: 'tool_use', id: 'fixture-call', name: tool.name, input: {} } : { type: 'text', text } });
  if (tool) emit('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(tool.input) } });
  emit('content_block_stop', { index: 0 });
  emit('message_delta', { delta: { stop_reason: tool ? 'tool_use' : 'end_turn', stop_sequence: null }, usage: { output_tokens: 3 } });
  emit('message_stop', {}); res.end();
}

it.each(['cancel_guardian', 'cancel_maintenance'] as const)('separates real host maintenance from Guardian recovery: %s', async direction => {
  const home = await mkdtemp(join(tmpdir(), 'nano-maintenance-guardian-'));
  const root = 'maintenance-root';
  const wire: Row[] = []; const counts = new Map<string, number>();
  const held = new Map<string, ServerResponse>();
  const closed = new Set<string>();
  let k1 = ''; let client: RuntimeClient | undefined; let logs = ''; let observation: Row | undefined;
  let finalFacts: Row | undefined; let finalRuns: Row[] = []; let exit: unknown; let passed = false; let forcedCleanup = false;
  const skill = (name: string) => ({ action: 'create', name, content: `---\nname: ${name}\ndescription: Fixture evidence\n---\nPreserve the actual successful step.` });
  const readRows = async (): Promise<Row[]> => (await readFile(join(home, 'capture.jsonl'), 'utf8').catch(() => '')).split('\n').slice(0, -1).filter(Boolean).map(line => JSON.parse(line));
  const workspaceInstruction = (messages: Row[]) => messages.find(message => message.role === 'user' && message.source?.kind === 'agent-instructions' && JSON.stringify(message.content).includes('WORKSPACE_INSTRUCTION_BOUNDARY'));
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw); const session = String(req.headers['x-agent-session-id']);
    const ordinal = (counts.get(session) ?? 0) + 1; counts.set(session, ordinal);
    const row: Row = { session, ordinal, model: body.model, rootHeader: req.headers['x-session-id'], time: Date.now(), body };
    wire.push(row);
    res.on('close', () => { row.closedAt = Date.now(); closed.add(`${session}:${ordinal}`); });
    res.on('error', error => { row.responseError = String(error); });
    if (body.model === 'review') {
      const previous = wire.filter(item => item.model === 'review').length;
      if (previous === 1) {
        row.status = 503; row.requestId = 'G-1'; row.retryAfter = 1;
        res.writeHead(503, { 'content-type': 'application/json', 'retry-after': '1', 'request-id': 'G-1' });
        res.end(JSON.stringify({ type: 'error', error: { type: 'overloaded_error', message: 'controlled Guardian failure' } }));
      } else { row.status = 200; respond(res, '{"outcome":"allow"}'); }
      return;
    }
    row.status = 200;
    if (session === root) {
      if (ordinal === 2) respond(res, '', { name: 'fixture_effect', input: { marker: direction } });
      else respond(res, 'main finished');
      return;
    }
    const instruction = JSON.stringify(body.messages);
    if (!instruction.includes('Review the conversation')) { res.writeHead(400); res.end('not host maintenance'); return; }
    if (!k1) k1 = session;
    if (session !== k1) { row.drain = 'natural K2: no-write normal stop'; respond(res, 'No additional verified update.'); return; }
    if (ordinal === 1) respond(res, '', { name: 'skill_manage', input: skill('retained-method') });
    else { held.set(session, res); row.heldAt = Date.now(); }
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    await writeFile(join(home, 'AGENTS.md'), 'WORKSPACE_INSTRUCTION_BOUNDARY: only verified evidence may become knowledge.');
    // Normal hook, downstream of Codex's prepend hook: its iterator must see the bound sink.
    await writeFile(join(home, 'fixture.mjs'), `
import {appendFile,readFile} from 'node:fs/promises';
import {currentReviewHttpSink} from ${JSON.stringify(new URL('../lib/policy/review-http.js', import.meta.url).href)};
export const name='maintenance-guardian-capture';
export const inject=['llm','tools','agents','systemPrompt','nanoKnowledge','codexApproval'];
export function apply(ctx){
 const log=value=>appendFile(process.env.DSH_HOME+'/capture.jsonl',JSON.stringify({...value,time:Date.now()})+String.fromCharCode(10));
 const ids=new WeakMap();let serial=0;const sinkId=sink=>{if(!sink)return null;if(!ids.has(sink))ids.set(sink,++serial);return ids.get(sink);};
 const system=messages=>messages.filter(m=>m.role==='system').map(m=>m.content.filter(b=>b.type==='text').map(b=>b.text).join('')).join('');
 ctx.on('agent/created',({agent})=>{
  if(agent.id===${JSON.stringify(root)})agent.ctx.systemPrompt.section({name:'fixture-main-system-boundary',order:50,text:'MAIN_SYSTEM_BOUNDARY: host fixture system prefix.',interpolate:false});
  return log({kind:'created',session:agent.id,parent:agent.session.header.parentSession});
 });
 ctx.on('agent/disposed',({agent})=>log({kind:'disposed',session:agent.id}));
 ctx.tools.register({name:'fixture_effect',description:'Record the separately reviewed effect',parameters:{type:'object',properties:{marker:{type:'string'}},required:['marker']},output:{schema:{},render:()=>[{type:'text',text:'effect recorded'}]},async execute(args,exec){await log({kind:'effect',session:exec.agent.id,args});return{};}});
 ctx.on('llm/stream',async function*(o,next){
  const sink=currentReviewHttpSink();const id=sinkId(sink);const agent=ctx.agents.get(o.sessionId);const parent=ctx.agents.get(${JSON.stringify(root)});
  const inherited=agent?.session.header.parentSession===${JSON.stringify(root)};
  const baseline=inherited?{header:parent.session.requestHeader(),system:system(parent.session.deriveMessages())}:undefined;
  await log({kind:'stream-start',session:o.sessionId,parent:agent?.session.header.parentSession,provider:o.provider,model:o.model,effort:o.reasoningEffort,purpose:o.purpose,messages:o.messages,system:system(o.messages),tools:o.tools,sink:id,active:sink?.active(),baseline});
  try{await log({kind:'iterator',phase:'enter',session:o.sessionId,sink:sinkId(currentReviewHttpSink()),active:currentReviewHttpSink()?.active()});yield*next();}
  finally{await log({kind:'stream-end',session:o.sessionId,sink:sinkId(currentReviewHttpSink()),active:sink?.active(),facts:sink?{...sink.facts}:undefined});}
 });
 // Test-host control only: no new product tool, RPC or HTTP cancellation API.
 let seen='';let pending;ctx.effect(()=>{const timer=setInterval(()=>{
  if(pending)return;pending=(async()=>{
   const raw=await readFile(process.env.DSH_HOME+'/host-control.json','utf8').catch(()=>undefined);if(!raw||raw===seen)return;seen=raw;
   const command=JSON.parse(raw);
   if(command.op==='cancel-k1'){
    const active=(await ctx.nanoKnowledge.reviews()).filter(r=>r.status==='running');
    if(active.length!==1||active[0].childSessionId!==command.id)throw new Error('Host cancel target is not exact K1');
    await ctx.nanoKnowledge.cancel('a','skills');
   }
   await log({kind:'control',nonce:command.nonce,op:command.op,session:command.id,registryPresent:!!ctx.agents.get(command.id),reviews:await ctx.nanoKnowledge.reviews()});
  })().catch(error=>log({kind:'control-error',error:String(error)})).finally(()=>{pending=undefined;});
 },10);return async()=>{clearInterval(timer);await pending;};});
}
`);
    const port = (server.address() as { port: number }).port;
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'anthropic-messages', baseURL: `http://127.0.0.1:${port}`, apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main', contextWindow: 200000 }, { id: 'review', contextWindow: 200000, reasoningEfforts: { low: 'low' } }], retryPolicy: { mode: 'normal', maxRetries: 0 } } } },
      { insert: [{ id: 'maintenance-guardian-capture', name: join(home, 'fixture.mjs') }] },
    ]);
    const config = { agentId: 'a', revision: '1', provider: 'fixture', model: 'main', mode: 'global',
      features: { intelligent_ui: false, task_graph: false, memory_curation: false, skill_creation: true }, knowledge: { skillInterval: 1 },
      toolAllowlist: ['read', 'skill_manage', 'list_agents', 'fixture_effect'],
      approval: { ...approvalDefaults, rules: 'codex', globalRoot: home, alwaysAllowTools: ['read', 'skill_manage'], reviewer: { provider: 'fixture', model: 'review' } } };
    const binding = { sessionId: root, agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
    client = new RuntimeClient({ home, cwd: home, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [binding] });
    await client.rpc.request('session.ensure', binding);
    const submit = (inputId: string) => client!.rpc.request('session.submit', { sessionId: root, inputId, mode: 'followup', content: [{ type: 'text', text: inputId }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: inputId } });
    const terminal = async (inputId: string) => (await client!.rpc.request('session.lookup', { sessionId: root, inputId }) as Row).terminal;
    const facts = async () => await client!.rpc.request('knowledge.facts', {}) as Row;
    const control = async (op: string, id: string) => {
      const nonce = `${op}:${id}`; await writeFile(join(home, 'host-control.json'), JSON.stringify({ op, id, nonce }));
      let result: Row | undefined;
      await expect.poll(async () => { result = (await readRows()).find(row => row.kind === 'control' && row.nonce === nonce); return result; }, { timeout: 5000, interval: 10 }).toBeTruthy();
      return result!;
    };
    await submit('seed-owned-evidence');
    await expect.poll(() => terminal('seed-owned-evidence'), { timeout: 10000 }).toBeTruthy();
    await expect.poll(() => held.has(k1), { timeout: 10000 }).toBe(true);
    const first = (await facts()).reviews.find((row: Row) => row.childSessionId === k1);
    expect(first).toMatchObject({ kind: 'skills', status: 'running', rootSessionId: root });
    const k1Review = first.id;
    const before = await readRows();
    const mainSeed = before.filter(row => row.kind === 'stream-start' && row.session === root);
    expect(mainSeed).toHaveLength(1); // This actual request is the last completed parent's baseline.
    const seedInstruction = workspaceInstruction(mainSeed[0]!.messages);
    expect(seedInstruction).toMatchObject({ role: 'user', source: { kind: 'agent-instructions', form: 'instructions' } });
    expect(Array.isArray(seedInstruction!.source.changes)).toBe(true);
    expect(seedInstruction!.source.actorId).toBeUndefined();
    expect(mainSeed[0]!.system).toContain('MAIN_SYSTEM_BOUNDARY'); // Separate public host system section, NOT AGENTS.md.
    const k1Start = before.find(row => row.kind === 'stream-start' && row.session === k1)!;
    expect(k1Start.baseline.header.tools).toEqual(mainSeed[0]!.tools);
    expect(k1Start.baseline.system).toBe(mainSeed[0]!.system);
    expect(k1Start.system).toContain('MAIN_SYSTEM_BOUNDARY');
    const successBeforeCancel = (await facts()).facts.find((row: Row) => row.name === 'retained-method');
    expect(successBeforeCancel).toMatchObject({ kind: 'skills', sessionId: k1, reviewId: k1Review });
    await submit('perform-reviewed-effect');
    await expect.poll(() => wire.filter(row => row.model === 'review').length, { timeout: 10000, interval: 10 }).toBe(1);
    const failedG = wire.find(row => row.model === 'review')!;
    await expect.poll(async () => (await readRows()).some(row => row.kind === 'disposed' && row.session === failedG.session), { timeout: 5000, interval: 10 }).toBe(true);
    if (direction === 'cancel_guardian') {
      await client.rpc.request('session.cancel', { sessionId: root });
      const stillRunning = (await facts()).reviews.find((row: Row) => row.id === k1Review);
      expect(stillRunning.status).toBe('running');
      expect(closed.has(`${k1}:2`)).toBe(false);
      respond(held.get(k1)!, 'Maintenance completed independently.');
    } else {
      await control('cancel-k1', k1);
      await expect.poll(async () => (await readRows()).some(row => row.kind === 'disposed' && row.session === k1), { timeout: 5000, interval: 10 }).toBe(true);
      await expect.poll(() => closed.has(`${k1}:2`), { timeout: 5000, interval: 10 }).toBe(true);
      // The TCP is already closed: this is an attempted late server write, not parser consumption.
      wire.push({ kind: 'late-server-attempt', session: k1, connectionClosed: true, parserConsumed: 'not claimed', time: Date.now() });
      try { respond(held.get(k1)!, '', { name: 'skill_manage', input: skill('after-close') }); }
      catch (error) { wire.push({ kind: 'late-server-write-error', session: k1, error: String(error) }); }
    }
    await expect.poll(() => terminal('perform-reviewed-effect'), { timeout: 10000 }).toBeTruthy();
    await expect.poll(async () => (await facts()).reviews.find((row: Row) => row.id === k1Review)?.status, { timeout: 5000 }).toBe(direction === 'cancel_guardian' ? 'completed' : 'cancelled');
    if (direction === 'cancel_maintenance') {
      // K1 cancellation intentionally leaves counters due; the next completed main turn starts K2.
      await expect.poll(async () => (await facts()).reviews.some((row: Row) => row.childSessionId && row.childSessionId !== k1 && row.status === 'completed'), { timeout: 10000 }).toBe(true);
    }
    await expect.poll(async () => (await readRows()).some(row => row.kind === 'disposed' && row.session === k1), { timeout: 5000 }).toBe(true);
    expect(await control('inspect', k1)).toMatchObject({ registryPresent: false });
    observation = await client.rpc.request('session.observe', { sessionId: root }) as Row;
    const audits = observation.approvals.filter((row: Row) => row.recovery);
    expect(audits).toHaveLength(1);
    const audit = audits[0]!;
    expect(audit).toBeTruthy();
    expect(audit.recovery).toMatchObject({ retriesUsed: 1, formatRetriesUsed: 0, finalRoute: direction === 'cancel_guardian' ? 'cancel' : 'allow' });
    const attempts = audit.recovery.attempts;
    expect(attempts[0]).toMatchObject({ category: 'transient', status: 503, sessionId: failedG.session });
    expect(attempts[0].delayMs).toBeGreaterThan(0); // Without this, cancellation was NOT proven in backoff.
    expect(attempts[0].requests[0].http).toMatchObject({ status: 503, requestId: 'G-1', retryAfterMs: 1000 });
    const gWire = wire.filter(row => row.model === 'review');
    expect(gWire).toHaveLength(direction === 'cancel_guardian' ? 1 : 2);
    expect(attempts).toHaveLength(gWire.length);
    if (direction === 'cancel_guardian') expect(audit.decision).toBe('cancel');
    else {
      expect(audit.decision).toBe('allow');
      expect(attempts[1]).toMatchObject({ budgetMs: 90000, contextMode: 'full-retry' });
      expect(gWire[1]!.session).not.toBe(failedG.session);
      expect(gWire[1]!.time - failedG.time).toBeGreaterThanOrEqual(950);
    }
    finalFacts = await facts();
    expect(finalFacts.facts.filter((row: Row) => row.kind === 'skills').map((row: Row) => row.name)).toEqual(['retained-method']);
    await expect(readFile(join(home, '.nanoassistant/skills/after-close/SKILL.md'), 'utf8')).rejects.toThrow('ENOENT');
    await client.rpc.request('trajectory.prepare', { observerId: root, rootAgentId: 'a', rootSessionId: root, sessionId: root, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 });
    finalRuns = (await client.rpc.request('trajectory.call', { observerId: root, method: 'trajectory/runs' }) as Row).value;
    expect(finalRuns.find(row => row.sessionId === k1)).toMatchObject({ kind: 'skills', provider: 'fork', state: direction === 'cancel_guardian' ? 'completed' : 'cancelled' });
    const naturalK2 = finalFacts.reviews.filter((row: Row) => row.childSessionId && row.childSessionId !== k1);
    for (const nextK of naturalK2) {
      expect(nextK.id).not.toBe(k1Review); expect(nextK.status).toBe('completed');
      expect(finalRuns.find(row => row.sessionId === nextK.childSessionId)).toMatchObject({ state: 'completed', kind: 'skills' });
      await expect.poll(async () => (await readRows()).some(row => row.kind === 'disposed' && row.session === nextK.childSessionId)).toBe(true);
      expect(await control('inspect', nextK.childSessionId)).toMatchObject({ registryPresent: false });
    }
    const descendants = await client.rpc.request('session.descendants', { sessionId: root });
    expect(descendants).toEqual([]);
    expect(observation.events.filter((row: Row) => row.type === 'subagent/catalog').map((row: Row) => row.data.childId)).not.toContain(k1);
    const captured = await readRows();
    expect(captured.filter(row => row.kind === 'control-error')).toEqual([]);
    expect(captured.filter(row => row.kind === 'effect')).toHaveLength(direction === 'cancel_guardian' ? 0 : 1);
    const starts = captured.filter(row => row.kind === 'stream-start');
    const guardians = starts.filter(row => row.model === 'review');
    expect(guardians).toHaveLength(gWire.length);
    expect(new Set(guardians.map(row => row.sink)).size).toBe(guardians.length);
    for (const guardian of guardians) {
      expect(guardian.sink).not.toBeNull(); expect(guardian.active).toBe(true);
      expect(guardian.system).not.toContain('MAIN_SYSTEM_BOUNDARY');
      expect(guardian.tools.map((tool: Row) => tool.name).sort()).toEqual(['guardian_list', 'guardian_read', 'guardian_stat']);
      expect(guardian.session).not.toBe(root); expect(guardian.session).not.toBe(k1);
      const ticks = captured.filter(row => row.kind === 'iterator' && row.session === guardian.session);
      expect(ticks.length).toBeGreaterThan(0);
      expect(ticks.every(row => row.sink === guardian.sink && row.active === true)).toBe(true);
      const end = captured.find(row => row.kind === 'stream-end' && row.session === guardian.session)!;
      expect(end.sink).toBe(guardian.sink);
      if (guardian.session === failedG.session) expect(end.facts).toMatchObject({ status: 503, requestId: 'G-1' });
    }
    const kRequests = starts.filter(row => row.parent === root && row.model === 'main');
    expect(kRequests.length).toBeGreaterThan(0);
    for (const request of kRequests) {
      expect(request.sink).toBeNull();
      const lifetime = captured.filter(row => ['iterator', 'stream-end'].includes(row.kind) && row.session === request.session);
      expect(lifetime.every(row => row.sink === null && row.facts === undefined)).toBe(true);
      if (request.session === k1) {
        expect(request.system).toBe(k1Start.baseline.system);
        expect(request.tools).toEqual(k1Start.baseline.header.tools);
        expect(request.tools.some((tool: Row) => tool.name === 'fixture_effect')).toBe(true); // Visible is not executable.
        const inheritedInstruction = workspaceInstruction(request.messages);
        expect(inheritedInstruction).toBeDefined();
        expect(inheritedInstruction!.id).toBe(seedInstruction!.id);
        expect(inheritedInstruction!.source).toEqual(seedInstruction!.source); // Inherited workspace data, not human consent.
        const maintenance = request.messages.findLast((message: Row) => message.role === 'user' && message.content.some((block: Row) => block.type === 'text' && block.text.startsWith('Review the conversation')));
        expect(maintenance).toBeDefined(); expect(maintenance.source?.actorId).toBeUndefined();
        expect(request.messages.some((message: Row) => message.source?.actorId === 'owner' && JSON.stringify(message.content).includes('seed-owned-evidence'))).toBe(true);
      }
    }
    for (const request of wire.filter(row => row.model)) {
      expect(request.session).toBeTruthy();
      expect(request.rootHeader).toBe(request.model === 'review' ? request.session : root);
      expect(starts.some(row => row.session === request.session && row.model === request.model)).toBe(true);
    }
    for (const request of starts.filter(row => row.session === root)) expect(request.sink).toBeNull();
    for (const [index, request] of gWire.entries()) expect(attempts[index].sessionId).toBe(request.session);
    expect(JSON.stringify(attempts.slice(1))).not.toContain('G-1');
    expect(JSON.stringify(audit.recovery)).not.toContain(k1);
    passed = true;
  } catch (error) {
    throw new Error(`${error}\nWIRE=${JSON.stringify(wire)}\nCAPTURE=${JSON.stringify(await readRows())}\n${logs}`, { cause: error });
  } finally {
    if (client) {
      const own = client;
      const force = setTimeout(() => { forcedCleanup = true; own.process.kill('SIGKILL'); }, 1000);
      try { await own.shutdown(); }
      catch { forcedCleanup = true; own.process.kill('SIGKILL'); }
      finally { exit = await own.exited; clearTimeout(force); }
    }
    server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));
    const output = new URL('../../../output/feat625-maintenance-guardian/', import.meta.url);
    await mkdir(output, { recursive: true });
    await writeFile(new URL(`${direction}.json`, output), JSON.stringify({ direction, scope: 'native fixture, not product Q', assertionsCompleted: passed, home, nativeExit: exit, forcedCleanup, listenerClosed: !server.listening, wire, capture: await readRows(), observation, facts: finalFacts, runs: finalRuns }, null, 2));
    if (!home.startsWith(join(tmpdir(), 'nano-maintenance-guardian-'))) throw new Error('Unexpected owned fixture cleanup path');
    await rm(home, { recursive: true, force: true });
    if (passed) expect(forcedCleanup, 'Owned fixture required forced shutdown; inspect capture').toBe(false);
  }
}, 30000);
