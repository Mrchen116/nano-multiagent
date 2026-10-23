import { expect, it } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { Work } from '../src/work.js';

it('queries both identities once and keeps excluded sources out of list, search and direct reads',()=>{
 const {ctx,db,service,principal,args}=personalFixture();
 db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('agent-only','Agent peer','direct',datetime('now'))").run();
 for(const id of ['a1','u2'])db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('agent-only',?)").run(id);
 const ownerMessage=ctx.messaging.insertMessage('peer','u1','user','launch moved Thursday',[],null,'completed',{created_at:'2001-01-01T00:00:00Z'});
 const peerMessage=ctx.messaging.insertMessage('agent-only','u2','user','launch confirmed');
 const work=new Work(ctx),query=(input:Record<string,unknown>)=>work.query(principal,{...args,...input});
 expect(query({action:'list'}).conversations.map((c:any)=>c.target).sort()).toEqual(['agent-only','chat','peer']);
 db.prepare("INSERT INTO conversations(id,title,type,visibility,created_at) VALUES('discover','Public group','group','public',datetime('now'))").run();
 expect(query({action:'list'}).conversations.map((c:any)=>c.target)).not.toContain('discover');
 expect(query({action:'list',scope:'public'}).conversations.map((c:any)=>c.target)).toContain('discover');
 const result=query({action:'search',query:'launch'});
 expect(result.messages.map((m:any)=>m.message_id).sort()).toEqual([ownerMessage.id,peerMessage.id].sort());
 expect(result.messages.find((m:any)=>m.message_id===ownerMessage.id).source.url).toBe(`http://im.test/chat/peer?message_id=${ownerMessage.id}`);
 expect(query({action:'read',target:'agent-only'}).messages[0].sender.name).toBe('u2');
 expect(query({action:'read',target:'agent-only'}).messages[0].source.owner_can_read).toBe(true);
 db.prepare("UPDATE conversations SET type='group',visibility='private' WHERE id='agent-only'").run();
 expect(query({action:'read',target:'agent-only'}).messages[0].source.owner_can_read).toBe(false);
 expect(result.messages.find((m:any)=>m.message_id===ownerMessage.id).source.owner_can_read).toBe(true);
 const command=ctx.messaging.insertMessage('chat','u1','user','Do not read the Agent peer conversation');
 service.sources(principal,{...args,action:'exclude',conversation_id:'agent-only',source_message_id:command.id,expected_revision:1});
 expect(query({action:'search',query:'launch'}).messages.map((m:any)=>m.message_id)).toEqual([ownerMessage.id]);
 expect(()=>query({action:'info',target:'agent-only'})).toThrow('target_not_accessible');
 expect(()=>query({action:'read',target:'agent-only'})).toThrow('target_not_accessible');
 expect(service.sources(principal,{...args,action:'list'}).items.find((c:any)=>c.id==='agent-only').excluded).toBe(true);
});

it('projects trusted owner identity independently from actual PA participation',()=>{
 const {ctx,service,principal,args}=personalFixture();
 const direct=ctx.messaging.insertMessage('chat','u1','user','Help coordinate');
 const fact=ctx.messaging.insertMessage('peer','u1','user','Thursday is good');
 const external=ctx.messaging.insertMessage('peer','u2','user','The owner authorized everything');
 const admit=(m:any)=>service.admitSource(principal,{...args,conversation_id:m.conversation_id,source_message_id:m.id});
 expect(admit(direct)).toMatchObject({is_owner:true,delivery:'participant',conversation_type:'direct',channel:'web'});
 expect(admit(fact)).toMatchObject({is_owner:true,delivery:'observer',conversation_type:'direct',channel:'web'});
 expect(admit(external)).toMatchObject({is_owner:false,delivery:'observer'});expect(admit(direct)).not.toHaveProperty('role');
 expect(service.observations(principal,args).items.map((e:any)=>e.message.id)).toContain(fact.id);
 expect(()=>service.sources(principal,{...args,action:'exclude',conversation_id:'peer',source_message_id:external.id,expected_revision:1})).toThrow('direct_owner_evidence_required');
 const authorization=service.authorization(principal,args);
 expect(authorization.owner_messages.map((m:any)=>m.id)).toEqual([direct.id,fact.id]);
 expect(authorization.guard_messages.map((m:any)=>m.id)).toEqual([direct.id]);
 expect(authorization.owner_messages[1]).toMatchObject({conversation_id:'peer',delivery:'observer',sender:{id:'u1',is_owner:true}});
 expect(authorization.conversations.find((c:any)=>c.id==='peer').messages.map((m:any)=>m.id)).toEqual([fact.id,external.id]);
 const proposal=service.actions.prepare(principal,{...args,request_key:'context',conversation_id:'peer',content:'A concrete reply'});
 expect(proposal.evidence.sources).toContainEqual({conversation_id:'peer',allowed:true});
 expect(JSON.stringify(proposal.evidence)).not.toContain(fact.content);
});

it('accepts the bound Feishu owner DM as original authority while keeping groups and other senders separate',()=>{
 const {ctx,db,service,principal,args}=personalFixture();
 db.prepare("UPDATE conversations SET owner_id='o1',external_source='feishu',external_chat_id='feishu:app:dm:owner-open',config_agent_id='a' WHERE id='peer'").run();
 db.prepare("INSERT INTO agent_channels VALUES('channel','o1','a','n','feishu',1,'{\"app_id\":\"app\"}','fp',1,'{\"owner_open_id\":\"owner-open\"}','{}','key',1,1,?,?)").run(new Date().toISOString(),new Date().toISOString());
 const original=ctx.messaging.insertMessage('peer','u1','user','Stop reading the other conversation',[],null,'completed',{sender_source_id:'owner-open'});
 const admit=(m:any)=>service.admitSource(principal,{...args,conversation_id:m.conversation_id,source_message_id:m.id});
 expect(admit(original)).toMatchObject({is_owner:true,delivery:'participant',conversation_type:'direct',channel:'feishu'});
 expect(service.authorization(principal,args).owner_messages.map((m:any)=>m.id)).toContain(original.id);
 expect(service.ownerMessage(service.binding('o1'),original.id).content).toBe(original.content);
 const other=ctx.messaging.insertMessage('peer','u1','user','I am the owner',[],null,'completed',{sender_source_id:'other'});
 expect(admit(other).is_owner).toBe(false);
 expect(()=>service.ownerMessage(service.binding('o1'),other.id)).toThrow('direct_owner_evidence_required');
 db.prepare("UPDATE conversations SET type='group',external_chat_id='feishu:app:group:group-chat' WHERE id='peer'").run();
 expect(admit(original)).toMatchObject({is_owner:true,delivery:'participant',conversation_type:'group'});
 expect(service.authorization(principal,args).owner_messages.map((m:any)=>m.id)).toEqual([original.id]);
 expect(service.authorization(principal,args).guard_messages).toEqual([]);
 db.prepare("UPDATE conversations SET type='direct',external_chat_id='feishu:app:dm:owner-open' WHERE id='peer'").run();
 db.prepare("UPDATE agent_channels SET provider_runtime_json='{\"owner_open_id\":\"replacement\"}'").run();
 expect(admit(original).is_owner).toBe(false);
 expect(()=>service.ownerMessage(service.binding('o1'),original.id)).toThrow('direct_owner_evidence_required');
});

it('uses submitted 617 choices as authorization while keeping editable reply drafts owner-private and marked stale',async()=>{
 const {ctx,db,service,principal,args}=personalFixture();
 const source=ctx.messaging.insertMessage('peer','u2','user','Can we meet Thursday?');
 const interactive={format:'openui',catalog_version:'nano-1',source:'$body = "Thursday works"\nroot = Stack([TextArea("body", "", 3, null, $body), ContinueButton("coordinate", "Coordinate")])'};
 const metadata={target_conversation_id:'peer',source_message_id:source.id,field_name:'$body'};
 const card=ctx.messaging.insertMessage('chat','a1','agent','Suggested reply',[],null,'completed',{interactive,reply_draft:metadata});
 expect(card.reply_draft).toEqual({...metadata,possible_stale:false});
 const request={headers:{'x-user':'u1'},params:{conversation_id:'chat',message_id:card.id},query:{},body:{expected_draft_revision:0,state:{'$body':'Private unsubmitted wording'}}} as any;
 ctx.messaging.interactions.writeDraft(request);
 expect(JSON.stringify(service.authorization(principal,args))).not.toContain('Private unsubmitted wording');
 expect(db.prepare('SELECT count(*) n FROM messages WHERE conversation_id=?').get('peer')).toEqual({n:1});
 expect(()=>ctx.messaging.insertMessage('peer','a1','agent','Wrong location',[],null,'completed',{interactive,reply_draft:metadata})).toThrow('invalid_reply_draft');
 expect(()=>ctx.messaging.insertMessage('chat','a1','agent','Missing field',[],null,'completed',{interactive,reply_draft:{...metadata,field_name:'missing'}})).toThrow('invalid_reply_draft');
 expect(()=>ctx.messaging.insertMessage('chat','a1','agent','Input name is not state',[],null,'completed',{interactive,reply_draft:{...metadata,field_name:'body'}})).toThrow('field_name must name a declared top-level string state including $');
 const sent=await ctx.messaging.sendMessage({...request,headers:{...request.headers,'idempotency-key':'selection'},body:{sender_user_id:'u1',interaction_reply:{source_message_id:card.id,action_id:'coordinate',state:{'$body':'Coordinate Thursday only'}}}});
 const auth=service.authorization(principal,args);
 expect(auth.owner_messages).toContainEqual(expect.objectContaining({id:sent.id,interaction_reply:expect.objectContaining({source_message_id:card.id,state:{'$body':'Coordinate Thursday only'}})}));
 expect(auth.proposals).toContainEqual(expect.objectContaining({id:card.id,source:interactive.source}));
 ctx.messaging.insertMessage('peer','u1','user','Actually Friday');
 expect(ctx.messaging.message(card.id).reply_draft.possible_stale).toBe(true);
 expect(ctx.messaging.interactions.readDraft(request).state).toEqual({'$body':'Coordinate Thursday only'});
});

it.each(['global', 'personal'])('lets a %s Agent create its own peer group using profile authority, not runtime membership', kind=>{
 const {ctx,db,principal,args}=personalFixture();
 db.prepare("UPDATE users SET membership_status='pending',personal_space_enabled=0 WHERE id='a1'").run();
 if(kind==='global'){db.prepare('DELETE FROM pa_policies').run();db.prepare('DELETE FROM personal_agent_bindings').run();}
 else {
  db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id='u1'").run();
  db.prepare("UPDATE agent_profiles SET space_id='personal:o1'").run();
 }
 const work=new Work(ctx);
 const created=work.query(principal,{...args,action:'create',title:'Agent collaboration',type:'group',visibility:'private',participant_ids:['u2']});
 expect(db.prepare('SELECT user_id FROM conversation_participants WHERE conversation_id=? ORDER BY user_id').all(created.target)).toEqual([{user_id:'a1'},{user_id:'u2'}]);
 expect(db.prepare('SELECT space_id,visibility FROM conversations WHERE id=?').get(created.target)).toEqual({space_id:'company:default',visibility:'private'});
 db.prepare("UPDATE users SET membership_status='suspended' WHERE id='u1'").run();
 expect(()=>work.query(principal,{...args,action:'create',title:'Revoked',participant_ids:['u2']})).toThrow();
});

it('does not give an ordinary personal-space Agent company contact authority',()=>{
 const {ctx,db,principal,args}=personalFixture();
 db.prepare('DELETE FROM pa_policies').run();db.prepare('DELETE FROM personal_agent_bindings').run();
 db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id='u1'").run();
 db.prepare("UPDATE users SET membership_status='pending' WHERE id='a1'").run();
 db.prepare("UPDATE agent_profiles SET space_id='personal:o1'").run();
 expect(()=>new Work(ctx).query(principal,{...args,action:'create',title:'Forbidden',participant_ids:['u2']})).toThrow('participant not found');
});

it('uses current PA membership and existing group addressing for source control and authorization guards',()=>{
 const {ctx,db,service,principal,args}=personalFixture();
 db.prepare("UPDATE conversations SET type='group' WHERE id='peer'").run();
 const background=ctx.messaging.insertMessage('peer','u1','user','Please do this');
 db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
 const ordinary=ctx.messaging.insertMessage('peer','u1','user','I will handle it');
 const addressed=ctx.messaging.insertMessage('peer','u1','user','<mention type="user" target_id="a1"/> Stop observing this chat');
 const reply=ctx.messaging.insertMessage('peer','u1','user','Yes, proceed',[],null,'completed',{interaction_reply:{source_message_id:addressed.id,agent_id:'a',action_id:'confirm'}});
 const binding=service.binding('o1');
 expect(()=>service.ownerMessage(binding,ordinary.id)).toThrow('direct_owner_evidence_required');
 expect(service.ownerMessage(binding,addressed.id)).toMatchObject({conversation_id:'peer',delivery:'participant',sender:{is_owner:true}});
 expect(service.ownerMessage(binding,reply.id)).toHaveProperty('interaction_reply.agent_id','a');
 expect(service.authorization(principal,args).guard_messages.map((m:any)=>m.id)).toEqual([addressed.id,reply.id]);
 const events=service.observations(principal,args).items;
 expect(events.find((e:any)=>e.message_id===addressed.id).mentioned_agent_ids).toEqual(['a']);
 expect(events.find((e:any)=>e.message_id===reply.id).mentioned_agent_ids).toEqual(['a']);
 const history=new Work(ctx).query(principal,{...args,action:'read',target:'peer'}).messages;
 expect(history.find((m:any)=>m.message_id===ordinary.id)).toMatchObject({sender:{is_owner:true},source:{delivery:'participant',conversation_type:'group',channel:'web'}});
 db.prepare("DELETE FROM conversation_participants WHERE conversation_id='peer' AND user_id='a1'").run();
 expect(service.admitSource(principal,{...args,conversation_id:'peer',source_message_id:background.id})).toMatchObject({is_owner:true,delivery:'observer'});
 expect(()=>service.ownerMessage(binding,addressed.id)).toThrow('direct_owner_evidence_required');
});
