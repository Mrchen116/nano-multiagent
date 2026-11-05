import { browserError, type BrowserError } from './errors.js';

export const MAX_INPUT_TEXT = 4_000;
export const MAX_READ_CHARS = 20_000;
export const DEFAULT_READ_CHARS = 8_000;
export const BROWSER_ACT_ACTIONS = ['open', 'click', 'type', 'scroll'] as const;

export interface StaticGuardInput {
  platform: string;
  tool: string;
  args: unknown;
  instance?: { windowId: string };
  cooldown?: { message: string; failedAt: number; until: number };
  /** True when the call would have to start a new instance. */
  needsLaunch?: boolean;
  /** Result of the user-presence gate when `needsLaunch` is true. */
  turnAllowed?: boolean;
  /** Clock shared with the cooldown bookkeeping; defaults to Date.now. */
  now?: number;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function validTab(value: unknown): boolean {
  if (value === undefined) return true;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const tab = value as Record<string, unknown>;
  if (tab.url !== undefined && typeof tab.url !== 'string') return false;
  if (tab.title !== undefined && typeof tab.title !== 'string') return false;
  if (tab.active !== undefined && typeof tab.active !== 'boolean') return false;
  return true;
}

function httpUrl(value: unknown): boolean {
  if (!nonEmpty(value)) return false;
  try { return ['http:', 'https:'].includes(new URL(value).protocol); }
  catch { return false; }
}

/** Pure argument contract shared by the pre-execute guard and tool execution. */
export function validateBrowserArguments(tool: string, args: unknown): BrowserError | undefined {
  const value = record(args);
  if (tool === 'browser_read') {
    if (value.max_chars !== undefined && (!Number.isInteger(value.max_chars) || (value.max_chars as number) < 1 || (value.max_chars as number) > MAX_READ_CHARS)) {
      return browserError('browser_arguments_invalid', `max_chars 必须是 1..${MAX_READ_CHARS} 的整数。`);
    }
    if (value.query !== undefined && typeof value.query !== 'string') return browserError('browser_arguments_invalid', 'query 必须是字符串。');
    if (value.screenshot !== undefined && typeof value.screenshot !== 'boolean') return browserError('browser_arguments_invalid', 'screenshot 必须是布尔值。');
    if (value.window_id !== undefined && typeof value.window_id !== 'string') return browserError('browser_arguments_invalid', 'window_id 必须是字符串。');
    if (!validTab(value.tab)) return browserError('browser_arguments_invalid', 'tab 必须是 {url?, title?, active?}。');
    return undefined;
  }
  if (tool !== 'browser_act') return undefined;
  if (value.x !== undefined || value.y !== undefined) return browserError('browser_arguments_invalid', '只接受 ref，无坐标；请先 browser_read 并使用返回的 ref。');
  const action = value.action;
  if (typeof action !== 'string' || !(BROWSER_ACT_ACTIONS as readonly string[]).includes(action)) {
    return browserError('browser_arguments_invalid', `action 必须是 ${BROWSER_ACT_ACTIONS.join('/')}；没有 close 动作。`);
  }
  if (value.window_id !== undefined && typeof value.window_id !== 'string') return browserError('browser_arguments_invalid', 'window_id 必须是字符串。');
  if (!validTab(value.tab)) return browserError('browser_arguments_invalid', 'tab 必须是 {url?, title?, active?}。');
  if (value.screenshot !== undefined && typeof value.screenshot !== 'boolean') return browserError('browser_arguments_invalid', 'screenshot 必须是布尔值。');
  if (action === 'open') {
    if (!nonEmpty(value.url)) return browserError('browser_arguments_invalid', 'open 需要非空 url。');
    if (!httpUrl(value.url)) return browserError('browser_navigation_rejected', 'open 只接受 http/https 地址。');
    return undefined;
  }
  if (!nonEmpty(value.read_id)) return browserError('browser_arguments_invalid', `${action} 需要最近一次 browser_read 返回的 read_id。`);
  if (action === 'click' || action === 'type' || action === 'scroll') {
    if (!nonEmpty(value.ref)) return browserError('browser_arguments_invalid', `${action} 需要最近一次 browser_read 返回的 ref。`);
  }
  if (action === 'type') {
    if (typeof value.text !== 'string') return browserError('browser_arguments_invalid', 'type 需要 text。');
    if (value.text.length > MAX_INPUT_TEXT) return browserError('browser_arguments_invalid', `type 文本最多 ${MAX_INPUT_TEXT} 个字符。`);
  }
  if (action === 'scroll') {
    const deltaX = value.delta_x;
    const deltaY = value.delta_y;
    const usable = (candidate: unknown) => typeof candidate === 'number' && Number.isFinite(candidate) && candidate !== 0;
    if (!usable(deltaX) && !usable(deltaY)) return browserError('browser_arguments_invalid', 'scroll 需要非零 delta_x 或 delta_y，并以 ref 为锚点。');
  }
  return undefined;
}

/** Deterministic pre-execute gate: platform, arguments, cooldown, window, presence.
 *
 * It performs no file, process or driver I/O and runs before the approval
 * classifier via `next()`.
 */
export function staticBrowserGuard(input: StaticGuardInput): BrowserError | undefined {
  if (!['browser_read', 'browser_act'].includes(input.tool)) return undefined;
  if (input.platform !== 'darwin') return browserError('browser_platform_unsupported', `当前平台 ${input.platform} 不支持浏览器页面能力。`);
  const invalid = validateBrowserArguments(input.tool, input.args);
  if (invalid) return invalid;
  if (input.cooldown && (input.now ?? Date.now()) < input.cooldown.until) {
    return browserError('browser_foreground_release_failed', input.cooldown.message, { failedAt: input.cooldown.failedAt });
  }
  const requested = typeof record(input.args).window_id === 'string' ? record(input.args).window_id as string : undefined;
  if (requested !== undefined && requested !== input.instance?.windowId) {
    return browserError('browser_window_not_registered', `window_id ${requested} 不是已登记主窗口 ${input.instance?.windowId ?? '<none>'}。`);
  }
  if (input.needsLaunch && input.turnAllowed === false) {
    return browserError('browser_launch_requires_user_turn', '当前轮次不在用户在场窗口内，不能启动新的浏览器实例。');
  }
  return undefined;
}
