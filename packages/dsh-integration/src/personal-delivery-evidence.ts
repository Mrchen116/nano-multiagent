import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { defineDomain,domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import { scheduleEvidence } from './schedule-evidence.js';

const domain=defineDomain({name:'nano_personal_schedule_sources',version:1,layout:'per-record',tables:{sources:domainTable(z.object({sessionId:z.string(),sourceMessageIds:z.array(z.string()),ownerUi:z.boolean().optional()}))}});
/** Bind later native schedule wakes to their actual creation input, never a model-supplied reason. */
export class PersonalDeliveryEvidence {
 private readonly state;
 constructor(ctx:Context,private readonly liveInputs:(agent:Agent)=>Promise<string[]>){
  this.state=ctx.storageDomain.open(domain);ctx.effect(()=>async()=>{await(await this.state).close();});
  ctx.on('tools/post-execute',async(exec,result,next)=>{
   const decision=await next();
   if(decision.kind!=='accept'||result.isError||!exec.agent||!['schedule_create','schedule_update'].includes(exec.name))return decision;
   const value=result.value as {id?:string};if(!value?.id)return decision;
   const inputs=await liveInputs(exec.agent);
   if(inputs.length)await(await this.state).table('sources').put(value.id,{sessionId:exec.agent.id,sourceMessageIds:inputs});
   return decision;
  });
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
