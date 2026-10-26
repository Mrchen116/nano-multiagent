import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { defineDomain,domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import { scheduleEvidence } from './schedule-evidence.js';
import { inputEvidence } from './input-evidence.js';
import { SessionId } from '@deepseek-ai/dsh-session';
import type { UserMessage } from '@deepseek-ai/dsh-llm';

const domain=defineDomain({name:'nano_personal_schedule_sources',version:1,layout:'per-record',tables:{sources:domainTable(z.object({sessionId:z.string(),sourceMessageIds:z.array(z.string()),ownerUi:z.boolean().optional()}))}});
const delegationDomain=defineDomain({name:'nano_personal_delegation_sources',version:1,layout:'per-record',tables:{sources:domainTable(z.object({sessionId:z.string(),sourceMessageIds:z.array(z.string())}))}});
/** Bind later native schedule wakes to their actual creation input, never a model-supplied reason. */
export class PersonalDeliveryEvidence {
 private readonly state;
 private readonly delegations;
 constructor(private readonly ctx:Context,private readonly liveInputs:(agent:Agent)=>Promise<string[]>){
  this.state=ctx.storageDomain.open(domain);ctx.effect(()=>async()=>{await(await this.state).close();});
  this.delegations=ctx.storageDomain.open(delegationDomain);ctx.effect(()=>async()=>{await(await this.delegations).close();});
  ctx.on('tools/post-execute',async(exec,result,next)=>{
   const decision=await next();
   if(decision.kind!=='accept'||result.isError||!exec.agent)return decision;
   const args=exec.arguments as {agent_id?:string};
   const child=(result.value as {subagentId?:string})?.subagentId;
   if(exec.name==='subagent'&&child){
    const inputs=await liveInputs(exec.agent);
    if(inputs.length)await(await this.delegations).table('sources').put(child,{sessionId:exec.agent.id,sourceMessageIds:inputs});
   }
   if(exec.name==='interrupt_agent'&&args.agent_id)await(await this.delegations).table('sources').delete(args.agent_id);
   if(!['schedule_create','schedule_update'].includes(exec.name))return decision;
   const value=result.value as {id?:string};if(!value?.id)return decision;
   const inputs=await liveInputs(exec.agent);
   if(inputs.length)await(await this.state).table('sources').put(value.id,{sessionId:exec.agent.id,sourceMessageIds:inputs});
   return decision;
  });
 }
 /** Carry the original request only on an actual direct child's return in this turn.
  *
  * Args:
  *   agent: Bound parent whose native inbox consumed the child message.
  * Returns:
  *   Host-persisted request references; child text and arbitrary old messages grant nothing.
  */
 async childReturns(agent:Agent):Promise<{childId:string;sourceMessageIds:string[]}[]>{
  const events=agent.session.snapshotEvents(),turn=events.findLast(event=>event.type==='turn/start');
  if(!turn||turn.type!=='turn/start')return [];
  const children=await this.ctx.subagents.listChildren(agent.id),table=(await this.delegations).table('sources');
  const inputs=new Map<string,UserMessage>();
  for(const event of events){
   const messages=event.type==='agent/inbox/spliced'?event.data.inserted:event.type==='user/message'?[event.data]:[];
   for(const message of messages)if(message.source.kind==='agent-message'||message.source.kind==='subagent-settled')inputs.set(message.id,message);
  }
  const results=new Map<string,{childId:string;sourceMessageIds:string[]}>();
  for(const message of inputs.values()){
   if(inputEvidence(events,message.id).turn!==turn.data.turn)continue;
   if(message.source.kind!=='agent-message'&&message.source.kind!=='subagent-settled')continue;
   const childId=String(message.source.senderSessionId),source=table.get(childId);
   if(source?.sessionId!==agent.id||!children.some(child=>child.id===childId&&child.mode==='continuable'))continue;
   using child=await this.ctx.sessionQuery.observeSession(SessionId(childId));
   const last=child.events.findLast(event=>event.type==='turn/start'||event.type==='turn/end');
   if(last?.type==='turn/end'&&last.data.reason.kind==='aborted')continue;
   results.set(childId,{childId,sourceMessageIds:source.sourceMessageIds});
  }
  return [...results.values()];
 }
 /** Record a trusted owner UI schedule creation at the host command boundary. */
 async ownerCreated(sessionId:string,scheduleId:string):Promise<void>{await(await this.state).table('sources').put(scheduleId,{sessionId,sourceMessageIds:[],ownerUi:true});}
 /** Return only native schedule messages consumed in this exact turn. */
 async current(agent:Agent):Promise<{scheduleId:string;sourceMessageIds:string[];ownerUi?:boolean}[]>{
  const events=agent.session.snapshotEvents(),turn=events.findLast(e=>e.type==='turn/start');
  const table=(await this.state).table('sources');
  return scheduleEvidence(events).filter(wake=>turn?.type==='turn/start'&&wake.turn===turn.data.turn).flatMap(wake=>{
   const grant=table.get(wake.scheduleId);return grant?.sessionId===agent.id?[{scheduleId:wake.scheduleId,sourceMessageIds:grant.sourceMessageIds,...(grant.ownerUi?{ownerUi:true}:{})}]:[];
  });
 }
}
