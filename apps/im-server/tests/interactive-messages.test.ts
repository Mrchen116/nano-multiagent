import { describe, expect, it, vi } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';
import { all, one } from '../src/context.js';

const interactive = { format: 'openui', catalog_version: 'nano-1', source: `root = Stack([form])
form = Form("draft", ContinueButton("send", "发送给林悦"), [FormControl("草稿", TextArea("body", "", 3, null, "周六见"))])` };
function setup() {
  const {db,ctx} = fixture(); ctx.gateway.broadcast = vi.fn();
  const messaging = new Messaging(ctx); ctx.messaging = messaging;
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  const card = messaging.insertMessage('chat','a1','agent','请先确认草稿',[],null,'completed',{interactive});
  const request = (user='u1', content?: string, state: Record<string,unknown> = {}, action_id: string|undefined = content ? undefined : 'send') => ({
    headers: {'x-user':user, 'idempotency-key':'same-key'}, params:{conversation_id:'chat',message_id:card.id}, query:{},
    body:{sender_user_id:user, ...(content ? {content} : {}), interaction_reply:{source_message_id:card.id, ...(action_id ? {action_id} : {}), state}},
  }) as any;
  return {db,ctx,messaging,card,request};
}
describe('interactive message persistence', () => {
  it('publishes complete cards and keeps user draft revisions private', () => {
    const {messaging,card,ctx,request} = setup();
    expect(card.interactive).toMatchObject(interactive);
    const req=request(); req.body={expected_draft_revision:0,state:{draft:{body:{value:'周日见'}}}};
    expect(messaging.interactions.writeDraft(req)).toMatchObject({draft_revision:1});
    expect(messaging.interactions.readDraft(request('u2'))).toMatchObject({state:{},draft_revision:0});
    expect(()=>messaging.interactions.writeDraft(req)).toThrow();
    expect(ctx.gateway.broadcast).toHaveBeenCalledTimes(1);
  });
  it('saves selection and one relay atomically even while the node is offline; retries do not enqueue again', async () => {
    const {messaging,card,db,request} = setup();
    const sent=await messaging.sendMessage(request());
    expect(sent).toMatchObject({sender_user_id:'u1',content:'发送给林悦',delivery_status:'pending',interaction_reply:{source_message_id:card.id,action_label:'发送给林悦'}});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
    expect(await messaging.sendMessage(request())).toMatchObject({id:sent.id});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(1);
    expect(messaging.interactions.readDraft(request())).toMatchObject({submission_message_id:sent.id});
  });
  it('preserves handwritten content and rejects changed retries without discarding the prior result', async () => {
    const {messaging,card,db,request} = setup();
    const state={draft:{body:{value:'林悦，周六11点断桥见'}}};
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
  });
  it('copies public cards as read-only without copying viewer drafts', () => {
    const {messaging,card,db,request} = setup();
    const req=request();req.body={expected_draft_revision:0,state:{draft:{body:{value:'仅我可见'}}}};
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
    const first=await messaging.sendMessage(request());
    const draft=request();draft.body={expected_draft_revision:1,state:{draft:{body:{value:'周日见'}}}};
    expect(messaging.interactions.writeDraft(draft)).toMatchObject({submission_message_id:null});
    const next=request('u1','解释这次的变化',{draft:{body:{value:'周日见'}}}); next.headers['idempotency-key']='next-key';
    const second=await messaging.sendMessage(next);
    expect(second.id).not.toBe(first.id);
    expect(await messaging.sendMessage(next)).toMatchObject({id:second.id});
    expect(all(db,'SELECT * FROM relay_tasks')).toHaveLength(2);
  });
  it('merges a patch into a new immutable version and retains publication input', () => {
    const {messaging,card} = setup();
    const patch={...interactive,source_mode:'patch',supersedes_message_id:card.id,source:'form = Form("draft", ContinueButton("send", "发送给林悦"), [FormControl("草稿", TextArea("body", "", 3, null, "周日见"))])'};
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
    req.body.interaction_reply.state={'$scale':[3],draft:{body:{value:'修改后的稿子'}}};
    const sent=await messaging.sendMessage(req);
    expect(sent.content).toBe('解释当前结果');
    expect(sent.interaction_reply).toMatchObject({event:{message:'分析参数',context:{kind:'comparison'}},state:{'$scale':[3]},fields:[{label:'草稿',value:'修改后的稿子'}]});
    const missing=request();delete missing.headers['idempotency-key'];
    await expect(messaging.sendMessage(missing)).rejects.toMatchObject({statusCode:422});
  });

});
