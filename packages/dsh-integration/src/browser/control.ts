import { randomBytes } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { PreToolDecision, ToolExecution } from '@deepseek-ai/dsh-tools';
import { DriverClient, type BrowserDriverLike, type DriverProbe } from './driver.js';
import { browserError, isBrowserError } from './errors.js';
import { ReadRegistry, normalizeBoundWindow, selectTab, type BoundWindow, type DriverTab, type TabMatcher } from './identity.js';
import { ScreenshotStore, pngSize } from './screenshots.js';
import { WindowRegistry, choosePrimaryWindow, normalizeWindows, type BindProbe, type DriverWindow } from './windows.js';
import { classifyNewWindows, type EventClassification } from './events.js';
import { evaluateTurnGate, judgmentSession, openTurn, liveTurnSession, type TurnGateDecision, type TurnSession } from '../policy/turn.js';
import { BROWSER_ACT_ACTIONS, DEFAULT_READ_CHARS, MAX_READ_CHARS, validateBrowserArguments, staticBrowserGuard } from './guard.js';

const SESSION_LABEL = /^nano-br-[0-9a-f]{8}$/;
const REFS_LIMIT = 200;
const COOLDOWN_MS = 300_000;
const MAX_INSTANCES = 2;

interface Instance {
  label: string;
  pid: string;
  version: string;
  windows: WindowRegistry;
  reads: ReadRegistry;
}

interface AgentState {
  instance?: Instance;
  /** Retained until confirmed cleanup or idle-expiry cooldown, even before registration. */
  ownership?: { label: string; pid?: string };
  /** A prepare is in flight; counts toward the process-wide instance cap. */
  launching?: boolean;
  /** Prevent new work from entering while queued disposal drains. */
  disposing?: boolean;
  /** Only a settled disposal may leave an expiry-prunable ownership tombstone. */
  disposalFinished?: boolean;
  cooldown?: { failedAt: number; until: number; detail: string };
  queue: Promise<unknown>;
}

export interface BrowserControlOptions {
  driver?: BrowserDriverLike;
  /** Live Agent registry used for subagent lineage; missing parents are chain breaks. */
  lookup: (id: string) => TurnSession | undefined;
  liveHumanTimes?: (sessionId: string, afterSeq: number) => readonly number[];
  now?: () => number;
  screenshots?: ScreenshotStore;
  logger?: { warn: (...args: unknown[]) => void };
  maxInstances?: number;
}

export interface BrowserReadArguments {
  tab?: TabMatcher;
  window_id?: string;
  query?: string;
  screenshot?: boolean;
  max_chars?: number;
}

export interface BrowserActArguments {
  action: 'open' | 'click' | 'type' | 'scroll';
  url?: string;
  read_id?: string;
  ref?: string;
  text?: string;
  replace?: boolean;
  delta_y?: number;
  delta_x?: number;
  screenshot?: boolean;
  window_id?: string;
  tab?: TabMatcher;
}

export interface ScreenshotView { path: string; width: number; height: number }

export interface BrowserReadResult {
  read_id: string;
  tab: { url: string; title: string; active: boolean; window_id: string };
  text: string;
  refs: { ref: string; role: string; name: string; actions?: string[] }[];
  truncated: boolean;
  screenshot?: ScreenshotView;
  screenshot_omitted?: string;
  driver: { version: string };
  events?: EventClassification['events'];
  ignored?: EventClassification['ignored'];
  foreground_released?: true;
  notice?: string;
}

export interface BrowserActResult {
  action: BrowserActArguments['action'];
  read_id?: string;
  dispatched: true;
  observed: { url: string; title: string; active: boolean };
  effect: 'changed' | 'unverifiable' | 'unchanged';
  text_after?: string;
  screenshot?: ScreenshotView;
  screenshot_omitted?: string;
  events?: EventClassification['events'];
  ignored?: EventClassification['ignored'];
  foreground_released?: true;
  notice?: string;
}

interface TurnKey { sessionId: string; turnStartSeq: number }

interface PageSnapshot {
  url: string;
  title: string;
  text: string;
  refs: BrowserReadResult['refs'];
  truncated: boolean;
  screenshot?: string;
}

/** Per-Agent browser page control with process-local state only. */
export class BrowserControl {
  private readonly driver: BrowserDriverLike;
  private readonly lookup: (id: string) => TurnSession | undefined;
  private readonly now: () => number;
  private readonly screenshots: ScreenshotStore;
  private readonly logger?: BrowserControlOptions['logger'];
  private readonly maxInstances: number;
  private readonly states = new Map<string, AgentState>();
  private readonly consumedTurns = new Map<string, number>();
  private readonly liveHumanTimes: NonNullable<BrowserControlOptions['liveHumanTimes']>;

  constructor(options: BrowserControlOptions) {
    this.driver = options.driver ?? new DriverClient();
    this.lookup = options.lookup;
    this.liveHumanTimes = options.liveHumanTimes ?? (() => []);
    this.now = options.now ?? Date.now;
    this.screenshots = options.screenshots ?? new ScreenshotStore({ now: this.now });
    this.logger = options.logger;
    this.maxInstances = options.maxInstances ?? MAX_INSTANCES;
  }

  /** Install the deterministic guard before the approval classifier. */
  install(ctx: Context): void {
    ctx.on('tools/pre-execute', async (exec: ToolExecution, next: () => Promise<PreToolDecision>) => {
      const error = exec.agent && this.precheck(exec.agent, exec.name, exec.arguments);
      if (error) return { kind: 'deny', reason: error.message, info: { name: error.name, code: error.code } };
      return next();
    }, { prepend: true });
    ctx.on('agent/disposed', ({ agent }) => { void this.dispose(agent.id); });
  }

  /** Synchronous pre-execute decision with no driver, file or process I/O. */
  precheck(agent: Agent, tool: string, args: unknown) {
    if (!['browser_read', 'browser_act'].includes(tool)) return undefined;
    const state = this.state(agent.id);
    const cooldown = this.cooldownView(state);
    const needsLaunch = !state.instance;
    const presence = needsLaunch ? this.presence(agent) : undefined;
    const error = staticBrowserGuard({
      platform: process.platform,
      tool,
      args,
      now: this.now(),
      ...(state.instance ? { instance: { windowId: state.instance.windows.get()!.windowId } } : {}),
      ...(cooldown ? { cooldown } : {}),
      needsLaunch,
      turnAllowed: presence?.allowed ?? true,
    });
    if (error) return error;
    if (needsLaunch && presence?.allowed && this.isConsumed(presence)) {
      return browserError('browser_launch_requires_user_turn', '真实新窗口已归还前台；继续操作需要新的用户轮次。');
    }
    return undefined;
  }

  /** Read a bounded snapshot from this Agent's own instance. */
  async read(agent: Agent, workspace: string | undefined, args: BrowserReadArguments, productAgentId: string = agent.id): Promise<BrowserReadResult> {
    const invalid = validateBrowserArguments('browser_read', args);
    if (invalid) throw invalid;
    return this.serial(agent.id, async () => {
      const state = this.assertUsable(agent.id);
      const turn = this.requestTurn(agent);
      const launched = !state.instance;
      const instance = await this.ensureInstance(agent, state);
      instance.windows.assertRequested(args.window_id);
      const bound = await this.bindPrimary(state, instance, turn);
      const tab = selectTab(bound.tabs, args.tab);
      const page = await this.snapshot(instance, bound, tab, args.query, args.screenshot === true);
      const maxChars = Math.min(args.max_chars ?? DEFAULT_READ_CHARS, MAX_READ_CHARS);
      const text = page.text.slice(0, maxChars);
      // Action readback is unfiltered, so only compare text from a full read.
      const record = instance.reads.mint({ ...tab, url: page.url, title: page.title || tab.title }, args.query ? undefined : page.text);
      const screenshot = await this.saveScreenshot(workspace, productAgentId, page.screenshot);
      const events = await this.inspectWindows(instance);
      const base = {
        read_id: record.readId,
        tab: { url: record.url, title: record.title, active: tab.active, window_id: instance.windows.get()!.windowId },
        text,
        refs: page.refs,
        truncated: page.truncated || page.text.length > text.length,
        driver: { version: instance.version },
        ...(screenshot.path ? { screenshot: { path: screenshot.path, width: screenshot.width, height: screenshot.height } } : {}),
        ...(screenshot.omitted ? { screenshot_omitted: screenshot.omitted } : {}),
        ...(events.events.length ? { events: events.events } : {}),
        ...(events.ignored.length ? { ignored: events.ignored } : {}),
        ...(launched ? { notice: '首次接入可能短暂占前台；不抢焦点地操作页面；新窗口或首次接入可能短暂占前台。' } : {}),
      } satisfies Omit<BrowserReadResult, 'foreground_released'>;
      await this.finishEvents(state, instance, events, turn);
      return events.events.length ? { ...base, foreground_released: true } : base;
    });
  }

  /** Dispatch one page action after validating its snapshot cursor. */
  async act(agent: Agent, workspace: string | undefined, args: BrowserActArguments, productAgentId: string = agent.id): Promise<BrowserActResult> {
    const invalid = validateBrowserArguments('browser_act', args);
    if (invalid) throw invalid;
    return this.serial(agent.id, async () => {
      const state = this.assertUsable(agent.id);
      const turn = this.requestTurn(agent);
      const launched = !state.instance;
      const instance = await this.ensureInstance(agent, state);
      instance.windows.assertRequested(args.window_id);
      const bound = await this.bindPrimary(state, instance, turn);
      const read = args.action === 'open'
        ? undefined
        : instance.reads.validate(args.read_id!, bound.tabs, args.tab);
      const tab = args.action === 'open'
        ? selectTab(bound.tabs, args.tab)
        : selectTab(bound.tabs, { url: read!.url, title: read!.title });
      const base = { session: instance.label, pid: instance.pid, window_id: instance.windows.get()!.windowId, target_id: bound.target_id, tab_id: tab.tab_id };
      let baselineUrl = tab.url;
      let baselineText: string | undefined;
      if (args.action === 'open') {
        await this.dispatch(() => this.driver.call('browser_navigate', { ...base, url: args.url, delivery_mode: 'background' }));
      } else if (args.action === 'click') {
        baselineText = read!.text;
        await this.dispatch(() => this.driver.call('browser_click', { ...base, ref: args.ref, delivery_mode: 'background' }));
      } else if (args.action === 'type') {
        baselineText = read!.text;
        await this.dispatch(() => this.driver.call('browser_type', { ...base, ref: args.ref, text: args.text, ...(args.replace === true ? { replace: true } : {}), delivery_mode: 'background' }));
      } else {
        baselineText = read!.text;
        await this.dispatch(() => this.driver.call('browser_pointer', {
          ...base, action: 'scroll', ref: args.ref,
          ...(args.delta_x !== undefined ? { delta_x: args.delta_x } : {}),
          ...(args.delta_y !== undefined ? { delta_y: args.delta_y } : {}),
          delivery_mode: 'background',
        }));
      }
      // Any action invalidates the model's refs; the driver has already started
      // a new snapshot namespace, so a stale read_id must not be reusable.
      instance.reads.clear();
      let effect: BrowserActResult['effect'] = 'unverifiable';
      let observed = { url: tab.url, title: tab.title, active: tab.active };
      let textAfter: string | undefined;
      let screenshotBase64: string | undefined;
      try {
        // The driver invalidates target/tab ids on every bind and may have
        // navigated during the action, so the readback starts from a fresh bind
        // and the current active tab.
        const after = await this.bindPrimary(state, instance, turn);
        const afterTab = selectTab(after.tabs);
        const readback = await this.snapshot(instance, after, afterTab, undefined, args.screenshot === true || args.action === 'scroll' && args.screenshot !== false);
        observed = { url: readback.url, title: readback.title, active: afterTab.active };
        textAfter = readback.text.slice(0, DEFAULT_READ_CHARS);
        screenshotBase64 = readback.screenshot;
        if (readback.url !== baselineUrl || baselineText !== undefined && readback.text !== baselineText) effect = 'changed';
        else if (args.action === 'open' || baselineText !== undefined) effect = 'unchanged';
      } catch (error) {
        if (isBrowserError(error) && ['browser_session_lost', 'browser_foreground_release_failed'].includes(error.browserCode)) throw error;
        effect = 'unverifiable';
      }
      const screenshot = await this.saveScreenshot(workspace, productAgentId, screenshotBase64);
      // A failed readback bind may already have cleared and ended the instance;
      // there is then nothing meaningful to classify.
      const events = instance.windows.get() ? await this.inspectWindows(instance) : { events: [], ignored: [], unclassified: [] };
      const result: BrowserActResult = {
        action: args.action,
        // The action invalidated the cursor; returning it would invite a
        // guaranteed stale retry. The model must browser_read again.
        dispatched: true,
        observed,
        effect,
        ...(textAfter !== undefined ? { text_after: textAfter } : {}),
        ...(screenshot.path ? { screenshot: { path: screenshot.path, width: screenshot.width, height: screenshot.height } } : {}),
        ...(screenshot.omitted ? { screenshot_omitted: screenshot.omitted } : {}),
        ...(events.events.length ? { events: events.events } : {}),
        ...(events.ignored.length ? { ignored: events.ignored } : {}),
        ...(launched ? { notice: '首次接入可能短暂占前台；不抢焦点地操作页面；新窗口或首次接入可能短暂占前台。' } : {}),
      };
      await this.finishEvents(state, instance, events, turn);
      return events.events.length ? { ...result, foreground_released: true } : result;
    });
  }

  /** End this Agent's instance without touching screenshots. */
  async dispose(agentId: string): Promise<void> {
    const state = this.states.get(agentId);
    if (!state) return;
    state.disposing = true;
    const run = state.queue.then(async () => {
      const instance = state.instance;
      state.instance = undefined;
      instance?.reads.clear();
      // A failed registration may own a launched session without an Instance.
      // Disposal must not erase that reservation or restart its expiry clock.
      const cooldown = this.cooldownView(state);
      if (state.ownership && !cooldown) {
        try { await this.endOwned(state); }
        catch (error) { this.logger?.warn(String(error)); }
      }
      state.disposalFinished = true;
      if (!state.ownership && this.states.get(agentId) === state) this.states.delete(agentId);
    });
    state.queue = run;
    await run;
  }

  /** One bounded, non-blocking cleanup over configured Agent workspaces only. */
  async sweepScreenshots(agents: readonly { agentId: string; workspace?: string }[]): Promise<number> {
    return this.screenshots.sweep(agents, message => this.logger?.warn(message));
  }

  private state(agentId: string): AgentState {
    let state = this.states.get(agentId);
    if (!state) { state = { queue: Promise.resolve() }; this.states.set(agentId, state); }
    return state;
  }

  private serial<T>(agentId: string, action: () => Promise<T>): Promise<T> {
    const state = this.state(agentId);
    if (state.disposing) return Promise.reject(browserError('browser_session_lost', '执行会话正在结束，请在新的用户轮次中重试。'));
    const run = state.queue.then(action, action);
    state.queue = run.then(() => undefined, () => undefined);
    return run;
  }

  private cooldownView(state: AgentState): { failedAt: number; until: number; message: string } | undefined {
    if (!state.cooldown) return undefined;
    if (this.now() >= state.cooldown.until) {
      state.cooldown = undefined;
      state.ownership = undefined;
      return undefined;
    }
    return { failedAt: state.cooldown.failedAt, until: state.cooldown.until, message: state.cooldown.detail };
  }

  private assertUsable(agentId: string): AgentState {
    const state = this.state(agentId);
    const cooldown = this.cooldownView(state);
    if (cooldown) throw browserError('browser_foreground_release_failed', cooldown.message, { failedAt: cooldown.failedAt });
    return state;
  }

  private presence(agent: Agent): TurnGateDecision {
    return evaluateTurnGate(liveTurnSession(agent), this.lookup, this.now(), this.liveHumanTimes);
  }

  private requestTurn(agent: Agent): TurnKey | undefined {
    const resolved = judgmentSession(liveTurnSession(agent), this.lookup);
    if ('reason' in resolved) return undefined;
    const turn = openTurn(resolved.session);
    return turn.open ? { sessionId: resolved.session.id, turnStartSeq: turn.startSeq! } : undefined;
  }

  private isConsumed(turn: TurnKey): boolean {
    return (this.consumedTurns.get(turn.sessionId) ?? -1) >= turn.turnStartSeq;
  }

  private instanceCount(): number {
    let count = 0;
    for (const [agentId, state] of this.states) {
      this.cooldownView(state);
      if (state.ownership || state.launching) count += 1;
      else if (state.disposalFinished) this.states.delete(agentId);
    }
    return count;
  }

  private async ensureInstance(agent: Agent, state: AgentState): Promise<Instance> {
    if (state.instance) return state.instance;
    if (this.instanceCount() >= this.maxInstances) throw browserError('browser_busy', `进程级浏览器实例已达上限 ${this.maxInstances}。`);
    const presence = this.presence(agent);
    if (!presence.allowed) throw browserError('browser_launch_requires_user_turn', `当前轮次不能新开浏览器实例（${presence.reason}）。`);
    if (this.isConsumed(presence)) {
      throw browserError('browser_launch_requires_user_turn', '真实新窗口已归还前台；继续操作需要新的用户轮次。');
    }
    // Reserve the slot synchronously so concurrent Agents cannot both pass the
    // cap check before either prepare resolves.
    state.launching = true;
    const label = `nano-br-${randomBytes(4).toString('hex')}`;
    let prepareStarted = false;
    try {
      const probe: DriverProbe = await this.driver.probe();
      // Probing yields to other Agents and turn updates. Revalidate the same
      // admission immediately before launch; never borrow a newer human turn.
      const current = this.presence(agent);
      if (!current.allowed || current.sessionId !== presence.sessionId
        || current.turnStartSeq !== presence.turnStartSeq || this.isConsumed(current)) {
        throw browserError('browser_launch_requires_user_turn', '等待驱动期间用户轮次已失效或已归还前台；请在新的用户轮次中重试。');
      }
      prepareStarted = true;
      // A timed-out/malformed prepare may still have launched Chrome. The
      // host-created label is sufficient to clean up that exact driver session.
      state.ownership = { label };
      const prepared = await this.driver.call('browser_prepare', { session: label, allow_launch: true, profile: { mode: 'isolated_new' } });
      const pid = ownerPid(prepared);
      if (!pid) throw browserError('browser_driver_malformed', 'browser_prepare 响应缺少 owner_pid。');
      state.ownership = { label, pid };
      const registration = await this.scanPrimary(label, pid);
      const instance: Instance = { label, pid, version: probe.version, windows: new WindowRegistry(), reads: new ReadRegistry() };
      instance.windows.adopt(registration.pid, registration.windowId);
      state.instance = instance;
      return instance;
    } catch (error) {
      if (prepareStarted) await this.endOwned(state);
      throw error;
    } finally {
      state.launching = false;
    }
  }

  private async scanPrimary(label: string, pid: string) {
    const windows = await this.listWindows(pid);
    const probes = new Map<string, BindProbe>();
    for (const window of windows) probes.set(window.window_id, await this.probeWindow(label, pid, window.window_id));
    return choosePrimaryWindow(pid, windows, windowId => probes.get(windowId) ?? { ok: false });
  }

  private async bindPrimary(state: AgentState, instance: Instance, turn?: TurnKey): Promise<BoundWindow> {
    const registered = instance.windows.get()!;
    // Never promote a surviving popup. A retry only rebinds the same identity.
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const bound = await this.bindWindow(instance.label, instance.pid, registered.windowId);
        if (bound.binding_quality === 'exact') return bound;
      } catch { /* One bounded read-only retry, never a page action replay. */ }
    }
    let events: EventClassification | undefined;
    let inspectionError: unknown;
    try { events = await this.inspectWindows(instance); }
    catch (error) { inspectionError = error; }
    await this.release(state, instance, turn);
    throw browserError('browser_session_lost', '原主窗口无法绑定；已结束自持实例，未采纳其它窗口。', {
      foreground_released: true,
      ...(events ? { events: events.events, ignored: events.ignored, unclassified: events.unclassified } : {}),
      ...(inspectionError ? { inspection_error: isBrowserError(inspectionError) ? inspectionError.browserCode : 'window_inspection_failed' } : {}),
    });
  }

  private async listWindows(pid: string): Promise<DriverWindow[]> {
    return normalizeWindows(await this.driver.call('list_windows', { pid }));
  }

  private async bindWindow(label: string, pid: string, windowId: string): Promise<BoundWindow> {
    const value = await this.driver.call('get_browser_state', { session: label, pid, window_id: windowId }, { requireFields: ['binding_quality', 'tabs'] });
    return normalizeBoundWindow(value);
  }

  private async probeWindow(label: string, pid: string, windowId: string): Promise<BindProbe> {
    try {
      const bound = await this.bindWindow(label, pid, windowId);
      return { ok: true, binding_quality: bound.binding_quality, target_id: bound.target_id, tabs: bound.tabs };
    } catch (error) {
      if (!isBrowserError(error) || error.browserCode !== 'browser_driver_refused') throw error;
      return { ok: false, error: error.message };
    }
  }

  private async snapshot(instance: Instance, bound: BoundWindow, tab: DriverTab, query: string | undefined, screenshot: boolean): Promise<PageSnapshot> {
    const value = await this.driver.call('get_browser_state', {
      session: instance.label,
      pid: instance.pid,
      window_id: instance.windows.get()!.windowId,
      target_id: bound.target_id,
      tab_id: tab.tab_id,
      snapshot_format: 'semantic_v2',
      ...(query ? { query } : {}),
      ...(screenshot ? { include_screenshot: true } : {}),
    }, { requireFields: ['snapshot'] });
    const normalized = normalizeSnapshot(value, tab);
    const base64 = typeof value.screenshot_png_b64 === 'string' ? value.screenshot_png_b64
      : typeof value.screenshot_b64 === 'string' ? value.screenshot_b64
        : value.screenshot && typeof value.screenshot === 'object' && typeof (value.screenshot as { base64?: unknown }).base64 === 'string' ? (value.screenshot as { base64: string }).base64
          : undefined;
    return { ...normalized, ...(base64 ? { screenshot: base64 } : {}) };
  }

  private async inspectWindows(instance: Instance): Promise<EventClassification> {
    const windows = await this.listWindows(instance.pid);
    const known = instance.windows.get()?.windowId;
    const probes = new Map<string, BindProbe>();
    for (const window of windows) {
      if (window.window_id === known) continue;
      probes.set(window.window_id, await this.probeWindow(instance.label, instance.pid, window.window_id));
    }
    return classifyNewWindows(known ? [known] : [], windows, windowId => probes.get(windowId) ?? { ok: false });
  }

  private async finishEvents(state: AgentState, instance: Instance, events: EventClassification, turn?: TurnKey): Promise<void> {
    if (events.events.length) await this.release(state, instance, turn);
    if (events.unclassified.length) {
      throw browserError('browser_unexpected_event', `出现 ${events.unclassified.length} 个无法分类的新窗口。`, {
        ...(events.events.length ? { foreground_released: true, events: events.events } : {}),
        windows: events.unclassified.map(window => ({ window_id: window.window_id, title: window.title, width: window.width, height: window.height })),
      });
    }
  }

  private async dispatch(action: () => Promise<Record<string, unknown>>): Promise<void> {
    try { await action(); }
    catch (error) {
      if (isBrowserError(error) && error.browserCode === 'browser_driver_refused' && error.details.refusalCode === 'browser_action_unavailable') {
        throw browserError('browser_driver_refused', '该 ref 没有声明 scroll/pointer 动作，不能作为滚动锚点；请换一个声明了 pointer 的 ref（refs[].actions 可判断）。', error.details);
      }
      throw error;
    }
  }

  private async release(state: AgentState, instance: Instance, turn?: TurnKey): Promise<void> {
    // Consume before I/O: expiry or ancestor closure during end_session must not
    // reopen the same turn for root/sibling launches.
    if (turn) this.consumedTurns.set(turn.sessionId, Math.max(this.consumedTurns.get(turn.sessionId) ?? -1, turn.turnStartSeq));
    if (state.instance !== instance || !state.ownership?.pid || !validReleaseTarget(instance.label, instance.pid, state.ownership.label, state.ownership.pid)) {
      throw this.releaseFailed(state, `实例标识与账本不一致：${instance.label}/${instance.pid}`);
    }
    await this.endOwned(state);
    instance.reads.clear();
    instance.windows.clear();
  }

  private async endOwned(state: AgentState): Promise<void> {
    const label = state.ownership?.label;
    if (!label || !SESSION_LABEL.test(label)) throw this.releaseFailed(state, '缺少自持 session label。');
    let lastError: unknown;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        await this.driver.call('end_session', { session: label });
        state.instance = undefined;
        state.ownership = undefined;
        return;
      } catch (error) { lastError = error; }
    }
    throw this.releaseFailed(state, `end_session 连续失败：${String((lastError as Error)?.message ?? lastError)}`);
  }

  private releaseFailed(state: AgentState, detail: string) {
    const failedAt = this.now();
    const message = `前台归还失败（failedAt=${new Date(failedAt).toISOString()}）。${detail} 请手动关闭本 Agent 的浏览器窗口；冷却期间不会继续派发动作。`;
    state.instance = undefined;
    state.cooldown = { failedAt, until: failedAt + COOLDOWN_MS, detail: message };
    return browserError('browser_foreground_release_failed', message, { failedAt });
  }

  private async saveScreenshot(workspace: string | undefined, agentId: string, base64: string | undefined): Promise<{ path?: string; omitted?: string; width: number; height: number }> {
    if (!base64) return { width: 0, height: 0 };
    const saved = await this.screenshots.save({ workspace, agentId, base64 });
    return 'path' in saved ? { path: saved.path, width: saved.width, height: saved.height } : { omitted: saved.omitted, width: 0, height: 0 };
  }
}

/** Release precheck is bookkeeping only; it is never a liveness proof. */
export function validReleaseTarget(label: string, pid: string, expectedLabel: string, expectedPid: string): boolean {
  return SESSION_LABEL.test(label) && label === expectedLabel && String(pid) === String(expectedPid);
}

function ownerPid(value: Record<string, unknown>): string | undefined {
  const ownership = value.endpoint_ownership && typeof value.endpoint_ownership === 'object' ? value.endpoint_ownership as Record<string, unknown> : undefined;
  const candidate = ownership?.owner_pid ?? value.owner_pid ?? value.pid;
  const pid = Number(candidate);
  return Number.isInteger(pid) && pid > 0 ? String(pid) : undefined;
}

function normalizeSnapshot(value: Record<string, unknown>, tab: DriverTab): Omit<PageSnapshot, 'screenshot'> {
  const nested = value.snapshot && typeof value.snapshot === 'object' && !Array.isArray(value.snapshot) ? value.snapshot as Record<string, unknown> : undefined;
  const snapshot = nested ?? value;
  // Real semantic_v2 responses put the page text in the top-level `outline`;
  // the `snapshot` object is only metadata (complete/omitted/node_budget...).
  const nestedText = snapshot.text ?? snapshot.content ?? snapshot.page_text ?? snapshot.markdown;
  const contentRefs = Array.isArray(value.content_refs) ? value.content_refs : [];
  const fallbackText = contentRefs.flatMap(item => {
    if (!item || typeof item !== 'object') return [];
    const row = item as Record<string, unknown>;
    const label = typeof row.name === 'string' ? row.name : typeof row.text === 'string' ? row.text : '';
    return label ? [label] : [];
  }).join('\n');
  const text = typeof value.outline === 'string' ? value.outline
    : typeof nestedText === 'string' ? nestedText
      : Array.isArray(nestedText) ? nestedText.filter(part => typeof part === 'string').join('\n')
        : fallbackText || undefined;
  if (text === undefined) throw browserError('browser_driver_malformed', '页面快照缺少 outline 可读文本字段。');
  const rawRefs = Array.isArray(value.refs) ? value.refs : Array.isArray(snapshot.refs) ? snapshot.refs : [];
  const refs = rawRefs.flatMap(item => {
    if (!item || typeof item !== 'object') return [];
    const ref = item as Record<string, unknown>;
    const token = typeof ref.ref === 'string' ? ref.ref : typeof ref.element_token === 'string' ? ref.element_token : '';
    if (!token) return [];
    return [{
      ref: token,
      role: typeof ref.role === 'string' ? ref.role : '',
      name: typeof ref.name === 'string' ? ref.name : typeof ref.text === 'string' ? ref.text : '',
      ...(Array.isArray(ref.actions) ? { actions: ref.actions.filter((action): action is string => typeof action === 'string') } : {}),
    }];
  }).slice(0, REFS_LIMIT);
  return {
    url: typeof snapshot.url === 'string' ? snapshot.url : tab.url,
    title: typeof snapshot.title === 'string' ? snapshot.title : tab.title,
    text,
    refs,
    truncated: value.outline_truncated === true || value.truncated === true || snapshot.truncated === true
      || snapshot.complete === false || snapshot.omitted === true || Array.isArray(snapshot.omitted) && snapshot.omitted.length > 0
      || rawRefs.length > REFS_LIMIT,
  };
}

export { BROWSER_ACT_ACTIONS };
