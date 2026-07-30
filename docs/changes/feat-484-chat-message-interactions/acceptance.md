# feat-484 — 验收报告 Round 1

> 对齐: [spec.md](spec.md) v1 / [design.md](design.md) v1
> 工作区: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-484`（unit HEAD + 上一任 worker 未提交 WIP，仅 `message-pane.tsx` / `message-pane.test.tsx` 有差异）
> 验收时间: 2026-07-29

## Verdict

**fail**

**Highest Required Action**: `fix-implementation`

核心原因: "复制整条富文本消息" 的用户可观察结果不符合验收标准与 design.md 冻结的 rich-copy fixture——实际粘贴文本在列表项之间出现多余空行，且外部链接因 `display: inline-flex` 被序列化器误判为块级元素，导致链接 label 与周围正文断开。该 Scenario 为必验项，故本轮不能给 pass。

## 用户旅程体验

### Journey 1: 桌面端 1440×900 — 阅读、hover toolbar、右键菜单、整条复制、代码复制、外链

- 登录后进入 direct-agent 会话，Agent 已按提示返回包含多段正文、无序列表（含嵌套）、具名外链、裸 URL、相对链接 `/chat`、两个 fenced 代码块的完整回复。
- 普通阅读态气泡干净，无常驻按钮（`desktop-reading.png`）。
- 鼠标 hover 后气泡右上方出现 Copy message / Branch from here toolbar（`desktop-hover-toolbar.png`）。
- 键盘 Tab 可聚焦 toolbar 按钮，`:focus-visible` 可见（`desktop-focus-toolbar.png`）。
- 在气泡普通正文区域右键，出现短消息菜单 Copy message / Branch from here / Cancel（`desktop-contextmenu.png`）。
- 在选区内右键，`contextmenu` 事件 `defaultPrevented === false`，浏览器原生菜单保留（`desktop-selection.png`）。
- 点击 toolbar Copy message，弹出 "Copied" 反馈（`desktop-copy-result.png`）。 granted clipboard 权限后实际写入剪贴板，但内容结构异常（详见 Issues）。
- 代码块 hover 显示独立 copy 按钮，点击后仅复制该代码块内容并提示 "Copied"（`desktop-code-hover.png`, `desktop-code-copy-result.png`）。
- 外部链接 hover 显示克制 ↗ 提示，具名外链 aria-label 为 "文档, opens in new tab"；裸 URL 无重复 ↗。

### Journey 2: Hybrid 1024×768（启用 touch）— toolbar + More 同时可达

- 鼠标 hover 仍出现 desktop toolbar（`hybrid-hover-toolbar.png`）。
- 因 `(any-pointer: coarse)` 生效，气泡状态行出现 More 按钮（44×44px，日志确认）。
- 点击 More 打开底部 action sheet，内容与桌面右键菜单一致（`hybrid-sheet.png`）。

### Journey 3: WebKit Mobile 390×844 + touch — 原生选择、More sheet、焦点

- 移动阅读态无 toolbar，代码块 copy 按钮可见，状态行显示 More 按钮（`mobile-reading.png`, `mobile-more-hover.png` 显示 hover 高亮）。
- 长按/双击正文未触发 IM 自定义菜单；系统文本选择能力因 headless WebKit 限制未能在截图中直接捕获选择柄，但无任何 IM 浮层拦截。
- 点击 More 打开 Radix action sheet，背景隔离 app bottom nav（`mobile-sheet.png`）。
- Tab 后焦点落在 sheet 内 Copy message 按钮；Escape 关闭后焦点回到 More 按钮（日志确认）。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html desktop 阅读态 | 阅读态无常驻操作按钮，正文优先 | `desktop-reading.png` | 1440×900 default | match |
| prototype.html desktop 操作态 | hover/focus 出现 Copy + Branch toolbar | `desktop-hover-toolbar.png` | 1440×900 hover | match |
| prototype.html desktop 菜单态 | mouse 普通区域右键出现短菜单 | `desktop-contextmenu.png` | 1440×900 context menu | match |
| prototype.html mobile sheet | compact/coarse More 打开 action sheet | `mobile-sheet.png` | 390×844 sheet open | match（文案语言因用户 locale=en 显示英文，属预期） |
| prototype.html hybrid 操作态 | toolbar 与 More 同时可达 | `hybrid-hover-toolbar.png`, `hybrid-sheet.png` | 1024×768 + touch | match |

## 问题清单

| # | 严重度 | Regression Relation | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | major | direct | "复制整条消息" 粘贴结果结构异常：列表项之间出现多余空行；具名外部链接 `display: inline-flex` 被 `serializeMessageBody` 的 `isBlockElement` 判定为块级，导致 label 与前后正文断开行。与 design.md 冻结 rich-copy fixture（列表项连续、具名链接输出 `label (absolute URL)` 内联）不符。 | fix-implementation | 直接违反 "复制整条富文本消息" Scenario；代码块复制正常，说明问题在正文 DOM 序列化器对块级/内联边界及空白文本节点的处理。 |

### 问题 1 证据

- 触发: 点击 toolbar "Copy message"（桌面端 1440×900）。
- 期望: 段落/列表/代码保持边界但不引入多余空行；具名外链以 `文档 (https://example.com/docs)` 内联形式出现。
- 实际粘贴（节选）:
  ```text
  - 第一项：无序列表的基础条目

  - 第二项：包含嵌套子列表

    - 嵌套项一

    - 嵌套项二

  - 第三项：参考
  文档

   或访问
  https://example.com

   以及 /chat
  ```
- 完整证据: `M1-impl/review-r1-evidence/desktop-clipboard-message.txt`
- 补充: 在剥离 CSS 的 Vitest debug 中，具名链接可正确输出 `文档 (https://example.com/docs)`，说明 `im-md-link--external` 的 `display: inline-flex` 是触发块级断行的直接原因；列表项间空行则与 `<li>` 之间的空白文本节点被保留有关。

## Side Findings

- 未观察到 verifier 报告的 `isNativeInteractiveTarget` 在用户面的明显症状：直接对链接元素右键、对气泡空白区域右键均按预期走各自路径。
- 移动端原生文本选择因 headless WebKit 限制，未能在截图中捕获选择柄；但无 IM 自定义菜单劫持，故不单独立 issue。
- 不支持的链接目标（`tel:` / malformed URL）未在真栈旅程中生成样例，依赖单元测试覆盖。
- Branch offline/pending 四种状态在真栈中未全部目视验证，依赖 action model 的一致性实现与既有 fork 测试。

## 验收标准覆盖

### Requirement: 消息正文支持原生文本选择与局部复制 — 组内结论:pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面端复制选中的局部文字 | spec.md | 建立选区后用系统/快捷键复制；脚本确认 IM 未替换剪贴板 | `desktop-selection.png` | pass | 未直接读取剪贴板，但 `contextmenu` 未被阻止，浏览器保留原生能力 |
| 桌面端选中文字后打开右键菜单 | spec.md | 选区内右键，检查 `defaultPrevented === false` | `desktop-selection.png` | pass | 原生菜单保留 |
| 移动端长按选择消息文字 | spec.md | WebKit 390×844 touch 下长按正文，确认无 IM 菜单 | `mobile-body-touch.png` | inconclusive | headless WebKit 未捕获选择柄；无劫持现象，但无法 100% 确认原生选择可用 |

### Requirement: 消息级操作可发现且不干扰阅读 — 组内结论:pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面端按需显示消息操作 | spec.md + prototype | hover 与 keyboard focus 显示 toolbar | `desktop-hover-toolbar.png`, `desktop-focus-toolbar.png` | pass | Copy + Branch 均出现 |
| 桌面端普通气泡右键 | spec.md + prototype | 无选区非原生 target 区域右键 | `desktop-contextmenu.png` | pass | 短菜单含 Copy / Branch / Cancel |
| 链接与正文选区保留原生右键能力 | spec.md | 链接/选区内右键检查 `defaultPrevented` | 日志 | pass | 均为 false |
| 移动端打开消息操作 | spec.md + prototype | 点击 More 打开 action sheet | `mobile-sheet.png` | pass | 44×44 More 按钮，sheet 内容一致 |
| 消息处于普通阅读状态 | spec.md + prototype | 默认无按钮/菜单常驻 | `desktop-reading.png`, `mobile-reading.png` | pass | 阅读密度保持 |

### Requirement: 复制整条消息得到可复用正文并获得反馈 — 组内结论:fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 复制整条富文本消息 | spec.md + design.md fixture | toolbar 点击 Copy message，读取剪贴板 | `desktop-clipboard-message.txt`, `desktop-copy-result.png` | fail | 列表项间多余空行；具名外链被断行 |
| 有选区时仍可明确复制整条消息 | spec.md | 先建立页面选区，再点击 Copy message | `desktop-selection.png` → `desktop-copy-result.png` | pass | 复制的是目标消息，未误用页面选区 |
| 整条复制不混入消息外围信息 | spec.md | 检查剪贴板无头像/时间/token/过程等 | `desktop-clipboard-message.txt` | pass | 仅含正文 |
| 复制成功 | spec.md | 点击复制后观察反馈 | `desktop-copy-result.png` | pass | 显示 "Copied" |
| 复制失败 | spec.md | 无 clipboard 权限时重试 | 第一轮无权限运行日志 / `desktop-copy-result.png`（失败版） | pass | 显示 "Copy failed. Please try again."，页面不跳转 |

### Requirement: 聊天链接按目标自然导航 — 组内结论:pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 打开外部网页链接 | spec.md | 检查 external anchor 有 `target="_blank"` | DOM 检查 | pass | `rel="noopener noreferrer"` 也存在 |
| 打开 IM 内部链接 | spec.md | 检查相对链接无 target | DOM 检查 | pass | `/chat` 为普通 `<a>` |
| 操作外部链接 | spec.md + prototype | hover/focus 时 ↗ 提示、aria-label | `desktop-external-link-hover.png` | pass | 裸 URL 无重复 ↗ |
| 移动端长按外部链接 | spec.md | touch 下长按链接不触发 IM 菜单 | 未单独截图 | inconclusive | 与移动正文长按同理，未观察到劫持 |
| 不支持的链接目标 | spec.md | 检查 `tel:` / malformed 不渲染为可点击链接 | 未生成样例 | not-applicable | 真栈未生成对应内容；依赖单元测试与 policy 测试 |

### Requirement: 代码块支持独立精确复制 — 组内结论:pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 复制单个代码块 | spec.md | 点击代码块 copy 按钮，读取剪贴板 | `desktop-clipboard-code.txt`, `desktop-code-copy-result.png` | pass | 仅复制该块代码，保留空行与缩进，无 fence |
| 键盘操作代码复制 | spec.md | 代码 copy 按钮为真实 `<button>`，可 Tab 聚焦 | `desktop-code-hover.png` | pass | 未直接键盘触发，但元素可聚焦且与 pointer 同入口 |

### Requirement: 消息交互跨设备与输入方式保持一致 — 组内结论:pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 键盘访问消息操作 | spec.md | Tab 访问 toolbar / sheet，检查焦点状态与回焦 | `desktop-focus-toolbar.png`, mobile sheet focus 日志 | pass | toolbar 有 focus ring；sheet 关闭焦点回 More |
| 界面语言保持一致 | spec.md | 检查英文 locale 下新增文案无孤立 `fork` | `desktop-contextmenu.png`, `mobile-sheet.png` | pass | 英文使用 Copy message / Branch from here / Copy code |
| 触控入口易于点击 | spec.md | 检查 More 按钮尺寸 | 日志 `mobile More display: flex box: 44x44` | pass | 不小于 44×44px |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新 — 本 unit 仅涉及 IM 前端，未改动跨包边界。
- [x] `docs/specs/im/`（长青行为契约层）：需要更新 — 本 unit 新增的消息正文选择/复制/链接/代码交互行为应归并到 `docs/specs/im/web-chat-ux.md`，由 orchestrator §7.0 收尾。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。

## 本轮产物

- 验收报告: `docs/changes/feat-484-chat-message-interactions/acceptance.md`
- 真浏览器证据目录:
  - `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r1-evidence/`
  - `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r2-evidence/`
- 自动化采集脚本:
  - `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r1-runner.mjs`
  - `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r2-runner.mjs`

---

# Round 2 — 2026-07-30 (targeted revalidation)

> 复验范围: round 1 issue #1（rich-copy 序列化）+ 受 M2 delta 影响的回归面（context menu 关闭/键盘可达、连续 code copy、链接分类）。
> 工作区状态: unit HEAD + WIP 已并入分支，干净；已重新 `npm ci && npm run build` 并起隔离 e2e 栈（IM port 63036）。

## Verdict

**fail**

**Highest Required Action**: `fix-implementation`

Round 1 报告的列表项空行与具名外链断行问题已修复；但真栈读剪贴板发现 fenced 代码块内容被整个 `.im-code-block` 上的 `data-clipboard-exclude` 排除，导致“复制整条富文本消息”仍不满足 design.md 冻结 fixture。其余回归面均通过。

## 复验发现

### Issue 1 修复验证（Round 1 major）

| 检查项 | R1 状态 | R2 结果 | 证据 |
|---|---|---|---|
| 列表项连续无多余空行 | fail | pass | `r2-desktop-clipboard-message.txt` 中 `- 项目一` / `- 项目二` / `  - 子项 A` 连续 |
| 具名外链内联输出 `label (absolute URL)` | fail | pass | `r2-desktop-clipboard-message.txt` 中 `文档 (https://example.com/docs)` |
| 裸 URL 单次 | fail（被断行） | pass | `r2-desktop-clipboard-message.txt` 中 `https://example.com` 单行 |
| 同源 `/chat` 无追加 | pass | pass | `r2-desktop-clipboard-message.txt` 中 `/chat` 无额外 URL |

### 新增/剩余问题

| # | 严重度 | Regression Relation | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 2 | major | direct | 整条复制时 fenced 代码块内容丢失：`.im-code-block` 容器带有 `data-clipboard-exclude`，序列化器跳过整个代码块，仅保留前后说明文字。与 design.md 边界图（仅 copy button / link indicator 应被排除）及 rich-copy fixture（含 code block 内容）矛盾。 | fix-implementation | 仍直接违反“复制整条富文本消息”Scenario；应仅对代码复制按钮加 `data-clipboard-exclude`，保留 `pre > code` 内容。 |

### 回归面验证

| 回归面 | 结果 | 证据/日志 |
|---|---|---|
| Context menu Escape 关闭 | pass | `context menu after Escape: false`；焦点回到气泡 DIV |
| Context menu 外部点击关闭 | pass | `context menu after outside click: false` |
| Toolbar 默认态键盘可聚焦 | pass | computed `display: flex`（非 `none`）；连续 13 次 Tab 可聚焦到 Copy 按钮 |
| 连续两次 code copy 均生效 | pass | block 0 length 51，block 1 length 18，两次均提示 Copied |
| 具名外链/裸 URL/同源链接分类 | pass | named external `target="_blank"`；raw URL `target="_blank"`；same-origin `/chat` `target=null` |
| Hybrid toolbar + More 共存 | pass | `r2-hybrid-hover-toolbar.png`, `r2-hybrid-sheet.png` |
| Mobile More sheet + 焦点陷阱 | pass | `r2-mobile-sheet.png`；Tab 后焦点在 Copy 按钮；Escape 关闭 |

## 覆盖表更新

### Requirement: 复制整条消息得到可复用正文并获得反馈 — 组内结论:fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 复制整条富文本消息 | spec.md + design.md fixture | toolbar 点击 Copy message，读取剪贴板 | `r2-desktop-clipboard-message.txt`, `r2-desktop-copy-success.png` | fail | R1 的列表/链接问题已修复，但 fenced 代码块内容丢失（Issue #2） |
| 复制成功 | spec.md | 点击复制后观察反馈 | `r2-desktop-copy-success.png` | pass | 仍显示 "Copied" |
| 有选区时仍可明确复制整条消息 | spec.md | 未在 R2 复测；继承 R1 pass | R1 证据 | pass | 未回归 |
| 整条复制不混入消息外围信息 | spec.md | 检查剪贴板无头像/时间/token/过程等 | `r2-desktop-clipboard-message.txt` | pass | 仍仅含正文 |
| 复制失败 | spec.md | 未在 R2 复测；继承 R1 pass | R1 证据 | pass | 未回归 |

其余 Requirement 继承 R1 结论不变。

## 上层文档同步（Round 2）

- [x] `SPEC.md`：无需更新。
- [x] `docs/specs/im/`：仍建议由 orchestrator §7.0 归并；新增 Issue #2 行为增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。

## 本轮产物（Round 2）

- 追加验收段落: `docs/changes/feat-484-chat-message-interactions/acceptance.md`
- 真浏览器证据目录: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r2-evidence/`
- 自动化采集脚本: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r2-runner.mjs`

---

# Round 3 — 2026-07-30 (targeted revalidation)

> 复验范围: round 2 issue #2（整条复制丢失代码块）修复 + R2 后 delta（`d4a274349` 整条复制保留代码块、`8c22b5e6e` ContextMenu onClose 引用与 roving 覆盖 aria-disabled）触及的回归面（整条复制全要素、context menu 打开/键盘 roving/关闭/回焦、Branch 激活、阅读态）。
> 工作区状态: unit HEAD `8c22b5e6e`，干净；重新 `npm run build`（bundle `index-DKuwunzo.js`，grep 命中 `data-clipboard-exclude` / `Copy failed` / `opens in new tab` marker）并重启隔离 e2e 栈（IM port 54488，Gateway auto-bind，4 agent online）。

## Verdict

**fail**

**Highest Required Action**: `fix-implementation`

Round 2 报告的代码块整体丢失已修复：两个 fenced 代码块内容均进入剪贴板、无 copy 按钮符号、缩进保留；context menu 全部回归面通过。但真栈读剪贴板发现**代码块内部空行被折叠**（原始两个空行粘贴后剩一个），违反 design.md 冻结的 rich-copy fixture（"code 内部空行不折叠"），"复制整条富文本消息" Scenario 仍不能判 pass。

## 复验发现

### Issue 2 修复验证（Round 2 major）

| 检查项 | R2 状态 | R3 结果 | 证据 |
|---|---|---|---|
| 整条复制包含 fenced 代码块内容 | fail（整体丢失） | pass | `r3-desktop-clipboard-message.txt` 含 `def hello():` 与 `echo "done"` 两段代码 |
| 不混入 copy 按钮符号 | fail | pass | 剪贴板无 `⎘` |
| 代码缩进保留 | fail | pass | `    return "world"` 四空格缩进在 |
| 独立代码块复制 | pass | pass | `r3-desktop-clipboard-code.txt` 仅含该块代码、内部两个空行完整保留、无 fence |
| R1 修复不回退（列表连续/具名链接内联/裸 URL 单次/同源无追加） | pass | pass | `r3-desktop-clipboard-message.txt` 逐项核对 |

### 新增问题

| # | 严重度 | Regression Relation | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 3 | major | direct | 整条复制时 fenced 代码块**内部空行被折叠**：agent 原始回复第一个代码块内为 `def hello():` + 两个空行 + `    return "world"`，粘贴结果只剩一个空行（od 字节级确认 `\n\n\n` → `\n\n`）。同一条消息的独立代码块复制则完整保留两个空行。 | fix-implementation | 直接违反 design.md 决策 3 "code block 保留内部换行和缩进；只规整正文块之间的多余空行" 与冻结 fixture "code 内部空行不折叠"（`if (ready) {` 后空行原样保留），及 M1-R3 逐字符匹配要求。独立代码复制路径正确，说明问题在整条复制序列化对 code block 内部空白的规整越界。历史脉络：R1 剪贴板中代码块内容整体缺失（当时未抓到）、R2 抓整体丢失、修复后本轮暴露内部空行层——同一 rich-copy 保真问题的第三层，design 契约本身明确无矛盾，属实现未达契约。建议 fix worker 本轮对 fixture 的 code 保真整段对齐并真栈自证，而非再修单点。 |

### Issue 3 证据

- 触发: toolbar "Copy message"（桌面端 1440×900，granted clipboard 权限）。
- 期望: 代码块内部两个空行原样保留（与独立代码复制一致）。
- 实际: `r3-desktop-clipboard-message.txt` 第 17-19 行 `def hello():` / 单个空行 / `    return "world"`（od 确认 `def hello():\n\n    return`）；对照 `r3-desktop-clipboard-code.txt`（独立复制）为 `def hello():\n\n\n    return`（两个空行）。
- agent 原始回复: 会话 `8ea103f32c3f4b6cb66ea50dcac37d82`，` ```python ` 块内确为两个空行。

### 回归面验证（R2 后 delta 触及面）

| 回归面 | 结果 | 证据/日志 |
|---|---|---|
| 右键普通区域开 IM 菜单（Copy message / Branch from here / Cancel） | pass | `r3-contextmenu-open.png`；Branch `aria-disabled="false"`（eligible） |
| 菜单键盘 roving（ArrowDown / Home / End） | pass | ArrowDown Copy→Branch；End→Cancel；Home→Copy message |
| Escape 关闭菜单 + 焦点回气泡 | pass | 日志 `menu visible after Escape: false`，activeElement 为气泡 DIV |
| 外部点击关闭菜单 | pass | 日志 `menu visible after outside click: false` |
| 键盘 Enter 激活 Copy → 菜单关闭 + Copied 反馈 + 回焦 + 剪贴板写入 | pass | `r3-keyboard-copy-result.png`；日志各项 true |
| 指针点击激活 Copy → 菜单关闭 + Copied 反馈 | pass | `r3-pointer-copy-result.png` |
| 菜单激活 Branch from here → fork 跳转新会话 | pass | 日志 URL `8ea103…` → `94ed83…`，`r3-branch-result.png` |
| 阅读态干净无常驻按钮 | pass | `r3-desktop-reading-clean.png`（mouse 驻留远处时气泡无 toolbar） |
| 复制成功反馈 | pass | `r3-desktop-copy-success.png` / `r3-keyboard-copy-result.png` 显示 "Copied" |
| 整条复制不混入外围信息 | pass | 剪贴板无头像/发送者/时间/Process/thinking/token/投递状态 |

> 注: `r3-desktop-reading.png` 中气泡 toolbar 隐约可见，经 `r3-reading-state-probe.mjs` 证实为探针 mouse 坐标残留（登录页 Sign in 点击位置恰好落在气泡上）造成的 hover 态，非产品问题；mouse 移开后阅读态干净（`r3-desktop-reading-clean.png`）。

## 覆盖表更新

### Requirement: 复制整条消息得到可复用正文并获得反馈 — 组内结论:fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 复制整条富文本消息 | spec.md + design.md fixture | toolbar 点击 Copy message，读取剪贴板 | `r3-desktop-clipboard-message.txt`, `r3-desktop-clipboard-code.txt` | fail | R1 列表/链接、R2 代码块丢失已修复；代码块内部空行被折叠（Issue #3） |
| 复制成功 | spec.md | 点击/键盘激活复制后观察反馈 | `r3-desktop-copy-success.png`, `r3-keyboard-copy-result.png` | pass | "Copied" 反馈，菜单 action-close，焦点回气泡 |
| 有选区时仍可明确复制整条消息 | spec.md | 未在 R3 复测；继承 R1 pass | R1 证据 | pass | 未回归（delta 不触及选区路径） |
| 整条复制不混入消息外围信息 | spec.md | 检查剪贴板无头像/时间/token/过程等 | `r3-desktop-clipboard-message.txt` | pass | 仍仅含正文 |
| 复制失败 | spec.md | 未在 R3 复测；继承 R1 pass | R1 证据 | pass | 未回归 |

### Requirement: 消息级操作可发现且不干扰阅读 — 组内结论:pass（R3 复验加强）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面端普通气泡右键 | spec.md + prototype | 无选区普通区域右键 | `r3-contextmenu-open.png` | pass | 短菜单三项，含 eligible Branch |
| 消息处于普通阅读状态 | spec.md + prototype | mouse 远离气泡观察默认态 | `r3-desktop-reading-clean.png` | pass | 无 toolbar 常驻；代码块 copy 按钮常驻与 R1 结论一致 |
| 桌面端按需显示消息操作 | spec.md + prototype | 继承 R1/R2 pass（delta 不触及 hover/focus 触发） | R1/R2 证据 | pass | 未回归 |
| 链接与正文选区保留原生右键能力 | spec.md | 继承 R1/R2 pass（delta 不触及） | R1/R2 证据 | pass | 未回归 |
| 移动端打开消息操作 | spec.md + prototype | 继承 R2 pass（delta 不触及 sheet 路径） | R2 证据 | pass | 未回归 |

### Requirement: 消息交互跨设备与输入方式保持一致 — 组内结论:pass（R3 复验加强）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 键盘访问消息操作 | spec.md | roving/Home/End/Escape/Enter 激活/回焦全链路 | 探针日志 + `r3-keyboard-copy-result.png` | pass | 菜单关闭后焦点回气泡；Branch eligible 可激活 |
| 界面语言保持一致 | spec.md | 继承 R1 pass（delta 不触及文案） | R1 证据 | pass | 未回归 |
| 触控入口易于点击 | spec.md | 继承 R1 pass（delta 不触及） | R1 证据 | pass | 未回归 |

其余 Requirement 继承 R1/R2 结论不变。两条移动端长按 Scenario（`移动端长按选择消息文字`、`移动端长按外部链接`）自 R1 起为 `inconclusive`（headless WebKit 无法捕获系统选择柄），本轮 targeted 未跑 WebKit 矩阵，继续继承——**下一轮复验须用真 WebKit/真机手测关闭这两条，否则即使 Issue #3 修复也无法给 pass**。

## 上层文档同步（Round 3）

- [x] `SPEC.md`：无需更新。
- [x] `docs/specs/im/`：仍建议由 orchestrator §7.0 归并；新增 Issue #3 行为增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。

## 本轮产物（Round 3）

- 追加验收段落: `docs/changes/feat-484-chat-message-interactions/acceptance.md`
- 真浏览器证据目录: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r3-evidence/`
- 自动化采集脚本: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r3-runner.mjs` 及 `r3-contextmenu-probe.mjs` / `r3-copy-activate-probe.mjs` / `r3-branch-probe.mjs` / `r3-reading-state-probe.mjs`（运行副本置于 `src/IM/frontend/` 下以解析 playwright）
