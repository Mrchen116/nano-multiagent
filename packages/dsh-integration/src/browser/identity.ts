import { browserError } from './errors.js';

export interface DriverTab {
  active: boolean;
  tab_id: string;
  url: string;
  title: string;
}

export interface BoundWindow {
  target_id: string;
  binding_quality: string;
  native_title?: string;
  tabs: DriverTab[];
}

export interface TabMatcher {
  url?: string;
  title?: string;
  active?: boolean;
}

export interface ReadRecord {
  readId: string;
  url: string;
  title: string;
  active: boolean;
  text: string | undefined;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

/** Validate one driver bind result before any identity decision uses it. */
export function normalizeBoundWindow(value: Record<string, unknown>): BoundWindow {
  const target = text(value.target_id);
  const tabs = Array.isArray(value.tabs) ? value.tabs : [];
  if (!target) throw browserError('browser_driver_malformed', 'get_browser_state 响应缺少 target_id。');
  if (typeof value.binding_quality !== 'string') throw browserError('browser_driver_malformed', 'get_browser_state 响应缺少 binding_quality。');
  return {
    target_id: target,
    binding_quality: value.binding_quality,
    ...(typeof value.native_title === 'string' ? { native_title: value.native_title } : {}),
    tabs: tabs.filter((tab): tab is Record<string, unknown> => !!tab && typeof tab === 'object').map(tab => ({
      active: tab.active === true,
      tab_id: text(tab.tab_id),
      url: text(tab.url),
      title: text(tab.title),
    })),
  };
}

/** Select exactly one tab by url/title/active; array position never decides. */
export function selectTab(tabs: readonly DriverTab[], matcher?: TabMatcher): DriverTab {
  const candidates = tabs.filter(tab => {
    if (!matcher) return tab.active;
    if (matcher.url !== undefined && tab.url !== matcher.url) return false;
    if (matcher.title !== undefined && tab.title !== matcher.title) return false;
    if (matcher.active !== undefined && tab.active !== matcher.active) return false;
    return true;
  });
  const shown = candidates.map(tab => ({ url: tab.url, title: tab.title, active: tab.active }));
  if (!candidates.length) throw browserError('browser_driver_refused', '主窗口内没有匹配的标签。', { code: 'browser_tab_not_found', candidates: shown });
  if (candidates.length > 1) throw browserError('browser_tab_ambiguous', `主窗口内有 ${candidates.length} 个标签同时匹配。`, { candidates: shown });
  return candidates[0]!;
}

/** Monotonic read cursor scoped to one Agent; every new read invalidates the previous one. */
export class ReadRegistry {
  private counter = 0;
  private current?: ReadRecord;

  mint(tab: DriverTab, pageText: string | undefined): ReadRecord {
    this.counter += 1;
    this.current = { readId: `r${this.counter}`, url: tab.url, title: tab.title, active: tab.active, text: pageText };
    return this.current;
  }

  latest(): ReadRecord | undefined { return this.current; }

  /** Return the read only while it is still the latest snapshot. */
  require(readId: string): ReadRecord {
    if (!this.current || this.current.readId !== readId) {
      throw browserError('browser_snapshot_stale', `read_id ${readId} 已过期，最近一次读取是 ${this.current?.readId ?? '<none>'}。`);
    }
    return this.current;
  }

  /** Verify the page is still the one the read cursor was minted for. */
  validate(readId: string, tabs: readonly DriverTab[], requested?: TabMatcher): ReadRecord {
    const read = this.require(readId);
    if (requested) {
      if (requested.url !== undefined && requested.url !== read.url
        || requested.title !== undefined && requested.title !== read.title
        || requested.active !== undefined && requested.active !== read.active) {
        throw browserError('browser_snapshot_stale', `read_id ${readId} 属于另一个标签，页面可能已经切换。`);
      }
    }
    if (!tabs.some(tab => tab.url === read.url)) {
      throw browserError('browser_snapshot_stale', `read_id ${readId} 记录的页面地址已变化。`);
    }
    return read;
  }

  clear(): void { this.current = undefined; }
}
