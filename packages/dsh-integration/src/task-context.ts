import type {Context} from '@deepseek-ai/cordis';
import type {Agent} from '@deepseek-ai/dsh-agent';
import {freezeMessage,MessageId} from '@deepseek-ai/dsh-llm';
import type {SessionBinding} from './index.js';
import type {RpcPeer} from './rpc.js';
interface Prepared {unavailable?:boolean;messages:{inputId:string;conversationId:string;humanControl?:Record<string,unknown>;content:{type:'text';text:string}[]}[];revoked:string[]}
/** Admit original product context only after a complete authoritative pre-step catch-up. */
export class TaskContextDriver {
  constructor(ctx:Context,options:{bindings:Map<string,SessionBinding>;peer:RpcPeer;availability(agent:Agent,available:boolean):void;lifecycleRevision(agentId:string):number}) {
    const identity=(agent:Agent)=>{const binding=options.bindings.get(agent.id)!;return {agentId:binding.agentId,sessionId:agent.id,ownerId:binding.ownerId};};
    const evidence=async(agent:Agent)=>{
      await ctx.sessions.flush(agent.session);
      let turn:number|undefined;
      return agent.session.snapshotEvents().flatMap(event=>{
        if(event.type==='turn/start')turn=event.data.turn;
        if(event.type==='turn/end')turn=undefined;
        return event.type==='user/message'&&event.data.source.kind==='nano-system'&&event.data.source.channel==='task-context'&&turn!==undefined
          ? [{inputId:event.data.id,content:event.data.content,turn,consumedSeq:event.seq}]:[];
      });
    };
    const preparations=new WeakMap<Agent,{prepared:Prepared;consumed:Set<string>}>();
    ctx.on('system-prompt/assemble',async(_assembly,context,next)=>{
      const agent=context.agent??context.scope as Agent|undefined;
      if(!agent||!context.signal||!options.bindings.has(agent.id))return next();
      preparations.delete(agent);
      const consumedEvidence=await evidence(agent);
      const prepared=await options.peer.request('product.task_context.prepare',{...identity(agent),evidence:consumedEvidence}) as Prepared;
      context.signal.throwIfAborted();
      // Source eligibility must be current before native Memory/context providers render.
      options.availability(agent,!prepared.unavailable);
      preparations.set(agent,{prepared,consumed:new Set(consumedEvidence.map(item=>item.inputId))});
      return next();
    },{prepend:true});
    ctx.on('agent/pre-step',async({agent,messages,signal},next)=>{
      if(!options.bindings.has(agent.id))return next();
      const current=identity(agent);
      const {prepared,consumed}=preparations.get(agent)!;
      preparations.delete(agent);
      signal.throwIfAborted();
      const revoked=new Set(prepared.revoked);
      // Remove from both the public queue and this already-claimed batch. Removing
      // only the inbox misses native candidates claimed before source revocation.
      for(const id of revoked)agent.inbox.remove(MessageId(id));
      messages.splice(0,messages.length,...messages.filter(message=>!revoked.has(message.id)));
      if(prepared.unavailable){
        const independent=(message:typeof messages[number])=>message.source.kind!=='nano-system'||!message.source.channel.startsWith('task-');
        messages.splice(0,messages.length,...messages.filter(independent));
        const events=agent.session.snapshotEvents(),start=events.findLastIndex(event=>event.type==='turn/start');
        const priorIndependent=events.slice(start).some(event=>event.type==='user/message'&&independent(event.data));
        if(!messages.length&&!priorIndependent)return {kind:'reject'};
      }
      for(const message of prepared.messages)if(!consumed.has(message.inputId)&&!messages.some(existing=>existing.id===message.inputId)) {
        agent.inbox.remove(MessageId(message.inputId));
        messages.push(freezeMessage({id:MessageId(message.inputId),role:'user',source:{kind:'nano-system',channel:'task-context',actorId:current.agentId,messageId:message.inputId,conversationId:message.conversationId,...(message.humanControl?{humanTaskControl:message.humanControl}:{}),lifecycle_revision:options.lifecycleRevision(current.agentId)},content:message.content}));
      }
      await ctx.sessions.flush(agent.session);
      return next();
    },{prepend:true});
    ctx.on('agent/turn-stopping',async({agent})=>{
      if(options.bindings.has(agent.id))await options.peer.request('product.task_context.commit',{...identity(agent),evidence:await evidence(agent)});
    });
  }
}
