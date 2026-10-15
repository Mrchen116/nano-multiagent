/** Workspace ownership around native DSH package installation and scoped plugin trees. */
import { randomUUID } from 'node:crypto';
import { cp, mkdir, realpath, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Context } from '@deepseek-ai/cordis';
import { Loader, type EntryOptions } from '@deepseek-ai/cordis-plugin-loader';
import { Include } from '@deepseek-ai/cordis-plugin-include';
import { PluginManager, type ChangeResult } from '@deepseek-ai/dsh-plugin-manager';
import type { PluginInstallRequestId } from '@deepseek-ai/dsh-plugin-manager/types';
import { type ProfilePnpmInvocation, type RuntimeResolution, PluginPackages, bundlePatchPaths, composeEntries, createRuntimeResolution, initProfile, loadOverlayPatches, loadProfileDirectory, readProfileManifest } from '@deepseek-ai/dsh-app-boot';
import { auditRows, leakedServices } from '@deepseek-ai/dsh-agent-preset-registry';
import { scopeOf } from '@deepseek-ai/dsh-scope';
import type {} from '@deepseek-ai/dsh-hmr';
import type { AgentConfiguration } from './index.js';

const require = createRequire(import.meta.url);
const anchor = require.resolve('@deepseek-ai/dsh/package.json');
const inside = (root: string, path: string) => { const value = relative(root, path); return value !== '..' && !value.startsWith(`..${sep}`) && !isAbsolute(value); };
interface Mount { ctx: Context; config: AgentConfiguration; tree: Include; namespace: string; baseline: Set<string>; tools: string[] }
export interface PluginCommand { action: 'list_bundles' | 'install_bundle' | 'set_bundle' | 'remove_bundle'; target?: string; enabled?: boolean; approvedBuilds?: string[]; registry?: string }

type PluginText = string | Record<string, string>;
export interface PluginView {
  workspace: string;
  entries: {name: string; display_name: PluginText; description: PluginText; version?: string; enabled: boolean; state: string;
    rows: {id: string; name: PluginText}[]; removable: boolean; diagnostics: string[]}[];
  pending?: {action: string; target: string; enabled?: boolean; phase: 'waiting' | 'applying'};
  error?: string;
  diagnostics: string[];
}

/** Capture a native Include without exporting a second loader service. */
class WorkspaceInclude extends Include {
  constructor(ctx: Context, config: Include.Config & { mounted(tree: Include): void }) { super(ctx, config); config.mounted(this); }
}

/** Own workspace profiles while native DSH owns package operations and plugin lifecycles. */
export class WorkspaceExtensions {
  packageManager?: ProfilePnpmInvocation;
  private readonly owners = new Map<string, Promise<WorkspaceOwner>>();
  private creating: Promise<unknown> = Promise.resolve();
  private readonly mounts = new Set<Mount>();
  constructor(private readonly ctx: Context, private readonly changed: (agentId: string) => void) {
    ctx.effect(() => async () => { for (const owner of [...this.owners.values()].reverse()) await (await owner).close(); });
  }
  /** Mount only the trusted configured workspace, never a model-supplied scope.
   *
   * Args:
   *   ctx: Native preset scope receiving the tools.
   *   config: Node-owned workspace and capability selection.
   */
  async attach(ctx: Context, config: AgentConfiguration): Promise<void> {
    if (!config.workspace) return;
    const workspace = await realpath(config.workspace);
    let pending = this.owners.get(workspace);
    if (!pending) {
      // Native resolver wrappers must be installed and released in opposite orders.
      pending = this.creating.then(() => WorkspaceOwner.create(this.ctx, workspace, id => this.changed(id), this.packageManager));
      this.creating = pending.catch(() => {});
      this.owners.set(workspace, pending);
    }
    const owner = await pending;
    ctx.tools.register({ name: 'plugin_manager',
      description: 'Create, install and manage standard DSH plugins in this configured workspace (tools, prompt sections, scoped listeners and isolated services). Actions: list_bundles, install_bundle (target local bundle directory or package spec), set_bundle (target bundle name and enabled), remove_bundle. list_bundles returns profileDir: edit its cordis.patch.yml to configure installed entries through the native workspace-only user overlay (hot applied). Never edit installed package files, runtime.json or the host profile. Create a local standard DSH bundle with package.json {name,version,type:"module",dsh:{bundle:{patch:"./cordis.patch.yml"}}}, a patch [{insert:[{id:"my-tool",name:"./tool.mjs"}]}], and a JS plugin exporting inject=["tools"] and apply(ctx) that calls ctx.tools.register with name, description, parameters, output {schema,render}, execute. A zero-tool plugin can export inject=["systemPrompt"] and apply(ctx) { ctx.systemPrompt.section({name:"report-style",order:850,text:"Format expense reports as a table."}); }. Use ctx.effect(() => () => cleanup()) for owned resources. Service providers and consumers must share a group:true entry with isolate:{serviceName:true}, config:[provider,consumer]; root service leakage is rejected. Configure existing bundle row ids via user overlay so disabling the bundle also removes their contribution. An isolated compaction provider in this workspace tree becomes the current Agent preset engine: host automatic compaction yields and manual compact routes to it; it does not require changing the host provider or restarting the session. Local entries must stay inside the bundle. Successful installation makes new tool names available now without editing the static allowlist. Fix failed local source and install its directory again. Bundles and dependencies persist across restart. approvedBuilds only after explicit user approval for pending build scripts. Package replacement outside local bundles can require restart.',
      parameters: { type: 'object', properties: { action: { enum: ['list_bundles', 'install_bundle', 'set_bundle', 'remove_bundle'] }, target: { type: 'string' }, enabled: { type: 'boolean' }, approvedBuilds: { type: 'array', items: { type: 'string' } }, registry: { type: 'string' } }, required: ['action'], additionalProperties: false },
      output: { schema: { type: 'object' }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
      timeoutMs: 600_000,
      isConcurrencySafe: () => false,
      execute: (args, exec) => owner.command(args as PluginCommand, exec.callId, exec.signal),
    });
    const baseline = new Set(ctx.tools.schemas(scopeOf(ctx)).map(tool => tool.name));
    let tree!: Include;
    const fiber = ctx.plugin(WorkspaceInclude, { path: pathToFileURL(join(owner.dir, 'runtime.json')).href, mounted: (value: Include) => { tree = value; } });
    await fiber.await();
    const mount = { ctx, config, tree, namespace: randomUUID(), baseline, tools: [] as string[] };
    this.mounts.add(mount); owner.mounts.add(mount);
    ctx.effect(() => () => { this.mounts.delete(mount); owner.mounts.delete(mount); });
    // A broken persisted bundle must not prevent access to the management tool needed to repair it.
    await this.ctx.hmr.runExclusive(() => owner.refresh());
  }
  /** Manage an installed bundle through trusted configuration, retaining its scope until settlement.
   *
   * Args:
   *   config: Node-owned Agent configuration whose preset has been acquired.
   *   command: Read, enable/disable or remove command from the owner control plane.
   *   maintain: Reserve this workspace's idle Agents for the native mutation.
   */
  async manage(config: AgentConfiguration, command: PluginCommand, maintain: (workspace: string, job: () => Promise<void>) => Promise<void>): Promise<{view: PluginView; settled: Promise<void>}> {
    if (!config.workspace) throw new Error('Agent has no configured workspace');
    const workspace = await realpath(config.workspace);
    const owner = await this.owners.get(workspace);
    if (!owner) throw new Error('Workspace preset is not mounted');
    return owner.manage(command, job => maintain(workspace, job));
  }
  /** Return active workspace additions; static names never gain implicit authorization. */
  tools(agentId: string): string[] {
    return [...new Set([...this.mounts].filter(mount => mount.config.agentId === agentId).flatMap(mount => mount.tools))];
  }
}

class WorkspaceOwner {
  readonly mounts = new Set<Mount>();
  private chain: Promise<unknown> = Promise.resolve();
  private changing = false;
  private pending?: {action: string; target: string; enabled?: boolean; phase: 'waiting' | 'applying'};
  private pendingEntries?: Awaited<ReturnType<WorkspaceOwner['entries']>>;
  private error?: string;
  private readonly watches: (() => Promise<void>)[] = [];
  private diagnostics: string[] = [];
  private constructor(private readonly host: Context, readonly workspace: string, readonly dir: string, private readonly managerRoot: Context, private readonly resolver: Context, private resolution: RuntimeResolution, private readonly changed: (agentId: string) => void) {}
  static async create(host: Context, workspace: string, changed: (agentId: string) => void, packageManager = host.profileContext.packageManager): Promise<WorkspaceOwner> {
    const dir = join(workspace, '.nanoassistant', 'dsh-plugins');
    // A workspace owns an empty profile, not a second base runtime. initProfile preserves existing state.
    initProfile(dir, []);
    await writeFile(join(dir, 'runtime.json'), '[]', { flag: 'wx' }).catch(error => { if (error.code !== 'EEXIST') throw error; });
    const managerRoot = new Context();
    managerRoot.provide('profileContext', { name: 'workspace', dir, patchPath: join(dir, 'cordis.patch.yml'), installAnchor: anchor, cwd: workspace,
      home: dir, startedBundles: [], overlays: [], telemetryDisabledEnv: '1', ...(packageManager ? { packageManager } : {}) });
    // Each profile routes only its own files to the shared installation, never another workspace.
    const resolution = await createRuntimeResolution({ installAnchor: anchor, profile: loadProfileDirectory('nano', dir, anchor), home: dir });
    // Keep native manager auto-refresh separate: retiring fibers need the old mappings until cleanup finishes.
    const resolver = managerRoot.isolate('pluginPackages', Symbol());
    await resolver.plugin(PluginPackages, { resolution }).await();
    await managerRoot.plugin(Loader).await();
    await managerRoot.plugin(PluginManager, {}).await();
    const owner = new WorkspaceOwner(host, workspace, dir, managerRoot, resolver, resolution, changed);
    for (const file of ['package.json', 'cordis.patch.yml']) owner.watches.push(await host.hmr.watchConfig(join(dir, file), async () => {
      // Management refreshes explicitly after the native package transaction; its intermediate writes are not activations.
      if (!owner.changing) await owner.refresh();
    }));
    return owner;
  }
  private rows(): EntryOptions[] {
    const profile = loadProfileDirectory('nano', this.dir, anchor);
    if (profile.skippedBundles.length) throw new Error(profile.skippedBundles.map(item => `${item.packageName}: ${item.reason}`).join('\n'));
    const manifest = readProfileManifest('nano', this.dir);
    const layers = profile.layers.map(layer => {
      const spec = manifest.dependencies?.[layer.packageName];
      const generation = spec?.startsWith('file:') ? resolve(this.dir, spec.slice(5)) : undefined;
      if (!generation || !inside(join(this.dir, 'generations'), generation)) return layer.patches;
      // Hoisted pnpm installs reuse node_modules/<name>. Resolve self-authored entries from the immutable source generation.
      const bundle = readProfileManifest('nano', generation).dsh?.bundle;
      if (!bundle) throw new Error(`Missing bundle metadata in ${generation}`);
      return bundlePatchPaths(generation, bundle).flatMap(file => loadOverlayPatches('nano', file));
    });
    return composeEntries([...layers, profile.patches]);
  }
  async refresh(): Promise<void> {
    let rows: EntryOptions[];
    let next: RuntimeResolution;
    try {
      rows = this.rows();
      next = await createRuntimeResolution({ installAnchor: anchor, profile: loadProfileDirectory('nano', this.dir, anchor), home: this.dir });
      const retained = { ...next,
        entries: [...next.entries, ...this.resolution.entries.filter(old => !next.entries.some(entry => entry.name === old.name))],
        localPackageNames: [...new Set([...next.localPackageNames, ...this.resolution.localPackageNames])],
        linkedRoots: [...next.linkedRoots, ...this.resolution.linkedRoots.filter(old => !next.linkedRoots.some(root => root.realPath === old.realPath))],
      };
      this.resolver.pluginPackages.replace(retained);
      this.resolution = retained;
    }
    catch (error) { this.diagnostics = [String(error)]; return; }
    const diagnostics: string[] = [];
    for (const mount of this.mounts) {
      // Services can contribute static tools after preset construction (for example Cron previews).
      // Only names introduced by this Include update may become workspace additions.
      for (const tool of mount.ctx.tools.schemas(scopeOf(mount.ctx))) {
        if (!mount.tools.includes(tool.name)) mount.baseline.add(tool.name);
      }
      const loadErrors: string[] = [];
      // Loader deliberately logs import failures instead of throwing them; retain the original local diagnostic too.
      const stop = this.host.logger.exporter({ levels: { default: 2 }, export: message => {
        if (message.type !== 'error' || loadErrors.length >= 8) return;
        for (const arg of message.args) if (arg instanceof Error && arg.stack?.includes(this.dir)) loadErrors.push(arg.stack.slice(0, 3000));
      } });
      const retired = new Set([...mount.tree.entries()].flatMap(entry => entry.fiber ? [entry.fiber] : []));
      const scoped = (entries: EntryOptions[]): EntryOptions[] => entries.map(row => ({ ...row,
        ...(row.isolate ? {isolate: Object.fromEntries(Object.entries(row.isolate).map(([name, label]) => [name, typeof label === 'string' ? `${mount.namespace}:${label}` : label]))} : {}),
        ...(row.group && Array.isArray(row.config) ? {config: scoped(row.config)} : {}),
      }));
      const mountedRows = scoped(rows);
      let audit: Awaited<ReturnType<typeof auditRows>>;
      try { await mount.tree.root.update(structuredClone(mountedRows)); audit = await auditRows(mount.tree); }
      finally { stop(); }
      const leaking = new Set<string>();
      for (const entry of mount.tree.entries()) if (entry.fiber && !entry.disabled) {
        const services = leakedServices(mount.ctx, entry.fiber);
        if (services.length) { leaking.add(entry.options.id); audit.failed.push(`${entry.options.id} (${entry.options.name}): root services ${services.join(', ')}; use a local isolate group`); }
      }
      diagnostics.push(...audit.failed, ...audit.pending);
      if (audit.failed.length || audit.pending.length) diagnostics.push(...loadErrors);
      // Retire failed rows so a saved broken bundle cannot poison the preset or leave partial registrations callable.
      if (audit.failed.length || audit.pending.length) {
        const unusable = new Set(leaking);
        for (const entry of mount.tree.entries()) {
          if (entry.disabled) continue;
          if (entry.fiber) retired.add(entry.fiber);
          try {
            if (!entry.fiber) throw new Error('Not loaded');
            await entry.fiber.await();
            if (Object.keys(entry.fiber.inject).some(name => entry.fiber!.ctx.get(name) === undefined)) throw new Error('Missing service');
          } catch { unusable.add(entry.options.id); }
        }
        const usable = (entries: EntryOptions[]): EntryOptions[] => entries.filter(row => !unusable.has(row.id)).map(row => row.group && Array.isArray(row.config)
          ? { ...row, config: usable(row.config) } : row);
        await mount.tree.root.update(structuredClone(usable(mountedRows)));
        await mount.tree.await();
      }
      const active = new Set([...mount.tree.entries()].filter(entry => !entry.disabled).map(entry => entry.fiber));
      await Promise.all([...retired].filter(fiber => !active.has(fiber)).map(fiber => fiber.inertia));
      mount.tools = mount.ctx.tools.schemas(scopeOf(mount.ctx)).map(tool => tool.name).filter(name => !mount.baseline.has(name));
      this.changed(mount.config.agentId);
    }
    // The removed plugins have drained; their dependency mappings can now leave the native table.
    this.resolver.pluginPackages.replace(next);
    this.resolution = next;
    this.diagnostics = [...new Set(diagnostics)];
  }
  private async stage(target: string): Promise<string | undefined> {
    if (!(isAbsolute(target) || target.startsWith('.') || target.startsWith('file:') || target.startsWith('link:'))) return;
    const source = await realpath(resolve(this.workspace, target.replace(/^(file|link):/, '')));
    if (!inside(this.workspace, source) || inside(source, this.dir)) throw new Error('Local plugin bundle must be inside this workspace and outside its managed profile');
    const dir = join(this.dir, 'generations', randomUUID());
    await mkdir(dir, { recursive: true });
    await cp(source, dir, { recursive: true, filter: path => !['node_modules', '.git'].includes(basename(path)) });
    const bundle = readProfileManifest('nano', dir).dsh?.bundle;
    if (!bundle) throw new Error('Local package must declare dsh.bundle');
    const patches = bundlePatchPaths(dir, bundle).flatMap(file => loadOverlayPatches('nano', file));
    const check = (rows: EntryOptions[]) => { for (const row of rows) {
      if (row.group && Array.isArray(row.config)) check(row.config);
      else if (!row.name?.startsWith('file:') || !inside(dir, fileURLToPath(row.name))) throw new Error('Local bundle plugin entries must use relative files inside the bundle');
    } };
    check(composeEntries([patches]));
    return `file:${dir}`;
  }
  private async entries() {
    return (await this.managerRoot.pluginManager.listBundles()).filter(bundle => bundle.installed).map(bundle => {
      const diagnostics = [...(bundle.error ? [bundle.error.diagnostic ?? bundle.error.code] : []),
        ...this.diagnostics.filter(message => bundle.rows.some(row => message.startsWith(`${row.rowId} (`)))];
      return { name: bundle.name, display_name: bundle.meta?.title ?? bundle.name, description: bundle.meta?.description ?? bundle.description ?? '',
        version: bundle.version, enabled: bundle.enabled, state: diagnostics.length ? 'failed' : bundle.enabled ? 'enabled' : 'disabled',
        rows: bundle.rows.map(row => ({id: row.rowId, name: row.meta?.title ?? row.rowId})), removable: bundle.removable, diagnostics };
    });
  }
  private async view() {
    return {workspace: this.workspace, entries: this.pendingEntries ?? await this.entries(), ...(this.pending ? {pending: {...this.pending}} : {}),
      ...(this.error ? {error: this.error} : {}), diagnostics: this.diagnostics};
  }
  async manage(args: PluginCommand, maintain: (job: () => Promise<void>) => Promise<void>) {
    if (args.action === 'list_bundles') return {view: await this.view(), settled: Promise.resolve()};
    if (!['set_bundle', 'remove_bundle'].includes(args.action) || !args.target || args.action === 'set_bundle' && typeof args.enabled !== 'boolean') throw new Error('Invalid plugin control command');
    if (this.pending) throw new Error('Workspace plugin change is already pending');
    this.pending = {action: args.action, target: args.target, ...(args.enabled !== undefined ? {enabled: args.enabled} : {}), phase: 'waiting'};
    this.error = undefined;
    try { this.pendingEntries = await this.entries(); }
    catch (error) { this.pending = undefined; throw error; }
    const settled = this.chain.then(() => maintain(async () => {
      this.pending!.phase = 'applying';
      const result = await this.execute(args, randomUUID(), new AbortController().signal);
      if (result.error) this.error = result.error.diagnostic ?? result.error.code;
    })).catch(error => {this.error = String(error);}).finally(() => {this.pending = undefined; this.pendingEntries = undefined;});
    this.chain = settled;
    return {view: await this.view(), settled};
  }
  command(args: PluginCommand, callId: string, signal: AbortSignal): Promise<unknown> {
    // Reads must never sit behind an operation waiting for the calling Agent to become idle.
    if (args.action === 'list_bundles') return this.managerRoot.pluginManager.listBundles().then(entries => ({profileDir: this.dir, entries: entries.filter(bundle => bundle.installed), diagnostics: this.diagnostics, ...(this.pending ? {pending: this.pending} : {})}));
    if (this.pending) return Promise.resolve({application:'failed', error:{code:'busy',diagnostic:'A workspace plugin change is pending. Finish this turn and retry later.'}});
    const task = this.chain.then(() => this.execute(args, callId, signal));
    this.chain = task.catch(() => {});
    return task;
  }
  private async execute(args: PluginCommand, callId: string, signal: AbortSignal) {
      signal.throwIfAborted();
      const manager = this.managerRoot.pluginManager;
      const requestId = callId as PluginInstallRequestId;
      if (!args.target) throw new Error('target is required');
      const previousDiagnostics = new Set(this.diagnostics);
      const previousBundles = await manager.listBundles();
      const previousPackages = new Set(Object.keys(readProfileManifest('nano', this.dir).dependencies ?? {}));
      this.changing = true;
      let result: ChangeResult;
      let local = false;
      const cancel = () => { void manager.cancelInstall(requestId); };
      signal.addEventListener('abort', cancel, { once: true });
      try {
        if (args.action === 'install_bundle') {
          const staged = await this.stage(args.target); local = staged !== undefined;
          signal.throwIfAborted();
          const localName = staged && readProfileManifest('nano', staged.slice(5)).name;
          const prior = previousBundles.find(bundle => bundle.name === localName || bundle.name === args.target);
          result = await manager.installBundle(staged ?? args.target, { enabled: args.enabled ?? (prior?.installed ? prior.enabled : undefined), approvedBuilds: args.approvedBuilds, registry: args.registry, requestId });
          // Package specs can include aliases or versions. The native result owns their resolved name.
          if (!result.error && args.enabled === undefined && result.bundle && previousBundles.some(bundle => bundle.name === result.bundle && bundle.installed && !bundle.enabled)) {
            const restored = await manager.setBundleEnabled(result.bundle, false);
            if (restored.error) return restored;
            result = {...result, enabled: false};
          }
        } else {
          if (!(await manager.listBundles()).some(bundle => bundle.name === args.target && bundle.installed)) throw new Error('Bundle is not installed in this workspace');
          if (args.action === 'set_bundle') {
            if (args.enabled === undefined) throw new Error('enabled is required');
            result = await manager.setBundleEnabled(args.target, args.enabled);
          } else {
            result = await manager.setBundleEnabled(args.target, false);
            if (result.error) return result;
            await this.host.hmr.runExclusive(() => this.refresh());
            result = await manager.removeBundle(args.target);
          }
        }
        signal.throwIfAborted();
        if (result.error || result.application === 'cancelled') return result;
        // Native manager owns no execution tree. Only this scoped activation can report that a tool is actually live.
        if (!local && args.action === 'install_bundle' && result.application === 'restart-required'
          && result.bundle && previousPackages.has(result.bundle)) return result;
        await this.host.hmr.runExclusive(() => this.refresh());
        const target = (await manager.listBundles()).find(bundle => bundle.name === (result.bundle ?? args.target));
        const failures = this.diagnostics.filter(diagnostic => !previousDiagnostics.has(diagnostic)
          || args.action !== 'remove_bundle' && args.enabled !== false && target?.rows.some(row => diagnostic.startsWith(`${row.rowId} (`)));
        return { ...result, profileDir: this.dir, application: failures.length ? 'failed' : 'applied', warnings: this.diagnostics,
          ...(failures.length ? { error: { code: 'activation-failed', diagnostic: failures.join('\n') } } : {}),
          tools: [...new Set([...this.mounts].flatMap(mount => mount.tools))] };
      } finally { signal.removeEventListener('abort', cancel); this.changing = false; }
  }
  async close(): Promise<void> {
    await this.chain;
    for (const dispose of this.watches) await dispose();
    for (const mount of this.mounts) {
      const fibers = [...mount.tree.entries()].flatMap(entry => entry.fiber ? [entry.fiber] : []);
      await mount.tree.root.update([]);
      await Promise.all(fibers.map(fiber => fiber.inertia));
    }
    await this.managerRoot.fiber.dispose();
  }
}
