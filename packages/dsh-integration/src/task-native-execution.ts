import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { SessionId } from '@deepseek-ai/dsh-session';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import type { TaskExecutionSnapshot } from '@nano/product-contracts';
import { inputEvidence } from './input-evidence.js';

const row=z.object({rootId:z.string(),graphId:z.string(),nodeId:z.string(),childId:z.string(),active:z.boolean()});
const domain=defineDomain({name:'nano_task_execution_refs',version:1,layout:'per-record',tables:{bindings:domainTable(row)}});
const key=(root:string,graph:string,node:string)=>Buffer.from(JSON.stringify([root,graph,node])).toString('base64url');
type Data=Record<string,unknown>;
/** Remember native references only; every responsibility decision rechecks canonical Tasks. */
export class NativeTaskExecutions {
 private readonly state;
 constructor(private readonly ctx:Context,private readonly snapshot:(rootId:string)=>Promise<TaskExecutionSnapshot>){
  this.state=ctx.storageDomain.open(domain);ctx.effect(()=>async()=>{(await this.state).close();});
  ctx.on('agent/pre-step',async({agent},next)=>{
   if(!await this.admitted(agent.id))return {kind:'reject'};
   return next();
  },{prepend:true});
  ctx.on('tools/pre-execute',async(exec,next)=>{
   if(exec.agent&&!await this.admitted(exec.agent.id))return {kind:'deny',reason:'The current canonical Task binding cannot authorize this execution. The root must coordinate it.'};
   return next();
  },{prepend:true});
 }
 /** Verify native identity and acceptance receipts before sending a canonical binding mutation. */
 async prepare(agent:Agent,args:Data):Promise<Data>{
  if(args.action!=='apply'||!Array.isArray(args.operations))return args;
  const bindings=args.operations.filter((op:Data)=>op.op==='bind_execution');
  if(!bindings.length)return args;
  if(agent.session.header.origin==='subagent')throw new Error('Only the product root may bind Task executions');
  const children=await this.ctx.subagents.listChildren(agent.id);
  const operations=[];
  for(const operation of args.operations){
   const op=operation as Data;
   if(op.op!=='bind_execution'){operations.push(op);continue;}
   if(!children.some(child=>child.id===op.child_id&&child.mode==='continuable'))throw new Error('Execution must be a real direct continuable child of this root');
   if(op.request_revision!==args.base_revision)throw new Error('Execution requires the current Task revision');
   if(op.input_receipt){
    using observation=await this.ctx.sessionQuery.observeSession(SessionId(String(op.child_id)));
    if(!inputEvidence(observation.events,String(op.input_receipt)).accepted)throw new Error('Correction receipt was not accepted by this child');
   }
   operations.push({...op,root_session_id:agent.id});
  }
  return {...args,operations};
 }
 /** Retain a recovery reference only after the canonical mutation actually committed. */
 async committed(root:Agent,args:Data,result:unknown):Promise<void>{
  const response=result as {ok?:boolean};
  if(response?.ok!==true||args.action!=='apply'||!Array.isArray(args.operations))return;
  const table=(await this.state).table('bindings');
  for(const op of args.operations as Data[])if(op.op==='bind_execution'){
   const id=key(root.id,String(args.graph_id),String(op.node_id));
   const prior=table.get(id);
   if(prior&&prior.childId!==op.child_id)await this.cancel(root,prior.childId);
   await table.put(id,{rootId:root.id,graphId:String(args.graph_id),nodeId:String(op.node_id),childId:String(op.child_id),active:true});
  }
  await this.running(root,await this.snapshot(root.id));
 }
 /** Revalidate at child boundaries, including cold restore, without trusting cached active flags. */
 private async admitted(childId:string):Promise<boolean>{
  const table=(await this.state).table('bindings');
  const rows=[...table.entries()].filter(([,value])=>value.childId===childId);
  if(!rows.length)return true;
  let allowed=false;
  for(const [id,ref] of rows){
   if(!ref.active)continue;
   let snapshot:TaskExecutionSnapshot;
   try{snapshot=await this.snapshot(ref.rootId);}catch{continue;}
   if(snapshot.kind==='unavailable')continue;
   const task=snapshot.tasks.find(item=>item.graph_id===ref.graphId&&item.node_id===ref.nodeId);
   const current=task?.status==='doing'&&task.execution?.child_id===childId&&task.execution.root_session_id===ref.rootId;
   if(current)allowed=true;
   else await table.put(id,{...ref,active:false});
  }
  return allowed;
 }
 /** Reconcile remembered native references and report only demonstrably running executions. */
 async running(root:Agent,snapshot:TaskExecutionSnapshot):Promise<Set<string>>{
  const running=new Set<string>();if(snapshot.kind==='unavailable')return running;
  const table=(await this.state).table('bindings');
  for(const [id,ref] of table.entries()){if(ref.rootId!==root.id||!ref.active)continue;
   const task=snapshot.tasks.find(task=>task.graph_id===ref.graphId&&task.node_id===ref.nodeId);
   if(!task||task.status!=='doing'||task.execution?.child_id!==ref.childId||task.execution?.root_session_id!==root.id){
    await table.put(id,{...ref,active:false});await this.cancel(root,ref.childId);
   }
  }
  const children=await this.ctx.subagents.listChildren(root.id);
  for(const task of snapshot.tasks){
   const ref=task.execution;
   if(task.status!=='doing'||!ref||ref.root_session_id!==root.id||ref.needs_coordination)continue;
   if(!children.some(child=>child.id===ref.child_id&&child.mode==='continuable'))continue;
   // A cold or unknown native state is coordination work, never a reason to suppress it.
   if(this.ctx.agents.get(SessionId(ref.child_id))?.status==='running')running.add(`${task.graph_id}/${task.node_id}`);
  }
  return running;
 }
 /** Stop only native executions actually bound to this root's Tasks. */
 async stop(root:Agent):Promise<void>{
  const table=(await this.state).table('bindings');
  for(const [id,ref] of table.entries())if(ref.rootId===root.id&&ref.active){
   await table.put(id,{...ref,active:false});await this.cancel(root,ref.childId);
  }
 }
 private async cancel(root:Agent,childId:string):Promise<void>{
  const child=SessionId(childId);
  if(!(await this.ctx.subagents.listChildren(root.id)).some(item=>item.id===child&&item.mode==='continuable'))return;
  this.ctx.subagents.interrupt(child,{kind:'ancestor',agent:root});
  const live=this.ctx.agents.get(child);if(live){live.cancel({kind:'hook',reason:'Canonical Task execution was withdrawn'});await live.whenIdle();}
  await this.ctx.subagents.drainContinuableChildren(root,[child]);
 }
}
