import { browserError } from './errors.js';

export interface DriverWindow {
  window_id: string;
  title: string;
  width: number;
  height: number;
}

export interface WindowCandidate {
  window_id: string;
  title: string;
  target_id: string;
}

/** Accept both `{windows: [...]}` and a bare array from list_windows. */
export function normalizeWindows(value: Record<string, unknown>): DriverWindow[] {
  const raw = Array.isArray(value.windows) ? value.windows : Array.isArray(value) ? value : undefined;
  if (!raw) throw browserError('browser_driver_malformed', 'list_windows 响应缺少 windows 数组。');
  return raw.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object').map(item => {
    const bounds = item.bounds && typeof item.bounds === 'object' ? item.bounds as Record<string, unknown> : undefined;
    const width = Number(item.width ?? bounds?.width ?? 0);
    const height = Number(item.height ?? bounds?.height ?? 0);
    return { window_id: String(item.window_id ?? ''), title: String(item.title ?? ''), width: Number.isFinite(width) ? width : 0, height: Number.isFinite(height) ? height : 0 };
  }).filter(window => window.window_id);
}

/** One main window per Agent instance; `browser_prepare` already narrowed the pid. */
export class WindowRegistry {
  private primary?: { pid: string; windowId: string };

  adopt(pid: string, windowId: string): void { this.primary = { pid, windowId }; }

  get(): { pid: string; windowId: string } | undefined { return this.primary; }

  /** Reject a request that names any window other than the registered one. */
  assertRequested(windowId: string | undefined): void {
    if (windowId !== undefined && (!this.primary || windowId !== this.primary.windowId)) {
      throw browserError('browser_window_not_registered', `window_id ${windowId} 不是已登记主窗口 ${this.primary?.windowId ?? '<none>'}。`);
    }
  }

  clear(): void { this.primary = undefined; }
}

export interface BindProbe {
  ok: boolean;
  binding_quality?: string;
  target_id?: string;
  tabs?: { url: string; title: string; active: boolean }[];
  error?: string;
}

export interface PrimaryRegistration {
  pid: string;
  windowId: string;
  targetId: string;
}

/** Choose the single exact-bind window as the instance's main window.
 *
 * `http(s)` is deliberately not required here: a freshly prepared instance
 * starts on `about:blank`, and rejecting it would make the first use
 * permanently unavailable. The pid already limits the set to our own driver
 * instance; URL evidence is only used by the new-window classifier.
 */
export function choosePrimaryWindow(pid: string, windows: readonly DriverWindow[], probe: (windowId: string) => BindProbe): PrimaryRegistration {
  const candidates: WindowCandidate[] = [];
  for (const window of windows) {
    const bound = probe(window.window_id);
    if (bound.ok && bound.binding_quality === 'exact' && bound.target_id) {
      candidates.push({ window_id: window.window_id, title: window.title, target_id: bound.target_id });
    }
  }
  if (!candidates.length) throw browserError('browser_session_lost', '无法在主窗口候选中完成 exact 绑定。');
  if (candidates.length > 1) {
    throw browserError('browser_window_ambiguous', `有 ${candidates.length} 个可绑定的浏览器窗口，无法唯一确定主窗口。`, {
      candidates: candidates.map(candidate => ({ window_id: candidate.window_id, title: candidate.title })),
    });
  }
  return { pid, windowId: candidates[0]!.window_id, targetId: candidates[0]!.target_id };
}
