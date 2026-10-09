import { Service, type Context } from '@deepseek-ai/cordis';
import { createUserMessage, ReasoningEffortId } from '@deepseek-ai/dsh-llm';
import { CommandId } from '@deepseek-ai/dsh-commands/brand';
import { defineDomain, domainTable, type Domain, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { AgentConfiguration } from './index.js';
import { ModelFallback } from './model-fallback.js';
import type NanoCompaction from './compaction.js';

export interface ModelRoute { provider: string; model: string; reasoningEffort?: string; maxTokens?: number }
interface Selection { revision: string; chain?: string; selected?: ModelRoute; effort?: string; sticky?: ModelRoute }
interface Command { sessionId: string; action: string; argument: string; status: 'pending' | 'completed'; text?: string; success?: boolean }
interface ModelDomain extends DomainSpec { tables: { sessions: DomainTableSpec<string, Selection>; commands: DomainTableSpec<string, Command> } }
const routeSchema = z.object({ provider: z.string(), model: z.string(), reasoningEffort: z.string().optional(), maxTokens: z.number().optional() });
const domain: ModelDomain = defineDomain({ name: 'nano_model', version: 1, layout: 'per-record', tables: {
  sessions: domainTable(z.object({ revision: z.string(), chain: z.string().optional(), selected: routeSchema.optional(), effort: z.string().optional(), sticky: routeSchema.optional() })),
  commands: domainTable(z.object({ sessionId: z.string(), action: z.string(), argument: z.string(), status: z.enum(['pending', 'completed']), text: z.string().optional(), success: z.boolean().optional() })),
} });
const chain = (config: AgentConfiguration) => JSON.stringify([config.provider, config.model, config.modelFallbacks ?? []]);
const key = (value: string) => Buffer.from(value).toString('base64url');
declare module '@deepseek-ai/cordis' { interface Context { nanoModels: ModelPolicy } }

/** One model authority couples prompt assembly, requests and session commands. */
export class ModelPolicy extends Service {
  static inject = ['llm', 'storageDomain', 'systemPrompt', 'compaction', 'sessions'];
  readonly fallback: ModelFallback;
  private readonly state: Promise<Domain<ModelDomain>>;
  private readonly selections = new Map<string, Selection>();
  private readonly commands = new Map<string, { task: Promise<Command>; sessionId: string; abort: AbortController }>();
  private readonly configs = new Map<string, AgentConfiguration>();
  private readonly host: Context;
  constructor(ctx: Context, options: { check: (agent: Agent, run: import('./model-fallback.js').ModelRun) => Promise<{ published: boolean }>; notify: (sessionId: string) => void }) {
    super(ctx, 'nanoModels'); this.host = ctx; this.state = ctx.storageDomain.open(domain);
    this.fallback = new ModelFallback(ctx, { route: agent => this.route(agent), select: (agent, route) => { this.selections.get(agent.id)!.selected = route; }, sticky: async (agent, route) => { const selection = this.selections.get(agent.id)!; selection.sticky = route; delete selection.effort; delete selection.selected; await (await this.state).table('sessions').put(key(agent.id), selection); }, ...options });
    ctx.effect(() => async () => { await this.stop(); await (await this.state).close(); });
  }
  async attach(agent: Agent, config: AgentConfiguration) {
    this.configs.set(agent.id, config);
    const saved = (await this.state).table('sessions').get(key(agent.id));
    let selection = saved ?? { revision: config.revision, chain: chain(config) };
    selection.chain ??= chain(config);
    delete selection.selected;
    if (selection.revision !== config.revision) selection = await this.revised(selection, config);
    this.selections.set(agent.id, selection);
    await this.fallback.attach(agent, config);
    let assembled: ModelRoute | undefined;
    agent.ctx.on('system-prompt/assemble', async (_assembly, _context, next) => {
      const route = this.route(agent); const assembly = await next(); assembled = route;
      return { ...assembly, variables: { ...assembly.variables, provider: route.provider, model: route.model } };
    }, { prepend: true });
    agent.ctx.on('agent/request', async (_payload, next) => {
      const route = assembled ?? this.route(agent);
      const { reasoningEffort: _, maxTokens: priorCap, ...request } = await next();
      return { ...request, provider: route.provider, model: route.model,
        ...(route.reasoningEffort ? { reasoningEffort: ReasoningEffortId(route.reasoningEffort) } : {}),
        ...(agent.session.header.parentSession && priorCap !== undefined ? { maxTokens: priorCap } : route.maxTokens === undefined ? {} : { maxTokens: route.maxTokens }),
      };
    }, { prepend: true });
    agent.ctx.on('agent/pre-step', async (_payload, next) => {
      const decision = await next(); if (decision.kind === 'reject') return decision;
      await this.fallback.checkpoint();
      const route = assembled ?? this.route(agent); const previous = agent.session.requestHeader()?.config;
      const messages = this.fallback.allowed(agent, decision.messages).filter(message => message.source.kind !== 'model-selection');
      if (decision.messages.length && !messages.length) return { kind: 'reject' };
      if (previous && (previous.provider !== route.provider || previous.model !== route.model)) messages.push(createUserMessage({
        content: [{ type: 'text', text: `Earlier assistant turns used ${previous.provider}/${previous.model}; this request uses ${route.provider}/${route.model}.` }],
        source: { kind: 'model-selection', form: 'notice', summary: `${previous.model} → ${route.model}` },
      }));
      return { ...decision, messages };
    }, { prepend: true });
    agent.ctx.effect(() => () => { this.configs.delete(agent.id); this.selections.delete(agent.id); });
  }
  route(agent: Agent): ModelRoute {
    const config = this.configs.get(agent.id)!;
    let selection = this.selections.get(agent.id)!;
    if (selection.revision !== config.revision) { selection = { revision: config.revision, effort: selection.effort }; this.selections.set(agent.id, selection); }
    const parent = agent.session.header.parentSession;
    const inherited = parent && this.host.agents.get(parent);
    const route = selection.selected ?? selection.sticky ?? (inherited && this.configs.has(inherited.id) ? this.route(inherited) : config);
    return { provider: route.provider, model: route.model, reasoningEffort: selection.selected ? route.reasoningEffort : selection.effort ?? route.reasoningEffort, maxTokens: route.maxTokens };
  }
  private async revised(selection: Selection, config: AgentConfiguration): Promise<Selection> {
    const sticky = selection.chain === chain(config) ? selection.sticky : undefined;
    const route = sticky ?? config;
    const info = await this.host.llm.resolveModelInfo(route.provider, route.model);
    const effort = info.reasoning?.efforts.some(effort => effort.id === selection.effort) ? selection.effort : undefined;
    return { revision: config.revision, chain: chain(config), ...(sticky ? { sticky } : {}), ...(effort ? { effort } : {}) };
  }
  async changed(config: AgentConfiguration) {
    for (const [id, previous] of this.configs) if (previous.agentId === config.agentId) {
      const agent = this.host.agents.get(id as Agent['id']); if (agent) this.fallback.interrupt(agent);
      const selection = await this.revised(this.selections.get(id)!, config);
      this.selections.set(id, selection); await (await this.state).table('sessions').put(key(id), selection);
    }
  }
  command(agent: Agent, request: { id: string; action: string; argument?: string }): Promise<Command> {
    const active = this.commands.get(request.id); if (active) return active.task;
    const abort = new AbortController();
    const task = this.perform(agent, request, abort.signal).finally(() => this.commands.delete(request.id));
    this.commands.set(request.id, { task, sessionId: agent.id, abort }); return task;
  }
  private async perform(agent: Agent, request: { id: string; action: string; argument?: string }, signal: AbortSignal): Promise<Command> {
    const commands = (await this.state).table('commands'); const id = key(request.id); const argument = request.argument?.trim() ?? '';
    let record = commands.get(id);
    if (record && (record.sessionId !== agent.id || record.action !== request.action || record.argument !== argument)) throw new Error('Command identity is already bound to different input');
    if (record?.status === 'completed') return record;
    record ??= { sessionId: agent.id, action: request.action, argument, status: 'pending' }; await commands.put(id, record);
    const complete = async (text: string, success: boolean) => { const result: Command = { ...record!, status: 'completed', text, success }; await commands.put(id, result); return result; };
    try {
      if (request.action === 'compact') {
        const previous = agent.session.snapshotEvents().findLast(event => event.type === 'compaction/end' && event.data.sourceCommandId === request.id);
        if (previous?.type === 'compaction/end') return complete(previous.data.error ? `压缩失败：${previous.data.error}` : '已压缩较早的会话上下文。', !previous.data.error);
        await agent.whenIdle(); signal.throwIfAborted();
        const result = await (this.host.compaction as NanoCompaction).compactFocused(agent, argument, signal, CommandId(request.id));
        return complete(result ? `已压缩 ${result.shadowedSeqs.length} 项较早上下文。` : '当前没有需要压缩的历史。', true);
      }
      await agent.whenIdle(); signal.throwIfAborted();
      return await agent.runMaintenance(async () => {
        const route = this.route(agent); const selection = this.selections.get(agent.id)!;
        if (request.action === 'effort') {
          const info = await this.host.llm.resolveModelInfo(route.provider, route.model, signal);
          const efforts = info.reasoning?.efforts.map(effort => effort.id as string) ?? [];
          const effort = argument === 'none' ? 'off' : argument;
          if (!efforts.length) return complete('当前模型未提供可调整的推理强度。', false);
          if (!efforts.includes(effort)) return complete(`可用推理强度：${efforts.join(', ')}；当前为 ${route.reasoningEffort ?? info.reasoning?.defaultEffort ?? '默认'}。`, false);
          selection.effort = effort;
        } else throw new Error('Unknown session command');
        await (await this.state).table('sessions').put(key(agent.id), selection);
        return complete(`当前会话推理强度已设为 ${selection.effort}。`, true);
      });
    } catch (error) { return complete(signal.aborted ? '本次控制操作未执行：已取消。' : `控制操作失败：${String(error)}`, false); }
  }
  cancelCommands(sessionId: string) {
    for (const active of this.commands.values()) if (active.sessionId === sessionId) active.abort.abort();
  }
  async stop() { await this.fallback.stop(); for (const active of this.commands.values()) active.abort.abort(); await Promise.allSettled([...this.commands.values()].map(active => active.task)); }
}
