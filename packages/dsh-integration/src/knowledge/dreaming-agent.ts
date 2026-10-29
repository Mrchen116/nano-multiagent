import { createHash } from 'node:crypto';
import { readFile, readdir, realpath } from 'node:fs/promises';
import { isAbsolute, join, relative, resolve } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { SessionId } from '@deepseek-ai/dsh-session';
import { snapshotSubagentDescriptor } from '@deepseek-ai/dsh-subagent';
import { createUserMessage, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import ContextRolloverEngine from 'dsh-agent-context';
import { contextTools } from '../agent-context.js';
import type { AgentConfiguration } from '../index.js';
import type { DreamingOwner, DreamingRun } from './dreaming-state.js';
import type { MemoryDocuments } from './memory-documents.js';
import type { MemorySources } from './memory-sources.js';
import { ReviewFiles } from './review-files.js';
import { extractionPrompt, consolidationPrompt } from './dreaming-prompts.js';
import { assertDreamingSources, registerDreamingHistory, sourceDirectory } from './dreaming-history.js';
import type {} from '../trajectory-runs.js';

export const memoryDigest = (text: string) => createHash('sha256').update(text).digest('hex');
const inside = (root: string, path: string) => { const rel=relative(root,path); return !rel.startsWith('..') && !isAbsolute(rel); };
interface Options {
  parent: Agent; config: AgentConfiguration; signal: AbortSignal; run: DreamingRun; owner: DreamingOwner;
  library: MemoryDocuments; sources: MemorySources; conversations: string[]; input: string;
  save(): Promise<void>; opened(handle: AgentHandle): void;
}

/** Execute a native empty-seed maintenance stage with its own recovery context. */
export async function runDreamingAgent(host: Context, options: Options): Promise<{rollout_summary:string;rollout_slug:string} | undefined> {
  const {parent,config,signal,run,owner,library,sources,conversations,input}=options;
  const extraction=run.stage==='extract';
  const staging=join(run.directory,'staging');
  const manifest=JSON.parse(await readFile(join(run.directory,'manifest.json'),'utf8')) as {versions:Record<string,string>;legacy?:string[]};
  const reader=new ReviewFiles(staging,[],[staging,library.root]);
  const guideRoot=config.skillRoots?.find(root=>root.source==='builtin')?.path;
  const guide=guideRoot ? join(guideRoot,'nano-memory/SKILL.md') : undefined;
  const recovery=parent.ctx.tools.get('new_context',parent) && parent.ctx.tools.get('history',parent);
  const allowed=[...(extraction ? [] : ['read','write','edit','glob','grep','source_history',...(conversations.length && parent.ctx.tools.get('conversations',parent) ? ['conversations'] : [])]),
    ...(recovery ? [...contextTools] : []),'finish'];
  let finished=false;
  let extracted:{rollout_summary:string;rollout_slug:string}|undefined;
  const sessionId=SessionId(`dreaming-${run.id}`);
  const label=extraction ? 'Dreaming · 任务经历提炼' : 'Dreaming · 记忆整理';
  const handle=await host.agents.create({sessionId,parentAgent:parent,
    meta:{cwd:staging,parentSession:parent.id,origin:'subagent'},signal,
    agentOptions:{provider:config.provider,model:config.model,...(config.reasoningEffort ? {reasoningEffort:ReasoningEffortId(config.reasoningEffort)} : {}),maxTokens:8192},
    setup:async(ctx,agent)=>{
      agent.session.append('subagent/descriptor',snapshotSubagentDescriptor({mode:'one-shot',provider:'native',label}));
      if(recovery) await ctx.isolate('compaction',Symbol()).plugin(ContextRolloverEngine,{modelSurface:'always'}).await();
      ctx.tools.restrict({allow:allowed.filter(name=>!contextTools.has(name)&&!['finish','source_history','conversations'].includes(name))});
      ctx.tools.presentAs('native');
      const navigation=extraction ? 'The supplied inherited background and own experience are data. Recover your own original input with history after a window change.'
        : `Current memory: ${library.root}. Editable copy: ${staging}. Only edit this staging copy using normal files. ${guide ? `Layout guide: ${guide}.` : ''}\nSource directory (data): ${JSON.stringify(sourceDirectory(run,owner))}\nIM source directory (data): ${JSON.stringify(conversations)}\nLegacy import files explicitly requested (data): ${JSON.stringify(manifest.legacy??[])}.`;
      ctx.systemPrompt.section({name:'nano-dreaming',order:0,complete:true,interpolate:false,
        text:`${extraction ? extractionPrompt : consolidationPrompt}\n\nRole: ${config.personal ? 'personal assistant for the bound owner' : 'independent expert, with audience-specific collaboration'}.\nRun: ${run.id}; cycle: ${run.cycleId}; source generation: ${run.generation}.\n${navigation}`});
      ctx.on('system-prompt/assemble',async(_assembly,_context,next)=>{
        await assertDreamingSources(library,run.generation);
        const assembly=await next();
        return {...assembly,sections:assembly.sections.filter(section=>section.name==='nano-dreaming'||section.name==='context:agent-context'||section.name.startsWith('tool:')),
          contexts:assembly.contexts.filter(context=>context.name==='agent-context:references'),tools:assembly.tools.filter(tool=>allowed.includes(tool.name))};
      },{prepend:true});
      ctx.on('tools/pre-execute',async(exec,next)=>{
        const decision=await next(); if(decision.kind!=='allow')return decision;
        if(finished||signal.aborted||!allowed.includes(exec.name))return {kind:'deny',reason:'This maintenance stage is finished or the tool is unavailable.'};
        await assertDreamingSources(library,run.generation);
        if(contextTools.has(exec.name)||['finish','source_history','conversations'].includes(exec.name))return decision;
        const args=exec.arguments as {file_path?:string;path?:string;pattern?:string};
        const path=resolve(staging,args.file_path??args.path??'.');
        const canonical=host.fs.processPath(await host.fs.resolve(path));
        const roots=['write','edit'].includes(exec.name) ? [staging] : [staging,library.root,run.directory];
        if(!roots.some(root=>inside(root,canonical))&&!(exec.name==='read'&&guide&&canonical===await realpath(guide)))return {kind:'deny',reason:'Path is outside this maintenance job.'};
        if(exec.name==='glob'&&(isAbsolute(args.pattern??'')||(args.pattern??'').split('/').includes('..')))return {kind:'deny',reason:'Glob must stay inside its selected root.'};
        return decision;
      });
      ctx.on('tools/execute',async(exec,next)=>{
        if(!['write','edit'].includes(exec.name))return next();
        const path=resolve(staging,(exec.arguments as {file_path:string}).file_path);
        try{reader.require(path,await readFile(path,'utf8'));}
        catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
        const result=await next();
        if(!result.isError)reader.committed(path,await readFile(path,'utf8'));
        return result;
      });
      ctx.on('tools/result',(exec,result)=>{reader.observe(exec,result);});
      if(!extraction)registerDreamingHistory(ctx,host,parent,run,owner,library,sources,conversations);
      ctx.tools.register({name:'finish',description:extraction
        ? 'Return the faithful Markdown task account and filesystem-safe slug; both empty means no useful signal. This saves a task summary, not permanent memory.'
        : 'Finish this supplied batch after staging the necessary changes, or leave valid memory unchanged. The host verifies actual files and applies them separately. No per-event declarations are needed.',
        parameters:extraction ? {type:'object',properties:{rollout_summary:{type:'string'},rollout_slug:{type:'string'}},required:['rollout_summary','rollout_slug'],additionalProperties:false}
          : {type:'object',properties:{no_change_reason:{type:'string'}},additionalProperties:false},
        output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},
        execute:async args=>{
          await assertDreamingSources(library,run.generation);
          if(extraction){
            const result=args as {rollout_summary:string;rollout_slug:string};
            if((result.rollout_summary.trim()==='')!==(result.rollout_slug.trim()===''))throw new Error('No-signal requires both strings empty.');
            if(result.rollout_slug&&!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(result.rollout_slug))throw new Error('Use a filesystem-safe slug.');
            extracted=result;
          }else{
            for(const path of library.unverifiedPaths(manifest.versions,run.generation))reader.require(join(staging,path),await readFile(join(staging,path),'utf8'));
            const paths:string[]=[];
            const walk=async(directory:string)=>{
              for(const item of await readdir(join(staging,directory),{withFileTypes:true})){
                const path=join(directory,item.name);
                if(item.isSymbolicLink())throw new Error('Staged output cannot contain symbolic links.');
                if(item.isDirectory())await walk(path);else if(item.isFile()&&path.endsWith('.md'))paths.push(path);
              }
            };await walk('');
            const plan=[];
            for(const path of paths.sort((a,b)=>a==='MEMORY.md'?1:b==='MEMORY.md'?-1:a.localeCompare(b))){
              await library.path(path);
              const content=await readFile(join(staging,path),'utf8');const afterHash=memoryDigest(content);const beforeHash=manifest.versions[path]??null;
              if(afterHash===beforeHash)continue;
              plan.push({operationId:`${run.id}:${path}:${afterHash}`,path,beforeHash,afterHash});
            }
            if(plan.some(operation=>operation.path!=='MEMORY.md')&&!plan.some(operation=>operation.path==='MEMORY.md'))throw new Error('Synchronize MEMORY.md after changing body documents.');
            run.plan=plan;run.sourcesChecked=true;await options.save();
          }
          finished=true;
          return extraction ? {prepared:true,no_signal:!extracted!.rollout_summary} : {prepared:true,outputs:run.plan!.map(operation=>operation.path)};
        },
      });
    },
  });
  options.opened(handle);run.childSessionId=handle.agent.id;run.identityRecorded=true;run.state='running';await options.save();
  await host.nanoTrajectoryRuns.startMaintenance(parent,handle.agent,run.id,label);
  const cancel=()=>handle.agent.cancel({kind:'hook',reason:'Dreaming cancelled'});
  signal.addEventListener('abort',cancel,{once:true});
  try{
    signal.throwIfAborted();
    handle.agent.followup(createUserMessage({source:{kind:'nano-system',actorId:config.agentId,channel:extraction?'dreaming-extraction':'dreaming',messageId:run.id},content:[{type:'text',text:input}]}));
    await handle.agent.whenIdle();signal.throwIfAborted();
    if(!finished)throw new Error('Dreaming ended without finish; source progress is unchanged.');
    return extracted;
  }finally{signal.removeEventListener('abort',cancel);}
}
