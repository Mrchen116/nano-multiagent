# Independent review witnesses — refactor-679-agent-context-optimization

## Scope and evidence boundary

- Reviewer: fresh independent context; approved inheritance of current model because the SDK cannot choose model/effort. This is **not a claim that `gpt-6.1-sol/high` was configured**.
- Branch `unit/refactor-679`; baseline HEAD `4b27d962c1cc09a27a567619bd5cabc3db2ee934`; implementation dirty and includes untracked files. Upstream is `unit/feat-676`, not main.
- **Latest:** the scoped Node24 repair recheck in [C/D](<review-witnesses.md#c-scoped-node24-repair-recheck-not-a-final-gate>) supersedes the original failures for the paths actually rerun. It is not a final gate verdict. Sections A/B and their original fingerprints remain historical pre-fix witnesses. No production/test/spec fixes, full-regression reruns, production access or HTTP services were performed by this reviewer.
- Historical probes A/B used `/opt/homebrew/bin/node` v25.8.2; every scoped repair probe C/D instead used the explicitly required Node v24.22.1. Native runtime/profile cleanup and background-job collection are recorded per round below.
- Probe A uses the actual native DSH admission/execution path and the actual product TaskContext, with only the disconnected relay and provider transport controlled. It is **not** real-model behavior evidence. Probe B exercises actual GlobalAgent.call and InboxStore, with a controlled public-read authorization response.

## A. Independent external input incorrectly requires IM Task synchronization

### Preconditions and sequence

1. Instantiate actual [RuntimeClient](<../../../packages/dsh-integration/src/client.ts>) with a temporary native profile. Insert an `llm/stream` observer that records every provider invocation, then returns a normal text response.
2. Configure an ordinary `single_thread` Agent with `features.task_graph=false`. Bind its root to an external Feishu conversation. Actual NodeStore and InboxStore are empty: no Task, task context mappings, unread system messages, or continuation.
3. Wire `product.task_context.prepare/commit` to actual [TaskContext](<../../../packages/personal-assistant/src/task-context.ts>). Its relay has `ready=false`; `request` increments a counter then throws `CENTER_OFFLINE_NO_TASKS`. Source refresh is an ordinary-Agent no-op.
4. Submit native followup `feishu-ordinary-no-task` with `source={kind:human,actorId:owner,channel:feishu,messageId:feishu-ordinary-no-task}` and text `Just answer: what is 2+2? No Task requested.`
5. Await that native turn reaching idle; inspect provider records and `session.lookup`.

### Observed output

```json
{
  "case": "ordinary-feishu-input-task-feature-disabled-center-offline",
  "node": "v25.8.2",
  "task_feature": false,
  "inbox_unread": [],
  "task_context_rows": [],
  "prepareCalls": 1,
  "relayCalls": 1,
  "providerCalls": 0,
  "status": "idle",
  "lookup": {
    "accepted": true,
    "acceptedSeq": 3,
    "pending": false,
    "turn": 1,
    "terminal": {
      "kind": "error",
      "error": {"message": "CENTER_OFFLINE_NO_TASKS", "code": "UNKNOWN"}
    },
    "turns": [1]
  }
}
```

This is the unconditional root [pre-step request](<../../../packages/dsh-integration/src/task-context.ts#L21-L25>) reaching unconditional [authoritative synchronization](<../../../packages/personal-assistant/src/task-context.ts#L30-L71>). It proves loss of the existing independent-external-input availability boundary. It does not argue that stale Task originals or automatic Task continuations should run offline; those must remain pending without a retry loop. See [SPEC](<../../../SPEC.md#L22>) and the [approved degradation rule](<design.md#L157-L191>).

## B. Revoked, never-consumed Task first appears through an old unread cursor

### Minimal reproducer

Run from the worktree root against the existing build (no build or service is needed):

```js
// node --input-type=module
import assert from "node:assert/strict";
import { InboxStore } from "./packages/personal-assistant/lib/inbox.js";
import { NodeStore } from "./packages/personal-assistant/lib/store.js";
import { GlobalAgent } from "./packages/personal-assistant/lib/global-agent.js";
const inbox = new InboxStore(":memory:"), store = new NodeStore(":memory:", "owner");
const agent = {agentId:"a", workspace:"/tmp/reviewer-only", mode:"global",
  revision:"1", provider:"p", model:"m"};
store.bind({agentId:"a", sessionId:"main", conversationId:"global:a",
  ownerId:"owner", cwd:agent.workspace, revision:"1"});
const product = new GlobalAgent({nodeId:"node", ownerId:"owner", agents:[agent], store, inbox,
  runtime:{onNotification:()=>()=>{}, request:async()=>({})},
  relay:{request:async()=>({type:"conversation.query.result", payload:{ok:true, result:{
    type:"group", visibility:"public", name:"Public read-only source",
    can_read:true, can_write:false, channel:"web"}}})},
  image:async()=>"", onError:error=>{throw error;}});
const input = (id, content) => ({agent_id:"a", conversation_id:"public-chat",
  relay_task_id:id, idempotency_key:id, metadata:{conversation_type:"group"},
  message:{id, content, sender_type:"system", sender_user_id:"system", attachments:[]}});
const task = {...input("withdrawn-task", "UNCONSUMED_WITHDRAWN_TASK_TITLE_AND_REQUIREMENTS"),
  metadata:{conversation_type:"group", task_context:true},
  message:{...input("withdrawn-task", "UNCONSUMED_WITHDRAWN_TASK_TITLE_AND_REQUIREMENTS").message,
    system_notice:{kind:"task_graph", attention_actor_ids:["a"]}}};
const read = (id,args) => product.call({method:"inbox", args:{action:"read",...args},
  operationId:id, callId:id, sessionId:"main", rootSessionId:"main", agentId:"a", ownerId:"owner"});
try {
  inbox.receive(input("ordinary-before-task", "ordinary first page"), true);
  inbox.receive(task, true);
  const first = await read("first", {target:"public-chat", limit:1});
  assert(first.next_cursor);
  assert(!JSON.stringify(first).includes("UNCONSUMED_WITHDRAWN"));
  assert(inbox.commitRead("main", "first", [{type:"text",text:JSON.stringify(first)}], false, 1));
  inbox.revokeSystemContext("a", "withdrawn-task");
  assert.equal(inbox.check("a").sources.length, 0);
  const after = await read("second", {target:"public-chat",cursor:first.next_cursor,limit:1});
  assert(JSON.stringify(after).includes("UNCONSUMED_WITHDRAWN_TASK_TITLE_AND_REQUIREMENTS"));
  console.log(JSON.stringify({first, after_revoke:inbox.check("a"), replayed_unconsumed_task:after}));
} finally {await product.stop(); inbox.close(); store.close();}
```

### Observed facts

- First saved page contains **only** `ordinary-before-task`; committing it leaves exactly one unread Task.
- `revokeSystemContext(a,withdrawn-task)` leaves `check(a).sources=[]`.
- Both actual Global read calls successfully obtain public-source `info`; normal read permission does not restore Task eligibility.
- The second read, with the old cursor and a fresh call ID, returns the full `withdrawn-task` content `UNCONSUMED_WITHDRAWN_TASK_TITLE_AND_REQUIREMENTS`.
- The Task was never on the first saved page, never committed by an Inbox read, and never consumed in a native step. This is **not** rereading already-consumed canonical history or replaying an already-returned tool page.

Root cause: [revocation](<../../../packages/personal-assistant/src/inbox.ts#L233-L235>) updates `consumed` and deletes saved reads but leaves `snapshots.fragments`. The [cursor path](<../../../packages/personal-assistant/src/inbox.ts#L293-L317>) selects those old fragments without revalidating their terminal Task revocation. [GlobalAgent.call](<../../../packages/personal-assistant/src/global-agent.ts#L460-L473>) still allows the source to be read when it remains public/readable. Expected fix: invalidate/filter affected unconsumed Task fragments in frozen unread snapshots and cover this exact race, preserving genuinely consumed native history. Also verify direct-consumption deduplication for preexisting cursors.

## Post-probe fingerprints

Captured immediately after both probes; these are **not final freeze fingerprints**.

```text
6073a4accf71871f1e65ee34e4d04ca65fb74d2b3f6741af44b6fd1350797ecd  packages/dsh-integration/lib/task-context.js
147618a7d4e4cdd258be9d7955452113fd2f904a03c419d31ef4d4e7856ae5f4  packages/personal-assistant/lib/task-context.js
3a2cd9e1f49223acd547cc4efddf25501290e2041cd017102a7f3a44074d7741  packages/personal-assistant/lib/inbox.js
ce6f330b493c95718515870b104ce9805abb119b7bd28b430dc0d4d0c25acf7e  packages/personal-assistant/lib/global-agent.js
6a5200b1e7e859d3fbca5e2d56a24d660c8159c7edbd9be6aeff2540072126d8  packages/dsh-integration/src/task-context.ts
244d2e68ceda2e60778daa9f41ecf7b8b34a019a28c8f4e2456b4e00b55fd0a8  packages/personal-assistant/src/task-context.ts
c9799f1e2e1ef5fb9af9e9f643cef684e90e4832b1547a590b4ea7be67c530d4  packages/personal-assistant/src/inbox.ts
```

## C. Scoped Node24 repair recheck (not a final gate)

The parent authorized only rechecking prior C1/C2/C3 and an external temporary Task-tool witness if needed. The model remains the approved **inherited current-model substitute**, not configured model/effort. All rechecks used Node **v24.22.1**, with its bin directory prepended to PATH for the spawned runtime. Sections A/B above remain historical pre-fix evidence, not current failures.

### C1: Ordinary input, pending Task originals, automatic work and hard tool boundary

The outside-repository temporary script used actual [RuntimeClient](<../../../packages/dsh-integration/src/client.ts>), [TaskContext](<../../../packages/personal-assistant/src/task-context.ts>), [NodeStore](<../../../packages/personal-assistant/src/store.ts>) and [InboxStore](<../../../packages/personal-assistant/src/inbox.ts>). Only center relay, responsibility responses and provider transport were controlled. Provider bodies were recorded at native `llm/stream`; these are **not real-model behavior or live-product acceptance**.

For pending cases an actual Inbox original was prepared while online, preserving its original ID and digest, then passively queued in native context. Authority was disconnected before the next native step. A responsibility response could still report a stale doing Task, so the shared availability gate had to block automatic work rather than relying on a conveniently unavailable snapshot response.

Native matrix job `bash-87af09567f9143a6` completed **exit 0**, checking provider bodies, native user events, durable PA mapping state and pending Inbox projection:

| Case | Independent observation |
|---|---|
| Feature off; empty Task state; ordinary human Feishu question; center offline | Provider 1, ordinary input present, D9 exactly 1; no idle prepare retry over 650ms |
| Feature off; pending original; ordinary human web input; offline → restored → later input | Offline provider 1 with no uncertain original, mapping still prepared; after restoration/later input total provider 3 but original-ID native user events exactly 1, mapping consumed, no pending original |
| Feature on; pending original; ordinary human Feishu input; same sequence | Same exclusion, pending preservation and exactly-once native consumption assertions |
| Task-only original + system execution candidate; center offline | Provider 0; no extra prepare over 900ms; changed adds exactly 1 failed prepare; no spontaneous prepare over another 500ms; original remains prepared |
| Restore authority and send changed after Task-only hold | Provider exactly 1, original-ID native user events exactly 1, mapping consumed; another 500ms idle produces no extra provider |
| Feature off, explicit Task allowlist; native provider actually emits `task_graph.apply` offline | Native tool/result is unavailable error, product.call 0, provider 2 (attempt and response), current D9 exactly 1: a hard denial, not prompt obedience |

The first inspected repair had D9 but **no executable Task-tool gate** anywhere in the inspected integration forwarding chain. The parent confirmed that omission and added a native pre-execute gate before this successful matrix. There is no claimed old-version native tool execution: an initial reviewer script failed syntax parsing before startup; it was corrected and Node24 syntax-checked before actual execution.

These built SHA-256 values matched before and after that successful matrix; they bind this intermediate scoped witness, **not a final freeze**:

```text
2c5ac3d8937e5d0cf0abb7ba861a6d621d01f5c18a1f6a3081cacb3cc089d1c6  packages/dsh-integration/lib/task-context.js
5b0b69a5749596c630fc3fd037c66939a8371f226c6e79690c56d6f393d2c37c  packages/dsh-integration/lib/task-execution.js
55100e341b08f78dba1292c428f769bd563749dc7c9efa5a2f27f931a0e07a54  packages/personal-assistant/lib/task-context.js
3e8e593fb67e37443a170e78570860c835fb4d6283e2915ce456123dcec18218  packages/personal-assistant/lib/inbox.js
```

### C1 follow-up: confirmed sticky gate in that intermediate repair

Job `bash-780e08e423d54991` first obtained the expected offline denial, then restored the relay and submitted a new independent human request in the **same feature-off session**. The provider emitted another real Task apply with a distinct call ID. Actual PA preparation succeeded after restoration, but the second native tool result was still unavailable: provider 4 total, product calls **0 instead of 1**. The assertion failed **exit 1**; runtime/profile cleanup ran in finally.

The [feature-off early return](<../../../packages/dsh-integration/src/task-execution.ts>) preceded recomputation of the cached authority-unavailable flag. PA preparation cleared only context-unavailable. The offline authority-unavailable snapshot stayed sticky, so manually permitted Task tools remained blocked after catch-up. This was independently reported, not mistaken for the original ordinary-conversation outage. The parent subsequently removed that cached flag and changed [the hard gate](<../../../packages/dsh-integration/src/task-execution.ts#L85-L92>) to revalidate the current snapshot at each tool invocation. A later subsection records the exact counterexample rerun; the intermediate failure is retained here rather than erased.

### C2: Old cursor withdrawal and direct-consumption deduplication

The exact actual [GlobalAgent.call](<../../../packages/personal-assistant/src/global-agent.ts>) / Inbox public-read witness from B was rerun on Node24, with assertions inverted to the fixed contract. Public source info stayed can_read=true / can_write=false. After committing only the first ordinary page, revoking the never-returned Task and making a fresh read with the old cursor yielded `{target:"public-chat",messages:[]}`, with no withdrawn title/requirements; check.sources stayed empty. A separate run replaced revocation with actual direct native-context consumption; the old cursor likewise returned no Task. Replaying the already-consumed ordinary saved read preserved its exact body in both cases. Both completed **exit 0**.

The [unread selection and next-cursor calculation](<../../../packages/personal-assistant/src/inbox.ts#L298-L326>) now intersect frozen fragments with current unconsumed rows and fragment-consumption state. Retaining snapshots no longer independently proves the old unread leak.

### C3: Original business semantics

A temporary Node24 script imported the actual [notice generator](<../../../apps/im-server/src/task-notifications.ts>) and completed **exit 0**, asserting:

- Explicit old→new named assignment roles; unassignment names the former assignee; a nonmember is not emitted as a live mention.
- Container, derived-from and selected-replacement edits each state old→new endpoints and reference changed/old/new Task IDs; directly affected endpoint owners are attended, unrelated owners excluded.
- Dependency removal a→b and addition c→a preserve directed endpoint text/references.
- Identical documents produce no notices; requirements bodies are not copied.

This closes the prior missing-business-facts counterexample at the inspected working snapshot, not transactional live delivery or real-Agent reaction.

### Not assessed in this scoped round

No final frozen review, full regression, dependency-contract rerun, M1 signoff, isolated live-product journeys, true-model behavior, child cold isolation, actual window/summary capture or Memory/Skill matrix was performed here. The parent owns those separate steps. No production, permanent test, design, delta or configuration file was modified; only this reviewer's reports and an external temporary witness were written.

## D. Latest scoped closure after per-tool revalidation

Job `bash-2f630a1037a04d46` completed **exit 0** on Node v24.22.1. It repeated every native case in C and then the exact same-session feature-off tool recovery counterexample. All original ordinary-input, uncertain-original, Task-only, bounded-no-hotloop and exactly-once assertions remained true. Offline apply still produced a real native unavailable tool result with product calls 0; after actual PA catch-up and a new independent human input, the second apply produced a real successful native tool result with product calls **1**, provider calls **4** total. The sticky gate counterexample is therefore repaired at this working snapshot, not silently removed from the review history.

Current [hard Task-tool gate](<../../../packages/dsh-integration/src/task-execution.ts#L85-L92>) rejects known context unavailability and otherwise obtains a fresh responsibility/source snapshot at the actual tool boundary. The observed off/on feature behavior is not being inferred from D9 text. This reviewer directly exercised the feature-off same-session native deny→allow boundary; the parent's additional four-quadrant focused test claim is not represented as a reviewer execution.

Before/after SHA-256 values for this latest full scoped native run were identical:

```text
2c5ac3d8937e5d0cf0abb7ba861a6d621d01f5c18a1f6a3081cacb3cc089d1c6  packages/dsh-integration/lib/task-context.js
83cb2384c875fa04785d8dccbebd98398250282c49be2148f9c15e333787416e  packages/dsh-integration/lib/task-execution.js
55100e341b08f78dba1292c428f769bd563749dc7c9efa5a2f27f931a0e07a54  packages/personal-assistant/lib/task-context.js
3e8e593fb67e37443a170e78570860c835fb4d6283e2915ce456123dcec18218  packages/personal-assistant/lib/inbox.js
```

**Scoped result:** original C1/C2 critical counterexamples and C3 business-semantic warning are repaired in their independently rechecked paths. Both newly exposed hard-gate repair issues are also closed by the latest exact witness. No unresolved defect from this narrow recheck is claimed. This does **not** constitute a final code gate, full design/spec alignment, M1 completion or product/model acceptance. All background jobs were collected; every generated native runtime was shut down and each temporary profile removed after an absolute-prefix check. The external script was archived below for reproducibility before cleanup.

### Replayable outside-repository native witness

Save this as a temporary module outside the repository, run from the worktree root against the intended built artifacts, and remove it afterwards. No server, source fix, permanent test or model credentials are required. The provider fixture is controlled transport, not an actual model.

```sh
export PATH="$HOME/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH"
node /absolute/path/to/reviewer-witness.mjs --all-with-recovery
```

```javascript
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';
const root='file://'+process.cwd()+'/';
const {RuntimeClient,prepareProfile}=await import(new URL('packages/dsh-integration/lib/client.js',root));
const {TaskContext}=await import(new URL('packages/personal-assistant/lib/task-context.js',root));
const {InboxStore}=await import(new URL('packages/personal-assistant/lib/inbox.js',root));
const {NodeStore}=await import(new URL('packages/personal-assistant/lib/store.js',root));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async(fn,label)=>{const start=Date.now();for(;;){if(await fn())return;if(Date.now()-start>16000)throw Error('Timeout '+label);await sleep(25);}};
const files=['packages/dsh-integration/lib/task-context.js','packages/dsh-integration/lib/task-execution.js','packages/personal-assistant/lib/task-context.js','packages/personal-assistant/lib/inbox.js'];
const hashes=async()=>Object.fromEntries(await Promise.all(files.map(async f=>[f,createHash('sha256').update(await readFile(f)).digest('hex')])));
console.log(JSON.stringify({phase:'start',node:process.version,fingerprints:await hashes()}));
const empty={kind:'quiescent',tasks:[],repair_task_ids:[]};
const task={graph_id:'g',node_id:'n',title:'Current Task',status:'doing',revision:1,updated_at:'2026-10-30T12:00:00Z',conversation:{id:'fixed-task-chat'},relative_url:'/tasks/g'};
async function fixture({feature=false,pending=false,tool=false}) {
 const home=await mkdtemp(join(tmpdir(),'nano-independent-recheck-'));let logs='';const inbox=new InboxStore(':memory:'),store=new NodeStore(':memory:','owner');
 const state={offline:false,prepares:0,relay:0,snapshots:0,doing:false,commits:0,sent:[]};
 const probe="import {appendFile} from 'node:fs/promises';export const name='independent-recheck-probe';export const inject=['llm'];export function apply(ctx){let count=0;ctx.on('llm/stream',async function*(o){count++;await appendFile(process.env.DSH_HOME+'/calls',JSON.stringify({messages:o.messages})+String.fromCharCode(10));const block="+(tool?"(count===1||count===3)?{type:'tool-call',id:'review-apply-'+count,name:'task_graph',arguments:JSON.stringify({action:'apply',graph_id:'g',base_revision:1,request_key:'independent-offline-apply',operations:[{op:'update_task',node_id:'n',patch:{status:'done',result:'controlled fixture result'}}]})}:{type:'text',text:'Checked tool result.'}":"{type:'text',text:'4. Independent input answered.'}")+";yield{type:'block-end',index:0,block};yield{type:'finish',reason:{kind:block.type==='tool-call'?'tool-calls':'stop'}};});}";
 await writeFile(join(home,'probe.mjs'),probe);await prepareProfile(home,[{insert:[{id:'independent-recheck-probe',name:join(home,'probe.mjs')}]}]);
 const config={agentId:'a',revision:'1',mode:'single_thread',workspace:home,provider:'deepseek-official',model:'deepseek-flash',features:{task_graph:feature,intelligent_ui:false,memory_curation:false,skill_creation:false},...(tool?{toolAllowlist:['task_graph'],approval:{dangerouslySkipPermissions:true}}:{})};
 const binding={sessionId:'s',agentId:'a',ownerId:'owner',revision:'1',cwd:home};store.bind({...binding,conversationId:'fixed-task-chat'});
 const client=new RuntimeClient({home,cwd:home,onLog:t=>{logs+=t;}});
 const runtime={onNotification:fn=>client.rpc.onNotification(fn),request:(m,p)=>client.rpc.request(m,p)};
 const relay={request:async(type,args)=>{state.relay++;if(state.offline)throw Error('CENTER_OFFLINE_NO_TASKS');assert.equal(type,'task.context.sync');return {type:'task.context.sync.result',payload:{ok:true,result:{through:0,next:0,items:[],revoked_message_ids:[]}}};}};
 const context=new TaskContext({nodeId:'node',ownerId:'owner',agents:[config],store,inbox,runtime,relay,refreshSources:async()=>{}});
 client.rpc.handle('product.task_context.prepare',async value=>{state.prepares++;return context.prepare(value);});
 client.rpc.handle('product.task_context.commit',async value=>{state.commits++;return context.commit(value);});
 const calls=async()=>{const text=await readFile(join(home,'calls'),'utf8').catch(()=>'');return text.trim()?text.trim().split(String.fromCharCode(10)).map(JSON.parse):[];};
 client.rpc.handle('product.task_execution.snapshot',async()=>{state.snapshots++;return state.doing&&(await calls()).length===0?{kind:'continue',tasks:[task],repair_task_ids:[]}:empty;});
 client.rpc.handle('product.call',value=>{state.sent.push(value);return {ok:true,result:{graph_id:'g',revision:2,changed_ids:['n']}};});
 let originals=[];
 if(pending){inbox.receive({agent_id:'a',conversation_id:'fixed-task-chat',relay_task_id:'pending-original',idempotency_key:'pending-original',metadata:{conversation_type:'group',task_context:true},message:{id:'pending-original',content:'UNCERTAIN_TASK_REQUIREMENTS_REVIEW_REPLAY',sender_type:'system',sender_user_id:'system',created_at:'2026-10-30T12:00:00Z',attachments:[],system_notice:{kind:'task_graph',attention_actor_ids:['a'],task_refs:[{graph_id:'g',node_id:'n'}]}}},false);originals=(await context.prepare(binding)).messages;assert.equal(originals.length,1);}
 state.offline=true;
 await client.rpc.request('initialize',{protocol:1,agents:[config],bindings:[binding]});await client.rpc.request('session.ensure',binding);
 if(pending)await client.rpc.request('task.context.passive',{agentId:'a',sessionId:'s',messages:originals,revoked:[]});
 const observe=()=>client.rpc.request('session.observe',{sessionId:'s'});
 const idle=()=>wait(async()=>(await observe()).status==='idle','idle');
 const submit=(id,channel='feishu',system=false)=>client.rpc.request('session.submit',{sessionId:'s',inputId:id,mode:'followup',content:[{type:'text',text:tool?'Save the independently verified result to the existing Task.':'Just answer: what is 2+2? No Task requested.'}],source:system?{kind:'system',channel:'task-execution',actorId:'a',messageId:id}:{kind:'human',actorId:'owner',channel,messageId:id}});
 const finish=async id=>{await wait(async()=>Boolean((await client.rpc.request('session.lookup',{sessionId:'s',inputId:id})).terminal),'terminal '+id);await idle();};
 const close=async()=>{await client.shutdown();inbox.close();store.close();const path=resolve(home),prefix=resolve(tmpdir())+'/nano-independent-recheck-';assert(path.startsWith(prefix));await rm(path,{recursive:true,force:true});};
 return {state,client,context,inbox,store,calls,observe,idle,submit,finish,close,logs:()=>logs};
}
async function independent(feature,pending,channel){const f=await fixture({feature,pending});try{await f.submit('ordinary-offline',channel);await f.finish('ordinary-offline');const first=await f.calls();assert.equal(first.length,1);assert(first[0].messages.some(m=>m.id==='ordinary-offline'));assert(!JSON.stringify(first).includes('UNCERTAIN_TASK_REQUIREMENTS_REVIEW_REPLAY'));assert.equal(first[0].messages.filter(m=>m.source?.channel==='task-context-limitation').length,1);assert.equal(f.store.systemContextInputs('a').filter(r=>r.state==='consumed').length,0);const offlinePrepares=f.state.prepares;await sleep(650);assert.equal(f.state.prepares,offlinePrepares);if(pending){assert.equal(f.store.systemContextInputs('a')[0].state,'prepared');f.state.offline=false;await f.submit('authority-restored',channel);await f.finish('authority-restored');await f.submit('later-human',channel);await f.finish('later-human');const obs=await f.observe();assert.equal(obs.events.filter(e=>e.type==='user/message'&&e.data.id==='pending-original').length,1);assert.equal(f.store.systemContextInputs('a')[0].state,'consumed');assert.equal(f.inbox.prepareSystemContext('a','s').length,0);assert.equal((await f.calls()).at(-1).messages.filter(m=>m.id==='pending-original').length,1);}console.log(JSON.stringify({case:'independent-input',feature,pending,channel,offlineProviderCalls:first.length,D9:first[0].messages.filter(m=>m.source?.channel==='task-context-limitation').length,idleNoRetry:true,recoveryOriginalEvents:pending?1:0,prepares:f.state.prepares,relay:f.state.relay,providerCalls:(await f.calls()).length}));}catch(e){console.error(f.logs());throw e;}finally{await f.close();}}
if(!process.argv.includes('--tool-recovery')){
await independent(false,false,'feishu');await independent(false,true,'web');await independent(true,true,'feishu');
{
 const f=await fixture({feature:true,pending:true});try{f.state.doing=true;await f.submit('task-only-candidate','test',true);await wait(()=>f.state.prepares>=1,'Task-only prepare');await f.idle();assert.equal((await f.calls()).length,0);const baseline=f.state.prepares;await sleep(900);assert.equal(f.state.prepares,baseline);assert.equal(f.store.systemContextInputs('a')[0].state,'prepared');await f.client.rpc.request('task.execution.changed',{agentId:'a'});await wait(()=>f.state.prepares>baseline,'changed offline retry');await f.idle();const afterChanged=f.state.prepares;await sleep(500);assert.equal(f.state.prepares,afterChanged);assert.equal((await f.calls()).length,0);f.state.offline=false;await f.client.rpc.request('task.execution.changed',{agentId:'a'});await wait(async()=>(await f.calls()).length===1,'recovered Task provider');await f.idle();await sleep(500);assert.equal((await f.calls()).length,1);const obs=await f.observe();assert.equal(obs.events.filter(e=>e.type==='user/message'&&e.data.id==='pending-original').length,1);assert.equal(f.store.systemContextInputs('a')[0].state,'consumed');console.log(JSON.stringify({case:'task-only',offlineProviderCalls:0,idleNoHotloop:true,changedOfflinePrepareDelta:afterChanged-baseline,recoveredProviderCalls:1,recoveryOriginalEvents:1,pendingPreservedOffline:true}));}catch(e){console.error(f.logs());throw e;}finally{await f.close();}
}
}
{
 const f=await fixture({feature:false,tool:true});try{await f.submit('offline-manual-task-mutation','feishu');await f.finish('offline-manual-task-mutation');const obs=await f.observe(),results=obs.events.filter(e=>e.type==='tool/result');assert.equal(results.length,1);const calls=await f.calls();assert.equal(f.state.sent.length,0,'Task mutation must not reach product when authority is unavailable');console.log(JSON.stringify({case:'offline-native-task-tool',feature:false,toolAllowlist:['task_graph'],providerCalls:calls.length,D9:calls[0].messages.filter(m=>m.source?.channel==='task-context-limitation').length,attemptedTool:'task_graph.apply',productCalls:f.state.sent.length,hardGateBlocked:true,toolResults:results.map(e=>e.data)}));if(process.argv.includes('--tool-recovery')||process.argv.includes('--all-with-recovery')){f.state.offline=false;await f.submit('online-manual-task-mutation','feishu');await f.finish('online-manual-task-mutation');const online=await f.observe();console.log(JSON.stringify({case:'recovered-native-task-tool',feature:false,providerCalls:(await f.calls()).length,productCalls:f.state.sent.length,toolResults:online.events.filter(e=>e.type==='tool/result').map(e=>e.data)}));assert.equal(f.state.sent.length,1,'Recovered independent manually allowed Task tool must reopen after authoritative context catch-up');}}catch(e){console.error(f.logs());throw e;}finally{await f.close();}
}
console.log(JSON.stringify({phase:'end',fingerprints:await hashes()}));
```


