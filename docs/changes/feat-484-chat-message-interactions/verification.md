# Verification Report: feat-484

## Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; all spec requirements have implementation |
| Correctness | implementation present but 1 CRITICAL correctness gap; several WARNINGs for spec/design drift and missing tests |
| Coherence | mostly followed; 2 design decisions violated (toolbar display:none; context-menu focus/arrow navigation missing) |

**Verdict: fail** — 1 CRITICAL issue found. Fix before PR.

---

## Completeness

- **Tasks:** 10/10 complete (`M1-impl/tasks.md` R1–R10 all `- [x]`).
- **Spec coverage:** every Requirement/Scenario from `spec.md` has a corresponding implementation:
  - native text selection / partial copy — `message-pane.tsx:1281-1293`, CSS `user-select:text` at `styles/global.css:1720-1733`.
  - message-level actions (toolbar / context menu / More sheet) — `MessageActionList` (`message-pane.tsx:992-1080`), `MessageBubble` toolbar (`message-pane.tsx:1325-1342`), context menu (`message-pane.tsx:867-910`), Radix action sheet (`message-pane.tsx:912-964`).
  - whole-message copy + feedback — `requestCopy`/`publishCopyResult`/`showCopyNotice` (`message-pane.tsx:296-372`).
  - link navigation by origin — `classifyChatLink` + `ChatMarkdownLink` renderer (`message-content-policy.ts:130-173`, `message-pane.tsx:1437-1477`).
  - independent code-block copy — `MarkdownCodeBlock` renderer (`message-pane.tsx:1478-1498`).
  - keyboard / touch / i18n consistency — i18n keys (`i18n/zh.json:521-532`, `i18n/en.json:524-532`), More button min 44×44 (`styles/global.css:1775-1806`), sheet focus trap via Radix Dialog.
- **Prototype / Reference contract:** all six `must-match` rows from `design.md` are projected to M1-R1–R6 and have durable evidence in `M1-impl/evidence/` (screenshots + `progress.md` Prototype Comparison).

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 桌面端复制选中的局部文字 | CSS `user-select:text`; no custom handler intercepts selection copy | N/A (browser native) | covered |
| 桌面端选中文字后打开右键菜单 | `shouldKeepNativeContextMenu` caret-point check (`message-content-policy.ts:265-310`) | `message-content-policy.test.ts:144-195` | covered |
| 移动端长按选择消息文字 | CSS `user-select:text`; `resolveContextMenuModality` returns touch/pen; no preventDefault | `message-pane.test.ts:913-929` | covered |
| 桌面端按需显示消息操作 | `.chat-message-toolbar` hover/focus-within; `.chat-message-more` media-query reveal | partially covered (no hover/focus visibility test) | warning — missing test |
| 桌面端普通气泡右键 | `handleContextMenu` → `shouldKeepNativeContextMenu` → `requestMessageMenu` | `message-pane.test.ts:891-911` | covered for plain card; **CRITICAL gap for link/code text targets** (see Issues) |
| 链接与正文选区保留原生右键能力 | `isNativeInteractiveTarget` (`message-content-policy.ts:244-257`) | missing | **CRITICAL** — `isNativeInteractiveTarget` ignores Text-node targets |
| 移动端打开消息操作 | `.chat-message-more` + Radix Dialog sheet | `message-pane.test.ts:931-950` | covered |
| 普通阅读状态不常驻操作 | toolbar hidden by default; More only on compact/coarse | no explicit assertion | warning — missing test |
| 复制整条富文本消息 | `serializeMessageBody` (`message-content-policy.ts:446-449`) | `message-content-policy.test.ts:264-297` rich-copy fixture | covered |
| 有选区时仍可明确复制整条消息 | `requestCopy` uses `bodyElement`, not page selection | no explicit assertion | warning — missing test |
| 整条复制不混入外围信息 | `serializeMessageBody` only traverses `.chat-message-body`; attachments/token/etc. excluded by DOM boundary | implicit in fixture | covered |
| 复制成功/失败反馈 | `showCopyNotice` + `chat-copy-notice` | `message-pane.test.ts:873-889`, `952-995` | covered for happy path and immediate rejection |
| A→B→A / newer attempt / stale notice timer | implemented in refs (`message-pane.tsx:228-314`) | **missing** | warning — design M1-R8 requires deferred-Promise tests |
| 外部网页链接新标签打开 | `target="_blank" rel="noopener noreferrer"` (`message-pane.tsx:1464-1465`) | missing | warning — design M1-R8 requires target/rel/aria-label test |
| IM 内部链接当前标签导航 | `classifyChatLink` same-origin/relative/hash → no target | `message-content-policy.test.ts:222-253` | covered for `/`/`./`/`#`/same-origin; **WARNING** bare relative like `foo/bar` misclassified as unsupported |
| 具名外链克制提示，裸 URL 不重复 | `im-md-link-indicator` pseudo-element; `isNamedExternal` check | missing | warning — `isNamedExternal` does not reuse `normalizeUrl`, so trailing-slash variants may show ↗ on bare URLs |
| 不支持的链接目标 | `unsupported` span | `message-content-policy.test.ts:243-253` | covered |
| 代码块独立精确复制 | `.im-code-block` + `.im-code-copy` + `extractCodeText` | `message-content-policy.test.ts:315-333` | policy covered; missing component-level test for button behavior / inline code no-button |
| 键盘操作代码复制 | button is real `<button>` with aria-label | missing | warning |
| 键盘访问消息操作 | toolbar/menu/sheet use real buttons; sheet uses Radix focus trap | missing focus/arrow tests | warning — context menu lacks focus management and arrow navigation |
| 界面语言保持一致 | i18n keys added for all new strings; zh no isolated "fork" | `i18n.test.ts` referenced in progress.md | covered |
| 触控入口易于点击 | `.chat-message-more` min 44×44; sheet rows min 44px | no explicit assertion | warning |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策1: 正文事件按输入方式与精确触发点判定所有权 | partially | `resolveContextMenuModality`/`shouldKeepNativeContextMenu` present (`message-content-policy.ts:61-310`); **Text-node target handling missing**; pointerdown recorded in bubble phase not capture phase (`message-pane.tsx:1149-1165`) |
| 决策2: 三种表面共享同一 action model | yes | `MessageActionList` shared by toolbar/context-menu/sheet (`message-pane.tsx:992-1080`) |
| 决策2: toolbar 不用 display:none | **no** | `styles/global.css:1759,1769-1772` uses `display:none` / `display:inline-flex` |
| 决策3: 从正文 DOM 序列化 text/plain | yes | `serializeMessageBody` (`message-content-policy.ts:446-449`); fixture matches `design.md` expected string |
| 决策4: 链接按 origin 分类，外链新标签 | partially | `classifyChatLink` + `ChatMarkdownLink` (`message-pane.tsx:1437-1477`); **bare relative URL unsupported**; **isNamedExternal does not reuse normalizeUrl** |
| 决策5: 代码块由 Markdown renderer 提供独立复制入口 | yes | `pre` renderer wraps `.im-code-block` with copy button (`message-pane.tsx:1478-1498`) |
| 决策6: Pane 级状态驱动 Radix Dialog 与单一反馈 | partially | copy coordinator tokens present (`message-pane.tsx:228-372`); Radix sheet focus restore present (`message-pane.tsx:923-930`); **context menu lacks focus-first-item and arrow-key roving navigation** |
| 决策7: 变更止于 Web IM 前端 | yes | changes only in `src/IM/frontend/src/` and `docs/changes/feat-484-chat-message-interactions/` |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| fine pointer/keyboard 普通阅读态 + hover/focus icon toolbar | M1-R2, M1-R6 | `styles/global.css:1755-1773`; `MessageActionList` toolbar surface | `r7-desktop-default.png`, `r7-desktop-hover-toolbar.png` | covered |
| mouse 精确选区/链接/code 保留原生菜单；普通区域开短 IM menu | M1-R1, M1-R2 | `message-content-policy.ts:265-310`; `message-pane.tsx:1167-1206` | `r7-desktop-context-menu.png` | **critical** — Text-node targets inside links/code slip through `isNativeInteractiveTarget` |
| clean whole-message copy + success/error snackbar | M1-R3 | `requestCopy`/`showCopyNotice` (`message-pane.tsx:296-372`) | `r7-desktop-copy-success.png` | covered |
| named external / raw URL / same-origin / unsupported link | M1-R4 | `classifyChatLink` + `ChatMarkdownLink` (`message-pane.tsx:1437-1477`) | `r7-desktop-external-link.png` | warning — `isNamedExternal` trailing-slash mismatch vs serializer |
| code block 独立 copy button | M1-R5, M1-R6 | `.im-code-block` + `.im-code-copy` (`message-pane.tsx:1478-1498`) | `r7-desktop-code-block.png` | covered |
| compact/coarse More + shallow Radix action sheet | M1-R1, M1-R2, M1-R6 | `.chat-message-more` + `Dialog.Root` (`message-pane.tsx:912-964`) | `r7-hybrid-toolbar-more.png`, `r7-hybrid-action-sheet.png`, `r7-mobile-action-sheet.png` | covered |

---

## Issues

### CRITICAL（提 PR 前必须修）

1. **Link/code 内文本节点右键无法保留原生菜单。** `isNativeInteractiveTarget` (`message-content-policy.ts:244-257`) checks `target instanceof Element` first and returns `false` for Text nodes. In a real browser a right-click inside `<a>text</a>` or `<code>text</code>` can have a Text-node `EventTarget`; the handler then proceeds past the native-target guard, calls `preventDefault`, and opens the IM menu instead of the browser link/code menu. This violates `spec.md` “链接与正文选区保留原生右键能力” and `design.md` 决策1 (flowchart: target on link/code → native).
   - **Fix:** resolve the element to test against, e.g. `const el = target instanceof Element ? target : (target instanceof Node ? target.parentElement : null); return el?.closest("a, button, input, textarea, select, code, pre") !== null;`.

### WARNING（应该修）

2. **Context menu does not implement required keyboard focus/arrow navigation.** `design.md` 决策6 requires “打开后聚焦首个 enabled item，ArrowUp/ArrowDown/Home/End 导航，Escape/外部点击关闭”. The current implementation (`message-pane.tsx:867-910`) renders a `role="menu"` with plain `<button>` children and only handles Escape; it never auto-focuses the first item and provides no roving Arrow/Home/End behavior. This is a keyboard-regression risk for the must-match context-menu contract.
   - **Fix:** on open, focus the first non-`aria-disabled` menuitem; add `onKeyDown` Arrow/Home/End handlers that move `document.activeElement` among items and wrap.

3. **Toolbar visibility uses `display:none`, violating design.md 决策2 accessibility requirement.** `styles/global.css:1759` sets `display: none` on `.chat-message-toolbar` and switches to `display: inline-flex` on hover/focus-within. `design.md` 决策2 explicitly rejects `display:none` because it removes the toolbar from the accessibility tree. The current CSS may also make toolbar buttons non-discoverable to keyboard users until focus happens to land inside.
   - **Fix:** use `opacity: 0; pointer-events: none;` in the default state and `opacity: 1; pointer-events: auto;` on `:hover`/`:focus-within`, keeping the buttons in the tree.

4. **`classifyChatLink` misclassifies bare relative URLs as unsupported.** `message-content-policy.ts:160-169` only accepts relative URLs starting with `/`, `./`, `../`, `#`, or `?`. A plain relative URL such as `foo/bar` or `path/to/page` (valid per CommonMark and react-markdown’s default sanitizer) is rejected and rendered as an inert `<span>`, breaking `spec.md` “打开 IM 内部链接” and `design.md` 决策4 (relative address → same-origin-document).
   - **Fix:** treat any remaining non-scheme, non-empty href as `same-origin-document` after the http/https/mailto checks, or explicitly parse with `new URL(href, currentUrl)` and accept success as same-origin.

5. **`MarkdownContent` does not reuse the serializer’s URL normalization for the external-indicator decision.** `message-pane.tsx:1450-1459` compares `new URL(label).href !== new URL(href).href`. For a bare URL like `[https://example.com/path](https://example.com/path/)` the trailing-slash difference makes the link appear named and renders `↗`, while `serializeMessageBody` (`message-content-policy.ts:175-185`) uses `normalizeUrl` and treats them as the same bare URL. This contradicts `design.md` 决策4: “是否为裸 URL 使用与 serializer 相同的 URL normalization 比较”.
   - **Fix:** export `normalizeUrl`/`isLabelJustUrl` from `message-content-policy.ts` and reuse them inside the `a` renderer, or duplicate the normalization logic.

6. **Missing copy-coordinator async-ownership regression tests.** `design.md` M1-R8 requires deferred-Clipboard-Promise coverage for same-pane new surface, conversation switch, A→B→A, newer attempt superseding older attempt, and stale notice timer not clearing new notice. None of these scenarios are asserted in `message-pane.test.tsx` (lines 847–996 only cover immediate success/rejection).
   - **Fix:** add tests that resolve/reject a deferred `writeText` promise after opening a second surface, after switching `conversation.id`, after a newer copy attempt, and after a new notice has replaced an old one.

7. **Missing cross-node selection context-menu test.** `design.md` M1-R8 requires coverage for “跨 text node” selection inside/outside behavior. `message-content-policy.test.ts:144-219` only builds ranges within a single text node.
   - **Fix:** add a test with a range spanning two sibling text nodes and assert caret-point inside/outside the range.

8. **Missing component-level tests for link rendering and code-block copy button.** `design.md` M1-R8 lists external `aria-label`/`target`/`rel`, same-origin no-target, code-block copy button behavior, and inline-code no-button as required `message-pane.test.tsx` coverage. The current test file does not assert any of these.
   - **Fix:** add render assertions for external anchor attributes and code-block DOM (copy button present; inline `<code>` has no copy button).

9. **Chinese copy-error string has a trailing period inconsistent with spec/tasks.md.** `i18n/zh.json:524` uses `"复制失败，请重试。"` while `spec.md` and `tasks.md` R5 state the string as `"复制失败，请重试"` without punctuation.
   - **Fix:** remove the trailing `。` from `copyError` in `zh.json`.

### SUGGESTION（可以修）

10. **`recordPointer` records in bubble phase, not capture phase as specified.** `design.md` 决策1 says “气泡在 capture phase 记录最近一次 pointerdown”. The handler is attached as `onPointerDown` on `.chat-bubble-card` (`message-pane.tsx:1285`), which is bubble phase. This is currently sufficient because no child stops propagation, but it is a divergence from the documented decision.
    - **Fix:** use `onPointerDownCapture` on the card.

11. **Context-menu `onFork` performs a redundant eligibility check.** `message-pane.tsx:901-905` checks `agentOnline && !forkPending && onFork` even though `MessageActionList` already refuses to call `onFork` when `forkAvailable` is false. The duplication is harmless but adds maintenance surface.
    - **Fix:** rely on `MessageActionList`’s guard or move the single source of truth to the pane level.

12. **R7 evidence script has a fragile `lastAgentBubble` filter.** `docs/changes/feat-484-chat-message-interactions/M1-impl/evidence/r7-browser-qa.js:83-86` uses `.filter(async (b) => ...)` on an array of `ElementHandle`s; the async predicate always returns a truthy Promise, so the filter is effectively a no-op. The fallback `|| bubbles[bubbles.length - 1]` rescues it, but the code is misleading.
    - **Fix:** iterate with a `for...of` loop and explicitly pick the last element whose class contains `chat-bubble--agent`.

---

*Report produced by change-verifier, round 1.*
