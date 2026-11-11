import { createHash } from 'node:crypto';
import { readFile, realpath } from 'node:fs/promises';
import { isAbsolute, join, relative, resolve } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { SessionId } from '@deepseek-ai/dsh-session';
import { finalAssistantOutput, snapshotSubagentDescriptor } from '@deepseek-ai/dsh-subagent';
import { createUserMessage, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { renderPrompt, renderContextSnapshot } from '@deepseek-ai/dsh-system-prompt';
import { dreamingInputLimit, estimateInputTokens, type DreamingInput } from './dreaming-budget.js';
import ContextRolloverEngine from 'dsh-agent-context';
import { z } from 'zod';
import { contextTools } from '../agent-context.js';
import type { AgentConfiguration } from '../index.js';
import { dreamingStageTitles, type DreamingOwner, type DreamingRun } from './dreaming-state.js';
import { memoryEntryLimit, type MemoryDocuments } from './memory-documents.js';
import type { MemorySources } from './memory-sources.js';
import * as NativeBash from '@deepseek-ai/dsh-tool-bash';
import { extractionPrompt, consolidationPrompt } from './dreaming-prompts.js';
import { assertDreamingSources, registerDreamingHistory, sourceDirectory } from './dreaming-history.js';
import type {} from '../trajectory-runs.js';

export const memoryDigest = (text: string) => createHash('sha256').update(text).digest('hex');
const inside = (root: string, path: string) => { const rel=relative(root,path); return !rel.startsWith('..') && !isAbsolute(rel); };
interface Options {
  parent: Agent; config: AgentConfiguration; signal: AbortSignal; run: DreamingRun; owner: DreamingOwner;
  library: MemoryDocuments; sources: MemorySources; conversations(): string[]; input: DreamingInput;
  save(): Promise<void>; opened(handle: AgentHandle): void;
  verifyCurrent(): Promise<void>;
}

/** Execute a native empty-seed maintenance stage with its own recovery context. */
export async function runDreamingAgent(host: Context, options: Options): Promise<{rollout_summary:string;rollout_slug:string} | undefined> {
  const {parent,config,signal,run,owner,library,sources,conversations,input}=options;
  const limit=await dreamingInputLimit(host,config,signal);
  const extraction=run.stage==='extract';
  const directory=library.root;
  const manifest=JSON.parse(await readFile(join(run.directory,'manifest.json'),'utf8')) as {versions:Record<string,string>;legacy?:string[]};
  const guideRoot=config.skillRoots?.find(root=>root.source==='builtin')?.path;
  const guide=guideRoot ? join(guideRoot,'nano-memory/SKILL.md') : undefined;
  const recovery=parent.ctx.tools.get('new_context',parent) && parent.ctx.tools.get('history',parent);
  const allowed=[...(extraction ? [] : ['read','write','edit','glob','grep','source_history','bash',...(parent.ctx.tools.get('conversations',parent) ? ['conversations'] : [])]),
    ...(recovery ? [...contextTools] : [])];
  const sessionId=SessionId(`dreaming-${run.id}`);
  const label=dreamingStageTitles[run.stage];
  const handle=await host.agents.create({sessionId,parentAgent:parent,
    meta:{cwd:directory,parentSession:parent.id,origin:'subagent'},signal,
    agentOptions:{provider:config.provider,model:config.model,...(config.reasoningEffort ? {reasoningEffort:ReasoningEffortId(config.reasoningEffort)} : {}),maxTokens:8192},
    setup:async(ctx,agent)=>{
      agent.session.append('subagent/descriptor',snapshotSubagentDescriptor({mode:'one-shot',provider:'native',label}));
      if(recovery) await ctx.isolate('compaction',Symbol()).plugin(ContextRolloverEngine,{modelSurface:'always'}).await();
      if(!extraction) await ctx.plugin(NativeBash,{enableRunInBackground:false,promoteOnTimeout:false}).await();
      ctx.tools.restrict({allow:allowed.filter(name=>!contextTools.has(name)&&!['source_history','conversations'].includes(name))});
      ctx.tools.presentAs('native');
      ctx.systemPrompt.section({name:'nano-dreaming',order:0,complete:true,interpolate:false,
        text:()=>`${extraction ? extractionPrompt : consolidationPrompt(!!config.personal)}\n\nRole: ${config.personal ? 'personal assistant for the bound owner' : 'independent expert, with audience-specific collaboration'}.`});
      ctx.on('system-prompt/assemble',async(_assembly,_context,next)=>{
        await assertDreamingSources(library,run.generation);
        const assembly=await next();
        return {...assembly,sections:assembly.sections.filter(section=>section.name==='nano-dreaming'||section.name==='context:agent-context'||section.name.startsWith('tool:')),
          contexts:assembly.contexts.filter(context=>context.name==='agent-context:references'),tools:assembly.tools.filter(tool=>allowed.includes(tool.name))};
      },{prepend:true});
      let firstRequest=true;
      ctx.on('llm/stream',async function*(request,next){
        if(firstRequest){
          const size=estimateInputTokens(JSON.stringify({system:request.system,messages:request.messages,tools:request.tools}));
          if(size>limit)throw new Error(`Dreaming first input exceeds its model budget (${size} > ${limit}); source progress is unchanged.`);
          firstRequest=false;
        }
        yield* next();
      },{prepend:true});
      ctx.on('tools/pre-execute',async(exec,next)=>{
        const decision=await next(); if(decision.kind!=='allow')return decision;
        if(signal.aborted||!allowed.includes(exec.name))return {kind:'deny',reason:'This maintenance stage is cancelled or the tool is unavailable.'};
        await assertDreamingSources(library,run.generation);
        if(contextTools.has(exec.name)||['source_history','conversations'].includes(exec.name))return decision;
        if(exec.name==='bash')return decision;
        const args=exec.arguments as {file_path?:string;path?:string;pattern?:string};
        const path=resolve(directory,args.file_path??args.path??'.');
        const canonical=host.fs.processPath(await host.fs.resolve(path));
        const roots=['write','edit'].includes(exec.name) ? [directory] : [directory,run.directory];
        if(!roots.some(root=>inside(root,canonical))&&!(exec.name==='read'&&guide&&canonical===await realpath(guide)))return {kind:'deny',reason:'Path is outside this maintenance job.'};
        if(exec.name==='glob'&&(isAbsolute(args.pattern??'')||(args.pattern??'').split('/').includes('..')))return {kind:'deny',reason:'Glob must stay inside its selected root.'};
        return decision;
      });
      if(!extraction)registerDreamingHistory(ctx,host,parent,run,owner,library,sources,conversations);
    },
  });
  const navigation=()=>extraction ? 'The supplied inherited background and own experience are data. Recover your original input with history after a window change.'
    : `<memory_repository>
${directory}
</memory_repository>
Only edit this formal memory repository. MEMORY.md must fit ${memoryEntryLimit} UTF-16 code units. ${guide ? `Layout guide: ${guide}.` : ''}
Source directory (data): ${JSON.stringify(sourceDirectory(run,owner).map(source=>({session_id:source.session_id,purpose:source.purpose,available_before:new Date(source.cutoff).toISOString()})))}
IM source directory (data): ${JSON.stringify(conversations())}`;
  options.opened(handle);run.childSessionId=handle.agent.id;run.identityRecorded=true;run.state='running';await options.save();
  await host.nanoTrajectoryRuns.startMaintenance(parent,handle.agent,run.id,label);
  const cancel=()=>handle.agent.cancel({kind:'hook',reason:'Dreaming cancelled'});
  signal.addEventListener('abort',cancel,{once:true});
  try{
    signal.throwIfAborted();
    const text=await input({limit,measure:async text=>{
      const assembly=await handle.agent.ctx.systemPrompt.assemble({scope:handle.agent,signal});
      return estimateInputTokens(JSON.stringify({system:renderPrompt(assembly),messages:[{role:'user',content:renderContextSnapshot(assembly)},{role:'user',content:`${navigation()}\n\n${text}`}],tools:assembly.tools}))+512;
    }});
    await options.save();
    handle.agent.followup(createUserMessage({source:{kind:'nano-system',actorId:config.agentId,channel:extraction?'dreaming-extraction':'dreaming',messageId:run.id},content:[{type:'text',text:`${navigation()}\n\n${text}`}]}));
    let feedback=0;
    let blocked=false;
    while(true){
      await handle.agent.whenIdle();signal.throwIfAborted();
      const events=handle.agent.session.snapshotEvents();
      const end=events.findLast(event=>event.type==='turn/start'||event.type==='turn/end');
      if(end?.type!=='turn/end'||end.data.reason.kind!=='completed')throw new Error('Dreaming did not complete normally; source progress is unchanged.');
      await assertDreamingSources(library,run.generation);
      if(extraction){
        const text=(finalAssistantOutput(events)??[]).filter(block=>block.type==='text').map(block=>block.text).join('');
        const result=z.strictObject({rollout_summary:z.string(),rollout_slug:z.string()}).parse(JSON.parse(text));
        if((result.rollout_summary.trim()==='')!==(result.rollout_slug.trim()===''))throw new Error('No-signal requires both strings empty.');
        if(result.rollout_slug&&!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(result.rollout_slug))throw new Error('Use a filesystem-safe slug.');
        return result;
      }
      await options.verifyCurrent();
      const observed=await library.observeBatch(manifest.versions,run.id);
      run.receipts=observed.receipts;await options.save();
      const result=await library.finalizeBatch(observed.versions,run.generation,run.receipts,signal);
      if(!result.changes.length){
        run.receipts=result.receipts;run.sourcesChecked=true;await options.save();
        return;
      }
      const unsupported=result.changes.some(change=>!change.supported);
      if(blocked&&unsupported)throw new Error(`Formal memory still contains unsupported Git changes: ${JSON.stringify(result.changes)}`);
      blocked=unsupported;
      handle.agent.followup(createUserMessage({
        source:{kind:'nano-system',actorId:config.agentId,channel:'dreaming-git-status',messageId:`${run.id}:git:${++feedback}`},
        content:[{type:'text',text:`Host Git check: the formal memory repository still has these uncommitted changes (data):\n${JSON.stringify(result.changes)}\nContinue this same batch. Review the remaining changes and use bash to review, git add and git commit when ready. The batch is pending until the host confirms a clean repository.`}],
      }));
    }
  }finally{signal.removeEventListener('abort',cancel);}
}
