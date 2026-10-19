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
    return { revision: p.revision, observation_enabled: !!p.observation_enabled, excluded_conversation_ids: JSON.parse(p.excluded_json) };
  }
  state(owner: string) {
    const binding = this.binding(owner), node=binding?one(this.db,'SELECT status FROM nodes WHERE node_id=?',binding.node_id):undefined;
    return {binding:binding?{...binding,status:binding.status==='active'&&node?.status!=='online'?'unavailable':binding.status}:null,
      policy:binding?this.policy(binding.binding_id):null,creation:binding?.status!=="active"&&binding?{request_key:binding.request_key,initial_goal:binding.initial_goal}:null};
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
  sourceAllowed(b: Row, conversationId: string, mode: 'read'|'write' = 'read') {
    const ownerAccess = conversationAccess(this.db, conversationId, b.owner_user_id);
    const agentUser=one(this.db,'SELECT id FROM users WHERE username=?',`agent:${b.agent_id}`);
    const contactAccess=agentUser?conversationAccess(this.db,conversationId,agentUser.id):undefined;
    const access=ownerAccess ?? (contactAccess?.is_member ? contactAccess : undefined);
    if (!access || (mode === 'write' && !access.can_write)) return false;
    if (ownerAccess && !one(this.db, 'SELECT 1 FROM conversation_participation_history WHERE conversation_id=? AND user_id=?', conversationId, b.owner_user_id) && !contactAccess?.is_member) return false;
    return !this.policy(b.binding_id).excluded_conversation_ids.includes(conversationId);
  }
  updatePolicy(owner: string, input: Row) {
    const b = this.binding(owner); if (!b) fail(404, 'personal_agent_not_found');
    const current = this.policy(b.binding_id);
    if (input.expected_revision !== current.revision) fail(409, 'policy_revision_conflict');
    const excluded = input.excluded_conversation_ids ?? current.excluded_conversation_ids;
    if (!Array.isArray(excluded) || excluded.some(id=>typeof id !== 'string' || id === b.conversation_id)) fail(422, 'invalid_source_exclusions');
    if (input.observation_enabled !== undefined && typeof input.observation_enabled !== 'boolean') fail(422,'invalid_observation_setting');
    transaction(this.db,()=> {
      this.db.prepare('UPDATE pa_policies SET revision=revision+1,observation_enabled=?,excluded_json=? WHERE binding_id=?').run(Number(input.observation_enabled ?? current.observation_enabled),JSON.stringify([...new Set(excluded)]),b.binding_id);
      this.db.prepare("UPDATE pa_operations SET state='invalidated',verdict_ref=NULL WHERE binding_id=? AND state IN ('prepared','allowed')").run(b.binding_id);
      for (const id of excluded) this.db.prepare("UPDATE pa_source_events SET state='revoked' WHERE binding_id=? AND conversation_id=? AND state!='processed'").run(b.binding_id,id);
      this.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'policy.changed',?,?,?)").run(b.binding_id,JSON.stringify({excluded_conversation_ids:excluded}),current.revision+1,now());
    });
    this.wake(b);
    return this.policy(b.binding_id);
  }
  wake(b: Row) { this.ctx.gateway.send(b.node_id,{type:'pa.observations.available',payload:{agent_id:b.agent_id,binding_id:b.binding_id,epoch:b.node_epoch}}); }
  history(principal: Row, args: Row): Row {
    const b=this.authority(principal,args), policy=this.policy(b.binding_id);
    if (args.conversation_id && !this.sourceAllowed(b,args.conversation_id)) fail(404,'source_not_accessible');
    const limit=Math.max(1,Math.min(100,Number(args.limit)||30));
    const clauses=['m.rowid < ?'], values:any[]=[Number(args.cursor)||Number.MAX_SAFE_INTEGER];
    if(args.conversation_id){clauses.push('m.conversation_id=?');values.push(args.conversation_id);}
    if(args.keyword){clauses.push("instr(lower(m.content),lower(?))>0");values.push(String(args.keyword));}
    if(args.before){clauses.push('m.created_at<?');values.push(args.before);}
    if(args.after){clauses.push('m.created_at>=?');values.push(args.after);}
    if(args.participant_id){clauses.push('EXISTS(SELECT 1 FROM conversation_participation_history hp WHERE hp.conversation_id=m.conversation_id AND hp.user_id=?)');values.push(args.participant_id);}
    const allowed=all(this.db,'SELECT conversation_id FROM conversation_participation_history WHERE user_id=?',b.owner_user_id).map(c=>c.conversation_id).filter(id=>this.sourceAllowed(b,id));
    if(!allowed.length)return {items:[],next_cursor:null,coverage:'current_authorized_participated_conversations'};
    clauses.push(`m.conversation_id IN (${allowed.map(()=>'?').join(',')})`);values.push(...allowed);
    const candidates=all(this.db,`SELECT m.rowid source_cursor,m.*,u.display_name author_name FROM messages m JOIN users u ON u.id=m.sender_user_id
      JOIN conversation_participation_history h ON h.conversation_id=m.conversation_id AND h.user_id=? WHERE ${clauses.join(' AND ')} ORDER BY m.rowid DESC LIMIT ?`,b.owner_user_id,...values,limit+1);
    const matches=candidates.filter(m=>this.sourceAllowed(b,m.conversation_id)).slice(0,limit+1), page=matches.slice(0,limit);
    for(const m of page) this.db.prepare('INSERT OR REPLACE INTO pa_source_reads VALUES(?,?,?,?)').run(b.binding_id,m.id,m.conversation_id,policy.revision);
    return {items:page.map(m=>({conversation_id:m.conversation_id,message_id:m.id,author_id:m.sender_user_id,author_name:m.author_name,content:m.content,created_at:m.created_at,source_policy_revision:policy.revision,url:`/chat/${m.conversation_id}?message_id=${m.id}`})),next_cursor:matches.length>limit?page.at(-1)!.source_cursor:null,coverage:'current_authorized_participated_conversations'};
  }
  readHistory(principal: Row,args:Row) {
    const b=this.authority(principal,args);
    if(!args.message_id) return this.history(principal,args);
    const message=one(this.db,'SELECT rowid source_cursor,* FROM messages WHERE id=?',args.message_id);
    if(!message || !this.sourceAllowed(b,message.conversation_id)) fail(404,'source_not_accessible');
    const after=all(this.db,'SELECT rowid source_cursor FROM messages WHERE conversation_id=? AND rowid>=? ORDER BY rowid LIMIT ?',message.conversation_id,message.source_cursor,1+Math.max(0,Math.min(50,Number(args.context_after)||0)));
    return this.history(principal,{...args,keyword:undefined,conversation_id:message.conversation_id,cursor:args.cursor ?? after.at(-1)!.source_cursor+1});
  }
  observations(principal: Row,args:Row) {
    const b=this.authority(principal,args), policy=this.policy(b.binding_id);
    const items:Row[]=all(this.db,"SELECT * FROM pa_source_events WHERE binding_id=? AND state IN ('pending','received') ORDER BY event_id",b.binding_id)
      .filter(e=>!e.conversation_id || (policy.observation_enabled && this.sourceAllowed(b,e.conversation_id)))
      .filter(e=>!e.message_id || !one(this.db,"SELECT 1 FROM pa_contact_blocks k JOIN messages m ON m.sender_user_id=k.actor_id WHERE k.binding_id=? AND m.id=?",b.binding_id,e.message_id))
      .slice(0,Math.max(1,Math.min(100,Number(args.limit)||50))).map(e=>({...e,payload:JSON.parse(e.payload_json),message:e.message_id?this.ctx.messaging.message(e.message_id):null}));
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
    const m=one(this.db,"SELECT * FROM messages WHERE id=? AND conversation_id=? AND sender_user_id=? AND sender_type='user'",id,b.conversation_id,b.owner_user_id);
    if(!m) fail(403,'direct_owner_evidence_required');
    return {id:m.id,content:m.content,created_at:m.created_at};
  }
  ownerDecisions(bindingId:string,taskRef?:string) {
    return all(this.db,"SELECT * FROM pa_decisions WHERE binding_id=? AND status IN ('resolved','declined')",bindingId)
      .filter(d=>!taskRef||d.task_ref===taskRef).map(d=>({decision_id:d.id,task_ref:d.task_ref,prompt:JSON.parse(d.payload_json),owner_resolution:JSON.parse(d.resolution_json??'null'),status:d.status,revision:d.revision}));
  }
  scopes(principal:Row,args:Row) {
    const b=this.authority(principal,args);
    const rows=all(this.db,'SELECT * FROM pa_goal_scopes WHERE binding_id=?',b.binding_id).filter(s=>!args.task_ref||s.task_ref===args.task_ref);
    return {binding:b,policy:this.policy(b.binding_id),assistance:this.assistance(b.owner_id).items,owner_decisions:this.ownerDecisions(b.binding_id,args.task_ref),owner_message:args.source_message_id?this.ownerMessage(b,args.source_message_id):null,conversations:this.ctx.messaging.conversations(b.owner_user_id).filter(c=>this.sourceAllowed(b,c.id)).map(c=>({id:c.id,title:c.title,participants:c.participants})),scopes:rows.map(s=>({...s,scope:JSON.parse(s.scope_json)}))};
  }
  createScope(principal:Row,args:Row) {
    const b=this.authority(principal,args), evidence=this.ownerMessage(b,args.source_message_id);
    if(!args.scope || !Array.isArray(args.scope.allowed_conversation_ids)||!Array.isArray(args.scope.allowed_action_kinds)) fail(422,'invalid_scope');
    for(const id of args.scope.allowed_conversation_ids) if(!this.sourceAllowed(b,id,'write')) fail(403,'scope_target_not_accessible');
    let taskRef=args.task_ref;
    if(!taskRef) {
      const task=this.ctx.gateway.tasks.execute({kind:'agent',id:b.agent_id,node_id:b.node_id,source_message_id:evidence.id},'create',{conversation_id:b.conversation_id,title:String(args.title||evidence.content).slice(0,240),description:args.goal_description||evidence.content,mode:'dag',request_key:`pa-goal:${b.binding_id}:${evidence.id}`});
      taskRef=task.graph_id;
    }
    const graph=one(this.db,'SELECT * FROM task_graphs WHERE graph_id=?',taskRef);
    if(!graph || !this.sourceAllowed(b,graph.conversation_id)) fail(404,'task_not_accessible');
    const previous=one(this.db,'SELECT * FROM pa_goal_scopes WHERE binding_id=? AND task_ref=?',b.binding_id,taskRef);
    if(previous && previous.owner_message_id===evidence.id) return {...previous,scope:JSON.parse(previous.scope_json)};
    if(previous && graph.conversation_id===b.conversation_id && (args.title || args.goal_description)) {
      const doc=JSON.parse(graph.document_json);
      this.ctx.gateway.tasks.execute({kind:'agent',id:b.agent_id,node_id:b.node_id},'apply',{graph_id:taskRef,base_revision:graph.revision,request_key:`pa-goal-update:${evidence.id}`,change_note:'Owner updated this goal',operations:[{op:'update_task',node_id:doc.root_node_id,patch:{...(args.title?{title:args.title}:{}),...(args.goal_description?{description:args.goal_description}:{})}}]});
    }
    const scopeId=previous?.scope_id??randomUUID();
    this.db.prepare(`INSERT INTO pa_goal_scopes(scope_id,binding_id,task_ref,owner_message_id,owner_text,scope_json) VALUES(?,?,?,?,?,?)
      ON CONFLICT(binding_id,task_ref) DO UPDATE SET owner_message_id=excluded.owner_message_id,owner_text=excluded.owner_text,scope_json=excluded.scope_json,revision=pa_goal_scopes.revision+1,revoked=0`).run(scopeId,b.binding_id,taskRef,evidence.id,previous ? previous.owner_text+'\n\n[Owner update]\n'+evidence.content : evidence.content,JSON.stringify(args.scope));
    this.db.prepare('INSERT OR IGNORE INTO pa_assistance(binding_id,task_ref,scope_id) VALUES(?,?,?)').run(b.binding_id,taskRef,scopeId);
    return {...one(this.db,'SELECT * FROM pa_goal_scopes WHERE scope_id=?',scopeId),scope:args.scope};
  }
  /** Only the host's independent interpretation of a current owner message can call this. */
  ownerControl(principal:Row,args:Row) {
    const b=this.authority(principal,args); this.ownerMessage(b,args.source_message_id);
    if(['pause','resume','draft_only'].includes(args.action)) {
      const a=one(this.db,'SELECT * FROM pa_assistance WHERE binding_id=? AND task_ref=?',b.binding_id,args.task_ref);
      if(!a || a.revision!==args.expected_revision) fail(409,'assistance_revision_conflict');
      transaction(this.db,()=>{
        if(args.action==='draft_only') {
          const scope=one(this.db,'SELECT * FROM pa_goal_scopes WHERE binding_id=? AND task_ref=?',b.binding_id,args.task_ref);
          if(!scope)fail(404,'goal_scope_not_found');
          const value=JSON.parse(scope.scope_json);value.allowed_action_kinds=value.allowed_action_kinds.filter((kind:string)=>kind!=='message');
          value.constraints=(value.constraints??'')+'; Only prepare private drafts until owner authorizes sending again.';
          this.db.prepare('UPDATE pa_goal_scopes SET scope_json=?,revision=revision+1 WHERE scope_id=?').run(JSON.stringify(value),scope.scope_id);
        }
        this.db.prepare('UPDATE pa_assistance SET paused=?,revision=revision+1 WHERE binding_id=? AND task_ref=?').run(args.action==='draft_only'?a.paused:Number(args.action==='pause'),b.binding_id,args.task_ref);
        this.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'assistance.changed',?,?,?)").run(b.binding_id,JSON.stringify({task_ref:args.task_ref,paused:args.action==='pause',preference:args.action}),this.policy(b.binding_id).revision,now());
      });
      this.wake(b);return this.assistance(b.owner_id);
    }
    const policy=this.policy(b.binding_id);
    if(args.action==='observe') return this.updatePolicy(b.owner_id,{expected_revision:args.expected_revision,observation_enabled:args.enabled});
    if(['exclude','include'].includes(args.action) && typeof args.conversation_id==='string' && args.conversation_id!==b.conversation_id) {
      if(!conversationAccess(this.db,args.conversation_id,b.owner_user_id))fail(404,'source_not_accessible');
      return this.updatePolicy(b.owner_id,{expected_revision:args.expected_revision,excluded_conversation_ids:args.action==='exclude'?[...policy.excluded_conversation_ids,args.conversation_id]:policy.excluded_conversation_ids.filter((id:string)=>id!==args.conversation_id)});
    }
    fail(422,'invalid_owner_control');
  }
  assistance(owner:string) {
    const b=this.binding(owner); if(!b) return {items:[]};
    return {items:all(this.db,'SELECT * FROM pa_assistance WHERE binding_id=?',b.binding_id).flatMap(a=>{
      const graph=one(this.db,'SELECT * FROM task_graphs WHERE graph_id=?',a.task_ref);
      if(!graph||!this.sourceAllowed(b,graph.conversation_id)) return [];
      const d=JSON.parse(graph.document_json),root=d.nodes.find((n:Row)=>n.id===d.root_node_id);
      return [{...a,paused:!!a.paused,task:{title:root.title,status:root.status,result:root.result}}];
    })};
  }
  updateAssistance(principal:Row,args:Row) {
    const b=this.authority(principal,args), a=one(this.db,'SELECT * FROM pa_assistance WHERE binding_id=? AND task_ref=?',b.binding_id,args.task_ref);
    if(!a) fail(404,'assistance_not_found');
    if(args.expected_revision!==a.revision) fail(409,'assistance_revision_conflict');
    if(args.next_check_at && !args.schedule_id) fail(422,'schedule_receipt_required');
    const completed=args.status==='completed';
    if(completed) {
      const graph=one(this.db,'SELECT * FROM task_graphs WHERE graph_id=?',args.task_ref);
      if(!graph || !this.sourceAllowed(b,graph.conversation_id)) fail(404,'task_not_accessible');
      if(graph.conversation_id!==b.conversation_id && JSON.parse(graph.document_json).nodes.find((node:Row)=>node.id===JSON.parse(graph.document_json).root_node_id)?.status!=='done') fail(409,'shared_task_result_requires_reviewed_update');
      if(graph.conversation_id===b.conversation_id) {
        const doc=JSON.parse(graph.document_json);
        this.ctx.gateway.tasks.execute({kind:'agent',id:b.agent_id,node_id:b.node_id},'apply',{graph_id:args.task_ref,base_revision:graph.revision,request_key:`pa-complete:${b.binding_id}:${args.task_ref}:${a.revision}`,change_note:'Goal outcome confirmed',operations:[{op:'update_task',node_id:doc.root_node_id,patch:{status:'done',...(typeof args.result==='string'?{result:args.result}:{})}}]});
      }
    }
    const value=(key:string)=>key in args?args[key]:a[key];
    this.db.prepare('UPDATE pa_assistance SET next_action=?,next_check_at=?,waiting_on=?,schedule_id=?,status=?,revision=revision+1 WHERE binding_id=? AND task_ref=?').run(completed?null:value('next_action'),completed?null:value('next_check_at'),completed?null:value('waiting_on'),value('schedule_id'),args.status??a.status,b.binding_id,args.task_ref);
    if(completed) {
      this.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'assistance.changed',?,?,?)").run(b.binding_id,JSON.stringify({task_ref:args.task_ref,completed:true}),this.policy(b.binding_id).revision,now());this.wake(b);
    }
    return this.assistance(b.owner_id);
  }
  createDecision(principal:Row,args:Row) {
    const b=this.authority(principal,args), d=args.decision??args;
    if(!d.question || !['draft','choice'].includes(d.kind)||!Array.isArray(d.options??[])) fail(422,'invalid_decision');
    if(d.target_conversation_id&&!this.sourceAllowed(b,d.target_conversation_id)) fail(404,'source_not_accessible');
    const old=d.request_key?one(this.db,'SELECT * FROM pa_decisions WHERE binding_id=? AND request_key=?',b.binding_id,d.request_key):null;
    const id=old?.id??randomUUID();
    if(!old) this.db.prepare('INSERT INTO pa_decisions(id,binding_id,task_ref,kind,payload_json,request_key) VALUES(?,?,?,?,?,?)').run(id,b.binding_id,d.task_ref??null,d.kind,JSON.stringify({...d,options:d.options??[],recommended:d.recommended??null}),d.request_key??null);
    return this.decisions(b.owner_id).items.find((item:Row)=>item.id===id);
  }
  decisions(owner:string) {
    const b=this.binding(owner); if(!b) return {items:[]};
    return {items:all(this.db,'SELECT * FROM pa_decisions WHERE binding_id=?',b.binding_id).map(d=>({...JSON.parse(d.payload_json),id:d.id,task_ref:d.task_ref,kind:d.kind,status:d.status,revision:d.revision,snooze_until:d.snooze_until}))};
  }
  incidents(owner:string) {
    const b=this.binding(owner);return {items:b?all(this.db,'SELECT i.*,u.display_name actor_name FROM pa_incidents i JOIN users u ON u.id=i.actor_id WHERE i.binding_id=? ORDER BY i.rowid DESC',b.binding_id):[]};
  }
  incident(principal:Row,args:Row) {
    const b=this.authority(principal,args),source=one(this.db,'SELECT * FROM messages WHERE id=?',args.source_message_id);
    if(!source||!this.sourceAllowed(b,source.conversation_id)||source.sender_user_id===b.owner_user_id)fail(404,'incident_source_not_accessible');
    args={...args,category:args.category??'suspected_probing'};
    if(typeof args.category!=='string'||typeof args.reason!=='string')fail(422,'incident_evidence_required');
    const seen=one(this.db,'SELECT i.* FROM pa_incidents i JOIN pa_incident_evidence e ON e.incident_id=i.id WHERE e.binding_id=? AND e.message_id=? AND e.category=?',b.binding_id,source.id,args.category);
    if(seen)return {...seen,peer_notice_content:PEER_NOTICE,peer_notice_requires_review:true};
    const open=one(this.db,"SELECT * FROM pa_incidents WHERE binding_id=? AND actor_id=? AND conversation_id=? AND category=? AND status='open'",b.binding_id,source.sender_user_id,source.conversation_id,args.category);
    if(open){this.db.prepare('INSERT INTO pa_incident_evidence VALUES(?,?,?,?)').run(b.binding_id,source.id,args.category,open.id);this.db.prepare('UPDATE pa_incidents SET count=count+1,source_message_id=?,reason=? WHERE id=?').run(source.id,args.reason,open.id);return {...one(this.db,'SELECT * FROM pa_incidents WHERE id=?',open.id)!,peer_notice_content:PEER_NOTICE,peer_notice_requires_review:true};}
    const id=randomUUID(),actor=one(this.db,'SELECT display_name FROM users WHERE id=?',source.sender_user_id)!;
    transaction(this.db,()=>{
      this.db.prepare('INSERT INTO pa_incidents(id,binding_id,actor_id,conversation_id,source_message_id,category,reason) VALUES(?,?,?,?,?,?,?)').run(id,b.binding_id,source.sender_user_id,source.conversation_id,source.id,args.category,args.reason);
      this.db.prepare('INSERT INTO pa_incident_evidence VALUES(?,?,?,?)').run(b.binding_id,source.id,args.category,id);
      const message=this.ctx.messaging.insertMessage(b.conversation_id,this.ctx.messaging.agentUser(b.agent_id).id,'agent',`${actor.display_name}的请求可能超出了协作范围。${args.reason}\n我已拒绝这次索取；其他工作继续。`,[],`pa-incident:${id}`,'completed',{publish:false});
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
      case 'pa.history.search': return this.history(principal,args);
      case 'pa.history.read': return this.readHistory(principal,args);
      case 'pa.observations.read': return this.observations(principal,args);
      case 'pa.observations.ack': return this.acknowledge(principal,args);
      case 'pa.scope.resolve': return this.scopes(principal,args);
      case 'pa.scope.create': return this.createScope(principal,args);
      case 'pa.owner.control': return this.ownerControl(principal,args);
      case 'pa.assistance.read': return this.assistance(b.owner_id);
      case 'pa.assistance.update': return this.updateAssistance(principal,args);
      case 'pa.decision.create': return this.createDecision(principal,args);
      case 'pa.incident.report': return this.incident(principal,args);
      case 'pa.action.prepare': return this.actions.prepare(principal,args);
      case 'pa.action.review-result': return this.actions.review(principal,args);
      case 'pa.action.commit': return this.actions.commit(principal,args);
      case 'pa.action.complete': return this.actions.complete(principal,args);
      case 'pa.cleanup.ack':
        this.db.prepare("UPDATE pa_cleanup_operations SET status='completed' WHERE binding_id=? AND operation_id=?").run(b.binding_id,args.operation_id);return {status:'completed'};
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
          ctx.db.prepare('INSERT INTO personal_agent_bindings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)').run(id,u.owner_id,u.id,agent,node.node_id,node.node_epoch,conversation,input.display_name.trim(),input.request_key,'pending',input.initial_goal??null,now());
          ctx.db.prepare('INSERT INTO pa_policies(binding_id,observation_enabled) VALUES(?,?)').run(id,Number(input.observation_enabled!==false));
          ctx.db.prepare('INSERT OR IGNORE INTO pa_node_residencies VALUES(?,?)').run(node.node_id,u.owner_id);
        });
        b=pa.binding(u.owner_id)!;
      }
      if(b.status==='active') return pa.state(u.owner_id);
      const personal={bindingId:b.binding_id,ownerId:b.owner_id,conversationId:b.conversation_id,epoch:b.node_epoch};
      const recovered=await ops.recover(b.agent_id,u.owner_id);
      if(!recovered) await ops.create({agent_id:b.agent_id,display_name:b.display_name,owner_id:u.owner_id,work_mode:'global',personal_agent:personal,features:{cron_scheduling:true,task_graph:true,memory_curation:true,heartbeat:true,skill_creation:false},skills:[],tool_allowlist:['inbox','conversations','send_message','personal_assistant','personal_files','web_search','subagent','subagent_fork','interrupt_agent','list_agents','structured_output','memory','task_graph','get_goal','set_goal','todo_write','schedule_list','schedule_history','workflow'],group_reply_policy:'manual',default_model:null,model_fallbacks:[],workspace_root:null},u.owner_id,b.node_id);
      transaction(ctx.db,()=>{
        const agentUser=ctx.messaging.agentUser(b!.agent_id);
        const space=`personal:${u.owner_id}`;
        ctx.db.prepare('UPDATE agent_profiles SET space_id=? WHERE agent_id=?').run(space,b!.agent_id);
        ctx.db.prepare('INSERT OR IGNORE INTO conversations(id,title,type,owner_id,space_id,creator_id,config_agent_id,created_at) VALUES(?,?,?,?,?,?,?,?)').run(b!.conversation_id,b!.display_name,'direct',u.owner_id,space,u.id,b!.agent_id,now());
        for(const id of [u.id,agentUser.id])ctx.db.prepare('INSERT OR IGNORE INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(b!.conversation_id,id);
        ctx.db.prepare("UPDATE personal_agent_bindings SET status='active' WHERE binding_id=?").run(b!.binding_id);
      });
      if(b.initial_goal) {
        const m=ctx.messaging.insertMessage(b.conversation_id,u.id,'user',b.initial_goal,[],`pa-first-goal:${b.binding_id}`);
        const profile=one(ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=?',b.agent_id)!;
        ctx.gateway.relayMessage(m,profile,`pa-first-goal:${b.binding_id}`);
      }
      reply.code(201);return pa.state(u.owner_id);
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
    transaction(ctx.db,()=>{
      ctx.db.prepare('UPDATE personal_agent_bindings SET display_name=? WHERE binding_id=?').run(name.trim(),b.binding_id);
      ctx.db.prepare('UPDATE users SET display_name=? WHERE username=?').run(name.trim(),`agent:${b.agent_id}`);
      ctx.db.prepare('UPDATE conversations SET title=? WHERE id=?').run(name.trim(),b.conversation_id);
    }); return pa.state(u.owner_id);
  });
  app.patch('/im/v1/personal-agent/policy',req=>pa.updatePolicy(user(req).owner_id,body(req)));
  app.get('/im/v1/personal-agent/assistance',req=>pa.assistance(user(req).owner_id));
  app.get('/im/v1/personal-agent/decisions',req=>pa.decisions(user(req).owner_id));
  for(const action of ['pause','resume'])app.post(`/im/v1/personal-agent/assistance/:taskRef/${action}`,req=>{
    const b=pa.binding(user(req).owner_id);if(!b)fail(404,'personal_agent_not_found');
    const changed=ctx.db.prepare("UPDATE pa_assistance SET paused=?,status='pending',revision=revision+1 WHERE binding_id=? AND task_ref=? AND revision=?").run(Number(action==='pause'),b.binding_id,params(req).taskRef,body(req).expected_revision);
    if(!changed.changes)fail(409,'assistance_revision_conflict');
    ctx.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'assistance.changed',?,?,?)").run(b.binding_id,JSON.stringify({task_ref:params(req).taskRef,paused:action==='pause'}),pa.policy(b.binding_id).revision,now());
    pa.wake(b);return pa.assistance(b.owner_id);
  });
  app.post('/im/v1/personal-agent/decisions/:id',req=>{
    const b=pa.binding(user(req).owner_id);if(!b)fail(404,'personal_agent_not_found');
    const d=one(ctx.db,'SELECT * FROM pa_decisions WHERE id=? AND binding_id=?',params(req).id,b.binding_id),input=body(req);
    if(!d)fail(404,'decision_not_found');
    if(d.resolution_json&&JSON.parse(d.resolution_json).request_key===input.request_key)return pa.decisions(b.owner_id).items.find((x:Row)=>x.id===d.id);
    if(d.revision!==input.expected_revision||d.status!=='pending')fail(409,'decision_revision_conflict');
    const payload=JSON.parse(d.payload_json);
    if(input.option&&!payload.options.some((o:Row)=>o.id===input.option)&&d.kind!=='draft')fail(422,'invalid_decision_option');
    if(!input.option&&!input.decline&&!input.snooze_until)fail(422,'decision_required');
    transaction(ctx.db,()=>{
      ctx.db.prepare('UPDATE pa_decisions SET status=?,revision=revision+1,snooze_until=?,resolution_json=? WHERE id=?').run(input.snooze_until?'pending':input.decline?'declined':'resolved',input.snooze_until??null,JSON.stringify(input),d.id);
      ctx.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'owner.decision',?,?,?)").run(b.binding_id,JSON.stringify({decision_id:d.id,...input}),pa.policy(b.binding_id).revision,now());
    });pa.wake(b);return pa.decisions(b.owner_id).items.find((x:Row)=>x.id===d.id);
  });
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
  app.get('/im/v1/personal-agent/cleanup',req=>{const b=pa.binding(user(req).owner_id);return {items:b?all(ctx.db,'SELECT * FROM pa_cleanup_operations WHERE binding_id=?',b.binding_id):[]};});
  app.post('/im/v1/personal-agent/cleanup',req=>{
    const b=pa.binding(user(req).owner_id),input=body(req);if(!b)fail(404,'personal_agent_not_found');if(!input.request_key)fail(422,'request_key_required');
    ctx.db.prepare('INSERT OR IGNORE INTO pa_cleanup_operations VALUES(?,?,?,?,?,?)').run(randomUUID(),b.binding_id,input.conversation_id??null,input.request_key,'pending',now());
    const op=one(ctx.db,'SELECT * FROM pa_cleanup_operations WHERE binding_id=? AND request_key=?',b.binding_id,input.request_key)!;
    ctx.db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'cleanup.requested',?,?,?)").run(b.binding_id,JSON.stringify(op),pa.policy(b.binding_id).revision,now());pa.wake(b);return op;
  });
}
