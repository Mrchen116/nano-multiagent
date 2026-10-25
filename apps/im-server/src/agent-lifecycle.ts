import type { DatabaseSync } from 'node:sqlite';
import type { FastifyInstance } from 'fastify';
import type { AgentLifecycleSnapshot } from '@nano/product-contracts';
import { all, body, fail, now, one, params, transaction, type ImContext, type Row } from './context.js';
import { agentAvailable, canAccessSpace, canContactPersonalAgent } from './identity.js';

/** Read the persistent execution intent without consulting runtime availability.
 * Args:
 *   db: Center business database.
 *   agentId: Existing product Agent identity.
 * Returns:
 *   The authoritative intent and its separately confirmed execution state.
 */
export function lifecycle(db:DatabaseSync,agentId:string):AgentLifecycleSnapshot {
  const row=one(db,'SELECT * FROM agent_lifecycle WHERE agent_id=?',agentId);
  if(!row)fail(404,'agent_not_found');
  return row as AgentLifecycleSnapshot;
}
/** Check execution authority without restricting historical reads.
 * Args:
 *   db: Center business database.
 *   agentId: Product Agent identity.
 *   revision: Generation captured when the work was originally admitted.
 * Returns:
 *   Whether this work belongs to the enabled generation. Missing generations
 *   remain compatible only before an Agent has ever been disabled.
 */
export function lifecycleAllows(db:DatabaseSync,agentId:string,revision:unknown):boolean {
  const state=lifecycle(db,agentId);
  return state.desired==='enabled' && (revision===state.revision || revision==null&&state.revision===1);
}
/** Enforce a producer's generation at the actual product write boundary.
 * Args:
 *   db: Center business database.
 *   agentId: Authenticated producer identity.
 *   revision: Original admission generation.
 * Raises:
 *   Error: HTTP 409 when this generation no longer has execution authority.
 */
export function requireLifecycle(db:DatabaseSync,agentId:string,revision:unknown):void {
  if(!lifecycleAllows(db,agentId,revision))fail(409,'agent_lifecycle_revoked');
}
export class AgentLifecycles {
  constructor(readonly ctx:ImContext) {}
  /** Publish state only to existing readers, redacting private diagnostics. */
  publish(state:AgentLifecycleSnapshot):void {
    const profile=one(this.ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=?',state.agent_id)!;
    const users=all(this.ctx.db,"SELECT * FROM users WHERE username NOT LIKE 'agent:%'").filter(user=>canAccessSpace(user,profile.space_id)||canContactPersonalAgent(this.ctx.db,user,profile));
    for(const user of users)this.ctx.gateway.broadcast([user.id],{op:'event',event_type:'agent.lifecycle.changed',data:user.owner_id===profile.owner_id?state:{...state,error_detail:null,process_instance_id:null}});
  }
  /** Deliver control directly, independently of ordinary RPC and work queues. */
  deliver(state:AgentLifecycleSnapshot):void {
    const profile=one(this.ctx.db,'SELECT node_id FROM agent_profiles WHERE agent_id=?',state.agent_id)!;
    const connection=this.ctx.gateway.nodes.get(profile.node_id);
    if(connection?.agent_lifecycle_v1)this.ctx.gateway.send(profile.node_id,{type:'agent.lifecycle.apply',payload:state});
  }
  /** Persist an authorized human change before delivering its control command.
   * Args:
   *   agentId: Agent whose owner was authenticated by the HTTP control resource.
   *   userId: Human actor recorded for audit and explicit Task suspension.
   *   input: Request identity, desired state and optimistic revision.
   *   retry: Resend the current disabled generation without advancing it.
   * Returns:
   *   The committed snapshot, independently of node confirmation.
   */
  change(agentId:string,userId:string,input:Row,retry=false):AgentLifecycleSnapshot {
    if(typeof input.request_id!=='string'||!input.request_id.trim()||input.request_id.length>200)fail(422,'request_id_required');
    if(!retry&&(typeof input.enabled!=='boolean'||!Number.isInteger(input.expected_revision)))fail(422,'invalid_lifecycle_change');
    const intent=retry?'retry':input.enabled?'enabled':'disabled';
    const state=transaction(this.ctx.db,()=>{
      const current=lifecycle(this.ctx.db,agentId);
      const prior=one(this.ctx.db,'SELECT * FROM agent_lifecycle_requests WHERE agent_id=? AND request_id=?',agentId,input.request_id);
      if(prior) {
        if(prior.intent!==intent)fail(409,'request_id_reused');
        return current;
      }
      if(retry&&current.desired!=='disabled')fail(409,'agent_not_disabled');
      if(!retry&&current.revision!==input.expected_revision)fail(409,{code:'revision_conflict',current_revision:current.revision});
      if(intent==='enabled'&&current.desired==='disabled'&&(current.observed!=='disabled'||current.applied_revision!==current.revision))fail(409,'stop_not_confirmed');
      if(!retry&&intent!==current.desired) {
        const revision=current.revision+1;
        const profile=one(this.ctx.db,'SELECT node_id FROM agent_profiles WHERE agent_id=?',agentId)!;
        const connection=this.ctx.gateway.nodes.get(profile.node_id);
        const unsupported=connection&&!connection.agent_lifecycle_v1;
        this.ctx.db.prepare(`UPDATE agent_lifecycle SET desired=?,revision=?,disabled_through_revision=?,request_id=?,actor_user_id=?,requested_at=?,observed=?,confirmed_at=NULL,error_code=?,error_detail=? WHERE agent_id=?`).run(
          intent,revision,intent==='disabled'?revision:current.disabled_through_revision,input.request_id,userId,now(),intent==='enabled'?'enabling':unsupported?'stop_unconfirmed':'stopping',unsupported?'node_upgrade_required':null,unsupported?'Update this node to confirm all managed execution has stopped':null,agentId);
      }
      const saved=lifecycle(this.ctx.db,agentId);
      this.ctx.db.prepare('INSERT INTO agent_lifecycle_requests VALUES(?,?,?,?)').run(agentId,input.request_id,intent,saved.revision);
      return saved;
    });
    // The persistent barrier and control frame precede any graph projection work.
    this.deliver(state);
    if(state.desired==='disabled') {
      this.interruptMessages(agentId);
      this.ctx.gateway.tasks.freezeAgent(agentId,userId,state.revision);
    }
    this.publish(state);
    return state;
  }
  private interruptMessages(agentId:string):void {
    const messages=all(this.ctx.db,"SELECT m.* FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE u.username=? AND (m.delivery_status='running' OR m.awaiting_permission_at IS NOT NULL)",`agent:${agentId}`);
    for(const message of messages) {
      const permissions=JSON.parse(message.permission_request_json??'[]').map((permission:Row)=>['pending','submitted'].includes(permission.status)?{...permission,status:'invalidated',reason:'agent_disabled'}:permission);
      this.ctx.db.prepare("UPDATE messages SET delivery_status='failed',awaiting_permission_at=NULL,permission_request_json=? WHERE id=?").run(JSON.stringify(permissions),message.id);
      this.ctx.messaging.event(message.conversation_id,message.id,'message.completed',{...this.ctx.messaging.message(message.id),interruption_reason:'agent_disabled'},'failed');
    }
  }
  /** Apply an observation from the currently authenticated node connection.
   * Args:
   *   agentId: Agent ownership already checked by Gateway.
   *   input: Report bound to the intended revision and process instance.
   * Returns:
   *   The current snapshot after rejecting stale or incompatible observations.
   */
  report(agentId:string,input:Row):AgentLifecycleSnapshot {
    const state=lifecycle(this.ctx.db,agentId);
    if(input.revision!==state.revision)fail(409,'lifecycle_revision_stale');
    const allowed=state.desired==='enabled'?['enabling','enabled']:['stopping','disabled','stop_unconfirmed'];
    if(!allowed.includes(input.observed))fail(409,'lifecycle_report_conflict');
    if(input.process_instance_id!==null&&(typeof input.process_instance_id!=='string'||!input.process_instance_id))fail(422,'process_instance_id_required');
    if(input.observed!=='enabling'&&state.process_instance_id!==null&&input.process_instance_id!==state.process_instance_id)fail(409,'lifecycle_process_stale');
    if(state.observed==='disabled'&&input.observed!=='disabled')return state;
    if(state.desired==='enabled'&&input.process_instance_id===null)fail(422,'process_instance_id_required');
    this.ctx.db.prepare('UPDATE agent_lifecycle SET observed=?,applied_revision=?,process_instance_id=?,confirmed_at=?,error_code=?,error_detail=? WHERE agent_id=?').run(input.observed,['enabled','disabled'].includes(input.observed)?state.revision:state.applied_revision,input.process_instance_id,['enabled','disabled'].includes(input.observed)?now():null,input.error_code??null,input.error_detail??null,agentId);
    const saved=lifecycle(this.ctx.db,agentId);this.publish(saved);return saved;
  }
}
/** Register independent lifecycle resources using existing human identity and ACLs.
 * Args:
 *   app: IM HTTP server.
 *   ctx: Shared business authority, transport and Task services.
 */
export function registerAgentLifecycleRoutes(app:FastifyInstance,ctx:ImContext):void {
  const service=new AgentLifecycles(ctx);
  const authorize=(req:any,write:boolean)=>{
    const user=ctx.identity.authenticateRequest(req),profile=one(ctx.db,'SELECT * FROM agent_profiles WHERE agent_id=?',params(req).agent_id);
    if(!profile||!agentAvailable(ctx.db,profile)||!(canAccessSpace(user,profile.space_id)||canContactPersonalAgent(ctx.db,user,profile)))fail(404,'agent_not_found');
    if(write&&(user.username.startsWith('agent:')||user.owner_id!==profile.owner_id))fail(403,'agent_owner_required');
    return {user,profile};
  };
  app.get('/im/v1/agents/:agent_id/lifecycle',async(req,reply)=>{
    reply.header('Cache-Control','private, no-store');const {user,profile}=authorize(req,false);
    const state=lifecycle(ctx.db,profile.agent_id);
    return user.owner_id===profile.owner_id?state:{...state,error_detail:null,process_instance_id:null};
  });
  for(const [method,url,retry] of [['PUT','/im/v1/agents/:agent_id/lifecycle',false],['POST','/im/v1/agents/:agent_id/lifecycle/retry',true]] as const)app.route({method,url,handler:async(req,reply)=>{
    const {user,profile}=authorize(req,true),state=service.change(profile.agent_id,user.id,body(req),retry);
    reply.header('Cache-Control','private, no-store').code(state.applied_revision===state.revision&&state.observed===state.desired?200:202);return state;
  }});
}
