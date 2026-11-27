import {ComputerHost} from './computer/host.js';
/** Nano's sole stdio server inside an unmodified DSH profile. */
import { personalEvidenceMessages, personalReviewAction, personalReviewImages, reviewPersonal, assertPersonalConfiguration } from './personal-security.js';
import { randomUUID } from 'node:crypto';
import { realpath, stat } from 'node:fs/promises';
import { AsyncLocalStorage } from 'node:async_hooks';
import { OwnedSessions, OwnedSessionController } from './owned-sessions.js';
import type { ProfilePnpmInvocation } from '@deepseek-ai/dsh-app-boot';
import { Context, Service } from '@deepseek-ai/cordis';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { ScheduleId } from '@deepseek-ai/dsh-schedule';
import { SessionId, SessionLogOffset, SessionSeq, type SessionEvent } from '@deepseek-ai/dsh-session';
import { freezeMessage, MessageId, ReasoningEffortId, type UserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-agent-preset-registry';
import { renderPrompt, renderContextSnapshot } from '@deepseek-ai/dsh-system-prompt';
import { foldSubagentDescriptor } from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-session-query';
import type {} from '@deepseek-ai/dsh-jobs';
import type {} from '@deepseek-ai/dsh-terminal';
import { ColdLifecycleBarrier, type RuntimeLifecycle } from './runtime-lifecycle.js';
import { UpdateBarrier } from './update-barrier.js';
import { dispatchRuntime, runtimeMethods, RuntimeRpcValidationError, type RuntimeHandlerMap, type RuntimeInput, type RuntimeMethod, type RuntimeOutput, type ScheduleHandlerMap } from '@nano/product-contracts/runtime-rpc';
import { RpcError, RpcPeer } from './rpc.js';
import { recordToolPresentations } from './tool-presentation.js';
import { scheduleEvidence } from './schedule-evidence.js';
import { isHumanSource } from './input-source.js';
import { CapabilityState, capabilityDraft, needsSchedules, configurationBlocks } from './capability-state.js';
import {workObject, type ProactiveSyncObservationsResult, type RuntimeEvent} from '@nano/product-contracts';
import type { RuntimePublicationEvidence, RuntimeWorkCatalog, RuntimeWorkChild, RuntimeWorkPage } from '@nano/product-contracts';
import { jsonBytes, workPage, workPageBytes, workPageItems, WorkCatalogPages } from './work-page.js';
import { definitionsForRole, effectiveFeatures, type CapabilityTarget } from '@nano/product-contracts/capabilities';
import { createSessionSchedule, CronOwners, deleteSessionSchedule, listSessionSchedules, updateSessionSchedule } from './cron-owners.js';
import { LogicalCronClock } from './features/cron.js';
import { ConfigurationScopes } from './agent-config.js';
import { assembleAgentPrompt } from './prompt-assembly.js';
import { TaskExecutionDriver } from './task-execution.js';
import { TaskContextDriver } from './task-context.js';
import { ProductBridge } from './product-bridge.js';
import { skillCatalog } from './capabilities.js';
import * as SelectedSkills from './capabilities.js';
import { createScope } from '@deepseek-ai/dsh-scope';
import { KnowledgeRuntime } from './knowledge/runtime.js';
import { initializeRoleDocument, roleDocument } from './knowledge/role-document.js';
import { NativeModelSetup } from './model-setup.js';
import { ModelPolicy } from './model-policy.js';
import { NativeHistory } from './history.js';
import { NanoApproval } from './policy/approval.js';
import { CcApproval } from './policy/cc.js';
import { CodexApproval } from './policy/codex.js';
import * as NanoWeb from './web.js';
import { NanoWorkflowEngine } from './workflow/engine.js';
import { registerWorkflowTool } from './workflow/tool.js';
import { ChatScope } from './chat-scope.js';
import { InboxDelivery } from './inbox-delivery.js';
import { installLlmAttribution } from './llm-attribution.js';
import { attachModelConnectionRetry } from './model-connection-retry.js';
import { installStandaloneModelRetry } from './standalone-model-retry.js';
import { TrajectoryRuns } from './trajectory-runs.js';
import { NativeTrajectory } from './trajectory.js';
import { TrajectoryAttachments } from './trajectory-attachments.js';
import { DescendantReader } from './descendants.js';
import { SubagentRecovery } from './subagent-recovery.js';
import {LocalWorkers} from './local-workers/manager.js';
import { InterruptedWork } from './interrupted-work.js';
import { SessionDeletion } from './agent-deletion.js';
import { ownedLinks, purgeDerived } from './agent-deletion-derived.js';

export interface AgentConfiguration {
  workerRuntime?: import('@nano/product-contracts').WorkerRuntime;
  personal?: {bindingId:string;ownerId:string;conversationId:string;epoch:number};
  agentId: string;
  displayName?: string;
  executionNode?: import('@nano/product-contracts').AgentConfiguration['executionNode'];
  workspace?: string;
  revision: string;
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  modelRouteFrozen?: boolean;
  workflow?: { outputTokenTarget?: number; sizeGuideline?: string };
  modelFallbacks?: { provider: string; model: string; reasoningEffort?: string; maxTokens?: number }[];
  features?: Record<string, boolean>;
  toolAllowlist?: string[];
  skillSelection?: { mode: 'default_discovery' | 'explicit_allowlist' | 'explicit_denylist'; names: string[] };
  skillRoots?: { path: string; source: string }[];
  extensions?: { global?: string; workspace?: string };
  knowledge?: import('@nano/product-contracts').AgentConfiguration['knowledge'];
  approval?: import('@nano/product-contracts').ApprovalConfiguration;
  collaborationScope?: 'team' | 'project' | 'owner_only';
  mode?: 'single_thread' | 'global';
}
export interface SessionBinding {
  sessionId: string;
  agentId: string;
  ownerId: string;
  cwd: string;
  revision: string;
}
type Submit = RuntimeInput<'session.submit'>;
declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    schedule: { kind: 'schedule'; lifecycle_revision?: number; scheduleId?: string; triggerKind?: 'manual' };
    'nano-system': { kind: 'nano-system'; nanoTeamChat?:boolean; lifecycle_revision?: number; actorId: string; channel: string; messageId: string; senderSessionId?: string; conversationId?:string; humanTaskControl?:Record<string,unknown>; background_returns?: Record<string, unknown>[] };
  }
}

function exitInspection(status: number): never {
  if (process.platform !== 'win32') process.kill(-process.pid, 'SIGKILL');
  process.exit(status);
}

/** Trusted node configuration is installed before any Session can be resumed. */
export default class NanoRuntime {
  static inject = ['jobs', 'agents', 'sessions', 'agentPresets', 'loader', 'tools', 'skills', 'systemPrompt', 'subagents', 'sessionQuery', 'sessionPersistence', 'storageDomain', 'llm', 'settings', 'credentials', 'authorization', 'sessionToolResults', ...SessionController.inject];
  private readonly peer = new RpcPeer(process.stdin, process.stdout, () => {
    if (process.env.NANO_CONFIGURATION_INSPECTION_ID && process.platform !== 'win32') exitInspection(1);
    process.kill(process.pid, 'SIGTERM');
  });
  private readonly bindings = new Map<string, SessionBinding>();
  private readonly configurations = new Map<string, AgentConfiguration>();
  private readonly inputs = new Map<string, ReturnType<NanoRuntime['submit']>>();
  private readonly approvals = new Map<string, (answer: ApprovalOutcome, reason?: string) => void>();
  private readonly unregisterPresets: (() => Promise<void>)[] = [];
  private accepting = false;
  private markRecovery = false;
  private readonly lifecycle: ColdLifecycleBarrier;
  private readonly owned: OwnedSessions;
  private readonly ownerOf: (sessionId: string) => string | undefined;
  private admissions = 0;
  private readonly controller;
  private readonly chatScope: ChatScope;
  private readonly models: Promise<ModelPolicy>;
  private readonly knowledgeRuntime: Promise<KnowledgeRuntime>;
  private readonly cron: CronOwners;
  private readonly capabilities: CapabilityState;
  private tasks!: TaskExecutionDriver;
  private readonly sessionController: Promise<SessionController>;
  private ownerTimezone?: string;
  private logicalNowMs?: number;
  private readonly clockNow = () => this.logicalNowMs ?? Date.now();
  private readonly syncedScheduleTurns = new Map<string, number>();

  constructor(private readonly ctx: Context, config?: {agentDeletion?: boolean}) {
    const inspection = process.env.NANO_CONFIGURATION_INSPECTION_ID;
    const inspectionAbort = new AbortController();
    if (inspection) {
      // If the main thread can still run, exit the group before its leader goes away.
      process.stdin.once('end', () => exitInspection(0));
      this.peer.onNotification(method => {if (method === 'configuration.cancel') inspectionAbort.abort();});
      const deadline = Number(process.env.NANO_CONFIGURATION_INSPECTION_DEADLINE);
      if (Number.isFinite(deadline)) setTimeout(() => exitInspection(1), Math.max(0,deadline-Date.now())+500).unref();
    }
    let inspectionPackageManager: ProfilePnpmInvocation | undefined;
    const cleanup = new AsyncLocalStorage<string[]>();
    ctx.logger.exporter({export: message => {
      if (message.type === 'error') cleanup.getStore()?.push(String(message.args[0]?.stack ?? message.args[0] ?? 'Runtime cleanup error'));
    }});
    const liveAgents = new WeakSet<Agent>();
    ctx.on('agent/inbox/inserted', ({agent, message}) => {
      if (!liveAgents.has(agent) || message.source.kind !== 'schedule' || 'lifecycle_revision' in message.source) return;
      const agentId = this.ownerOf(agent.id);
      if (agentId) agent.inbox.replace(message.id, freezeMessage({...message, source: {...message.source, lifecycle_revision: this.lifecycle.current(agentId).revision}}));
    });
    let terminals: Context['terminals'] | undefined;
    ctx.inject(['terminals'], child => { terminals = child.terminals; child.effect(() => () => { terminals = undefined; }); });
    const lifecycle = this.lifecycle = new ColdLifecycleBarrier(ctx);
    const deletion = !inspection && config?.agentDeletion ? SessionDeletion.forRuntime(ctx, process.env.DSH_HOME!) : undefined;
    installStandaloneModelRetry(ctx);
    const takeConnectionFailure = installLlmAttribution(ctx, sessionId => {
      let session = ctx.sessions.get(SessionId(sessionId));
      while (session && !this.bindings.has(session.id) && session.header.parentSession) {
        const parent = ctx.sessions.get(session.header.parentSession);
        if (!parent) break;
        session = parent;
      }
      return session?.id ?? sessionId;
    });
    const inboxDelivery = new InboxDelivery(ctx, sessionId => this.bindings.get(sessionId)?.agentId, sessionId => {
      this.peer.notify('session.work.changed', {sessionId,rootSessionId:sessionId});
    });
    this.chatScope = new ChatScope(ctx,id=>this.bindings.get(id)?.agentId);
    new TrajectoryRuns(ctx);
    const workers=new LocalWorkers(ctx,async(root,worker,event,text)=>{
      const binding=this.bindings.get(root);
      if(!binding)throw new Error('Worker parent is no longer bound');
      const messageId=`worker:${worker}:${event}`;
      const receipt=await this.submit({sessionId:root,inputId:messageId,mode:'steer',content:[{type:'text',text}],
        source:{kind:'system',channel:'worker-report',actorId:binding.agentId,senderSessionId:worker,messageId}});
      if(!receipt.accepted)throw new Error('Parent did not accept the worker report');
    },id=>this.bindings.has(id),root=>this.peer.notify('session.work.changed',{sessionId:root,rootSessionId:root}),
    async (root, row, assignment, dispatchCallId) => (await approval).bindWorker(root, row, assignment, dispatchCallId,
      async (callId, toolName, summary, escalation, signal, timeout) => {
        if (disabled(root.id) || !this.bindings.has(root.id)) return {allow:false, reason:'Worker root is unavailable.'};
        const worker = {workerId:row.workerId, label:row.label, runtime:row.runtime};
        const reason = `${JSON.stringify(worker.label)} (${worker.runtime}, ${worker.workerId}) · ${toolName}\n${JSON.stringify(summary)}\n${escalation}`;
        const result = await this.waitForApproval({sessionId:root.id, callId, toolName, worker, reason,
          toolInput:{arguments:summary}}, signal, timeout);
        return {allow:result.outcome === 'allowed-once', reason:result.reason || result.outcome};
      }));
    let configurationService: ConfigurationScopes;
    new ComputerHost(ctx,this.bindings,agent=>configurationService?.forAgent(agent));
    this.capabilities = new CapabilityState((config, names) => configurationService.selection(config, names));
    const history = new NativeHistory(ctx, process.env.DSH_HOME!);
    this.cron = new CronOwners(ctx, process.env.DSH_HOME!, (agentId, action) => !['catalog', 'history', 'list', 'delete'].includes(action) && (this.capabilities.held(agentId, {kind: 'feature', name: 'cron_scheduling'}) || this.capabilities.held(agentId, {kind: 'tool', name: `schedule_${action}`})));
    const self = this;
    new LogicalCronClock(ctx, {
      get enabled() { return self.cron.isLogicalClock; },
      now: () => self.clockNow(),
      createSchedule: (agentId, sessionId, args, signal) => self.cron.createAtLogicalClock(agentId, sessionId, args, signal),
      listSchedules: (agentId, sessionId) => self.cron.listAtLogicalClock(agentId, sessionId),
      alignSchedule: (agentId, scheduleId) => self.cron.alignToLogicalClock(agentId, scheduleId, self.clockNow()),
    });
    const activeSubagents = new Set<string>();
    let wakeSubagentIdle: (() => void) | undefined;
    ctx.on('subagent/start', ({ runId }) => { activeSubagents.add(runId); });
    ctx.on('subagent/end', ({ runId }) => { activeSubagents.delete(runId); wakeSubagentIdle?.(); });
    ctx.plugin(ConfigurationScopes, {configurations:this.configurations, changed:agentId => this.peer.notify('configuration.catalog.changed', {agentId})});
    const descendantReader = new DescendantReader(ctx);
    const boundRoot = (id: string): string | undefined => {
      let current: string | undefined = id;
      while (current) {
        if (this.bindings.has(current)) return current;
        const known = descendantReader.rootOf(current);
        if (known && this.bindings.has(known)) return known;
        current = ctx.sessions.get(SessionId(current))?.header.parentSession;
      }
    };
    this.ownerOf = id => {
      const root = boundRoot(id);
      return root ? this.bindings.get(root)?.agentId : this.configurations.get(ctx.agents.get(SessionId(id))?.session.header.agentPreset ?? '')?.agentId;
    };
    const disabled = (id: string) => { const owner = this.ownerOf(id); return owner ? lifecycle.current(owner).disabled === true : false; };
    const cancelPersisted = async (agentId: string) => {
      const owns = (id: string) => this.ownerOf(id) === agentId;
      const coldOwns=async(id:string)=>{
        const seen=new Set<string>();
        let sessionId:string|undefined=id;
        while(sessionId && !seen.has(sessionId)) {
          seen.add(sessionId);
          const owner=this.ownerOf(sessionId);
          if(owner)return owner===agentId;
          const snapshot=await ctx.sessionPersistence.stat(SessionId(sessionId));
          sessionId=snapshot?.header?.parentSession;
        }
        return false;
      };
      await (await models).cancelPersisted(owns,coldOwns);
      await (await workflow).cancelPersisted(owns);
      await (await knowledge).cancelPersisted(agentId);
    };
    const workChanged = (rootSessionId: string, childId: string) => {
      const binding = this.bindings.get(rootSessionId);
      if (!binding || this.configurations.get(`nano:${binding.agentId}:${binding.revision}`)?.mode !== 'global') return;
      this.peer.notify('session.work.changed', {sessionId:rootSessionId,rootSessionId,childId}, `session.work.changed:${childId}`);
    };
    const modelFiber = ctx.plugin(ModelPolicy, { check: (agent: Agent, run: import('./model-fallback.js').ModelRun) => this.peer.request('model.check', { sessionId: agent.id, turn: run.turn, turns: run.attempts.map(attempt => attempt.turn) }) as Promise<{ published: boolean }>, notify: (sessionId: string) => {
      const rootSessionId = boundRoot(sessionId);
      const session = ctx.sessions.get(SessionId(sessionId));
      if (session?.header.origin === 'subagent')
        void captureWorkerTurns(session).catch(error=>ctx.logger.error(error));
      this.peer.notify('model.changed', { sessionId, rootSessionId, workChild:descendantReader.hasChild(sessionId) });
    } });
    const webHandle: NanoWeb.NanoWebHandle = {};
    const webFiber = ctx.plugin(NanoWeb, webHandle);
    const workflowFiber = ctx.plugin(NanoWorkflowEngine, { configuration: (agent: Agent) => configurationService.forAgent(agent)!, completed: (record: import('./workflow/state.js').WorkflowRecord) => this.peer.notify('workflow.completed', record) });
    const workflow = new Promise<NanoWorkflowEngine>(resolve => { ctx.inject(['workflowEngine', 'nanoApproval', 'nanoModels'], child => { const engine = child.workflowEngine as NanoWorkflowEngine; registerWorkflowTool(child, engine, agent => configurationService.forAgent(agent)!); resolve(engine); }); });
    const models = this.models = new Promise<ModelPolicy>(resolve => { ctx.inject(['nanoModels'], child => { resolve(child.nanoModels); }); });
    const captureWorkerTurns = async (session: import('@deepseek-ai/dsh-session').Session) => {
      const {fallback} = await models;
      await workers.nativeTurns(session,turn=>fallback.workModel(session.id,turn));
    };
    const knowledgeFiber = ctx.plugin(KnowledgeRuntime, { configOf: (agent: Agent) => configurationService.forAgent(agent), configs: this.configurations, bindings: this.bindings,
      childConfiguration: (sessionId: string) => history.childConfiguration(sessionId),
      roleWorkspace: async (agentId: string) => (await this.peer.request('knowledge.role.workspace', {agentId}) as {workspace: string | null}).workspace,
      notify: () => this.peer.notify('knowledge.changed', {}),
      held: (agentId: string, kind: 'memory' | 'skills') => lifecycle.current(agentId).disabled === true || this.capabilities.held(agentId, {kind: 'feature', name: kind === 'memory' ? 'memory_curation' : 'skill_creation'}),
      timeZone: () => this.ownerTimezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
      resolveSession: (sessionId: string) => this.owned.resolve(sessionId, false) });
    const knowledge = this.knowledgeRuntime = new Promise<KnowledgeRuntime>(resolve => { ctx.inject(['nanoKnowledge'], child => { resolve(child.nanoKnowledge); }); });
    let updateServices: { models: ModelPolicy; knowledge: KnowledgeRuntime; workflow: NanoWorkflowEngine } | undefined;
    const update = new UpdateBarrier({
      agents: () => ctx.agents.list(),
      busy: () => !this.accepting || modelSetup.busy || this.admissions > 0 || this.approvals.size > 0 ||
        !updateServices || updateServices.models.busy || updateServices.knowledge.busy || updateServices.workflow.busy,
      pause: async () => {
        updateServices!.knowledge.suspendUpdates(true);
        await this.cron.pause();
        // Cold bindings may contain durable inbox entries before PA recovery.
        for (const id of this.bindings.keys()) if (!disabled(id)) await this.agent(id);
      },
      resume: async () => { updateServices?.knowledge.suspendUpdates(false); await this.cron.resume(); },
    });
    // Track in-flight RPCs before their first await. Read paths resolving an
    // Agent can also restore durable inbox work, so they share admission.
    const handle = (method: string, action: (value: unknown) => unknown, options?: {pull?: string}) => this.peer.handle(method, async value => {
      if (update.held && method !== 'approval.answer') throw new RpcError(-32003, 'Runtime is held for update');
      this.admissions++;
      try {
        const input = value as {agentId?: string; sessionId?: string; config?: {agentId?: string}} | undefined;
        const owner = input?.agentId ?? input?.config?.agentId ?? (input?.sessionId ? this.ownerOf(input.sessionId) : undefined);
        return await (deletion ? deletion.admit(owner, () => action(value)) : action(value));
      } finally { this.admissions--; }
    }, options);
    const modelSetup = new NativeModelSetup(ctx, { handle, notify: (method, value) => this.peer.notify(method, value) }, providers => webHandle.refresh?.(providers));
    this.peer.handle('update.prepare', async value => {
      const operationId = (value as { operationId: string }).operationId;
      if (typeof operationId !== 'string' || !operationId) throw new RpcError(-32602, 'Update operation identity is required');
      return update.prepare(operationId);
    });
    this.peer.handle('update.release', value => update.release((value as { operationId: string }).operationId));
    ctx.plugin(CcApproval);
    ctx.plugin(CodexApproval, {
      boundRoot: sessionId => {
        const root = boundRoot(sessionId);
        return root ? ctx.agents.get(SessionId(root)) : undefined;
      },
      recordOwner: deletion ? (parent, child) => deletion.rememberReviewer(parent, child) : undefined,
    });
    const codex = new Promise<CodexApproval>(resolve => { ctx.inject(['codexApproval'], child => { resolve(child.codexApproval); }); });
    const approvalFiber = ctx.plugin(NanoApproval, (agent: Agent) => configurationService.forAgent(agent));
    const approval = new Promise<NanoApproval>(resolve => { ctx.inject(['nanoApproval'], child => { resolve(child.nanoApproval); }); });
    const configuration = new Promise<ConfigurationScopes>(resolve => { ctx.inject(['nanoConfiguration'], child => { configurationService = child.nanoConfiguration; resolve(configurationService); }); });
    ctx.on('tools/pre-execute', async (exec, next) => {
      if (exec.agent && disabled(exec.agent.id)) return {kind: 'deny', reason: 'agent_disabled'};
      const config = exec.agent && configurationService.forAgent(exec.agent);
      if (!config) return next();
      const key = `${exec.agent!.id}:${exec.callId}`;
      if (!this.capabilities.begin(key, config.agentId, {kind: 'tool', name: exec.name}, configurationService.independentTool(exec.agent!, exec.name))) return {kind: 'deny', reason: 'Capability is reserved by configuration'};
      const skill = exec.name === 'skill' && (exec.arguments as {name?: string}).name;
      if (skill && !this.capabilities.begin(`${key}:skill`, config.agentId, {kind: 'skill', name: skill})) { this.capabilities.end(key); return {kind: 'deny', reason: 'Skill is reserved by configuration'}; }
      try { return await next(); } catch (error) { this.capabilities.end(key); this.capabilities.end(`${key}:skill`); throw error; }
    }, {prepend: true});
    ctx.on('tools/result', exec => { if (exec.agent) { this.capabilities.end(`${exec.agent.id}:${exec.callId}`); this.capabilities.end(`${exec.agent.id}:${exec.callId}:skill`); } });
    ctx.plugin(ProductBridge, { peer: this.peer, bindings: this.bindings });
    this.tasks=new TaskExecutionDriver(ctx,{peer:this.peer,bindings:this.bindings,configuration:agent=>configurationService.forAgent(agent),lifecycleRevision:agentId=>lifecycle.current(agentId).revision,allowed:agentId=>!lifecycle.current(agentId).disabled,clockNow:this.clockNow});
    ctx.on('agent/disposed', ({ agent }) => { this.syncedScheduleTurns.delete(agent.id); });
    ctx.on('agent/pre-step', async ({ agent, messages, turn }, next) => {
      const binding = this.bindings.get(agent.id);
      const config = binding && configurationService.forAgent(agent);
      if (binding && config?.personal && messages.some(m => m.source.kind === 'schedule') && this.syncedScheduleTurns.get(agent.id) !== turn) {
        this.syncedScheduleTurns.set(agent.id, turn);
        let timer: ReturnType<typeof setTimeout> | undefined;
        try {
          const synced = await Promise.race([
            this.peer.request('product.proactive.sync_observations', {
              sessionId: agent.id, agentId: binding.agentId, ownerId: binding.ownerId,
            }) as Promise<ProactiveSyncObservationsResult>,
            new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error('sync_observations_timeout')), 5000); timer.unref(); }),
          ]);
          if (synced?.unread_conversations?.length) {
            const msgId = MessageId(`schedule-observation-sync:${agent.id}:${turn}`);
            messages.push(freezeMessage({
              id: msgId,
              role: 'user',
              source: {
                kind: 'nano-system',
                actorId: binding.agentId,
                channel: 'schedule-observation-sync',
                messageId: msgId,
                lifecycle_revision: lifecycle.current(binding.agentId).revision,
              },
              content: [{
                type: 'text',
                text: `Fresh observation sync completed before this scheduled check. Unread conversations in your Inbox (read relevant targets with inbox(action="read", target=...) before sending any reminder or follow-up):\n${JSON.stringify(synced.unread_conversations)}`,
              }],
            }));
          }
        } catch {
          // Offline center or 5s timeout degrades gracefully without failing the scheduled turn.
        } finally {
          if (timer) clearTimeout(timer);
        }
      }
      return next();
    }, { prepend: true });
    // Both hooks prepend: register catch-up last so its authority cut precedes Task decisions.
    const taskContext = new TaskContextDriver(ctx,{bindings:this.bindings,peer:this.peer,availability:(agent,available,inputs)=>this.tasks.contextAvailability(agent,available,inputs),lifecycleRevision:agentId=>this.lifecycle.current(agentId).revision});
    ctx.on('agent/pre-step', async ({agent}, next) => disabled(agent.id) ? {kind: 'reject'} : next(), {prepend: true});
    const subagentRecovery = new SubagentRecovery(ctx, agent => {
      const binding = this.bindings.get(agent.id);
      if (!binding || configurationService.forAgent(agent)?.mode !== 'global') return;
      return {agentId: binding.agentId, revision: lifecycle.current(binding.agentId).revision};
    });
    this.owned = new OwnedSessions(ctx, this.bindings, agentId => lifecycle.assertEnabled(agentId), async binding => {
      if (this.markRecovery && this.configurations.get(`nano:${binding.agentId}:${binding.revision}`)?.mode === 'single_thread')
        await this.peer.request('session.recovery.mark', {sessionId: binding.sessionId, agentId: binding.agentId});
    }, async (binding, session) => {
      if (this.configurations.get(`nano:${binding.agentId}:${binding.revision}`)?.mode !== 'global') return;
      const revision = lifecycle.current(binding.agentId).revision;
      const assertCurrent = () => {
        lifecycle.assertEnabled(binding.agentId);
        if (lifecycle.current(binding.agentId).revision !== revision) throw new RpcError(-32003, 'stale_lifecycle');
      };
      const projections = ctx.get('sessionProjections')?.snapshot(session, ['subagentCatalog']);
      const {interrupted, complete} = await descendantReader.interruptedChildren({header: session.header, projections});
      const wf = await workflow;
      await wf.ready;
      await subagentRecovery.record(binding.sessionId, interrupted.filter(child =>
        wf.workRelationship(binding.sessionId, child.id) === undefined &&
        projections?.values.subagentCatalog?.find(entry => entry.id === child.id)?.mode !== 'continuable'), assertCurrent);
      if (!complete) throw new RpcError(-32005, 'Subagent recovery evidence is temporarily unavailable');
    }, binding => this.configurations.get(`nano:${binding.agentId}:${binding.revision}`));
    ctx.provide('nanoSessions', this.owned);
    this.interruptedWork = new InterruptedWork(ctx, descendantReader, async (parentId, childId) => (await workflow).isWorkChild(parentId, childId));
    this.controller = ctx.plugin(OwnedSessionController, {nativeOpen: false});
    this.sessionController = new Promise(resolve => {
      ctx.inject(['sessionController'], child => { resolve(child.sessionController); });
    });
    new TrajectoryAttachments(ctx);
    const trajectory = new NativeTrajectory(ctx, { controller: this.sessionController, bindings: this.bindings, configurations: this.configurations });
    trajectory.register(this.peer, (id, action) => deletion ? deletion.admit(id, action) : action());
    const scheduleNotifyHolds = new Map<string, {gate: PromiseWithResolvers<void>; maintenance?: Promise<unknown>}>();
    const scheduleNotifyPending = new Map<string, Promise<{durable: true}>>();
    ctx.on('subagent/start', ({ id }) => {
      const notifyHold = scheduleNotifyHolds.get(id);
      const live = notifyHold && ctx.agents.get(id);
      if (live && !notifyHold.maintenance) notifyHold.maintenance = live.runMaintenance(() => notifyHold.gate.promise);
    }, { prepend: true });
    ctx.on('agent/created', async ({ agent, source }) => {
      const agentId = this.ownerOf(agent.id);
      if (agentId) { lifecycle.assertEnabled(agentId); await lifecycle.clean(agentId, agent, source === 'resume'); }
      const preset = agent.session.header.agentPreset;
      // Dreaming has no Nano preset; independent reviewers retain their own retry policy.
      if (preset?.startsWith('nano:') || agent.id.startsWith('dreaming-')) attachModelConnectionRetry(agent, takeConnectionFailure,
        async (turn, signal) => (await models).fallback.canSwitchAfterFailure(agent, turn, signal));
      if (!preset?.startsWith('nano:')) return;
      if(source==='resume' && !agent.session.header.parentSession)await workers.recover(agent);
      const desired = this.configurations.get(preset);
      if (!desired) throw new Error(`Missing Nano configuration for ${preset}`);
      const scopes = await configuration;
      const parent = agent.session.header.parentSession && ctx.agents.get(agent.session.header.parentSession);
      const config = await history.configuration(agent, desired, parent ? (await workflow).childConfiguration(scopes.forAgent(parent)!) : undefined);
      config.workerRuntime=desired.workerRuntime;
      if (source === 'resume' && agent.session.header.origin === 'subagent'
        && foldSubagentDescriptor(agent.session.snapshotEvents().filter(event => agent.session.isOwnSeq(event.seq)))?.mode === 'continuable') {
        // Historical execution choices survive resume, but approval follows the current owner configuration.
        config.approval = desired.approval;
      }
      // A history branch preserves execution choices, while node identity comes from the running host.
      config.executionNode = desired.executionNode;
      if (desired.personal) { config.personal = desired.personal; assertPersonalConfiguration(config); }
      await scopes.attachAgent(agent, config, (await knowledge).isWorkWorker(agent, config));
      await (await approval).attach(agent, config);
      const modelPolicy = await models; await modelPolicy.attach(agent, config);
      if (source === 'resume' && agent.session.header.origin === 'subagent') await captureWorkerTurns(agent.session);
      history.attach(agent, config, () => modelPolicy.route(agent));
      if (agentId) lifecycle.assertEnabled(agentId);
      await (await workflow).recordWorkChild(agent);
      liveAgents.add(agent);
    });
    const toolViews = recordToolPresentations(ctx, process.env.DSH_HOME!);
    ctx.on('session/event', (session, event) => {
      if (event.type === 'turn/end' && session.header.origin === 'subagent' && session.isOwnSeq(event.seq))
        void captureWorkerTurns(session).catch(error=>ctx.logger.error(error));
      const rootSessionId = boundRoot(session.id);
      if (rootSessionId) {
        const discovered = descendantReader.remember(session,event,rootSessionId);
        if (discovered) workChanged(rootSessionId,discovered);
      }
      const source = event.type === 'user/message' ? event.data.source : undefined;
      const hint = {seq:event.seq, type:event.type, time:event.time, data: event.type === 'user/message'
        ? {id:event.data.id, source:source && {kind:source.kind, ...('channel' in source ? {channel:source.channel} : {})}} : {}};
      this.peer.notify('session.event', {sessionId:session.id, rootSessionId, workChild:descendantReader.hasChild(session.id), event:hint},
        ['user/message','turn/end','step/start'].includes(event.type) ? undefined : `session.event:${session.id}:changed`);
    });
    const liveness = setInterval(() => {
      for (const sessionId of this.bindings.keys()) {
        const agent = ctx.agents.get(SessionId(sessionId));
        if (agent?.status === 'running') this.peer.notify('session.liveness', { sessionId });
      }
    }, 15000);
    liveness.unref();
    ctx.effect(() => () => clearInterval(liveness));
    ctx.on('agent/status', ({ agent, status }) => this.peer.notify('session.status', { sessionId: agent.id, status }));
    ctx.on('agent/assistant-stream', ({ agent, frame }) => this.peer.notify('session.stream', { sessionId: agent.id, frame }));
    ctx.on('agent/error', ({ agent, error }) => this.peer.notify('session.error', { sessionId: agent.id, message: String(error) }));
    ctx.on('approval/request', async request => {
      if (disabled(request.agent.id)) return 'cancelled';
      const config = configurationService.forAgent(request.agent);
      const history = request.agent.session.snapshotEvents();
      const turnStart = history.findLast(event => event.type === 'turn/start')?.seq ?? -1;
      const human = history.some(event => event.seq > turnStart && event.type === 'user/message' && isHumanSource(event.data.source));
      const taskTurn=history.some(event=>event.seq>turnStart&&event.type==='user/message'&&event.data.source?.kind==='nano-system'&&['task-execution','task-change'].includes(String(event.data.source.channel)));
      if (request.agent.session.header.origin === 'subagent' || config?.mode === 'global' || !human&&!taskTurn) return 'rejected';
      const approvalSessionId = request.agent.id;
      if(!this.bindings.has(approvalSessionId)) return 'rejected';
      const {outcome, reason, requestId} = await this.waitForApproval({
        sessionId:approvalSessionId, toolName:request.toolName, callId:request.callId, reason:request.reason,
        toolInput:history.findLast(event=>event.type==='tool/call'&&event.data.callId===request.callId)?.data,
      }, request.signal, config?.approval?.askTimeoutSec ?? 600);
      if (outcome === 'rejected' && reason?.trim()) request.agent.inject(freezeMessage({ id: MessageId(randomUUID()), role: 'user' as const, content: [{ type: 'text', text: `The human rejected ${request.toolName} (${request.callId ?? requestId}). Their reason: ${reason}` }],
        source: { kind: 'user-approval', form: 'notice', summary: 'The human rejected this tool call with a reason.' } }));
      return outcome;
    });
    handle('runtime.health', async () => { await stat(process.cwd()); return {healthy:true}; });
    handle('initialize', async value => {
      if (this.accepting) throw new RpcError(-32002, 'Runtime is already initialized');
      const config = value as { recoveryMarkers?: boolean; observationOnly?: boolean; ownerTimezone?: string; initialLogicalNowMs?: number; lifecycle?: Record<string, RuntimeLifecycle>; blockedScheduleIds?: string[]; protocol: number; pendingConfigurations?: {operationId: string; fingerprint: string; config: AgentConfiguration}[]; taskStops?: string[]; taskStopFences?: (string|{sessionId:string;stoppedAt?:string})[]; packageManager?: ProfilePnpmInvocation; agents: AgentConfiguration[]; bindings: SessionBinding[]; providers?: Parameters<NativeModelSetup['apply']>[0] };
      if (config.ownerTimezone) this.ownerTimezone = config.ownerTimezone;
      await deletion?.restore();
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      for (const agent of config.agents) {
        const retired = deletion?.retiredRevision(agent.agentId);
        lifecycle.configure(agent.agentId, retired === undefined ? config.lifecycle?.[agent.agentId] ?? {revision: 1} : {revision: retired, disabled: true, disabledThroughRevision: retired});
        this.cron.block(agent.agentId, lifecycle.current(agent.agentId).disabled === true);
      }
      if (config.protocol !== 1) throw new RpcError(-32002, 'Unsupported Nano runtime protocol');
      this.markRecovery = config.recoveryMarkers === true;
      await this.sessionController;
      await approvalFiber.await();
      await modelFiber.await();
      await descendantReader.ready;
      await subagentRecovery.ready;
      await (await models).fallback.ready;
      await webFiber.await();
      await workflowFiber.await();
      await workflow;
      await knowledgeFiber.await();
      if (typeof config.initialLogicalNowMs === 'number' && Number.isSafeInteger(config.initialLogicalNowMs)) {
        this.logicalNowMs = config.initialLogicalNowMs;
        (await knowledge).dreaming.useClock(this.clockNow);
        this.cron.useClock(this.clockNow);
      }
      // Archive readers must not replay recovery jobs whose saved paths point outside the copy.
      if (config.observationOnly && config.agents.some(agent => !config.lifecycle?.[agent.agentId]?.disabled)) throw new RpcError(-32002, 'Observation-only initialization requires disabled agents');
      if (!config.observationOnly) await (await knowledge).recover(agentId => deletion?.retired(agentId) === true);
      for (const agent of config.observationOnly ? [] : config.agents) await lifecycle.prepare(agent.agentId, async () => {
        if (deletion?.retired(agent.agentId)) return;
        await cancelPersisted(agent.agentId);
        await this.cron.skipMissed(agent.agentId, new Set(config.blockedScheduleIds ?? []));
      });
      await ctx.loader.await();
      configurationService.packageManager(config.packageManager);
      inspectionPackageManager = config.packageManager;
      if (config.providers !== undefined) await modelSetup.apply(config.providers);
      else await webHandle.refresh?.();
      const personal = config.agents.filter(agent => agent.personal);
      if (personal.length && (config.agents.length !== 1 || config.bindings.some(binding => binding.agentId !== personal[0]!.agentId || binding.ownerId !== personal[0]!.personal!.ownerId))) throw new RpcError(-32002, 'Personal runtime must contain only its trusted binding');
      for (const agent of config.agents) {
        if (deletion?.retired(agent.agentId)) continue;
        assertPersonalConfiguration(agent);
        await ctx.llm.resolveModelInfo(agent.provider, agent.model);
        const revisions = new Set([agent.revision, ...config.bindings.filter(binding => binding.agentId === agent.agentId).map(binding => binding.revision)]);
        // Existing Sessions retain their native preset identity while receiving
        // the node's current Agent configuration after a cold restart.
        for (const revision of revisions) {
        const id = `nano:${agent.agentId}:${revision}`;
        this.configurations.set(id, agent);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: agent.agentId } }] }));
        }
      }
      for(const stop of config.taskStopFences??[]) {
        const id=typeof stop==='string'?stop:stop.sessionId;
        this.tasks.interrupt(id,typeof stop==='string'?undefined:stop.stoppedAt);this.interruptedWork.stop(id,typeof stop==='string'?undefined:stop.stoppedAt);
      }
      for(const sessionId of config.taskStops??[])this.tasks.block(sessionId,true);
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      updateServices = { models: await models, knowledge: await knowledge, workflow: await workflow };
      for (const pending of config.pendingConfigurations ?? []) if (!deletion?.retired(pending.config.agentId)) await prepare(pending,true);
      this.accepting = true;
      for (const agent of config.agents) if (!deletion?.retired(agent.agentId)) { await this.configureSchedules(agent); this.peer.notify('heartbeat.subscription', { agentId: agent.agentId, enabled: agent.features?.heartbeat === true }); }
      return { protocol: 1, runtime: '@deepseek-ai/dsh', version: '0.2.2-rc.5', agentDeletion: !!deletion && !config.observationOnly && !personal.length };
    });
    handle('session.capabilities', async value => {
      const agent = await this.agent((value as { sessionId: string }).sessionId);
      return { tools: ctx.tools.schemas(agent).map(tool => tool.name).sort(), skills: await ctx.skills.list({ scope: agent, cwd: agent.session.header.cwd }), prompt: await assembleAgentPrompt(ctx, agent) };
    });
    const preview = async (requested: AgentConfiguration, cwd: string, catalogOnly = false): Promise<unknown> => {
      assertPersonalConfiguration(requested);
      if (!inspection) return this.peer.request('configuration.inspect', {
        method:catalogOnly ? 'catalog' : 'preview', config:requested, cwd,
        providers:modelSetup.inspectionProviders, packageManager:inspectionPackageManager,
      });
      const previewId = `preview-${randomUUID()}`;
      const started = Date.now();
      const observe = (event: string, fields: Record<string,unknown> = {}) => process.stderr.write(`${JSON.stringify({
        component:'dsh.configuration-inspection',event,refresh_id:inspection,request_id:process.env.NANO_CONFIGURATION_INSPECTION_REQUEST,
        preview_id:previewId,agent_id:requested.agentId,elapsed_ms:Date.now()-started,...fields,
      })}\n`);
      const config = { ...requested, agentId: previewId, ...(catalogOnly ? { features: { task_graph: true, memory_curation: true, skill_creation: true, cron_scheduling: true, heartbeat: true } } : {}) };
      const preset = `nano:${previewId}:preview`;
      let unregister: (() => Promise<void>) | undefined;
      let handle: AgentHandle | undefined;
      this.configurations.set(preset, config);
      observe('preview.start');
      try {
        inspectionAbort.signal.throwIfAborted();
        unregister = await ctx.agentPresets.register({ id: preset, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: previewId } }] });
        await this.cron.setEnabled(previewId, true);
        handle = await ctx.agents.create({sessionId:SessionId(previewId),meta:{cwd,agentPreset:preset},signal:inspectionAbort.signal,
          agentOptions:{provider:config.provider,model:config.model,...(config.reasoningEffort?{reasoningEffort:ReasoningEffortId(config.reasoningEffort)}:{}),...(config.maxTokens!==undefined?{maxTokens:config.maxTokens}:{})},
          setup:async agentCtx => {await ctx.agentPresets.mount(agentCtx,preset);}});
        inspectionAbort.signal.throwIfAborted();
        const scopes = await configuration; await scopes.ready(previewId); const scoped = scopes.forAgent(handle.agent)!;
        const catalog = {tools:scopes.catalog(handle.agent),skills:await skillCatalog(scoped,cwd),
          workflows:(await (await workflow).catalog(handle.agent).list()).map(item=>({name:item.name,description:item.meta.description}))};
        observe('catalog.built', {tool_count:catalog.tools.length,skill_count:catalog.skills.length,workflow_count:catalog.workflows.length});
        if (catalogOnly) return catalog;
        const invalid = configurationBlocks(requested, {tools:catalog.tools.map(tool=>tool.name),skills:catalog.skills.map(skill=>skill.name)});
        if (invalid.length) throw new RpcError(-32602, `Invalid capability dependencies: ${JSON.stringify(invalid)}`);
        const assembly = await assembleAgentPrompt(ctx, handle.agent, inspectionAbort.signal);
        return {prompt:[renderPrompt(assembly),renderContextSnapshot(assembly)].filter(Boolean).join('\n\n'),section_count:assembly.sections.length,
          tools:assembly.tools.map(tool=>tool.name),skills:await ctx.skills.list({scope:handle.agent,cwd}),catalog};
      } finally {
        const errors: unknown[] = [];
        // Attempt every owned disposer even if a previous one failed. The outer
        // worker owner enforces a hard process boundary for a hung disposer.
        for (const dispose of [() => handle?.dispose(), () => unregister?.(), () => this.cron.disposeAgent(previewId,true)]) {
          try {await dispose();} catch (error) {errors.push(error);}
        }
        this.configurations.delete(preset);
        observe(errors.length ? 'cleanup.error' : 'cleanup.done');
        if (errors.length) throw new AggregateError(errors,'Temporary preview cleanup failed');
      }
    };
    handle('configuration.catalog', async value => {
      const { agentId, cwd, config: candidate } = value as { agentId?: string; cwd: string; config?: AgentConfiguration };
      const config = candidate ?? [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config) throw new RpcError(-32004, 'Unknown product Agent');
      return preview(config, cwd, true);
    });
    handle('plugins.manage', async value => {
      const command = value as import('./workspace-tools.js').PluginCommand & {agentId: string};
      lifecycle.assertEnabled(command.agentId);
      const entry = [...this.configurations].find(([, config]) => config.agentId === command.agentId);
      if (!entry) throw new RpcError(-32004, 'Unknown product Agent');
      const preset = await ctx.agentPresets.acquireScope(entry[0]);
      try {
        const {view, settled} = await (await configuration).managePlugins(entry[1], command);
        // An accepted background operation must keep its native preset alive through teardown.
        void settled.finally(() => preset[Symbol.asyncDispose]()).catch(error => ctx.logger.error(error));
        return view;
      } catch (error) { await preset[Symbol.asyncDispose](); throw error; }
    });
    handle('configuration.role', async value => {
      const { agentId, workspace, update } = value as { agentId: string; workspace: string; update?: {content: string; version: string | null} };
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!workspace || !config?.workspace || config.knowledge?.memoryMode === 'legacy'
        || await realpath(config.workspace).catch(() => null) !== workspace) return { error: 'role_unavailable' };
      return roleDocument(ctx.fs, workspace, update);
    });
    handle('configuration.preview', value => {
      const { config, cwd } = value as { config: AgentConfiguration; cwd: string };
      return preview(config, cwd);
    });
    handle('knowledge.usage', async value => (await knowledge).usage((value as { agentId: string }).agentId));
    type WorkRead = {sessionId:string; afterSeq?:number; replayFrom?:number; modelVersion?:string; stoppedRevision?:number};
    const disabling = new Map<string, Promise<{confirmed: boolean}>>();
    const workBinding = async ({sessionId, stoppedRevision}: WorkRead) => {
      const binding = this.bindings.get(sessionId);
      if (!binding) throw new RpcError(-32004, 'Session has no trusted product binding');
      if (stoppedRevision === undefined) lifecycle.assertEnabled(binding.agentId);
      else {
        const state = lifecycle.current(binding.agentId);
        if (!state.disabled || state.revision !== stoppedRevision || !(await disabling.get(binding.agentId))?.confirmed)
          throw new RpcError(-32004, 'Work requires a confirmed runtime stop at this revision');
      }
      return binding;
    };
    const projectPage = async (input: WorkRead, firstOwn: number, head: number, eventAt: (seq: number) => SessionEvent | undefined, modelPolicy: ModelPolicy) => {
      const {sessionId, afterSeq = -1, replayFrom} = input;
      const fallback = modelPolicy.fallback;
      return workPage({afterSeq, replayFrom, firstOwn, head, eventAt,
        present:event=>toolViews.one(sessionId,event), model:turn=>fallback.workModel(sessionId,turn), modelVersion:fallback.workVersion(sessionId)});
    };
    handle('session.status', async value => ({status:(await this.agent((value as WorkRead).sessionId)).status}));
    type CatalogEntry = Awaited<ReturnType<DescendantReader['targets']>>[number];
    const workChild = (entry: CatalogEntry, policy: ModelPolicy, engine: NanoWorkflowEngine): RuntimeWorkChild => {
      if (entry.kind !== 'child') return {kind:'diagnostic',id:entry.id,parentId:entry.parentId,reason:entry.reason};
      const workflowRunId = engine.workRelationship(entry.parentId,entry.id);
      return {kind:'child',id:entry.id,parentId:entry.parentId,label:entry.label,throughSeq:entry.throughSeq,mode:entry.mode,
        ...(entry.nativeWorker && {nativeWorker:true}),depth:entry.depth,activity:entry.activity,hasChildren:entry.hasChildren,modelVersion:policy.fallback.workVersion(entry.id),
        ...(workflowRunId ? {workflowRunId} : {})};
    };
    const catalogs = new WorkCatalogPages();
    handle('workflow.read', async value => { const {sessionId,runId} = value as {sessionId:string;runId?:string}; return (await workflow).read(await this.agent(sessionId),runId); });
    handle('workflow.control', async value => { const {sessionId,runId,action,ordinal} = value as {sessionId:string;runId:string;action:string;ordinal?:number}; return (await workflow).control(await this.agent(sessionId),runId,action,ordinal); });
    handle('workflow.catalog', async value => (await workflow).catalog(await this.agent((value as {sessionId:string}).sessionId)).list());
    handle('task.execution.state', value=>{
      const {agentId}=value as {agentId:string};
      if(![...this.configurations.values()].some(config=>config.agentId===agentId))throw new RpcError(-32004,'Unknown product Agent');
      return this.tasks.observe(agentId);
    });
    const personalScopes = async (agentId:string,sessionId:string) => {
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config?.personal) throw new RpcError(-32004,'Unknown personal evidence binding');
      const agent = this.bindings.has(sessionId) ? await this.agent(sessionId) : ctx.agents.get(SessionId(sessionId));
      if (!agent) throw new RpcError(-32004,'Unknown personal evidence binding');
      const lineage = [agent];
      let root = agent;
      // Native children share the product identity, but their own evidence and
      // delegation context must both reach the disclosure reviewer.
      while (!this.bindings.has(root.id) && root.session.header.parentSession) {
        const parent = ctx.agents.get(root.session.header.parentSession);
        if (!parent) throw new RpcError(-32004,'Unknown personal evidence binding');
        lineage.push(parent);
        root = parent;
      }
      if (this.bindings.get(root.id)?.agentId !== agentId) throw new RpcError(-32004,'Unknown personal evidence binding');
      return {config,lineage,root};
    };
    handle('pa.evidence', async value => {
      const {agentId,sessionId} = value as {agentId:string;sessionId:string};
      const {lineage,root}=await personalScopes(agentId,sessionId);
      const evidence = await Promise.all(lineage.map(async scope => {
        const assembly = await assembleAgentPrompt(ctx, scope);
        return {sessionId:scope.id,messages:personalEvidenceMessages(scope),system:renderPrompt(assembly),contexts:renderContextSnapshot(assembly)};
      }));
      return {...evidence[0],rootSessionId:root.id,ancestors:evidence.slice(1)};
    });
    const usage = async (agentId: string, selectionOnly = false) => {
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      const schedules = await this.cron.catalog(agentId);
      const busy: CapabilityTarget[] = [...this.capabilities.busy(agentId, selectionOnly), ...(await knowledge).busyKinds(agentId).map(kind => ({kind: 'feature' as const, name: kind === 'memory' ? 'memory_curation' : 'skill_creation'}))];
      for (const binding of this.bindings.values()) {
        if (binding.agentId !== agentId) continue;
        const agent = ctx.agents.get(SessionId(binding.sessionId));
        if (!agent) continue;
        const events = agent.session.snapshotEvents();
        const lastEnd = events.findLast(event => event.type === 'turn/end')?.seq ?? -1;
        if ([...agent.inbox.nextTurn, ...agent.inbox.nextStep].some(message => message.source.kind === 'nano-system' && message.source.channel === 'heartbeat') || events.some(event => event.seq > lastEnd && event.type === 'user/message' && event.data.source.kind === 'nano-system' && event.data.source.channel === 'heartbeat')) busy.push({kind: 'feature', name: 'heartbeat'});
        if ([...agent.inbox.nextTurn, ...agent.inbox.nextStep].some(message => message.source.kind === 'nano-system' && ['proactive_review', 'proactive_nightly'].includes(String(message.source.channel))) || events.some(event => event.seq > lastEnd && event.type === 'user/message' && event.data.source.kind === 'nano-system' && ['proactive_review', 'proactive_nightly'].includes(String(event.data.source.channel)))) busy.push({kind: 'feature', name: 'proactive_planning'});
      }
      return {checked_at: new Date(this.clockNow()).toISOString(), active_schedules: schedules.filter(task => task.status === 'active').length, busy};
    };
    const prepare = async (input: {operationId: string; fingerprint: string; config: AgentConfiguration; initialRole?: string}, protectChat = false) => {
      if (!input.operationId || !input.fingerprint) throw new RpcError(-32602, 'Configuration operation identity is required');
      const previous = [...this.configurations.values()].find(config => config.agentId === input.config.agentId);
      const catalog = await preview(input.config, input.config.workspace ?? previous?.workspace ?? process.cwd(), true) as {tools: {name: string}[]; skills: {name: string}[]};
      const prepared = await this.capabilities.prepare(input, previous, {tools: catalog.tools.map(tool => tool.name), skills: catalog.skills.map(skill => skill.name)},
        async () => previous ? {...await usage(input.config.agentId), toolSelectionBusy: this.capabilities.busy(input.config.agentId, true)} : {active_schedules: 0, busy: []});
      if (prepared.ready && input.initialRole !== undefined) {
        const workspace = input.config.workspace && await realpath(input.config.workspace).catch(() => null);
        const role = workspace && input.config.knowledge?.memoryMode !== 'legacy'
          ? await initializeRoleDocument(ctx.fs, workspace, input.initialRole)
          : {error: 'role_unavailable' as const};
        if ('error' in role) {
          this.capabilities.release(input.config.agentId, input.operationId);
          return {ready: false, error_code: role.error, message: role.error === 'role_conflict'
            ? 'This workspace already has a different role agreement. Leave the initial role empty to keep it, or choose another workspace.'
            : 'Initial ROLE could not be saved'};
        }
      }
      const prevScope = previous?.collaborationScope ?? 'team';
      const nextScope = input.config.collaborationScope ?? 'team';
      const tightening = (prevScope === 'team' && nextScope !== 'team') || (prevScope === 'project' && nextScope === 'owner_only');
      if (protectChat && previous && prepared.ready && tightening)
        this.chatScope.reserve(input.config.agentId,input.operationId);
      return prepared;
    };
    // The editor asks which selections are in use, not whether native workers are active.
    handle('configuration.usage', value => usage((value as {agentId: string}).agentId, true));
    handle('configuration.prepare', value => prepare(value as Parameters<typeof prepare>[0],true));
    handle('configuration.release', value => { const {agentId, operationId} = value as {agentId: string; operationId: string}; this.capabilities.release(agentId, operationId); this.chatScope.release(agentId,operationId); return {released: true}; });
    handle('configuration.restrictChat', value => {
      const {agentId,changes,operationId}=value as {agentId:string;operationId?:string;changes:Parameters<ChatScope['restrict']>[1]};
      return this.chatScope.restrict(agentId,changes).then(result=>{if(operationId)this.chatScope.release(agentId,operationId);return result;});
    });
    handle('configuration.apply', async value => {
      const {operationId = `runtime:${(value as AgentConfiguration).revision}`, fingerprint = (value as AgentConfiguration).revision, ...next} = value as AgentConfiguration & {operationId?: string; fingerprint?: string};
      if (!this.capabilities.matches(next.agentId, operationId, fingerprint, next)) {
        const prepared = await prepare({operationId, fingerprint, config: next});
        if (!prepared.ready) return {effective: false, ...prepared};
      }
      try {
      assertPersonalConfiguration(next);
      const host = [...this.configurations.values()][0];
      if (host && (Boolean(host.personal) !== Boolean(next.personal) || host.personal && (host.agentId !== next.agentId || JSON.stringify(host.personal) !== JSON.stringify(next.personal)))) throw new RpcError(-32002, 'Configuration cannot change runtime partition');
      await ctx.llm.resolveModelInfo(next.provider, next.model);
      const previous = [...this.configurations.values()].find(config => config.agentId === next.agentId);
      if (previous && previous.mode !== next.mode) throw new RpcError(-32602, 'Work mode is immutable');
      // A display-name revision does not change execution and must not wait for a long-running goal.
      const scopes = await configuration, modelPolicy = await models;
      const metadataOnly = previous && scopes.applyRevisionOnly(next);
      if (metadataOnly) await modelPolicy.advanceRevision(next);
      if (previous && !metadataOnly) {
        if (next.personal) {
          const nextEffective = effectiveFeatures(next.features, definitionsForRole(true), capabilityDraft(next));
          if (nextEffective.proactive_planning !== true) {
            for (const binding of this.bindings.values()) {
              if (binding.agentId !== next.agentId) continue;
              const boundAgent = ctx.agents.get(SessionId(binding.sessionId));
              if (!boundAgent) continue;
              for (const pending of [...boundAgent.inbox.nextTurn, ...boundAgent.inbox.nextStep]) {
                if (pending.source.kind === 'nano-system' && ['proactive_review', 'proactive_nightly'].includes(String(pending.source.channel))) {
                  boundAgent.inbox.remove(pending.id);
                }
              }
              const events = boundAgent.session.snapshotEvents();
              const lastEnd = events.findLast(event => event.type === 'turn/end')?.seq ?? -1;
              const openInputs = events.filter(event => event.seq > lastEnd && event.type === 'user/message');
              if (openInputs.length > 0 && openInputs.every(event => event.type === 'user/message' && event.data.source.kind === 'nano-system' && ['proactive_review', 'proactive_nightly'].includes(String(event.data.source.channel)))) {
                boundAgent.cancel({ kind: 'user' }, { keepInbox: true });
              }
            }
          }
        }
        await (await knowledge).dreaming.configurationChanging(next);
        await (await configuration).restrictSelection(next);
        const restricted = { ...previous.features };
        for (const [key, enabled] of Object.entries(next.features ?? {})) if (!enabled) restricted[key] = false;
        await (await configuration).setFeatures(next.agentId, restricted);

        await (await configuration).whenIdle(next.agentId);
        await (await models).changed(next);
        await (await configuration).setConfiguration(next);
      }
      const id = `nano:${next.agentId}:${next.revision}`;
      if (!this.configurations.has(id)) {
        this.configurations.set(id, previous ?? next);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: next.agentId } }] }));
      }
      await this.configureSchedules(next);
      this.peer.notify('heartbeat.subscription', { agentId: next.agentId, enabled: next.features?.heartbeat === true });
      if (!metadataOnly) this.tasks.configured(next.agentId);
      return { effective: true, revision: next.revision };
      } finally { this.capabilities.release(next.agentId, operationId); this.chatScope.release(next.agentId, operationId); }
    });
    for (const method of ['configuration.features', 'schedule.enabled']) handle(method, () => {
      throw new RpcError(-32602, 'Use configuration.prepare and configuration.apply with a complete candidate');
    });
    handle('schedule.deleted.notify',async value=>{
      const {agentId,sessionId,inputId,content}=value as {agentId:string;sessionId:string;inputId:string;content:Submit['content']};
      if(!inputId.startsWith('schedule-deleted:'))throw new RpcError(-32602,'Invalid Schedule change identity');
      const notifyKey = `${sessionId}\0${inputId}`;
      const existingNotify = scheduleNotifyPending.get(notifyKey);
      if (existingNotify) return existingNotify;
      const runNotify = (async (): Promise<{durable: true}> => {
        this.lifecycle.assertEnabled(agentId);
        const {agent: initialAgent, root}=await this.owned.resolveManaged(sessionId,agentId);
        if(root.sessionId===sessionId)return await this.submit({sessionId,inputId,content,mode:this.tasks.passive(root.sessionId)?'inject':'followup',source:{kind:'system',actorId:agentId,channel:'schedule-change',messageId:inputId}}) as {durable: true};
        // Preserve the native child's identity and SubagentManager residency; never redirect to root.
        const revision=this.lifecycle.current(agentId).revision;
        const fallback=(await models).fallback;
        const admitted=await ctx.attachments.admitPromptContent(content);
        const passive=this.tasks.passive(root.sessionId);
        const message:UserMessage=freezeMessage({id:MessageId(inputId),role:'user' as const,content:admitted,source:{kind:'nano-system',actorId:agentId,channel:'schedule-change',messageId:inputId,lifecycle_revision:revision}});
        let agent = initialAgent;
        let placed = false;
        if (!agent) {
          using coldView = await ctx.sessionQuery.observeSession(SessionId(sessionId));
          const alreadyRecorded = coldView.events.slice(coldView.inheritedEventCount).some(event =>
            (event.type === 'user/message' && event.data.id === inputId) ||
            (event.type === 'agent/inbox/spliced' && event.data.inserted.some(item => item.id === inputId)));
          if (alreadyRecorded) return {durable: true};
          const hold: {gate: PromiseWithResolvers<void>; maintenance?: Promise<unknown>} = {gate: Promise.withResolvers<void>()};
          scheduleNotifyHolds.set(sessionId, hold);
          try {
            const receipt = await ctx.subagents.prompt({
              childSessionId: SessionId(sessionId),
              requestId: `nano-runtime-schedule-change:${inputId}` as import('@deepseek-ai/dsh-subagent').SubagentPromptRequestId,
              delivery: 'steer',
              content,
            }, AbortSignal.timeout(30_000));
            agent = ctx.agents.get(SessionId(sessionId));
            this.lifecycle.assertEnabled(agentId);
            if(this.lifecycle.current(agentId).revision!==revision)throw new Error('stale_lifecycle');
            if (agent && hold.maintenance) {
              agent.inbox.remove(receipt.messageId);
              if (!passive && !fallback.nativeEvidence(agent, inputId).accepted) {
                agent.followup(message);
                placed = true;
              }
              hold.gate.resolve();
              await hold.maintenance;
              if (passive && !fallback.nativeEvidence(agent, inputId).accepted) {
                agent.inject(message);
                placed = true;
              }
            }
          } finally {
            scheduleNotifyHolds.delete(sessionId);
            hold.gate.resolve();
          }
        }
        if (!agent) throw new Error('Child schedule notification failed to establish residency');
        this.lifecycle.assertEnabled(agentId);
        if(this.lifecycle.current(agentId).revision!==revision)throw new Error('stale_lifecycle');
        if(!placed && !fallback.nativeEvidence(agent,inputId).accepted){
          if(passive)agent.inject(message);else agent.followup(message);
        }
        if (!await ctx.sessions.flush(agent.session)) throw new RpcError(-32005, 'Session has no persistence barrier');
        return {durable:true};
      })().finally(() => { scheduleNotifyPending.delete(notifyKey); });
      scheduleNotifyPending.set(notifyKey, runNotify);
      return runNotify;
    });
    const scheduleOwner = (agentId: string, sessionId?: string) => {
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      if (sessionId && this.ownerOf(sessionId) !== agentId) throw new RpcError(-32004, 'Schedule Session does not belong to this Agent');
    };
    const scheduleHandlers = {
      jobs: async ({agentId, sessionId}) => {
        scheduleOwner(agentId, sessionId);
        const tasks = await this.cron.catalog(agentId);
        return tasks.map(({id, title, prompt, sessionId, status, lastDelivery: _delivery, ...schedule}) => ({
          id, sessionId, name: title, instruction: prompt, schedule, enabled: status === 'active', delete_after_run: false,
        }));
      },
      run: async ({agentId, sessionId, args}) => {
        scheduleOwner(agentId, sessionId);
        const key = `schedule-command:${agentId}:${randomUUID()}`;
        if (!this.capabilities.begin(key, agentId, {kind: 'tool', name: 'schedule_run'})) throw new RpcError(-32003, 'Capability is reserved by configuration');
        try {
          if (this.capabilities.held(agentId, {kind: 'feature', name: 'cron_scheduling'}) || this.capabilities.held(agentId, {kind: 'tool', name: 'schedule_run'})) throw new RpcError(-32003, 'Capability is reserved by configuration');
          const tasks = await this.cron.catalog(agentId);
          const task = tasks.find(task => task.id === args.id && task.sessionId === sessionId);
          if (!task || task.status !== 'active') throw new RpcError(-32602, 'Schedule does not exist or is inactive');
          const fallback = (await models).fallback;
          const agent = await this.agent(sessionId);
          if (!fallback.nativeEvidence(agent, args.inputId).accepted) {
            agent.followup(freezeMessage({ id: MessageId(args.inputId), role: 'user' as const,
              content: [{ type: 'text', text: `Manual run of an existing schedule. This is configured work, not live human permission.\nTitle: ${task.title}\nSaved instructions:\n${task.prompt}` }],
              source: { kind: 'schedule' as const, scheduleId: task.id, triggerKind: 'manual' } }));
          }
          await this.flush(agent); return { inputId: args.inputId, ...fallback.nativeEvidence(agent, args.inputId) };
        } finally { this.capabilities.end(key); }
      },
      catalog: input => {
        scheduleOwner(input.agentId, input.sessionId);
        return this.cron.catalog(input.agentId);
      },
      history: input => {
        scheduleOwner(input.agentId, input.sessionId);
        return this.cron.history(input.agentId, input.sessionId, input.args.id, input.args.limit);
      },
      create: async input => {
        scheduleOwner(input.agentId, input.sessionId);
        if (this.cron.isLogicalClock) {
          const created = await this.cron.createAtLogicalClock(input.agentId, input.sessionId, input.args as unknown as Record<string, unknown>);
          if ('code' in created) throw new RpcError(-32602, created.message);
          return created;
        }
        return this.cron.withSchedule(input.agentId, input.action, service =>
          createSessionSchedule(service, input.sessionId, input.args));
      },
      list: input => {
        scheduleOwner(input.agentId, input.sessionId);
        if (this.cron.isLogicalClock) return this.cron.listAtLogicalClock(input.agentId, input.sessionId);
        return this.cron.withSchedule(input.agentId, input.action, service => listSessionSchedules(service, input.sessionId));
      },
      update: input => {
        scheduleOwner(input.agentId, input.sessionId);
        return this.cron.withSchedule(input.agentId, input.action, service =>
          updateSessionSchedule(service, input.sessionId, input.args));
      },
      delete: input => {
        scheduleOwner(input.agentId, input.sessionId);
        return this.cron.withSchedule(input.agentId, input.action, service =>
          deleteSessionSchedule(service, input.sessionId, input.args.id));
      },
    } satisfies ScheduleHandlerMap;
    const productHandlers = {
      'session.ensure': value => this.ensure(value),
      'session.recovery.probe': value => {
        const {sessionId, afterSeq, localWork} = value;
        if (!Number.isSafeInteger(afterSeq) || afterSeq < -1) throw new RpcError(-32602, 'Invalid recovery cursor');
        return this.owned.recoveryProbe(sessionId, afterSeq, localWork);
      },
      'session.submit': input => {
        const key = `${input.sessionId}\0${input.inputId}`;
        const running = this.inputs.get(key);
        if (running) return running;
        const task = this.submit(input).finally(() => { this.inputs.delete(key); });
        this.inputs.set(key, task);
        return task;
      },
      'configuration.selection': async value => {
        const { agentId, cwd } = value;
        const entry = [...this.configurations].find(([, config]) => config.agentId === agentId);
        if (!entry) throw new RpcError(-32004, 'Unknown product Agent');
        await using preset = await ctx.agentPresets.acquireScope(entry[0]);
        const key = {}; const diagnostic = createScope(ctx, key, { parent: preset.key });
        try {
          await diagnostic.ctx.plugin(SelectedSkills, {config: entry[1], isWorkWorker: false}).await();
          return { tools: (await configuration).selection(entry[1], ctx.tools.schemas(key).map(tool => tool.name)),
            skills: await ctx.skills.list({ scope: key, cwd }) };
        } finally { await diagnostic.dispose(); }
      },
      'session.fork': async value => {
        const { sessionId, messageId, operationId } = value;
        const source = await this.agent(sessionId); const binding = this.bindings.get(sessionId)!;
        const desired = this.configurations.get(source.session.header.agentPreset!)!;
        const result = await history.fork(source, messageId, operationId, desired, this.owned);
        this.bindings.set(result.sessionId, { ...binding, sessionId: result.sessionId });
        return { ...result, revision: binding.revision };
      },
      'session.export': async value => {
        const { sessionId } = value;
        if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
        return { path: await history.path(sessionId) };
      },
      'knowledge.sources.sync': async input => (await knowledge).documents.syncSources(input.agentId, input.snapshot),
      'knowledge.sources.pending': async value => { await (await knowledge).documents.sourcesPending(value.agentId); return { pending: true }; },
      'knowledge.facts': async () => ({ facts: await (await knowledge).facts(), reviews: await (await knowledge).reviews() }),
      'knowledge.acknowledge': async value => { await (await knowledge).acknowledge(value.id); return { acknowledged: true }; },
      'session.lookup': async value => {
        const { sessionId, inputId } = value;
        const agent = await this.agent(sessionId);
        await this.flush(agent);
        const evidence=(await models).fallback.evidence(agent, inputId);
        const event=evidence.consumedSeq === undefined ? undefined : agent.session.eventAt(SessionSeq(evidence.consumedSeq));
        const message=event?.type === 'user/message' ? event.data : [...agent.inbox.nextStep,...agent.inbox.nextTurn].find(m=>m.id===inputId);
        return message && 'nanoTeamChat' in message.source && message.source.nanoTeamChat ?
          {...evidence,providerDelivered:await this.chatScope.delivered(sessionId,inputId)} : evidence;
      },
      'session.work.check': async input => {
        await workBinding(input);
        const id = SessionId(input.sessionId), fallback = (await models).fallback;
        const rootSettled = await descendantReader.settled(id, {[id]:input.afterSeq ?? -1}, () =>
          fallback.hasActive(id) || input.modelVersion!==fallback.workVersion(id), false);
        return {rootSettled:rootSettled && !(await inboxDelivery.pending(input.sessionId)).length &&
          !await workers.hasPendingWork(input.sessionId) && !await descendantReader.hasInterruptedDescendants(id)};
      },
      'session.publication': async value => {
        const {sessionId, afterSeq, callId, readIds, head: upper} = value;
        await workBinding({sessionId});
        const {session} = await this.agent(sessionId);
        const head = Math.min(session.seq - 1, upper ?? Infinity);
        const first = Math.max(session.inheritedEventCount, afterSeq + 1);
        const slice = (from: number, to: number) => session.snapshotEvents(SessionLogOffset(from), SessionLogOffset(to));
        let call: RuntimePublicationEvidence['call'];
        if (callId !== undefined) for (let end = head + 1; end > first && !call;) {
          const start = Math.max(first, end - workPageItems);
          const event = slice(start, end).findLast(event => event.type === 'tool/call' && event.data.callId === callId);
          if (event?.type === 'tool/call') call = {turn: event.data.turn, seq: event.seq};
          end = start;
        }
        if (!await ctx.sessions.flush(session)) throw new RpcError(-32005, 'Publication has no persistence barrier');
        lifecycle.assertEnabled(this.bindings.get(sessionId)!.agentId);
        const reads: RuntimePublicationEvidence['reads'] = [];
        const pending = new Set(readIds);
        const fallback = pending.size ? (await models).fallback : undefined;
        let throughSeq = first - 1, bytes = 128;
        if (!pending.size) throughSeq = head;
        scan: for (let start = first; pending.size && start <= head; start += workPageItems) {
          for (const event of slice(start, Math.min(start + workPageItems, head + 1))) {
            if (event.type === 'tool/result' && !event.data.message.isError && pending.has(event.data.message.toolCallId)) {
              const {type, seq, time, data:{turn, message}} = event;
              const read = {type, seq, time, data:{turn:fallback?.workModel(sessionId,turn)?.turn ?? turn, message}};
              const size = jsonBytes(read);
              if (reads.length && (bytes + size > workPageBytes || reads.length >= workPageItems)) break scan;
              reads.push(read);
              bytes += size;
            }
            throughSeq = event.seq;
          }
        }
        return {durable:true, call, reads, throughSeq, head} satisfies RuntimePublicationEvidence;
      },
      'session.inbox-delivered.confirm': async input => {
        await workBinding(input); await inboxDelivery.confirm(input.sessionId,input.inputIds); return {};
      },
      'session.work.workers.confirm': async input => {
        await workBinding(input);
        await workers.confirmWork(input.sessionId,input.changes);
        return {};
      },
      'session.work.root': async input => {
        await workBinding(input);
        const id = SessionId(input.sessionId), policy = await models;
        const workerPage=await workers.workPage(input.sessionId);
        const withWorkers=(page:RuntimeWorkPage) => ({...page,workerChanges:workerPage.page,more:page.more || workerPage.more});
        if (input.stoppedRevision !== undefined) {
          if (!await ctx.sessionPersistence.stat(id))
            return withWorkers(await projectPage(input, 0, -1, () => undefined, policy));
          using cut = await ctx.sessionQuery.observeSession(id, {projectionMode:'none'});
          return withWorkers(await projectPage(input, cut.inheritedEventCount, cut.cursor, seq => cut.events[seq], policy));
        }
        const {session} = await this.agent(id);
        const head = session.seq - 1;
        if (!await ctx.sessions.flush(session)) throw new RpcError(-32005, 'Root Session has no persistence barrier');
        const page = await projectPage(input, session.inheritedEventCount, head,
          seq => session.snapshotEvents(SessionLogOffset(seq), SessionLogOffset(seq + 1))[0], policy);
        const inboxDelivered = await inboxDelivery.pending(input.sessionId);
        return withWorkers({...page,inboxDelivered,more:page.more || inboxDelivered.length === 256});
      },
      'session.work.children': async input => {
        await workBinding(input);
        const root = SessionId(input.sessionId), policy = await models, engine = await workflow;
        await engine.ready;
        return catalogs.read(root,input.afterId,input.stoppedRevision,async function* () {
          if (!ctx.sessions.get(root) && !await ctx.sessionPersistence.stat(root)) return;
          for await (const entry of descendantReader.catalog(root)) yield workChild(entry,policy,engine);
        });
      },
      'session.work.targets': async input => {
        await workBinding(input);
        const policy = await models, engine = await workflow;
        await engine.ready;
        const targets = await descendantReader.targets(SessionId(input.sessionId),SessionId(input.childId));
        return {children:targets.map(target=>workChild(target,policy,engine))} satisfies RuntimeWorkCatalog;
      },
      'session.work.child': async input => {
        await workBinding(input);
        const id = SessionId(input.childId), policy = await models;
        const modelVersion=policy.fallback.workVersion(id), afterSeq=input.afterSeq ?? -1;
        const page=await descendantReader.eventPage(SessionId(input.sessionId),id,afterSeq,input.modelVersion!==modelVersion,
          (session,head)=>projectPage({...input,sessionId:id},session.inheritedEventCount,head,
            seq=>session.snapshotEvents(SessionLogOffset(seq),SessionLogOffset(seq+1))[0],policy),
          cut=>projectPage({...input,sessionId:id},cut.inheritedEventCount,cut.cursor,seq=>cut.events[seq],policy));
        return page ?? {durable:true,events:[],modelRuns:[],modelVersion,throughSeq:afterSeq,more:false} satisfies RuntimeWorkPage;
      },
      'session.observe': async value => {
        const { sessionId, afterSeq = -1 } = value;
        const agent = await this.agent(sessionId);
        const events = agent.session.snapshotEvents().filter(event => agent.session.isOwnSeq(event.seq) && event.seq > afterSeq);
        await this.flush(agent);
        const runs = structuredClone((await models).fallback.list(sessionId));
        const presented = await toolViews(sessionId, events);
        // Native event interfaces have named fields. Plugins may contribute additional data.
        if (!presented.every((event): event is SessionEvent & RuntimeEvent => workObject(event.data)))
          throw new RpcError(-32000, 'Invalid native event data');
        return { status: agent.status, events: presented, modelRuns: runs, modelVersion: (await models).fallback.workVersion(sessionId), approvals: await (await approval).entries(sessionId), throughSeq: events.at(-1)?.seq ?? afterSeq, durable: true };
      },
      'workflow.pending': async () => (await workflow).pending(),
      'workflow.acknowledge': async value => { await (await workflow).acknowledge(value.runId); return {acknowledged:true}; },
      'session.command': async value => {
        const request = value;
        if (request.action === 'config') {
          const match = /^workflowSizeGuideline\s+(unrestricted|small|medium|large)$/.exec(request.argument ?? '');
          if (!match) return {text: '用法: /config workflowSizeGuideline <unrestricted|small|medium|large>'};
          const agent = await this.agent(request.sessionId);
          const config = (await configuration).forAgent(agent)!;
          await this.peer.request('configuration.workflow', {agentId: config.agentId, guideline: match[1]});
          return {text: `Workflow size guideline: ${match[1]}`};
        }
        if(request.action === 'workflows') return (await workflow).command(await this.agent(request.sessionId),request.id,request.argument??'');
        return (await models).command(await this.agent(request.sessionId), request);
      },
      'task.execution.changed': value=>{this.tasks.changed(value.agentId,value.reset!==false);return {ok:true};},
      'task.execution.block': value=>{const {sessionId,blocked}=value;this.tasks.block(sessionId,blocked);return {ok:true};},
      'session.cancel': async value => {
        const { sessionId,stoppedAt,settleTaskContext } = value;
        this.interruptedWork.stop(sessionId,stoppedAt);
        await workers.stopRoot(sessionId);
        this.tasks.interrupt(sessionId,stoppedAt);
        const agent = await this.agent(sessionId);
        (await models).cancelCommands(sessionId);
        (await models).fallback.interrupt(agent);
        const workflowCount = await (await workflow).stopSession(sessionId);
        const wasRunning = agent.status === 'running' || workflowCount > 0;
        agent.cancel({ kind: 'user' }, { keepInbox: true });
        await agent.whenIdle();
        await this.flush(agent);
        if (settleTaskContext) await taskContext.reconcile(agent);
        return { stopped: true, wasRunning };
      },
      'approval.answer': value => {
        const { requestId, decision, reason } = value;
        if (!['allowed-once', 'rejected'].includes(decision)) throw new RpcError(-32602, 'Invalid approval decision');
        const answer = this.approvals.get(requestId);
        if (!answer) throw new RpcError(-32004, 'Approval is no longer pending');
        answer(decision, reason);
        return { answered: true };
      },
      'pa.review': async value => {
        const {agentId,kind,evidence,sessionId,callId} = value;
        const config = [...this.configurations.values()].find(config => config.agentId === agentId);
        if (!config?.personal) throw new RpcError(-32004, 'Unknown personal Agent');
        if(kind==='input')return reviewPersonal(ctx,config,'input',evidence);
        if(kind!=='action'||!sessionId)throw new RpcError(-32602,'Personal disclosure requires a bound session');
        const {lineage}=await personalScopes(agentId,sessionId);
        try {
          return await (await codex).reviewDisclosure({agent:lineage[0]!,config,action:personalReviewAction(evidence),images:await personalReviewImages(ctx,evidence),
            evidence:async()=>{
              const scopes=await Promise.all([...lineage].reverse().map(async scope=>{
                const assembly=await assembleAgentPrompt(ctx, scope);
                const rows=await (await approval).sources.history(scope,scope.id===sessionId?callId:undefined,false,{toolResults:true,fullAssistant:true,privateContext:true});
                return [{context:renderPrompt(assembly),origin:{kind:'runtime-system'},session_id:scope.id},
                  {context:renderContextSnapshot(assembly),origin:{kind:'runtime-context'},session_id:scope.id},
                  ...rows.map(row=>({...row,session_id:scope.id}))];
              }));
              return scopes.flat();
            }});
        } catch(error) {return {decision:'unavailable',reason:`Independent review unavailable: ${String(error)}`};}
      },
      'task.context.passive': async value=>{
        const {agentId,sessionId,messages,revoked}=value;
        if(this.bindings.get(sessionId)?.agentId!==agentId)throw new RpcError(-32602,'Invalid Task context identity');
        this.lifecycle.assertEnabled(agentId);const agent=await this.agent(sessionId);
        for(const id of revoked)agent.inbox.remove(MessageId(id));
        for(const message of messages)await this.submit({sessionId,inputId:message.inputId,content:message.content,mode:'inject',source:{kind:'system',channel:'task-context',actorId:agentId,messageId:message.inputId,conversationId:message.conversationId,...(message.humanControl?{humanTaskControl:message.humanControl}:{})}});
        await this.ctx.sessions.flush(agent.session);return {durable:true};
      },
      'runtime.timezone': value => {
        this.ownerTimezone = value.timezone;
        return { ok: true };
      },
      'runtime.clock.advance': async value => {
        if (!this.cron.isLogicalClock) throw new RpcError(-32002, 'Logical clock is not enabled on this runtime');
        if (value.nowMs < (this.logicalNowMs ?? 0)) throw new RpcError(-32602, 'Logical clock cannot move backwards');
        this.logicalNowMs = value.nowMs;
        const activeAgentIds = [...new Set([...this.configurations.values()].map(item => item.agentId))]
          .filter(agentId => !lifecycle.current(agentId).disabled && deletion?.retired(agentId) !== true);
        const settleRuntime = async () => {
          for (;;) {
            const live = [...this.bindings.keys()]
              .map(id => ctx.agents.get(SessionId(id)))
              .filter((agent): agent is Agent => !!agent);
            await Promise.all(live.map(agent => agent.whenIdle()));
            for (const agentId of activeAgentIds) await (await knowledge).dreaming.whenIdle(agentId);
            const workerPending = (await Promise.all([...this.bindings.keys()].map(id => workers.hasPendingWork(id)))).some(Boolean);
            if (!activeSubagents.size && !workerPending && live.every(agent => agent.status === 'idle' && !agent.inbox.nextTurn.length && !agent.inbox.nextStep.length)) {
              await Promise.all(live.map(agent => this.flush(agent)));
              break;
            }
            if (activeSubagents.size) {
              await new Promise<void>(resolve => { wakeSubagentIdle = resolve; setTimeout(resolve, 100).unref(); });
            } else {
              await new Promise<void>(resolve => { setTimeout(resolve, 50).unref(); });
            }
          }
        };
        await this.cron.advanceClock(activeAgentIds, value.nowMs, async (agentId, sessionId, msg) => {
          const agent = await this.agent(sessionId);
          const stamped = freezeMessage({
            ...msg,
            source: { ...msg.source, lifecycle_revision: lifecycle.current(agentId).revision },
          });
          agent.followup(stamped);
          await this.flush(agent);
        });
        if (value.settle) await settleRuntime();
        for (const agentId of activeAgentIds) {
          await (await knowledge).dreaming.tick(agentId, value.nowMs);
          await (await knowledge).dreaming.whenIdle(agentId);
        }
        if (value.settle) await settleRuntime();
        return { nowMs: value.nowMs };
      },
      'schedule.wait.inspect': async value=>{
        const {agentId,sessionId,scheduleId}=value;
        const config=[...this.configurations.values()].find(config=>config.agentId===agentId);
        const nowMs=this.clockNow();
        const checked_at=new Date(nowMs).toISOString();
        if(!config||this.bindings.get(sessionId)?.agentId!==agentId)return {valid:false,checked_at,reason_code:'owner_or_session_mismatch'};
        const catalog=await this.cron.catalog(agentId);
        const task=catalog.find(t=>t.id===scheduleId);
        if(task&&task.sessionId!==sessionId)return {valid:false,checked_at,reason_code:'owner_or_session_mismatch'};
        const agent=await this.agent(sessionId);await this.flush(agent);
        const pending=scheduleEvidence(agent.session.snapshotEvents()).find(item=>item.scheduleId===scheduleId&&item.trigger==='timed'&&item.pending&&item.consumedSeq===undefined);
        if(pending)return {valid:true,checked_at,owner_agent_id:agentId,session_id:sessionId,next_check_at:pending.scheduledAt,pending_occurrence_id:pending.messageId};
        const reason_code=!task?'missing':task.status!=='active'?'inactive':!(Date.parse(task.scheduledAt)>nowMs)?'expired':undefined;
        return {valid:!reason_code,checked_at,owner_agent_id:agentId,session_id:sessionId,next_check_at:task?.scheduledAt,...(reason_code?{reason_code}:{})};
      },
      'schedule.evidence': async value => {
        const agent = await this.agent(value.sessionId); await this.flush(agent);
        return scheduleEvidence(agent.session.snapshotEvents());
      },
      'schedule.command': scheduleHandlers,
    } satisfies RuntimeHandlerMap;
    const pullLanes: Partial<Record<RuntimeMethod, {pull: string}>> = {
      'session.publication': {pull:'publication'},
      'session.work.root': {pull:'work-root'},
      'session.work.children': {pull:'work-descendants'},
      'session.work.targets': {pull:'work-descendants'},
      'session.work.child': {pull:'work-descendants'},
    };
    for (const method of runtimeMethods) {
      handle(method, async raw => {
        try { return await dispatchRuntime(productHandlers, method, raw); }
        catch (error) {
          if (error instanceof RuntimeRpcValidationError) throw new RpcError(-32602, error.message);
          throw error;
        }
      }, pullLanes[method]);
    }
    const deleting = new Set<string>();
    const removeAgentExecution = async (value: unknown, purge: boolean) => {
      const {agentId, revision, operationId, plan, knownSessionIds = []} = value as {
        agentId: string; revision: number; operationId: string; plan: unknown; knownSessionIds?: string[];
      };
      if (!this.accepting || !deletion) throw new Error('Scoped Agent deletion is unavailable');
      if (!agentId || !Number.isSafeInteger(revision) || !Array.isArray(knownSessionIds)) throw new Error('Invalid Agent deletion identity');
      const config = [...this.configurations.values()].find(item => item.agentId === agentId);
      if (config?.personal || (!config && deletion.retiredRevision(agentId) !== revision)) throw new Error('Unknown ordinary product Agent');
      if (deleting.has(agentId)) throw new Error('Agent deletion is already in progress');
      deleting.add(agentId);
      try {
        const stopped = await disabling.get(agentId);
        const current = lifecycle.current(agentId);
        if (!current.disabled || current.revision !== revision || stopped?.confirmed === false ||
          ctx.agents.list().some(agent => this.ownerOf(agent.id) === agentId)) throw new Error('Agent stop has not been confirmed');
        await deletion.begin(agentId, revision);
        await trajectory.closeAgent(agentId);
        await deletion.drain(agentId);
        await trajectory.closeAgent(agentId);
        if (!purge) {
          const {known, links} = ownedLinks(ctx, agentId);
          return await deletion.plan(agentId, revision, this.bindings, [...knownSessionIds, ...known], preset => this.configurations.get(preset)?.agentId, links);
        }
        const sessionIds = await deletion.purge(agentId, revision, operationId, plan);
        const ids = new Set(sessionIds);
        await Promise.all([
          (await models).fallback.forget(ids),
          inboxDelivery.forget(ids), this.chatScope.forget(ids), workers.forget(ids),
          ctx.nanoTrajectoryRuns.forget(ids),
          ctx.nanoTrajectoryAttachments.settle(ids),
          toolViews.purge(ids),
        ]);
        await purgeDerived(ctx, process.env.DSH_HOME!, agentId, sessionIds);
        descendantReader.forget(ids);
        (await workflow).forgetWorkChildren(ids);
        for (const id of ids) await catalogs.forget(id);
        await this.cron.disposeAgent(agentId, true);
        for (const id of sessionIds) if (this.bindings.get(id)?.agentId === agentId) this.bindings.delete(id);
        for (const [preset, item] of this.configurations) if (item.agentId === agentId) this.configurations.delete(preset);
        disabling.delete(agentId);
        return {purged: true, sessionIds};
      } finally { deleting.delete(agentId); }
    };
    this.peer.handle('agent.deletion.plan', value => removeAgentExecution(value, false));
    this.peer.handle('agent.deletion.purge', value => removeAgentExecution(value, true));
    this.peer.handle('agent.disable', value => {
      const {agentId, revision} = value as {agentId: string; revision: number};
      if (deletion?.retiredRevision(agentId) === revision) return {confirmed: true};
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new Error('Unknown product Agent');
      if (revision < lifecycle.current(agentId).revision) throw new Error('stale_lifecycle');
      // Admission closes before the first await; shared services and B remain alive.
      lifecycle.configure(agentId, {revision, disabled: true, disabledThroughRevision: revision});
      this.cron.block(agentId, true);
      for (const agent of ctx.agents.list()) if (this.ownerOf(agent.id) === agentId) agent.cancel({kind: 'user'});
      let task = disabling.get(agentId);
      if (!task) {
        const errors: string[] = [];
        let disposingScopes = false;
        task = (async () => {
          await this.owned.settle(agentId);
          for(const binding of this.bindings.values())if(binding.agentId===agentId)await workers.stopRoot(binding.sessionId);
          const agents = ctx.agents.list().filter(agent => this.ownerOf(agent.id) === agentId);
          for (const agent of agents) agent.cancel({kind: 'user'});
          // Close owned terminals before cancelling their Jobs. Cancelling a
          // send first can race an exited foreground group and poison native
          // terminal cleanup with ESRCH even after the process tree has exited.
          const terminalService = terminals;
          if (terminalService) await Promise.all(agents.flatMap(agent => terminalService.list(agent).map(async terminal => {
            try { await terminalService.signal(agent, terminal.sessionId, 'SIGINT'); }
            catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
            await terminalService.kill(agent, terminal.sessionId, 'Agent disabled');
          })));
          // Cancel background operations before their terminal/Agent scopes unwind.
          // Every lookup is owner-scoped; shared-host and B jobs are untouched.
          const jobStops = agents.flatMap(agent => ctx.jobs.list(agent.id).map(job => {
            ctx.jobs.kill(job.id, agent.id, 'Agent disabled');
            return ctx.jobs.wait(job.id, 4500, agent.id).then(result => {
              if (result.status === 'running' || result.status === 'stopping') throw new Error('Managed job did not settle');
            });
          }));
          await Promise.all([
            ...jobStops,
            this.cron.disposeAgent(agentId),
            knowledge.then(owner => owner.stopAgent(agentId)),
            workflow.then(owner => Promise.all(agents.map(agent => owner.stopSession(agent.id)))),
            models.then(owner => owner.cancelPersisted(id => this.ownerOf(id) === agentId)),
          ]);
          disposingScopes = true;
          await cleanup.run(errors, async () => {
            await ctx.subagents.drainDescendants(agents);
            await this.owned.disposeAgent(agentId);
          });
          await lifecycle.prepare(agentId, () => cancelPersisted(agentId));
          if (ctx.agents.list().some(agent => this.ownerOf(agent.id) === agentId)) throw new Error('Managed Agents remain after cleanup');
          if (errors.length) throw new Error(`Runtime cleanup failed: ${errors[0]}`);
          return {confirmed: true};
        })();
        disabling.set(agentId, task);
        void task.catch(() => {
          // A slow managed operation can settle after the first deadline. Once
          // scope disposal begins, lost cleanup evidence must stay unconfirmed.
          if (!disposingScopes && disabling.get(agentId) === task) disabling.delete(agentId);
        });
      }
      return task;
    });
    this.peer.handle('agent.enable', async value => {
      const {agentId, revision, disabledThroughRevision = 0, blockedScheduleIds = []} = value as RuntimeLifecycle & {agentId: string; blockedScheduleIds?: string[]};
      if (deletion?.retired(agentId) || deleting.has(agentId)) throw new Error('Agent execution is being deleted');
      const current = lifecycle.current(agentId);
      if (revision < current.revision) throw new Error('stale_lifecycle');
      const pending = disabling.get(agentId);
      if (pending) await pending;
      if (!current.disabled && current.revision === revision) return {enabled: true};
      // Keep admission closed until old persisted owners and missed timers are fenced.
      lifecycle.configure(agentId, {revision, disabled: true, disabledThroughRevision});
      this.cron.block(agentId, true);
      await lifecycle.prepare(agentId, () => cancelPersisted(agentId));
      if (current.disabled || current.revision !== revision) await this.cron.skipMissed(agentId, new Set(blockedScheduleIds));
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config) throw new Error('Unknown product Agent');
      lifecycle.configure(agentId, {revision, disabledThroughRevision});
      this.cron.block(agentId, false);
      disabling.delete(agentId);
      await this.configureSchedules(config);
      this.peer.notify('heartbeat.subscription', {agentId, enabled: config.features?.heartbeat === true});
      return {enabled: true};
    });
    this.peer.handle('shutdown', async () => {
      this.accepting = false;
      await update.stop();
      trajectory.dispose();
      await this.cron.dispose();
      for (const id of this.bindings.keys()) ctx.agents.get(SessionId(id))?.cancel({ kind: 'user' }, { keepInbox: true });
      await (await models).stop();
      await (await knowledge).stop();
      await (await workflow).stop();
      await Promise.allSettled([...this.inputs.values()]);
      const agents = [...this.bindings.keys()].map(id => ctx.agents.get(SessionId(id))).filter((agent): agent is Agent => !!agent);
      for (const agent of agents) agent.cancel({ kind: 'user' }, { keepInbox: true });
      await Promise.all(agents.map(async agent => { await agent.whenIdle(); await this.flush(agent); }));
      await history.stop();
      await this.controller.dispose();
      for (const unregister of this.unregisterPresets) await unregister();
      return { stopped: true };
    });
  }

  private waitForApproval(request: {sessionId:string; toolName:string; callId?:string; reason?:string; toolInput?:unknown;
    worker?:{workerId:string; label:string; runtime:string}}, signal: AbortSignal | undefined, timeoutSec: number) {
    const requestId = randomUUID();
    const expiresAt = Date.now() + Math.max(0, timeoutSec * 1000);
    return new Promise<{outcome:ApprovalOutcome; reason?:string; requestId:string}>(resolve => {
      const finish = (answer: ApprovalOutcome, reason?: string) => {
        if (!this.approvals.delete(requestId)) return;
        clearTimeout(timer);
        signal?.removeEventListener('abort', cancel);
        const expired = !!request.worker && Date.now() >= expiresAt;
        const outcome = expired ? 'unavailable' : answer;
        resolve({outcome, requestId, reason:expired ? 'Worker approval timed out.' : reason});
        this.peer.notify('approval.resolved', {requestId, sessionId:request.sessionId, outcome:expired ? 'timed_out' : outcome});
      };
      const cancel = () => finish('cancelled');
      const timer = setTimeout(() => finish('unavailable'), Math.max(0, expiresAt - Date.now()));
      this.approvals.set(requestId, finish);
      if (signal?.aborted) return cancel();
      signal?.addEventListener('abort', cancel, {once:true});
      this.peer.notify('approval.request', {...request, requestId, ...(request.worker ? {expiresAt} : {})});
    });
  }

  *[Service.init]() { yield () => { this.peer.close(); for (const answer of this.approvals.values()) answer('unavailable'); }; }

  private readonly interruptedWork: InterruptedWork;

  private async ensure(binding: SessionBinding) {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting sessions');
    const previous = this.bindings.get(binding.sessionId);
    if (previous && (['sessionId', 'agentId', 'ownerId', 'cwd', 'revision'] as const).some(key => previous[key] !== binding[key])) throw new RpcError(-32002, 'Session binding conflict');
    const preset = `nano:${binding.agentId}:${binding.revision}`;
    const config = this.configurations.get(preset);
    if (config?.personal && (binding.ownerId !== config.personal.ownerId || binding.cwd !== config.workspace)) throw new RpcError(-32004, 'Personal Session must retain its owner and private workspace');
    if (!this.configurations.has(preset)) throw new RpcError(-32002, 'Unknown configuration revision');
    this.bindings.set(binding.sessionId, binding);
    const agent = await this.owned.resolve(binding.sessionId, true);
    if (config?.mode === 'global') await this.interruptedWork.recover(agent, {agentId:binding.agentId,revision:this.lifecycle.current(binding.agentId).revision});
    await this.flush(agent);
    if(config?.mode==='global')await this.ctx.nanoWorkers.flushReports(agent.id);
    void this.tasks.poke(agent);
    return { sessionId: agent.id, revision: binding.revision };
  }

  private async agent(sessionId: string): Promise<Agent> {
    if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
    return this.owned.resolve(sessionId);
  }

  private async configureSchedules(config: AgentConfiguration) {
    if (this.lifecycle.current(config.agentId).disabled) { await this.cron.setEnabled(config.agentId, false); return; }
    const tasks = await this.cron.catalog(config.agentId);
    await this.cron.setEnabled(config.agentId, needsSchedules(config) || tasks.some(task => task.status === 'active'));
  }

  private async submit(input: Submit): Promise<RuntimeOutput<'session.submit'>> {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting inputs');
    const agentId = this.bindings.get(input.sessionId)?.agentId;
    if (!agentId) throw new Error('Session has no trusted product binding');
    const revision = this.lifecycle.current(agentId).revision;
    this.lifecycle.assertEnabled(agentId);
    if ((input.lifecycle_revision ?? input.source.lifecycle_revision ?? revision) !== revision) throw new RpcError(-32003, 'stale_lifecycle');
    const agent = await this.agent(input.sessionId);
    const fallback = (await this.models).fallback;
    if (!fallback.nativeEvidence(agent, input.inputId).accepted) {
      if (!['human', 'system'].includes(input.source.kind)) throw new RpcError(-32602, 'Invalid input source');
      let content = await this.ctx.attachments.admitPromptContent(input.content);
      if (input.attachmentSources) await this.ctx.nanoTrajectoryAttachments.record(input.sessionId, content, input.attachmentSources);
      const config = this.configurations.get(agent.session.header.agentPreset!);
      if (input.source.channel === 'heartbeat' && config && this.capabilities.held(config.agentId, {kind: 'feature', name: 'heartbeat'})) return {accepted: false, busy: true};
      const isProactiveWake = input.source.kind === 'system' && (input.source.channel === 'proactive_review' || input.source.channel === 'proactive_nightly');
      if (isProactiveWake && config) {
        const eff = effectiveFeatures(config.features, definitionsForRole(Boolean(config.personal)), capabilityDraft(config));
        if (!config.personal || eff.proactive_planning !== true || eff.task_graph === false) {
          return { accepted: false, withdrawn: true, durable: true };
        }
        if (this.capabilities.held(config.agentId, { kind: 'feature', name: 'proactive_planning' })) {
          return { accepted: false, busy: true };
        }
      }
      if (input.onlyIfIdle && (agent.status !== 'idle' || agent.inbox.nextTurn.length || agent.inbox.nextStep.length)) return { accepted: false, busy: true };
      if (isProactiveWake && config && input.source.channel === 'proactive_nightly') {
        const knowledgeSvc = await this.knowledgeRuntime;
        const ds = await knowledgeSvc.dreaming.nightlyStatus(config.agentId, this.clockNow());
        if (!ds.completed && ds.failures < 3 && (ds.retryAt ?? 0) < ds.nightWindowEndAt) {
          void knowledgeSvc.dreaming.tick(config.agentId, this.clockNow()).catch(() => {});
          return { accepted: false, busy: true };
        }
        const updatedMemory = await knowledgeSvc.documents.updatedEntrySinceWindowStart(agent);
        if (updatedMemory && content.length > 0 && content[0]?.type === 'text') {
          const firstText = content[0].text;
          const newlineIdx = firstText.indexOf('\n');
          const memTag = `<updated-formal-memory complete="${updatedMemory.complete ? 'true' : 'preview'}">\n${updatedMemory.body}\n</updated-formal-memory>`;
          const injected = newlineIdx >= 0
            ? `${firstText.slice(0, newlineIdx + 1)}${memTag}\n${firstText.slice(newlineIdx + 1)}`
            : `${firstText}\n${memTag}`;
          content = [{ type: 'text', text: injected }, ...content.slice(1)];
        }
      }
      fallback.interrupt(agent);
      this.lifecycle.assertEnabled(agentId);
      if (this.lifecycle.current(agentId).revision !== revision) throw new Error('stale_lifecycle');
      const source = {...input.source, admittedAt:this.clockNow(), lifecycle_revision: input.source.lifecycle_revision ?? input.lifecycle_revision ?? revision};
      const original = freezeMessage({ id: MessageId(input.inputId), role: 'user' as const, content,
        source: input.source.kind === 'human' ? { ...source, kind: 'user' as const } : { ...source, kind: 'nano-system' as const } });
      const [message] = this.chatScope.queued(input.sessionId,original);
      if (!message || config?.collaborationScope === 'owner_only' && input.source.nanoTeamChat) return {accepted:false, withdrawn:true, durable:true};
      if (input.mode === 'followup') agent.followup(message);
      else if (input.mode === 'steer') {
        if (message.source.kind === 'nano-system' && message.source.channel === 'inbox') {
          // Only pending notices are redundant; keep the newest durable wake ID
          // so recovery still tracks the latest admitted Inbox watermark.
          for (const pending of [...agent.inbox.nextTurn, ...agent.inbox.nextStep])
            if (pending.source.kind === 'nano-system' && pending.source.channel === 'inbox') agent.inbox.remove(pending.id);
        }
        agent.steer(message);
      }
      else if (input.mode === 'inject') agent.inject(message);
      else throw new RpcError(-32602, 'Invalid input mode');
    }
    await this.flush(agent);
    return { ...fallback.nativeEvidence(agent, input.inputId), durable: true };
  }

  private async flush(agent: Agent) {
    if (!await this.ctx.sessions.flush(agent.session)) throw new RpcError(-32005, 'Session has no persistence barrier');
  }
}
