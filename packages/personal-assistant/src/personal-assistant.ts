import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import type { ExternalDelivery } from './external.js';
import { randomUUID } from 'node:crypto';
import { chatTaskCards, interactiveResponse, TASK_STATUS_BADGE_LABELS, workObject, type AgentConfiguration, type RelayInput, type RuntimePort, type SessionBinding, type TaskCardRef, type TaskStatus } from '@nano/product-contracts';
import { RelayDeliveryError, type ProtocolFrame } from '@nano/channels';
import type { ProductCall } from './global-agent.js';
import { prepareLocalAttachments, unknownScreenshotReceipt, type AttachmentUploader, type ScreenshotUploader } from './screenshot-delivery.js';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';
import { joinThreadTarget, splitThreadTarget } from './tool-references.js';

type Data = Record<string, unknown>;
export interface AdmissionResult {kind:'admitted'|'rejected'|'source_unavailable'|'failed'|'in_progress';message_id:string;reason?:string;incident_id?:string;error_code?:string}
export interface BatchReviewSummary {
  admitted: number;
  rejected: RelayInput[];
  failed: RelayInput[];
  unavailable: RelayInput[];
  sourceRevoked: string[];
}
type Verdict = import('@nano/product-contracts/runtime-rpc').RuntimeOutput<'pa.review'>;
interface Options {
  nodeId: string; ownerId: string; agents: AgentConfiguration[]; store: NodeStore; inbox: InboxStore; runtime: RuntimePort;
  relay: {request(type: string, payload: Data): Promise<ProtocolFrame>}; onError(error: unknown): void;
  uploadScreenshot?: ScreenshotUploader;
  uploadAttachment?: AttachmentUploader;
  flushConversation?: (config: AgentConfiguration, binding: SessionBinding, conversationId?: string) => Promise<void>;
}

const MAX_REVIEW_BATCH = 20;

/** Coordinates personal product facts; DSH remains the sole execution loop. */
export class PersonalAssistant {
  private readonly reviewBatches = new Map<string, Promise<BatchReviewSummary>>();
  constructor(private readonly options: Options) {}

  get busy(): boolean {
    return this.reviewBatches.size > 0;
  }

  async request(config: AgentConfiguration, method: string, args: Data = {}): Promise<Data> {
    const identity = config.personal;
    if (!identity || identity.ownerId !== this.options.ownerId) throw new Error('Missing trusted personal binding');
    const response = await this.options.relay.request(method, { ...args, request_id: randomUUID(), node_id: this.options.nodeId,
      agent_id: config.agentId, binding_id: identity.bindingId, epoch: identity.epoch });
    if (response.payload.ok !== true) throw Object.assign(new Error(JSON.stringify(response.payload.error ?? 'Personal source unavailable')), {detail:response.payload.error});
    return response.payload.result as Data;
  }

  private async review(config: AgentConfiguration, kind: 'input'|'action', evidence: unknown, sessionId?:string, callId?:string): Promise<Verdict> {
    try {
      if (!workObject(evidence)) throw new Error('Independent review evidence is unavailable');
      if (kind === 'input') return await this.options.runtime.request('pa.review', {agentId:config.agentId,kind,evidence});
      if (!sessionId) throw new Error('Action review requires a session');
      return await this.options.runtime.request('pa.review', {agentId:config.agentId,kind,evidence,sessionId,callId});
    } catch (error) { this.options.onError(error); return {decision:'unavailable',reason:'Independent review is temporarily unavailable'}; }
  }

  /** Refresh authenticated source facts without reviewing observed text as a request. */
  async source(config: AgentConfiguration, input: RelayInput): Promise<boolean> {
    const source=await this.request(config,'pa.source.admit',{source_message_id:input.message.id,conversation_id:input.conversation_id});
    if(source.allowed!==true){if(source.scope_skipped===true)input.metadata.scope_skipped=true;return false;}
    if (typeof source.is_owner !== 'boolean' || !['participant','observer'].includes(String(source.delivery))) throw new Error('Missing trusted personal source facts');
    delete input.metadata.personal_source_role;
    input.metadata.personal_is_owner = source.is_owner;
    input.metadata.personal_delivery = source.delivery;
    input.metadata.conversation_type = source.conversation_type;
    input.metadata.channel = source.channel;
    for (const key of ['owner_direct', 'addressed_to_owner', 'addressed_to_agent'] as const) {
      if (typeof source[key] === 'boolean') input.metadata[key] = source[key];
    }
    for (const key of ['thread_root_message_id','thread_root_sender','thread_root_excerpt','thread_earlier','thread_history_truncated','thread_follow_reactivated']) {
      if (key in source) input.metadata[key] = source[key];
    }
    if('provider_source_time' in source)input.metadata.provider_source_time=source.provider_source_time;
    if(typeof source.agent_user_id==='string'&&source.agent_user_id)input.metadata.agent_user_id=source.agent_user_id;
    if(Array.isArray(source.explicit_mentioned_agent_ids))input.metadata.explicit_mentioned_agent_ids=source.explicit_mentioned_agent_ids;
    if(typeof source.context_only==='boolean')input.metadata.context_only=source.context_only;
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

  /** Settle an owner or observer input without calling the independent input reviewer. */
  admitTrusted(config: AgentConfiguration, binding: SessionBinding, input: RelayInput): boolean {
    const { inbox } = this.options;
    const existing = inbox.reviews.get(config.agentId, input.message.id);
    if (existing?.state === 'admitted') return true;
    const generation = inbox.reviews.begin(config.agentId, input.message.id);
    if (generation === undefined) return inbox.reviews.get(config.agentId, input.message.id)?.state === 'admitted';
    if (!inbox.reviews.settle(config.agentId, input.message.id, generation, { state: 'admitted' })) return false;
    this.options.store.receive(binding.sessionId, input);
    return true;
  }

  /** Fail closed for an unprojectable non-owner attachment without poisoning sibling text inputs. */
  failAttachmentInput(config: AgentConfiguration, input: RelayInput): boolean {
    const { inbox } = this.options;
    const generation = inbox.reviews.begin(config.agentId, input.message.id);
    if (generation === undefined) return false;
    const reason = 'Independent review unavailable: Error: Input review attachment projection is unavailable';
    return inbox.reviews.settle(config.agentId, input.message.id, generation, { state: 'failed', reason, error_code: 'review_unavailable' });
  }

  /** Settle unavailable source admission on a pending unreviewed input. */
  settleSourceUnavailable(config: AgentConfiguration, input: RelayInput): void {
    const { inbox } = this.options;
    const generation = inbox.reviews.begin(config.agentId, input.message.id);
    if (generation !== undefined) {
      inbox.reviews.settle(config.agentId, input.message.id, generation, {
        state: 'rejected', reason: 'Source is no longer accessible', error_code: 'source_unavailable',
      });
    }
  }

  /** Flush staged pending participant reviews across one or all conversations. */
  async flushReviews(
    config: AgentConfiguration,
    binding: SessionBinding,
    conversationId: string | undefined,
    classifyFlags: (input: RelayInput) => { attention: boolean; high: boolean },
  ): Promise<BatchReviewSummary> {
    const prefix = `${config.agentId}:`;
    const inFlight = [...this.reviewBatches.keys()]
      .filter(key => key.startsWith(prefix))
      .map(key => key.slice(prefix.length));
    const conversations = conversationId
      ? [conversationId]
      : [...new Set([...this.options.inbox.reviews.pendingConversations(config.agentId), ...inFlight])];
    if (!conversations.length) {
      return { admitted: 0, rejected: [], failed: [], unavailable: [], sourceRevoked: [] };
    }
    const parts = await Promise.all(conversations.map(cid => this.flushConversationReviews(config, binding, cid, classifyFlags)));
    return {
      admitted: parts.reduce((sum, item) => sum + item.admitted, 0),
      rejected: parts.flatMap(item => item.rejected),
      failed: parts.flatMap(item => item.failed),
      unavailable: parts.flatMap(item => item.unavailable),
      sourceRevoked: [...new Set(parts.flatMap(item => item.sourceRevoked))],
    };
  }

  private flushConversationReviews(
    config: AgentConfiguration,
    binding: SessionBinding,
    conversationId: string,
    classifyFlags: (input: RelayInput) => { attention: boolean; high: boolean },
  ): Promise<BatchReviewSummary> {
    const key = `${config.agentId}:${conversationId}`;
    const active = this.reviewBatches.get(key);
    if (active) return active;
    const task = this.drainConversationReviews(config, binding, conversationId, classifyFlags)
      .finally(() => { if (this.reviewBatches.get(key) === task) this.reviewBatches.delete(key); });
    this.reviewBatches.set(key, task);
    return task;
  }

  private async drainConversationReviews(
    config: AgentConfiguration,
    binding: SessionBinding,
    conversationId: string,
    classifyFlags: (input: RelayInput) => { attention: boolean; high: boolean },
  ): Promise<BatchReviewSummary> {
    const { inbox } = this.options;
    const summary: BatchReviewSummary = { admitted: 0, rejected: [], failed: [], unavailable: [], sourceRevoked: [] };
    for (;;) {
      const claimed = inbox.reviews.beginBatch(config.agentId, conversationId, MAX_REVIEW_BATCH);
      if (!claimed.length) break;
      const textBatch: typeof claimed = [];
      for (const entry of claimed) {
        if (entry.input.message.attachments.length > 0) {
          const reason = 'Independent review unavailable: Error: Input review attachment projection is unavailable';
          if (inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, { state: 'failed', reason, error_code: 'review_unavailable' })) {
            summary.failed.push(entry.input);
          }
        } else {
          textBatch.push(entry);
        }
      }
      if (textBatch.length) {
        await this.reviewBatchSlice(config, binding, conversationId, textBatch, classifyFlags, summary);
      }
      if (summary.sourceRevoked.includes(conversationId)) break;
    }
    return summary;
  }

  private async reviewBatchSlice(
    config: AgentConfiguration,
    binding: SessionBinding,
    conversationId: string,
    slice: { input: RelayInput; generation: number; due_at: number | null }[],
    classifyFlags: (input: RelayInput) => { attention: boolean; high: boolean },
    summary: BatchReviewSummary,
  ): Promise<void> {
    const { inbox } = this.options;
    let context: Data;
    try {
      context = await this.request(config, 'pa.input.context', {
        conversation_id: conversationId,
        source_message_ids: slice.map(entry => entry.input.message.id),
      });
    } catch (error) {
      this.options.onError(error);
      const reason = error instanceof Error ? error.message : String(error);
      for (const entry of slice) {
        if (inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, { state: 'failed', reason, error_code: 'review_unavailable' })) {
          summary.failed.push(entry.input);
        }
      }
      return;
    }

    if (context.source_allowed === false) {
      for (const entry of slice) {
        inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, {
          state: 'rejected', reason: 'Source is no longer accessible', error_code: 'source_unavailable',
        });
        summary.unavailable.push(entry.input);
      }
      summary.sourceRevoked.push(conversationId);
      return;
    }

    const unavailableSet = new Set(Array.isArray(context.unavailable_message_ids) ? context.unavailable_message_ids as string[] : []);
    const active = slice.filter(entry => {
      if (!unavailableSet.has(entry.input.message.id)) return true;
      if (inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, {
        state: 'rejected', reason: 'Source message is no longer accessible', error_code: 'source_unavailable',
      })) {
        summary.unavailable.push(entry.input);
      }
      return false;
    });
    if (!active.length) return;

    const evidence = Array.isArray(context.timeline)
      ? context
      : {
          conversation: { id: conversationId, type: active[0]!.input.metadata.conversation_type ?? 'group', delivery: 'participant', channel: active[0]!.input.metadata.channel ?? 'web' },
          previous: Array.isArray(context.previous) ? context.previous : [],
          timeline: active.map(entry => ({
            id: entry.input.message.id,
            needs_decision: true,
            sender: { id: entry.input.message.sender_user_id, type: entry.input.message.sender_type, is_owner: false },
            ...(entry.input.metadata.personal_actor_risk ? { actor_risk: entry.input.metadata.personal_actor_risk } : {}),
            content: entry.input.message.content,
            created_at: entry.input.message.created_at ?? null,
          })),
          omissions: Array.isArray(context.omissions) ? context.omissions : [],
        };

    const verdict = await this.review(config, 'input', evidence);
    if (verdict.decision === 'unavailable') {
      if (verdict.error_code === 'context_overflow' && active.length > 1) {
        const mid = Math.ceil(active.length / 2);
        await this.reviewBatchSlice(config, binding, conversationId, active.slice(0, mid), classifyFlags, summary);
        await this.reviewBatchSlice(config, binding, conversationId, active.slice(mid), classifyFlags, summary);
        return;
      }
      for (const entry of active) {
        if (inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, {
          state: 'failed', reason: verdict.reason, error_code: 'review_unavailable',
        })) {
          summary.failed.push(entry.input);
        }
      }
      return;
    }

    const decisionMap = new Map<string, { decision: string; reason: string; incident?: { reason: string } }>();
    if (Array.isArray(verdict.decisions)) {
      for (const item of verdict.decisions) decisionMap.set(item.id, item);
    } else {
      for (const entry of active) {
        decisionMap.set(entry.input.message.id, { decision: verdict.decision, reason: verdict.reason, incident: verdict.incident });
      }
    }

    for (const entry of active) {
      const itemVerdict = decisionMap.get(entry.input.message.id);
      if (!itemVerdict || itemVerdict.decision === 'unavailable') {
        const reason = itemVerdict?.reason ?? 'Independent review omitted decision for message';
        if (inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, { state: 'failed', reason, error_code: 'review_unavailable' })) {
          summary.failed.push(entry.input);
        }
        continue;
      }
      if (itemVerdict.incident || itemVerdict.decision !== 'allow') {
        const reason = itemVerdict.incident?.reason ?? itemVerdict.reason;
        const settled = inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, {
          state: 'rejected',
          reason,
          ...(!itemVerdict.incident && itemVerdict.decision === 'needs_owner' ? { error_code: 'needs_owner' } : {}),
        });
        if (settled) {
          await this.reportInputIncident(config, entry.input).catch(this.options.onError);
          summary.rejected.push(entry.input);
        }
        continue;
      }
      if (!inbox.reviews.settle(config.agentId, entry.input.message.id, entry.generation, { state: 'admitted' })) continue;
      const latest = inbox.input(config.agentId, entry.input.message.id) ?? entry.input;
      const { attention, high } = classifyFlags(latest);
      this.options.store.receive(binding.sessionId, latest);
      inbox.classify(latest, attention, high, entry.due_at);
      summary.admitted++;
    }
  }

  /** Apply source preferences directly; the server authenticates the owner's original instruction. */
  async tool(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    if (call.sessionId !== binding.sessionId) throw new Error('Source preferences belong to the main PA');
    if (!['list','exclude','include'].includes(String(call.args.action))) throw new Error('Unknown personal source action');
    return this.request(config,'pa.sources',call.args);
  }

  /** Preserve caller identity while forwarding a separately chosen creation target. */
  async createAgent(config: AgentConfiguration, binding: SessionBinding, call: ProductCall): Promise<unknown> {
    if (call.sessionId !== binding.sessionId) throw new Error('Only the main PA can create Agents');
    if (config.toolAllowlist && !config.toolAllowlist.includes('agent_creation')) throw new Error('Agent creation tool is not enabled');
    const {node_id,...args}=call.args;
    try {
      return await this.request(config,'pa.agent.creation',{...args,target_node_id:node_id,lifecycle_revision:call.lifecycle_revision});
    } catch(error) {
      if(error instanceof RelayDeliveryError && error.delivery==='unknown')
        return {status:'unknown',request_key:args.request_key,message:'Outcome unknown. Query status using the same request_key before retrying.'};
      throw error;
    }
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

  /** Read the receipt from the authority that committed this screenshot message. */
  async screenshotReceipt(config: AgentConfiguration, target: string, operationId: string): Promise<Data> {
    const conversation = await this.resolve(config, this.options.store.toolReferences.splitResolvedTarget(config.agentId, target).base);
    if (conversation === config.personal!.conversationId)
      return (await this.options.relay.request('agent.message.status', {node_id:this.options.nodeId,agent_id:config.agentId,operation_id:operationId})).payload;
    return this.request(config, 'pa.action.status', {request_key:operationId,conversation_id:conversation});
  }

  /** Freeze, independently review, and commit one exact message with a durable receipt. */
  async send(config: AgentConfiguration, binding: SessionBinding, call: ProductCall, signal = new AbortController().signal): Promise<unknown> {
    const {inbox} = this.options;
    const target = String(call.args.target ?? '');
    const { base: targetBase, root: inThread } = this.options.store.toolReferences.splitResolvedTarget(config.agentId, target);
    const text = String(call.args.text ?? '');
    if(call.args.reply_draft!==undefined)throw new Error('reply_draft is retired; use an interactive ComposeMessage action');
    const interactive = interactiveResponse(call.args.interactive);
    const taskCards = chatTaskCards(call.args.task_cards);
    if (!target || !text.trim() && !interactive && !taskCards?.length) throw new Error('Sending requires a target and text, interactive content, or task_cards');
    const paths = call.args.local_images as string[] | undefined;
    const filePaths = call.args.local_files as string[] | undefined;
    const hasLocalMedia = !!(paths?.length || filePaths?.length);
    const replyTo=typeof call.args.reply_to_message_id==='string'?call.args.reply_to_message_id:undefined;
    const incident=typeof call.args.incident_ref==='string'?call.args.incident_ref:undefined;
    if(incident&&(call.sessionId!==binding.sessionId||call.method!=='send_message'||interactive||(call.args.attachments as unknown[]|undefined)?.length||taskCards?.length))throw new Error('Incident communication belongs to the main PA and must be plain self-authored text');
    const representation=call.method==='send_user_message'?'owner':'self';
    if (hasLocalMedia && (incident || representation !== 'self')) throw new Error('Local attachments require a regular self-authored message');
    if(representation==='owner' && (call.sessionId!==binding.sessionId || !config.personal))throw new Error('Only the bound main PA may represent its owner');
    const deliveryTarget=this.options.store.canonicalConversation(config.agentId,targetBase.replace(/^conversation:/,''));
    if (hasLocalMedia && deliveryTarget.startsWith('external:')) throw new Error('Local attachments require a writable Nano IM conversation');
    if(deliveryTarget.startsWith('external:')&&representation==='owner')throw new Error('Owner representation requires a native IM conversation');
    if((replyTo || inThread) && deliveryTarget.startsWith('external:'))throw new Error('Quotes and topics require a Nano IM destination');
    const conversation = deliveryTarget.startsWith('external:')?targetBase.replace(/^conversation:/,''):await this.resolve(config,targetBase);
    const reviewTarget = joinThreadTarget(conversation, inThread);
    if(incident) {
      const event=await this.request(config,'pa.incident.read',{incident_ref:incident,conversation_id:conversation});
      const receipt=conversation===config.personal!.conversationId?event.owner_notice_message_id:event.peer_notice_message_id;
      if(typeof receipt==='string')return {status:'sent',target,message_id:receipt,conversation_id:conversation};
    }
    const incidentKey=incident?`pa-incident:${incident}:${conversation===config.personal!.conversationId?'owner':'peer'}`:undefined;
    let operationId=incidentKey??call.operationId;
    const publicationBody = sortedJsonAscii({text, attachments:call.args.attachments ?? [], interactive:interactive ?? null, representation, ...(paths ? {local_images:paths} : {}), ...(filePaths ? {local_files:filePaths} : {}), ...(replyTo ? {reply_to_message_id:replyTo} : {}), ...(inThread ? {in_thread_of:inThread} : {}), ...(taskCards?.length ? {task_cards:taskCards} : {})});
    const incidentPrevious=incidentKey?inbox.incidentPublication(incidentKey):undefined;
    let previous = incidentPrevious??inbox.publication(operationId);
    if(incidentKey&&incidentPrevious&&previous) {
      operationId=incidentPrevious.id;
      if(['sending','unknown'].includes(previous.state)) {
        if(conversation===config.personal!.conversationId) {
          const status=await this.options.relay.request('agent.message.status',{node_id:this.options.nodeId,agent_id:config.agentId,operation_id:operationId});
          if(status.payload.found===true&&typeof status.payload.message_id==='string'&&status.payload.conversation_id===conversation) {
            const result={status:'sent',target,message_id:status.payload.message_id,conversation_id:conversation};
            inbox.settlePublication(operationId,'confirmed',result);
            await this.request(config,'pa.incident.receipt',{incident_ref:incident,message_id:result.message_id});
            return result;
          }
        }
        return {status:'unknown',operation_id:operationId,message:incident?'Call send_message with the same incident_ref and target to check its receipt; this will not resend while unknown.':'Check the existing publication receipt; do not resend with another key.'};
      }
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
    if (hasLocalMedia && previous && ['sending','unknown'].includes(previous.state)) {
      const receipt = await this.screenshotReceipt(config, target, operationId).catch(() => undefined);
      if (receipt?.found !== true) return unknownScreenshotReceipt(target, operationId);
      const result = {status:'sent', target, message_id:receipt.message_id, conversation_id:receipt.conversation_id};
      inbox.settlePublication(operationId, 'confirmed', result);
      return result;
    }
    if(previous&&['sending','unknown'].includes(previous.state))return {status:'unknown',operation_id:operationId,message:incident?'Call send_message with the same incident_ref and target to check its receipt; this will not resend while unknown.':'Check the existing publication receipt; do not resend with another key.'};
    if(deliveryTarget.startsWith('external:')) {
      if(representation==='owner')throw new Error('Owner representation requires a native IM conversation');
      const shadowId = this.options.store.imConversation(config.agentId, deliveryTarget);
      await this.options.flushConversation?.(config, binding, shadowId);
      if (shadowId && inbox.blocking(config.agentId, joinThreadTarget(shadowId, inThread))) {
        return {status:'held_for_revalidation',target,message:'Read new messages in this conversation and reconsider this draft before sending.'};
      }
      const externalText = taskCards?.length ? await this.formatExternalTaskCardsText(config.agentId, text, taskCards) : text;
      const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${deliveryTarget}`,text:externalText,
        ...(incident?{pa_incident_ref:incident}:{}),from_session_id:`${config.agentId}|tool_call:${operationId}`});
      if(typeof response.payload.message_id!=='string')throw new Error('External provider has no delivery receipt');
      return {status:'sent',target,message_id:response.payload.message_id};
    }
    if (conversation !== config.personal!.conversationId) await this.options.flushConversation?.(config, binding, conversation);
    if (inbox.blocking(config.agentId,reviewTarget)) return {status:'held_for_revalidation',target,
      message:'Read new messages in this conversation and reconsider this draft before sending.'};
    inbox.preparePublication(operationId,target,publicationBody,binding.agentId);
    let attachments = call.args.attachments ?? [];
    if (hasLocalMedia) {
      if (conversation !== config.personal!.conversationId)
        await this.request(config, 'pa.action.status', {request_key:operationId,conversation_id:conversation,prepare_screenshot:!!paths?.length,prepare_attachment:true});
      attachments = await prepareLocalAttachments(this.options.uploadScreenshot, this.options.uploadAttachment, {
        agentId:config.agentId, conversationId:config.personal!.conversationId, operationId,
        lifecycleRevision:this.options.store.lifecycle.assert(config.agentId), signal,
      }, paths, filePaths, call.args.attachments);
      signal.throwIfAborted();
      if (conversation !== config.personal!.conversationId) await this.options.flushConversation?.(config, binding, conversation);
      if (inbox.blocking(config.agentId,reviewTarget)) {
        const result = {status:'held_for_revalidation',target,message:'Read the new messages before sending this draft.'};
        inbox.settlePublication(operationId, 'held', result);
        return result;
      }
    }
    if (conversation === config.personal!.conversationId) {
      if(representation==='owner')throw new Error('Owner representation cannot target the owner PA conversation');
      // Private owner replies use the ordinary publication path, including IntelligentUI.
      inbox.settlePublication(operationId,'sending');
      try {
        const response=await this.options.relay.request('agent.message',{node_id:this.options.nodeId,to:`conversation:${conversation}`,text,
          attachments,...(interactive ? {interactive} : {}), ...(taskCards?.length ? {task_cards:taskCards} : {}), ...(replyTo ? {reply_to_message_id:replyTo} : {}), ...(inThread ? {in_thread_of:inThread} : {}),
          ...(incident?{pa_incident_ref:incident}:{}),from_session_id:`${config.agentId}|tool_call:${operationId}`});
        if(typeof response.payload.message_id !== 'string') throw new Error('Missing actual delivery receipt');
        const result={status:'sent',target,message_id:response.payload.message_id,conversation_id:response.payload.conversation_id};
        inbox.settlePublication(operationId,'confirmed',result);
        if(incident)await this.request(config,'pa.incident.receipt',{incident_ref:incident,message_id:response.payload.message_id});
        return result;
      } catch(error) {
        if (hasLocalMedia && error instanceof RelayDeliveryError && error.delivery === 'not-sent') {
          const result = {status:'not_sent',target,reason:error.message};
          inbox.settlePublication(operationId,'rejected',result);
          return result;
        }
        if ((interactive || hasLocalMedia || taskCards?.length) && error instanceof RelayDeliveryError && error.delivery === 'rejected') {
          inbox.settlePublication(operationId,'rejected');
          throw new Error(error.detail ? JSON.stringify(error.detail) : error.code ?? error.message);
        }
        if(inbox.publication(operationId)?.state!=='confirmed')inbox.settlePublication(operationId,'unknown');
        if (hasLocalMedia) return unknownScreenshotReceipt(target, operationId);
        throw error;
      }
    }
    const proposal = await this.request(config,'pa.action.prepare',{request_key:operationId,representation,conversation_id:conversation,
      ...(incident?{incident_ref:incident}:{}),content:text,attachments,...(interactive ? {interactive} : {}), ...(taskCards?.length ? {task_cards:taskCards} : {}), ...(replyTo ? {reply_to_message_id:replyTo} : {}), ...(inThread ? {in_thread_of:inThread} : {})});
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
    } catch(error) {
      const rejected=interactive && (error as {detail?:{code?:string}}).detail?.code==='invalid_interactive_source';
      if (hasLocalMedia && !rejected && error instanceof Error
        && (error instanceof RelayDeliveryError ? error.delivery !== 'unknown' : 'detail' in error)) {
        const result = {status:'not_sent',target,reason:error.message};
        inbox.settlePublication(operationId,'rejected',result);
        return result;
      }
      inbox.settlePublication(operationId,rejected?'rejected':'unknown');
      if (hasLocalMedia && !rejected) return unknownScreenshotReceipt(target, operationId);
      throw error;
    }
  }

  /** Freeze and consume a provider permit immediately before the real channel send. */
  async external(config:AgentConfiguration,binding:SessionBinding,delivery:ExternalDelivery):Promise<string> {
    if(!delivery.shadowId)throw new Error('External source has not yet synchronized');
    await this.options.flushConversation?.(config, binding, delivery.shadowId);
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
  private async formatExternalTaskCardsText(agentId: string, baseText: string, taskCards: TaskCardRef[]): Promise<string> {
    const refs = taskCards.map(card => `${card.graph_id}:${card.node_id}`).join(',');
    let lines: string[];
    try {
      const res = await this.options.relay.request('task_graph.command', {
        node_id: this.options.nodeId, agent_id: agentId, request_id: randomUUID(), action: 'nodes', source_message_id: null, args: { refs },
      });
      const items = res.payload.ok ? ((res.payload.result as { items?: { graph_id: string; node_id: string; title: string; status: string }[] })?.items ?? []) : [];
      const byKey = new Map(items.map(item => [`${item.graph_id}:${item.node_id}`, item]));
      lines = taskCards.map(card => {
        const hit = byKey.get(`${card.graph_id}:${card.node_id}`);
        if (!hit) return `- ${card.graph_id}/${card.node_id}`;
        const label = TASK_STATUS_BADGE_LABELS[hit.status as TaskStatus] ?? hit.status;
        return `- [${label}] ${hit.title}`;
      });
    } catch {
      lines = taskCards.map(card => `- ${card.graph_id}/${card.node_id}`);
    }
    const summary = `关联事项：\n${lines.join('\n')}`;
    return baseText.trim() ? `${baseText.trimEnd()}\n\n${summary}` : summary;
  }

}
