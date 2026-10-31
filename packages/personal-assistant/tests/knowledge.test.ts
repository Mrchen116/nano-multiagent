import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { AgentConfiguration, RuntimePort } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { KnowledgeUpdates } from '../src/knowledge.js';

it('retains maintenance links without writes or history traversal and recovers them idempotently', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-maintenance-links-'));
  const store=new NodeStore(join(home,'node.db'),'owner'),inbox=new InboxStore(join(home,'inbox.db'));
  store.bind({sessionId:'main',agentId:'a',conversationId:'global:a',ownerId:'owner',cwd:home,revision:'1'});
  const agent:AgentConfiguration={agentId:'a',workspace:home,revision:'1',mode:'global',provider:'test',model:'test'};
  const reviews=['running','completed','error','cancelled'].map((status,index)=>({id:`review-${index}`,status,agentId:'a',rootSessionId:'main',childSessionId:`maintenance-${index}`,kind:'combined',at:1000+index}));
  const calls:string[]=[];let signals=0;
  const options={nodeId:'node',agents:[agent],store,inbox,onError:(error:unknown)=>{throw error;},onWork:()=>{signals++;},
    runtime:{onNotification:()=>()=>{},request:async(method:string)=>{calls.push(method);if(method!=='knowledge.facts')throw new Error('History and execution must remain demand-loaded');return{facts:[],reviews:[...reviews,{...reviews[0],id:'foreign',rootSessionId:'unbound'}]};}},
    relay:{request:async()=>{throw new Error('No public notice without a knowledge change');}},im:async()=>({})};
  let updates=new KnowledgeUpdates(options);
  try{
    await updates.recover();
    const links=inbox.journal(0).filter(event=>event.type==='session_linked');
    expect(links.map(event=>({root:event.root_agent_id,session:event.session_id,payload:event.payload}))).toEqual(reviews.map(review=>({root:'a',session:'main',payload:expect.objectContaining({parent_session_id:'main',child_session_id:review.childSessionId,title:'记忆与技能复盘'})})));
    expect(signals).toBe(1);
    await updates.stop();updates=new KnowledgeUpdates(options);await updates.recover();
    expect(inbox.journal(0).filter(event=>event.type==='session_linked')).toHaveLength(4);
    expect(signals).toBe(1);expect(calls).toEqual(['knowledge.facts','knowledge.facts']);
  }finally{await updates.stop();inbox.close();store.close();await rm(home,{recursive:true,force:true});}
});

it('recovers committed changes without re-enabling disabled skills and retries unacknowledged notices', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-knowledge-product-'));
  const store = new NodeStore(join(home, 'node.db'), 'owner'); const inbox = new InboxStore(join(home, 'inbox.db'));
  store.bind({ sessionId: 'original', agentId: 'a', conversationId: 'original-chat', ownerId: 'owner', cwd: home, revision: '1' });
  store.bind({ sessionId: 'later', agentId: 'a', conversationId: 'later-chat', ownerId: 'owner', cwd: home, revision: '1' });
  const agent: AgentConfiguration = { agentId: 'a', workspace: home, revision: '1', mode: 'single_thread', provider: 'test', model: 'test', skillSelection: { mode: 'explicit_denylist', names: ['new-skill'] } };
  const facts = [{ id: 'write', agentId: 'a', rootSessionId: 'original', sessionId: 'child', reviewId: 'review', turn: 1, kind: 'skills', action: 'create', name: 'new-skill', scope: 'agent', skill_root: join(home, '.nanoassistant/skills') }];
  let status = 'running'; let fail = true; const notices: Record<string, unknown>[] = []; const enables: unknown[] = [];
  const runtime: RuntimePort = { onNotification: () => () => {}, request: async method => {
    if (method === 'knowledge.facts') return { facts: [...facts], reviews: [{ id: 'review', status }] };
    if (method === 'knowledge.acknowledge') facts.splice(0); return {};
  } };
  const options = { nodeId: 'node', agents: [agent], runtime, store, inbox, onError: () => {}, im: async (path: string, init?: RequestInit) => {
    if (path.endsWith('source=mirror')) return { skills: [], profile_version: 7 };
    enables.push(JSON.parse(String(init?.body))); agent.skillSelection!.names.push('new-skill'); return {};
  }, relay: { request: async (_type: string, payload: Record<string, unknown>) => {
    notices.push(payload); if (fail) throw new Error('Disconnected before receipt'); return { type: 'ack', payload: { message_id: 'notice-1' } };
  } } };
  let updates = new KnowledgeUpdates(options);
  try {
    await updates.recover(); expect(notices).toHaveLength(0); expect(enables).toHaveLength(0);
    status = 'completed'; await updates.recover(); expect(facts).toHaveLength(1);
    expect(enables).toEqual([]);
    expect(agent.skillSelection?.names).toEqual(['new-skill']);
    await updates.stop(); updates = new KnowledgeUpdates(options); fail = false;
    await updates.recover(); expect(facts).toHaveLength(0); expect(enables).toHaveLength(0);
    expect(notices).toHaveLength(2); expect(notices[0]).toEqual(notices[1]);
    expect(notices[0]).toMatchObject({ node_id: 'node', conversation_id: 'original-chat', system_notice: { updated_targets: ['skills'] } });
  } finally { await updates.stop(); inbox.close(); store.close(); await rm(home, { recursive: true, force: true }); }
});

it('isolates a failed legacy migration and retries it without blocking other agents', async () => {
  const agents: AgentConfiguration[] = ['a', 'b'].map(agentId => ({ agentId, workspace: '/tmp/review', revision: '1', mode: 'single_thread', provider: 'test', model: 'test', skillSelection: { mode: 'explicit_allowlist', names: [] } }));
  let fail = true;
  const errors: unknown[] = []; const migrated: string[] = [];
  const updates = new KnowledgeUpdates({ agents, runtime: { onNotification: () => () => {} }, onError: error => errors.push(error),
    im: async (path: string, init?: RequestInit) => {
      if (path.includes('/a/') && fail) throw new Error('IM 503');
      if (!init) return { profile_version: 1 };
      migrated.push(path); agents.find(agent => path.includes(`/${agent.agentId}/`))!.skillSelection = { mode: 'explicit_denylist', names: [] }; return {};
    },
  } as ConstructorParameters<typeof KnowledgeUpdates>[0]);
  try {
    await expect(updates.migrateSkills()).resolves.toBeUndefined();
    expect(errors).toHaveLength(1); expect(migrated).toEqual(['/im/v1/agents/b/skills/migrate']);
    expect(agents[0]!.skillSelection!.mode).toBe('explicit_allowlist');
    fail = false; await updates.migrateSkills();
    expect(migrated).toEqual(['/im/v1/agents/b/skills/migrate', '/im/v1/agents/a/skills/migrate']);
    expect(agents[0]!.skillSelection!.mode).toBe('explicit_denylist');
  } finally { await updates.stop(); }
});

it('projects authoritative Dreaming partial receipts into Work without any public notice', async () => {
  const home=await mkdtemp(join(tmpdir(),'nano-dreaming-work-'));
  const store=new NodeStore(join(home,'node.db'),'owner'), inbox=new InboxStore(join(home,'inbox.db'));
  store.bind({sessionId:'main',agentId:'a',conversationId:'global:a',ownerId:'owner',cwd:home,revision:'1'});
  const agent:AgentConfiguration={agentId:'a',workspace:home,revision:'1',mode:'global',provider:'test',model:'test'};
  const review={id:'dream',kind:'dreaming',status:'partial',agentId:'a',rootSessionId:'main',childSessionId:'child',at:1000,endedAt:2000,summary:'保存 1/2 页；入口待同步；未推进处理游标'};
  const updates=new KnowledgeUpdates({nodeId:'n',agents:[agent],store,inbox,onError:error=>{throw error;},im:async()=>({}),
    runtime:{onNotification:()=>()=>{},request:async()=>({facts:[],reviews:[review]})},relay:{request:async()=>{throw new Error('Dreaming must remain quiet');}}});
  try {
    await updates.recover();await updates.recover();
    const events=inbox.journal(0);
    expect(events.filter(event=>event.type==='session_linked')).toHaveLength(1);
    expect(events.find(event=>event.type==='message')).toMatchObject({session_id:'child',payload:{text:review.summary,source_kind:'host_receipt'}});
    expect(events.find(event=>event.type==='turn_end')).toMatchObject({session_id:'child',payload:{status:'partial',completed:false}});
    expect(events).toHaveLength(4);
  } finally {await updates.stop();inbox.close();store.close();await rm(home,{recursive:true,force:true});}
});
