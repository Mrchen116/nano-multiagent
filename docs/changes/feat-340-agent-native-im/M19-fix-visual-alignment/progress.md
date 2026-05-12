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
