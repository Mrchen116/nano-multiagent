import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import type { ExternalDelivery } from './external.js';
import { randomUUID } from 'node:crypto';
import { interactiveResponse, type AgentConfiguration, type RelayInput, type RuntimePort, type SessionBinding } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { ProductCall } from './global-agent.js';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

type Data = Record<string, unknown>;
export interface AdmissionResult {kind:'admitted'|'rejected'|'source_unavailable'|'failed'|'in_progress';message_id:string;reason?:string;incident_id?:string;error_code?:string}
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
    if (response.payload.ok !== true) throw new Error(JSON.stringify(response.payload.error ?? 'Personal source unavailable'));
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

  /** Persist and settle one input; transport duplicates return the existing verdict. */
  async admit(config: AgentConfiguration, binding: SessionBinding, input: RelayInput, explicit=false): Promise<AdmissionResult> {
    const {inbox}=this.options;
    const saved=structuredClone(input);saved.metadata.personal_unclassified=true;
    if(!inbox.input(config.agentId,input.message.id))inbox.receive(saved,false);
    const generation=inbox.reviews.begin(config.agentId,input.message.id,explicit);
    const existing=inbox.reviews.get(config.agentId,input.message.id)!;
    if(generation===undefined) {
      const original=inbox.input(config.agentId,input.message.id);
      if(original)Object.assign(input.metadata,original.metadata);
      return {kind:existing.state==='pending'||existing.state==='reviewing'?'in_progress':existing.error_code==='source_unavailable'?'source_unavailable':existing.state,
        message_id:input.message.id,reason:existing.reason,incident_id:existing.incident_id,error_code:existing.error_code};
    }
    try {
      if(!await this.source(config,input)) {
        inbox.reviews.settle(config.agentId,input.message.id,generation,{state:'rejected',reason:'Source is no longer accessible',error_code:'source_unavailable'});
        return {kind:'source_unavailable',message_id:input.message.id};
      }
      // Save authenticated provenance before a crash; this does not itself admit the text.
      inbox.classify(input,false);
      if(input.metadata.personal_is_owner!==true && input.metadata.personal_delivery==='participant') {
        const context=await this.request(config,'pa.input.context',{source_message_id:input.message.id});
        const verdict=await this.review(config,'input',{...context,source:{conversation_id:input.conversation_id,message_id:input.message.id,
          actor:input.message.sender_user_id,kind:input.message.sender_type,actor_risk:input.metadata.personal_actor_risk}});
        if(verdict.decision==='unavailable')throw new Error(verdict.reason);
        if(verdict.incident || verdict.decision!=='allow') {
          const reason=verdict.incident?.reason??verdict.reason;
          inbox.reviews.settle(config.agentId,input.message.id,generation,{state:'rejected',reason,...(!verdict.incident&&verdict.decision==='needs_owner'?{error_code:'needs_owner'}:{})});
          await this.reportInputIncident(config,input).catch(this.options.onError);
          return {kind:'rejected',message_id:input.message.id,reason,incident_id:inbox.reviews.get(config.agentId,input.message.id)?.incident_id};
        }
      }
      if(!inbox.reviews.settle(config.agentId,input.message.id,generation,{state:'admitted'}))return {kind:'in_progress',message_id:input.message.id};
      this.options.store.receive(binding.sessionId,input);
      return {kind:'admitted',message_id:input.message.id};
    }catch(error) {
      this.options.onError(error);
      const reason=error instanceof Error?error.message:String(error);
      inbox.reviews.settle(config.agentId,input.message.id,generation,{state:'failed',reason,error_code:'review_unavailable'});
      return {kind:'failed',message_id:input.message.id,reason,error_code:'review_unavailable'};
    }
  }

  /** Retry only durable incident delivery, never the rejected input's model review. */
  async reportInputIncident(config:AgentConfiguration,input:RelayInput):Promise<void> {
    const review=this.options.inbox.reviews.get(config.agentId,input.message.id);
    if(review?.state!=='rejected'||review.error_code||review.incident_id)return;
    const incident=await this.request(config,'pa.incident.report',{source_message_id:input.message.id,conversation_id:input.conversation_id,category:'prompt_injection',reason:review.reason});
    if(typeof incident.id!=='string')throw new Error('Security incident has no durable identity');
    this.options.inbox.reviews.incident(config.agentId,input.message.id,incident.id);
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
    const incident=typeof call.args.incident_ref==='string'?call.args.incident_ref:undefined;
    if(incident&&(call.sessionId!==binding.sessionId||call.method!=='send_message'||interactive||(call.args.attachments as unknown[]|undefined)?.length))throw new Error('Incident communication belongs to the main PA and must be plain self-authored text');
    const representation=call.method==='send_user_message'?'owner':'self';
    if(representation==='owner' && (call.sessionId!==binding.sessionId || !config.personal))throw new Error('Only the bound main PA may represent its owner');
    const deliveryTarget=this.options.store.canonicalConversation(config.agentId,target.replace(/^conversation:/,''));
    if(deliveryTarget.startsWith('external:')&&representation==='owner')throw new Error('Owner representation requires a native IM conversation');
    const conversation = deliveryTarget.startsWith('external:')?target.replace(/^conversation:/,''):await this.resolve(config,target);
    if(incident) {
      const event=await this.request(config,'pa.incident.read',{incident_ref:incident,conversation_id:conversation});
      const receipt=conversation===config.personal!.conversationId?event.owner_notice_message_id:event.peer_notice_message_id;
      if(typeof receipt==='string')return {status:'sent',target,message_id:receipt,conversation_id:conversation};
    }
    const incidentKey=incident?`pa-incident:${incident}:${conversation===config.personal!.conversationId?'owner':'peer'}`:undefined;
    let operationId=incidentKey??call.operationId;
    const publicationBody = sortedJsonAscii({text, attachments:call.args.attachments ?? [], interactive:interactive ?? null, representation});
    const incidentPrevious=incidentKey?inbox.incidentPublication(incidentKey):undefined;
    let previous = incidentPrevious??inbox.publication(operationId);
    if(incidentKey&&incidentPrevious&&previous) {
      operationId=incidentPrevious.id;
      if(['sending','unknown'].includes(previous.state))return {status:'unknown',operation_id:operationId,message:'Check the existing publication receipt; do not resend with another key.'};
      if(previous.state==='held'&&(previous.target!==target||previous.body!==publicationBody)) {
        operationId=`${incidentKey}:${randomUUID()}`;
        previous=undefined;
      }
    }
    if (previous && (previous.target !== target || previous.body !== publicationBody)) {
      if(!incident)throw new Error('Publication identity conflict');
      return {status:'not_sent',changed_reason:'publication_identity_conflict',message:'This incident already has a frozen publication; inspect its existing receipt before proposing another message.'};
    }
    if (previous?.result) {
      const result=JSON.parse(previous.result);
      if(incident&&conversation===config.personal!.conversationId&&result.message_id)await this.request(config,'pa.incident.receipt',{incident_ref:incident,message_id:result.message_id});
      return result;
    }
    if(previous&&['sending','unknown'].includes(previous.state))return {status:'unknown',operation_id:operationId,message:'Check the existing publication receipt; do not resend with another key.'};
    if(deliveryTarget.startsWith('external:')) {
      if(representation==='owner')throw new Error('Owner representation requires a native IM conversation');
      const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${deliveryTarget}`,text,
        ...(incident?{pa_incident_ref:incident}:{}),from_session_id:`${config.agentId}|tool_call:${operationId}`});
      if(typeof response.payload.message_id!=='string')throw new Error('External provider has no delivery receipt');
      return {status:'sent',target,message_id:response.payload.message_id};
    }
    if (inbox.blocking(config.agentId,conversation)) return {status:'held_for_revalidation',target,
      message:'Read new messages in this conversation and reconsider this draft before sending.'};
    inbox.preparePublication(operationId,target,publicationBody,binding.agentId);
    if (conversation === config.personal!.conversationId) {
      if(representation==='owner')throw new Error('Owner representation cannot target the owner PA conversation');
      // Private owner replies use the ordinary publication path, including IntelligentUI.
      inbox.settlePublication(operationId,'sending');
      try {
        const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${conversation}`,text,
          attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {}),
          ...(incident?{pa_incident_ref:incident}:{}),from_session_id:`${config.agentId}|tool_call:${operationId}`});
        if(typeof response.payload.message_id !== 'string') throw new Error('Missing actual delivery receipt');
        const result={status:'sent',target,message_id:response.payload.message_id,conversation_id:response.payload.conversation_id};
        inbox.settlePublication(operationId,'confirmed',result);
        if(incident)await this.request(config,'pa.incident.receipt',{incident_ref:incident,message_id:response.payload.message_id});
        return result;
      } catch(error) {if(inbox.publication(operationId)?.state!=='confirmed')inbox.settlePublication(operationId,'unknown');throw error;}
    }
    const proposal = await this.request(config,'pa.action.prepare',{request_key:operationId,representation,conversation_id:conversation,
      ...(incident?{incident_ref:incident}:{}),content:text,attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {})});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string') {
      const result={status:'sent',target,message_id:proposal.message_id,conversation_id:proposal.conversation_id};
      inbox.settlePublication(operationId,'confirmed',result); return result;
    }
    // The runtime reads the host-bound scope directly; the model cannot choose review evidence.
    const verdict: Verdict = await this.review(config,'action',proposal.evidence,call.sessionId,call.callId);
    const receipt = await this.request(config,'pa.action.review-result',{proposal_ref:proposal.proposal_ref,
      payload_digest:proposal.payload_digest,evidence_digest:proposal.evidence_digest,verdict});
    if (verdict.decision !== 'allow' || !receipt.verdict_ref) {
      const result = {status:verdict.decision === 'allow'?'unavailable':verdict.decision,target,reason:verdict.reason,
        message:'Nothing was sent. Continue safe work; use a different, reduced disclosure if possible. Ask the owner only for a necessary new decision.'};
      // An unavailable reviewer remains retryable under the same operation after recovery.
      if (result.status !== 'unavailable') inbox.settlePublication(operationId,'held',result);
      return result;
    }
    inbox.settlePublication(operationId,'sending');
    try {
      const committed = await this.request(config,'pa.action.commit',{proposal_ref:proposal.proposal_ref,verdict_ref:receipt.verdict_ref});
      if(committed.state==='not_sent') {inbox.settlePublication(operationId,'held',committed);return {status:'not_sent',target,...committed};}
      if (committed.state !== 'confirmed' || typeof committed.message_id !== 'string') throw new Error('Missing actual delivery receipt');
      const result = {status:'sent',target,message_id:committed.message_id,conversation_id:committed.conversation_id};
      inbox.settlePublication(operationId,'confirmed',result);
      return result;
    } catch(error) { inbox.settlePublication(operationId,'unknown'); throw error; }
  }

  /** Freeze and consume a provider permit immediately before the real channel send. */
  async external(config:AgentConfiguration,binding:SessionBinding,delivery:ExternalDelivery):Promise<string> {
    if(!delivery.shadowId)throw new Error('External source has not yet synchronized');
    const proposal=await this.request(config,'pa.action.prepare',{request_key:delivery.operationId,incident_ref:delivery.incidentRef,
      conversation_id:delivery.shadowId,content:delivery.text,transport:{kind:'feishu',destination:{app_id:delivery.appId,chat_id:delivery.chatId,source_id:delivery.sourceId},card:delivery.card}});
    if(proposal.owner_private===true)return delivery.dispatch(delivery.text,delivery.card);
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
