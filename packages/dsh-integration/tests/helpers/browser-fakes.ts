import type { Agent } from '@deepseek-ai/dsh-agent';
import type { BrowserDriverLike, DriverCallOptions, DriverCallTool, DriverProbe } from '../../src/browser/driver.js';
import { browserError } from '../../src/browser/errors.js';
import type { TurnEvent, TurnSession } from '../../src/policy/turn.js';
import type { DriverWindow } from '../../src/browser/windows.js';

export interface ScriptedCall {
  tool: DriverCallTool;
  args: Record<string, unknown>;
  options?: DriverCallOptions;
}

/** Deterministic driver double; no browser or process is involved. */
export class ScriptedDriver implements BrowserDriverLike {
  readonly calls: ScriptedCall[] = [];
  probeCalls = 0;
  version = '0.38.0';
  inFlight = 0;
  maxInFlight = 0;
  delayMs = 0;
  constructor(private readonly handler: (tool: DriverCallTool, args: Record<string, unknown>) => unknown | Promise<unknown>) {}

  async probe(): Promise<DriverProbe> {
    this.probeCalls += 1;
    return { version: this.version };
  }

  async call(tool: DriverCallTool, args: Record<string, unknown>, options?: DriverCallOptions): Promise<Record<string, unknown>> {
    this.calls.push({ tool, args, options });
    this.inFlight += 1;
    this.maxInFlight = Math.max(this.maxInFlight, this.inFlight);
    try {
      if (this.delayMs) await new Promise(resolve => setTimeout(resolve, this.delayMs));
      const value = await this.handler(tool, args);
      return value as Record<string, unknown>;
    } finally { this.inFlight -= 1; }
  }

  count(tool: DriverCallTool): number { return this.calls.filter(call => call.tool === tool).length; }
}

export interface FakeWindowState {
  windows: DriverWindow[];
  binds: Map<string, { url: string; title: string; active: boolean; http: boolean }>;
  popup?: { windowId: string; url: string; title: string };
  popupKind?: 'real' | 'noise' | 'unclassified';
  text?: string;
  url?: string;
  title?: string;
  textOnClick?: string;
  queryText?: string;
  navigateUrl?: string;
  navigateText?: string;
  preparePid?: string;
  prepareError?: Error;
  endSessionError?: Error;
  actionError?: Error;
  screenshot?: string;
  tabs?: { url: string; title: string; active: boolean }[];
  bindingQuality?: string;
}

/** Stateful fake that behaves like the parts of cua-driver the control uses. */
export class BrowserFixtureDriver extends ScriptedDriver {
  state: FakeWindowState;

  constructor(initial: Partial<FakeWindowState> = {}) {
    const state: FakeWindowState = {
      windows: [{ window_id: '10', title: 'about:blank', width: 1200, height: 800 }],
      binds: new Map([['10', { url: 'about:blank', title: 'about:blank', active: true, http: false }]]),
      text: 'Hello page',
      url: 'about:blank',
      title: 'about:blank',
      preparePid: '42',
      ...initial,
    };
    // A fixture that names an initial page should also expose it through the
    // window bind, which is what the control reads for tab identity.
    if (!initial.binds) {
      const url = state.url!;
      state.binds = new Map([['10', { url, title: state.title!, active: true, http: /^https?:/i.test(url) }]]);
    }
    super((tool, args) => {
      if (tool === 'browser_prepare') {
        if (state.prepareError) throw state.prepareError;
        return { action: 'launched_isolated_browser', endpoint_ownership: { owner_pid: Number(state.preparePid) } };
      }
      if (tool === 'list_windows') return { windows: state.windows };
      if (tool === 'get_browser_state') {
        if (args.snapshot_format) {
          // Shape captured from cua-driver 0.38.0: `snapshot` is metadata and
          // the page text/elements live in top-level outline/refs.
          return {
            snapshot: { format: 'semantic_v2', complete: true, omitted: [], node_budget: 250 },
            outline: (args.query && state.queryText) || state.text,
            refs: [{ ref: 'p1:0', role: 'button', name: 'Increment', actions: ['click', 'pointer'] }],
            content_refs: [{ ref: 'p1:0', role: 'button', name: 'Increment' }],
            ...(state.screenshot ? { screenshot_png_b64: state.screenshot, screenshot_width: 2400, screenshot_height: 1464, mime_type: 'image/png' } : {}),
          };
        }
        const id = String(args.window_id);
        if (state.popup && id === state.popup.windowId && state.popupKind !== 'real') {
          if (state.popupKind === 'noise') throw browserError('browser_driver_refused', 'refused', { refusalCode: 'browser_window_unavailable' });
          if (state.popupKind === 'unclassified') return { binding_quality: 'exact', target_id: `bt-${id}`, tabs: [{ active: true, tab_id: `tab-${id}`, url: 'about:blank', title: '' }] };
        }
        const bind = state.binds.get(id) ?? { url: state.url!, title: state.title!, active: true, http: true };
        return {
          binding_quality: state.bindingQuality ?? 'exact',
          target_id: `bt-${id}-${this.bindTick++}`,
          native_title: bind.title,
          tabs: state.tabs ?? [{ active: bind.active, tab_id: `tab-${id}-${this.bindTick}`, url: bind.url, title: bind.title }],
        };
      }
      if (tool === 'browser_navigate') {
        if (state.actionError) throw state.actionError;
        state.url = state.navigateUrl ?? String(args.url);
        state.text = state.navigateText ?? state.text;
        state.binds.set('10', { url: state.url, title: state.title!, active: true, http: /^https?:/i.test(state.url) });
        return { status: 'ok', refs_invalidated: true };
      }
      if (tool === 'browser_click') {
        if (state.actionError) throw state.actionError;
        if (state.textOnClick !== undefined) state.text = state.textOnClick;
        if (state.popup) {
          if (state.popupKind === 'real') {
            state.windows = [...state.windows, { window_id: state.popup.windowId, title: state.popup.title, width: 520, height: 426 }];
            state.binds.set(state.popup.windowId, { url: state.popup.url, title: state.popup.title, active: true, http: true });
          } else if (state.popupKind === 'noise') {
            state.windows = [...state.windows, { window_id: state.popup.windowId, title: '翻译此页？', width: 284, height: 87 }];
          } else {
            state.windows = [...state.windows, { window_id: state.popup.windowId, title: '', width: 900, height: 700 }];
          }
        }
        return { status: 'ok', effect: 'unverifiable', summary: 'clicked' };
      }
      if (tool === 'browser_type') {
        if (state.actionError) throw state.actionError;
        return { status: 'ok', effect: 'unverifiable' };
      }
      if (tool === 'browser_pointer') {
        if (state.actionError) throw state.actionError;
        return { status: 'ok', effect: 'unverifiable' };
      }
      if (tool === 'end_session') {
        if (state.endSessionError) throw state.endSessionError;
        return { active: false, session: args.session };
      }
      throw new Error(`Unexpected fake driver tool ${tool}`);
    });
    this.state = state;
  }

  private bindTick = 0;
}

/** Build a minimal live session fixture for the browser gate. */
export function turnSession(id: string, events: TurnEvent[], header: TurnSession['header'] = {}): TurnSession {
  return { id, header, snapshotEvents: () => events };
}

export function event(seq: number, time: number, type: string, data: TurnEvent['data']): TurnEvent {
  return { seq, time, type, data };
}

export function humanMessage(seq: number, time: number, channel = 'im'): TurnEvent {
  return event(seq, time, 'user/message', { source: { kind: 'nano-human', actorId: 'owner', channel, messageId: `m${seq}` } as never });
}

export function systemMessage(seq: number, time: number, channel: string): TurnEvent {
  return event(seq, time, 'user/message', { source: { kind: 'nano-system', actorId: 'system', channel, messageId: `s${seq}` } as never });
}

/** Agent-shaped object accepted by BrowserControl's structural casts. */
export function fakeAgent(id: string, events: TurnEvent[], header: TurnSession['header'] = {}): Agent {
  return { id, session: { header, snapshotEvents: () => events } } as unknown as Agent;
}
