import { createHash } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { createHistoryView, type HistoryQuery } from 'dsh-agent-context';
import type { DreamingOwner, DreamingRun } from './dreaming-state.js';
import type { MemoryDocuments } from './memory-documents.js';
import { MemorySources } from './memory-sources.js';
import { qualifiedEvents, safeBoundary } from './memory-source-view.js';
import type {} from '../product-bridge.js';

interface Query extends HistoryQuery {
  action: 'list_windows' | 'list_items' | 'search' | 'read'; session_id: string;
  item_id?: string; offset_chars?: number; limit_chars?: number;
}
interface SourceRange { session_id: string; root_session_id: string; parent_session_id?: string; baseline: number; through: number; cutoff: number; purpose: string }
const marker = (event: SessionEvent) => event.type.startsWith('compaction/');

/** Build an explicit source directory from host-owned cuts, never from model identities. */
export function sourceDirectory(run: DreamingRun, owner: DreamingOwner): SourceRange[] {
  const roots = Object.entries(run.target.roots).map(([id, cut]) => {
    const range = run.batch.ranges.find(item => item.sessionId === id);
    const page = run.batch.units.findLast(item => item.sessionId === id)?.page;
    return {session_id:id, root_session_id:id, baseline:owner.streams[id]!.baseline,
      through:run.batch.historyThrough?.[id] ?? (page ? run.batch.units.findLast(item => item.sessionId === id)!.through : range?.through ?? cut.through),
      cutoff:run.batch.cutoffs?.[id] ?? cut.time, purpose:'Global dialogue and already processed background'};
  });
  const children = run.summaries.map(summary => ({session_id:summary.sessionId, root_session_id:summary.rootSessionId,
    baseline:summary.baseline, through:summary.through,
    cutoff:run.batch.ranges.some(range => range.sessionId === summary.rootSessionId && (range.through > range.start || range.continuation))
      ? run.batch.cutoffs![summary.rootSessionId]! : run.target.children[summary.sessionId]!.time,
    purpose:'Original evidence for this task summary'}));
  return [...roots, ...children];
}

/** A source-policy change invalidates old tool results as well as future file publication. */
export async function assertDreamingSources(library: MemoryDocuments, generation: number): Promise<void> {
  const status = await library.status();
  if (status.sourcesPending || status.generation !== generation) throw new Error('Source eligibility changed; do not reuse prior source results or apply this batch.');
}

/** Register business-history recovery separately from the maintenance Agent's own history. */
export function registerDreamingHistory(ctx: Context, host: Context, parent: Agent, run: DreamingRun,
  owner: DreamingOwner, library: MemoryDocuments, sources: MemorySources, conversations: string[] | (()=>string[])) {
  const resolveScope=async(sessionId:string):Promise<SourceRange>=>{
    const directory=sourceDirectory(run,owner);
    const known=directory.find(item=>item.session_id===sessionId);if(known)return known;
    const chain:Array<{id:string;snapshot:Awaited<ReturnType<MemorySources['snapshot']>>}>=[];
    let id=sessionId;
    while(!directory.some(item=>item.session_id===id)){
      if(chain.some(item=>item.id===id))throw new Error('Invalid descendant lineage.');
      const snapshot=await sources.snapshot(id);
      if(snapshot.header.origin!=='subagent'||!snapshot.header.parentSession)throw new Error('Source session is outside the supplied directory.');
      chain.push({id,snapshot});id=snapshot.header.parentSession;
    }
    const ancestor=directory.find(item=>item.session_id===id)!;
    if(ancestor.session_id===ancestor.root_session_id)throw new Error('Only descendants of a supplied task summary may be expanded.');
    let parent=await sources.snapshot(ancestor.session_id);let scope=ancestor;
    for(const child of chain.reverse()){
      const relation=parent.events.findLast(event=>event.type==='subagent/catalog'&&event.data.childId===child.id&&event.data.mode!=='unknown'&&event.seq<=scope.through&&event.time<=scope.cutoff);
      if(relation?.type!=='subagent/catalog'||!Number.isFinite(relation.data.childCreatedAt))throw new Error('Descendant is not certified within the task cutoff.');
      const own=child.snapshot.events.slice(child.snapshot.inheritedEventCount);
      const cut=safeBoundary(own,scope.cutoff);
      const baseline=relation.data.childCreatedAt>=owner.activationAt?child.snapshot.inheritedEventCount-1:safeBoundary(own,owner.activationAt).through;
      scope={session_id:child.id,root_session_id:scope.root_session_id,parent_session_id:parent.header.id,baseline,through:cut.through,cutoff:scope.cutoff,purpose:'Original evidence from a trusted task descendant'};
      parent=child.snapshot;
    }
    return scope;
  };
  ctx.tools.register({name:'source_history',
    description:'Read original business evidence from the supplied source directory, including active and older windows and returned trusted task descendants. This is distinct from history, which restores your own maintenance work. Use list_windows/list_items/search to find original window_id/item_id; read supports Unicode continuation. Current source permissions and the frozen batch boundary apply before search/pagination. Missing or omitted records are unknown, never proof of completion.',
    parameters:{type:'object',properties:{
      action:{enum:['list_windows','list_items','search','read']},session_id:{type:'string'},window_id:{type:'string'},item_id:{type:'string'},
      role:{type:'string'},tool_name:{type:'string'},query:{type:'string'},recent_first:{type:'boolean'},limit:{type:'integer',minimum:1,maximum:100},
      cursor:{type:'string'},max_chars_per_item:{type:'integer',minimum:1,maximum:20000},offset_chars:{type:'integer',minimum:0},limit_chars:{type:'integer',minimum:1,maximum:20000},
    },required:['action','session_id'],additionalProperties:false},
    output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},
    execute:async raw => {
      const args = raw as Query;
      await assertDreamingSources(library, run.generation);
      const scope = await resolveScope(args.session_id);
      const snapshot = await sources.snapshot(scope.session_id);
      if (scope.session_id === scope.root_session_id ? snapshot.header.origin === 'subagent'
        : snapshot.header.origin !== 'subagent' || snapshot.header.parentSession !== (scope.parent_session_id??scope.root_session_id)) throw new Error('Source identity changed.');
      const status = await library.status();
      const events = snapshot.events.filter(event => event.seq <= scope.through && event.time <= scope.cutoff &&
        (marker(event) || event.seq > Math.max(scope.baseline, snapshot.inheritedEventCount - 1)));
      const qualified = qualifiedEvents(events, {sources:status.sources});
      const view = createHistoryView(scope.session_id, qualified);
      const {action,session_id,window_id,item_id,offset_chars,limit_chars,cursor,...query} = args;
      const tokenScope = createHash('sha256').update(JSON.stringify({scope,generation:run.generation,action,window_id,query})).digest('hex');
      let innerCursor: string | undefined;
      if (cursor) {
        const decoded = JSON.parse(Buffer.from(cursor,'base64url').toString()) as {scope:string;cursor:string};
        if (decoded.scope !== tokenScope) throw new Error('Cursor belongs to a different source or query range.');
        innerCursor = decoded.cursor;
      }
      let result: Record<string,unknown>;
      if (action === 'read') {
        if (!window_id || !item_id) throw new Error('read requires returned window_id and item_id.');
        result = view.read(window_id,item_id,offset_chars,limit_chars);
      } else if (action === 'list_windows') result = view.listWindows({...query,cursor:innerCursor});
      else {
        if (action === 'search' && query.query === undefined) throw new Error('search requires query.');
        result = view.search({...query,window_id,cursor:innerCursor});
      }
      await assertDreamingSources(library, run.generation);
      if (typeof result.next_cursor === 'string') result.next_cursor = Buffer.from(JSON.stringify({scope:tokenScope,cursor:result.next_cursor})).toString('base64url');
      const descendants=scope.session_id===scope.root_session_id?[]:snapshot.events.flatMap(event=>event.type==='subagent/catalog'&&event.data.mode!=='unknown'&&event.seq<=scope.through&&event.time<=scope.cutoff?[{session_id:event.data.childId,purpose:'Task descendant; source_history validates its original evidence on access'}]:[]);
      return {session_id,...result,allowed_range:{session_id:scope.session_id,purpose:scope.purpose,available_before:new Date(scope.cutoff).toISOString()},descendants};
    },
  });
  const allowedConversations=()=>typeof conversations==='function'?conversations():conversations;
  if (!parent.ctx.tools.get('conversations',parent)) return;
  ctx.tools.register({name:'conversations',
    description:'Read-only IM evidence for this frozen memory batch: info/read/search only, using original conversation/message IDs from the supplied directory or evidence. info is current metadata. Results preserve real authors and participant/observer scope; omitted historical versions are unavailable. Does not consume Inbox or send/join/create anything.',
    parameters:{type:'object',properties:{action:{enum:['info','read','search']},target:{type:'string'},query:{type:'string'},keyword:{type:'string'},message_id:{type:'string'},before:{type:'string'},after:{type:'string'},cursor:{type:'string'},limit:{type:'integer',minimum:1,maximum:50}},required:['action','target'],additionalProperties:false},
    output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},
    execute:async (raw,exec) => {
      await assertDreamingSources(library, run.generation);
      const args = raw as {target:string;[key:string]:unknown};
      if (!allowedConversations().includes(args.target)) throw new Error('Conversation is outside this batch source directory.');
      const ranges = sourceDirectory(run,owner).filter(item => item.root_session_id === parent.id);
      const cutoff = Math.max(...ranges.map(item => item.cutoff));
      const result = await host.nanoProduct.call('memory.conversations',{...args,cutoff,afterTime:owner.activationAt},{...exec,agent:parent});
      await assertDreamingSources(library, run.generation);
      return result;
    },
  });
}
