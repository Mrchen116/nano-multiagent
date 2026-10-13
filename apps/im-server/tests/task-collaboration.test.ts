import { describe, expect, it, vi } from 'vitest';
import { fixture } from './control-fixture.js';
import { TaskGraphService } from '../src/task-graphs.js';
import { Messaging } from '../src/messaging.js';
import { one, all } from '../src/context.js';
const human = {kind:'user' as const,id:'u1'};
const agent = {kind:'agent' as const,id:'a',node_id:'n'};
function setup() {
  const {db,ctx} = fixture();
  ctx.gateway.broadcast = vi.fn();
  ctx.messaging = new Messaging(ctx);
  return {db,ctx,service:new TaskGraphService(db,ctx.messaging)};
}
describe('conversation task collaboration',()=>{
  it('uses real creators, member writes and distinct subtree deletion authority',()=>{
    const {db,service:s}=setup();
    const create={title:'Release',mode:'dag',conversation_id:'chat',request_key:'create'};
    const graph=s.execute(human,'create',create);
    expect(()=>s.execute({kind:'user',id:'u2'},'get',{graph_id:graph.graph_id})).toThrow('not accessible');
    db.prepare("UPDATE conversations SET visibility='public' WHERE id='chat'").run();
    const read=s.execute({kind:'user',id:'u2'},'get',{graph_id:graph.graph_id,view:'all'});
    expect(read.nodes[0]).toMatchObject({created_by:{type:'user',id:'u1'},assignee:null,can_edit:false,can_delete:false});
    expect(()=>s.execute({kind:'user',id:'u2'},'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'outsider',change_note:'',operations:[{op:'claim_task',node_id:'n1'}]})).toThrow('not accessible');
    const edit=s.execute(agent,'apply',{graph_id:graph.graph_id,base_revision:1,request_key:'child',change_note:'',operations:[{op:'add_task',client_ref:'child',container_id:'n1',title:'Build',assignee:{type:'user',id:'u1'}}]});
    expect(()=>s.execute(agent,'delete',{graph_id:graph.graph_id,base_revision:2,request_key:'no'})).toThrow('not accessible');
    expect(s.execute(agent,'get',{graph_id:graph.graph_id,view:'all'}).nodes[1]).toMatchObject({created_by:{type:'agent',id:'a'},assignee:{type:'user',id:'u1'}});
    expect(()=>s.execute(human,'apply',{graph_id:graph.graph_id,base_revision:2,request_key:'fake',change_note:'',operations:[{op:'update_task',node_id:'n1',patch:{created_by:{type:'agent',id:'a'}}}]})).toThrow();
    expect(edit.revision).toBe(2);
    const deleted=s.execute(human,'delete',{graph_id:graph.graph_id,base_revision:2,request_key:'delete'});
    expect(deleted.deleted_ids).toEqual(['n1','n2']);
    expect(s.execute(human,'delete',{graph_id:graph.graph_id,base_revision:2,request_key:'delete'})).toEqual(deleted);
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='u1'").run();
    expect(()=>s.execute(human,'delete',{graph_id:graph.graph_id,base_revision:2,request_key:'delete'})).toThrow('not accessible');
  });
  it('atomically saves assignment, one system message, durable relay and idempotent receipt while offline',()=>{
    const {db,ctx,service:s}=setup();
    // Agent control-plane creation uses a user placeholder; qualification belongs to its active owner.
    db.prepare("UPDATE users SET membership_status='pending',owner_id='' WHERE username='agent:a'").run();
    const args={title:'<mention type="user" target_id="a1"/>',mode:'dag',conversation_id:'chat',assignee:{type:'agent',id:'a'},request_key:'create'};
    expect(()=>s.execute(human,'create',{...args,request_key:'bad-create',assignee:{type:'user',id:'a1'}})).toThrow('actor type');
    const g=s.execute(human,'create',args);
    expect(s.execute(human,'create',args)).toEqual(g);
    for (const operation of [{op:'add_task',client_ref:'bad',container_id:'n1',title:'Bad',assignee:{type:'user',id:'a1'}},{op:'set_assignee',node_id:'n1',assignee:{type:'user',id:'a1'}}]) {
      expect(()=>s.execute(human,'apply',{graph_id:g.graph_id,base_revision:1,request_key:operation.op,change_note:'',operations:[operation]})).toThrow('actor type');
    }
    const messages=all(db,'SELECT * FROM messages');
    expect(messages).toHaveLength(1);
    expect(messages[0].sender_type).toBe('system');
    expect(ctx.messaging.mentionedAgents('chat',messages[0].content)).toEqual(['a']);
    expect(messages[0].content.match(/<mention/g)).toHaveLength(1);
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
    expect(one(db,'SELECT status FROM relay_tasks')?.status).toBe('queued');
    expect(()=>s.execute(human,'apply',{graph_id:g.graph_id,base_revision:1,request_key:'bad',change_note:'',operations:[{op:'set_assignee',node_id:'n1',assignee:{type:'user',id:'u2'}}]})).toThrow();
    expect(all(db,'SELECT * FROM messages')).toHaveLength(1);
    expect(s.execute(human,'get',{graph_id:g.graph_id,view:'all'}).revision).toBe(1);
    db.exec("CREATE TRIGGER fail_notice BEFORE INSERT ON messages BEGIN SELECT RAISE(ABORT,'notice fault'); END;");
    expect(()=>s.execute(human,'apply',{graph_id:g.graph_id,base_revision:1,request_key:'fault',change_note:'',operations:[{op:'set_assignee',node_id:'n1',assignee:null}]})).toThrow('notice fault');
    expect(s.execute(human,'get',{graph_id:g.graph_id,view:'all'}).nodes[0].assignee.id).toBe('a');
    expect(one(db,"SELECT 1 FROM task_graph_mutation_receipts WHERE request_key='fault'")).toBeUndefined();
  });
  it('claims without stealing, counts direct children, filters all matching levels and rechecks cursor ACL',()=>{
    const {db,service:s}=setup();
    const g=s.execute(human,'create',{title:'Root',mode:'dag',conversation_id:'chat',assignee:{type:'user',id:'u1'},request_key:'create'});
    s.execute(human,'apply',{graph_id:g.graph_id,base_revision:1,request_key:'children',change_note:'',operations:[
      {op:'add_task',client_ref:'p',container_id:'n1',title:'Parent',mode:'dag',assignee:{type:'user',id:'u1'}},
      {op:'add_task',client_ref:'c',container_id:'@p',title:'Child',status:'in_review',assignee:{type:'user',id:'u1'}},
    ]});
    expect(()=>s.execute(agent,'apply',{graph_id:g.graph_id,base_revision:2,request_key:'steal',change_note:'',operations:[{op:'claim_task',node_id:'n2'}]})).toThrow('already assigned');
    s.execute(human,'apply',{graph_id:g.graph_id,base_revision:2,request_key:'claim',change_note:'',operations:[{op:'claim_task',node_id:'n2'}]});
    const graph=s.execute(human,'get',{graph_id:g.graph_id,view:'all'});
    expect(graph.nodes[0]).toMatchObject({status:'todo',direct_counts:{doing:1,total:1}});
    expect(graph.nodes[1].status).toBe('doing');
    const first=s.execute(human,'list',{assignee_type:'user',assignee_id:'u1',limit:1});
    expect(first.total).toBe(3);
    expect(first.items[0]).toHaveProperty('parent_path');
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='u1'").run();
    expect(s.execute(human,'list',{assignee_type:'user',assignee_id:'u1',limit:1,cursor:first.next_cursor}).items).toEqual([]);
  });
  it('filters each status column before its limit and binds cursors to that status set',()=>{
    const {db,service:s}=setup();
    const create=(title:string,status:string,key:string)=>s.execute(human,'create',{title,status,mode:'dag',conversation_id:'chat',request_key:key,assignee:{type:'user',id:'u1'}});
    const done=create('Column done','done','done');
    create('Column paused','paused','paused');
    for(let i=0;i<3;i++)create('Column todo '+i,'todo','todo'+i);
    s.execute(human,'apply',{graph_id:done.graph_id,base_revision:1,request_key:'deep-done',change_note:'',operations:[{op:'add_task',client_ref:'deep',container_id:'n1',title:'Column deep done',status:'done',assignee:{type:'user',id:'u1'}}]});
    const first=s.execute(human,'list',{query:'Column',statuses:'todo,paused',limit:2});
    expect(first.total).toBe(4);
    expect(first.items).toHaveLength(2);
    expect(first.next_cursor).toBeTruthy();
    const next=s.execute(human,'list',{query:'Column',statuses:'paused,todo',limit:2,cursor:first.next_cursor});
    expect(next.total).toBe(4);
    expect(new Set([...first.items,...next.items].map((item:any)=>item.graph_id)).size).toBe(4);
    expect([...first.items,...next.items].some((item:any)=>item.status==='paused')).toBe(true);
    expect(s.execute(human,'list',{statuses:'done',limit:1}).items[0].graph_id).toBe(done.graph_id);
    expect(s.execute(human,'list',{statuses:'done',assignee_type:'user',assignee_id:'u1'}).total).toBe(2);
    expect(()=>s.execute(human,'list',{query:'Column',statuses:'done',cursor:first.next_cursor})).toThrow('Invalid cursor');
    expect(()=>s.execute(human,'list',{statuses:'invented'})).toThrow('statuses');
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='u1'").run();
    expect(s.execute(human,'list',{statuses:'done',assignee_type:'user',assignee_id:'u1'})).toMatchObject({items:[],total:0});
  });

});
