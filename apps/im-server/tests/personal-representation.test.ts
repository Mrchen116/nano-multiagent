import { expect, it, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { personalFixture } from './personal-fixture.js';

it('publishes reviewed owner identity atomically without treating it as original owner authorization', () => {
  const {ctx, db, service, principal, args} = personalFixture();
  ctx.gateway.groupReply=vi.fn();
  const owner = ctx.messaging.insertMessage('chat', 'u1', 'user', 'Ask Bob to confirm Wednesday');
  const guard = service.authorizationGuard(service.authority(principal, args));
  const proposal = service.actions.prepare(principal, {...args, representation:'owner', request_key:'owner-send', conversation_id:'peer', content:'Please confirm Wednesday'});
  const reviewed = service.actions.review(principal, {...args, proposal_ref:proposal.proposal_ref, payload_digest:proposal.payload_digest, evidence_digest:proposal.evidence_digest, verdict:{decision:'allow'}});
  const receipt = service.actions.commit(principal, {...args, proposal_ref:proposal.proposal_ref, verdict_ref:reviewed.verdict_ref});
  const message = ctx.messaging.message(receipt.message_id);
  expect(message).toMatchObject({sender_user_id:'u1', sender_type:'user', pa_agent_id:'a'});
  expect(message).not.toHaveProperty('delegation');
  const event = db.prepare("SELECT payload_json FROM conversation_events WHERE message_id=? AND event_type='message.created'").get(message.id)!;
  expect(JSON.parse(String(event.payload_json))).toMatchObject({sender_user_id:'u1', pa_agent_id:'a'});
  expect(db.prepare('SELECT 1 FROM pa_source_events WHERE message_id=?').get(message.id)).toBeUndefined();
  expect(service.authorizationGuard(service.authority(principal, args))).toBe(guard);
  expect(service.authorization(principal,args).owner_messages.map(m=>m.id)).toEqual([owner.id]);
  expect(()=>service.ownerMessage(service.authority(principal,args),message.id)).toThrow('direct_owner_evidence_required');
  expect(service.actions.commit(principal,{...args,proposal_ref:proposal.proposal_ref,verdict_ref:reviewed.verdict_ref})).toEqual(receipt);
});

it('requires the selected author to have current write access and freezes the selected identity',()=>{
  const {db, service, principal, args}=personalFixture();
  const proposal={...args,request_key:'identity',conversation_id:'peer',content:'Wednesday'};
  expect(()=>service.actions.prepare(principal,{...proposal,representation:'self'})).toThrow('destination_not_accessible');
  service.actions.prepare(principal,{...proposal,representation:'owner'});
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  expect(()=>service.actions.prepare(principal,{...proposal,representation:'self'})).toThrow('operation_key_content_conflict');
  expect(()=>service.actions.prepare(principal,{...proposal,request_key:'private',conversation_id:'chat',representation:'owner'})).toThrow('invalid_owner_representation');
});

it('keeps the PA as card executor while the owner is its public author and rechecks participation',()=>{
  const {ctx,db,service,principal,args}=personalFixture();
  const interactive={format:'openui',catalog_version:'nano-1',source:'$draft = "Wednesday"\nroot = Stack([TextArea("draft", "", 3, null, $draft), ContinueButton("revise", "Revise")])'};
  const input={...args,representation:'owner',request_key:'card',conversation_id:'peer',content:'Please review',interactive};
  expect(()=>service.actions.prepare(principal,input)).toThrow('owner_interactive_requires_pa_participant');
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  const prepare=(value:any)=>{
    const p=service.actions.prepare(principal,value);
    const v=service.actions.review(principal,{...args,proposal_ref:p.proposal_ref,payload_digest:p.payload_digest,evidence_digest:p.evidence_digest,verdict:{decision:'allow'}});
    return {...args,proposal_ref:p.proposal_ref,verdict_ref:v.verdict_ref};
  };
  const first=service.actions.commit(principal,prepare(input));
  expect(ctx.messaging.message(first.message_id)).toMatchObject({sender_type:'user',pa_agent_id:'a',interactive});
  const source=ctx.messaging.interactions.source(first.message_id,'peer');
  expect(source).toMatchObject({sender_user_id:'u1',executor_user_id:'a1',executor_agent_id:'a'});
  const req={headers:{'x-user':'u2'},params:{conversation_id:'peer',message_id:first.message_id},query:{}} as any;
  expect(ctx.messaging.interactions.readDraft(req)).toMatchObject({can_interact:true,read_only:false,superseded_by:null});
  const click=ctx.messaging.interactions.prepare({id:'u2',username:'bob'},'peer',{interaction_reply:{source_message_id:first.message_id,action_id:'revise',state:{'$draft':'Friday'}}},'click');
  expect(click.snapshot).toMatchObject({agent_id:'a',state:{'$draft':'Friday'}});
  expect(ctx.messaging.interactions.contexts({id:'u2',username:'bob'},'peer',[{source_message_id:first.message_id,state:{'$draft':'Friday'}}])[0].agent_id).toBe('a');
  const replacement=prepare({...input,request_key:'replacement',interactive:{...interactive,supersedes_message_id:first.message_id}});
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='peer' AND user_id='a1'").run();
  expect(()=>service.actions.commit(principal,replacement)).toThrow('owner_interactive_requires_pa_participant');
  expect(ctx.messaging.interactions.readDraft(req).can_interact).toBe(false);
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  expect(()=>service.actions.commit(principal,replacement)).toThrow('independent_review_required');
  const second=service.actions.commit(principal,prepare({...input,request_key:'replacement',interactive:{...interactive,supersedes_message_id:first.message_id}}));
  expect(ctx.messaging.interactions.readDraft(req)).toMatchObject({can_interact:false,superseded_by:second.message_id});
  expect(db.prepare('SELECT count(*) n FROM relay_tasks WHERE message_id IN (?,?)').get(first.message_id,second.message_id)).toEqual({n:0});
});


it.each(['prepared','allowed','confirmed'])('decodes a legacy %s operation as self and never upgrades it to owner',state=>{
 const {ctx,db,service,principal,args}=personalFixture();ctx.gateway.groupReply=vi.fn();
 db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
 const input={...args,request_key:'legacy',conversation_id:'peer',content:'Legacy self message'};
 const proposal=service.actions.prepare(principal,input);
 const payload=JSON.parse(String(db.prepare('SELECT payload_json FROM pa_operations WHERE operation_id=?').get(proposal.proposal_ref)!.payload_json));
 delete payload.representation;
 const json=JSON.stringify(payload),hash=createHash('sha256').update(json).digest('hex');
 db.prepare('UPDATE pa_operations SET payload_json=?,payload_digest=? WHERE operation_id=?').run(json,hash,proposal.proposal_ref);
 const p=service.actions.prepare(principal,input);
 expect(p.proposal_ref).toBe(proposal.proposal_ref);
 expect(()=>service.actions.prepare(principal,{...input,representation:'owner'})).toThrow('operation_key_content_conflict');
 const v=service.actions.review(principal,{...args,proposal_ref:p.proposal_ref,payload_digest:p.payload_digest,evidence_digest:p.evidence_digest,verdict:{decision:'allow'}});
 const commit={...args,proposal_ref:p.proposal_ref,verdict_ref:v.verdict_ref};
 if(state==='confirmed')service.actions.commit(principal,commit);
 else if(state==='prepared')expect(p.state).toBe('prepared');
 const sent=service.actions.commit(principal,commit),message=ctx.messaging.message(sent.message_id);
 expect(message).toMatchObject({sender_user_id:'a1',sender_type:'agent',delegation:{agent_id:'a'}});
 expect(message).not.toHaveProperty('pa_agent_id');
 expect(db.prepare('SELECT count(*) n FROM messages WHERE id=?').get(sent.message_id)).toEqual({n:1});
});
