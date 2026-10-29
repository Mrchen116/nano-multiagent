import { randomUUID } from 'node:crypto';
import { DEFAULT_DREAMING_SCHEDULE } from '@nano/product-contracts';
import { mkdir, readFile, writeFile, readdir, chmod, rm } from 'node:fs/promises';
import { join } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import { SessionId, SessionSeq, snapshotSessionEvent } from '@deepseek-ai/dsh-session';
import { snapshotSubagentDescriptor } from '@deepseek-ai/dsh-subagent';
import { createUserMessage, ToolCallId } from '@deepseek-ai/dsh-llm';
import type { AgentConfiguration, SessionBinding } from '../index.js';
import type { DocumentMemory } from './document-memory.js';
import { MemorySources, commitSourceRange, type ChildMaterial, type CycleTarget, type FrozenBatch } from './memory-sources.js';
import { dreamingDomain, type DreamingOwner, type DreamingRun, type TaskSummary } from './dreaming-state.js';
import type { MemoryDocuments } from './memory-documents.js';
import { atomicWrite } from './files.js';
import { runDreamingAgent, memoryDigest } from './dreaming-agent.js';
import { sourceConversations } from './memory-source-view.js';
import { assertDreamingSources } from './dreaming-history.js';
import type {} from '../product-bridge.js';
import type {} from '../trajectory-runs.js';

interface Options {
  configOf(agent: Agent): AgentConfiguration | undefined; configs: Map<string, AgentConfiguration>; bindings: Map<string, SessionBinding>;
  held?(agentId: string): boolean; notify(): void;
}
interface Active { automatic: boolean; controller: AbortController; promise: Promise<unknown>; handle?: AgentHandle }
const key = (id: string) => Buffer.from(id).toString('base64url');
const retryDelays = [300000, 1800000, 7200000];
const summaryKey = (agentId: string, sessionId: string) => key(`${agentId}:${sessionId}`);

/** Runs low-priority memory maintenance in a native empty-context execution. */
export class Dreaming {
  private readonly domain;
  private readonly sources: MemorySources;
  private readonly owners = new Map<string, Promise<DreamingOwner>>();
  private readonly active = new Map<string, Active>();
  private readonly lastActivity = new Map<string, number>();
  private readonly maintenance = new Set<string>();
  private foregroundRequests = 0;
  private stopped = false;
  private now = () => Date.now();
  private hostClock = false;
  private readonly timer: ReturnType<typeof setInterval>;
  constructor(private readonly ctx: Context, private readonly documents: DocumentMemory, private readonly options: Options) {
    this.domain = ctx.storageDomain.open(dreamingDomain); this.sources = new MemorySources(ctx, options.bindings);
    documents.run = (agent, requestRef, importLegacy) => this.start(agent, false, requestRef, importLegacy);
    ctx.on('agent/created', async ({ agent }) => {
      const binding = options.bindings.get(agent.id);
      const config = binding && [...options.configs.values()].find(config => config.agentId === binding.agentId);
      if (config?.knowledge?.memoryMode !== 'legacy' && config) {
        const owner = await this.owner(config);
        if (binding && !owner.streams[binding.sessionId]) {
          const baselines = await this.sources.baseline(config.agentId);
          owner.streams[binding.sessionId] = baselines[binding.sessionId]!;
          await this.saveOwner(config.agentId, owner);
        }
      }
    });
    ctx.on('session/event', (session, event) => {
      const binding = options.bindings.get(session.id);
      if (!binding) return;
      if (event.type === 'user/message' || event.type === 'tool/result') this.recordActivity(binding.agentId);
      if (event.type === 'step/end' && !this.hostClock) void this.tick(binding.agentId).catch(() => {});
    });
    const self = this;
    ctx.on('llm/stream', async function* (request, next) {
      const foreground = !self.maintenance.has(String(request.sessionId));
      if (foreground) self.foregroundRequests++;
      try { yield* next(); } finally { if (foreground) self.foregroundRequests--; }
    }, { prepend: true });
    this.timer = setInterval(() => { for (const config of new Set(options.configs.values())) void this.tick(config.agentId).catch(() => {}); }, 1000);
    this.timer.unref(); ctx.effect(() => () => clearInterval(this.timer));
  }
  /** Use a host-driven clock before initializing any owner.
   *
   * Args:
   *   now: Monotonic logical time in Unix milliseconds. The host must call tick explicitly.
   * Raises:
   *   Error: An owner has already been initialized.
   * Side Effects:
   *   Disables timer and completed-step admission for this isolated service instance.
   */
  useClock(now: () => number): void {
    if (this.owners.size) throw new Error('Install the maintenance clock before initializing owners.');
    this.now = now; this.hostClock = true; clearInterval(this.timer);
  }

  /** Record completed source activity without replaying historical business tools. */
  recordActivity(agentId: string, at = this.now()): void { this.lastActivity.set(agentId, at); }

  /** Return the earliest idle-owner admission time, or undefined when maintenance is disabled. */
  async nextAutomaticAt(agentId: string): Promise<number | undefined> {
    const config = this.configuration(agentId);
    if (this.stopped || !config || config.knowledge?.memoryMode === 'legacy' || config.features?.dreaming === false || this.options.held?.(agentId)) return;
    const timing = this.automaticTiming(config, await this.owner(config));
    return Math.max(timing.dueAt, timing.quietAt);
  }

  /** Wait only for work already admitted; never start an additional maintenance cycle. */
  async whenIdle(agentId: string): Promise<unknown> { return this.active.get(agentId)?.promise; }

  private automaticTiming(config: AgentConfiguration, owner: DreamingOwner) {
    const settings = config.knowledge?.dreaming;
    return {
      dueAt: Math.max(owner.retryAt ?? 0, (owner.lastSuccessAutomatic ?? owner.activationAt) + (settings?.intervalMs ?? DEFAULT_DREAMING_SCHEDULE.intervalMs)),
      quietAt: (this.lastActivity.get(config.agentId) ?? owner.activationAt) + (settings?.quietMs ?? DEFAULT_DREAMING_SCHEDULE.quietMs),
    };
  }

  get busy() { return this.active.size > 0; }
  private configuration(agentId: string) { return [...this.options.configs.values()].find(config => config.agentId === agentId); }
  private async owner(config: AgentConfiguration): Promise<DreamingOwner> {
    const existing = this.owners.get(config.agentId); if (existing) return existing;
    const promise = (async () => {
      const table = (await this.domain).table('owners'); const saved = table.get(key(config.agentId)); if (saved) {
        if (saved.protocol !== 2) throw new Error('Dreaming state needs the offline protocol-2 migration before maintenance can run.');
        return saved;
      }
      const library = await this.documents.forConfig(config);
      let imported: Partial<DreamingOwner> | undefined;
      try { imported = JSON.parse(await readFile(join(library.workspace, '.nanoassistant/maintenance/dreaming-state.json'), 'utf8')) as DreamingOwner; }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
      const owner: DreamingOwner = { protocol: 2, integrated: {}, activationAt: imported?.activationAt ?? this.now(), streams: imported?.streams ?? await this.sources.baseline(config.agentId), seen: [], rotation: 0, failures: 0 };
      await table.put(key(config.agentId), owner); return owner;
    })();
    this.owners.set(config.agentId, promise);
    try { return await promise; } catch (error) { this.owners.delete(config.agentId); throw error; }
  }
  private async saveOwner(agentId: string, owner: DreamingOwner) { await (await this.domain).table('owners').put(key(agentId), owner); }
  private async saveRun(run: DreamingRun) { await (await this.domain).table('runs').put(run.id, { ...run, batch: { ...run.batch, units: run.batch.units.map(unit => ({ ...unit, events: [] })) } }); this.options.notify(); }
  /** Automatic admission never reserves the root Agent for the model call. */
  async tick(agentId: string, now = this.now()): Promise<unknown> {
    const config = this.configuration(agentId);
    const active = this.active.get(agentId);
    if (active) {
      if (this.options.held?.(agentId) || config?.knowledge?.memoryMode === 'legacy' || active.automatic && config?.features?.dreaming === false) active.controller.abort();
      return;
    }
    if (this.stopped || !config || config.knowledge?.memoryMode === 'legacy' || config.features?.dreaming === false || this.options.held?.(agentId)) return;
    const parent = [...this.options.bindings.values()].filter(binding => binding.agentId === agentId).map(binding => this.ctx.agents.get(SessionId(binding.sessionId))).find(Boolean);
    if (!parent) return;
    const timing = this.automaticTiming(config, await this.owner(config));
    if (now < timing.dueAt) return;
    const quiet = now >= timing.quietAt;
    // A completed-step callback can admit work during a continuous turn, but only with spare provider capacity.
    if (this.foregroundRequests > 0 || !quiet && parent.status === 'idle') return;
    return this.start(parent, true);
  }
  private async refreshSources(parent: Agent, config: AgentConfiguration, signal: AbortSignal) {
    if (!config.personal) return;
    await this.documents.sourcesPending(config.agentId);
    await this.ctx.nanoProduct.call('memory.sources.refresh', {}, { agent: parent, signal, callId: ToolCallId(`dreaming-policy-${randomUUID()}`) });
  }
  /** Manually requested work bypasses automatic timing, not scope, budgets or lifecycle. */
  start(parent: Agent, automatic: boolean, _requestRef?: string, importLegacy = false): Promise<unknown> {
    const config = this.options.configOf(parent);
    if (!config || config.knowledge?.memoryMode === 'legacy' || this.stopped || this.options.held?.(config.agentId)) return Promise.reject(new Error('Document maintenance is not available.'));
    if (automatic && config.features?.dreaming === false) return Promise.reject(new Error('Automatic Dreaming is disabled.'));
    const prior = this.active.get(config.agentId); if (prior) return Promise.resolve({ accepted: false, reason: 'maintenance_already_running' });
    const required = ['read', 'write', 'edit', 'memory_maintenance'];
    const missing = required.filter(name => !parent.ctx.tools.get(name, parent));
    if (missing.length) return Promise.resolve({ accepted: false, reason: 'missing_tools', missing });
    const controller = new AbortController();
    const work: Active = { automatic, controller, promise: Promise.resolve() };
    this.active.set(config.agentId, work);
    work.promise = this.execute(parent, config, work, importLegacy).finally(() => this.active.delete(config.agentId));
    return work.promise;
  }

  private async execute(parent: Agent, config: AgentConfiguration, work: Active, importLegacy: boolean): Promise<unknown> {
    const owner=await this.owner(config);const library=await this.documents.forConfig(config);const signal=work.controller.signal;
    const table=(await this.domain).table('runs');
    owner.lastAttempt=this.now();await this.saveOwner(config.agentId,owner);
    const completed:string[]=[];let run:DreamingRun|undefined;
    try{
      await this.refreshSources(parent,config,signal);
      const eligibility=await library.status();
      if(eligibility.sourcesPending)throw new Error('Source eligibility has not been refreshed.');
      // Recover a finished file plan before freezing new work. Unfinished model staging is never reused.
      for(const [,previous] of table.entries()){
        if(previous.agentId!==config.agentId||previous.stage!=='consolidate'||!previous.plan||previous.planRetired||!(['applying','partial','failed'].includes(previous.state)||previous.state==='completed'&&previous.receipts.some(receipt=>receipt.saved&&!receipt.versionRecorded)))continue;
        run=previous;
        const versions=await library.versions();
        if(run.generation!==eligibility.generation||run.plan!.some(operation=>{
          const current=versions[operation.path]??null;return current!==operation.beforeHash&&current!==operation.afterHash;
        })){
          run.state='failed';run.planRetired=true;run.error='Frozen plan retired after source or document change; successful file receipts are preserved.';
          run.endedAt=this.now();run.summary=this.summary(run);await this.saveRun(run);await this.publish(run);continue;
        }
        await this.apply(parent,config,work,run,library,owner);completed.push(run.id);
      }
      run=undefined;
      const baselines=await this.sources.baseline(config.agentId);
      for(const [id,progress] of Object.entries(baselines))owner.streams[id]??=progress;
      await this.saveOwner(config.agentId,owner);
      const target=await this.sources.freezeTarget(config.agentId,owner.streams,owner.activationAt,{generation:eligibility.generation});
      const cycleId=randomUUID();const budget=config.knowledge?.dreaming?.maxInputTokens??24000;
      let importPending=importLegacy;
      while(true){
        signal.throwIfAborted();await assertDreamingSources(library,target.generation);
        const policy=await library.status();
        const options={maxInputTokens:budget,seen:owner.seen,sources:policy.sources,excluded:policy.exclusions.flatMap(item=>item.sources),rotation:owner.rotation++,target};
        const batch=await this.sources.freeze(config.agentId,owner.streams,options);
        const materials=await this.sources.children(config.agentId,target,batch,options);
        batch.conversations=[...new Set([...(batch.conversations??[]),...materials.flatMap(material=>sourceConversations([...material.events,...material.inheritedEvents]))])];
        const summaries:TaskSummary[]=[];
        for(const material of materials){
          const cached=(await this.domain).table('summaries').get(summaryKey(config.agentId,material.sessionId));
          const valid=cached?.sourceVersion===material.sourceVersion&&cached.generation===target.generation;
          if(valid){
            if(memoryDigest(await readFile(cached.path,'utf8'))!==cached.hash)throw new Error('Task summary cache changed unexpectedly.');
            summaries.push(cached);
          }else{
            run=this.newRun(parent,config,work,library,target,cycleId,{...batch,id:randomUUID(),units:[],ranges:[],text:material.text},'extract');
            const extracted=await this.extract(parent,config,work,run,library,owner,material);
            summaries.push(extracted);run=undefined;
          }
        }
        const pending=summaries.filter(summary=>owner.integrated[summary.sessionId]!==summary.sourceVersion);
        const selected:TaskSummary[]=[];let remaining=budget-batch.inputTokens;
        for(const summary of [...pending,...summaries.filter(item=>!pending.includes(item))]){
          const size=Math.ceil((await readFile(summary.path,'utf8')).length/3)+150;
          if(size<=remaining){selected.push(summary);remaining-=size;}
        }
        const pendingSelected=selected.some(summary=>owner.integrated[summary.sessionId]!==summary.sourceVersion);
        const check=Boolean((await library.context()).reason);
        const hasProgress=batch.ranges.some(range=>range.through>range.start||range.continuation);
        if(!batch.units.length&&!pendingSelected&&!check&&!importPending){
          // Filtered system events can advance without a model; genuine blocked prefixes cannot.
          for(const range of batch.ranges)commitSourceRange(owner.streams[range.sessionId]!,range);
          await this.saveOwner(config.agentId,owner);
          const rootPending=Object.entries(target.roots).some(([id,cut])=>owner.streams[id]!.cursor<cut.through||owner.streams[id]!.continuation);
          if(pending.length)throw new Error('A task summary does not fit the configured input capacity; it remains unintegrated.');
          if(target.blocked.length||batch.blocked.length&&(!hasProgress||rootPending))throw new Error(`Source ranges remain blocked: ${JSON.stringify([...target.blocked,...batch.blocked])}`);
          if(rootPending)throw new Error('No safe progress towards the frozen source boundary.');
          owner.failures=0;delete owner.retryAt;if(work.automatic)owner.lastSuccessAutomatic=this.now();
          await this.saveOwner(config.agentId,owner);
          return completed.length ? {accepted:true,state:'completed',runIds:completed} : {accepted:false,completed:false,reason:'no_eligible_increment'};
        }
        run=this.newRun(parent,config,work,library,target,cycleId,batch,'consolidate');
        run.summaries=selected;run.importLegacy=importPending;
        const omitted=pending.filter(summary=>!selected.includes(summary));
        if(omitted.length)run.batch.blocked.push(...omitted.map(item=>({sessionId:item.sessionId,reason:'Task summary left for a subsequent batch due to input capacity.'})));
        const input=await this.prepare(run,library,owner);
        await this.saveRun(run);
        await this.model(parent,config,work,run,library,owner,input);
        await this.apply(parent,config,work,run,library,owner);
        completed.push(run.id);importPending=false;run=undefined;
        await this.disposeHandle(work);
        // Re-enter even after the final root page: tasks may have later evidence inside this cycle's cut.
      }
    }catch(error){
      owner.failures++;owner.retryAt=this.now()+retryDelays[Math.min(owner.failures-1,retryDelays.length-1)]!;await this.saveOwner(config.agentId,owner);
      if(!run)return {accepted:completed.length>0,state:'failed',runIds:completed,reason:String(error)};
      run.state=signal.aborted ? run.receipts.some(receipt=>receipt.saved)?'partial':'cancelled' : run.receipts.some(receipt=>receipt.saved)?'partial':'failed';
      if(signal.aborted)run.planRetired=true;
      run.error=String(error);run.endedAt=this.now();run.summary=this.summary(run);await this.saveRun(run);await this.publish(run,work.handle);
      return {accepted:true,runId:run.id,state:run.state,summary:run.summary};
    }finally{await this.disposeHandle(work);}
  }
  private newRun(parent:Agent,config:AgentConfiguration,work:Active,library:MemoryDocuments,target:CycleTarget,cycleId:string,batch:FrozenBatch,stage:DreamingRun['stage']):DreamingRun{
    return {id:batch.id,agentId:config.agentId,rootSessionId:parent.id,mode:work.automatic?'automatic':'manual',stage,cycleId,
      state:'prepared',at:this.now(),generation:target.generation,directory:join(library.workspace,'.nanoassistant/maintenance/dreaming',batch.id),
      target,batch,summaries:[],receipts:[]};
  }
  private async extract(parent:Agent,config:AgentConfiguration,work:Active,run:DreamingRun,library:MemoryDocuments,owner:DreamingOwner,material:ChildMaterial):Promise<TaskSummary>{
    const input=await this.prepare(run,library,owner);await this.saveRun(run);
    const result=await this.model(parent,config,work,run,library,owner,input);
    if(!result)throw new Error('Task extraction produced no completed result.');
    await assertDreamingSources(library,run.generation);
    const path=join(library.workspace,'.nanoassistant/maintenance/task-summaries',`${key(material.sessionId)}.md`);
    await mkdir(join(path,'..'),{recursive:true,mode:0o700});
    const text=result.rollout_summary;
    await atomicWrite(path,text);await chmod(path,0o600);
    const summary:TaskSummary={agentId:config.agentId,sessionId:material.sessionId,rootSessionId:material.rootSessionId,baseline:material.baseline,through:material.through,
      sourceVersion:material.sourceVersion,generation:run.generation,path,hash:memoryDigest(text),noSignal:!text,extractionRunId:run.id,slug:result.rollout_slug};
    await (await this.domain).table('summaries').put(summaryKey(config.agentId,material.sessionId),summary);
    run.summaries=[summary];run.state='completed';run.endedAt=this.now();run.summary=this.summary(run);
    await this.saveRun(run);await this.publish(run,work.handle);await this.disposeHandle(work);
    return summary;
  }
  private async prepare(run:DreamingRun,library:MemoryDocuments,owner:DreamingOwner):Promise<string>{
    const staging=join(run.directory,'staging');
    for(const directory of [run.directory,staging,join(run.directory,'summaries')]){await mkdir(directory,{recursive:true,mode:0o700});await chmod(directory,0o700);}
    const versions=run.stage==='consolidate'?await library.versions():{};
    for(const path of Object.keys(versions)){
      const target=join(staging,path);await mkdir(join(target,'..'),{recursive:true,mode:0o700});
      await writeFile(target,await readFile(join(library.root,path),'utf8'),{mode:0o600});
    }
    const inputs=[run.stage==='extract'?'# Task extraction: inherited context and own experience':'# Qualified Global dialogue (original evidence)',run.batch.text??''];
    if(run.stage==='consolidate'){
      inputs.push('# Task source updates');
      for(const summary of run.summaries){
        const text=await readFile(summary.path,'utf8');if(memoryDigest(text)!==summary.hash)throw new Error('Task summary changed before snapshot.');
        const path=join(run.directory,'summaries',`${key(summary.sessionId)}.md`);await writeFile(path,text,{mode:0o600});
        inputs.push(`## ${summary.noSignal?'No-signal replacement; old summary retired':owner.integrated[summary.sessionId]?'Updated task summary, replaces same source':'Task summary'}\nSource session_id=${summary.sessionId}; root=${summary.rootSessionId}; events ${summary.baseline+1}–${summary.through}; version=${summary.sourceVersion}\n${text}`);
      }
      const view=await library.context();
      inputs.push(`# Current memory entry (data)\n${view.entry??`Entry requires verification: ${view.reason}; pages: ${Object.keys(view.versions).join(', ')}`}`);
      inputs.push(`# Source exclusions (data)\n${JSON.stringify(view.exclusions)}\n# Omitted or deferred sources (data)\n${JSON.stringify(run.batch.blocked)}`);
    }
    const legacy=run.importLegacy?await this.importFiles(run,library):[];
    if(run.importLegacy){if(!legacy.length)throw new Error('No registered Markdown legacy backup is available for this owner.');inputs.push(`# Requested legacy import\nRead these verified backup files as old evidence, compare current memory and preserve scope: ${JSON.stringify(legacy)}`);}
    await writeFile(join(run.directory,'manifest.json'),JSON.stringify({versions,legacy}),{mode:0o600});
    return inputs.join('\n\n');
  }
  private async importFiles(run:DreamingRun,library:MemoryDocuments):Promise<string[]>{
    const result:string[]=[];
    const entries=await readdir(library.backupRoot,{withFileTypes:true}).catch(error=>{if(error.code==='ENOENT')return [];throw error;});
    for(const entry of entries){
      if(!entry.isDirectory())continue;
      const root=join(library.backupRoot,entry.name);
      const manifest=JSON.parse(await readFile(join(root,'manifest.json'),'utf8')) as {agentId:string;workspace:string;files:Record<string,{kind:string;sha256?:string}>};
      if(manifest.agentId!==run.agentId||manifest.workspace!==library.workspace)continue;
      for(const [path,info] of Object.entries(manifest.files)){
        if(info.kind!=='file'||!path.endsWith('.md')||path.split('/').some(part=>part==='..'||part.startsWith('.')))continue;
        const content=await readFile(join(root,'memory',path),'utf8');if(memoryDigest(content)!==info.sha256)throw new Error('Legacy backup differs from its registered manifest.');
        const target=join(run.directory,'legacy',entry.name,path);await mkdir(join(target,'..'),{recursive:true,mode:0o700});await writeFile(target,content,{mode:0o600});result.push(target);
      }
    }
    return result;
  }
  private model(parent:Agent,config:AgentConfiguration,work:Active,run:DreamingRun,library:MemoryDocuments,owner:DreamingOwner,input:string){
    this.maintenance.add(`dreaming-${run.id}`);
    return library.status().then(status=>runDreamingAgent(this.ctx,{parent,config,signal:work.controller.signal,run,owner,library,input,sources:this.sources,
      conversations:[...new Set(status.sources?.allowed??run.batch.conversations??[])].filter(id=>!status.sources?.excluded.includes(id)&&!status.exclusions.some(item=>item.sources.includes(id))),
      save:()=>this.saveRun(run),opened:handle=>{work.handle=handle;}}));
  }
  private async apply(parent:Agent,config:AgentConfiguration,work:Active,run:DreamingRun,library:MemoryDocuments,owner:DreamingOwner){
    work.controller.signal.throwIfAborted();await this.refreshSources(parent,config,work.controller.signal);await assertDreamingSources(library,run.generation);
    if(!run.plan)throw new Error('No completed staging plan.');
    run.state='applying';await this.saveRun(run);
    for(const operation of run.plan){
      work.controller.signal.throwIfAborted();const current=this.configuration(config.agentId);
      if(this.options.held?.(config.agentId)||current?.knowledge?.memoryMode==='legacy'||work.automatic&&current?.features?.dreaming===false)throw new Error('Maintenance disabled before file application.');
      const content=await readFile(join(run.directory,'staging',operation.path),'utf8');if(memoryDigest(content)!==operation.afterHash)throw new Error('Staged output changed after host validation.');
      const receipt=await library.apply({...operation,content},run.generation,work.controller.signal);
      run.receipts=[...run.receipts.filter(item=>item.operationId!==receipt.operationId),receipt];await this.saveRun(run);
      if(!receipt.saved)throw new Error(receipt.error??'File was not saved.');
    }
    if(run.sourcesChecked){
      const manifest=JSON.parse(await readFile(join(run.directory,'manifest.json'),'utf8')) as {versions:Record<string,string>};
      const confirmed={...manifest.versions};for(const operation of run.plan)confirmed[operation.path]=operation.afterHash;
      await library.checkpoint(Object.fromEntries(Object.entries(confirmed).sort(([a],[b])=>a.localeCompare(b))),run.generation);
    }
    run.state='completed';run.endedAt=this.now();run.summary=this.summary(run);await this.saveRun(run);
    await this.commitProgress(run,owner);await this.publish(run,work.handle);
  }
  private async commitProgress(run:DreamingRun,owner:DreamingOwner){
    for(const range of run.batch.ranges)if(owner.streams[range.sessionId])commitSourceRange(owner.streams[range.sessionId]!,range);
    owner.seen=[...new Set([...owner.seen,...run.batch.units.flatMap(unit=>unit.fingerprints)])];
    for(const summary of run.summaries)owner.integrated[summary.sessionId]=summary.sourceVersion;
    await this.saveOwner(run.agentId,owner);
  }
  private async disposeHandle(work:Active){
    if(work.handle){this.maintenance.delete(work.handle.agent.id);await work.handle.dispose();work.handle=undefined;}
  }
  private summary(run:DreamingRun):string{
    if(run.stage==='extract')return `任务经历提炼 ${run.state}；${run.state==='completed'?(run.summaries[0]?.noSignal?'无值得保留的新信号，旧摘要退役':'已保存任务复盘，尚未整合进正式记忆'):'未生成有效的新版本'}。${run.error??''}`;
    const saved=run.receipts.filter(receipt=>receipt.saved).length;const git=run.receipts.filter(receipt=>receipt.saved&&!receipt.versionRecorded).length;
    return `Dreaming ${run.state}: 本批交流${run.state==='completed'?'已整理':'未完成'}；使用 ${run.summaries.length} 份任务复盘；保存 ${saved}/${run.plan?.length??0} 页；${run.state==='completed'?'本批成功进度已登记':'未推进处理游标'}。${git?`${git} 页内容已保存，版本记录失败。`:''}${run.batch.blocked.length?`另有 ${run.batch.blocked.length} 个源范围待处理。`:''}${run.error??''}`;
  }
  private async publish(run:DreamingRun,handle?:AgentHandle){
    if(handle){handle.agent.session.append('user/message',createUserMessage({source:{kind:'nano-system',actorId:run.agentId,channel:'dreaming-receipt',messageId:`${run.id}:receipt`},content:[{type:'text',text:`Host application receipt (authoritative outcome): ${run.summary}`}]}),{surfaceOp:'append'});await this.ctx.sessions.flush(handle.agent.session);}
    if(run.childSessionId)await this.ctx.nanoTrajectoryRuns.finishMaintenance(run.id,run.state==='completed'?'completed':run.state==='cancelled'?'cancelled':'failed');this.options.notify();
  }
  async reviews(){return [...(await this.domain).table('runs').entries()].map(([,run])=>({id:run.id,agentId:run.agentId,rootSessionId:run.rootSessionId,...(run.childSessionId?{childSessionId:run.childSessionId}:{}),at:run.at,kind:'dreaming' as const,status:run.state,...(run.summary!==undefined?{summary:run.summary}:{}),...(run.endedAt!==undefined?{endedAt:run.endedAt}:{})}));}
  /** Report both source streams without making a model call or consuming any progress. */
  async status(agentId:string){
    const config=this.configuration(agentId);if(!config)return undefined;const owner=await this.owner(config);
    const policy=await(await this.documents.forConfig(config)).status();
    if(policy.sourcesPending)return {...owner,active:this.active.has(agentId),backlog:{state:'source_eligibility_pending',scope:'unavailable'}};
    const target=await this.sources.freezeTarget(agentId,owner.streams,owner.activationAt,{generation:policy.generation});
    const options={maxInputTokens:config.knowledge?.dreaming?.maxInputTokens??24000,seen:owner.seen,sources:policy.sources,excluded:policy.exclusions.flatMap(item=>item.sources),rotation:owner.rotation,target};
    const batch=await this.sources.freeze(agentId,owner.streams,options);
    const materials=await this.sources.children(agentId,target,{...batch,ranges:[],cutoffs:{}},options);
    const summaries=(await this.domain).table('summaries');
    const children=materials.map(material=>{const cached=summaries.get(summaryKey(agentId,material.sessionId));return {sessionId:material.sessionId,
      state:cached?.sourceVersion!==material.sourceVersion||cached.generation!==policy.generation?'pending_extraction':owner.integrated[material.sessionId]!==material.sourceVersion?'pending_integration':'integrated'};});
    const pending=batch.units.length>0||children.some(child=>child.state!=='integrated');
    const blocked=[...target.blocked,...batch.blocked];
    return {...owner,active:this.active.has(agentId),backlog:{state:pending?'pending':blocked.length?'blocked':'no_eligible_increment',scope:'frozen_sources',
      global:{pending:batch.units.length>0,ranges:batch.ranges},children,blocked},reviews:(await this.reviews()).filter(run=>run.agentId===agentId)};
  }
  /** Recover real application receipts; never reuse unfinished model staging or an old cycle target. */
  async recover(){
    const domain=await this.domain;
    for(const [,run] of [...domain.table('runs').entries()].sort((a,b)=>a[1].at-b[1].at)){
      if(run.childSessionId&&!run.identityRecorded)await this.repairIdentity(run);
      // A saved file may still need its frozen content to retry version recording.
      const pendingVersion=run.receipts.some(receipt=>receipt.saved&&!receipt.versionRecorded);
      if(run.endedAt&&this.now()-run.endedAt>7*86400000&&(run.planRetired||run.state==='completed'&&!pendingVersion||!run.plan&&['failed','cancelled'].includes(run.state))){
        for(const path of ['input','input.md','staging','summaries','legacy'])await rm(join(run.directory,path),{recursive:true,force:true});
      }
      if(run.stage==='consolidate'&&run.state==='completed'){
        const owner=domain.table('owners').get(key(run.agentId));if(owner?.protocol===2)await this.commitProgress(run,owner);
      }else if(run.state==='prepared'||run.state==='running'){
        run.state=run.plan?'applying':'failed';run.error='Interrupted before application; next run freezes a new target.';await this.saveRun(run);
      }
    }
  }
  /** Backfill pre-descriptor Dreaming logs once, without activating an Agent or rewriting history. */
  private async repairIdentity(run: DreamingRun) {
    const id = SessionId(run.childSessionId!);
    if (!await this.ctx.sessionPersistence.stat(id)) return;
    await using handle = await this.ctx.sessionPersistence.open(id, 'write');
    if (id !== `dreaming-${run.id}` || handle.header.origin !== 'subagent' || handle.header.parentSession !== run.rootSessionId || handle.inheritedEventCount !== 0) {
      throw new Error('Dreaming history identity does not match its recorded run.');
    }
    const { events } = await handle.read();
    if (!events.some(event => event.type === 'subagent/descriptor')) {
      // Append model-hidden metadata at today's time; retain every original event and sequence.
      const descriptor = snapshotSessionEvent({ type: 'subagent/descriptor', seq: SessionSeq(events.length), time: this.now(),
        data: snapshotSubagentDescriptor({ mode: 'one-shot', provider: 'native', label: 'Dreaming · 自动整理记忆' }) });
      await handle.append([descriptor]); await handle.flush();
    }
    run.identityRecorded = true; await this.saveRun(run);
  }
  async configurationChanging(config: AgentConfiguration) {
    const active = this.active.get(config.agentId);
    if (active && (config.knowledge?.memoryMode === 'legacy' || active.automatic && config.features?.dreaming === false)) await this.stopAgent(config.agentId);
  }
  async stopAgent(agentId: string) { const active = this.active.get(agentId); active?.controller.abort(); if (active) await active.promise; }
  async stop() { this.stopped = true; for (const active of this.active.values()) active.controller.abort(); await Promise.allSettled([...this.active.values()].map(active => active.promise)); await (await this.domain).close(); }
}
