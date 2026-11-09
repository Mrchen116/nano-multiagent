import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import {freezeMessage,MessageId} from '@deepseek-ai/dsh-llm';
import type {Session,SessionEvent} from '@deepseek-ai/dsh-session';
import {stripContextItemId} from 'dsh-agent-context';
import type {SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';

interface Prepared {
  unavailable?: boolean;
  unavailableInputs?: {inputId:string;conversationId:string}[];
  messages: {inputId:string;conversationId:string;humanControl?:Record<string,unknown>;content:{type:'text';text:string}[]}[];
  revoked: string[];
}
interface Evidence {
  inputId: string;
  content: ReturnType<typeof stripContextItemId>;
  turn: number;
  consumedSeq: number;
}
interface EvidenceCut {
  turn?: number;
  independent: boolean;
  cursor: number;
  pending: Map<number,Evidence>;
  starting?: SessionEvent[];
}
const taskOriginal = (message: {source:{kind:string;channel?:string}}) =>
  message.source.kind === 'nano-system' && message.source.channel === 'task-context';
const independent = (message: {source:{kind:string;channel?:string}}) =>
  message.source.kind !== 'nano-system' || !message.source.channel?.startsWith('task-');

function observeEvent(cut: EvidenceCut, event: SessionEvent) {
  if (event.seq <= cut.cursor) return;
  cut.cursor = event.seq;
  if (event.type === 'turn/start') {
    cut.turn = event.data.turn;
    cut.independent = false;
  }
  if (event.type === 'turn/end') cut.turn = undefined;
  if (event.type !== 'user/message') return;
  cut.independent ||= independent(event.data);
  if (cut.turn !== undefined && taskOriginal(event.data)) cut.pending.set(event.seq, {
    inputId: event.data.id, content: stripContextItemId(event.data.content), turn: cut.turn, consumedSeq: event.seq,
  });
}

/** Admit original product context only after a complete authoritative pre-step catch-up. */
export class TaskContextDriver {
  private readonly cuts = new WeakMap<Session,Promise<EvidenceCut>>();
  private readonly starting = new WeakMap<Session,EvidenceCut>();
  private readonly tails = new WeakMap<Session,Promise<EvidenceCut>>();
  private readonly liveIndependent = new WeakMap<Session,boolean>();

  constructor(private readonly ctx:Context,private readonly options:{
    bindings:Map<string,SessionBinding>;peer:RpcPeer;
    availability(agent:Agent,available:boolean,inputs:NonNullable<Prepared['unavailableInputs']>):void;
    lifecycleRevision(agentId:string):number;
  }) {
    const preparations = new WeakMap<Agent,{prepared:Prepared;cut?:EvidenceCut}>();
    ctx.on('session/event', (session, event) => {
      const cut = this.starting.get(session);
      if (cut && !cut.starting) {
        observeEvent(cut,event);
        return;
      }
      if (!options.bindings.has(session.id)) return;
      cut?.starting?.push(event);
      // Keep the live turn's authorization even if its first history read fails.
      if (event.type === 'turn/start') this.liveIndependent.set(session,false);
      if (event.type === 'user/message' && independent(event.data)) this.liveIndependent.set(session,true);
    });
    ctx.on('system-prompt/assemble', async (_assembly,context,next) => {
      const agent = context.agent ?? context.scope as Agent | undefined;
      if (!agent || !context.signal || !options.bindings.has(agent.id)) return next();
      preparations.delete(agent);
      let cut: EvidenceCut | undefined;
      try { cut = await this.reconcile(agent); } catch { /* Current authority can still identify withheld inputs. */ }
      const prepared = await options.peer.request('product.task_context.prepare',{
        ...this.identity(agent), evidenceReady: Boolean(cut),
      }) as Prepared;
      context.signal.throwIfAborted();
      if (!cut) {
        prepared.unavailable = true;
        prepared.messages = [];
      }
      options.availability(agent,!prepared.unavailable,prepared.unavailableInputs??[]);
      preparations.set(agent,{prepared,cut});
      return next();
    },{prepend:true});
    ctx.on('agent/pre-step',async ({agent,messages,signal},next) => {
      if (!options.bindings.has(agent.id)) return next();
      const current = this.identity(agent);
      const {prepared,cut} = preparations.get(agent)!;
      preparations.delete(agent);
      signal.throwIfAborted();
      const revoked = new Set(prepared.revoked);
      const pending = new Set(Array.from(cut?.pending.values() ?? [], item => item.inputId));
      const authorized = new Set(prepared.messages.map(message => message.inputId).filter(id => !pending.has(id)));
      // A passive original can already be claimed by the native step before the authority check.
      for (const id of revoked) agent.inbox.remove(MessageId(id));
      messages.splice(0,messages.length,...messages.filter(message =>
        !revoked.has(message.id) && (!taskOriginal(message) || authorized.has(message.id))));
      if (prepared.unavailable) {
        messages.splice(0,messages.length,...messages.filter(independent));
        if (!messages.length) {
          const observed = cut ?? this.starting.get(agent.session);
          if (!(observed?.independent ?? this.liveIndependent.get(agent.session))) return {kind:'reject'};
        }
      }
      for (const message of prepared.messages) if (authorized.has(message.inputId) && !messages.some(existing => existing.id === message.inputId)) {
        agent.inbox.remove(MessageId(message.inputId));
        messages.push(freezeMessage({id:MessageId(message.inputId),role:'user',
          source:{kind:'nano-system',channel:'task-context',actorId:current.agentId,messageId:message.inputId,
            conversationId:message.conversationId,...(message.humanControl?{humanTaskControl:message.humanControl}:{}),
            lifecycle_revision:options.lifecycleRevision(current.agentId)},content:message.content}));
      }
      await ctx.sessions.flush(agent.session);
      return next();
    },{prepend:true});
    ctx.on('agent/turn-stopping', async ({agent}) => {
      if (options.bindings.has(agent.id)) await this.reconcile(agent).catch(() => {});
    });
  }

  private identity(agent: Agent) {
    const binding = this.options.bindings.get(agent.id)!;
    return {agentId:binding.agentId,sessionId:agent.id,ownerId:binding.ownerId};
  }

  private readCut(session: Session): Promise<EvidenceCut> {
    const previous = this.cuts.get(session);
    if (previous) return previous;
    const cut: EvidenceCut = {cursor:-1,independent:false,pending:new Map(),starting:[]};
    this.starting.set(session,cut);
    const read = (async () => {
      using observed = await this.ctx.sessionQuery.observeSession(session.id,{projectionMode:'none'});
      for (let i=observed.inheritedEventCount; i<observed.events.length; i++) observeEvent(cut,observed.events[i]!);
      for (const event of cut.starting!) observeEvent(cut,event);
      cut.starting = undefined;
      return cut;
    })().catch(error => {
      this.cuts.delete(session);
      this.starting.delete(session);
      throw error;
    });
    this.cuts.set(session,read);
    return read;
  }

  /** Confirm flushed Task evidence before original admission or retiring a Session. */
  reconcile(agent: Agent): Promise<EvidenceCut> {
    const active = this.tails.get(agent.session);
    if (active) return active;
    const task = this.commit(agent).finally(() => this.tails.delete(agent.session));
    this.tails.set(agent.session,task);
    return task;
  }

  private async commit(agent: Agent): Promise<EvidenceCut> {
    const cut = await this.readCut(agent.session);
    if (!cut.pending.size) return cut;
    const through = cut.cursor;
    if (!await this.ctx.sessions.flush(agent.session)) throw new Error('Task evidence has no persistence barrier');
    let page: Evidence[] = [], bytes = 0;
    const send = async () => {
      const reply = await this.options.peer.request('product.task_context.commit',{...this.identity(agent),evidence:page}) as
        {confirmed?: {inputId:string;consumedSeq:number;status:'consumed'|'discarded'}[]} | null;
      const sent = new Map(page.map(item => [item.consumedSeq,item.inputId]));
      for (const item of reply?.confirmed ?? []) {
        if (sent.get(item.consumedSeq) === item.inputId) cut.pending.delete(item.consumedSeq);
      }
      page = [];
      bytes = 0;
    };
    for (const item of cut.pending.values()) {
      if (item.consumedSeq > through) break;
      const size = Buffer.byteLength(JSON.stringify(item));
      if (page.length && (page.length >= 64 || bytes + size > 256 * 1024)) await send();
      page.push(item);
      bytes += size;
    }
    if (page.length) await send();
    return cut;
  }
}
