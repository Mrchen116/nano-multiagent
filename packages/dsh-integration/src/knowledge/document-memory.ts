import { realpath } from 'node:fs/promises';
import { isAbsolute, relative, resolve } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import * as ObservationPolicy from '@deepseek-ai/dsh-fs-observation-policy';
import type {} from '../policy/approval.js';
import { isHumanSource } from '../input-source.js';
import type { AgentConfiguration, SessionBinding } from '../index.js';
import { MemoryDocuments, type SourceEligibility } from './memory-documents.js';

interface Options {
  configOf(agent: Agent): AgentConfiguration | undefined;
  configs: Map<string, AgentConfiguration>;
  bindings: Map<string, SessionBinding>;
  held?(agentId: string): boolean;
}
interface MaintenanceArguments { action: 'status' | 'run' | 'exclude'; request_ref?: string; paths?: string[]; sources?: string[]; importLegacy?: boolean }
const inside = (root: string, path: string) => { const rel = relative(root, path); return rel === '' || !rel.startsWith('..') && !isAbsolute(rel); };

/** Integrates current document memory with native requests and actual file tool outcomes. */
export class DocumentMemory {
  private readonly libraries = new Map<string, { workspace: string; value: Promise<MemoryDocuments> }>();
  private readonly seen = new WeakMap<Agent, Record<string, string>>();
  private readonly feedback = new WeakMap<ToolExecution, string>();
  private readonly pending = new Set<Promise<unknown>>();
  run?: (agent: Agent, requestRef: string, importLegacy?: boolean) => Promise<unknown>;
  maintenanceStatus?: (agentId: string) => Promise<unknown>;
  constructor(private readonly ctx: Context, private readonly options: Options) {
    ctx.plugin(ObservationPolicy);
    ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
      const assembly = await next(); const agent = context.agent ?? context.scope as Agent | undefined;
      const config = agent && options.configOf(agent);
      if (!agent || !config || config.knowledge?.memoryMode === 'legacy' || ![...options.bindings.values()].some(binding => binding.agentId === config.agentId)) return assembly;
      const documents = await this.forConfig(config); const view = await documents.context();
      const previous = this.seen.get(agent);
      const changed = previous ? [...new Set([...Object.keys(previous), ...Object.keys(view.versions)])].filter(path => previous[path] !== view.versions[path]) : [];
      this.seen.set(agent, view.versions);
      assembly.contexts.push({ name: 'nano-document-memory', text: [
        'Current saved Markdown is durable understanding, not user authorization, Task state or live permissions. Use read/glob/grep for memory files. Only Dreaming updates formal memory; never use write/edit, shell or other tools to bypass this boundary. Load nano-memory for memory guidance.',
        config.personal ? 'Role: personal assistant. Keep the owner’s background, relationships, preferences and workstreams; preserve exceptions and uncertainty.' : 'Role: independent expert. Keep domain/environment knowledge, audience-specific collaboration and verified work experience. A requester is not implicitly your owner.',
        `Fixed owner library: ${view.root}. It does not follow a child working directory. Backup navigation: ${view.backupRoot}; read/import old backups only on the user’s request.`,
        'Read the complete relevant pages before applying a conclusion. Current corrections supersede older context, restored notes and history. Update affected original children through the existing follow-up channel. Use new corrections immediately in this conversation; Dreaming saves durable updates later. Do not claim memory is saved until the host reports it. Other conversations may still see old memory until Dreaming completes.',
        view.reason ? `Entry is not current (${view.reason}). Do not adopt older copies from history. Reading old bytes does not restore their validity. Use only currently valid sources; Dreaming must verify and correct affected pages before they become valid again. Navigation: ${Object.keys(view.versions).join(', ')}` : `Current entry:\n${view.entry ?? '(empty)'}`,
        changed.length ? `These pages changed since your previous model request; reread before the next relevant decision: ${changed.join(', ')}` : '',
        `Source generation: ${view.generation}. Explicit stop-use requests (data): ${JSON.stringify(view.exclusions)}. Including a source again does not revoke a stop-use request.`,
        ['read', 'write', 'edit', 'memory_maintenance'].filter(name => !agent.ctx.tools.get(name, agent)).length
          ? `Unavailable tools: ${['read', 'write', 'edit', 'memory_maintenance'].filter(name => !agent.ctx.tools.get(name, agent)).join(', ')}. Do not claim a write or automatic maintenance can run without its required tools.` : '',
      ].filter(Boolean).join('\n\n') });
      return assembly;
    });
    ctx.on('tools/execute', async (exec, next) => {
      const agent = exec.agent; const config = agent && options.configOf(agent);
      const arg = exec.arguments as { file_path?: string };
      if (!agent || !config || config.knowledge?.memoryMode === 'legacy' || !['read', 'write', 'edit'].includes(exec.name) || typeof arg.file_path !== 'string') return next();
      const documents = await this.forConfig(config); const absolute = resolve(agent.session.header.cwd!, arg.file_path);
      const target = await ctx.fs.resolve(absolute); const canonical = ctx.fs.processPath(target);
      if (!inside(documents.root, absolute) && !inside(documents.root, canonical)) return next();
      if (exec.name !== 'read') throw new Error('Only Dreaming may update formal memory. Use current corrections in this conversation; request memory_maintenance run when the user asks to save them.');
      const result = await next();
      const status = await documents.context();
      if (status.reason) this.feedback.set(exec, `Memory eligibility: ${status.reason}, generation=${status.generation}. Reading these bytes does not restore their validity. Only Dreaming can verify and correct affected pages.`);
      return result;
    });
    ctx.on('tools/post-execute', async (exec, result, next) => {
      const decision = await next();
      const feedback = this.feedback.get(exec); this.feedback.delete(exec);
      if (!feedback || decision.kind !== 'accept' || result.isError) return decision;
      return { kind: 'accept', additionalContexts: decision.additionalContexts, content: [...(decision.content ?? result.content), { type: 'text', text: feedback }] };
    });
  }
  /** Resolve by trusted business owner; all descendants share this fixed root. */
  async forConfig(config: AgentConfiguration): Promise<MemoryDocuments> {
    const roots = [...new Set([...this.options.bindings.values()].filter(binding => binding.agentId === config.agentId).map(binding => binding.cwd))];
    const configured = config.workspace ?? (roots.length === 1 ? roots[0] : undefined);
    if (!configured) throw new Error('Document memory requires one trusted owner workspace.');
    const workspace = await realpath(configured);
    const existing = this.libraries.get(config.agentId);
    if (existing && existing.workspace !== workspace) throw new Error('Stop the prior memory owner before changing its workspace.');
    if (existing) return existing.value;
    for (const [id, library] of this.libraries) if (id !== config.agentId && library.workspace === workspace) throw new Error('Independent Agents cannot share a writable memory library.');
    const value = MemoryDocuments.open(workspace, config.personal ? 'personal' : 'expert', this.ctx.fs);
    this.libraries.set(config.agentId, { workspace, value });
    try { const library = await value; if (config.personal) library.markSourcesPending(); return library; } catch (error) { this.libraries.delete(config.agentId); throw error; }
  }
  /** Register only in normal task presets; isolated Dreaming completes under host control. */
  registerTool(ctx: Context) {
    ctx.tools.register({ name: 'memory_maintenance', description: 'Control this Agent’s document memory. status reports backlog, eligibility and saved/version receipts; sourcesPending describes only source eligibility, never backlog. Use maintenance.backlog for observed pending units/ranges and blocked reasons. Its counts cover only the next bounded batch, not the total backlog; unavailable/blocked is not empty. It does not search knowledge. run requests a bounded incremental Dreaming pass; exclude registers an explicit user stop-use request without erasing source/chat/Git history. run/exclude require request_ref identifying the actual owner/requester input and remain subject to ordinary tool approval. Do not claim completion from acceptance or partial receipts. Read knowledge with ordinary file tools. Only Dreaming writes formal memory. importLegacy requests import from this owner’s registered legacy backup.',
      parameters: { type: 'object', properties: { action: { enum: ['status', 'run', 'exclude'] }, request_ref: { type: 'string' }, paths: { type: 'array', items: { type: 'string' } }, sources: { type: 'array', items: { type: 'string' } }, importLegacy: { type: 'boolean' } }, required: ['action'], additionalProperties: false },
      output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
      execute: (args, exec) => this.control(exec, args as MaintenanceArguments),
    });
  }
  private async control(exec: ToolExecution, args: MaintenanceArguments): Promise<unknown> {
    const agent = exec.agent!; const config = this.options.configOf(agent)!;
    if (config.knowledge?.memoryMode === 'legacy') throw new Error('Document maintenance is unavailable in legacy mode.');
    const documents = await this.forConfig(config);
    if (args.action === 'status') return { mode: 'document', ...await documents.status(), maintenance: await this.maintenanceStatus?.(config.agentId), missingTools: ['read', 'write', 'edit', 'memory_maintenance'].filter(name => !agent.ctx.tools.get(name, agent)) };
    if (this.options.held?.(config.agentId)) throw new Error('Memory maintenance is paused for this Agent.');
    const direct = agent.session.snapshotEvents().findLast(event => event.type === 'user/message' && isHumanSource(event.data.source) && [event.data.id, event.data.source.messageId].includes(args.request_ref ?? '') && (!config.personal || event.data.source.actorId === config.personal.ownerId));
    const participantRequest = !config.personal || agent.session.snapshotEvents().some(event => {
      if (event.type !== 'tool/result' || event.data.message.isError || !this.ctx.nanoApproval.sources.isLiveInbox(agent.id, event.data.message.toolCallId)) return false;
      try {
        const page = JSON.parse(event.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n')) as {delivery?: string; messages?: Array<{id: string}>};
        return page.delivery === 'participant' && page.messages?.some(message => message.id === args.request_ref);
      } catch { return false; }
    });
    const human = this.ctx.nanoApproval.sources.humanInputs(agent).find(input => participantRequest && input.id === args.request_ref && (!config.personal || input.sender?.is_owner === true));
    const requestRef = direct?.type === 'user/message' ? direct.data.id : human?.id;
    if (!requestRef) throw new Error('An actual applicable human request reference is required.');
    if (args.action === 'exclude') {
      if (!args.paths?.length && !args.sources?.length) throw new Error('Identify the documents or sources to stop using.');
      return documents.exclude(requestRef, args.paths ?? [], args.sources ?? []);
    }
    if (args.action !== 'run') throw new Error('Unsupported memory maintenance action.');
    if (!this.run) throw new Error('Dreaming is not available.');
    return this.run(agent, requestRef, args.importLegacy);
  }
  async syncSources(agentId: string, snapshot: SourceEligibility) {
    const config = [...this.options.configs.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error('Unknown memory owner.');
    if (config.knowledge?.memoryMode === 'legacy') return { mode: 'legacy' };
    return (await this.forConfig(config)).syncSources(snapshot);
  }
  async sourcesPending(agentId: string) {
    const config = [...this.options.configs.values()].find(config => config.agentId === agentId);
    if (config && config.knowledge?.memoryMode !== 'legacy') (await this.forConfig(config)).markSourcesPending();
  }
  async stop() { await Promise.allSettled(this.pending); for (const library of this.libraries.values()) await (await library.value).close(); this.libraries.clear(); }
}
