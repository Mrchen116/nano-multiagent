import { randomUUID } from 'node:crypto';
import { Service, type Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { BlockAssembler } from '@deepseek-ai/dsh-llm';
import type { PreToolDecision, ToolExecution } from '@deepseek-ai/dsh-tools';
import { setApprovalPolicy } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-permission-presets';
import type { ApprovalConfiguration } from '@nano/product-contracts';
import type { AgentConfiguration } from '../index.js';
import { approvalDomain, type ApprovalAudit } from './audit.js';
import type { Domain } from '@deepseek-ai/dsh-storage-domain';
import { ApprovalSources, inboxSourceInstructions } from './sources.js';
import { buildPolicy, parseNanoDecision, parseDshDecision, policyAsset, type ReviewDecision } from './rules.js';

declare module '@deepseek-ai/cordis' { interface Context { nanoApproval: NanoApproval } }
const safeTools = new Set(['read', 'read_image', 'glob', 'grep', 'web_search', 'skill', 'job_output', 'job_list', 'job_kill', 'subagent', 'subagent_fork', 'interrupt_agent', 'list_agents', 'structured_output', 'inbox', 'conversations', 'memory']);

/** One automatic reviewer; native dispatch, approval audit and cancellation stay native. */
export class NanoApproval extends Service {
  static inject = ['tools', 'approval', 'permissionPresets', 'llm', 'agents', 'storageDomain'];
  private readonly audit: Promise<Domain<typeof approvalDomain>>;
  private readonly epoch = randomUUID();
  readonly sources = new ApprovalSources();
  constructor(ctx: Context, private readonly configOf: (agent: Agent) => AgentConfiguration | undefined) {
    super(ctx, 'nanoApproval');
    this.audit = ctx.storageDomain.open(approvalDomain);
    ctx.effect(() => async () => { await (await this.audit).close(); });
    ctx.permissionPresets.registerAuto(() => {});
    ctx.on('tools/pre-execute', (exec, next) => this.review(exec, next), { prepend: true });
    ctx.on('agent/disposed', ({ agent }) => { this.sources.release(agent.id); });
    ctx.on('approval/request', async (request, next) => {
      const outcome = await next();
      if (outcome === 'allowed-once' && request.callId && this.config(request.agent)?.approval) {
        await (await this.audit).table('sessions').update(request.agent.id, entries => [...entries, {
          time: Date.now(), callId: request.callId!, tool: request.toolName, source: 'human', decision: 'allow', reason: '', consecutive: 0,
          total: entries.at(-1)?.total ?? 0,
        }]);
      }
      return outcome;
    }, { prepend: true });
  }
  async entries(sessionId: string) { return (await this.audit).table('sessions').get(sessionId) ?? []; }
  async attach(agent: Agent, config: AgentConfiguration) {
    if (!config.approval) return;
    const table = (await this.audit).table('sessions');
    if (!table.get(agent.id)) await table.put(agent.id, []);
    if(config.workflowParent?.interactive) agent.ctx.on('system-prompt/assemble', async (_assembly,_context,next)=>{const assembly=await next();assembly.contexts=assembly.contexts.map(context=>context.name==='subagent:delegation'?{...context,text:'You are a Workflow child. Tool access is limited to the inherited selection. Actions requiring approval are routed to the original human conversation; wait for that answer and respect rejection.'}:context);return assembly;},{prepend:true});
    const delegated = (await this.audit).table('delegated');
    const parentId = agent.session.header.parentSession;
    const parent = parentId && this.ctx.agents.get(parentId);
    if (agent.session.header.origin === 'subagent' && !agent.session.header.isSeeded && !delegated.get(agent.id) && parent) {
      await delegated.put(agent.id, { epoch: this.epoch, entries: [...await this.inherited(parent.id), ...await this.sources.history(parent)] });
    }
    if (config.approval.enabled || config.approval.dangerouslySkipPermissions) this.ctx.permissionPresets.set(agent.session, 'auto');
    if ((agent.session.header.origin !== 'subagent' || config.workflowParent?.interactive) && this.ctx.approval.overrideOf(agent.session) !== 'ask') setApprovalPolicy(agent.session, 'ask');
  }
  private config(agent: Agent) { return this.configOf(agent); }
  private async inherited(sessionId: string): Promise<unknown[]> {
    const saved = (await this.audit).table('delegated').get(sessionId);
    if (!saved) return [];
    if (saved.epoch === this.epoch) return saved.entries;
    // Previously observed host messages remain background after process recovery.
    return saved.entries.map(entry => {
      if (entry && typeof entry === 'object' && 'host_context_live' in entry) {
        const { host_context_live, ...rest } = entry;
        return { ...rest, host_context: host_context_live };
      }
      return entry;
    });
  }
  private route(agent: Agent, config: AgentConfiguration): 'interactive' | 'unattended' | 'return_to_agent' {
    const events = agent.session.snapshotEvents(); const start = events.findLast(event => event.type === 'turn/start')?.seq ?? -1;
    const inputs = events.filter(event => event.seq > start && event.type === 'user/message').map(event => event.data as { source?: { kind?: string; channel?: string } });
    if (inputs.some(input => input.source?.kind === 'schedule' || input.source?.kind === 'nano-system' && input.source.channel === 'heartbeat')) return 'unattended';
    if (config.workflowParent?.interactive && config.mode !== 'global') return 'interactive';
    if (config.mode === 'global' || agent.session.header.origin === 'subagent') return 'return_to_agent';
    return inputs.some(input => input.source?.kind === 'nano-human') ? 'interactive' : 'unattended';
  }
  private async record(exec: ToolExecution, source: string, decision: string, reason: string, config: ApprovalConfiguration, details: Partial<Pick<ApprovalAudit, 'reviewer' | 'elapsedMs' | 'usage'>> = {}) {
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
  private async escalate(exec: ToolExecution, config: AgentConfiguration, reason: string, source: string): Promise<PreToolDecision> {
    const route = this.route(exec.agent!, config);
    if (route === 'interactive') return { kind: 'ask', reason };
    const allowed = route === 'unattended' && config.approval!.unattendedFallback === 'allow';
    await this.record(exec, route, allowed ? 'allow' : 'deny', reason, config.approval!);
    return allowed ? { kind: 'allow' } : { kind: 'deny', reason: `${reason} (${source}; ${route})`, info: { name: 'NanoApprovalDenied', code: source } };
  }
  private async review(exec: ToolExecution, next: () => Promise<PreToolDecision>): Promise<PreToolDecision> {
    const agent = exec.agent; const config = agent && this.config(agent); const policy = config?.approval;
    if (!agent || !config || !policy || exec.name === 'run_code' && !exec.parent) return next();
    const downstream = await next();
    if (downstream.kind !== 'allow') return downstream;
    const allow = async (source: string) => { await this.record(exec, source, 'allow', '', policy); return { kind: 'allow' } as const; };
    if (policy.dangerouslySkipPermissions) return allow('explicit_skip');
    if (policy.rules === 'nano' && (safeTools.has(exec.name) || exec.name !== 'bash' && policy.alwaysAllowTools.includes(exec.name)
      || exec.name === 'send_message' && typeof (exec.arguments as { agent_id?: unknown }).agent_id === 'string')) return allow('safe_tool');
    if (!policy.enabled) return this.escalate(exec, config, `Permission required for ${exec.name}`, 'manual_required');
    const header = agent.session.requestHeader();
    const reviewer = policy.reviewer ?? { provider: header?.config.provider ?? config.provider, model: header?.config.model ?? config.model };
    const started = Date.now();
    let decision: ReviewDecision | undefined; let usage: unknown;
    try {
      const prompt = await buildPolicy(policy, agent.session.header.cwd!);
      const transcript = await this.sources.transcript(agent, exec, await this.inherited(agent.id));
      for (const stage of policy.rules === 'nano' ? [1, 2] : [1]) {
        const suffix = policy.rules === 'nano' ? await policyAsset(`cc-2.1.267-nano-v1/s${stage}_suffix.txt`) : '';
        const assembly = new BlockAssembler();
        const signal = AbortSignal.any([exec.signal, AbortSignal.timeout(stage === 1 ? 30_000 : 60_000)]);
        for await (const chunk of this.ctx.llm.stream({ ...reviewer, system: `${prompt}\n\n${inboxSourceInstructions}`, messages: [{ role: 'user', content: [{ type: 'text', text: transcript + suffix }] }], temperature: 0,
          maxTokens: stage === 1 ? 2112 : 10240, signal })) assembly.push(chunk);
        usage = assembly.usage;
        if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted') throw new Error(JSON.stringify(assembly.finish));
        const result = assembly.blocks().filter(block => block.type === 'text').map(block => block.text).join('');
        decision = policy.rules === 'nano' ? parseNanoDecision(result) : parseDshDecision(result);
        if (!decision) throw new Error('Reviewer returned no valid verdict');
        if (policy.rules !== 'nano' || stage === 2 || decision.behavior === 'allow') break;
      }
    } catch (error) {
      if (exec.signal.aborted) return { kind: 'cancel' };
      const reason = `Automatic reviewer unavailable: ${String(error)}`;
      await this.record(exec, 'classifier_unavailable', 'no_verdict', reason, policy, { reviewer, elapsedMs: Date.now() - started });
      return this.escalate(exec, config, reason, 'classifier_unavailable');
    }
    const verdict = decision!;
    const counts = await this.record(exec, verdict.behavior === 'deny' ? 'classifier_block' : 'classifier_allow', verdict.behavior, verdict.reason, policy,
      { reviewer, elapsedMs: Date.now() - started, ...(usage ? { usage } : {}) });
    if (verdict.behavior === 'allow') return { kind: 'allow' };
    if (verdict.risk !== 'high' && (counts.consecutive >= policy.denyLimit || counts.total >= policy.totalDenyLimit)) return this.escalate(exec, config, verdict.reason, 'classifier_block');
    return { kind: 'deny', reason: verdict.reason, info: { name: 'NanoApprovalDenied', code: 'classifier_block', reason: verdict.reason } };
  }
}
