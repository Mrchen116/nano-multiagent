import { createHash, randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, type SessionEvent } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import type { SessionBinding } from '../index.js';
import { qualifiedEvents, safeBoundary } from './memory-source-view.js';
import { estimateInputTokens } from './dreaming-budget.js';
import { isHumanSource } from '../input-source.js';
import type { SourceEligibility } from './memory-documents.js';

export interface SourceContinuation { hash: string; offset: number; messageId?: string; segment?: number }
export interface StreamProgress { baseline: number; cursor: number; continuation?: SourceContinuation }
/** Commit only reviewed pages; a logical unit's cursor advances after its last page. */
export function commitSourceRange(progress: StreamProgress, range: FrozenBatch['ranges'][number]): void {
  if (range.through < progress.cursor) return;
  if (range.through > progress.cursor) { progress.cursor = range.through; delete progress.continuation; }
  if (range.continuation && (!progress.continuation || progress.continuation.hash !== range.continuation.hash || (progress.continuation.segment ?? 0) < (range.continuation.segment ?? 0) || (progress.continuation.segment ?? 0) === (range.continuation.segment ?? 0) && progress.continuation.offset < range.continuation.offset)) {
    progress.continuation = range.continuation;
  }
}
export interface MemoryUnit {
  id: string; sessionId: string; start: number; through: number;
  events: unknown[]; fingerprints: string[]; page?: { offset: number; end: number; total: number; hash: string };
}
export interface CycleTarget {
  generation: number; activationAt: number;
  roots: Record<string, { through: number; time: number; baseline?: number }>;
  children: Record<string, { rootSessionId: string; through: number; time: number; baseline: number }>;
  blocked: Array<{sessionId: string; reason: string}>;
}
export interface ChildMaterial {
  sessionId: string; rootSessionId: string; baseline: number; through: number; sourceVersion: string;
  text: string; events: SessionEvent[]; inheritedEvents: SessionEvent[]; omitted: number; unavailable?: number;
}
export interface SourceOptions { maxInputTokens: number; seen?: string[]; sources?: SourceEligibility; excluded?: string[]; rotation?: number; target?: CycleTarget; generation?: number }
export interface FrozenBatch {
  id: string; units: MemoryUnit[]; ranges: Array<{ sessionId: string; start: number; through: number; observed: number; continuation?: SourceContinuation }>;
  conversations?: string[]; text?: string; cutoffs?: Record<string, number>; filtered: number; blocked: Array<{ sessionId: string; reason: string }>; inputTokens: number;
}
const hash = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const dataText = (content: readonly { type: string; text?: string }[]) => content.filter(block => block.type === 'text').map(block => block.text ?? '').join('\n');
const messageContent = (content: unknown): unknown => {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return content;
  const blocks: unknown[] = [];
  for (const block of content) {
    if (block?.type === 'text') {
      if (typeof blocks.at(-1) === 'string') blocks[blocks.length - 1] += String(block.text ?? '');
      else blocks.push(String(block.text ?? ''));
    } else blocks.push(block);
  }
  return blocks.length === 1 && typeof blocks[0] === 'string' ? blocks[0] : blocks;
};
const excludedTools = new Set(['notes', 'history', 'source_history', 'new_context', 'get_context_remaining', 'memory', 'memory_maintenance', 'skill', 'skill_manage', 'read_note', 'write_note', 'list_notes', 'search_history', 'read_history', 'list_history']);

/** Render evidence as readable source paragraphs; metadata remains attached to its original record. */
export function renderMaterial(events: readonly unknown[]): string {
  return events.map(value => {
    const e = value as Record<string, unknown>;
    if (e.type === 'source_text_continuation') return `Original message ${e.messageId}; characters ${e.offset}–${e.end}/${e.total}; ${Number(e.end)<Number(e.total)?'same message continues':'message end'}\nSource: ${JSON.stringify(e.source)}\n${e.text}`;
    const { content, ...metadata } = e;
    if (content && typeof content === 'object' && !Array.isArray(content) && Array.isArray((content as {messages?:unknown[]}).messages)) {
      const {messages,...envelope} = content as {messages: Record<string,unknown>[]};
      return `${JSON.stringify(metadata)}\nConversation: ${JSON.stringify(envelope)}\n${renderMaterial(messages)}`;
    }
    const text = typeof content === 'string' ? content : Array.isArray(content)
      ? content.map(block => block?.type === 'text' ? block.text : `[attachment: ${JSON.stringify(block)}]`).join('\n')
      : content === undefined ? '' : JSON.stringify(content, null, 2);
    return `${JSON.stringify(metadata)}\n${text}`;
  }).join('\n\n');
}

/** Split at original message boundaries so a long human message retains its identity. */
function materialSegments(values: readonly unknown[]): Array<{messageId:string;text:string;source:unknown}> {
  return values.flatMap((value,index)=>{
    const record=value as Record<string,unknown>;
    const body=record.content as {messages?:Record<string,unknown>[]} | undefined;
    if(body && !Array.isArray(body) && typeof body==='object' && Array.isArray(body.messages)){
      const {messages,...envelope}=body;
      return messages.map((message,i)=>({messageId:String(message.id??message.message_id??`${record.seq}:${i}`),
        text:typeof message.content==='string'?message.content:renderMaterial([{content:message.content}]).replace(/^\{\}\n/,''),
        source:{...record,content:undefined,conversation:envelope,message:{...message,content:undefined}}}));
    }
    const {content,...source}=record;
    return [{messageId:String(record.messageId??`${record.sessionId}:${record.seq??index}`),
      text:typeof content==='string'?content:renderMaterial([{content}]).replace(/^\{\}\n/,''),source}];
  });
}

/** Exports only certified, paired own history from this business Agent's trusted roots. */
export class MemorySources {
  constructor(private readonly ctx: Pick<Context, 'sessionQuery' | 'sessions'>, private readonly bindings: Map<string, SessionBinding>) {}
  /** Freeze a bounded continuous prefix per stream, without retaining observations across streams.
   *
   * Args:
   *   agentId: Trusted business owner, never an arbitrary model-provided identity.
   *   streams: Previously committed baselines and cursors.
   *   options: Input budget, deduplication receipts and current source eligibility.
   * Returns:
   *   Immutable material, source ranges and explicit gaps; no cursor is committed here.
   */
  async freeze(agentId: string, streams: Record<string, StreamProgress>, options: SourceOptions): Promise<FrozenBatch> {
    const result: FrozenBatch = { id: randomUUID(), units: [], ranges: [], filtered: 0, blocked: [], inputTokens: 0 };
    const seen = new Set(options.seen ?? []);
    const roots = [...this.bindings.values()].filter(binding => binding.agentId === agentId && streams[binding.sessionId]).sort((a, b) => a.sessionId.localeCompare(b.sessionId));
    const rotation = roots.length ? (options.rotation ?? 0) % roots.length : 0;
    for (const binding of [...roots.slice(rotation), ...roots.slice(0, rotation)]) {
      const streamSeen = new Set(seen);
      const id = SessionId(binding.sessionId); const progress = streams[id]!;
      try {
        const live = this.ctx.sessions.get(id);
        if (live && !await this.ctx.sessions.flush(live)) throw new Error('No persistence listener certified the live source.');
        using observation = await this.ctx.sessionQuery.observeSession(id, { projectionMode: 'none' });
        if (observation.header.cwd !== binding.cwd || observation.header.origin === 'subagent') throw new Error('Source identity does not match the trusted root binding.');
        const observed = options.target?.roots[id]?.through ?? observation.cursor;
        if (options.target && !options.target.roots[id]) continue;
        // Copy the immutable cut BEFORE the second barrier. Never replace it with a newer live log.
        const events = observation.events.slice(observation.inheritedEventCount).filter(event => event.seq > Math.max(progress.baseline, progress.cursor) && event.seq <= observed);
        if (observation.source === 'live') {
          if (!live || this.ctx.sessions.get(id) !== live || !await this.ctx.sessions.flush(live)) throw new Error('Observed source cut could not be durably certified.');
        } else if (!observation.revision) throw new Error('Cold source has no durable revision.');
        const fragments = new Map<string, { total: number; parts: Map<number, Record<string, unknown>> }>();
        const pending = new Set<string>(); const calls = new Map<string, { name: string; arguments: unknown; skip: boolean }>();
        let start = Math.max(progress.cursor, progress.baseline); let through = start; let selected: unknown[] = []; let fingerprints: string[] = [];
        let stopped = false; let continuation: SourceContinuation | undefined;
        for (const event of events) {
          if (typeof event.surfaceOp === 'object' && event.surfaceOp.op === 'replace') { result.filtered++; continue; }
          if (event.type === 'tool/call') {
            pending.add(event.data.callId);
            let args: unknown;
            try { args = JSON.parse(event.data.arguments); } catch { args = event.data.arguments; }
            const value = args as { file_path?: string };
            const skip = excludedTools.has(event.data.name) || ['read', 'write', 'edit', 'glob', 'grep'].includes(event.data.name) && /\.nanoassistant\/(?:memory|maintenance)/.test(String(value?.file_path ?? ''));
            calls.set(event.data.callId, { name: event.data.name, arguments: args, skip });
            if (!skip) selected.push({ seq: event.seq, time: event.time, sessionId: id, type: 'tool/call', callId: event.data.callId, name: event.data.name, arguments: args });
            else result.filtered++;
          } else if (event.type === 'tool/result') {
            const call = calls.get(event.data.message.toolCallId); pending.delete(event.data.message.toolCallId);
            if (!call) { result.blocked.push({ sessionId: id, reason: 'Unpaired result; source prefix is incomplete.' }); stopped = true; break; }
            if (!call.skip) {
              let content: unknown = event.data.message.content;
              if (['inbox', 'conversations'].includes(call.name) && !event.data.message.isError) {
                try {
                  const body = JSON.parse(dataText(event.data.message.content)) as { source?: string; target?: string; conversation_id?: string; messages?: Array<Record<string, unknown>> };
                  if (Array.isArray(body.messages)) body.messages = body.messages.flatMap(original => {
                    let message = original;
                    const conversation = String(message.conversation_id ?? message.target ?? body.conversation_id ?? body.target ?? body.source ?? '');
                    const messageId = String(message.id ?? message.message_id ?? '');
                    if (options.excluded?.includes(conversation) || options.sources && (!options.sources.allowed.includes(conversation) || options.sources.excluded.includes(conversation))) { result.filtered++; return []; }
                    if (message.partial) {
                      const part = Number(message.part); const total = Number(message.parts);
                      const fragmentKey = `${conversation}:${messageId}`;
                      const group = fragments.get(fragmentKey) ?? { total, parts: new Map<number, Record<string, unknown>>() };
                      fragments.set(fragmentKey, group);
                      if (!Number.isInteger(part) || part < 1 || part > total || group.total !== total) return [];
                      group.parts.set(part, message);
                      if (group.parts.size !== total) return [];
                      message = { ...message, partial: false, content: Array.from({length: total}, (_, i) => group.parts.get(i + 1)!.content).flat() };
                      message.content = messageContent(message.content);
                      delete message.part; delete message.parts; fragments.delete(fragmentKey);
                    }
                    const sender = message.sender as {id?: string; type?: string} | undefined;
                    const identity = `${conversation}:${messageId}:${String(message.revision ?? hash({ content: messageContent(message.content), sender: {id:sender?.id,type:sender?.type} }))}`;
                    if (streamSeen.has(identity)) { result.filtered++; return []; }
                    streamSeen.add(identity); fingerprints.push(identity); (result.conversations??=[]).push(conversation); return [message];
                  });
                  content = body;
                } catch { content = { unavailable: 'Mixed-source payload could not be filtered safely.' }; result.filtered++; }
              }
              selected.push({ seq: event.seq, time: event.time, sessionId: id, type: 'tool/result', callId: event.data.message.toolCallId, isError: event.data.message.isError === true, content });
            } else result.filtered++;
          } else if (event.type === 'user/message') {
            const source = event.data.source;
            if (isHumanSource(source) || source.kind === 'agent-message' || source.kind === 'subagent-settled') {
              const conversation = 'conversationId' in source ? String(source.conversationId) : '';
              if (conversation && (options.excluded?.includes(conversation) || options.sources && (!options.sources.allowed.includes(conversation) || options.sources.excluded.includes(conversation)))) result.filtered++;
              else {
                if(conversation)(result.conversations??=[]).push(conversation);
                selected.push({ seq: event.seq, time: event.time, sessionId: id, type: 'user/message', messageId: event.data.id, source, content: event.data.content.filter(block => block.type !== 'reasoning') });

              }
            } else result.filtered++;
          } else if (event.type === 'assistant/message') {
            const content = event.data.message.content.filter(block => block.type === 'text');
            if (content.length) selected.push({ seq: event.seq, time: event.time, sessionId: id, type: 'assistant/message', evidence: 'assistant_self_report', content });
          } else if (event.type === 'step/end' && pending.size === 0 && fragments.size === 0) {
            const tokens = estimateInputTokens(JSON.stringify(selected));
            if (tokens > options.maxInputTokens) {
              const segments = materialSegments(selected);
              const saved = progress.continuation;
              const candidate = saved?.segment ?? 0;
              const matches = segments[candidate] && saved?.messageId === segments[candidate]!.messageId && saved.hash === hash(segments[candidate]!.text);
              const segment = matches ? candidate : 0;
              const item = segments[segment]!; const characters = Array.from(item.text); const bodyHash = hash(item.text);
              const offset = matches ? saved!.offset : 0;
              const remaining = options.maxInputTokens - result.inputTokens;
              let end = Math.min(characters.length, offset + Math.max(0, remaining * 3 - 800));
              const paragraph = characters.slice(offset,end).join('').lastIndexOf('\n\n');
              if(end < characters.length && paragraph > (end-offset)*0.75)end=offset+Array.from(characters.slice(offset,end).join('').slice(0,paragraph+2)).length;
              let pageEvents = [{ type:'source_text_continuation', messageId:item.messageId, source:item.source,
                offset, end, total:characters.length, text:characters.slice(offset,end).join('') }];
              while (end > offset && estimateInputTokens(JSON.stringify(pageEvents)) > remaining) {
                end -= Math.max(1, Math.ceil((end - offset) / 10));
                pageEvents = [{...pageEvents[0]!,end,text:characters.slice(offset,end).join('')}];
              }
              if (end > offset || characters.length===0) {
                const segmentComplete = end === characters.length;
                const complete = segmentComplete && segment === segments.length-1;
                result.units.push({ id: `${id}:${start + 1}-${event.seq}:message-${segment}-${offset}-${end}`, sessionId:id,start,through:event.seq,
                  events:pageEvents,fingerprints:complete?fingerprints:[],page:{offset,end,total:characters.length,hash:bodyHash} });
                result.inputTokens += estimateInputTokens(JSON.stringify(pageEvents));
                if(complete)through=event.seq;
                else if(segmentComplete){const next=segments[segment+1]!;continuation={hash:hash(next.text),offset:0,messageId:next.messageId,segment:segment+1};}
                else continuation={hash:bodyHash,offset:end,messageId:item.messageId,segment};
              }
              result.blocked.push({ sessionId:id,reason:'Original message material continues on the next bounded page; the complete-step cursor advances only after every segment.' });
              stopped = true; break;
            }
            if (result.inputTokens + tokens > options.maxInputTokens) {
              result.blocked.push({ sessionId: id, reason: 'Next complete unit exceeds the remaining input budget.' }); stopped = true; break;
            }
            if (selected.length) {
              result.units.push({ id: `${id}:${start + 1}-${event.seq}`, sessionId: id, start, through: event.seq, events: selected, fingerprints });
              result.inputTokens += tokens;
              for (const identity of fingerprints) seen.add(identity);
            }
            through = event.seq; start = through; selected = []; fingerprints = [];
          } else result.filtered++;
        }
        result.cutoffs ??= {};
        const boundary = events.find(event => event.seq === (continuation ? result.units.at(-1)?.through : through));
        result.cutoffs[id] = boundary?.time ?? options.target?.roots[id]?.time ?? 0;
        result.ranges.push({ sessionId: id, start: progress.cursor, through, observed, ...(continuation ? { continuation } : {}) });
        if (!stopped && fragments.size) result.blocked.push({ sessionId: id, reason: 'An observed Inbox message has unread fragments.' });
        if (!stopped && pending.size) result.blocked.push({ sessionId: id, reason: 'Open tool calls remain beyond the safe step boundary.' });
      } catch (error) { result.blocked.push({ sessionId: id, reason: String(error) }); }
    }
    result.text = result.units.map(unit => `## Source ${unit.sessionId}, events ${unit.start + 1}–${unit.through}${unit.page ? `; continuation ${unit.page.offset}–${unit.page.end}/${unit.page.total}` : ''}\n${renderMaterial(unit.events)}`).join('\n\n');
    return result;
  }
  /** Freeze certified per-source limits once; subsequent batches cannot include new arrivals. */
  async freezeTarget(agentId: string, streams: Record<string, StreamProgress>, activationAt: number, options: {generation?: number} = {}): Promise<CycleTarget> {
    const target: CycleTarget = { generation: options.generation ?? 0, activationAt, roots: {}, children: {}, blocked: [] };
    for (const binding of this.bindings.values()) {
      if (binding.agentId !== agentId || !streams[binding.sessionId]) continue;
      try {
        const root = await this.snapshot(binding.sessionId);
        if (root.header.cwd !== binding.cwd || root.header.origin === 'subagent') throw new Error('Untrusted root identity.');
        const own = root.events.slice(root.inheritedEventCount);
        target.roots[binding.sessionId] = {...safeBoundary(own),baseline:streams[binding.sessionId]!.baseline};
        for (const event of own) {
          if (event.type !== 'subagent/catalog' || event.data.mode === 'unknown') continue;
          const id = event.data.childId;
          try {
            const child = await this.snapshot(id);
            if (child.header.parentSession !== binding.sessionId || child.header.origin !== 'subagent') throw new Error('Untrusted direct child identity.');
            const events = child.events.slice(child.inheritedEventCount);
            const cut = safeBoundary(events);
            const baseline = event.data.childCreatedAt >= activationAt ? child.inheritedEventCount - 1 : safeBoundary(events, activationAt).through;
            if (!Number.isFinite(event.data.childCreatedAt) || events.some(item => !Number.isFinite(item.time))) throw new Error('Child activation/time boundary is unavailable.');
            target.children[id] = { rootSessionId: binding.sessionId, ...cut, baseline };
          } catch (error) { target.blocked.push({sessionId:id,reason:String(error)}); }
        }
      } catch (error) { target.blocked.push({sessionId:binding.sessionId,reason:String(error)}); }
    }
    return target;
  }

  /** Read one durable immutable cut; the returned events retain original native identity. */
  async snapshot(sessionId: string) {
    const id = SessionId(sessionId); const live = this.ctx.sessions.get(id);
    if (live && !await this.ctx.sessions.flush(live)) throw new Error('Source persistence barrier failed.');
    using observation = await this.ctx.sessionQuery.observeSession(id, {projectionMode:'none'});
    const copy = {header: observation.header, events: [...observation.events], inheritedEventCount: observation.inheritedEventCount, cursor: observation.cursor};
    if (observation.source === 'live') {
      if (!live || this.ctx.sessions.get(id) !== live || !await this.ctx.sessions.flush(live)) throw new Error('Source cut could not be certified.');
    } else if (!observation.revision) throw new Error('Cold source lacks durable revision.');
    return copy;
  }

  /** Re-select each direct task from its activation baseline, including qualified inherited context. */
  async children(agentId: string, target: CycleTarget, batch: FrozenBatch, options: SourceOptions): Promise<ChildMaterial[]> {
    const result: ChildMaterial[] = [];
    for (const [sessionId, limit] of Object.entries(target.children)) {
      const binding = this.bindings.get(limit.rootSessionId);
      if (!binding || binding.agentId !== agentId) continue;
      try {
        const snapshot = await this.snapshot(sessionId);
        if (snapshot.header.parentSession !== limit.rootSessionId || snapshot.header.origin !== 'subagent') throw new Error('Child identity changed.');
        const range = batch.ranges.find(item => item.sessionId === limit.rootSessionId);
        const rootIncrement = range && (range.through > range.start || range.continuation);
        const cutoff = rootIncrement ? batch.cutoffs?.[limit.rootSessionId] : limit.time;
        if (cutoff === undefined) throw new Error('Root batch cutoff is unavailable.');
        const own = snapshot.events.slice(snapshot.inheritedEventCount).filter(event => event.seq > limit.baseline && event.seq <= limit.through);
        const cut = safeBoundary(own, cutoff);
        if (cut.through <= limit.baseline) continue;
        const events = qualifiedEvents(own.filter(event => event.seq <= cut.through), options);
        const parent = await this.snapshot(limit.rootSessionId);
        const inherited = snapshot.events.slice(0,snapshot.inheritedEventCount).filter(event => event.seq > (target.roots[limit.rootSessionId]?.baseline??-1) && event.time >= target.activationAt && event.time <= cutoff);
        // A fork copy must still match the original parent record. Missing provenance stays a gap.
        const inheritedEvents = qualifiedEvents(inherited.filter(event => parent.events.some(original => original.seq === event.seq && hash(original) === hash(event))), options);
        const material = selectChildMaterial({sessionId,rootSessionId:limit.rootSessionId,events,inheritedEvents,unavailable:inherited.length-inheritedEvents.length}, options.maxInputTokens);
        result.push({sessionId,rootSessionId:limit.rootSessionId,baseline:limit.baseline,through:cut.through,sourceVersion:hash({events,inheritedEvents,generation:target.generation,through:cut.through}),...material,events,inheritedEvents,unavailable:inherited.length-inheritedEvents.length});
      } catch (error) { batch.blocked.push({sessionId,reason:String(error)}); }
    }
    return result;
  }

  /** Establish initial positions from persisted safe steps; no whole-history default import. */
  async baseline(agentId: string): Promise<Record<string, StreamProgress>> {
    const streams: Record<string, StreamProgress> = {};
    for (const binding of this.bindings.values()) {
      if (binding.agentId !== agentId) continue;
      const id = SessionId(binding.sessionId); const live = this.ctx.sessions.get(id);
      if (live && !await this.ctx.sessions.flush(live)) throw new Error('Unable to persist initial memory baseline.');
      try {
        using observation = await this.ctx.sessionQuery.observeSession(id, { projectionMode: 'none' });
        const cursor = observation.events.findLast(event => event.type === 'step/end')?.seq ?? -1;
      if (observation.source === 'live' && (!live || !await this.ctx.sessions.flush(live))) throw new Error('Unable to certify initial memory baseline.');
      if (observation.source === 'prepared' && !observation.revision) throw new Error('Initial cold baseline lacks a durable revision.');
      streams[id] = { baseline: cursor, cursor };
      } catch (error) {
        // Bindings may be registered before their first native session exists.
        if (!(error instanceof SessionQueryError) || error.code !== 'SESSION_QUERY_SESSION_NOT_FOUND') throw error;
      }
    }
    return streams;
  }
}

function renderNative(event: SessionEvent): string {
  if (event.type === 'user/message') return renderMaterial([{source:event.data.source,
    evidence:isHumanSource(event.data.source)?'host_attested_human':'agent_or_delegated_task_input_not_human_authorization',content:event.data.content}]);
  if (event.type === 'assistant/message') return renderMaterial([{role:'assistant',evidence:'self_report',content:event.data.message.content.filter(block=>block.type==='text')}]);
  if (event.type === 'tool/result') {
    let content:unknown=event.data.message.content;
    try{const body=JSON.parse(dataText(event.data.message.content));if(Array.isArray(body.messages))content=body;}catch{/* Non-JSON tool output remains original text. */}
    return renderMaterial([{role:'tool',callId:event.data.message.toolCallId,isError:event.data.message.isError,content}]);
  }
  return JSON.stringify(event.data);
}

/** Repack the same certified child evidence without querying or changing its source version. */
export function selectChildMaterial(material: Pick<ChildMaterial,'sessionId'|'rootSessionId'|'events'|'inheritedEvents'|'unavailable'>, maxInputTokens: number): {text:string;omitted:number} {
  const entries = [...material.inheritedEvents.map(event => ({event,sessionId:material.rootSessionId,inherited:true})), ...material.events.map(event => ({event,sessionId:material.sessionId,inherited:false}))];
  const messageCarrier = (event:SessionEvent) => event.type==='tool/result' && entries.some(item=>item.event.type==='tool/call' && item.event.data.callId===event.data.message.toolCallId && ['inbox','conversations'].includes(item.event.data.name));
  const priority = (event: SessionEvent) => event.type === 'user/message' || messageCarrier(event) ? 0 : event.type === 'assistant/message' ? 1 : 2;
  const selected = new Set<number>(); let used = 0;
  for (const {index,entry} of entries.map((entry,index)=>({entry,index})).sort((a,b)=>priority(a.entry.event)-priority(b.entry.event) || b.entry.event.time-a.entry.event.time)) {
    if (selected.has(index)) continue;
    const event = entry.event;
    const callId = event.type === 'tool/call' ? event.data.callId : event.type === 'tool/result' ? event.data.message.toolCallId : undefined;
    const group = callId ? entries.flatMap((candidate,i)=>candidate.sessionId === entry.sessionId && candidate.inherited === entry.inherited &&
      (candidate.event.type === 'tool/call' && candidate.event.data.callId === callId || candidate.event.type === 'tool/result' && candidate.event.data.message.toolCallId === callId) ? [i] : []) : [index];
    const size = group.reduce((sum,i)=>sum + estimateInputTokens(JSON.stringify(entries[i])),0);
    if (used + size <= maxInputTokens) { for (const i of group) selected.add(i); used += size; }
  }
  const text = entries.flatMap((entry,index)=>selected.has(index) ? [`### ${entry.inherited ? 'Inherited background, not new evidence' : 'Own experience'}; session_id=${entry.sessionId}; item_id=${entry.event.seq}; time=${entry.event.time}\n${renderNative(entry.event)}`] : []).join('\n\n');
  const omitted = entries.length-selected.size + (material.unavailable??0);
  return {text:`${text}\n\nOmitted/unavailable records: ${omitted}. Missing conditions remain unknown.`,omitted};
}
