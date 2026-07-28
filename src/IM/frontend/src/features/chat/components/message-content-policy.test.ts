import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  classifyChatLink,
  extractCodeText,
  resolveContextMenuModality,
  serializeMessageBody,
  shouldKeepNativeContextMenu,
  type ContextMenuContextFacts,
  type RecentPointerRecord,
} from "./message-content-policy";

const CURRENT_URL = "https://app.example.com/chat/c1";

function ctx(over: Partial<ContextMenuContextFacts> = {}): ContextMenuContextFacts {
  return {
    messageId: "m1",
    pointerType: "mouse",
    button: 2,
    buttons: 2,
    ctrlKey: false,
    clientX: 100,
    clientY: 100,
    timeStamp: 1000,
    ...over,
  };
}

function recent(over: Partial<RecentPointerRecord> = {}): RecentPointerRecord {
  return {
    messageId: "m1",
    pointerType: "mouse",
    button: 2,
    ctrlKey: false,
    clientX: 100,
    clientY: 100,
    timeStamp: 500,
    ...over,
  };
}

describe("resolveContextMenuModality", () => {
  it("returns mouse for direct mouse secondary click (button === 2)", () => {
    expect(resolveContextMenuModality(ctx(), null)).toBe("mouse");
  });

  it("returns mouse for macOS Control-click (button === 0, ctrlKey)", () => {
    expect(resolveContextMenuModality(ctx({ button: 0, ctrlKey: true }), null)).toBe("mouse");
  });

  it("returns keyboard for ContextMenu/Shift+F10 (button === -1)", () => {
    expect(resolveContextMenuModality(ctx({ button: -1, pointerType: "mouse" }), null)).toBe("keyboard");
  });

  it("returns keyboard for direct mouse primary click without ctrlKey", () => {
    expect(resolveContextMenuModality(ctx({ button: 0, ctrlKey: false }), null)).toBe("keyboard");
  });

  it("returns touch for direct touch", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: "touch", button: 0 }), null)).toBe("touch");
  });

  it("returns pen for direct pen", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: "pen", button: 0 }), null)).toBe("pen");
  });

  it("returns unknown for unrecognized direct pointerType", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: "", button: 0 }), null)).toBe("unknown");
  });

  it("uses recent mouse fallback when context lacks pointerType but matches secondary kind", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined }), recent())).toBe("mouse");
  });

  it("rejects recent fallback when messageId differs", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined }), recent({ messageId: "m2" }))).toBe("unknown");
  });

  it("rejects recent fallback when secondary kind differs", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined }), recent({ button: 0, ctrlKey: true }))).toBe("unknown");
  });

  it("rejects recent fallback beyond 1500ms", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined, timeStamp: 2100 }), recent({ timeStamp: 500 }))).toBe("unknown");
  });

  it("accepts recent fallback at exactly 1500ms", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined, timeStamp: 2000 }), recent({ timeStamp: 500 }))).toBe("mouse");
  });

  it("rejects recent fallback beyond 8px Euclidean distance", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined, clientX: 109 }), recent({ clientX: 100 }))).toBe("unknown");
  });

  it("accepts recent fallback within 8px Euclidean distance", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined, clientX: 107 }), recent({ clientX: 100 }))).toBe("mouse");
  });

  it("rejects recent fallback when recent was not mouse", () => {
    expect(resolveContextMenuModality(ctx({ pointerType: undefined }), recent({ pointerType: "touch", button: 0 }))).toBe("unknown");
  });
});

describe("shouldKeepNativeContextMenu", () => {
  function makeBody(html: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "chat-message-body";
    el.innerHTML = html;
    el.getBoundingClientRect = () => ({
      top: 0, left: 0, bottom: 200, right: 400, width: 400, height: 200,
      x: 0, y: 0, toJSON: () => ({}),
    });
    document.body.appendChild(el);
    return el;
  }

  afterEach(() => {
    document.body.innerHTML = "";
    window.getSelection()?.removeAllRanges();
  });

  it("keeps native for non-mouse modality", () => {
    const body = makeBody("<p>hello</p>");
    expect(shouldKeepNativeContextMenu("touch", body, body, 10, 10, null, document)).toBe(true);
  });

  it("keeps native when target is a link", () => {
    const body = makeBody('<p><a href="https://x.com">link</a></p>');
    const link = body.querySelector("a")!;
    expect(shouldKeepNativeContextMenu("mouse", body, link, 10, 10, null, document)).toBe(true);
  });

  it("keeps native when target is inside code", () => {
    const body = makeBody("<pre><code>code</code></pre>");
    const code = body.querySelector("code")!;
    expect(shouldKeepNativeContextMenu("mouse", body, code, 10, 10, null, document)).toBe(true);
  });

  it("opens IM menu on plain card area with no selection", () => {
    const body = makeBody("<p>hello world</p>");
    expect(shouldKeepNativeContextMenu("mouse", body, body, 10, 10, null, document)).toBe(false);
  });

  it("keeps native when caret point is inside current selection", () => {
    const body = makeBody("<p id='p'>hello world</p>");
    const p = body.querySelector("#p")!.firstChild!;
    const range = document.createRange();
    range.setStart(p, 0);
    range.setEnd(p, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);

    // Mock caret API to return a point inside the selection.
    const originalCaretRangeFromPoint = (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint;
    (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint = () => {
      const r = document.createRange();
      r.setStart(p, 2);
      r.setEnd(p, 2);
      return r;
    };

    try {
      expect(shouldKeepNativeContextMenu("mouse", body, body, 10, 10, null, document)).toBe(true);
    } finally {
      (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint = originalCaretRangeFromPoint;
      sel.removeAllRanges();
    }
  });

  it("opens IM menu when caret point is outside current selection", () => {
    const body = makeBody("<p id='p'>hello world</p>");
    const p = body.querySelector("#p")!.firstChild!;
    const range = document.createRange();
    range.setStart(p, 0);
    range.setEnd(p, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);

    const originalCaretRangeFromPoint = (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint;
    (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint = () => {
      const r = document.createRange();
      r.setStart(p, 8);
      r.setEnd(p, 8);
      return r;
    };

    try {
      expect(shouldKeepNativeContextMenu("mouse", body, body, 10, 10, null, document)).toBe(false);
    } finally {
      (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint = originalCaretRangeFromPoint;
      sel.removeAllRanges();
    }
  });

  it("keeps native when caret API is unavailable and there is a selection", () => {
    const body = makeBody("<p id='p'>hello world</p>");
    const p = body.querySelector("#p")!.firstChild!;
    const range = document.createRange();
    range.setStart(p, 0);
    range.setEnd(p, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);

    const originalCaretRangeFromPoint = (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (document as any).caretRangeFromPoint;

    try {
      expect(shouldKeepNativeContextMenu("mouse", body, body, 10, 10, null, document)).toBe(true);
    } finally {
      if (originalCaretRangeFromPoint) {
        (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint = originalCaretRangeFromPoint;
      }
      sel.removeAllRanges();
    }
  });
});

describe("classifyChatLink", () => {
  it("classifies relative URL as same-origin-document", () => {
    expect(classifyChatLink("/chat/c2", "chat", CURRENT_URL)).toBe("same-origin-document");
  });

  it("classifies hash as same-origin-document", () => {
    expect(classifyChatLink("#section", "section", CURRENT_URL)).toBe("same-origin-document");
  });

  it("classifies same-origin absolute URL as same-origin-document", () => {
    expect(classifyChatLink("https://app.example.com/openapi.json", "api", CURRENT_URL)).toBe("same-origin-document");
  });

  it("classifies cross-origin http(s) as external", () => {
    expect(classifyChatLink("https://example.com/docs", "Docs", CURRENT_URL)).toBe("external");
  });

  it("classifies mailto as system", () => {
    expect(classifyChatLink("mailto:hi@example.com", "email", CURRENT_URL)).toBe("system");
  });

  it("classifies empty href as unsupported", () => {
    expect(classifyChatLink("", "x", CURRENT_URL)).toBe("unsupported");
  });

  it("classifies tel (rejected by sanitizer) as unsupported", () => {
    expect(classifyChatLink("tel:+123", "call", CURRENT_URL)).toBe("unsupported");
  });

  it("classifies malformed URL as unsupported", () => {
    expect(classifyChatLink("::not-a-url", "x", CURRENT_URL)).toBe("unsupported");
  });
});

describe("serializeMessageBody", () => {
  function body(html: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "chat-message-body";
    el.innerHTML = html;
    return el;
  }

  it("serializes the design.md rich-copy fixture exactly", () => {
    const fixtureHtml = [
      "<p>Intro</p>",
      "<ul><li>Alpha</li><li>Beta<ul><li>Nested</li></ul></li></ul>",
      '<ol start="3"><li>Third</li><li value="4">Fourth</li></ol>',
      "<table><tbody><tr><td>Name</td><td>Value</td></tr><tr><td>Count</td><td>2</td></tr></tbody></table>",
      "<pre><code>if (ready) {\n\n  run();\n}</code></pre>",
      '<p><a href="https://example.com/docs">Docs</a></p>',
    ].join("");
    const fixture = body(fixtureHtml);

    const expected = [
      "Intro",
      "",
      "- Alpha",
      "- Beta",
      "  - Nested",
      "",
      "3. Third",
      "4. Fourth",
      "",
      "Name\tValue",
      "Count\t2",
      "",
      "if (ready) {",
      "",
      "  run();",
      "}",
      "",
      "Docs (https://example.com/docs)",
    ].join("\n");

    expect(serializeMessageBody(fixture)).toBe(expected);
  });

  it("skips data-clipboard-exclude nodes", () => {
    const el = body("<p>keep <span data-clipboard-exclude>ignore</span> end</p>");
    expect(serializeMessageBody(el)).toBe("keep  end");
  });

  it("does not duplicate URL for raw URL links", () => {
    const el = body('<p><a href="https://example.com/">https://example.com</a></p>');
    expect(serializeMessageBody(el)).toBe("https://example.com");
  });

  it("preserves inline code without extra formatting", () => {
    const el = body("<p>use <code>const x = 1</code> please</p>");
    expect(serializeMessageBody(el)).toBe("use const x = 1 please");
  });
});

describe("extractCodeText", () => {
  it("removes a single renderer trailing newline", () => {
    const code = document.createElement("code");
    code.textContent = "if (x) {\n  y();\n}\n";
    expect(extractCodeText(code)).toBe("if (x) {\n  y();\n}");
  });

  it("keeps internal blank lines and indentation", () => {
    const code = document.createElement("code");
    code.textContent = "line1\n\n  line3\n";
    expect(extractCodeText(code)).toBe("line1\n\n  line3");
  });

  it("returns text unchanged when no trailing newline", () => {
    const code = document.createElement("code");
    code.textContent = "compact";
    expect(extractCodeText(code)).toBe("compact");
  });
});
