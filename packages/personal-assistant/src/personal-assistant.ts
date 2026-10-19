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
    if (response.payload.ok !== true) throw new Error(JSON.stringify(response.payload.error ?? 'Personal source unavailable'));
    return response.payload.result as Data;
  }

  private async review(config: AgentConfiguration, kind: 'input'|'action', evidence: unknown): Promise<Verdict> {
    try {
      const result = await this.options.runtime.request('pa.review', {agentId:config.agentId,kind,evidence}) as Verdict;
      if (!result || !['allow','deny','needs_owner','unavailable'].includes(result.decision) || typeof result.reason !== 'string') throw new Error('Invalid independent verdict');
      return result;
    } catch (error) { this.options.onError(error); return {decision:'unavailable',reason:'Independent review is temporarily unavailable'}; }
  }

  /** Admit a current authorized source, preserving owner instructions versus ambient facts. */
  async admit(config: AgentConfiguration, binding: SessionBinding, input: RelayInput): Promise<boolean> {
    const source=await this.request(config,'pa.source.admit',{source_message_id:input.message.id,conversation_id:input.conversation_id});
    if(source.allowed!==true)return false;
    input.metadata.personal_source_role = source.role;
    if (source.role !== 'owner_instruction' && source.role !== 'owner_fact') {
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
    const evidence=await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:call.sessionId});
    const result=await this.executeReviewed(config,{},evidence,proposal);
    return result.state==='confirmed'?{ok:true,result:result.result}:{ok:false,error:result};
  }

  private async executeReviewed(config:AgentConfiguration,args:Data,evidence:unknown,prepared?:Data):Promise<Data> {
    const proposal=prepared ?? await this.request(config,'pa.action.prepare',args);
    if(['confirmed','sending','unknown'].includes(String(proposal.state))) return proposal.state==='sending'?{state:'unknown'}:proposal;
    const verdict=await this.review(config,'action',{...proposal.evidence as Data,executionEvidence:evidence});
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
    const interactive = interactiveResponse(call.args.interactive);
    if (interactive && config.features?.intelligent_ui === false) throw new Error('Intelligent UI Feature is disabled; send a plain-text reply instead');
    const replyDraft = call.args.reply_draft;
    const publicationBody = canonicalJson({text, attachments:call.args.attachments ?? [], interactive:interactive ?? null, reply_draft:replyDraft ?? null});
    const previous = inbox.publication(call.operationId);
    if (previous && (previous.target !== target || previous.body !== publicationBody)) throw new Error('Publication identity conflict');
    if (previous?.result) return JSON.parse(previous.result) as unknown;
    if(target.replace(/^conversation:/,'').startsWith('external:')) {
      const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:target.startsWith('conversation:')?target:`conversation:${target}`,text,
        from_session_id:`${config.agentId}|tool_call:${call.operationId}`});
      if(typeof response.payload.message_id!=='string')throw new Error('External provider has no delivery receipt');
      return {status:'sent',target,message_id:response.payload.message_id};
    }
    const conversation = await this.resolve(config,target);
    if (inbox.blocking(config.agentId,conversation)) return {status:'held_for_revalidation',target,
      message:'Read new messages in this conversation and reconsider this draft before sending.'};
    inbox.preparePublication(call.operationId,target,publicationBody);
    if (conversation === config.personal!.conversationId) {
      // Private owner replies use the ordinary publication path, including IntelligentUI.
      inbox.settlePublication(call.operationId,'sending');
      try {
        const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${conversation}`,text,
          attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {}),...(replyDraft ? {reply_draft:replyDraft} : {}),
          from_session_id:`${config.agentId}|tool_call:${call.operationId}`});
        if(typeof response.payload.message_id !== 'string') throw new Error('Missing actual delivery receipt');
        const result={status:'sent',target,message_id:response.payload.message_id,conversation_id:response.payload.conversation_id};
        inbox.settlePublication(call.operationId,'confirmed',result);return result;
      } catch(error) {inbox.settlePublication(call.operationId,'unknown');throw error;}
    }
    const proposal = await this.request(config,'pa.action.prepare',{request_key:call.operationId,conversation_id:conversation,
      content:text,attachments:call.args.attachments ?? [],...(interactive ? {interactive} : {}),...(replyDraft ? {reply_draft:replyDraft} : {})});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string') {
      const result={status:'sent',target,message_id:proposal.message_id,conversation_id:proposal.conversation_id};
      inbox.settlePublication(call.operationId,'confirmed',result); return result;
    }
    // All used source data is collected by the runtime host; the main model cannot choose it.
    const executionEvidence = await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:call.sessionId});
    const verdict: Verdict = await this.review(config,'action',{...proposal.evidence as Data,executionEvidence});
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

  /** Freeze and consume a provider permit immediately before the real channel send. */
  async external(config:AgentConfiguration,binding:SessionBinding,delivery:ExternalDelivery):Promise<string> {
    if(!delivery.shadowId)throw new Error('External source has not yet synchronized');
    const proposal=await this.request(config,'pa.action.prepare',{request_key:delivery.operationId,incident_ref:delivery.incidentRef,
      conversation_id:delivery.shadowId,content:delivery.text,transport:{kind:'feishu',destination:{app_id:delivery.appId,chat_id:delivery.chatId,source_id:delivery.sourceId},card:delivery.card}});
    if(proposal.state==='confirmed' && typeof proposal.message_id==='string')return proposal.message_id;
    if(['sending','unknown'].includes(String(proposal.state)))throw new Error('External outcome unknown; no automatic resend');
    const evidence=await this.options.runtime.request('pa.evidence',{agentId:config.agentId,sessionId:binding.sessionId});
    const verdict=await this.review(config,'action',{...proposal.evidence as Data,executionEvidence:evidence});
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
