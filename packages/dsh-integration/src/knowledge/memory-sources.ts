import { createHash, randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, type SessionEvent } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import type { SessionBinding } from '../index.js';
import { qualifiedEvents, safeBoundary, sourceConversations } from './memory-source-view.js';
import { estimateInputTokens } from './dreaming-budget.js';
import { isHumanSource } from '../input-source.js';
import { batchToolResult, historyLocators, nativeMaterial, renderMaterial, renderSessionMaterials, type HistoryLocators } from './memory-trajectory.js';
export { renderMaterial, renderSessionMaterials } from './memory-trajectory.js';

export interface SourceContinuation { hash: string; offset: number; messageId?: string; segment?: number; boundedToolOutput?: true }
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
  events: unknown[]; page?: { offset: number; end: number; total: number; hash: string };
}
export interface CycleTarget {
  generation: number; activationAt: number;
  roots: Record<string, { through: number; time: number; baseline?: number }>;
  children: Record<string, { rootSessionId: string; through: number; time: number; baseline: number }>;
  blocked: Array<{sessionId: string; reason: string}>;
}
export interface ChildMaterial {
  sessionId: string; rootSessionId: string; baseline: number; through: number; sourceVersion: string;
  text: string; events: SessionEvent[]; inheritedEvents: SessionEvent[]; historyLocators?: HistoryLocators; omitted: number; unavailable?: number;
}
export interface SourceOptions { maxInputTokens: number; rotation?: number; target?: CycleTarget; generation?: number }
export interface FrozenBatch {
  id: string; units: MemoryUnit[]; ranges: Array<{ sessionId: string; start: number; through: number; observed: number; continuation?: SourceContinuation }>;
  conversations?: string[]; text?: string; cutoffs?: Record<string, number>; historyThrough?: Record<string, number>; filtered: number; blocked: Array<{ sessionId: string; reason: string }>; inputTokens: number;
}
const hash = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');

/** Split oversized records without parsing or rewriting tool payloads. */
function materialSegments(values: readonly unknown[]): Array<{messageId:string;text:string;source:unknown}> {
  return values.flatMap((value,index)=>{
    const record=value as Record<string,unknown>;
    const {content,arguments:toolArguments,...source}=record;
    return [{messageId:String(record.messageId??String(record.seq??index)),
      text:record.type==='tool/call' ? String(toolArguments ?? '') : typeof content==='string'?content:renderMaterial([{content}]),source}];
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
   *   options: Input budget and frozen source boundaries.
   * Returns:
   *   Immutable material, source ranges and explicit gaps; no cursor is committed here.
   */
  async freeze(agentId: string, streams: Record<string, StreamProgress>, options: SourceOptions): Promise<FrozenBatch> {
    const result: FrozenBatch = { id: randomUUID(), units: [], ranges: [], filtered: 0, blocked: [], inputTokens: 0 };
    const roots = [...this.bindings.values()].filter(binding => binding.agentId === agentId && streams[binding.sessionId]).sort((a, b) => a.sessionId.localeCompare(b.sessionId));
    const rotation = roots.length ? (options.rotation ?? 0) % roots.length : 0;
    for (const binding of [...roots.slice(rotation), ...roots.slice(0, rotation)]) {
      const id = SessionId(binding.sessionId); const progress = streams[id]!;
      try {
        const live = this.ctx.sessions.get(id);
        if (live && !await this.ctx.sessions.flush(live)) throw new Error('No persistence listener certified the live source.');
        using observation = await this.ctx.sessionQuery.observeSession(id, { projectionMode: 'none' });
        if (observation.header.cwd !== binding.cwd || observation.header.origin === 'subagent') throw new Error('Source identity does not match the trusted root binding.');
        const observed = options.target?.roots[id]?.through ?? observation.cursor;
        if (options.target && !options.target.roots[id]) continue;
        // Copy the immutable cut BEFORE the second barrier. Never replace it with a newer live log.
        const locators = historyLocators(id, qualifiedEvents(observation.events.filter(event => event.seq <= observed &&
          (event.type.startsWith('compaction/') || event.seq > Math.max(progress.baseline, observation.inheritedEventCount - 1)))));
        const events = observation.events.slice(observation.inheritedEventCount).filter(event => event.seq > Math.max(progress.baseline, progress.cursor) && event.seq <= observed);
        if (observation.source === 'live') {
          if (!live || this.ctx.sessions.get(id) !== live || !await this.ctx.sessions.flush(live)) throw new Error('Observed source cut could not be durably certified.');
        } else if (!observation.revision) throw new Error('Cold source has no durable revision.');
        const pending = new Set<string>(); const calls = new Map<string,Extract<SessionEvent,{type:'tool/call'}>>();
        let start = Math.max(progress.cursor, progress.baseline); let through = start; let selected: unknown[] = [];
        let stopped = false; let continuation: SourceContinuation | undefined;
        for (const event of events) {
          if (typeof event.surfaceOp === 'object' && event.surfaceOp.op === 'replace') { result.filtered++; continue; }
          if (event.type === 'tool/call') {
            pending.add(event.data.callId);
            calls.set(event.data.callId,event);
            selected.push(nativeMaterial(event, locators[event.seq]));
          } else if (event.type === 'tool/result') {
            pending.delete(event.data.message.toolCallId);
            const call = calls.get(event.data.message.toolCallId);
            if (!call) { result.blocked.push({ sessionId: id, reason: 'Unpaired result; source prefix is incomplete.' }); stopped = true; break; }
            (result.conversations ??= []).push(...sourceConversations([call,event]));
            // Older continuations were computed against full tool output.
            selected.push(progress.continuation && start === progress.cursor && !progress.continuation.boundedToolOutput
              ? nativeMaterial(event, locators[event.seq])
              : batchToolResult(event, call.data.name, locators[event.seq]));
          } else if (event.type === 'user/message') {
            const source = event.data.source;
            if (isHumanSource(source) || source.kind === 'agent-message' || source.kind === 'subagent-settled') {
              const conversation = 'conversationId' in source ? String(source.conversationId) : '';
              if(conversation)(result.conversations??=[]).push(conversation);
              selected.push(nativeMaterial(event, locators[event.seq]));
            } else result.filtered++;
          } else if (event.type === 'assistant/message') {
            const content = event.data.message.content.filter(block => block.type === 'text');
            if (content.length) selected.push(nativeMaterial(event, locators[event.seq]));
          } else if (event.type === 'step/end' && pending.size === 0) {
            const tokens = estimateInputTokens(JSON.stringify(selected));
            if (tokens > options.maxInputTokens || progress.continuation && start === progress.cursor) {
              const segments = materialSegments(selected);
              const saved = progress.continuation;
              const boundedToolOutput = !saved || saved.boundedToolOutput ? {boundedToolOutput:true as const} : {};
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
              if ((end > offset || characters.length===0) && estimateInputTokens(JSON.stringify(pageEvents)) <= remaining) {
                const segmentComplete = end === characters.length;
                const complete = segmentComplete && segment === segments.length-1;
                result.units.push({ id: `${id}:${start + 1}-${event.seq}:message-${segment}-${offset}-${end}`, sessionId:id,start,through:event.seq,
                  events:pageEvents,page:{offset,end,total:characters.length,hash:bodyHash} });
                result.inputTokens += estimateInputTokens(JSON.stringify(pageEvents));
                if(complete)through=event.seq;
                else if(segmentComplete){const next=segments[segment+1]!;continuation={hash:hash(next.text),offset:0,messageId:next.messageId,segment:segment+1,...boundedToolOutput};}
                else continuation={hash:bodyHash,offset:end,messageId:item.messageId,segment,...boundedToolOutput};
              }
              result.blocked.push({ sessionId:id,reason:'Original message material continues on the next bounded page; the complete-step cursor advances only after every segment.' });
              stopped = true; break;
            }
            if (result.inputTokens + tokens > options.maxInputTokens) {
              result.blocked.push({ sessionId: id, reason: 'Next complete unit exceeds the remaining input budget.' }); stopped = true; break;
            }
            if (selected.length) {
              result.units.push({ id: `${id}:${start + 1}-${event.seq}`, sessionId: id, start, through: event.seq, events: selected });
              result.inputTokens += tokens;
            }
            through = event.seq; start = through; selected = [];
          } else result.filtered++;
        }
        result.cutoffs ??= {};
        const boundary = events.find(event => event.seq === (continuation ? result.units.at(-1)?.through : through));
        result.cutoffs[id] = boundary?.time ?? options.target?.roots[id]?.time ?? 0;
        result.ranges.push({ sessionId: id, start: progress.cursor, through, observed, ...(continuation ? { continuation } : {}) });
        if (!stopped && pending.size) result.blocked.push({ sessionId: id, reason: 'Open tool calls remain beyond the safe step boundary.' });
      } catch (error) { result.blocked.push({ sessionId: id, reason: String(error) }); }
    }
    result.text = renderSessionMaterials(result.units).map(group => group.text).join('\n\n');
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
    const parents = new Map<string, Map<number, SessionEvent>>();
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
        const events = qualifiedEvents(own.filter(event => event.seq <= cut.through));
        let parent = parents.get(limit.rootSessionId);
        if (!parent) {
          parent = new Map((await this.snapshot(limit.rootSessionId)).events.map(event => [event.seq, event]));
          parents.set(limit.rootSessionId, parent);
        }
        const inherited = snapshot.events.slice(0,snapshot.inheritedEventCount).filter(event => event.seq > (target.roots[limit.rootSessionId]?.baseline??-1) && event.time >= target.activationAt && event.time <= cutoff);
        // A fork copy must still match the original parent record. Missing provenance stays a gap.
        const matchedInherited = inherited.filter(event => { const original = parent.get(event.seq); return original !== undefined && hash(original) === hash(event); });
        const inheritedEvents = qualifiedEvents(matchedInherited);
        const locators: HistoryLocators = {
          [sessionId]: historyLocators(sessionId, qualifiedEvents(snapshot.events.filter(event => event.seq <= cut.through && event.time <= cutoff &&
            (event.type.startsWith('compaction/') || event.seq > Math.max(limit.baseline, snapshot.inheritedEventCount - 1))))),
          [limit.rootSessionId]: historyLocators(limit.rootSessionId, qualifiedEvents([...parent.values()].filter(event => event.time <= cutoff &&
            (event.type.startsWith('compaction/') || event.seq > (target.roots[limit.rootSessionId]?.baseline ?? -1))))),
        };
        const material = selectChildMaterial({sessionId,rootSessionId:limit.rootSessionId,events,inheritedEvents,historyLocators:locators,unavailable:inherited.length-matchedInherited.length}, options.maxInputTokens);
        result.push({sessionId,rootSessionId:limit.rootSessionId,baseline:limit.baseline,through:cut.through,sourceVersion:hash({events,inheritedEvents,generation:target.generation,through:cut.through}),...material,events,inheritedEvents,historyLocators:locators,unavailable:inherited.length-matchedInherited.length});
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

/** Repack the same certified child evidence without querying or changing its source version. */
export function selectChildMaterial(material: Pick<ChildMaterial,'sessionId'|'rootSessionId'|'events'|'inheritedEvents'|'unavailable'|'historyLocators'>, maxInputTokens: number): {text:string;omitted:number} {
  const entries = [...material.inheritedEvents.map(event => ({event,sessionId:material.rootSessionId,inherited:true})), ...material.events.map(event => ({event,sessionId:material.sessionId,inherited:false}))]
    .filter(({event})=>event.type==='user/message'||event.type==='tool/call'||event.type==='tool/result'||event.type==='assistant/message'&&event.data.message.content.some(block=>block.type==='text'))
    .map(entry=>entry.event.type==='assistant/message'?{...entry,event:{...entry.event,data:{...entry.event.data,message:{...entry.event.data.message,content:entry.event.data.message.content.filter(block=>block.type==='text')}}}}:entry);
  const messageCalls = new Set(entries.flatMap(({event}) => event.type === 'tool/call' && ['inbox','conversations'].includes(event.data.name) ? [event.data.callId] : []));
  const priority = (event: SessionEvent) => event.type === 'user/message' || event.type === 'tool/result' && messageCalls.has(event.data.message.toolCallId) ? 0 : event.type === 'assistant/message' ? 1 : 2;
  const groupKey = (entry: typeof entries[number]) => {
    const event = entry.event;
    const callId = event.type === 'tool/call' ? event.data.callId : event.type === 'tool/result' ? event.data.message.toolCallId : undefined;
    return callId ? JSON.stringify([entry.sessionId, entry.inherited, callId]) : undefined;
  };
  const locators = material.historyLocators ?? {
    [material.rootSessionId]: historyLocators(material.rootSessionId, material.inheritedEvents),
    [material.sessionId]: historyLocators(material.sessionId, material.events),
  };
  const toolNames = new Map<string, string>();
  for (const entry of entries) {
    if (entry.event.type === 'tool/call') toolNames.set(groupKey(entry)!, entry.event.data.name);
  }
  const records = entries.map(entry => {
    const {event,sessionId,inherited} = entry;
    const locator = locators[sessionId]?.[event.seq];
    return event.type === 'tool/result'
      ? batchToolResult(event, toolNames.get(groupKey(entry)!), locator)
      : nativeMaterial(event, locator, {mainAgentSessionId:material.rootSessionId,delegated:!inherited && material.sessionId !== material.rootSessionId});
  });
  const sizes = entries.map((entry, index) => {
    const content = records[index]?.content;
    const event = entry.event;
    return estimateInputTokens(JSON.stringify(event.type === 'tool/result' && typeof content === 'string'
      ? {...entry,event:{...event,data:{...event.data,message:{...event.data.message,content}}}}
      : entry));
  });
  const groups = new Map<string, {indices:number[];size:number}>();
  for (const [index, entry] of entries.entries()) {
    const key = groupKey(entry);
    if (!key) continue;
    const group = groups.get(key) ?? {indices:[],size:0};
    group.indices.push(index);
    group.size += sizes[index]!;
    groups.set(key, group);
  }
  const selected = new Set<number>(); let used = 0;
  for (const {index,entry} of entries.map((entry,index)=>({entry,index})).sort((a,b)=>priority(a.entry.event)-priority(b.entry.event) || b.entry.event.time-a.entry.event.time)) {
    if (selected.has(index)) continue;
    const key = groupKey(entry);
    const group = key ? groups.get(key)! : {indices:[index],size:sizes[index]!};
    if (used + group.size <= maxInputTokens) { for (const i of group.indices) selected.add(i); used += group.size; }
  }
  const sections = [true,false].flatMap(inherited => {
    const sessionId = inherited ? material.rootSessionId : material.sessionId;
    const selectedRecords = records.filter((_, index) => entries[index]!.inherited === inherited && selected.has(index));
    if (!selectedRecords.length) return [];
    return [`${inherited ? 'Inherited background, not new evidence' : 'Own experience'}\n\n${renderSessionMaterials([{sessionId,events:selectedRecords}])[0]!.text}`];
  });
  const text = sections.join('\n\n');
  const omitted = entries.length-selected.size + (material.unavailable??0);
  return {text: omitted ? `${text}\n\nAdditional records omitted for input capacity or unavailable provenance: ${omitted}.` : text,omitted};
}
