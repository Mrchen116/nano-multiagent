import type {AgentConfiguration,RuntimePort} from '@nano/product-contracts';
import type {NodeStore} from './store.js';
export interface ScheduleDeletionIntent {
 operationId:string;agentId:string;sessionId:string;scheduleId:string;title:string;
 actor:{kind:'user'|'agent';id:string};phase:'pending'|'deleted';deletedAt?:string;
 changeInputId:string;repairInputId:string;changeNotified:boolean;repairNotified:boolean;
}
interface Identity {operationId:string;agentId:string;scheduleId:string;actor:ScheduleDeletionIntent['actor'];sessionId?:string}
interface Options {
 ownerId:string;agents:AgentConfiguration[];store:NodeStore;runtime:RuntimePort;
 repair(intent:ScheduleDeletionIntent):Promise<void>;
 notify(intent:ScheduleDeletionIntent):Promise<void>;
 onError(error:unknown):void;
}
/** Durable intent for one authorized native deletion, not another Schedule catalog. */
export class ScheduleDeletions {
 private chain:Promise<unknown>=Promise.resolve();
 constructor(private readonly options:Options){}
 private exclusive<T>(action:()=>Promise<T>):Promise<T>{const next=this.chain.catch(()=>{}).then(action);this.chain=next;return next;}
 /** Save trusted operation identity before invoking the native owner. */
 delete(input:Identity):Promise<{id:string;deleted:boolean;code?:'schedule_not_found'}> {
  return this.exclusive(async()=>{
   if(!input.operationId||!this.options.agents.some(agent=>agent.agentId===input.agentId)||input.actor.kind==='user'&&input.actor.id!==this.options.ownerId||input.actor.kind==='agent'&&input.actor.id!==input.agentId)throw new Error('Invalid Schedule deletion authority');
   let intent=this.options.store.scheduleDeletions().find(item=>item.operationId===input.operationId);
   if(intent&&(intent.agentId!==input.agentId||intent.scheduleId!==input.scheduleId||intent.actor.kind!==input.actor.kind||intent.actor.id!==input.actor.id||input.sessionId!==undefined&&input.sessionId!==intent.sessionId))throw new Error('Schedule deletion identity conflict');
   if(!intent){
    const catalog=await this.options.runtime.request('schedule.command',{agentId:input.agentId,action:'jobs'}) as {id:string;sessionId:string;name:string}[];
    const schedule=catalog.find(item=>item.id===input.scheduleId&&(input.sessionId===undefined||item.sessionId===input.sessionId));
    if(!schedule)return {id:input.scheduleId,deleted:false,code:'schedule_not_found'};
    intent={operationId:input.operationId,agentId:input.agentId,sessionId:schedule.sessionId,scheduleId:schedule.id,title:schedule.name,actor:input.actor,phase:'pending',changeInputId:'schedule-deleted:'+input.operationId,repairInputId:'task-wait-repair:'+input.operationId,changeNotified:input.actor.kind!=='user',repairNotified:false};
    this.options.store.saveScheduleDeletion(intent);
   }
   await this.execute(intent);
   return {id:intent.scheduleId,deleted:true};
  });
 }
 private async execute(intent:ScheduleDeletionIntent):Promise<void>{
  if(intent.phase==='pending'){
   const catalog=await this.options.runtime.request('schedule.command',{agentId:intent.agentId,action:'jobs'}) as {id:string;sessionId:string}[];
   if(catalog.some(item=>item.id===intent.scheduleId&&item.sessionId===intent.sessionId)){
    const result=await this.options.runtime.request('schedule.command',{agentId:intent.agentId,sessionId:intent.sessionId,action:'delete',args:{id:intent.scheduleId}}) as {deleted?:boolean};
    if(!result.deleted){
     const current=await this.options.runtime.request('schedule.command',{agentId:intent.agentId,action:'jobs'}) as {id:string}[];
     if(current.some(item=>item.id===intent.scheduleId))throw new Error('Native Schedule deletion is unconfirmed');
    }
   }
   intent.phase='deleted';intent.deletedAt=new Date().toISOString();this.options.store.saveScheduleDeletion(intent);
  }
  // The two receipts are independent. A crash retries their stable native IDs.
  if(!intent.changeNotified)try{await this.options.notify(intent);intent.changeNotified=true;this.options.store.saveScheduleDeletion(intent);}catch(error){this.options.onError(error);}
  if(!intent.repairNotified)try{await this.options.repair(intent);intent.repairNotified=true;this.options.store.saveScheduleDeletion(intent);}catch(error){this.options.onError(error);}
 }
 /** Reconcile pending deletion and each unfinished notification after runtime recovery. */
 recover(agentIds:string[]):Promise<void>{return this.exclusive(async()=>{for(const intent of this.options.store.scheduleDeletions())if(agentIds.includes(intent.agentId)&&(!intent.changeNotified||!intent.repairNotified||intent.phase==='pending'))await this.execute(intent);});}
}
