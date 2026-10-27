import type { ExternalDelivery } from './external.js';
import { createHash, randomUUID } from 'node:crypto';
import { canonicalJson, interactiveResponse, type AgentConfiguration, type RelayInput, type RuntimePort, type SessionBinding } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { ProductCall } from './global-agent.js';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

type Data = Record<string, unknown>;
interface Verdict { decision: 'allow' | 'deny' | 'needs_owner' | 'unavailable'; reason: string; incident?: {reason:string} }
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
    if (response.payload.ok !== true) {
      const error = response.payload.error as Data | undefined;
      if (error?.code === 'owner_authorization_changed') throw new Error(JSON.stringify({...error,
        message:'The prepared review snapshot is stale: original owner inputs or their accessibility changed while review was running. Read the latest owner instructions and current source restrictions, then reconsider and prepare a fresh review. This error alone does not establish that the owner revoked the requested action.'}));
      throw new Error(JSON.stringify(error ?? 'Personal source unavailable'));
    }
    return response.payload.result as Data;
  }

  private async review(config: AgentConfiguration, kind: 'input'|'action', evidence: unknown, sessionId?:string, callId?:string): Promise<Verdict> {
    try {
      const result = await this.options.runtime.request('pa.review', {agentId:config.agentId,kind,evidence,sessionId,callId}) as Verdict;
      if (!result || !['allow','deny','needs_owner','unavailable'].includes(result.decision) || typeof result.reason !== 'string') throw new Error('Invalid independent verdict');
      return result;
    } catch (error) { this.options.onError(error); return {decision:'unavailable',reason:'Independent review is temporarily unavailable'}; }
  }

  /** Refresh authenticated source facts without reviewing observed text as a request. */
  async source(config: AgentConfiguration, input: RelayInput): Promise<boolean> {
    const source=await this.request(config,'pa.source.admit',{source_message_id:input.message.id,conversation_id:input.conversation_id});
    if(source.allowed!==true)return false;
    if (typeof source.is_owner !== 'boolean' || !['participant','observer'].includes(String(source.delivery))) throw new Error('Missing trusted personal source facts');
    delete input.metadata.personal_source_role;
    input.metadata.personal_is_owner = source.is_owner;
    input.metadata.personal_delivery = source.delivery;
    input.metadata.conversation_type = source.conversation_type;
    input.metadata.channel = source.channel;
    // Only the authenticated server admission can set or clear this annotation.
    delete input.metadata.personal_actor_risk;
    if(source.actor_risk) input.metadata.personal_actor_risk = source.actor_risk;
    return true;
  }

  /** Admit authorized sources; only participant requests need input review. */
  async admit(config: AgentConfiguration, binding: SessionBinding, input: RelayInput): Promise<boolean> {
    if (!await this.source(config,input)) return false;
    if (input.metadata.personal_is_owner !== true && input.metadata.personal_delivery === 'participant') {
      const verdict = await this.review(config,'input',{source:{conversation_id:input.conversation_id,message_id:input.message.id,
        actor:input.message.sender_user_id,kind:input.message.sender_type,actor_risk:input.metadata.personal_actor_risk},content:input.message.content});
      if (verdict.decision === 'unavailable') throw new Error(verdict.reason);
      if (verdict.incident || verdict.decision === 'deny') {
        const notice=await this.request(config,'pa.incident.report',{source_message_id:input.message.id,conversation_id:input.conversation_id,reason:verdict.incident?.reason ?? verdict.reason});
        if(notice.owner_notice_message_id && notice.peer_notice_content && !notice.peer_notice_message_id) {
          const target=this.options.store.canonicalConversation(config.agentId,input.conversation_id);
          if(target.startsWith('external:')) await this.options.relay.request('agent.message',{
            node_id:this.options.nodeId,to:`conversation:${target}`,text:notice.peer_notice_content,pa_incident_ref:notice.id,from_session_id:`${config.agentId}|incident:${notice.id}`});
          else {
          // A revised fixed notice is a new frozen operation; never mutate an old proposal on retry.
          const digest=createHash('sha256').update(String(notice.peer_notice_content)).digest('hex');
          const result=await this.executeReviewed(config,{request_key:`pa-incident:${notice.id}:${digest}`,incident_ref:notice.id,conversation_id:input.conversation_id,content:notice.peer_notice_content},binding.sessionId);
          if(result.state==='unavailable')throw new Error(String(result.reason??'Privacy notice review is temporarily unavailable'));
          }
        }
      }
      if (verdict.decision !== 'allow') return false;
    }
    this.options.store.receive(binding.sessionId,input);
    return true;
  }

  /** Apply source preferences directly; the server authenticates the owner's original instruction. */
  async tool(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    if (call.sessionId !== binding.sessionId) throw new Error('Source preferences belong to the main PA');
    if (!['list','exclude','include'].includes(String(call.args.action))) throw new Error('Unknown personal source action');
    return this.request(config,'pa.sources',call.args);
  }

  /** Private tasks continue through the ordinary command; shared writes review the complete command. */
  async task(config:AgentConfiguration,call:ProductCall,task:Data):Promise<unknown> {
    const proposal=await this.request(config,'pa.action.prepare',{request_key:call.operationId,task});
    if(proposal.owner_private === true) return undefined;
    const result=await this.executeReviewed(config,{},call.sessionId,proposal,call.callId);
    return result.state==='confirmed'?{ok:true,result:result.result}:{ok:false,error:result};
  }

  private async executeReviewed(config:AgentConfiguration,args:Data,sessionId:string,prepared?:Data,callId?:string):Promise<Data> {
    const proposal=prepared ?? await this.request(config,'pa.action.prepare',args);
    if(['confirmed','sending','unknown'].includes(String(proposal.state))) return proposal.state==='sending'?{state:'unknown'}:proposal;
    const verdict=await this.review(config,'action',proposal.evidence,sessionId,callId);
    const receipt=await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,payload_digest:proposal.payload_digest,evidence_digest:proposal.evidence_digest,verdict});
    if(verdict.decision!=='allow'||!receipt.verdict_ref)return {...verdict,state:verdict.decision};
    return {...await this.request(config,'pa.action.commit',{proposal_ref:proposal.proposal_ref,verdict_ref:receipt.verdict_ref}),proposal_ref:proposal.proposal_ref};
  }

  /** Freeze, independently review, and commit one exact message with a durable receipt. */
  async send(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    const {inbox} = this.options;
    const target = String(call.args.target ?? '');
    const text = String(call.args.text ?? '');
    if (!target || !text.trim()) throw new Error('Sending requires target and nonempty text');
    if(call.args.reply_draft!==undefined)throw new Error('reply_draft is retired; use an interactive ComposeMessage action');
    const interactive = interactiveResponse(call.args.interactive);
    const representation=call.method==='send_user_message'?'owner':'self';
    if(representation==='owner' && (call.sessionId!==binding.sessionId || !config.personal))throw new Error('Only the bound main PA may represent its owner');
    const publicationBody = canonicalJson({text, attachments:call.args.attachments ?? [], interactive:interactive ?? null, representation});
    const previous = inbox.publication(call.operationId);
    if (previous && (previous.target !== target || previous.body !== publicationBody)) throw new Error('Publication identity conflict');
    if (previous?.result) return JSON.parse(previous.result) as unknown;
    const deliveryTarget=this.options.store.canonicalConversation(config.agentId,target.replace(/^conversation:/,''));
    if(deliveryTarget.startsWith('external:')) {
      if(representation==='owner')throw new Error('Owner representation requires a native IM conversation');
      const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${deliveryTarget}`,text,
        personal_owner_delivery:this.ownerDelivery(config,call),from_session_id:`${config.agentId}|tool_call:${call.operationId}`});
      if(typeof response.payload.message_id!=='string')throw new Error('External provider has no delivery receipt');
      return {status:'sent',target,message_id:response.payload.message_id};
    }
    const conversation = await this.resolve(config,target);
    if (inbox.blocking(config.agentId,conversation)) return {status:'held_for_revalidation',target,
      message:'Read new messages in this conversation and reconsider this draft before sending.'};
    inbox.preparePublication(call.operationId,target,publicationBody,binding.agentId);
    if (conversation === config.personal!.conversationId) {
      if(representation==='owner')throw new Error('Owner representation cannot target the owner PA conversation');
      const delivery=await this.request(config,'pa.attention.delivery.prepare',{conversation_id:conversation,operation_id:call.operationId,
        ...this.ownerDelivery(config,call)});
      if(delivery.status==='already_sent')return {status:'sent',target,message_id:delivery.message_id};
      if(delivery.status!=='allowed')return {...delivery,target,message:'No notification was sent. Use current source evidence, an assigned Task, or a checked attention candidate.'};
      // Classification and candidate publication commit with the actual message.

      inbox.settlePublication(call.operationId,'sending');
      try {
        const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${conversation}`,text,
          attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {}),personal_delivery_operation_id:call.operationId,
          from_session_id:`${config.agentId}|tool_call:${call.operationId}`});
        if(typeof response.payload.message_id !== 'string') throw new Error('Missing actual delivery receipt');
        const result={status:'sent',target,message_id:response.payload.message_id,conversation_id:response.payload.conversation_id};
        inbox.settlePublication(call.operationId,'confirmed',result);return result;
      } catch(error) {inbox.settlePublication(call.operationId,'unknown');throw error;}
    }
    const proposal = await this.request(config,'pa.action.prepare',{request_key:call.operationId,representation,conversation_id:conversation,
      content:text,attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {})});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string') {
      const result={status:'sent',target,message_id:proposal.message_id,conversation_id:proposal.conversation_id};
      inbox.settlePublication(call.operationId,'confirmed',result); return result;
    }
    // The runtime reads the host-bound scope directly; the model cannot choose review evidence.
    const verdict: Verdict = await this.review(config,'action',proposal.evidence,call.sessionId,call.callId);
    const receipt = await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,
      payload_digest:proposal.payload_digest,evidence_digest:proposal.evidence_digest,verdict});
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

  private ownerDelivery(config:AgentConfiguration,call:ProductCall):Data {
    const {inbox}=this.options;
    // The owner can request work in a shared chat and receive a private clarification.
    // The server still checks that these original words actually addressed this PA.
    const live=(call.liveInputIds??[]).map(id=>inbox.input(config.agentId,id)).findLast(input=>input?.metadata.personal_is_owner===true&&input.metadata.personal_delivery==='participant');
    const scheduled=(call.scheduleTriggers??[]).flatMap<Data>(trigger=>{const source=trigger.sourceMessageIds.map(id=>inbox.input(config.agentId,id)).find(input=>input?.metadata.personal_is_owner===true&&input.metadata.personal_delivery==='participant');return source?[{kind:'schedule',schedule_id:trigger.scheduleId,source_message_id:source.message.id}]:trigger.ownerUi?[{kind:'schedule',schedule_id:trigger.scheduleId,owner_ui:true}]:[];})[0];
    const returned=(call.childReturns??[]).flatMap<Data>(child=>{const source=child.sourceMessageIds.map(id=>inbox.input(config.agentId,id)).find(input=>input?.metadata.personal_is_owner===true&&input.metadata.personal_delivery==='participant');return source?[{kind:'delegation',child_id:child.childId,source_message_id:source.message.id}]:[];})[0];
    return {feature_enabled:config.features?.personal_proactivity===true,attention_id:call.args.attention_id,attention_revision:call.args.attention_revision,
      ...(live?{evidence:{kind:'direct_request',source_message_id:live.message.id}}:scheduled?{evidence:scheduled}:returned?{evidence:returned}:call.args.task_ref?{evidence:{kind:'task',...(call.args.task_ref as Data)}}:{})};
  }

  /** Freeze and consume a provider permit immediately before the real channel send. */
  async external(config:AgentConfiguration,binding:SessionBinding,delivery:ExternalDelivery):Promise<string> {
    if(!delivery.shadowId)throw new Error('External source has not yet synchronized');
    const proposal=await this.request(config,'pa.action.prepare',{request_key:delivery.operationId,incident_ref:delivery.incidentRef,
      conversation_id:delivery.shadowId,content:delivery.text,transport:{kind:'feishu',destination:{app_id:delivery.appId,chat_id:delivery.chatId,source_id:delivery.sourceId},card:delivery.card}});
    if(proposal.owner_private===true){
      const classified=await this.request(config,'pa.attention.delivery.prepare',{...delivery.ownerDelivery,feature_enabled:config.features?.personal_proactivity===true,conversation_id:delivery.shadowId,operation_id:delivery.operationId});
      if(classified.status==='already_sent')return String(classified.message_id).replace(/^external:/,'');
      if(classified.status!=='allowed')throw new Error(`Owner delivery ${classified.status}: no notification was sent`);
      const id=await delivery.dispatch(delivery.text,delivery.card);
      await this.request(config,'pa.attention.delivery.external-complete',{operation_id:delivery.operationId,provider_message_id:id});
      return id;
    }
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string')return proposal.message_id;
    if(['sending','unknown'].includes(String(proposal.state)))throw new Error('External outcome unknown; no automatic resend');
    const verdict=await this.review(config,'action',proposal.evidence,binding.sessionId);
    const checked=await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,payload_digest:proposal.payload_digest,evidence_digest:proposal.evidence_digest,verdict});
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

}
