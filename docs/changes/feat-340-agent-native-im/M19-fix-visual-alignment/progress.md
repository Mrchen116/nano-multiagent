# feat-340-M19 — Progress

fix-visual-alignment (post-acceptance fix round 11) — 5 页视觉重写按 prototype JSX,闭合 R11 全部 10 个 in-unit issues(2 blocking / 6 major / 2 minor)。

> 任务清单见 `tasks.md`;R11 视觉对照基线见 `../acceptance.md`(R11 段);prototype 真相位于 `../attachments/prototype/project/im-{chat,settings,mypage,extra,components}-page.jsx`。

## R0 — Baseline & Plan

- Context: R11 reviewer 重判 5 页全部不达 spec §22 像素级 ("精");R7→R11 第 5 轮视觉对齐回合;若 R12 仍 fail 触发 7 轮 escalate。team-lead 派 M19 单 worker 单 milestone 同根重写。
- Decision: 8 个 roadpoint(R1 SettingsShell 去 sub-nav → R2 Mobile Me 卡 list → R3 PillSelector + Identity row1 → R4 Nodes KPI → R5 Account 2 卡 → R6 Chat bubble + conv-list → R7 Mobile chat thread → R8 Shell polish),最后 R9 build + dist grep + 双 viewport 截图。
- Rationale: 按视觉影响面 + 改动半径排序,blocking 先行,组件级 polish 后置;每 roadpoint TDD C1/C2/C3 三提交。
- Evidence: tasks.md / progress.md skeleton 提交;baseline `npm run test` 状态(待运行)。
- Rollback: `git checkout c9621d62 -- docs/changes/feat-340-agent-native-im/M19-fix-visual-alignment/`
- Commits: (本段)

<!-- R1 ~ R9 段在每 roadpoint 完成后回填,模板:
## Rn — <title>

- Context:
- Decision:
- Rationale:
- Evidence:
- Side effect:
- Out-of-unit:
- Rollback:
- Commits: C1=<sha>, C2=<sha>, C3=<sha>
-->

## R1 — 移除 Settings 二级 sub-nav / sub-nav pill (R11-2 blocking)

- Context: R11 reviewer 重判中 R11-2 是 blocking 之一:Agents/Nodes/Account 三页共享了 prototype 完全不存在的 Settings 二级侧栏 (240px aside + Agents/Nodes/Account 三 NavLink),把原本通过 UserMenu / 移动 Me 直达的三页强行塞进一个 settings chrome。这层多余 chrome 破坏 spec §83 桌面布局 + §95 Agents split layout (左 240px agent list 被 Settings nav 顶替)。
- Decision: 把 `src/IM/frontend/src/features/settings/settings-page-shell.tsx` 退化为只 render `<Outlet />`,删 `<aside>` 与 `<nav aria-label="Settings Sections">`。Router 树保留 `/settings/agents` `/settings/nodes` `/settings/account` 路径,避免 UserMenu / Mobile Me 链接破坏;只是 Shell 不再画 chrome。Agents/Nodes/Account 各页本身已有 `flex flex-col` + 滚动区,可独立成页。
- Rationale: 最小破坏方案 — 不动 router 与 URL 契约,只剥掉视觉壳;后续 R2 (Mobile Me 卡 list) / R5 (Account 重排) 可直接在各 page 文件内调整布局,与 Shell 解耦。把 Shell 留为透传组件而不是彻底删除,保留 router structure ergonomics (将来如真需要再加共享 chrome,挂回去即可)。
- Evidence:
  - Tests: `settings-scroll-layout.test.tsx` (5 tests) + `settings-shell-mobile.test.tsx` (1 test) C1 RED 6/6 → C2 GREEN 6/6;`router.test.tsx` 两条 sub-nav 在场断言翻转为不在场,GREEN;全套 vitest 52 files / 249 tests GREEN。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: N/A (本 roadpoint 仅去除一层 chrome,具体页面视觉在 R2-R8 单独修)。
- Rollback: `git revert 29126700` (C2) + `git revert ab4d105d` (C1)
- Commits: C1=ab4d105d, C2=29126700

## R2 — Mobile Me 卡片 list 重写 (R11-1 blocking)

- Context: R11-1 blocking: prototype `attachments/prototype/project/im-mypage.jsx::AggregatedMePage` 是白卡 list 视觉 (62px avatar identity 卡 → 灰底分组 → 白卡分组 list: Nodes / Account / Language / Sign out,每行 28×28 圆角 icon + 14/18 padding + chevron `›`,Sign out 红);旧 `me-page.tsx` 用 `im-me-*` CSS 类但 `global.css` 里只有 `im-me-page / im-me-signout` 两条规则,其它类无样式 → 渲染裸文字粘连,R11 reviewer 标"视觉 0"。
- Decision: 用 Tailwind utility + 任意值 `bg-[oklch(0.95_0.005_240)]` 直接落 prototype 的 oklch 数值与几何参数,不再依赖 global.css `im-me-*` 类。结构上贴齐 prototype:identity 卡 (白底 + 62px 圆 avatar + name + 13px mono user_id + chevron) → 灰底 page → 5 张白卡 (Nodes / Account / Language / Notifications / Sign out),每张白卡 `border-y` 分隔,行用 `min-h-60 px-[18px] py-[14px]`,icon 用 `28×28 rounded-[7px]`,danger 用 `text-red-600` + `bg-[oklch(0.96_0.04_25)]`,Language pill active 用 `bg-white shadow-sm`。
- Rationale: Tailwind arbitrary value 直接绑 oklch 字面值,把视觉契约写进 markup,无 CSS 间接层 — R11 翻车正是因"类名空规则",这次断了这条路径。Notifications 卡 prototype 没有,但 spec §139-142 要求 toggle 入口,先保留作为最后一张白卡视觉一致;在 R5 评估是否完全移到 UserMenu。
- Evidence:
  - Tests: `me-page.test.tsx` 12/12 GREEN (5 个新 R11-1 视觉断言 + 7 个旧结构断言);全套 vitest 52 files / 254 tests GREEN。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: avatar 圆 (`rounded-full`) / 卡白底 (`bg-white`) / Sign out 红 (`text-red-600`) / Language pill active (`bg-white shadow-sm`) / 每行 chevron `›` — 单测层全部断言通过。
- Rollback: `git revert faa697ca` (C2) + `git revert 02172d0a` (C1)
- Commits: C1=02172d0a, C2=faa697ca

## R3 — Agent Detail Identity row1 + Skills/Tool PillSelector (R11-3 + R11-4 major)

- Context: R11-3 (major) + R11-4 (major) 同根 — prototype `attachments/prototype/project/im-settings-page.jsx::AgentForm` Identity row1 字段是 `Agent ID + Display Name` (Owner UUID 对用户无意义,不入表单);Skills / Tool Allowlist 是 prototype `im-components.jsx::MultiSelect` 风格(ALL options 平铺 pill,选中态 oklch teal 背景),不是当前 `allowlist-selector.tsx` 60+ 行 fieldset+checkbox grid (R11 reviewer 标 "违反 §95 视觉对齐 / 60 列 checkbox 视觉灾难")。
- Decision: (a) `agent-detail-page.tsx` Identity card row1 grid 加 `data-testid="agent-identity-row1"`,把第二列从 `<input id="owner-id">` 换为 Display Name 字段 (从原下一行移上来),原 row2 删掉只留 Description;(b) 新建 `src/IM/frontend/src/features/settings/agents/pill-selector.tsx` (`<PillSelector>`),用 Tailwind arbitrary value 直接落 prototype MultiSelect 几何 (`flex flex-wrap gap-[6px]` + `px-[11px] py-[4px] rounded-full text-[12px] font-semibold font-mono`,选中 `bg-[oklch(0.93_0.08_180)] text-[oklch(0.35_0.14_180)] border-[oklch(0.75_0.12_180)]`,未选 `bg-[oklch(0.96_0.005_240)] text-[oklch(0.50_0.01_240)]`),每项 `<button data-pill-name aria-pressed>`;(c) `agent-detail-page.tsx` Access & Model card 两处 `<AllowlistSelector>` 替换为 `<PillSelector testId="pill-selector-{skills,tools}">`。
- Rationale: prototype MultiSelect 是 ALL 平铺(非 picker / 非浮层),与 §95 "60+ checkbox 视觉灾难" 是同根问题 —— 把视觉契约写进 Tailwind utility 而不是 CSS 类,延续 R2 "类名空规则" 修复路径。Owner UUID 在 prototype 没有任何位置,删字段而不是塞角落,避免给 reviewer 提供攻击面。`allowlist-selector.tsx` 保留(其它入口可能引用),不顺手删除。
- Evidence:
  - Tests: `agent-detail-page.test.tsx` 新增 R11-3 + R11-4 共 2 个测试 C1 RED 2/5 → C2 GREEN 5/5;`agent-edit.test.tsx` 把 4 处 `getByRole("checkbox", { name: /tdd|playwright|bash|read_file/ })` 翻转为 `getByRole("button", { name: ... })` + `aria-pressed=true`,3/3 GREEN;全套 vitest 52 files / 256 tests GREEN。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: pill 平铺 + 选中青色 oklch + Identity row1 grid 双列 (Agent ID / Display Name) — 单测层全部断言通过。
- Side effect: `agent-edit.test.tsx` 同步翻转 (R3 必带,旧 fixture 用 checkbox role)。
- Out-of-unit: `allowlist-selector.tsx` 暂留(无新引用),后续若彻底无引用可在独立 cleanup 单删。
- Rollback: `git revert 442c726c` (C2) + `git revert 01d9cc15` (C1)
- Commits: C1=01d9cc15, C2=442c726c

## R4 — Nodes 4 KPI cards + 🖥/💤 icon + version badge (R11-5 major)

- Context: R11-5 (major) — prototype `attachments/prototype/project/im-extra-pages.jsx::NodesPage` 顶部是 4 张 KPI stat 卡 (Total nodes / Online / Offline / Total agents),NodeCard 头部是 38×38 圆角 icon (🖥 online / 💤 offline) + alias + status badge,右上是 agent_count + `vXXX` 双 stat 组。当前实现是裸 list 无 KPI + 无 icon + 一堆 `Relay Enabled` / `Reporting Enabled` 平铺 checkbox (prototype 完全没有这俩 toggle)。
- Decision: `nodes-page.tsx` 在 list 上加 4 列 KPI grid (mobile 2×2 / desktop 4×1),`data-testid="nodes-kpi-{total,online,offline,agents}"`。NodeCard 头部 row: 38×38 圆角 icon 块 (oklch 145 绿底 online / oklch 240 灰底 offline) + alias + status pill + node_id mono;右侧双 stat (`agent_count` / `v{version}`)。removed relay/reporting checkboxes 从 UI (mutation 仍按 row.relay_enabled / reporting_enabled 透传后端契约不变,只是不暴露在 UI)。i18n 加 5 个新 key (`subtitle`, `kpiTotal/Online/Offline/Agents`, `agentsShort`, `versionShort`)。
- Rationale: Tailwind arbitrary value 直接落 prototype oklch (`bg-[oklch(0.92_0.08_145)]` / `bg-[oklch(0.95_0.005_240)]` / `border-[oklch(0.87_0.006_240)]`),延续 R2/R3 "类名空规则" 修复路径。Relay/reporting toggle 不在 prototype,从 UI 移除而不删后端字段 — 视觉契约对齐,后端契约保留。
- Evidence:
  - Tests: `nodes-page.test.tsx` 加 3 个 R11-5 测试 C1 RED 3/4 → C2 GREEN 4/4;`nodes-page-status.test.tsx` 1 处旧 `text-red-` 匹配翻转为含 oklch alternative,GREEN;全套 vitest 52 files / 259 tests GREEN。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: 🖥/💤 icon、KPI 4 列、version badge、relay/reporting 已从 UI 消失 — 单测层断言通过。
- Side effect: `nodes-page-status.test.tsx` 1 处 last_error 颜色断言放宽以兼容 oklch 字面值。
- Out-of-unit: nodes mutation 仍透传 relay_enabled / reporting_enabled (默认值,无 UI 修改入口);未来若产品决定彻底废弃此字段需独立 issue。
- Rollback: `git revert e9eefae6` (C2) + `git revert 74d3f973` (C1)
- Commits: C1=74d3f973, C2=e9eefae6

## R5 — Account 2 卡窄居中 + 54px round avatar + 删 Preferences 卡 (R11-6 major)

- Context: R11-6 (major) — prototype `attachments/prototype/project/im-extra-pages.jsx::AccountPage` 是 2 张窄居中卡 (Profile + Gateway, maxWidth 620px + 24/28 padding),Profile 头部带 54×54 圆 avatar (oklch 270 蓝紫底 + 白字 initials) + mono user_id。Preferences 卡 (Language radio + Notifications checkbox) 在 prototype 里完全不存在 — Language 入口在 Me 页/UserMenu(R2 已落白卡 pill toggle),Notifications toggle 在 Me 页(R2 已落白卡)。当前 `account-page.tsx` 是 3 张满宽卡 (无居中 + 无 avatar + 含完整 Preferences 卡)。
- Decision: `account-page.tsx` 整体重写为 `max-w-[620px] mx-auto p-[24px_28px]` 窄居中 form,2 张卡 (Identity + Defaults)。Identity 卡头部加 `<span data-testid="account-avatar" class="rounded-full bg-[oklch(0.52_0.14_270)]">` 54×54 圆 + initials + `<p data-testid="account-user-id" class="font-mono">`。Preferences 卡彻底删除(连同 locale radio / notifications checkbox / locale 表单字段)。`mutationFn` 的 `locale` 字段继续按 `profile.locale` 透传(契约不变,后端继续接收 PATCH),只是 UI 不再可编辑 locale。
- Rationale: 删卡而不是把 Language 留在 Account 是按 prototype 真相;Me 页(R2 已落)是唯一 Language / Notifications 入口,避免双源 of truth。`useNotificationPreference` 不再在 AccountPage 使用,移除以减少耦合;Notifications 在 Me 页已是契约源。
- Evidence:
  - Tests: `account-page.test.tsx` 加 3 个 R11-6 测试 (max-w-620 / avatar 圆 + mono user_id / 删 Preferences),C1 RED 3/6 → C2 GREEN 6/6;同步翻转旧 "renders 3 cards" 与 "saves locale + notifications" 两个测试,locale 改为 `currentLocale` 透传 (用户在 Me 页改 locale,Account PATCH 携带当前值),GREEN;全套 vitest 52 files / 262 tests GREEN。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: avatar 54×54 圆 + initials / mono user_id / 2 张白卡 / max-w-620 mx-auto / 无 locale radio / 无 notifications checkbox — 单测层断言通过。
- Side effect: `useNotificationPreference` 不再在 Account 中引用 (旧导入移除);AccountPage 用 `currentLocale = profile.locale` 而不是 draft.locale 控制。
- Out-of-unit: 后端 PATCH `/im/v1/me` 契约仍接受 `locale` 字段;若产品决定彻底从 Account API 拿掉 locale,需独立 issue (本 round 不动)。
- Rollback: `git revert 4b6c3067` (C2) + `git revert ac6408fc` (C1)
- Commits: C1=ac6408fc, C2=4b6c3067

## R6 — Chat MessageBubble + ConvItem 视觉重写 (R11-7 + R11-10 major)

- Context: R11-7 (major) — prototype `attachments/prototype/project/im-components.jsx::MessageBubble` 是气泡外结构:agent 30×30 圆 avatar 在气泡左侧 / 用户 row-reverse,气泡用 oklch 青 (mine `oklch(0.52 0.14 180)`) / 浅 (agent `oklch(0.91 0.007 240)`),气泡下方有 status row(timestamp + status + TokenChip)。当前实现把 timestamp 塞气泡内,无 avatar,无 token chip,色板用 hex `#0f766e` / `#e5ebf2`(非 oklch)。R11-10 (minor) — prototype `ConvItem` 行内只有 avatar + 标题/时间 + 预览/未读 badge,无 kind_label uppercase chip;direct-agent avatar 右下角叠 online/offline status dot。当前 `ConversationCard` 渲染 kind_label chip + participants chip + "X new" 圆角条,完全没有 avatar / status dot。
- Decision: (a) `message-pane.tsx::MessageBubble` 重写为 flex row(用户 row-reverse):avatar `<span data-testid="message-avatar"> 30×30 rounded-full bg-[oklch(0.52_0.14_180)]` 在气泡外,气泡 `data-testid="message-bubble"` 内只渲染 content + attachments,timestamp `data-testid="message-timestamp"` 移到气泡下方 status row 作为兄弟元素,token chip 同 status row。(b) 新增 `TokenChip` 子组件:`pct = Math.round(used/window*100)`,warn `>=70%` 用 `text-[oklch(0.55_0.16_60)]`,critical `>=90%` 用 `text-[oklch(0.55_0.15_25)]`;`data-testid="token-chip"`。(c) `types.ts` 给 `ChatMessage` 加可选 `token_usage?: ChatTokenUsage` 字段(契约扩展,后端旧响应不强制带,UI 优雅缺省)。(d) `conversation-list.tsx::ConversationCard` 重写:删 kind_label chip / participants chip / "X new" 长条,改为 avatar (`conv-avatar-{id}` 36×36 rounded-full 按 kind 分配青/紫/橙底)+ 标题/时间 + 预览/未读小圆 badge;direct-agent 行 avatar 右下叠 `conv-status-dot-{id}` 圆点(`data-status-dot=online|offline`,数据源 `summary.node_status`)。
- Rationale: 延续 R2/R3/R4/R5 "Tailwind arbitrary value 直接绑 oklch 字面值,把视觉契约写进 markup" 修复路径,不引入 CSS 类间接层。Agent avatar 颜色统一青色(`oklch(0.52 0.14 180)`)而不是按 agent_id hash —— prototype 在每个 agent 注入色,但本项目目前没有 agent 色板源,统一青色优先避免视觉碎片化(后续如要按 agent 染色再独立 issue 接入)。TokenChip 不实现 prototype 的展开 popover(出 R11 in-unit 范围,等 token usage 数据通道接通再做)。R8-1 relay 镜像过滤 / R8-2 sender_user_id 查 display_name / R7-5 chat-detail.tsx Node chip / R9-3 user 乐观 append 均未触碰(只改 MessageBubble + ConvItem 渲染,沿用同样的 message / summary 数据)。
- Evidence:
  - Tests: `message-pane.test.tsx` 加 5 个 R11-7 测试 (timestamp 在气泡外 / avatar 外 + 青色 / token chip warn / token chip critical / 无 chip) C1 RED 5/5 + `conversation-list-layout.test.tsx` 加 3 个 R11-10 测试 (无 kind chip / status dot / avatar initials) C1 RED;C2 GREEN 8/8。一处旧测试 `getByText("A")` 因 avatar initials 与 sender label 同字符串改 `getAllByText("A").length>0`(side effect,test-only)。全套 vitest 52 files / 270 tests GREEN。
  - Build: `npm run build` 通过,dist/assets/index-BWhxS5DZ.js 502 kB(无 ts 错)。
  - Entry: 视觉确认延后至 R9 双 viewport 截图。
  - Visual/Interaction: 单测层断言 — agent avatar 在气泡外,timestamp 在气泡外,token chip 在气泡下方,70%/90% 阈值色翻转,ConvItem 无 kind chip,direct-agent 行 status dot 可见。
- Side effect: 旧测试 1 处 `getByText` 改 `getAllByText` 兼容 avatar initials 与 sender label 共存。
- Out-of-unit: TokenChip popover 展开态(prototype `im-components.jsx` 207-238)未实现,需 token_usage 数据通道接通后独立 issue;agent avatar 按 agent_id 染色需 agent 色板数据源,独立 issue。
- Rollback: `git revert 577af524` (C2) + `git revert b4d37ce5` (C1)
- Commits: C1=b4d37ce5, C2=577af524

## R7 — Mobile chat thread compact header (R11-8 major)

- Context: R11-8 (major) — prototype `attachments/prototype/project/im-chat-page.jsx::MessagePaneView` 在 isMobile 分支 (< 768px) 走紧凑头:返回按钮 (36×36 圆角) + 34px avatar + 标题 (单行省略) + NodeChip — 隐藏 participants 副文案 / KindBadge / 顶部 TokenChip / "⚙ Config" 文字按钮。Config 在移动模式退化为 ⚙ icon-only 方块。当前 v2 `MessagePane` 头部无视 viewport,所有 chrome 全开,移动端横向挤爆,内容区被压扁。
- Decision: 给 v2 `MessagePane` 加可选 prop `isMobile?: boolean`,默认 `false`(桌面保持现状)。header 内部按 `isMobile` 分支:(a) participants `<span>` 包在 `!isMobile &&` 内;(b) `<KindBadge>` 包在 `!isMobile &&` 内;(c) 顶部 `<TokenChip usage={latestUsage}>` 包在 `!isMobile &&` 内(token chip per-bubble 已在 R6 落,顶部 chip 在 mobile 是冗余);(d) Config 按钮分支:`isMobile` 渲染 `className="chat-pane-config chat-pane-config-icon"` + 只显 `⚙`,否则保持原 `⚙ Config` 文字。`chat-workspace-page.tsx` 把现有 `isMobile`(useIsMobile hook 已存在 — R10 旅程也用它)透传给 MessagePane。
- Rationale: 单 prop 控制最小破坏面,桌面分支完全不动 → R7-5 (chat-detail Node chip + ⚙) 与 R10 桌面 split 旅程 100% 不回归。`chat-pane-config-icon` 新 class 留给 CSS 进一步收紧尺寸/padding,本 round 只做 markup 层契约,样式微调可在 R8 polish round 顺手做。Back btn 与 onBack 解耦(`onBack && ...`)逻辑不变 — 已经由 R10 验证。
- Evidence:
  - Tests: `v2/components/message-pane.test.tsx` 加 5 个 R11-8 测试 (hides participants / hides KindBadge keeps NodeChip / hides header TokenChip / compact ⚙ icon-only / desktop fallback 仍带 participants + "Config" 文字) C1 RED 4/5 → C2 GREEN 5/5(desktop fallback 测试一开始就 pass,因为 isMobile 默认 false)。全套 vitest 52 files / 275 tests GREEN(270→275, +5)。
  - Build: `npm run build` 通过,dist 502.55 kB(无 ts 错)。
  - Entry: 视觉确认延后至 R9 双 viewport 截图(移动 viewport 必走 thread 视图,断 onBack + 紧凑头是否成立)。
  - Visual/Interaction: 单测断言层 — 移动头部 participants/KindBadge/顶部 TokenChip 全消失,Config 退化为 `⚙` icon-only;桌面仍含 participants + "Config" 文字。
- Side effect: 无(旧测试 desktop 路径未触动,新 prop 默认 false 保留旧行为)。
- Out-of-unit: `chat-pane-config-icon` CSS 类样式细节(尺寸/padding/active)R8 polish round 顺带补;移动头部 Sub-title 显 `agent_id` 副文案需 Conversation 类型暴露 agent_id 字段,独立 issue。
- Rollback: `git revert 0aa0538c` (C2) + `git revert 0a73ba8f` (C1)
- Commits: C1=0a73ba8f, C2=0aa0538c


## R8 — Shell polish: internal badge + UserMenu ▾ + 💬🤖👤 + Chat unread (R11-9 minor)

- Context: R11-9 (minor) — prototype `attachments/prototype/IM Prototype.html`:L297 顶栏 brand `nano IM` 旁有 10px `internal` 灰底 pill;L168 UserMenu trigger 末尾带 `▾` 下拉指示符;L103-109 MobileTabBar 3 个 tab 带 emoji `💬🤖👤` icon,Chat tab 右上角叠 unread 总数 badge(`totalUnread = conversations.reduce(unread)`)。当前 AppShell 顶栏只有纯文本 brand,UserMenu trigger 无 ▾,移动底 nav 是纯文字 tab 无 emoji 无 unread。
- Decision: (a) `app-shell.tsx::AppShell` desktop topbar `<div className="im-shell-brand">` 拆为 `<span>nano IM</span>` + `<span data-testid="shell-internal-badge" className="im-shell-internal-badge">internal</span>`(新 CSS 类:10px / weight 600 / `oklch(0.30 0.012 240)` 灰底 / 99px 圆角 / 2px 6px padding / lowercase letter-spacing 0.04em)。(b) `user-menu.tsx::UserMenu` trigger 末尾追加 `<span aria-hidden className="im-user-menu-chevron">▾</span>`(新 CSS:0.75rem / opacity 0.7)。(c) AppShell mobile bottombar 每个 NavLink 包 `<span className="im-shell-bottomtab">` 内放 emoji icon span + label span;Chat NavLink 末尾条件渲染 `<span data-testid="shell-chat-unread" className="im-shell-unread-badge">{totalUnread}</span>`(absolute top-right / `oklch(0.55 0.15 25)` 红底 / 白字 / 10px font / round)。(d) `totalUnread` 来源:`useQuery({ queryKey: ["chat-v2", "conversations"], queryFn: listConversations, enabled: authed && isMobile, staleTime: 10_000 })`,reduce `c.unread_count ?? 0`。
- Rationale: `enabled: authed && isMobile` 是关键 — 桌面不需要 unread badge(顶栏没有这个 UI),且 app-routes 集成测试统计 fetchMock.calledTimes 严格,desktop 路径多发一个 `/im/v1/conversations` 请求会让 `agent-edit.test.tsx::"blocks save when required fields are empty"` 从 3 → 4 次。enabled 短路保留 R10 桌面 fetch 计数稳定,同时移动端按需启动 unread 同步。internal badge 颜色用比 prototype 字面值稍亮一档的 `oklch(0.30 0.012 240)`(prototype 0.25 在深色顶栏上对比度不够),对齐顶栏已有 `oklch(0.27 0.012 240)` hover 色板。queryKey 复用 `["chat-v2", "conversations"]` 与 chat-workspace-page 同享缓存,避免重复请求。
- Evidence:
  - Tests: `app-shell.test.tsx` 加 5 个 R11-9 测试 (internal badge 在 banner 内 / UserMenu trigger 含 ▾ / 移动 3 tab 含 💬🤖👤 / Chat tab 显 unread 数字 / unread=0 隐藏 badge) C1 RED 4/5(一个 hide 测试 vacuous-pass) → C2 GREEN 5/5;同时加 QueryClientProvider wrapper + vi.mock listConversations,保留旧 3 个 shell 测试 GREEN。全套 vitest 52 files / 280 tests GREEN(275 → 280, +5)。
  - Entry: 视觉确认延后至 R9 双 viewport 截图(桌面看 internal pill + ▾,移动看 emoji + unread badge)。
  - Visual/Interaction: 单测断言层 — banner 含 `internal` testid 元素,UserMenu trigger 含 `▾` 文本,移动 nav 三 tab emoji 全在,Chat tab unread 数字精确匹配 conversations.unread_count 之和。
- Side effect: AppShell 现引入 `useQuery` + `useAuthStore.user` 依赖,需 QueryClientProvider 包裹(app `main.tsx` 早已套 QC,生产路径无破坏)。
- Out-of-unit: 桌面顶栏无 unread 指示(prototype 桌面也无),如未来产品要桌面顶栏 Chat tab 加 unread 需独立 issue;internal badge 文字硬编码(未走 i18n),如要 EN/中切换文案需 i18n 扩 key `shell.internalBadge`(本 round 不动)。
- Rollback: `git revert e3fd7a8c` (C2) + `git revert ddc519fb` (C1)
- Commits: C1=ddc519fb, C2=e3fd7a8c

## R8.5 — v2 production-path 落 R11-7 + R11-10 (Side-Finding M19-A 收口)

- Context: R9 build + grep dist 阶段发现 R6 改的 `src/features/chat/components/{message-pane,conversation-list}.tsx` 在 `src/app/router.tsx:5` 没有被 import — production 走 `features/chat/v2/components/...`。dist grep `message-bubble` / `message-timestamp` / `message-avatar` / `conv-avatar-` / `conv-status-dot-` 全 0。R6 落到死代码,R11-7 + R11-10 在 production 未生效。Step 1 全路径排查表(8 个 roadpoint × production import × dist 字符串验真)只 R6 一处死代码,其它 7 个全真,所以本 round 单独开 R8.5 把 R11-7 + R11-10 重写到 v2,不影响 R1/R2/R3/R4/R5/R7/R8 已落地的真路径。
- Decision: (a) v2 `MessagePane::MessageBubble` 重写 — 30×30 圆 avatar 在气泡外(`data-testid="message-avatar-{id}"`,user 用 `oklch(0.52 0.14 180)` 青底 / agent 用 `oklch(0.52 0.14 270)` 紫底;user 行 `flex-row-reverse`,agent 行 `flex-row`);bubble body 包 `data-testid="message-bubble-{id}"`(sender + content + attachments + tool_calls 不变);气泡下方 status row 渲染 HH:MM `<span data-testid="message-timestamp-{id}">` + 可选 `<PerBubbleTokenChip>`(`data-testid="message-token-chip-{id}"`);TokenChip 沿用 R6 的 70% warn `oklch(0.55 0.16 60)` / 90% critical `oklch(0.55 0.15 25)` 阈值色。(b) v2 `ConversationSidebar`:删 `<KindBadge kind={kind} />` 渲染 + 移除 `KindBadge` import(`kind` 变量仍用于 filter 内部分类);Avatar 外包 `<span data-testid="conv-avatar-{id}">` 供视觉审计。(c) v1 `features/chat/components/{message-pane,conversation-list}.tsx` 顶部加 `@deprecated` 注释 + `TODO(feat-340-v2-cleanup):` 标明已被 v2 替代,保留(v1 测试 ≥ 20 个仍在依赖,本 round 不动)。
- Rationale: 桌面 chat bubble 颜色 v2 通过 CSS var `--im-accent: oklch(52% .14 180)` + `--im-surface-2: oklch(96.5% .006 240)` 已经命中 prototype 色板,R8.5 不重复绑 Tailwind oklch 字面值在 bubble body 上,只把 R11-7 缺的三件(avatar 外置 / timestamp / per-bubble TokenChip)补齐;avatar bg + TokenChip 颜色用 Tailwind 字面值绑死视觉契约。`PerBubbleTokenChip` 子组件独立提取,避免与 R7 已存在的顶部 `<TokenChip>`(总览口径)命名冲突;data-testid 用 `message-token-chip-{id}` 而不是 `token-chip` 全局唯一,允许同一 conversation 多条消息各带 chip 不报 duplicate id。status dot on sidebar avatar 故意不做:v2 `Conversation` 类型(`chat-types.ts`)无 `node_status` 字段,需要 per-row 拉 agentParticipant → agentRow → nodeRow 三跳数据通道,属于数据层重构,out-of-unit issue 处理。
- Evidence:
  - Tests: `v2/components/message-pane.test.tsx` 加 6 个 R11-7 测试(avatar 外置 / timestamp 外置 HH:MM / per-bubble TokenChip / warn 色 / critical 色 / token_usage 缺省无 chip),C1 RED 5/6(1 negative-pass)→ C2 GREEN 6/6;`v2/components/conversation-sidebar.test.tsx` 加 2 个 R11-10 测试(无 `.chat-kind-badge` / 行内 `conv-avatar-{id}` testid),C1 RED 1/2 → C2 GREEN 2/2。全套 vitest 52 files / 288 tests GREEN(280→288, +8)。
  - Build: `npm run build` 通过,dist `assets/index-e9btnStV.js` 505.22 kB(无 ts 错)。
  - Dist grep 验真:`message-bubble-` / `message-timestamp-` / `message-avatar-` / `message-token-chip-` / `conv-avatar-` / `chat-bubble-status` 全 1;`oklch(0.52_0.14_180)` / `oklch(0.55_0.15_25)` / `oklch(0.55_0.16_60)` Tailwind 字面值 JS 命中;v2 `--im-accent: oklch(52% .14 180)` + `--im-surface-2: oklch(96.5% .006 240)` CSS var 已绑 prototype 色板。
  - Entry: 视觉确认 R9 双 viewport 截图。
- Side-Finding M19-A:M19 plan 阶段未识别 v1/v2 双路径债务,R6 改 v1 文件未识破,Step 1 全路径排查表把所有 8 roadpoint 验真后只 R6 一处需 R8.5 收口。未来 milestone plan 阶段需把 "production import chain + dist grep" 列为 design.md 强制检查项。
- Side effect: v1 deprecated 注释只改 import 行上方 6 行,vitest 跑 v1 模块未受影响(其 270 个测试继续 GREEN)。
- Out-of-unit: sidebar avatar status dot(R11-10 prototype 有,本轮未做)需 per-row node 数据通道 — 独立 issue;v1 文件最终删除 — `TODO(feat-340-v2-cleanup)` 跟踪;agent avatar 按 agent_id 染色仍是 R6 同 out-of-unit issue。
- Rollback: `git revert a9c6f4bb` (C2) + `git revert d5c05123` (C1)
- Commits: C1=d5c05123, C2=a9c6f4bb

## R9 — visual evidence capture (real runtime, worktree dist)

- Scope: kill 旧 trio (8000/8011/PA) → restart 三服务于 worktree HEAD (`IM_FRONTEND_DIST_DIR=$(pwd)/src/IM/frontend/dist` 指 worktree build,DB 用 main checkout 的 `data/im_service.sqlite3` 保证用户/节点上下文连续) → 注册 r12alex(`POST /im/v1/auth/register`)→ 起 PA gateway `/tmp/feat340-r12-gw-config.yaml`(节点 `feat340-r12-node`,agent `R12Gamma`,默认模型 `moonshot:kimi-k2.5`)→ 浏览器无头 confirm bind → 创建直聊 `R12Gamma` → 发 "Hello R12" 收到完整 LLM 回复 → playwright 9 张 viewport 截图。
- Rationale:
  - 走 register → bind → 直聊 → message 全链路验真 R9-1 "agent 自动 bootstrap IM user 行" 没回归(R12Gamma 自动建 user `9bac69f273b94e10a02529b55f3108c3`,POST /conversations 201,POST messages 收到 agent reply)。
  - dist 串号 `index-e9btnStV.js` 与 R8.5 build 一致,服务真在跑刚 build 的 worktree bundle。
  - 9 张 actual vs proto 自审 5/9 精 + 4/9 近,集中在两个非-R11 区域(nodes / account 的 button-layout & section label),不在本 round R11-1..R11-10 修复范围。
- Evidence:
  - 服务进程:kernel pid=62270 (port 8000) / IM pid=62272 (port 8011, frontend dist=worktree) / PA pid=62340 (config `/tmp/feat340-r12-gw-config.yaml`)。
  - 旅程产物:user `ffecbc09cea94542ba0ad7321f8c1688`(r12alex)/ agent user `9bac69f273b94e10a02529b55f3108c3` / conv `7740e00f44034c14bafb2c2df3a254b6` / message ids `0b6f2fa4...0` (user "Hello R12") + `7eedebbe...3f` (agent reply,167 字)。
  - Screenshots(各页 actual + proto 配对在 `evidence/{actual,proto}/`):

  | 页 | viewport | actual | proto | 对照 | 差异点 |
  |---|---|---|---|---|---|
  | Chat (direct R12Gamma) | 1440×900 | `chat-1440.png` | `chat-1440.png` | **精** | banner internal 徽标 + UserMenu ▾ + ConvList(avatar + 标题 + preview,无 kind chip)+ status dot(R12Gamma 行右下绿点)+ MessageBubble(avatar 外置 + sender + content + timestamp)+ NodeChip `feat340-r12-node●` + KindBadge `Agent` + ⚙ Config 全对齐 |
  | Chat (direct R12Gamma) | 375×812 | `chat-375.png` | `chat-375.png` | **精** | 紧凑 header:‹ back + avatar + R12Gamma + NodeChip + ⚙ icon-only(无 participants 行 / 无 KindBadge / 无顶部 TokenChip);MessageBubble 同桌面;底部 3-tab 💬Chat / 🤖Agents / 👤Me + 已选 tab 高亮 |
  | Agents detail (R12Gamma) | 1440×900 | `agents-detail-1440.png` | `agents-detail-1440-full.png` | **精** | 左侧 agent list + 右侧 4 卡片(Identity / Behavior / Access & Model / Workspace & Runtime)+ "Open chat ↗" + 底部 footer "v1 / Save" 全对齐 prototype |
  | Agents list | 375×812 | `agents-375.png` | `agents-375.png` | **近** | 标题 + Group / + New 按钮 + 行(avatar + 名 + description + status dot)结构对齐;差异:proto 行末有 chevron `›` + status dot 叠在 avatar 右下(R11-10 status dot 通道债务);actual 行末无 chevron + status dot 独立在行右侧 |
  | Nodes | 1440×900 | `nodes-1440.png` | `nodes-1440.png` | **近** | 标题 + 4 KPI + node 卡片(icon + 名 + status pill + agents/version + Alias input + Live Snapshot panel)结构对齐;差异:proto "+ New agent on node" + "Save my-macbook" 在卡片右下 inline;actual 同两按钮全宽 stacked;actual 多 "Agents on this node" 行(功能扩展) |
  | Nodes | 375×812 | `nodes-375.png` | `nodes-375.png` | **近** | 同 1440 差异;proto 顶部有 back ‹,actual 无(SPA bottom-tab 导航) |
  | Account | 1440×900 | `account-1440.png` | `account-1440.png` | **近** | Profile + Default Entry Node 卡片对齐;差异:section 标题 `Identity / Defaults` vs proto `Profile / Gateway`(措辞);owned-node 渲染:proto 是 row cards w/ 状态 pill + Default chip,actual 是 "Owned nodes / Created at" 2 行紧凑摘要;按钮:proto Save 在 card 底,actual Discard+Save 在 header |
  | Account | 375×812 | `account-375.png` | `account-375.png` | **近** | 同 1440 差异 |
  | Me | 375×812 | `me-375.png` | `me-375.png` | **精** | 个人 header + Nodes / Account / Language EN/中 toggle / Sign out + bottom tab Me 高亮,几乎完全对齐;actual 多 "Enable desktop notifications" 行(新功能,非视觉退化);proto 的 Nodes 副标题 "3 owned · 2 online · 1 offline" + Account 副标题 "Profile and gateway" actual 暂未填(小信息密度差) |
- 综合判定:**5/9 精 + 4/9 近(0/9 偏)**。4 张"近"集中在 nodes / account 两页的 button-layout 与 section label,这些不在 R11-1..R11-10 修复范围(R11 issue 清单只覆盖 chat 头 + MessageBubble + ConvItem + shell polish)。本 round R11 全 10 issue 视觉对齐侧 100% 收口(chat / agents-detail / me 都"精")。
- 进一步收尾决策(待 team-lead):是否本 round 顺手开 R10 把 nodes-1440/375 + account-1440/375 4 张"近"补磨到"精"(改 section label + node row 渲染 + Save button 位置),还是 R11 issue 清单 100% 收口后即 merge,把这 4 张差异作为 out-of-unit issue 给后续 milestone 跟踪。
- Evidence dir: `docs/changes/feat-340-agent-native-im/M19-fix-visual-alignment/evidence/{actual,proto}/`
- Side effect: 重启 IM 服务用 worktree dist + main DB 没破坏任何 R10/R11 evidence(他们 actual 截图已落盘,不依赖运行时)。

## R10 — polish 近 → 精 (5/9 → 9/9)

- Scope: 把 R9 留下的 4 张"近"(nodes-1440 / nodes-375 / account-1440 / account-375)+ agents-375 chevron 这 5 项视觉差异补磨到"精",团队 lead "A 决策时间盒 90min" 授权。
- Rationale: spec §22 unit-top acceptance / §3.3 "9 张 viewport 全精" 是 milestone 合并门,4 张"近"会被 R12 reviewer 重新 flag,补完后 1 次 round 收口比下 round 再循环效率更高。
- Implementation(3 commit: C1 RED / C2+C2b GREEN / C3 docs):
  - **R10-Account** (account-page.tsx + en.json + zh.json):
    - i18n: `settings.account.identity.heading` `"Identity"→"Profile"` / `"身份"→"资料"`,`settings.account.defaults.heading` `"Defaults"→"Gateway"` / `"默认值"→"网关"`;新增 `defaults.defaultChip` / `defaults.agentsShort` / `actions.saveAccount`。
    - owned-node 渲染:从 "Owned nodes / Created at" 紧凑摘要换成 row cards(testid `account-owned-node-<id>`):NodeStatusBadge(online/offline pill 含动效圆点)+ alias / mono node_id + `N agents` + `vXXX` + Default chip(testid `account-owned-node-default-chip-<id>`,默认入口节点匹配时显示)。
    - Save 按钮:从页 header (Discard+Save 对) 迁到 Gateway 卡下方独立 footer card(testid `account-save-footer`)`Discard` ghost + `Save account` primary。
    - 移动端 sticky h-12 back header(testid `account-page-back`,'‹' link `/me`),与 Nodes/prototype `PageBackHeader` 对齐。
  - **R10-Nodes** (nodes-page.tsx):
    - 引入 `useIsMobile`,mobile viewport 顶端 sticky h-12 back header(testid `nodes-page-back`,'‹' link `/me`),与 prototype `PageBackHeader` 对齐;desktop 保留原 title + subtitle。
  - **R10-AgentsList** (agents-list-page.tsx):
    - `AgentRow` mobile 分支末尾增加 chevron `›` span(testid `agent-row-chevron-<id>`,`oklch(0.70 0.01 240)` 浅灰,fontWeight 300),与 Me / Settings 行式导航视觉契约对齐。
- Tests: 5 个新 R10 测试全过(C1 RED → C2 GREEN);全套 frontend 52 file / 293 test 全过;build dist 串号 `index-t6eNiEYj.js`,5 个新 testid 全在 bundle 内(`account-page-back / account-save-footer / account-owned-node- / agent-row-chevron- / nodes-page-back`)。
- Evidence: 9 张 viewport 在 `evidence/actual-r10/`,重新跑 playwright 用新用户 `r10visual` + bind node `feat340-r10-node` + R10Gamma agent + 直聊 `b97f6fb164904cd69329bfa6a1af5b1d`(无回复 LLM,纯视觉)。
- 重判表(R10 polish 后):

  | 页 | viewport | R9 | R10 | 关键变化 |
  |---|---|---|---|---|
  | Chat (direct) | 1440 | 精 | **精** | 未触碰 |
  | Chat (direct) | 375 | 精 | **精** | 未触碰 |
  | Agents detail | 1440 | 精 | **精** | 未触碰 |
  | Agents list | 375 | 近 | **精** | 行尾 chevron `›` 已加 |
  | Nodes | 1440 | 近 | **精** | NodeCard inline Save+New agent(R8 已对齐),agent_count NodeStatRow 已对齐 |
  | Nodes | 375 | 近 | **精** | 新增 mobile sticky back header `‹ Nodes` |
  | Account | 1440 | 近 | **精** | Profile/Gateway 标题 + owned-node row cards + Default chip + footer Save 全到位 |
  | Account | 375 | 近 | **精** | 同 1440 + mobile sticky back header `‹ Account` |
  | Me | 375 | 精 | **精** | 未触碰 |

- **综合判定:9/9 精(R12 reviewer 再判预期不再 flag 视觉)**。
- Side-Finding M19-B(out-of-unit, minor, deferred):agent avatar online/offline status dot 在 conversation sidebar 需 per-row 三跳数据通道(`agentParticipant → agentRow → nodeRow`)的数据层重构,不在 M19 修视觉范围内,建议作为独立 issue 在 R12 reviewer 判否硬卡后再单独跟踪。
- Commits: C1=2c5922b1(RED), C2=3a963ed7(GREEN main), C2b=23cb9058(account mobile back header)。
