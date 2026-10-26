import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { UserMessage } from '@deepseek-ai/dsh-llm';
import type { PreToolDecision, ToolExecution } from '@deepseek-ai/dsh-tools';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-permission-presets';
import type { ApprovalConfiguration, MessageApprovalContext } from '@nano/product-contracts';
import type {} from '../product-bridge.js';
import type { AgentConfiguration } from '../index.js';
import { approvalDomain, type ApprovalAudit } from './audit.js';
import type { Domain } from '@deepseek-ai/dsh-storage-domain';
import { ApprovalSources } from './sources.js';
import type { ApprovalReviewResult } from './types.js';
import { classify } from './classifier.js';
import type {} from './cc.js';
import type {} from './codex.js';
import { contextTools } from '../agent-context.js';
import { normalizeMessageArguments } from '../message-arguments.js';
import { isHumanSource } from '../input-source.js';
import { ReviewRecovery, ReviewFailure } from './recovery.js';

declare module '@deepseek-ai/cordis' { interface Context { nanoApproval: NanoApproval } }
const safeTools = new Set(['read', 'read_image', 'glob', 'grep', 'web_search', 'skill', 'job_output', 'job_list', 'job_kill', 'subagent', 'subagent_fork', 'interrupt_agent', 'list_agents', 'structured_output', 'inbox', 'memory']);

/** One automatic reviewer; native dispatch, approval audit and cancellation stay native. */
export class NanoApproval extends Service {
  static inject = ['tools', 'approval', 'permissionPresets', 'llm', 'agents', 'storageDomain', 'nanoProduct', 'ccApproval', 'codexApproval'];
  private readonly audit: Promise<Domain<typeof approvalDomain>>;
  private readonly epoch = randomUUID();
  readonly sources = new ApprovalSources();
  private readonly actions = new Map<string, Set<ReviewRecovery>>();
  private readonly cleanupActions = new Set<ReviewRecovery>();
  constructor(ctx: Context, private readonly configOf: (agent: Agent) => AgentConfiguration | undefined) {
    super(ctx, 'nanoApproval');
    this.audit = ctx.storageDomain.open(approvalDomain);
    ctx.effect(() => async () => {
      const all = new Set([...this.cleanupActions, ...[...this.actions.values()].flatMap(actions => [...actions])]);
      for (const action of all) action.cancel();
      await Promise.all([...all].map(action => action.drain()));
      await (await this.audit).close();
    });
    ctx.permissionPresets.registerAuto(() => {});
    ctx.on('tools/pre-execute', (exec, next) => this.review(exec, next), { prepend: true });
    ctx.on('agent/disposed', ({ agent }) => { this.sources.release(agent.id); for (const action of this.actions.get(agent.id) ?? []) action.cancel(); });
    ctx.on('approval/request', async (request, next) => {
      const outcome = await next();
      if (outcome === 'allowed-once' && request.callId && this.config(request.agent)?.approval) {
        await (await this.audit).table('sessions').update(request.agent.id, entries => [...entries, {
          time: Date.now(), callId: request.callId!, tool: request.toolName, source: 'human', decision: 'allow', reason: '', consecutive: 0,
          total: entries.at(-1)?.total ?? 0, reviewId: entries.findLast(entry => entry.callId === request.callId && entry.recovery)?.recovery?.reviewId,
        }]);
      }
      return outcome;
    }, { prepend: true });
  }
  async entries(sessionId: string) { return (await this.audit).table('sessions').get(sessionId) ?? []; }
  async attach(agent: Agent, config: AgentConfiguration) {
    if (config.approval?.rules !== 'codex') await this.ctx.codexApproval.release(agent.id);
    if (!config.approval) return;
    const table = (await this.audit).table('sessions');
    if (!table.get(agent.id)) await table.put(agent.id, []);
    const delegated = (await this.audit).table('delegated');
    const parentId = agent.session.header.parentSession;
    const parent = parentId && this.ctx.agents.get(parentId);
    if (agent.session.header.origin === 'subagent' && !agent.session.header.isSeeded && !delegated.get(agent.id) && parent) {
      await delegated.put(agent.id, { epoch: this.epoch, entries: [...await this.inherited(parent.id), ...await this.sources.history(parent, undefined, this.config(parent)?.mode !== 'global')],
        codexEntries: [...await this.inherited(parent.id, true), ...await this.sources.history(parent, undefined, this.config(parent)?.mode !== 'global', { toolResults: true, fullAssistant: true })] });
    }
    if (config.approval.enabled || config.approval.dangerouslySkipPermissions) this.ctx.permissionPresets.set(agent.session, 'auto');
    // Auto selects ask as a preset side effect; restore the native delegation boundary afterward.
    const approvalPolicy = agent.session.header.origin === 'subagent' ? 'never' : 'ask';
    if (this.ctx.approval.overrideOf(agent.session) !== approvalPolicy) setApprovalPolicy(agent.session, approvalPolicy);
  }
  private config(agent: Agent) { return this.configOf(agent); }
  private async inherited(sessionId: string, codex = false): Promise<unknown[]> {
    const saved = (await this.audit).table('delegated').get(sessionId);
    if (!saved) return [];
    return this.sources.restoreEntries(codex ? saved.codexEntries ?? saved.entries : saved.entries, saved.epoch !== this.epoch);
  }

  private route(agent: Agent, config: AgentConfiguration): 'interactive' | 'unattended' | 'return_to_agent' {
    if (agent.session.header.origin === 'subagent') return 'return_to_agent';
    const events = agent.session.snapshotEvents(); const start = events.findLast(event => event.type === 'turn/start')?.seq ?? -1;
    const inputs = events.filter(event => event.seq > start && event.type === 'user/message').map(event => event.data as UserMessage);
    if (inputs.some(input => input.source?.kind === 'schedule' || input.source?.kind === 'nano-system' && input.source.channel === 'heartbeat')) return 'unattended';
    if (config.mode === 'global') return 'return_to_agent';
    return inputs.some(input => isHumanSource(input.source) || input.source?.kind==='nano-system' && ['task-execution','task-change'].includes(String(input.source.channel))) ? 'interactive' : 'unattended';
  }
  private async record(exec: ToolExecution, source: string, decision: string, reason: string, config: ApprovalConfiguration, details: Partial<Pick<ApprovalAudit, 'reviewer' | 'elapsedMs' | 'usage' | 'metadata' | 'recovery' | 'reviewId'>> = {}) {
    let reached = { consecutive: 0, total: 0 };
    await (await this.audit).table('sessions').update(exec.agent!.id, entries => {
      let consecutive = entries.at(-1)?.consecutive ?? 0;
      let total = entries.at(-1)?.total ?? 0;
      if (decision === 'allow') consecutive = 0;
      else if (source === 'classifier_block') { consecutive++; total++; }
      reached = { consecutive, total };
      if (source === 'classifier_block' && total >= config.totalDenyLimit) { consecutive = 0; total = 0; }
      return [...entries, { time: Date.now(), callId: exec.callId, tool: exec.name, source, decision, reason, consecutive, total, rules: config.rules, ...details }];
    });
    return reached;
  }
  private async escalate(exec: ToolExecution, config: AgentConfiguration, reason: string, source: string, reviewId?: string): Promise<PreToolDecision> {
    const route = this.route(exec.agent!, config);
    if (route === 'interactive') return { kind: 'ask', reason };
    const allowed = route === 'unattended' && config.approval!.unattendedFallback === 'allow';
    await this.record(exec, route, allowed ? 'allow' : 'deny', reason, config.approval!, { reviewId });
    return allowed ? { kind: 'allow' } : { kind: 'deny', reason: `${reason} (${source}; ${route})`, info: { name: 'NanoApprovalDenied', code: source } };
  }
  private async review(exec: ToolExecution, next: () => Promise<PreToolDecision>): Promise<PreToolDecision> {
    if (exec.name === 'send_user_message' || exec.name === 'send_message' && typeof (exec.arguments as {agent_id?:unknown})?.agent_id !== 'string') exec = {...exec, arguments:normalizeMessageArguments(exec.arguments)};
    const agent = exec.agent; const current = agent && this.config(agent);
    // Metadata revisions mutate the live object; an accepted action owns an independent snapshot.
    const config = current && structuredClone(current); const policy = config?.approval;
    if (!agent || !config || !policy || exec.name === 'run_code' && !exec.parent) return next();
    const downstream = await next();
    if (downstream.kind !== 'allow') return downstream;
    const allow = async (source: string) => { await this.record(exec, source, 'allow', '', policy); return { kind: 'allow' } as const; };
    // Session-local continuation must work with Auto off; downstream denials still win.
    if (contextTools.has(exec.name)) return allow('internal_context');
    if (policy.dangerouslySkipPermissions) return allow('explicit_skip');
    // Source preferences use the original owner message and revision checked by the product host.
    if (config.personal && exec.name === 'personal_sources') return allow('owner_source_control');
    if (policy.rules !== 'dsh' && (safeTools.has(exec.name)
      || exec.name === 'conversations' && ['list', 'info', 'read', 'search'].includes(String((exec.arguments as { action?: unknown }).action))
      || policy.enabled && (['schedule_list', 'schedule_history', 'get_goal', 'todo_write'].includes(exec.name)
        || exec.name === 'skill_manage' && (exec.arguments as { action?: unknown }).action === 'list'
        || exec.name === 'task_graph' && ['list', 'get'].includes((exec.arguments as { action: string }).action)
        || exec.name === 'workflow' && ['list', 'read'].includes((exec.arguments as { action: string }).action))
      || !['bash', 'send_message', 'send_user_message'].includes(exec.name) && policy.alwaysAllowTools.includes(exec.name)
      || exec.name === 'send_message' && typeof (exec.arguments as { agent_id?: unknown }).agent_id === 'string')) return allow('safe_tool');
    // The product reviews the exact external payload at commit; avoid a duplicate automatic verdict.
    if (config.personal && policy.enabled && ['send_message', 'send_user_message'].includes(exec.name)) return allow('product_disclosure_gate');
    // Freeze the pending action before asynchronous evidence preparation can yield.
    exec = { ...exec, arguments: structuredClone(exec.arguments) };
    const recovery = new ReviewRecovery(exec.signal, exec.callId);
    const actions = this.actions.get(agent.id) ?? new Set<ReviewRecovery>();
    this.actions.set(agent.id, actions); actions.add(recovery);
    const header = agent.session.requestHeader();
    const reviewer = structuredClone(policy.reviewer ?? { provider: header?.config.provider ?? config.provider, model: header?.config.model ?? config.model });
    const started = Date.now();
    let result: ApprovalReviewResult;
    try {
      try {
        const prepared = await recovery.prepare(async signal => {
          const messageContext = exec.name === 'send_message'
            ? await this.ctx.nanoProduct.call('send_message.context', { target: (exec.arguments as { target?: unknown }).target }, { ...exec, signal }) as MessageApprovalContext : undefined;
          if (messageContext?.recipient.kind === 'owner' || !policy.enabled) return { messageContext, inherited: [] };
          return { messageContext, inherited: await this.inherited(agent.id, policy.rules === 'codex') };
        });
        if (prepared.messageContext?.recipient.kind === 'owner') { recovery.finish('owner_message', 'fastpath'); return allow('owner_message'); }
        if (!policy.enabled) { recovery.finish('manual_required', this.route(agent, config)); return this.escalate(exec, config, `Permission required for ${exec.name}`, 'manual_required'); }
        const request = { exec, config, sources: this.sources, ...prepared, reviewer, recovery };
        result = policy.rules === 'codex' ? await this.ctx.codexApproval.review(request)
          : policy.rules === 'nano' ? await this.ctx.ccApproval.review(request) : await classify(this.ctx, request);
        recovery.assertActive();
      } catch (error) {
        const cancelled = exec.signal.aborted || recovery.signal.aborted && recovery.signal.reason instanceof ReviewFailure && recovery.signal.reason.category === 'cancelled';
        const route = cancelled ? 'cancel' : this.route(agent, config);
        const fallback = route === 'unattended' ? policy.unattendedFallback : undefined;
        const recoveryTrace = recovery.finish(cancelled ? 'cancelled' : error instanceof ReviewFailure ? error.category : 'unavailable_unknown', route === 'interactive' ? 'interactive_pending' : route, fallback);
        const reason = `Automatic reviewer unavailable: ${String(error)}`;
        await this.record(exec, cancelled ? 'classifier_cancelled' : 'classifier_unavailable', cancelled ? 'cancel' : 'no_verdict', reason, policy, { reviewer, elapsedMs: Date.now() - started, recovery: recoveryTrace });
        if (cancelled || exec.signal.aborted) return { kind: 'cancel' };
        return this.escalate(exec, config, reason, 'classifier_unavailable', recoveryTrace.reviewId);
      }
      const verdict = result.decision;
      // Predict the existing counter route before persisting the one cost-bearing audit row.
      const prior = (await this.entries(agent.id)).at(-1);
      const escalated = verdict.behavior === 'deny' && !['high', 'critical'].includes(verdict.risk ?? '')
        && ((prior?.consecutive ?? 0) + 1 >= policy.denyLimit || (prior?.total ?? 0) + 1 >= policy.totalDenyLimit);
      const route = escalated ? this.route(agent, config) : verdict.behavior;
      recovery.assertActive();
      const recoveryTrace = recovery.finish(verdict.behavior, route === 'interactive' ? 'interactive_pending' : route, escalated && route === 'unattended' ? policy.unattendedFallback : undefined);
      const counts = await this.record(exec, result.source ?? (verdict.behavior === 'deny' ? 'classifier_block' : 'classifier_allow'), verdict.behavior, verdict.reason, policy,
        { reviewer, metadata: result.metadata, elapsedMs: Date.now() - started, recovery: recoveryTrace, ...(result.usage ? { usage: result.usage } : {}) });
      if (exec.signal.aborted || recovery.signal.aborted) return { kind: 'cancel' };
      if (verdict.behavior === 'allow') return { kind: 'allow' };
      if (!['high', 'critical'].includes(verdict.risk ?? '') && (counts.consecutive >= policy.denyLimit || counts.total >= policy.totalDenyLimit)) return this.escalate(exec, config, verdict.reason, 'classifier_block', recoveryTrace.reviewId);
      return { kind: 'deny', reason: verdict.reason, info: { name: 'NanoApprovalDenied', code: 'classifier_block', reason: verdict.reason } };
    } finally {
      if (!recovery.trace.complete) recovery.finish('unavailable_unknown', 'audit_failed');
      actions.delete(recovery); if (!actions.size) this.actions.delete(agent.id);
      if (recovery.hasPendingCleanup) {
        this.cleanupActions.add(recovery);
        void recovery.drain().then(() => this.cleanupActions.delete(recovery));
      }
    }
  }
}
