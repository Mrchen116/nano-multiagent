import type { BindProbe, DriverWindow } from './windows.js';

/** Fixed macOS Chrome UI sizes observed in the verification run. */
export const CHROME_NOISE_SIZES = [
  { width: 284, height: 87 },
  { width: 1038, height: 218 },
] as const;

const CHROME_NOISE_TITLES = /^(?:|翻译此页？|translate this page\??|建议|suggestions?)$/i;

export interface RealWindowEvent {
  kind: 'window';
  window_id: string;
  title: string;
  width: number;
  height: number;
  url: string;
}

export interface IgnoredWindowEvent {
  width: number;
  height: number;
  title: string;
}

export interface EventClassification {
  events: RealWindowEvent[];
  ignored: IgnoredWindowEvent[];
  unclassified: DriverWindow[];
}

function isHttp(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

function isKnownChromeOverlay(window: DriverWindow): boolean {
  const width = Math.round(window.width);
  const height = Math.round(window.height);
  const title = window.title.trim();
  if (/^(?:更改您的密码|Change your password)$/i.test(title)) return width === 448 && height === 299;
  return CHROME_NOISE_TITLES.test(title) && CHROME_NOISE_SIZES.some(size => width === size.width && height === size.height);
}

/** Ordered three-way classifier for windows that were not the registered main window.
 *
 * 1. bind exact plus at least one http(s) tab -> real browsing window;
 * 2. bind failed/refused AND no target AND no URL AND empty/browser-chrome title
 *    AND a fixed UI size -> Chrome noise (counted, never a failure);
 * 3. everything else -> unclassified (the caller ends the call and hands the
 *    evidence back to the model).
 */
export function classifyNewWindows(
  known: readonly string[],
  windows: readonly DriverWindow[],
  probe: (windowId: string) => BindProbe,
): EventClassification {
  const result: EventClassification = { events: [], ignored: [], unclassified: [] };
  const knownIds = new Set(known);
  for (const window of windows) {
    if (knownIds.has(window.window_id)) continue;
    const bound = probe(window.window_id);
    const tabs = bound.tabs ?? [];
    const urls = tabs.map(tab => tab.url).filter(Boolean);
    if (bound.ok && bound.binding_quality === 'exact' && urls.some(isHttp)) {
      result.events.push({ kind: 'window', window_id: window.window_id, title: window.title, width: window.width, height: window.height, url: urls.find(isHttp)! });
      continue;
    }
    const noise = !bound.ok
      && !bound.target_id
      && urls.length === 0
      && isKnownChromeOverlay(window);
    if (noise) result.ignored.push({ width: window.width, height: window.height, title: window.title });
    else result.unclassified.push(window);
  }
  return result;
}
