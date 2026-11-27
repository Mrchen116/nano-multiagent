/** Structural host invariants for an authenticated owner turn; semantic target matching belongs to NanoApproval. */
export function computerScope(text: string, clipboard: boolean) {
  if (clipboard) return { clipboard: true, browser: false, desktop: false, isolatedOnly: false };
  const isolatedOnly = /隔离|干净|独立.{0,6}(?:环境|profile)|isolated|clean profile/i.test(text);
  return { clipboard: false, browser: true, desktop: true, isolatedOnly };
}

export function scopeAllows(
  _text: string,
  scope: ReturnType<typeof computerScope>,
  surface: 'browser' | 'desktop',
  action: string,
  input: Record<string, unknown>,
) {
  if (action === 'read_clipboard') return surface === 'desktop' && scope.clipboard;
  if (!scope[surface]) return false;
  if (surface === 'browser' && action === 'open' && scope.isolatedOnly && input.mode !== 'isolated') {
    return false;
  }
  // Every open/navigate/new_tab/bind/click/type/upload action enters NanoApproval with host_observation
  // and full retained conversation instructions, supporting natural language and multi-turn follow-ups.
  return true;
}

/** A same-app ambiguity needs a window the owner actually identified in the conversation. */
export function permitsWindow(text: string, window: { title: string; candidates: number }) {
  const matches = [
    ...text.matchAll(/(?:[「“"]([^」”"\n]+)[」”"]\s*(?:的)?窗口|\bwindow\s+[「“"]([^」”"\n]+)[」”"])/giu),
  ];
  const lastNamed = matches.at(-1);
  if (lastNamed) return window.title === (lastNamed[1] ?? lastNamed[2]);
  return window.candidates === 1 || (!!window.title && text.includes(window.title));
}
