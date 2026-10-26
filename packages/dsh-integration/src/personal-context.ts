import { scheduleRealm } from './features/cron.js';
import type {} from '@deepseek-ai/dsh-schedule';
import type { Context } from '@deepseek-ai/cordis';
import type {} from './knowledge/runtime.js';
import type {} from './product-bridge.js';

const taskRef = {type:'object' as const,properties:{graph_id:{type:'string' as const},node_id:{type:'string' as const}},required:['graph_id','node_id'],additionalProperties:false};
/** Register optional, root-private discovery tools; neither consumes the Inbox. */
export function registerTools(ctx: Context, agentId: string): void {
  ctx.tools.register({name:'personal_context',description:'Query current private memory, permitted IM sources, canonical Tasks and attention together. Coverage and cursors are independent; complete means only the reported scope. No Inbox acknowledgement. Read all relevant pages before proposing proactive work.',
    parameters:{type:'object',properties:{query:{type:'string'},conversation_ids:{type:'array',items:{type:'string'}},task_refs:{type:'array',items:taskRef},cursor:{type:'string'},memory_cursor:{type:'string'},limit:{type:'integer',minimum:1,maximum:100}},additionalProperties:false},
    output:{schema:{type:'object',additionalProperties:true},render:(_a,v)=>[{type:'text',text:JSON.stringify(v)}]},
    execute:async(args,exec)=>{
      const a=args as {query?:string;memory_cursor?:string;limit?:number};
      const memory=ctx.nanoKnowledge.personalMemory(exec.agent!);
      if(!memory||!ctx.nanoKnowledge.memoryConsumer(exec.agent!))throw new Error('Private context requires the root PA');
      const sources=await ctx.nanoProduct.call('personal_context',args,exec) as Record<string,unknown>;
      const records=await memory.search({action:'search',query:a.query,cursor:a.memory_cursor,limit:a.limit});
      const skills=await exec.agent!.ctx.get('skills')!.list({scope:exec.agent!,cwd:exec.agent!.session.header.cwd,signal:exec.signal});
      return {...sources,memory:records,capabilities:{tools:ctx.tools.schemas(exec.agent!).map(tool=>tool.name),skills:skills.map(skill=>skill.name),external_connections:'unknown'}};
    }});
  ctx.tools.register({name:'personal_attention',description:'Persist a private opportunity or reminder candidate, not an executable Task. Upsert needs source references and a complete fresh personal_context receipt before notification. Versioned feedback needs the original owner message. Snooze requires a real native schedule receipt; pending is not scheduled. Settings never expand permissions.',
    parameters:{type:'object',properties:{action:{type:'string',enum:['list','get','upsert','snooze','dismiss','resolve','link','settings']},id:{type:'string'},expected_revision:{type:'integer'},source_refs:{type:'array',items:{type:'string'}},query_receipt_id:{type:'string'},kind:{type:'string'},topic:{type:'string'},why_now:{type:'string'},next_step:{type:'string'},prepared_result_refs:{type:'array',items:{type:'string'}},canonical_task_ref:taskRef,idempotency_key:{type:'string'},owner_instruction_id:{type:'string'},snoozed_until:{type:'string'},settings:{type:'object',additionalProperties:true},status:{type:'string'},limit:{type:'integer'}},required:['action'],additionalProperties:false},
    output:{schema:{type:'object',additionalProperties:true},render:(_a,v)=>[{type:'text',text:JSON.stringify(v)}]},
    execute:async(args,exec)=>{
      const result=await ctx.nanoProduct.call('personal_attention',{...(args as object),exploration_batch_id:`${exec.agent!.id}:${exec.agent!.session.snapshotEvents().findLast(e=>e.type==='turn/start')?.seq??0}`},exec) as Record<string,unknown>;
      if((args as {action:string}).action!=='snooze'||result.schedule_status==='scheduled')return result;
      const schedule=ctx.isolate('schedule',scheduleRealm(agentId)).get('schedule');
      if(!schedule)throw new Error('Snooze remains pending: enable native schedule support before retrying.');
      const title=`Attention ${result.id} revision ${result.revision}`;
      const existing=(await schedule.list({sessionId:exec.agent!.session.id})).find(item=>item.title===title);
      const saved=existing??await schedule.create(exec.agent!.session.id,{title,at:String(result.snoozed_until),prompt:`Recheck private attention ${result.id}. Query fresh sources and Task status; respect quiet hours and notification receipts. A snooze wake is not new permission.`},exec.signal);
      return ctx.nanoProduct.call('pa.attention.snooze.complete',{id:result.id,expected_revision:result.revision,schedule_id:saved.id,scheduled_at:saved.scheduledAt},exec);
    }});
}
