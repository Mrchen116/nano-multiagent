/** Targets selected by the original owner message; worker-provided assignment text is never parsed. */
export function computerScope(text: string, clipboard: boolean) {
  if (clipboard) return { clipboard: true, browser: false, desktop: false, origins: new Set<string>() };
  const origins = new Set<string>();
  for (const match of text.matchAll(/https?:\/\/[^\s<>"'，。；）)]+/gi)) {
    try {
      origins.add(new URL(match[0]).origin);
    } catch {
      /* An invalid link grants no origin. */
    }
  }
  const browserNamed = /浏览器|网页|Chrome|Chromium|browser|website|web page/i.test(text);
  if (browserNamed) {
    for (const match of text.matchAll(
      /(?<![\w.\/:@-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}(?::\d+)?(?![\w.-])/gi,
    )) {
      try {
        origins.add(new URL('https://' + match[0]).origin);
      } catch {
        /* Invalid host or port. */
      }
    }
  }
  const browser = origins.size > 0 || browserNamed;
  const desktop =
    /桌面|窗口|原生应用|应用程序|desktop|window|\bapp\b|\b(?:com|org|net)\.[a-z0-9.-]+\.[a-z0-9.-]+/i.test(text) ||
    /(?:用|打开|在|操作)\s*(?:[A-Za-z][\w .-]*|文本编辑|备忘录|日历|提醒事项|预览|访达|邮件|表格)/u.test(text);
  return { clipboard: false, browser, desktop, origins };
}

export function scopeAllows(
  text: string,
  scope: ReturnType<typeof computerScope>,
  surface: 'browser' | 'desktop',
  action: string,
  input: Record<string, unknown>,
) {
  if (action === 'read_clipboard') return surface === 'desktop' && scope.clipboard;
  if (!scope[surface]) return false;
  if (surface === 'browser' && ['open', 'navigate', 'new_tab'].includes(action)) {
    if (
      action === 'open' &&
      /隔离|干净|独立.{0,6}(?:环境|profile)|isolated|clean profile/i.test(text) &&
      input.mode !== 'isolated'
    )
      return false;
    try {
      return scope.origins.has(new URL(String(input.url)).origin);
    } catch {
      return false;
    }
  }
  if (surface === 'desktop' && (action === 'list_windows' || action === 'bind')) {
    const app = String(input.app).toLowerCase();
    const name = app.split('.').at(-1);
    const aliases: Record<string, string> = {
      'com.apple.textedit': '文本编辑',
      'com.apple.notes': '备忘录',
      'com.apple.ical': '日历',
      'com.apple.reminders': '提醒事项',
      'com.apple.preview': '预览',
      'com.apple.finder': '访达',
      'com.apple.mail': '邮件',
    };
    return (
      !!name &&
      (text.toLowerCase().includes(app) ||
        (name.length >= 3 && text.toLowerCase().includes(name)) ||
        (!!aliases[app] && text.includes(aliases[app]!)))
    );
  }
  // Backend observations and mutations now require the already-admitted tab or window. Writes are still reviewed.
  return true;
}

/** A same-app ambiguity needs a window the owner actually identified. */
export function permitsWindow(text: string, window: { title: string; candidates: number }) {
  const named = /(?:[「“"]([^」”"\n]+)[」”"]\s*(?:的)?窗口|\bwindow\s+[「“"]([^」”"\n]+)[」”"])/iu.exec(text);
  if (named) return window.title === (named[1] ?? named[2]);
  return window.candidates === 1 || (!!window.title && text.includes(window.title));
}
