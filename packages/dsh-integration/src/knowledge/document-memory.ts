import { lstat, readFile, realpath } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ToolExecution } from '@deepseek-ai/dsh-tools';
import type { ContextFormed } from '@deepseek-ai/dsh-llm';
import * as ObservationPolicy from '@deepseek-ai/dsh-fs-observation-policy';
import { parsePatch } from '@deepseek-ai/dsh-fs-patch';
import type {} from '@deepseek-ai/dsh-working-directory';
import type {} from '../policy/approval.js';
import { isHumanSource } from '../input-source.js';
import type { AgentConfiguration, SessionBinding } from '../index.js';
import { MemoryDocuments, proactivityPolicyLimit, type MemoryConsolidationRole, type SourceEligibility } from './memory-documents.js';
import { resolveRoleFile, roleDocument, roleLimit, rolePath } from './role-document.js';

/** Resolve the three-state formal memory consolidation role for one Agent configuration. */
export function resolveMemoryConsolidationRole(config: Pick<AgentConfiguration, 'personal' | 'mode'>): MemoryConsolidationRole {
  if (config.personal) return 'personal';
  return config.mode === 'global' ? 'global_expert' : 'single_thread_expert';
}

declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    'runtime-context': { kind: 'runtime-context' } & ContextFormed;
  }
}

interface Options {
  isWorkWorker(agent: Agent): boolean;
  configOf(agent: Agent): AgentConfiguration | undefined;
  configs: Map<string, AgentConfiguration>;
  bindings: Map<string, SessionBinding>;
  held?(agentId: string): boolean;
  roleWorkspace?(agentId: string): Promise<string | null>;
}
interface MaintenanceArguments { action: 'status' | 'run'; request_ref?: string; importLegacy?: boolean }
const inside = (root: string, path: string) => { const rel = relative(root, path); return rel === '' || !rel.startsWith('..') && !isAbsolute(rel); };
const entrySection = 'nano-document-memory-entry';
const managedContextSections = new Set(['nano-document-memory', entrySection, 'nano-role-agreement']);
const changedPagesPrefix = 'These pages changed since your previous model request; reread before the next relevant decision: ';
const entryPreviewPrefix = 'Key memory exceeds the inline limit.';
const oversizedEntry = (path: string) => `Key memory is too long to include here. Read ${path} for the current contents.`;
interface PreparedMemory {
  main: boolean;
  memoryPath: string;
  memory: string;
  freshEntry: string;
  role?: string;
}

function scrubSignalsFromResult<T extends { isError?: boolean; value?: unknown }>(result: T): T {
  if (result.isError || !result.value || typeof result.value !== 'object') return result;
  const val = result.value as { matches?: Array<{ path?: string }>; paths?: unknown[] };
  if (Array.isArray(val.matches)) {
    const matches = val.matches.filter(item => typeof item?.path !== 'string' || !item.path.endsWith('proactivity-signals.md'));
    return matches.length === val.matches.length ? result : { ...result, value: { ...val, matches } };
  }
  if (Array.isArray(val.paths)) {
    const paths = val.paths.filter(item => typeof item !== 'string' || !item.endsWith('proactivity-signals.md'));
    return paths.length === val.paths.length ? result : { ...result, value: { ...val, paths } };
  }
  return result;
}

function savedEntry(agent: Agent) {
  const messages = agent.session.deriveMessages();
  for (let i = messages.length - 1; i >= 0; i--) {
    const source = messages[i]!.source;
    if (source.kind === 'compact-checkpoint') break;
    if (source.kind !== 'runtime-context' || source.form !== 'snapshot') continue;
    const sections = source.sections;
    const entry = sections.find(section => section.name === entrySection);
    if (entry) return entry.text;
    // Sessions created before this change stored the entry after four guidance paragraphs.
    const combined = sections.find(section => section.name === 'nano-document-memory');
    if (combined) {
      const text = combined.text.split('\n\n').slice(4).join('\n\n');
      const notice = text.lastIndexOf('\n\n' + changedPagesPrefix);
      if (text) return notice > text.lastIndexOf('</memory_content>') ? text.slice(0, notice) : text;
    }
  }
}

function latestWindowWakeBlocks(agent: Agent): { memoryTag?: string; policyBody?: string } {
  const messages = agent.session.deriveMessages();
  let memoryTag: string | undefined;
  let policyBody: string | undefined;
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]!;
    const source = message.source as { kind?: string; channel?: string };
    if (source.kind === 'compact-checkpoint') break;
    if (source.kind !== 'nano-system' || (source.channel !== 'proactive_review' && source.channel !== 'proactive_nightly')) {
      continue;
    }
    const text = message.content
      .filter((block): block is { type: 'text'; text: string } => block.type === 'text')
      .map(block => block.text)
      .join('\n');
    if (memoryTag === undefined) {
      const match = text.match(/<updated-formal-memory complete="(?:true|preview)">\n[\s\S]*?\n<\/updated-formal-memory>/);
      if (match) memoryTag = match[0];
    }
    if (policyBody === undefined) {
      const match = text.match(/<proactive-policy>\n([\s\S]*?)\n<\/proactive-policy>/);
      if (match) policyBody = match[1];
    }
    if (memoryTag !== undefined && policyBody !== undefined) break;
  }
  return { memoryTag, policyBody };
}

/** Integrates current document memory with native requests and actual file tool outcomes. */
export class DocumentMemory {
  private readonly libraries = new Map<string, { workspace: string; value: Promise<MemoryDocuments> }>();
  private readonly roleAgents = new WeakSet<Agent>();
  private readonly prepared = new WeakMap<Agent, PreparedMemory>();
  private readonly pending = new Set<Promise<unknown>>();
  run?: (agent: Agent, requestRef: string, importLegacy?: boolean) => Promise<unknown>;
  maintenanceStatus?: (agentId: string) => Promise<unknown>;
  constructor(private readonly ctx: Context, private readonly options: Options) {
    ctx.plugin(ObservationPolicy);
    const resolveEntry = (agent: Agent | undefined) => {
      const state = agent && this.prepared.get(agent);
      if (!agent || !state) return '';
      const windowEntry = savedEntry(agent);
      return !state.main && windowEntry?.startsWith(entryPreviewPrefix)
        ? oversizedEntry(state.memoryPath)
        : windowEntry ?? state.freshEntry;
    };
    ctx.systemPrompt.context({
      name: 'nano-document-memory',
      order: 600,
      interpolate: false,
      text: context => {
        const agent = context.agent ?? context.scope as Agent | undefined;
        return (agent && this.prepared.get(agent)?.memory) ?? '';
      },
    });
    ctx.systemPrompt.context({
      name: entrySection,
      order: 601,
      interpolate: false,
      text: context => resolveEntry(context.agent ?? context.scope as Agent | undefined),
    });
    ctx.systemPrompt.context({
      name: 'nano-role-agreement',
      order: 602,
      interpolate: false,
      text: context => {
        const agent = context.agent ?? context.scope as Agent | undefined;
        return (agent && this.prepared.get(agent)?.role) ?? '';
      },
    });
    ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
      const assembly = await next(); const agent = context.agent ?? context.scope as Agent | undefined;
      assembly.contexts = assembly.contexts.filter(section => !managedContextSections.has(section.name));
      const config = agent && options.configOf(agent);
      if (agent) {
        this.roleAgents.delete(agent);
        this.prepared.delete(agent);
      }
      if (!agent || !config || options.isWorkWorker(agent) || config.knowledge?.memoryMode === 'legacy' || ![...options.bindings.values()].some(binding => binding.agentId === config.agentId)) return assembly;
      const binding = options.bindings.get(agent.id);
      const main = binding?.agentId === config.agentId;
      const documents = await this.forConfig(config);
      const memoryPath = join(documents.root, 'MEMORY.md');
      const freshEntry = await this.entry(documents, main);
      const memory = [
        'Current saved Markdown is durable understanding, not user authorization, Task state or live permissions. Use read/glob/grep for memory files. Only Dreaming updates formal memory; never use write/edit, shell or other tools to bypass this boundary. Load nano-memory for memory guidance.',
        config.personal
          ? 'Role: personal assistant. Keep the owner’s background, relationships, preferences and workstreams; preserve exceptions and uncertainty. Confirmed proactive & intervention calibration lives in MEMORY.md; knowledge/proactivity-signals.md is an offline Dreaming observation pool—do not read or query it.'
          : config.mode === 'global'
            ? 'Role: independent expert. Keep domain/environment knowledge, audience-specific collaboration and verified work experience. A requester is not implicitly your owner. Confirmed role-wide and collaborator/conversation-scoped proactive calibration lives in MEMORY.md (with detailed collaborator/project context in entities/ and projects/); knowledge/proactivity-signals.md is an offline Dreaming observation pool—do not read or query it.'
            : 'Role: independent expert. Keep domain/environment knowledge, audience-specific collaboration and verified work experience. A requester is not implicitly your owner.',
        `Memory directory: ${documents.root}. This library belongs to the product Agent and does not follow a child working directory. Search this directory for more detailed memory.`,
        'Read the complete relevant pages before applying a conclusion. The inline MEMORY.md is a snapshot taken at the start of this context window. Current corrections supersede older context, restored notes and history. Update affected original children through the existing follow-up channel. Apply corrections and requests to stop using a memory immediately within their stated scope, without a maintenance call. Dreaming reads those original conversation messages and updates durable memory later. A correction limited to this turn does not delete a lasting preference. Do not claim memory is saved until the host reports it.',
      ].join('\n\n');
      let roleText: string | undefined;
      if (main) {
        const role = await this.readRole(config, true);
        if (role) {
          const owner = (binding as { ownerRef?: string }).ownerRef ?? config.personal?.ownerId ?? binding.ownerId;
          const confirmer = config.personal ? 'owner' : 'bound administrator';
          const privateContact = `Contact your ${confirmer} privately in this turn. Use send_message to ${JSON.stringify(`user:${owner}`)} if available, or reply in a verified private conversation with them. If neither is possible, bring it up the next time you can speak privately.`;
          const agreementPath = rolePath(documents.workspace);
          let currentAgreement: string;
          if ('error' in role) {
            currentAgreement = [
              `Role agreement file: ${agreementPath}.`,
              'The host could not read the saved role file. Check it with the ordinary read tool first.',
              privateContact,
              'Explain what you could verify, even if the read fails, and agree on how to restore a readable regular file.',
            ].join(' ');
          } else if (role.content.length > roleLimit) {
            currentAgreement = [
              `Role agreement file: ${agreementPath}.`,
              `The saved role file exceeds the ${roleLimit} UTF-16 code unit limit. Read the complete original first.`,
              privateContact,
              'Ask them for any missing text. Draft a shorter version that preserves the original meaning and send it privately. Continue from the existing draft if you already sent one. Save only after they explicitly confirm the exact text, then read the saved file again to verify that it is readable and within the limit.',
            ].join(' ');
          } else if (role.content) {
            currentAgreement = `Contents of ${agreementPath} — your confirmed role agreement:\n<role_content>\n${role.content}\n</role_content>`;
          } else {
            currentAgreement = `Role agreement file: ${agreementPath}.\n\nRole agreement is unset. In a private conversation with your ${confirmer}, offer to establish one useful long-term responsibility. Follow their current intent first: if they have an urgent task or defer setup, help with that and do not keep asking. Resume when they choose to discuss the agreement. Do not ask other contacts to define your role.`;
          }
          this.roleAgents.add(agent);
          roleText = [
            config.personal
              ? 'ROLE.md records how your owner wants you to help over time. Use it to understand what they want ongoing support with, what you should follow up on proactively, and what they handle themselves.'
              : 'ROLE.md records the long-term responsibilities, goals, and division of work you agreed on with your administrator. Use it to decide what you own, what you need to deliver, and what other collaborators are responsible for.',
            `Before establishing ROLE.md or discussing changes requested by your ${confirmer} (${JSON.stringify(owner)}) or proposed by you, load and follow the nano-role-agreement skill.`,
            currentAgreement,
          ].join('\n\n');
        }
      }
      this.prepared.set(agent, { main, memoryPath, memory, freshEntry, ...(roleText ? { role: roleText } : {}) });
      assembly.contexts.push({ name: 'nano-document-memory', text: memory, interpolate: false });
      assembly.contexts.push({ name: entrySection, text: resolveEntry(agent), interpolate: false });
      if (roleText) assembly.contexts.push({ name: 'nano-role-agreement', text: roleText, interpolate: false });
      return assembly;
    });
    const memoryWriteDenied = 'Only Dreaming may update formal memory. Use current corrections in this conversation; request memory_maintenance run when the user asks to save them.';
    const touchesFormalMemory = async (memoryRoot: string, candidateAbs: string): Promise<boolean> => {
      if (inside(memoryRoot, candidateAbs)) return true;
      const target = await ctx.fs.resolve(candidateAbs);
      if (inside(memoryRoot, ctx.fs.processPath(target))) return true;
      // Also resolve the nearest existing ancestor so creating a new file through a symlink to formal memory is caught.
      let cursor = dirname(candidateAbs);
      while (true) {
        const ancestorTarget = await ctx.fs.resolve(cursor);
        const info = await ctx.fs.stat(ancestorTarget);
        if (info) return inside(memoryRoot, ctx.fs.processPath(ancestorTarget));
        const parent = dirname(cursor);
        if (parent === cursor) return false;
        cursor = parent;
      }
    };
    ctx.on('tools/execute', async (exec, next) => {
      const agent = exec.agent; const config = agent && options.configOf(agent);
      if (!agent || !config || config.knowledge?.memoryMode === 'legacy') return next();
      const arg = exec.arguments as { file_path?: string; path?: string; command?: string; input?: unknown };
      const nonDreamingProactive = (!!config.personal || config.mode === 'global') && !String(agent.id).startsWith('dreaming-');
      const signalsError = 'knowledge/proactivity-signals.md is an offline Dreaming observation pool and cannot be read during foreground or worker turns. Rely on confirmed preferences in MEMORY.md.';
      if (nonDreamingProactive && exec.name === 'bash' && typeof arg.command === 'string' && arg.command.includes('proactivity-signals.md')) {
        throw new Error(signalsError);
      }
      const baseCwd = ctx.get('workingDirectory')?.get(agent.session) || agent.session.header.cwd;
      if (!baseCwd) return next();
      if (exec.name === 'apply_patch') {
        const rawInput = arg?.input;
        if (typeof rawInput !== 'string') return next();
        const documents = await this.forConfig(config);
        let operations: ReturnType<typeof parsePatch>;
        try {
          operations = parsePatch(rawInput);
        } catch {
          if (rawInput.includes('.nanoassistant') || rawInput.includes(documents.root)) throw new Error(memoryWriteDenied);
          return next();
        }
        for (const op of operations) {
          if (await touchesFormalMemory(documents.root, resolve(baseCwd, op.path))) throw new Error(memoryWriteDenied);
          if ('moveTo' in op && op.moveTo !== undefined && await touchesFormalMemory(documents.root, resolve(baseCwd, op.moveTo))) {
            throw new Error(memoryWriteDenied);
          }
        }
        return next();
      }
      if (!['read', 'write', 'edit', 'grep', 'glob'].includes(exec.name)) return next();
      const documents = await this.forConfig(config);
      const rawPath = exec.name === 'grep' || exec.name === 'glob' ? arg.path : arg.file_path;
      if (typeof rawPath !== 'string') {
        if (nonDreamingProactive && (exec.name === 'grep' || exec.name === 'glob')) return scrubSignalsFromResult(await next());
        return next();
      }
      const absolute = resolve(baseCwd, rawPath);
      if (exec.name === 'read' && this.roleAgents.has(agent) && absolute === rolePath(documents.workspace) && !await resolveRoleFile(ctx.fs, documents.workspace)) {
        throw new Error('The role path is not a regular file in the assigned workspace.');
      }
      const target = await ctx.fs.resolve(absolute); const canonical = ctx.fs.processPath(target);
      const signalsPath = join(documents.root, 'knowledge', 'proactivity-signals.md');
      if (nonDreamingProactive && (absolute === signalsPath || canonical === signalsPath)) {
        throw new Error(signalsError);
      }
      if (nonDreamingProactive && (exec.name === 'grep' || exec.name === 'glob') && (inside(absolute, signalsPath) || inside(canonical, signalsPath))) {
        return scrubSignalsFromResult(await next());
      }
      if (!await touchesFormalMemory(documents.root, absolute)) return next();
      if (exec.name === 'write' || exec.name === 'edit') throw new Error(memoryWriteDenied);
      return next();
    });
  }
  private async entry(documents: MemoryDocuments, main: boolean) {
    const view = await documents.context({ includePreview: main });
    const path = join(view.root, 'MEMORY.md');
    if (view.entry !== undefined) {
      return `Contents of ${path} — your one-page key memory:\n<memory_content>\n${view.entry || '(empty)'}\n</memory_content>`;
    }
    if (view.entryPreview !== undefined) {
      return `${entryPreviewPrefix} Later content is omitted. Read ${path} for the complete file.${view.entryPreview
        ? `\n<memory_content>\n${view.entryPreview}\n</memory_content>`
        : '\nNo complete opening block fits the preview budget.'}`;
    }
    return oversizedEntry(path);
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
    const value = MemoryDocuments.open(workspace, resolveMemoryConsolidationRole(config), this.ctx.fs);
    this.libraries.set(config.agentId, { workspace, value });
    try { const library = await value; if (config.personal) library.markSourcesPending(); return library; } catch (error) { this.libraries.delete(config.agentId); throw error; }
  }
  /** Read the Node-authorized agreement without using a child working directory. */
  async readRole(config: AgentConfiguration, initialize = false) {
    if (!config.workspace || config.knowledge?.memoryMode === 'legacy' || !this.options.roleWorkspace) return;
    const workspace = await this.options.roleWorkspace(config.agentId).catch(() => null);
    if (!workspace || await realpath(config.workspace).catch(() => null) !== workspace) return;
    return roleDocument(this.ctx.fs, workspace, undefined, initialize);
  }
  /** Register only in normal task presets; isolated Dreaming completes under host control. */
  registerTool(ctx: Context) {
    ctx.tools.register({ name: 'memory_maintenance', description: 'Control this Agent’s document memory. status reports backlog, eligibility and saved/version receipts; sourcesPending describes only source eligibility, never backlog. Use maintenance.backlog for observed pending material counts and blocked reasons. Its counts cover only the next bounded batch, not the total backlog; unavailable/blocked is not empty. It does not search knowledge. run requests a bounded incremental Dreaming pass and requires request_ref identifying the actual owner/requester input and remains subject to ordinary tool approval. Do not claim completion from acceptance or partial receipts. Read knowledge with ordinary file tools. Only Dreaming writes formal memory. importLegacy requests import from this owner’s registered legacy backup.',
      parameters: { type: 'object', properties: { action: { enum: ['status', 'run'] }, request_ref: { type: 'string' }, importLegacy: { type: 'boolean' } }, required: ['action'], additionalProperties: false },
      output: { schema: { type: 'object', additionalProperties: true }, render: (_args, result) => [{ type: 'text', text: JSON.stringify(result) }] },
      execute: (args, exec) => this.control(exec, args as MaintenanceArguments),
    });
  }
  private async control(exec: ToolExecution, args: MaintenanceArguments): Promise<unknown> {
    const agent = exec.agent!; const config = this.options.configOf(agent)!;
    if (this.options.isWorkWorker(agent)) throw new Error('Memory maintenance is unavailable for workers.');
    if (config.knowledge?.memoryMode === 'legacy') throw new Error('Document maintenance is unavailable in legacy mode.');
    const documents = await this.forConfig(config);
    if (args.action === 'status') return { mode: 'document', ...await this.status(documents), maintenance: await this.maintenanceStatus?.(config.agentId) };
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
    if (args.action !== 'run') throw new Error('Unsupported memory maintenance action.');
    if (!this.run) throw new Error('Dreaming is not available.');
    return this.run(agent, requestRef, args.importLegacy);
  }
  private async status(documents: MemoryDocuments) {
    const state = await documents.status();
    return { sourcesPending: state.sourcesPending,
      receipts: state.receipts.map(({ path, saved, versionRecorded, commit, error }) => ({ path, saved, versionRecorded, ...(commit ? { commit } : {}), ...(error ? { error } : {}) })) };
  }
  async syncSources(agentId: string, snapshot: SourceEligibility) {
    const config = [...this.options.configs.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error('Unknown memory owner.');
    if (config.knowledge?.memoryMode === 'legacy') return { mode: 'legacy' as const };
    return (await this.forConfig(config)).syncSources(snapshot);
  }
  async sourcesPending(agentId: string) {
    const config = [...this.options.configs.values()].find(config => config.agentId === agentId);
    if (config && config.knowledge?.memoryMode !== 'legacy') (await this.forConfig(config)).markSourcesPending();
  }
  /** Return the current MEMORY.md body and completeness flag when Dreaming updated it after this context window's initial snapshot. */
  async updatedEntrySinceWindowStart(agent: Agent): Promise<{ body: string; complete: boolean } | undefined> {
    const config = this.options.configOf(agent);
    if (!config || config.knowledge?.memoryMode === 'legacy') return undefined;
    const documents = await this.forConfig(config);
    const windowEntry = savedEntry(agent);
    const currentRendered = await this.entry(documents, true);
    if (windowEntry !== undefined && currentRendered === windowEntry) return undefined;
    const view = await documents.context({ includePreview: true });
    const body = (view.entry ?? view.entryPreview ?? '').trim();
    return body ? { body, complete: view.entry !== undefined } : undefined;
  }
  /** Return `<updated-formal-memory>` for a proactive wake only when unseen in the current context window. */
  async updatedEntryForWindowWake(agent: Agent): Promise<{ body: string; complete: boolean; renderedTag: string } | undefined> {
    const config = this.options.configOf(agent);
    if (!config || config.knowledge?.memoryMode === 'legacy') return undefined;
    const documents = await this.forConfig(config);
    const latest = latestWindowWakeBlocks(agent);
    const windowEntry = savedEntry(agent);
    // When this turn is the very first turn of a new window, system-prompt/assemble embeds fresh MEMORY.md directly.
    if (windowEntry === undefined && latest.memoryTag === undefined) return undefined;
    const currentRendered = await this.entry(documents, true);
    if (latest.memoryTag === undefined && currentRendered === windowEntry) return undefined;
    const view = await documents.context({ includePreview: true });
    const body = (view.entry ?? view.entryPreview ?? '').trim();
    if (!body) return undefined;
    const renderedTag = `<updated-formal-memory complete="${view.entry !== undefined ? 'true' : 'preview'}">\n${body}\n</updated-formal-memory>`;
    if (latest.memoryTag === renderedTag) return undefined;
    return { body, complete: view.entry !== undefined, renderedTag };
  }
  /** Return `<proactive-policy>` from `knowledge/proactivity-policy.md` only when valid, bounded, and unseen in this window. */
  async proactivePolicyForWindowWake(agent: Agent): Promise<{ body: string; renderedTag: string } | undefined> {
    const config = this.options.configOf(agent);
    if (!config || config.knowledge?.memoryMode === 'legacy' || (!config.personal && config.mode !== 'global')) {
      return undefined;
    }
    const documents = await this.forConfig(config);
    const latest = latestWindowWakeBlocks(agent);
    const policyAbs = join(documents.root, 'knowledge', 'proactivity-policy.md');
    const info = await lstat(policyAbs).catch(error => {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
      throw error;
    });
    if (!info) {
      if (latest.policyBody !== undefined && latest.policyBody !== '(none)') {
        return { body: '(none)', renderedTag: '<proactive-policy>\n(none)\n</proactive-policy>' };
      }
      return undefined;
    }
    if (!info.isFile()) return undefined;
    if (await realpath(policyAbs).catch(() => '') !== policyAbs) return undefined;
    const raw = await readFile(policyAbs, 'utf8');
    if (raw.length > proactivityPolicyLimit) return undefined;
    const body = raw.trim();
    if (!body) {
      if (latest.policyBody !== undefined && latest.policyBody !== '(none)') {
        return { body: '(none)', renderedTag: '<proactive-policy>\n(none)\n</proactive-policy>' };
      }
      return undefined;
    }
    if (latest.policyBody === body) return undefined;
    return { body, renderedTag: `<proactive-policy>\n${body}\n</proactive-policy>` };
  }
  async stop() { await Promise.allSettled(this.pending); for (const library of this.libraries.values()) await (await library.value).close(); this.libraries.clear(); }
}
