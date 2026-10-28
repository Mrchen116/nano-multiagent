import { createHash, randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import type { SessionBinding } from '../index.js';
import { isHumanSource } from '../input-source.js';
import type { SourceEligibility } from './memory-documents.js';

export interface StreamProgress { baseline: number; cursor: number }
export interface MemoryUnit {
  id: string; sessionId: string; start: number; through: number;
  events: unknown[]; fingerprints: string[];
}
export interface FrozenBatch {
  id: string; units: MemoryUnit[]; ranges: Array<{ sessionId: string; start: number; through: number; observed: number }>;
  filtered: number; blocked: Array<{ sessionId: string; reason: string }>; inputTokens: number;
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
const excludedTools = new Set(['memory', 'memory_maintenance', 'skill', 'skill_manage', 'read_note', 'write_note', 'list_notes', 'search_history', 'read_history', 'list_history']);

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
  async freeze(agentId: string, streams: Record<string, StreamProgress>, options: { maxInputTokens: number; seen?: string[]; sources?: SourceEligibility; excluded?: string[]; rotation?: number }): Promise<FrozenBatch> {
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
        const observed = observation.cursor;
        // Copy the immutable cut BEFORE the second barrier. Never replace it with a newer live log.
        const events = observation.events.slice(observation.inheritedEventCount).filter(event => event.seq > Math.max(progress.baseline, progress.cursor));
        if (observation.source === 'live') {
          if (!live || this.ctx.sessions.get(id) !== live || !await this.ctx.sessions.flush(live)) throw new Error('Observed source cut could not be durably certified.');
        } else if (!observation.revision) throw new Error('Cold source has no durable revision.');
        const fragments = new Map<string, { total: number; parts: Map<number, Record<string, unknown>> }>();
        const pending = new Set<string>(); const calls = new Map<string, { name: string; arguments: unknown; skip: boolean }>();
        let start = Math.max(progress.cursor, progress.baseline); let through = start; let selected: unknown[] = []; let fingerprints: string[] = [];
        let stopped = false;
        for (const event of events) {
          if (typeof event.surfaceOp === 'object' && event.surfaceOp.op === 'replace') { result.filtered++; continue; }
          if (event.type === 'tool/call') {
            pending.add(event.data.callId);
            let args: unknown;
            try { args = JSON.parse(event.data.arguments); } catch { args = event.data.arguments; }
            const value = args as { file_path?: string };
            const skip = excludedTools.has(event.data.name) || ['read', 'write', 'edit', 'glob', 'grep'].includes(event.data.name) && /\.nanoassistant\/(?:memory|maintenance)/.test(String(value?.file_path ?? ''));
            calls.set(event.data.callId, { name: event.data.name, arguments: args, skip });
            if (!skip) selected.push({ seq: event.seq, type: 'tool/call', callId: event.data.callId, name: event.data.name, arguments: args });
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
                    streamSeen.add(identity); fingerprints.push(identity); return [message];
                  });
                  content = body;
                } catch { /* Preserve unparseable error/output as an observed result, not invented messages. */ }
              }
              selected.push({ seq: event.seq, type: 'tool/result', callId: event.data.message.toolCallId, isError: event.data.message.isError === true, content });
            } else result.filtered++;
          } else if (event.type === 'user/message') {
            const source = event.data.source;
            if (isHumanSource(source) || source.kind === 'agent-message' || source.kind === 'subagent-settled') {
              const conversation = 'conversationId' in source ? String(source.conversationId) : '';
              if (conversation && (options.excluded?.includes(conversation) || options.sources && !options.sources.allowed.includes(conversation))) result.filtered++;
              else {
                selected.push({ seq: event.seq, type: 'user/message', source, content: event.data.content.filter(block => block.type !== 'reasoning') });
                if (source.kind === 'agent-message' || source.kind === 'subagent-settled') {
                  const child = await this.childEvidence(id, source.senderSessionId);
                  if (child) {
                    const identity = `child:${source.senderSessionId}:${child.through}`;
                    if (!streamSeen.has(identity)) { selected.push(child); streamSeen.add(identity); fingerprints.push(identity); }
                  }
                }
              }
            } else result.filtered++;
          } else if (event.type === 'assistant/message') {
            const content = event.data.message.content.filter(block => block.type === 'text');
            if (content.length) selected.push({ seq: event.seq, type: 'assistant/message', evidence: 'assistant_self_report', content });
          } else if (event.type === 'step/end' && pending.size === 0 && fragments.size === 0) {
            const tokens = Math.ceil(JSON.stringify(selected).length / 3);
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
        result.ranges.push({ sessionId: id, start: progress.cursor, through, observed });
        if (!stopped && fragments.size) result.blocked.push({ sessionId: id, reason: 'An observed Inbox message has unread fragments.' });
        if (!stopped && pending.size) result.blocked.push({ sessionId: id, reason: 'Open tool calls remain beyond the safe step boundary.' });
      } catch (error) { result.blocked.push({ sessionId: id, reason: String(error) }); }
    }
    return result;
  }
  /** Resolve only a report's direct native child, retaining paired results as primary evidence. */
  private async childEvidence(parentId: string, childId: string) {
    const id = SessionId(childId); const live = this.ctx.sessions.get(id);
    if (live && !await this.ctx.sessions.flush(live)) throw new Error('Child report lacks durable tool evidence.');
    using observation = await this.ctx.sessionQuery.observeSession(id, {projectionMode:'none'});
    if (observation.header.parentSession !== parentId || observation.header.origin !== 'subagent') throw new Error('Report is not from a verified direct descendant.');
    const own = observation.events.slice(observation.inheritedEventCount);
    const end = own.findLast(event => event.type === 'step/end')?.seq ?? -1;
    const cut = own.filter(event => event.seq <= end);
    if (observation.source === 'live') {
      if (!live || this.ctx.sessions.get(id) !== live || !await this.ctx.sessions.flush(live)) throw new Error('Child evidence cut was not certified.');
    } else if (!observation.revision) throw new Error('Child evidence has no durable revision.');
    const calls = new Map<string, {seq: number; name: string; arguments: string}>();
    const events: unknown[] = [];
    for (const event of cut) {
      if (typeof event.surfaceOp === 'object' && event.surfaceOp.op === 'replace') continue;
      if (event.type === 'tool/call') {
        if (!excludedTools.has(event.data.name) && !/\.nanoassistant\/(?:memory|maintenance)/.test(event.data.arguments)) calls.set(event.data.callId, {seq:event.seq,name:event.data.name,arguments:event.data.arguments});
      } else if (event.type === 'tool/result') {
        const call = calls.get(event.data.message.toolCallId);
        if (call) { events.push({call, resultSeq:event.seq, result:event.data.message}); calls.delete(event.data.message.toolCallId); }
      }
    }
    return events.length ? {type:'child_tool_evidence',sessionId:id,parentId,through:end,events} : undefined;
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
