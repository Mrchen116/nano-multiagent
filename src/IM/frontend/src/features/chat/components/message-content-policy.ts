/**
 * feat-484-M1: 消息正文内容策略。
 *
 * 这些函数是纯策略接口：不读 React state、不写 Clipboard、不导航。
 * DOM 副作用仍由用户事件发起处承担，便于对策略做稳定单测。
 */

export type ChatLinkDisposition =
  | "same-origin-document"
  | "external"
  | "system"
  | "unsupported";

export type ContextMenuModality =
  | "mouse"
  | "touch"
  | "pen"
  | "keyboard"
  | "unknown";

export type MouseSecondaryKind = "button-2" | "control-primary";

export type ContextMenuContextFacts = {
  messageId: string;
  pointerType?: string | undefined;
  button: number;
  buttons: number;
  ctrlKey: boolean;
  clientX: number;
  clientY: number;
  timeStamp: number;
};

export type RecentPointerRecord = {
  messageId: string;
  pointerType: string;
  button: number;
  ctrlKey: boolean;
  clientX: number;
  clientY: number;
  timeStamp: number;
};

function getMouseSecondaryKind(button: number, ctrlKey: boolean): MouseSecondaryKind | null {
  if (button === 2) return "button-2";
  if (button === 0 && ctrlKey) return "control-primary";
  return null;
}

/**
 * 按本次输入方式解析 context menu 的 modality。
 *
 * 判定顺序：
 * 1. button < 0 → keyboard（Chromium 的 ContextMenu 键/Shift+F10 会如此上报）。
 * 2. direct touch/pen → 原样返回。
 * 3. direct mouse → 只有存在 secondary kind（button-2 或 control-primary）才返回 mouse。
 * 4. 无有效 direct pointerType → 用 recent pointer record fallback；必须满足
 *    same-message、0–1500ms、欧氏距离 ≤8px、secondary kind 完全相同。
 * 5. 其余 → unknown。
 */
export function resolveContextMenuModality(
  context: ContextMenuContextFacts,
  recent: RecentPointerRecord | null
): ContextMenuModality {
  if (context.button < 0) return "keyboard";

  const directPointerType = context.pointerType;
  if (directPointerType === "touch") return "touch";
  if (directPointerType === "pen") return "pen";

  if (directPointerType === "mouse") {
    const kind = getMouseSecondaryKind(context.button, context.ctrlKey);
    return kind !== null ? "mouse" : "keyboard";
  }

  // No direct pointerType or unrecognized: use recent record fallback if context itself looks
  // like a secondary click (browser may report pointerType:"mouse" for keyboard menu).
  const contextKind = getMouseSecondaryKind(context.button, context.ctrlKey);
  if (!recent || contextKind === null) return "unknown";

  if (recent.messageId !== context.messageId) return "unknown";
  if (recent.pointerType !== "mouse") return "unknown";

  const recentKind = getMouseSecondaryKind(recent.button, recent.ctrlKey);
  if (recentKind !== contextKind) return "unknown";

  const elapsed = context.timeStamp - recent.timeStamp;
  if (elapsed < 0 || elapsed > 1500) return "unknown";

  const dx = context.clientX - recent.clientX;
  const dy = context.clientY - recent.clientY;
  if (Math.hypot(dx, dy) > 8) return "unknown";

  return "mouse";
}

function normalizeUrl(url: string): string {
  try {
    // Drop trailing slash and default port differences for "is the label just the URL" checks.
    const u = new URL(url);
    let host = u.host;
    if (
      (u.protocol === "https:" && u.port === "443") ||
      (u.protocol === "http:" && u.port === "80")
    ) {
      host = u.hostname;
    }
    let pathname = u.pathname;
    if (pathname !== "/" && pathname.endsWith("/")) {
      pathname = pathname.slice(0, -1);
    }
    return `${u.protocol}//${host}${pathname}${u.search}`.toLowerCase();
  } catch {
    return url.trim().toLowerCase();
  }
}

function looksLikeUrl(text: string): boolean {
  return /^https?:\/\//i.test(text.trim());
}

/**
 * 对 react-markdown 默认 urlTransform 后的 href 做链接分类。
 *
 * - same-origin-document: 相对地址、hash、或解析后与当前页面 origin 同源的 http(s)。
 * - external: 跨 origin 的 http(s)。
 * - system: mailto:。
 * - unsupported: 空、malformed、tel: 或其他未被默认 sanitizer 放行的 scheme。
 */
export function classifyChatLink(
  href: string,
  label: string,
  currentUrl: string | URL
): ChatLinkDisposition {
  if (!href || href.trim() === "") return "unsupported";

  const trimmedHref = href.trim();
  const lower = trimmedHref.toLowerCase();

  if (lower.startsWith("mailto:")) {
    return "system";
  }

  // Absolute http(s) URLs
  if (lower.startsWith("http://") || lower.startsWith("https://")) {
    let resolved: URL;
    let base: URL;
    try {
      resolved = new URL(trimmedHref);
      base = typeof currentUrl === "string" ? new URL(currentUrl) : currentUrl;
    } catch {
      return "unsupported";
    }
    if (resolved.origin.toLowerCase() === base.origin.toLowerCase()) {
      return "same-origin-document";
    }
    return "external";
  }

  // Relative paths, hash links, query-only links.
  if (
    trimmedHref.startsWith("/") ||
    trimmedHref.startsWith("./") ||
    trimmedHref.startsWith("../") ||
    trimmedHref.startsWith("#") ||
    trimmedHref.startsWith("?")
  ) {
    return "same-origin-document";
  }

  // Anything else (including malformed schemes like "tel:", "::not-a-url") is unsupported.
  return "unsupported";
}

function isLabelJustUrl(label: string, href: string, currentUrl: string | URL): boolean {
  const trimmed = label.trim();
  if (!trimmed) return false;
  try {
    const labelResolved = new URL(trimmed, currentUrl);
    const hrefResolved = new URL(href, currentUrl);
    return normalizeUrl(labelResolved.href) === normalizeUrl(hrefResolved.href);
  } catch {
    return false;
  }
}

function getSelectionForMessage(bodyRoot: HTMLElement): Selection | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  if (sel.isCollapsed) return null;

  // Ensure at least part of the selection is inside the body root.
  for (let i = 0; i < sel.rangeCount; i++) {
    const range = sel.getRangeAt(i);
    if (
      bodyRoot.contains(range.commonAncestorContainer) ||
      bodyRoot === range.commonAncestorContainer
    ) {
      return sel;
    }
  }
  return null;
}

function caretPointFrom(
  doc: Document,
  clientX: number,
  clientY: number
): { node: Node; offset: number } | null {
  // Standard API (Gecko)
  const caretPosition = (doc as Document & { caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null })
    .caretPositionFromPoint?.(clientX, clientY);
  if (caretPosition) {
    return { node: caretPosition.offsetNode, offset: caretPosition.offset };
  }

  // WebKit/Blink fallback
  const docRange = (doc as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null })
    .caretRangeFromPoint?.(clientX, clientY);
  if (docRange) {
    return { node: docRange.startContainer, offset: docRange.startOffset };
  }

  return null;
}

function isPointInsideSelection(
  selection: Selection,
  point: { node: Node; offset: number }
): boolean {
  for (let i = 0; i < selection.rangeCount; i++) {
    const range = selection.getRangeAt(i);
    try {
      if (range.comparePoint(point.node, point.offset) === 0) {
        return true;
      }
    } catch {
      // comparePoint throws for non-text containers; ignore.
    }
  }
  return false;
}

function isNativeInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === "a" ||
    tag === "button" ||
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    tag === "code" ||
    target.closest("code") !== null ||
    target.closest("pre") !== null
  );
}

/**
 * 判断是否应把 contextmenu 完全交给浏览器原生处理。
 *
 * 只对明确 mouse、非原生 target、且精确触发点在选区外的事件返回 false。
 * 无法解析时保守返回 true（交给浏览器）。
 */
export function shouldKeepNativeContextMenu(
  modality: ContextMenuModality,
  bodyRoot: HTMLElement,
  target: EventTarget | null,
  clientX: number,
  clientY: number,
  selection: Selection | null,
  doc: Document
): boolean {
  if (modality !== "mouse") return true;

  if (isNativeInteractiveTarget(target)) return true;

  const bodyRect = bodyRoot.getBoundingClientRect();
  if (
    clientX < bodyRect.left ||
    clientX > bodyRect.right ||
    clientY < bodyRect.top ||
    clientY > bodyRect.bottom
  ) {
    return true;
  }

  const effectiveSelection = (selection && !selection.isCollapsed ? selection : null) ?? getSelectionForMessage(bodyRoot);
  if (!effectiveSelection) {
    // No selection in this message: proceed to IM menu if not on native target.
    return false;
  }

  const point = caretPointFrom(doc, clientX, clientY);
  if (!point) {
    // Cannot precisely locate caret: conservatively let browser handle it.
    return true;
  }

  // If the caret point is outside the body root, let browser handle.
  if (!bodyRoot.contains(point.node) && bodyRoot !== point.node) {
    return true;
  }

  if (isPointInsideSelection(effectiveSelection, point)) {
    return true;
  }

  return false;
}

function isBlockElement(node: Node): boolean {
  if (!(node instanceof HTMLElement)) return false;
  const blockish = new Set([
    "P", "DIV", "H1", "H2", "H3", "H4", "H5", "H6", "BLOCKQUOTE",
    "UL", "OL", "LI", "TABLE", "THEAD", "TBODY", "TR", "PRE",
    "BR", "HR"
  ]);
  if (blockish.has(node.tagName)) return true;
  const display = window.getComputedStyle?.(node).display;
  if (display && display !== "inline") return true;
  return false;
}

function collectText(
  node: Node,
  opts: { excludeSelector: string; withinCode: boolean }
): { text: string; endsWithBlock: boolean } {
  if (node.nodeType === Node.TEXT_NODE) {
    return { text: node.textContent ?? "", endsWithBlock: false };
  }

  if (!(node instanceof Element)) {
    return { text: "", endsWithBlock: false };
  }

  if (node.matches(opts.excludeSelector)) {
    return { text: "", endsWithBlock: false };
  }

  const tag = node.tagName.toLowerCase();

  // Inside a code block, preserve whitespace exactly; do not add list markers.
  if (tag === "code" || opts.withinCode) {
    const inner = node.textContent ?? "";
    return { text: inner, endsWithBlock: false };
  }

  if (tag === "br") {
    return { text: "\n", endsWithBlock: false };
  }

  // List item: prepend marker based on parent list type and start/value.
  let prefix = "";
  if (tag === "li") {
    const parent = node.parentElement;
    if (parent?.tagName.toLowerCase() === "ol") {
      const start = Number(parent.getAttribute("start") || "1");
      const value = Number(node.getAttribute("value") || String(start + Array.from(parent.children).indexOf(node)));
      prefix = `${value}. `;
    } else {
      const depth = listDepth(node);
      prefix = `${"  ".repeat(Math.max(0, depth))}- `;
    }
  }

  let text = prefix;
  let endsWithBlock = false;

  if (tag === "tr") {
    // Table row: separate cells with tabs.
    const cells: string[] = [];
    for (const child of Array.from(node.children)) {
      const childTag = child.tagName.toLowerCase();
      if (childTag === "td" || childTag === "th") {
        cells.push(collectText(child, opts).text.trim().replace(/\t/g, " "));
      }
    }
    return { text: cells.join("\t") + "\n", endsWithBlock: true };
  }

  for (const child of Array.from(node.childNodes)) {
    const childResult = collectText(child, { ...opts, withinCode: tag === "pre" });
    if (childResult.endsWithBlock && text.length > prefix.length && !text.endsWith("\n")) {
      text += "\n";
    }
    text += childResult.text;
    endsWithBlock = childResult.endsWithBlock;
  }

  if (tag === "li") {
    return { text: text.replace(/\n+$/g, "") + "\n", endsWithBlock: true };
  }

  if (isBlockElement(node)) {
    // Block elements are separated by a blank line (two newlines).
    text = text.replace(/\n+$/g, "") + "\n\n";
    return { text, endsWithBlock: true };
  }

  // Inline link: if label is not just the URL, append absolute URL in parentheses.
  if (tag === "a") {
    const href = node.getAttribute("href") ?? "";
    const labelText = node.textContent ?? "";
    const currentUrl = window.location.href;
    if (href && !isLabelJustUrl(labelText, href, currentUrl)) {
      try {
        const absolute = new URL(href, currentUrl).href;
        text = `${text.trimEnd()} (${absolute})`;
      } catch {
        // keep label as-is
      }
    }
  }

  return { text, endsWithBlock: false };
}

function listDepth(li: Element): number {
  let depth = 0;
  let el: Element | null = li.parentElement;
  while (el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "ul" || tag === "ol") depth++;
    el = el.parentElement;
  }
  // The immediate parent list is depth 0; each nested ancestor adds one.
  return Math.max(0, depth - 1);
}

function collapseBlockSpacing(text: string): string {
  // Collapse 3+ consecutive newlines down to 2 (one blank line between blocks).
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * 把 `.chat-message-body` 根节点序列化为干净的 `text/plain`。
 *
 * - 跳过 `data-clipboard-exclude` 节点。
 * - 段落/标题/引用/list item/table row/code block 保持边界。
 * - list item 带可读项目符号；有序项沿用 ol[start]/li[value]。
 * - table cell 以 tab 分隔。
 * - code block 保留内部换行和缩进。
 * - 具名链接输出 `label (absolute URL)`；裸 URL 不重复。
 */
export function serializeMessageBody(root: HTMLElement): string {
  const raw = collectText(root, { excludeSelector: "[data-clipboard-exclude]", withinCode: false });
  return collapseBlockSpacing(raw.text);
}

/**
 * 提取单个代码块的精确文本。
 *
 * 保留缩进与内部空行，仅移除 renderer 追加的单个结构性尾换行。
 */
export function extractCodeText(codeElement: HTMLElement): string {
  const text = codeElement.textContent ?? "";
  // react-markdown typically appends one trailing newline to fenced code blocks.
  return text.endsWith("\n") ? text.slice(0, -1) : text;
}
