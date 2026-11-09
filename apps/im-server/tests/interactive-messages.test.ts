import { describe, expect, it, vi } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';
import { Gateway } from '../src/gateway.js';
import { all, one } from '../src/context.js';

const interactive = { format: 'openui', catalog_version: 'nano-iui-1', source: `$body = "周六见"
root = Col([form])
form = Form([TextArea($body, "草稿"), Button("发送给林悦", @SendToChat("发送给林悦"))])` };
function setup() {
  const {db,ctx} = fixture(); ctx.gateway.broadcast = vi.fn();
  const messaging = new Messaging(ctx); ctx.messaging = messaging;
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const card = messaging.insertMessage('chat','a1','agent','请先确认草稿',[],null,'completed',{interactive});
  const request = (user='u1', content?: string, state: Record<string,unknown> = {}, action_id: string|undefined = content ? undefined : 'send') => ({
    headers: {'x-user':user, 'idempotency-key':'same-key'}, params:{conversation_id:'chat',message_id:card.id}, query:{},
    body:{sender_user_id:user, ...(content ? {content} : {}), interaction_reply:{source_message_id:card.id, ...(action_id ? {event:{type:"continue_conversation",label:"发送给林悦",message:"发送给林悦"}} : {}), state}},
  }) as any;
  return {db,ctx,messaging,card,request};
}
describe('interactive message persistence', () => {
  it('uses the first visible card title for a pure card preview and keeps ordinary previews', () => {
    const {messaging} = setup();
    const preview = () => messaging.conversation('chat','u1');
    const addCard = (source: string, content = '') =>
      messaging.insertMessage('chat','a1','agent',content,[],null,'completed',{interactive:{...interactive,source}});
    addCard('root = Col([Popover(Icon("info"), Table(["列"], [[Title("隐藏说明")]])), Flashcard("正面", Title("背面")), Title("读书会预算"), Title("预算明细")])');
    expect(preview()).toMatchObject({last_message_preview:'',last_message_card:{title:'读书会预算'}});
    addCard('root = Text("周六见")\nunused = Title("未显示的标题")');
    expect(preview()).toMatchObject({last_message_preview:'',last_message_card:{title:null}});
    addCard('root = Title("读书会预算")', '已更新预算');
    expect(preview()).toMatchObject({last_message_preview:'已更新预算',last_message_card:null});
  });

  it('keeps a card attachment name even when a historical fork stored only the empty body', () => {
    const {messaging,db} = setup();
    messaging.insertMessage('chat','a1','agent','',[{url:'/im/files/plan.pdf',content_type:'application/pdf',file_name:'plan.pdf'}],null,'completed',{
      interactive:{...interactive,source:'root = Title("Read the plan")'},
    });
    db.prepare("UPDATE conversations SET last_message_preview='' WHERE id='chat'").run();
    expect(messaging.conversation('chat','u1')).toMatchObject({last_message_preview:'plan.pdf',last_message_card:null});
  });

  it('publishes complete cards and keeps user draft revisions private', () => {
    const {messaging,card,ctx,request} = setup();
    expect(card.interactive).toMatchObject(interactive);
    const req=request(); req.body={expected_draft_revision:0,state:{'$body':'周日见'}};
    expect(messaging.interactions.writeDraft(req)).toMatchObject({draft_revision:1});
    expect(messaging.interactions.readDraft(request('u2'))).toMatchObject({state:{},draft_revision:0});
    expect(()=>messaging.interactions.writeDraft(req)).toThrow();
    expect(ctx.gateway.broadcast).toHaveBeenCalledTimes(1);
  });
  it('accepts UI-only gateway HTTP messages, keeps retries idempotent and rejects empty or invalid sends', async () => {
    const {messaging,ctx} = setup();
    ctx.gateway.authenticate=()=>({node_id:'n',owner_id:'o1',node_epoch:1}) as any;
    const req={headers:{authorization:'Bearer fixture','idempotency-key':'ui-only'},params:{conversation_id:'chat'},query:{agent_id:'a'},body:{sender_type:'agent',interactive}} as any;
    const first=await messaging.sendMessage(req);
    expect(first).toMatchObject({content:'',interactive});
    expect(await messaging.sendMessage(req)).toMatchObject({id:first.id});
    for (const empty of [undefined,null,false,'',0]) {
      await expect(messaging.sendMessage({...req,body:{sender_type:'agent',interactive:empty}})).rejects.toThrow();
    }
    await expect(messaging.sendMessage({...req,headers:{...req.headers,'idempotency-key':'invalid'},body:{sender_type:'agent',interactive:{...interactive,source:'root = Unknown("x")'}}})).rejects.toThrow();
  });
  it('relays a UI-only group reply to peers without relaying an empty stream placeholder', () => {
    const {messaging,ctx,db} = setup();
    db.prepare("UPDATE conversations SET type='group' WHERE id='chat'").run();
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES('b','o1','n','Colleague','now','now')").run();
    const peer=messaging.agentUser('b');
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(peer.id);
    const gateway=new Gateway(ctx);
    const empty=messaging.insertMessage('chat','a1','agent','');
    gateway.groupReply(empty.id,{deferDelivery:true});
    expect(all(db,'SELECT * FROM relay_tasks WHERE message_id=?',empty.id)).toHaveLength(0);
    const card=messaging.insertMessage('chat','a1','agent','',[],null,'completed',{interactive});
    gateway.groupReply(card.id,{deferDelivery:true});
    gateway.groupReply(card.id,{deferDelivery:true});
    const deliveries=all(db,'SELECT payload_json FROM relay_tasks WHERE message_id=?',card.id);
    expect(deliveries).toHaveLength(1);
    expect(JSON.parse(deliveries[0]!.payload_json)).toMatchObject({agent_id:'b',message:{id:card.id,content:'',interactive}});
  });
  it('saves selection and one relay atomically even while the node is offline; retries do not enqueue again', async () => {
    const {messaging,card,db,request} = setup();
    const sent=await messaging.sendMessage(request());
    expect(sent).toMatchObject({sender_user_id:'u1',content:'发送给林悦',delivery_status:'pending',interaction_reply:{source_message_id:card.id,event:expect.objectContaining({label:'发送给林悦'})}});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
    expect(await messaging.sendMessage(request())).toMatchObject({id:sent.id});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
    expect(messaging.interactions.readDraft(request())).toMatchObject({submission_message_id:sent.id});
  });
  it('preserves handwritten content and rejects changed retries without discarding the prior result', async () => {
    const {messaging,card,db,request} = setup();
    db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
    const state={'$body':'林悦，周六11点断桥见'};
    const sent=await messaging.sendMessage(request('u1','先别发送，把语气改得随意一点',state));
    expect(sent.content).toBe('先别发送，把语气改得随意一点');
    expect(sent.interaction_reply.fields[0].value).toContain('周六11点');
    await expect(messaging.sendMessage(request('u1','发给林悦',state))).rejects.toMatchObject({statusCode:409});
    await expect(messaging.sendMessage(request('u1',undefined,state))).rejects.toMatchObject({statusCode:409});
    expect(one(db,'SELECT content FROM messages WHERE id=?',sent.id)?.content).toBe(sent.content);
    expect(all(db,'SELECT * FROM interaction_submissions WHERE source_message_id=?',card.id)).toHaveLength(1);
  });
  it('isolates different people even with the same client idempotency key', async () => {
    const {messaging,request} = setup();
    const first=await messaging.sendMessage(request());
    const second=await messaging.sendMessage(request('u2'));
    expect(second.id).not.toBe(first.id);expect(second.sender_user_id).toBe('u2');
  });
  it('rejects new submissions on replaced cards but returns the original committed retry', async () => {
    const {messaging,card,request} = setup();
    const first=await messaging.sendMessage(request());
    const next=messaging.insertMessage('chat','a1','agent','已更新',[],null,'completed',{interactive:{...interactive,supersedes_message_id:card.id}});
    expect(messaging.message(card.id).interactive.superseded_by).toBe(next.id);
    expect(await messaging.sendMessage(request())).toMatchObject({id:first.id});
    await expect(messaging.sendMessage(request('u2'))).rejects.toMatchObject({statusCode:409});
  });
  it('rejects malformed publication atomically and keeps the previous card active', () => {
    const {messaging,card,db} = setup();
    const before=all(db,'SELECT * FROM messages').length;
    expect(()=>messaging.insertMessage('chat','a1','agent','无效卡片',[],null,'completed',{interactive:{...interactive,source:'root = Unknown("x")',supersedes_message_id:card.id}})).toThrow();
    expect(all(db,'SELECT * FROM messages')).toHaveLength(before);
    expect(messaging.message(card.id).interactive.superseded_by).toBeUndefined();
    expect(()=>messaging.insertMessage('chat','a1','agent','无效卡片',[],null,'completed',{interactive:{...interactive,source:'root = Title("Hello", "huge")'}}))
      .toThrow(expect.objectContaining({statusCode:422, detail:expect.objectContaining({code:'invalid_interactive_source',errors:[expect.objectContaining({code:'type-mismatch',component:'Title',path:'/size',statementId:'root'})]})}));
    expect(all(db,'SELECT * FROM messages')).toHaveLength(before);
  });
  it('copies public cards as read-only without copying viewer drafts', () => {
    const {messaging,card,db,request} = setup();
    const req=request();req.body={expected_draft_revision:0,state:{'$body':'仅我可见'}};
    messaging.interactions.writeDraft(req);
    const copy=messaging.insertMessage('chat','a1','agent','复制的历史',[],null,'completed',{});
    messaging.interactions.copy(new Map([[card.id,copy.id]]));
    expect(messaging.message(copy.id).interactive).toMatchObject({source:interactive.source,read_only:true});
    expect(all(db,'SELECT * FROM interaction_drafts WHERE source_message_id=?',copy.id)).toHaveLength(0);
    req.params.message_id=copy.id;
    expect(()=>messaging.interactions.writeDraft(req)).toThrow();
  });
  it('rejects a viewer outside the conversation before exposing their draft or submitting', async () => {
    const {messaging,request,db} = setup();
    db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='u2'").run();
    expect(()=>messaging.interactions.readDraft(request('u2'))).toThrow();
    await expect(messaging.sendMessage(request('u2'))).rejects.toMatchObject({statusCode:404});
  });

  it('keeps exploring after submission and persists each new request with its own identity', async () => {
    const {messaging,request,db} = setup();
    db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
    const first=await messaging.sendMessage(request());
    const draft=request();draft.body={expected_draft_revision:1,state:{'$body':'周日见'}};
    expect(messaging.interactions.writeDraft(draft)).toMatchObject({submission_message_id:null});
    const next=request('u1','解释这次的变化',{'$body':'周日见'}); next.headers['idempotency-key']='next-key';
    const second=await messaging.sendMessage(next);
    expect(second.id).not.toBe(first.id);
    expect(await messaging.sendMessage(next)).toMatchObject({id:second.id});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(2);
  });
  it('merges a patch into a new immutable version and retains publication input', () => {
    const {messaging,card} = setup();
    const patch={...interactive,source_mode:'patch',supersedes_message_id:card.id,source:'$body = "周日见"'};
    const next=messaging.insertMessage('chat','a1','agent','已改',[],null,'completed',{interactive:patch});
    expect(next.interactive.source).toContain('root =');
    expect(messaging.interactions.publication(next.id)).toEqual(patch);
    expect(next.interactive.source).toContain('周日见');
    expect(messaging.message(card.id).interactive.source).toContain('周六见');
  });

  it('persists native action metadata and full local state without treating generated message as handwritten text', async () => {
    const {messaging,request} = setup();
    const req=request();delete req.body.interaction_reply.action_id;
    req.body.interaction_reply.event={type:'continue_conversation',label:'解释当前结果',message:'分析参数',context:{kind:'comparison'}};
    req.body.interaction_reply.state={'$scale':[3],'$body':'修改后的稿子'};
    const sent=await messaging.sendMessage(req);
    expect(sent.content).toBe('解释当前结果');
    expect(sent.interaction_reply).toMatchObject({event:{message:'分析参数',context:{kind:'comparison'}},state:{'$scale':[3]},fields:[{label:'草稿',value:'修改后的稿子'}]});
    const missing=request();delete missing.headers['idempotency-key'];
    await expect(messaging.sendMessage(missing)).rejects.toMatchObject({statusCode:422});
  });

});


it('freezes private-chat background in durable relays without publishing or submitting it', async () => {
  const {messaging,card,db,ctx,request}=setup();
  db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
  ctx.gateway.send=()=>true;
  const req=request('u1','为什么这里不同？'); delete req.body.interaction_reply;
  req.body.interaction_contexts=[{source_message_id:card.id,state:{'$body':'仅私聊背景'}}];
  const sent=await messaging.sendMessage(req);
  const relay=JSON.parse(all(db,'SELECT * FROM relay_tasks')[0].payload_json);
  expect(relay.metadata.interaction_contexts).toMatchObject([{source_message_id:card.id,fields:[{value:'仅私聊背景'}]}]);
  expect(sent.content).toBe('为什么这里不同？'); expect(sent.interaction_reply).toBeNull();
  expect(JSON.stringify(vi.mocked(ctx.gateway.broadcast).mock.calls)).not.toContain('仅私聊背景');
  expect(JSON.stringify(messaging.message(sent.id))).not.toContain('仅私聊背景');
  expect(all(db,'SELECT * FROM interaction_submissions')).toHaveLength(0);
  expect(messaging.interactions.readDraft(request()).draft_revision).toBe(0);
  req.body.interaction_contexts[0].state['$body']='后来修改';
  await expect(messaging.sendMessage(req)).rejects.toMatchObject({statusCode:409});
  expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
  expect(JSON.parse(all(db,'SELECT * FROM relay_tasks')[0].payload_json).metadata.interaction_contexts[0].fields[0].value).toBe('仅私聊背景');
});
it('keeps group drafts invisible to every Agent until an explicit action is submitted', async () => {
  const {messaging,card,db,ctx,request}=setup();
  db.prepare("UPDATE conversations SET type='group' WHERE id='chat'").run(); ctx.gateway.send=()=>true;
  const draft=request(); draft.body={expected_draft_revision:0,state:{'$body':'不能共享'}};
  messaging.interactions.writeDraft(draft);
  const plain=request('u1','解释一下');delete plain.body.interaction_reply;
  const sent=await messaging.sendMessage(plain);
  const relay=JSON.parse(all(db,'SELECT * FROM relay_tasks')[0].payload_json);
  expect(relay.metadata.mentioned_agent_ids).toEqual([]);
  expect(JSON.stringify(relay)).not.toContain('不能共享');expect(sent.interaction_reply).toBeNull();
  const leak=request('u1','普通文字');delete leak.body.interaction_reply;
  leak.body.interaction_contexts=[{source_message_id:card.id,state:{'$body':'不能共享'}}];
  await expect(messaging.sendMessage(leak)).rejects.toMatchObject({statusCode:422});
  await expect(messaging.sendMessage(request('u1','隐式附带',{'$body':'不能共享'}))).rejects.toMatchObject({statusCode:422});
  const explicit=request('u1',undefined,{'$body':'明确共享'});explicit.headers['idempotency-key']='explicit';
  const result=await messaging.sendMessage(explicit);
  expect(result.interaction_reply.fields[0].value).toBe('明确共享');
  const last=JSON.parse(all(db,'SELECT * FROM relay_tasks').at(-1)!.payload_json);
  expect(last.metadata.mentioned_agent_ids).toContain('a');
  expect(last.metadata.explicit_mentioned_agent_ids).toEqual([]);
});

it('does not accept background sourced from another conversation', async () => {
  const {messaging,card,db,request}=setup();
  db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('other','Other','now')").run();
  db.prepare("UPDATE messages SET conversation_id='other' WHERE id=?").run(card.id);
  const req=request('u1','解释'); delete req.body.interaction_reply;
  req.body.interaction_contexts=[{source_message_id:card.id,state:{}}];
  await expect(messaging.sendMessage(req)).rejects.toMatchObject({statusCode:404});
  expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(0);
});
