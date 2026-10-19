import type { ExternalDelivery } from './external.js';
import { createHash, randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimePort, SessionBinding } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { ProductCall } from './global-agent.js';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

type Data = Record<string, unknown>;
interface Verdict { decision: 'allow' | 'deny' | 'needs_owner' | 'unavailable'; reason: string; scopes?: Data[]; controls?: Data[]; incident?: {reason:string} }
interface Options {
  nodeId: string; ownerId: string; agents: AgentConfiguration[]; store: NodeStore; inbox: InboxStore; runtime: RuntimePort;
  relay: {request(type: string, payload: Data): Promise<ProtocolFrame>}; onError(error: unknown): void;
}

/** Coordinates personal product facts; DSH remains the sole execution loop. */
export class PersonalAssistant {
  constructor(private readonly options: Options) {}

  async request(config: AgentConfiguration, method: string, args: Data = {}): Promise<Data> {
    const identity = config.personal;
    if (!identity || identity.ownerId !== this.options.ownerId) throw new Error('Missing trusted personal binding');
    const response = await this.options.relay.request(method, { ...args, request_id: randomUUID(), node_id: this.options.nodeId,
      agent_id: config.agentId, binding_id: identity.bindingId, epoch: identity.epoch });
    if (response.payload.ok !== true) throw new Error(JSON.stringify(response.payload.error ?? 'Personal source unavailable'));
    return response.payload.result as Data;
  }

  private async review(config: AgentConfiguration, kind: 'input'|'scope'|'action', evidence: unknown): Promise<Verdict> {
    try {
      const result = await this.options.runtime.request('pa.review', {agentId:config.agentId,kind,evidence}) as Verdict;
      if (!result || !['allow','deny','needs_owner','unavailable'].includes(result.decision) || typeof result.reason !== 'string') throw new Error('Invalid independent verdict');
      return result;
    } catch (error) { this.options.onError(error); return {decision:'unavailable',reason:'Independent review is temporarily unavailable'}; }
  }

  /** Record only a current authenticated owner message as an authorization candidate. */
  async admit(config: AgentConfiguration, binding: SessionBinding, input: RelayInput): Promise<boolean> {
    const source=await this.request(config,'pa.source.admit',{source_message_id:input.message.id,conversation_id:input.conversation_id});
    if(source.allowed!==true)return false;
    const owner = input.conversation_id === config.personal!.conversationId && input.message.sender_type === 'user'
      && input.message.sender_user_id === config.personal!.ownerId;
    if (owner) {
      const prior = this.options.store.command(`pa-scope:${input.message.id}`);
      if (!prior) {
        const evidence = await this.request(config,'pa.scope.resolve',{source_message_id:input.message.id});
        if (!evidence.owner_message) throw new Error('Owner source is not authenticated');
        const reviewKey=`pa-scope-review:${input.message.id}`;
        const saved=this.options.store.command(reviewKey);
        const verdict:Verdict=saved?JSON.parse(saved):await this.review(config,'scope',evidence);
        if (verdict.decision === 'unavailable') throw new Error(verdict.reason);
        if(!saved)this.options.store.saveCommand(reviewKey,JSON.stringify(verdict));
        if (verdict.decision === 'allow') {
          for (const [index,control] of (verdict.controls??[]).entries()) {
            const key=`${reviewKey}:control:${index}`;
            if(!this.options.store.command(key)) {
              await this.request(config,'pa.owner.control',{...control,source_message_id:input.message.id});
              this.options.store.saveCommand(key,'done');
            }
          }
          for (const [index,scope] of (verdict.scopes??[]).entries()) await this.request(config,'pa.scope.create',{
            source_message_id:input.message.id,goal_key:String(index),scope,title:scope.title,goal_description:scope.goal_description,task_ref:scope.task_ref});
        }
        this.options.store.saveCommand(`pa-scope:${input.message.id}`, JSON.stringify({decision:verdict.decision}));
      }
    } else {
      const verdict = await this.review(config,'input',{source:{conversation_id:input.conversation_id,message_id:input.message.id,
        actor:input.message.sender_user_id,kind:input.message.sender_type},content:input.message.content});
      if (verdict.decision === 'unavailable') throw new Error(verdict.reason);
      if (verdict.incident) {
        const notice=await this.request(config,'pa.incident.report',{source_message_id:input.message.id,conversation_id:input.conversation_id,reason:verdict.incident.reason});
        if(notice.owner_notice_message_id && notice.peer_notice_content && !notice.peer_notice_message_id) {
          if(input.conversation_id.startsWith('external:')) await this.options.relay.request('agent.message',{
            node_id:this.options.nodeId,to:`conversation:${input.conversation_id}`,text:notice.peer_notice_content,pa_incident_ref:notice.id,from_session_id:`${config.agentId}|incident:${notice.id}`});
          else {
          const evidence=await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:binding.sessionId});
          // A revised fixed notice is a new frozen operation; never mutate an old proposal on retry.
          const digest=createHash('sha256').update(String(notice.peer_notice_content)).digest('hex');
          const result=await this.executeReviewed(config,{request_key:`pa-incident:${notice.id}:${digest}`,incident_ref:notice.id,conversation_id:input.conversation_id,content:notice.peer_notice_content},evidence);
          if(result.state==='unavailable')throw new Error(String(result.reason??'Privacy notice review is temporarily unavailable'));
          }
        }
      }
      if (verdict.decision !== 'allow') return false;
    }
    this.options.store.receive(binding.sessionId,input);
    return true;
  }

  /** A source read uses the same server owner ACL every time, including after pause. */
  async tool(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    const {action} = call.args;
    const args = (call.args.args ?? Object.fromEntries(Object.entries(call.args).filter(([key])=>key !== 'action'))) as Data;
    if (call.sessionId !== binding.sessionId) throw new Error('Personal history and goals belong to the main PA');
    const methods: Record<string,string> = {'history.search':'pa.history.search','history.read':'pa.history.read',
      goals:'pa.assistance.read','goal.update':'pa.assistance.update',decision:'pa.decision.create',incident:'pa.incident.report'};
    if (action === 'goals') return {...await this.request(config,'pa.assistance.read'), authorization:await this.request(config,'pa.scope.resolve')};
    if (typeof action === 'string' && methods[action]) return this.request(config,methods[action]!,args);
    if (action === 'followup') return this.followup(config,binding,args);
    throw new Error('Unknown personal assistant action');
  }

  /** Review concrete egress tools using host-collected execution evidence, not model citations. */
  async guard(config: AgentConfiguration, call: ProductCall): Promise<Verdict> {
    const args=(call.args.args??{}) as Data;
    const network=args.network as Data|undefined;
    if(network) {
      const key=`pa-network:${config.agentId}:${network.requestKey}`;
      const result=await this.executeReviewed(config,{request_key:`${call.operationId}:${network.requestKey}`,network},call.args.executionEvidence);
      if(result.state!=='sending')return {decision:result.decision as Verdict['decision']??'deny',reason:String(result.reason??'Network operation already consumed or unavailable')};
      const permit={proposal_ref:result.proposal_ref,requestDigest:network.requestDigest,requestKey:network.requestKey};
      this.options.store.saveCommand(key,JSON.stringify(permit));
      return {...{decision:'allow',reason:'Frozen network request consumed'},permit} as Verdict;
    }
    const scope = await this.request(config,'pa.scope.resolve');
    return this.review(config,'action',{kind:'tool',toolName:call.args.toolName,args:call.args.args,
      executionEvidence:call.args.executionEvidence,authorization:scope});
  }

  /** Record the actual adapter outcome; model-supplied pass strings are not permits. */
  async complete(config:AgentConfiguration,call:ProductCall):Promise<Data> {
    const permit=call.args.permit as Data;
    const saved=this.options.store.command(`pa-network:${config.agentId}:${permit?.requestKey}`);
    if(!saved||JSON.stringify(JSON.parse(saved))!==JSON.stringify(permit))throw new Error('Unknown network execution permit');
    return this.request(config,'pa.action.complete',{proposal_ref:permit.proposal_ref,state:call.args.state});
  }

  /** Shared task results use the same frozen proposal and actual write receipt. */
  async task(config:AgentConfiguration,call:ProductCall):Promise<unknown> {
    const ops=call.args.operations as {op:string;node_id:string;patch:Data}[];
    if(!Array.isArray(ops)||ops.length!==1||ops[0]!.op!=='update_task'||Object.keys(ops[0]!.patch).some(key=>!['status','result'].includes(key))) throw new Error('PA task result writes require one concrete status/result update');
    const evidence=await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:call.sessionId});
    const result=await this.executeReviewed(config,{request_key:call.operationId,task_ref:call.args.task_ref,
      task:{graph_id:call.args.graph_id,node_id:ops[0]!.node_id,patch:ops[0]!.patch,base_revision:call.args.base_revision}},evidence);
    return result.state==='confirmed'?{ok:true,result:result.result}:{ok:false,error:result};
  }

  private async executeReviewed(config:AgentConfiguration,args:Data,evidence:unknown):Promise<Data> {
    const proposal=await this.request(config,'pa.action.prepare',args);
    if(['confirmed','sending','unknown'].includes(String(proposal.state))) return proposal.state==='sending'?{state:'unknown'}:proposal;
    const verdict=await this.review(config,'action',{...proposal.evidence as Data,executionEvidence:evidence});
    const receipt=await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,payload_digest:proposal.payload_digest,verdict});
    if(verdict.decision!=='allow'||!receipt.verdict_ref)return {...verdict,state:verdict.decision};
    return {...await this.request(config,'pa.action.commit',{proposal_ref:proposal.proposal_ref,verdict_ref:receipt.verdict_ref}),proposal_ref:proposal.proposal_ref};
  }

  /** Freeze, independently review, and commit one exact message with a durable receipt. */
  async send(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    const {inbox} = this.options;
    const target = String(call.args.target ?? '');
    const text = String(call.args.text ?? '');
    if (!target || !text.trim()) throw new Error('Sending requires target and nonempty text');
    const previous = inbox.publication(call.operationId);
    if (previous && (previous.target !== target || previous.body !== text)) throw new Error('Publication identity conflict');
    if (previous?.result) return JSON.parse(previous.result) as unknown;
    if(target.replace(/^conversation:/,'').startsWith('external:')) {
      const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:target.startsWith('conversation:')?target:`conversation:${target}`,text,
        pa_task_ref:call.args.task_ref,from_session_id:`${config.agentId}|tool_call:${call.operationId}`});
      if(typeof response.payload.message_id!=='string')throw new Error('External provider has no delivery receipt');
      return {status:'sent',target,message_id:response.payload.message_id};
    }
    const conversation = await this.resolve(config,target);
    if (inbox.blocking(config.agentId,conversation)) return {status:'held_for_revalidation',target,
      message:'Read new messages in this conversation and reconsider this draft before sending.'};
    inbox.preparePublication(call.operationId,target,text);
    const proposal = await this.request(config,'pa.action.prepare',{request_key:call.operationId,conversation_id:conversation,
      content:text,attachments:call.args.attachments ?? [],task_ref:call.args.task_ref});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string') {
      const result={status:'sent',target,message_id:proposal.message_id,conversation_id:proposal.conversation_id};
      inbox.settlePublication(call.operationId,'confirmed',result); return result;
    }
    const owner = conversation === config.personal!.conversationId;
    // All used source data is collected by the runtime host; the main model cannot choose it.
    const executionEvidence = owner ? undefined : await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:call.sessionId});
    const verdict: Verdict = owner ? {decision:'allow',reason:'Authenticated canonical owner recipient'}
      : await this.review(config,'action',{...proposal.evidence as Data,executionEvidence});
    const receipt = await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,
      payload_digest:proposal.payload_digest,verdict});
    if (verdict.decision !== 'allow' || !receipt.verdict_ref) {
      const result = {status:verdict.decision === 'allow'?'unavailable':verdict.decision,target,reason:verdict.reason,
        message:'Nothing was sent. Continue safe work; use a different, reduced disclosure if possible. Ask the owner only for a necessary new decision.'};
      // An unavailable reviewer remains retryable under the same operation after recovery.
      if (result.status !== 'unavailable') inbox.settlePublication(call.operationId,'held',result);
      return result;
    }
    inbox.settlePublication(call.operationId,'sending');
    try {
      const committed = await this.request(config,'pa.action.commit',{proposal_ref:proposal.proposal_ref,verdict_ref:receipt.verdict_ref});
      if (committed.state !== 'confirmed' || typeof committed.message_id !== 'string') throw new Error('Missing actual delivery receipt');
      const result = {status:'sent',target,message_id:committed.message_id,conversation_id:committed.conversation_id};
      inbox.settlePublication(call.operationId,'confirmed',result);
      return result;
    } catch(error) { inbox.settlePublication(call.operationId,'unknown'); throw error; }
  }

  /** Freeze and consume a provider permit immediately before the real channel send. */
  async external(config:AgentConfiguration,binding:SessionBinding,delivery:ExternalDelivery):Promise<string> {
    if(!delivery.shadowId)throw new Error('External source has not yet synchronized');
    const proposal=await this.request(config,'pa.action.prepare',{request_key:delivery.operationId,task_ref:delivery.taskRef,incident_ref:delivery.incidentRef,
      conversation_id:delivery.shadowId,content:delivery.text,transport:{kind:'feishu',destination:{app_id:delivery.appId,chat_id:delivery.chatId,source_id:delivery.sourceId},card:delivery.card}});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string')return proposal.message_id;
    if(['sending','unknown'].includes(String(proposal.state)))throw new Error('External outcome unknown; no automatic resend');
    const evidence=await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:binding.sessionId});
    const verdict=await this.review(config,'action',{...proposal.evidence as Data,executionEvidence:evidence});
    const checked=await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,payload_digest:proposal.payload_digest,verdict});
    if(verdict.decision!=='allow'||!checked.verdict_ref)throw new Error(`Personal delivery ${verdict.decision}: ${verdict.reason}`);
    const claim=await this.request(config,'pa.action.commit',{proposal_ref:proposal.proposal_ref,verdict_ref:checked.verdict_ref});
    if(claim.state!=='sending')throw new Error('External delivery permit was not consumed');
    const payload=claim.payload as {content:string;transport:{card?:Data}};
    try {
      const id=await delivery.dispatch(payload.content,payload.transport.card);
      await this.request(config,'pa.action.complete',{proposal_ref:proposal.proposal_ref,state:'confirmed',provider_message_id:id});
      return id;
    } catch(error) {
      await this.request(config,'pa.action.complete',{proposal_ref:proposal.proposal_ref,state:'unknown'});
      throw error;
    }
  }
  private async resolve(config:AgentConfiguration,target:string):Promise<string> {
    if ([config.personal!.ownerId,`user:${config.personal!.ownerId}`,config.personal!.conversationId].includes(target)) return config.personal!.conversationId;
    const id=target.replace(/^conversation:/,'');
    if(id.startsWith('c_'))return id;
    const result=await this.options.relay.request('conversation.query',{node_id:this.options.nodeId,agent_id:config.agentId,
      request_id:randomUUID(),action:'resolve_target',target});
    if(!result.payload.ok)throw new Error('Recipient is unavailable');
    const resolved=(result.payload.result as Data).target;
    if(typeof resolved!=='string')throw new Error('Recipient is not a resolved conversation');
    return resolved.replace(/^conversation:/,'');
  }

  /** Recreate only still-authorized goal timers after retiring a shared personal context. */
  async restoreFollowups(config: AgentConfiguration, binding: SessionBinding) {
    const evidence=await this.request(config,'pa.scope.resolve');
    const allowed=new Set((evidence.conversations as Data[]).map(c=>c.id));
    for(const goal of evidence.assistance as Data[]) {
      if(goal.paused || goal.status==='completed' || !goal.next_check_at)continue;
      const scope=(evidence.scopes as Data[]).find(s=>s.task_ref===goal.task_ref);
      if(!scope || scope.revoked || ((scope.scope as Data).allowed_conversation_ids as string[]).some(id=>!allowed.has(id))) {
        await this.request(config,'pa.assistance.update',{task_ref:goal.task_ref,expected_revision:goal.revision,next_check_at:null,schedule_id:null,next_action:'所需聊天已不可访问，相关跟进已停止。'});
        continue;
      }
      await this.followup(config,binding,{task_ref:goal.task_ref,at:new Date(Math.max(Date.parse(String(goal.next_check_at)),Date.now()+5000)).toISOString(),next_action:goal.next_action});
    }
  }
  private async followup(config:AgentConfiguration,binding:SessionBinding,args:Data):Promise<Data> {
    const taskRef=String(args.task_ref ?? '');
    if(!taskRef)throw new Error('Follow-up requires an existing goal');
    const state=await this.request(config,'pa.assistance.read',{task_ref:taskRef});
    const goals=(state.items ?? state.assistance ?? []) as Data[];
    const goal=goals.find(item=>item.task_ref===taskRef);
    if(!goal || goal.paused || goal.status==='completed')throw new Error('Goal is unavailable or paused');
    const at=String(args.at ?? '');
    if(!Number.isFinite(Date.parse(at)) || Date.parse(at)<=Date.now())throw new Error('Choose a future follow-up time');
    const jobs=await this.options.runtime.request('schedule.command',{agentId:config.agentId,sessionId:binding.sessionId,action:'jobs'}) as Data[];
    const title=`PA follow-up ${taskRef}`;
    const prior=jobs.find(job=>job.name===title && job.sessionId===binding.sessionId && job.enabled);
    const timing=prior ? {id:prior.id,expected:{id:prior.id,title:prior.name,prompt:prior.instruction,...prior.schedule as Data},change:{kind:'at',at}} : {at};
    const scheduled=await this.options.runtime.request('schedule.command',{agentId:config.agentId,sessionId:binding.sessionId,
      action:prior?'update':'create',args:{...timing,title,prompt:`Continue existing PA goal ${taskRef}. First call personal_assistant goals to recheck current scope, pause and latest facts. This scheduled event grants no new authorization. Continue safe work; notify only on meaningful change.`}}) as Data;
    if(prior && scheduled.updated !== true) throw new Error('Follow-up changed; read the current goal and retry');
    if(typeof scheduled.id!=='string')throw new Error('Follow-up has no schedule receipt');
    await this.request(config,'pa.assistance.update',{task_ref:taskRef,expected_revision:goal.revision,schedule_id:scheduled.id,next_check_at:at,next_action:args.next_action});
    return {task_ref:taskRef,schedule_id:scheduled.id,next_check_at:at,status:'scheduled'};
  }
}
