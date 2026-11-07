import { HarnessError } from '@deepseek-ai/dsh-llm';

/** Stable model-visible failure classes for the browser control surface. */
export type BrowserErrorCode =
  | 'browser_platform_unsupported'
  | 'browser_driver_unavailable'
  | 'browser_driver_version_unsupported'
  | 'browser_driver_not_running'
  | 'browser_permission_missing'
  | 'browser_arguments_invalid'
  | 'browser_snapshot_stale'
  | 'browser_tab_ambiguous'
  | 'browser_window_ambiguous'
  | 'browser_window_not_registered'
  | 'browser_launch_requires_user_turn'
  | 'browser_session_lost'
  | 'browser_navigation_rejected'
  | 'browser_driver_refused'
  | 'browser_driver_timeout'
  | 'browser_driver_malformed'
  | 'browser_foreground_release_failed'
  | 'browser_unexpected_event'
  | 'browser_busy';

const guidance: Record<BrowserErrorCode, string> = {
  browser_platform_unsupported: '本节点不是 macOS，无法使用浏览器页面能力。',
  browser_driver_unavailable: '请安装 cua-driver 0.38.x，或用 NANO_CUA_DRIVER 指定可执行文件路径。',
  browser_driver_version_unsupported: '请安装 0.38.x；本能力不会替换或升级驱动。',
  browser_driver_not_running: '请先启动 cua-driver daemon；本能力不会自动启动或重启它。',
  browser_permission_missing: '请在系统设置中授予缺失的辅助功能/屏幕录制权限。',
  browser_arguments_invalid: '请修正参数后重试。',
  browser_snapshot_stale: '页面或读取游标已变化，请重新 browser_read 后再操作。',
  browser_tab_ambiguous: '请提供更精确的 tab 匹配条件，或先重新读取确认标签。',
  browser_window_ambiguous: '报告该情况并等待用户处理；不要按窗口顺序取第一个。',
  browser_window_not_registered: '请使用最近一次读取返回的 window_id。',
  browser_launch_requires_user_turn:
    '需要用户在对话里发起这一步；如果用户刚说过但已超过 5 分钟，请用户再发一条消息以刷新在场窗口，轮次已结束同样不能新开实例。不要重试开窗。',
  browser_session_lost: '请重新读取；持续失败则报告用户。',
  browser_navigation_rejected: '只接受 http/https 地址，请换合法地址。',
  browser_driver_refused: '请按驱动 hint 处理，不要原样重试；background 被拒时不得改 foreground 重试。',
  browser_driver_timeout: '页面状态未知，不要当作成功；只允许用户显式发起一次重新读取。',
  browser_driver_malformed: '本次结果不完整，不能当作成功；请报告失败并说明可怎样继续。',
  browser_foreground_release_failed:
    '请用户手动关闭该浏览器窗口；冷却结束前不会再派发任何页面动作。',
  browser_unexpected_event: '先把这件事告知用户，再决定是否继续；不要自动重试或自动忽略。',
  browser_busy: '进程级实例已满，请稍后再试或结束其他 Agent 的浏览器实例。',
};

/** Failure carrying a stable browser code plus bounded diagnostic details. */
export class BrowserError extends HarnessError {
  constructor(readonly browserCode: BrowserErrorCode, detail: string, readonly details: Record<string, unknown> = {}) {
    const suffix = guidance[browserCode];
    // Native tool failures transport Error.message, not custom Error fields.
    const evidence = Object.keys(details).length ? ` evidence=${excerpt(JSON.stringify(details), 6000)}` : '';
    super(`[${browserCode}] ${detail}${suffix ? ` ${suffix}` : ''}${evidence}`, browserCode);
    this.name = 'BrowserError';
  }
}

/** Create a browser failure with the shared model guidance for its code. */
export function browserError(code: BrowserErrorCode, detail: string, details: Record<string, unknown> = {}): BrowserError {
  return new BrowserError(code, detail, details);
}

/** Narrow an unknown thrown value without hiding unrelated failures. */
export function isBrowserError(value: unknown): value is BrowserError {
  return value instanceof BrowserError;
}

/** Truncate raw driver output before it reaches a model-visible error. */
export function excerpt(value: unknown, limit = 1200): string {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}
