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
- 真浏览器证据目录: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r1-evidence/`
- 自动化采集脚本: `docs/changes/feat-484-chat-message-interactions/M1-impl/review-r1-runner.mjs`
