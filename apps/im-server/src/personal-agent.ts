import { isInteractiveStringState } from './interactive-source.js';
import { randomUUID } from 'node:crypto';
import type { FastifyInstance } from 'fastify';
import { all, one, now, fail, body, params, transaction, type Row, type ImContext } from './context.js';
import { conversationAccess } from './conversation-access.js';
import { ConfigOperations, profileResponse } from './control.js';
import { PersonalActions, PEER_NOTICE } from './personal-actions.js';

/** Personal authority and source access are resolved from the authenticated node. */
export class PersonalAgents {
  readonly actions: PersonalActions;
  constructor(readonly ctx: ImContext) { this.actions = new PersonalActions(this); }
  get db() { return this.ctx.db; }
  binding(owner: string) { return one(this.db, 'SELECT * FROM personal_agent_bindings WHERE owner_id=?', owner); }
  policy(bindingId: string): Row {
    const p = one(this.db, 'SELECT * FROM pa_policies WHERE binding_id=?', bindingId)!;
    return { revision: p.revision, excluded_conversation_ids: JSON.parse(p.excluded_json) };
  }
  state(owner: string) {
    const binding = this.binding(owner), node=binding?one(this.db,'SELECT status FROM nodes WHERE node_id=?',binding.node_id):undefined;
    const runtime=binding?one(this.db,'SELECT available FROM pa_runtime_status WHERE binding_id=? AND node_epoch=?',binding.binding_id,binding.node_epoch):undefined;
    return {binding:binding?{...binding,status:binding.status==='active'&&(node?.status!=='online'||runtime?.available===0)?'unavailable':binding.status}:null,
      policy:binding?this.policy(binding.binding_id):null,creation:binding?.status!=="active"&&binding?{request_key:binding.request_key}:null};
  }
  authority(principal: Row, args: Row): Row {
    const b = one(this.db, `SELECT b.* FROM personal_agent_bindings b JOIN node_binding_state n ON n.node_id=b.node_id
      JOIN users u ON u.id=b.owner_user_id JOIN agent_profiles a ON a.agent_id=b.agent_id
      WHERE b.agent_id=? AND b.node_id=? AND b.owner_id=? AND n.owner_id=b.owner_id AND n.node_epoch=b.node_epoch
      AND a.is_stale=0 AND (u.membership_status='active' OR u.personal_space_enabled=1)`, args.agent_id, principal.node_id, principal.owner_id);
    if (!b || b.status !== 'active' || b.node_epoch !== principal.node_epoch ||
      (args.binding_id !== undefined && args.binding_id !== b.binding_id) || (args.epoch !== undefined && args.epoch !== b.node_epoch)) fail(403, 'personal_binding_not_authorized');
    return b;
  }
  sourceAccess(b: Row, conversationId: string, mode: 'read'|'write' = 'read') {
    const owner = conversationAccess(this.db, conversationId, b.owner_user_id);
    const agentUser = this.ctx.messaging.agentUser(b.agent_id);
    const agent = conversationAccess(this.db, conversationId, agentUser.id);
    const participated = one(this.db, 'SELECT 1 FROM conversation_participation_history WHERE conversation_id=? AND user_id=?', conversationId, b.owner_user_id);
    return [owner && participated ? owner : undefined, agent].find(access => access && (mode === 'read' || access.can_write));
  }
  sourceAllowed(b: Row, conversationId: string, mode: 'read'|'write' = 'read') {
    return !!this.sourceAccess(b, conversationId, mode) && !this.policy(b.binding_id).excluded_conversation_ids.includes(conversationId);
  }
  sourceConversations(b: Row,scope="joined"): Row[] {
    const agentUser = this.ctx.messaging.agentUser(b.agent_id);
    const policy = this.policy(b.binding_id);
    const ids = new Set<string>([...all(this.db,'SELECT conversation_id FROM conversation_participation_history WHERE user_id=?',b.owner_user_id).map(row=>row.conversation_id),
      ...this.ctx.messaging.conversations(agentUser.id,scope).map(row=>row.id),...policy.excluded_conversation_ids]);
    return [...ids].filter(id => this.sourceAccess(b,id)).map(id => {
      const viewer = conversationAccess(this.db,id,b.owner_user_id) ? b.owner_user_id : agentUser.id;
      return {...this.ctx.messaging.conversation(id,viewer),excluded:policy.excluded_conversation_ids.includes(id)};
    });
  }
  /** Change future source access using an authenticated owner message, without erasing prior work. */
  sources(principal: Row, args: Row) {
    const b = this.authority(principal,args);
    if (!['list','exclude','include'].includes(args.action)) fail(422,'invalid_source_action');
    if (args.action !== 'list') {
      this.ownerMessage(b,args.source_message_id);
      if (!this.sourceAccess(b,args.conversation_id)) fail(404,'source_not_accessible');
      const excluded = new Set(this.policy(b.binding_id).excluded_conversation_ids);
      if (args.action === 'exclude') excluded.add(args.conversation_id); else excluded.delete(args.conversation_id);
      this.updatePolicy(b.owner_id,{expected_revision:args.expected_revision,excluded_conversation_ids:[...excluded]});
    }
    return {policy:this.policy(b.binding_id),items:this.sourceConversations(b)};
  }
  /** Revalidate every ingress path, including relays queued before a policy change. */
  sourceActor(message:Row) {return message.sender_source_id?`external:${message.conversation_id}:${message.sender_source_id}`:message.sender_user_id;}
  messageAllowed(b: Row, message: Row) {
    return this.sourceAllowed(b,message.conversation_id) && !one(this.db,
      'SELECT 1 FROM pa_contact_blocks WHERE binding_id=? AND actor_id=?',b.binding_id,this.sourceActor(message));
  }
  admitSource(principal: Row, args: Row) {
    const b=this.authority(principal,args),m=one(this.db,'SELECT * FROM messages WHERE id=? AND conversation_id=?',args.source_message_id,args.conversation_id);
    if(!m || !this.messageAllowed(b,m)) return {allowed:false};
    this.db.prepare('INSERT OR REPLACE INTO pa_source_reads VALUES(?,?,?,?)').run(b.binding_id,m.id,m.conversation_id,this.policy(b.binding_id).revision);
    const role = m.sender_type === 'user' && m.sender_user_id === b.owner_user_id && !m.sender_source_id
      ? m.conversation_id === b.conversation_id ? 'owner_instruction' : 'owner_fact' : 'external';
    return {allowed:true,role,policy_revision:this.policy(b.binding_id).revision};
  }
  updatePolicy(owner: string, input: Row) {
    const b = this.binding(owner); if (!b) fail(404, 'personal_agent_not_found');
    const current = this.policy(b.binding_id);
    if (input.expected_revision !== current.revision) fail(409, 'policy_revision_conflict');
    const excluded = input.excluded_conversation_ids ?? current.excluded_conversation_ids;
    if (!Array.isArray(excluded) || excluded.some(id=>typeof id !== 'string' || id === b.conversation_id)) fail(422, 'invalid_source_exclusions');
    if (excluded.some(id=>!current.excluded_conversation_ids.includes(id)&&!this.sourceAccess(b,id))) fail(404,'source_not_accessible');
    transaction(this.db,()=> {
      this.db.prepare('UPDATE pa_policies SET revision=revision+1,excluded_json=? WHERE binding_id=?').run(JSON.stringify([...new Set(excluded)]),b.binding_id);
      this.db.prepare("UPDATE pa_operations SET state='invalidated',verdict_ref=NULL WHERE binding_id=? AND state IN ('prepared','allowed')").run(b.binding_id);
      for (const id of excluded) this.db.prepare("UPDATE pa_source_events SET state='revoked' WHERE binding_id=? AND conversation_id=? AND state!='processed'").run(b.binding_id,id);
      this.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'policy.changed',?,?,?)").run(b.binding_id,JSON.stringify({excluded_conversation_ids:excluded}),current.revision+1,now());
    });
    this.wake(b);
    return this.policy(b.binding_id);
  }
  wake(b: Row) { this.ctx.gateway.send(b.node_id,{type:'pa.observations.available',payload:{agent_id:b.agent_id,binding_id:b.binding_id,epoch:b.node_epoch}}); }
  observations(principal: Row,args:Row) {
    const b=this.authority(principal,args), policy=this.policy(b.binding_id);
    const items:Row[]=all(this.db,"SELECT * FROM pa_source_events WHERE binding_id=? AND state IN ('pending','received') ORDER BY event_id",b.binding_id)
      .filter(e=>!e.conversation_id || this.sourceAllowed(b,e.conversation_id))
      .filter(e=>!e.message_id || this.messageAllowed(b,one(this.db,'SELECT * FROM messages WHERE id=?',e.message_id)!))
      .slice(0,Math.max(1,Math.min(100,Number(args.limit)||50))).map(e=>({...e,conversation_type:e.conversation_id?one(this.db,'SELECT type FROM conversations WHERE id=?',e.conversation_id)?.type:undefined,payload:JSON.parse(e.payload_json),message:e.message_id?this.ctx.messaging.message(e.message_id):null}));
    for(const event of items) if(event.message_id) this.db.prepare("INSERT OR REPLACE INTO pa_source_reads VALUES(?,?,?,?)").run(b.binding_id,event.message_id,event.conversation_id,policy.revision);
    return {items,policy_revision:policy.revision};
  }
  acknowledge(principal: Row,args:Row) {
    const b=this.authority(principal,args);
    if(!Array.isArray(args.event_ids)||!['received','processed'].includes(args.stage)) fail(422,'invalid_observation_ack');
    transaction(this.db,()=>{ for(const id of args.event_ids) {
      const e=one(this.db,'SELECT * FROM pa_source_events WHERE event_id=? AND binding_id=?',id,b.binding_id);
      if(!e || e.state==='revoked' || (e.conversation_id&&!this.sourceAllowed(b,e.conversation_id))) fail(409,'observation_revoked');
      if(e.state!=='processed') this.db.prepare('UPDATE pa_source_events SET state=? WHERE event_id=?').run(args.stage,id);
    }});
    return {acknowledged:args.event_ids,stage:args.stage};
  }
  ownerMessage(b:Row,id:string) {
    const m=one(this.db,"SELECT * FROM messages WHERE id=? AND conversation_id=? AND sender_user_id=? AND sender_type='user' AND sender_source_id IS NULL",id,b.conversation_id,b.owner_user_id);
    if(!m) fail(403,'direct_owner_evidence_required');
    return {id:m.id,content:m.content,created_at:m.created_at};
  }
  /** Return original owner inputs and their published UI context; private drafts are not authorization. */
  authorization(principal: Row, args: Row) {
    const b = this.authority(principal,args);
    const messages = all(this.db,"SELECT * FROM messages WHERE conversation_id=? AND sender_user_id=? AND sender_type='user' AND sender_source_id IS NULL ORDER BY rowid",b.conversation_id,b.owner_user_id);
    return {policy:this.policy(b.binding_id),owner_messages:messages.map(m=>({id:m.id,content:m.content,created_at:m.created_at,
      ...(m.interaction_reply_json ? {interaction_reply:JSON.parse(m.interaction_reply_json)} : {})})),
      proposals:all(this.db,'SELECT m.id,m.content,m.created_at,i.source,i.superseded_by FROM messages m JOIN message_interactive i ON i.message_id=m.id WHERE m.conversation_id=? AND m.sender_user_id=? ORDER BY m.rowid',b.conversation_id,this.ctx.messaging.agentUser(b.agent_id).id)};
  }
  /** Validate a draft's original chat and declared state field without treating it as send permission. */
  validateReplyDraft(conversationId:string,senderId:string,input:Row,interactiveSource?:string):Row {
    const b=one(this.db,"SELECT b.* FROM personal_agent_bindings b JOIN users u ON u.username='agent:'||b.agent_id WHERE u.id=? AND b.conversation_id=?",senderId,conversationId);
    const source=one(this.db,'SELECT * FROM messages WHERE id=? AND conversation_id=?',input?.source_message_id??'',input?.target_conversation_id??'');
    if(!b||!source||!conversationAccess(this.db,source.conversation_id,b.owner_user_id)?.can_write||!this.sourceAllowed(b,source.conversation_id))fail(422,'invalid_reply_draft');
    if(typeof input.field_name!=='string'||!interactiveSource||!isInteractiveStringState(interactiveSource,input.field_name))
      fail(422,'invalid_reply_draft: field_name must name a declared top-level string state including $, for example $draft, not the TextArea name');
    return {target_conversation_id:source.conversation_id,source_message_id:source.id,field_name:input.field_name};
  }
  /** Bind navigation metadata only; 617 owns all editable draft content. */
  recordReplyDraft(messageId:string,input:Row):void {
    const m=one(this.db,'SELECT * FROM messages WHERE id=?',messageId)!;
    const interactive=one(this.db,'SELECT source FROM message_interactive WHERE message_id=?',messageId);
    const draft=this.validateReplyDraft(m.conversation_id,m.sender_user_id,input,interactive?.source);
    this.db.prepare('INSERT INTO pa_reply_drafts VALUES(?,?,?,?)').run(messageId,draft.target_conversation_id,draft.source_message_id,draft.field_name);
  }
  replyDraft(messageId:string):Row|undefined {
    const draft=one(this.db,'SELECT d.*,m.conversation_id FROM pa_reply_drafts d JOIN messages m ON m.id=d.message_id WHERE d.message_id=?',messageId);
    if(!draft)return;
    const b=one(this.db,'SELECT owner_user_id FROM personal_agent_bindings WHERE conversation_id=?',draft.conversation_id);
    const stale=!!b&&!!one(this.db,"SELECT 1 FROM messages WHERE conversation_id=? AND sender_user_id=? AND sender_type='user' AND rowid>(SELECT rowid FROM messages WHERE id=?) LIMIT 1",draft.target_conversation_id,b.owner_user_id,draft.source_message_id);
    return {target_conversation_id:draft.target_conversation_id,source_message_id:draft.source_message_id,field_name:draft.field_name,possible_stale:stale};
  }
  incidents(owner:string) {
    const b=this.binding(owner);return {items:b?all(this.db,'SELECT i.*,COALESCE(m.sender_display_name,u.display_name,i.actor_id) actor_name FROM pa_incidents i JOIN messages m ON m.id=i.source_message_id LEFT JOIN users u ON u.id=i.actor_id WHERE i.binding_id=? ORDER BY i.rowid DESC',b.binding_id):[]};
  }
  incident(principal:Row,args:Row) {
    const b=this.authority(principal,args),source=one(this.db,'SELECT * FROM messages WHERE id=?',args.source_message_id);
    if(!source||!this.sourceAllowed(b,source.conversation_id)||(source.sender_user_id===b.owner_user_id&&!source.sender_source_id))fail(404,'incident_source_not_accessible');
    const actorId=this.sourceActor(source);
    args={...args,category:args.category??'suspected_probing'};
    if(typeof args.category!=='string'||typeof args.reason!=='string')fail(422,'incident_evidence_required');
    const seen=one(this.db,'SELECT i.* FROM pa_incidents i JOIN pa_incident_evidence e ON e.incident_id=i.id WHERE e.binding_id=? AND e.message_id=? AND e.category=?',b.binding_id,source.id,args.category);
    if(seen)return {...seen,peer_notice_content:PEER_NOTICE,peer_notice_requires_review:true};
    const open=one(this.db,"SELECT * FROM pa_incidents WHERE binding_id=? AND actor_id=? AND conversation_id=? AND category=? AND status='open'",b.binding_id,actorId,source.conversation_id,args.category);
    if(open){this.db.prepare('INSERT INTO pa_incident_evidence VALUES(?,?,?,?)').run(b.binding_id,source.id,args.category,open.id);this.db.prepare('UPDATE pa_incidents SET count=count+1,source_message_id=?,reason=? WHERE id=?').run(source.id,args.reason,open.id);return {...one(this.db,'SELECT * FROM pa_incidents WHERE id=?',open.id)!,peer_notice_content:PEER_NOTICE,peer_notice_requires_review:true};}
    const id=randomUUID(),actor=source.sender_display_name?{display_name:source.sender_display_name}:one(this.db,'SELECT display_name FROM users WHERE id=?',source.sender_user_id)!;
    transaction(this.db,()=>{
      this.db.prepare('INSERT INTO pa_incidents(id,binding_id,actor_id,conversation_id,source_message_id,category,reason) VALUES(?,?,?,?,?,?,?)').run(id,b.binding_id,actorId,source.conversation_id,source.id,args.category,args.reason);
      this.db.prepare('INSERT INTO pa_incident_evidence VALUES(?,?,?,?)').run(b.binding_id,source.id,args.category,id);
      const message=this.ctx.messaging.insertMessage(b.conversation_id,this.ctx.messaging.agentUser(b.agent_id).id,'agent',`${actor.display_name}的请求可能超出了协作范围。${args.reason}\n\n原请求${source.content.length > 500 ? "（摘录）" : ""}：\n${String(source.content).slice(0,500).split("\n").map(line=>`> ${line}`).join("\n")}\n\n我已拒绝这次索取；其他工作继续。`,[],`pa-incident:${id}`,'completed',{publish:false});
      this.db.prepare('UPDATE pa_incidents SET owner_notice_message_id=? WHERE id=?').run(message.id,id);
    });
    const incident=one(this.db,'SELECT * FROM pa_incidents WHERE id=?',id)!;
    this.ctx.messaging.publishMessages([this.ctx.messaging.message(incident.owner_notice_message_id)]);
    return {...incident,peer_notice_content:PEER_NOTICE,peer_notice_requires_review:true};
  }
  async handle(principal:Row,type:string,args:Row):Promise<Row> {
    const b=this.authority(principal,args);
    switch(type) {
      case 'pa.state': return this.state(b.owner_id);
      case 'pa.sources': return this.sources(principal,args);
      case 'pa.authorization': return this.authorization(principal,args);
      case 'pa.runtime.status':
        if(typeof args.available!=='boolean')fail(422,'runtime_availability_required');
        this.db.prepare('INSERT OR REPLACE INTO pa_runtime_status VALUES(?,?,?)').run(b.binding_id,b.node_epoch,Number(args.available));return {recorded:true};
      case 'pa.source.admit': return this.admitSource(principal,args);
      case 'pa.observations.read': return this.observations(principal,args);
      case 'pa.observations.ack': return this.acknowledge(principal,args);
      case 'pa.incident.report': return this.incident(principal,args);
      case 'pa.action.prepare': return this.actions.prepare(principal,args);
      case 'pa.action.review-result': return this.actions.review(principal,args);
      case 'pa.action.commit': return this.actions.commit(principal,args);
      case 'pa.action.complete': return this.actions.complete(principal,args);
      default: fail(400,'unsupported_personal_operation');
    }
  }
}

/** Register owner-only product controls; node operations use the authenticated gateway. */
export function registerPersonalAgentRoutes(app:FastifyInstance,ctx:ImContext) {
  const pa=ctx.personal!; const ops=new ConfigOperations(ctx);
  const user=(req:any)=>ctx.identity.authenticateRequest(req);
  app.get('/im/v1/personal-agent',req=>pa.state(user(req).owner_id));
  app.post('/im/v1/personal-agent',async(req,reply)=>{
    const u=user(req),input=body(req);
    if(typeof input.request_key!=='string'||!input.request_key||typeof input.display_name!=='string'||!input.display_name.trim()) fail(422,'name_and_request_key_required');
    const node=one(ctx.db,'SELECT n.*,b.node_epoch FROM nodes n JOIN node_binding_state b ON b.node_id=n.node_id WHERE n.node_id=? AND n.owner_id=?',input.node_id,u.owner_id);
    if(!node) fail(404,'node_not_found');
    return ops.serialized(`personal:${u.owner_id}`,async()=>{
      let b=pa.binding(u.owner_id);
      if(b && b.request_key!==input.request_key) return pa.state(u.owner_id);
      if(!b) {
        const id=randomUUID(),agent=`pa_${id.replaceAll('-','').slice(0,12)}`,conversation=`c_${randomUUID().replaceAll('-','').slice(0,12)}`;
        transaction(ctx.db,()=>{
          ctx.db.prepare("UPDATE users SET personal_space_enabled=1 WHERE id=?").run(u.id);
          ctx.db.prepare('INSERT INTO personal_agent_bindings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)').run(id,u.owner_id,u.id,agent,node.node_id,node.node_epoch,conversation,input.display_name.trim(),input.request_key,'pending',null,now());
          ctx.db.prepare('INSERT INTO pa_policies(binding_id) VALUES(?)').run(id);
          ctx.db.prepare('INSERT OR IGNORE INTO pa_node_residencies VALUES(?,?)').run(node.node_id,u.owner_id);
        });
        b=pa.binding(u.owner_id)!;
      }
      if(b.status==='active') return pa.state(u.owner_id);
      const personal={bindingId:b.binding_id,ownerId:b.owner_id,conversationId:b.conversation_id,epoch:b.node_epoch};
      const recovered=await ops.recover(b.agent_id,u.owner_id);
      if(!recovered) {
        const resolved=await ctx.gateway.request(b.node_id,'node.capabilities.resolve',{});
        const catalog=resolved?.capabilities;
        if(!catalog||!Array.isArray(catalog.tools))fail(503,'node_capabilities_unavailable');
        const tools=[...new Set([...catalog.tools.filter((tool:Row)=>tool.default_on||tool.name==='send_message').map((tool:Row)=>tool.name),'personal_sources'])];
        await ops.create({agent_id:b.agent_id,display_name:b.display_name,owner_id:u.owner_id,work_mode:'global',personal_agent:personal,features:{cron_scheduling:true,task_graph:true,memory_curation:true,heartbeat:true,skill_creation:true},skills:[],tool_allowlist:tools,group_reply_policy:'manual',default_model:null,model_fallbacks:[],workspace_root:null},u.owner_id,b.node_id);
      }
      transaction(ctx.db,()=>{
        const agentUser=ctx.messaging.agentUser(b!.agent_id);
        const space=`personal:${u.owner_id}`;
        ctx.db.prepare('UPDATE agent_profiles SET space_id=? WHERE agent_id=?').run(space,b!.agent_id);
        ctx.db.prepare('INSERT OR IGNORE INTO conversations(id,title,type,owner_id,space_id,creator_id,config_agent_id,created_at) VALUES(?,?,?,?,?,?,?,?)').run(b!.conversation_id,b!.display_name,'direct',u.owner_id,space,u.id,b!.agent_id,now());
        for(const id of [u.id,agentUser.id])ctx.db.prepare('INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(b!.conversation_id,id);
        ctx.db.prepare("UPDATE personal_agent_bindings SET status='active' WHERE binding_id=?").run(b!.binding_id);
      });
      reply.code(201);return pa.state(u.owner_id);
    });
  });
  app.post('/im/v1/personal-agent/restore',async req=>{
    const u=user(req),input=body(req);
    return ops.serialized(`personal:${u.owner_id}`,async()=>{
      const b=pa.binding(u.owner_id);if(!b)fail(404,'personal_agent_not_found');
      const node=one(ctx.db,'SELECT n.*,b.node_epoch FROM nodes n JOIN node_binding_state b USING(node_id) WHERE n.node_id=? AND n.owner_id=? AND b.owner_id=?',input.node_id,u.owner_id,u.owner_id);
      if(!node)fail(404,'node_not_found');if(node.status!=='online')fail(409,'node_offline');
      const pending=one(ctx.db,"SELECT node_id FROM agent_config_operations WHERE agent_id=? AND status IN ('pending','gateway_applied')",b.agent_id);
      if(pending&&pending.node_id!==node.node_id)fail(409,'restore_already_pending');
      if(pending)await ops.recover(b.agent_id,u.owner_id);
      else if(b.node_id!==node.node_id||b.status!=='active') {
        const profile=one(ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=?',b.agent_id);if(!profile)fail(409,'complete_initial_setup_first');
        await ops.restorePersonal(profile,u.owner_id,node.node_id,node.node_epoch);
      }
      pa.wake(pa.binding(u.owner_id)!);return pa.state(u.owner_id);
    });
  });
  app.patch('/im/v1/personal-agent',async req=>{
    const u=user(req),b=pa.binding(u.owner_id),name=body(req).display_name;
    if(!b)fail(404,'personal_agent_not_found');if(typeof name!=='string'||!name.trim()||name.length>80)fail(422,'invalid_name');
    await ops.serialized(b.agent_id,async()=>{
      await ops.recover(b.agent_id,u.owner_id);
      const profile=one(ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=?',b.agent_id)!;
      await ops.update(profile,{...profileResponse(profile,true),display_name:name.trim()},u.owner_id);
    });
    return pa.state(u.owner_id);
  });
  app.patch('/im/v1/personal-agent/policy',req=>pa.updatePolicy(user(req).owner_id,body(req)));
  app.get('/im/v1/personal-agent/sources',req=>{const b=pa.binding(user(req).owner_id);return {policy:b?pa.policy(b.binding_id):null,items:b?pa.sourceConversations(b):[]};});
  app.get('/im/v1/personal-agent/incidents',req=>pa.incidents(user(req).owner_id));
  app.post('/im/v1/personal-agent/incidents/:id',req=>{
    const b=pa.binding(user(req).owner_id);if(!b)fail(404,'personal_agent_not_found');
    const incident=one(ctx.db,'SELECT * FROM pa_incidents WHERE id=? AND binding_id=?',params(req).id,b.binding_id),action=body(req).action;
    if(!incident)fail(404,'incident_not_found');if(!['block','misunderstanding'].includes(action))fail(422,'invalid_incident_action');
    transaction(ctx.db,()=>{
      if(action==='block')ctx.db.prepare('INSERT OR IGNORE INTO pa_contact_blocks VALUES(?,?)').run(b.binding_id,incident.actor_id);
      ctx.db.prepare('UPDATE pa_incidents SET status=? WHERE id=?').run(action==='block'?'blocked':'closed',incident.id);
      ctx.db.prepare('UPDATE pa_policies SET revision=revision+1 WHERE binding_id=?').run(b.binding_id);
    });pa.wake(b);return pa.incidents(b.owner_id).items.find((i:Row)=>i.id===incident.id);
  });
}
