# feat-340-M19: fix-visual-alignment — Tasks

> 对齐: ../design.md Milestone 表 M19 行 + ../acceptance.md R11 段(2026-05-12)

## 目标

R11 reviewer 重判 5 页全部不达 spec §22 像素级 ("精"):0 精 / 1 近 (Chat 桌面) / 9 viewport 偏。本 milestone 同根重写 5 页视觉,**按 prototype JSX (`attachments/prototype/project/im-{chat,settings,mypage,extra,components}-page.jsx`) 为唯一视觉真相**。R7→R11 已第 5 轮,M19 R12 再 fail 触发 7 轮 escalate。

闭合 R11 全部 10 个 in-unit issues:

- (R11-1 blocking) Mobile Me 页 0 视觉 → 按 `im-mypage.jsx` AggregatedMePage 重写为卡片 list
- (R11-2 blocking) Agents/Nodes/Account 共有的 Settings 二级侧栏 / sub-nav pill → 移除,改 UserMenu / 移动 Me 直达
- (R11-3 major) Skills/Tool Allowlist 60+ checkbox grid → PillSelector
- (R11-4 major) Identity row1 Agent ID + Owner(UUID) → Agent ID + Display Name
- (R11-5 major) Nodes 缺 4 KPI 卡 + 🖥 icon + version 大字 + Relay/Reporting 文本暴露
- (R11-6 major) Account 3 卡全宽 → 2 卡窄居中 + avatar 圆 + 删 Preferences 卡 + Language 回 UserMenu
- (R11-7 major) Chat 缺 bubble timestamp + token chip 移气泡下 + 70/90% 预警 + 统一青色 avatar
- (R11-8 major) Mobile Chat 无专用 thread 视图 → 紧凑 chat header + 全屏消息流
- (R11-9 minor) `internal` 徽标 + UserMenu ▾ + 底部 tab emoji + unread badge
- (R11-10 minor) 会话列表移除 "Agent" kind badge + avatar online/offline 圆点

## 退出标准

- [ ] R11-1 / R11-2 两 blocking 视觉项消除 (5 页双 viewport 截图对照)
- [ ] R11-3 ~ R11-8 六 major 视觉项消除
- [ ] R11-9 / R11-10 两 minor 视觉细节到位
- [ ] `cd src/IM/frontend && npm run build` 成功
- [ ] grep `dist/assets/*.js` 验关键修复进 bundle(`internal` 徽标 / `append_optimistic` 沿用 M18 / pill selected 类名 / KPI 卡文案 / Mobile Me 卡 class / bubble timestamp 格式)
- [ ] 每页桌面 1440x900 + 移动 375x812 双 viewport 截图,放 `M19-fix-visual-alignment/progress.md` Evidence 段(prototype-vs-actual 并排)
- [ ] vitest `cd src/IM/frontend && npm run test` 全绿
- [ ] **无后端代码改动**(spec/design 不变,只动 `src/IM/frontend/`)
- [ ] **无 spec §22 自降**(标准沿用,只补实现)

## 测试策略

| 改动点 | 测试 |
|---|---|
| R11-1 Mobile Me 卡片 list | vitest `me-page.test.tsx` 新增 "render aggregated card list with chevron + danger Sign out + Language pill toggle" |
| R11-2 移除 Settings 侧栏 | vitest 重写 `settings-page-shell` 或 router 测试:`/settings/agents` 不渲染 sub-nav |
| R11-3 PillSelector | vitest `allowlist-pill-selector.test.tsx` 新增 "render selected as pills + open picker + multi-select" |
| R11-4 Identity row1 | vitest `agent-detail-page.test.tsx` 新增 "row1 显示 Agent ID + Display Name 不显示 Owner UUID" |
| R11-5 Nodes KPI | vitest `nodes-page.test.tsx` 新增 "render 4 KPI cards (Total/Online/Offline/Total agents) + node icon" |
| R11-6 Account 2 卡 | vitest `account-page.test.tsx` 新增 "render 2 cards (Profile/Gateway) + avatar circle + 不渲染 Preferences" |
| R11-7 Chat timestamp + token chip | vitest `message-pane.test.tsx` 新增 "每条 bubble 含 HH:mm + token chip 在 bubble 下方 + 70%/90% 预警" |
| R11-8 Mobile chat thread | vitest mobile chat thread 视图(useIsMobile = true)断言紧凑 header(back/avatar/name/NodeChip/⚙) |
| R11-9 顶栏 internal + UserMenu chevron | vitest `app-shell.test.tsx` + `user-menu.test.tsx` |
| R11-10 conv-list kind badge 移除 + avatar dot | vitest `conversation-sidebar.test.tsx` |
| build + dist 自验 | bash:`npm run build` + grep dist 关键串 |
| 真实入口 | 双 viewport 截图 prototype-vs-actual 5 页;留给 reviewer R12 验视觉精度 |

## Roadpoints

### R1 — 移除 Settings 二级侧栏 / sub-nav pill (R11-2 blocking)

- 步骤:
  1. 在 `src/IM/frontend/src/features/settings/settings-page-shell.tsx` 删 `<aside>` 二级 nav;整个 Shell 退化为透传 `<Outlet />`(或直接在 router 取消父布局)。
  2. `src/IM/frontend/src/app/router.tsx` 把 `/settings/agents` `/settings/nodes` `/settings/account` 三 route 提升至 app shell 顶层,各自独立渲染,不再继承 SettingsPageShell。
  3. 移动 `/settings/*` 顶部的 sub-nav tab pill(若 mobile 路径有渲染逻辑)。
  4. 验证 UserMenu 链接 / Mobile Me 链接到 `/settings/agents` `/settings/nodes` `/settings/account` 仍可达。
- 验证:
  - vitest:`/settings/agents` DOM 中不含 `nav[aria-label="Settings Sections"]`
  - 浏览器:进 `/settings/agents/<id>` 看不到 Agents/Nodes/Account 三 tab

### R2 — Mobile Me 页按 prototype 重写为卡片 list (R11-1 blocking)

- 步骤:
  1. 按 `attachments/prototype/project/im-mypage.jsx::AggregatedMePage` 重写 `src/IM/frontend/src/features/me/me-page.tsx`:
     - 顶部 Identity 卡:大 avatar(62px,圆角) + Display Name + User ID 副文案
     - 分组白卡 list:Nodes / Account / Language / Sign out
     - 每行 MyRow:`rounded-2xl bg-white shadow-sm` + 28×28 圆角 icon + label + 右 chevron `›`
     - Sign out 行 danger 红色(`text-red-600`)
     - Language 行用 LangRowMobile 风格的分段控件(EN / 中 pill toggle,选中态 `bg-accent text-white`)
  2. 移除现有 me-page 中"裸 ↗ Sign out"" 文Language EN中"" 🔔Enable desktop notifications☐" 这些非视觉项(Desktop notification 不在 prototype Me 页,移除或移到 Account)。
- 验证:
  - vitest `me-page.test.tsx` 加 "render aggregated card list" 断言含 `rounded-2xl bg-white` 类 + chevron `›` + Sign out 红
  - 浏览器 375x812:cards / padding / chevron / danger 全部到位

### R3 — Agents 详情 Identity row1 + Skills/Tool Allowlist PillSelector (R11-3, R11-4)

- 步骤:
  1. `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`:Identity card row1 改为 `Agent ID + Display Name`,Owner UUID 从 row1 移除(隐藏或并入头部小灰字)。
  2. 新建 `src/IM/frontend/src/features/settings/agents/pill-selector.tsx`(替换 `allowlist-selector.tsx` 的 checkbox grid):
     - selected items 显示为青色 pill (`rounded-full bg-accent/15 text-accent px-2 py-0.5 text-xs`)
     - 点 `+ Add` 打开多选 picker 浮层(可继承 portal 实现)
     - picker 内为 compact 列表,带描述 tooltip
  3. 替换 detail page 两处 `<AllowlistSelector>` 为 `<PillSelector>`。
- 验证:
  - vitest `agent-detail-page.test.tsx`:row1 含 Display Name,不含 Owner UUID 字段值
  - vitest `pill-selector.test.tsx`:selected items 渲染为 pill,picker 多选

### R4 — Nodes 页加 4 KPI 卡 + 🖥 icon + version 右上 + 隐藏 relay/reporting 文本暴露 (R11-5)

- 步骤:
  1. `src/IM/frontend/src/features/settings/nodes/nodes-page.tsx` 顶部加 4 KPI 卡 grid(`grid-cols-4` 桌面 / `grid-cols-2` 移动):Total nodes / Online / Offline / Total agents;数字来自现有 `query.data` 聚合(`length` / `status === 'online'` 等)。
  2. 每节点卡片左侧加 🖥(online) / 💤(offline) 圆角 38×38 icon block;Version `v0.9.4` 大字号放卡片右上(从现有 `row.version` 取)。
  3. 移除 `relay_enabled` / `reporting_enabled` 两 checkbox label 文本暴露 — 改成放在 alias 输入下方的小开关(无 label,只 icon + tooltip),或者整段从主卡移到一个"Advanced"折叠区(prototype 不显示,做最小保留)。
- 验证:
  - vitest `nodes-page.test.tsx`:`data-testid="nodes-kpi-total"` `nodes-kpi-online` `nodes-kpi-offline` `nodes-kpi-agents` 4 个数字 + `nodes-icon-online` SVG/emoji
  - 浏览器 1440 / 375 双视图:KPI / icon / version 到位

### R5 — Account 页 2 卡窄居中 + avatar 圆 + 移除 Preferences + Language 回 UserMenu (R11-6)

- 步骤:
  1. `src/IM/frontend/src/features/settings/account/account-page.tsx` 改 layout:`max-w-[720px] mx-auto`,只渲染 2 个卡:
     - Profile 卡:顶部 54px 圆形 avatar(initials)+ User ID + Display Name 字段 + 副文案 `Member since: <localized date>`
     - Gateway 卡:Default Entry Node 下拉 + Owned nodes 列表(每行 status / agent_count / version + Default 徽标)
  2. 删除 Preferences 卡的整段;Desktop notification toggle 暂保留入口但移到 Profile 卡底部小开关(或彻底移除,prototype 无),由 worker 判断最小破坏取舍 — 倾向"移除以贴齐 prototype"。
  3. `src/IM/frontend/src/app/shell/user-menu.tsx` 加 Language 切换菜单项(EN / 中 pill 风格),让 spec §128 i18n 入口仍存在;移除 Account 页对 Language 字段的依赖。
- 验证:
  - vitest `account-page.test.tsx`:仅 2 卡 + 含 avatar 圆 + 不渲染 Preferences 内容
  - 浏览器:窄居中 / 圆 avatar / Member since 本地化日期

### R6 — Chat 消息气泡 timestamp + token chip 移气泡下 + 70/90% 预警 + 统一青色 avatar + conv-list 移除 kind badge + avatar 圆点 (R11-7, R11-10)

- 步骤:
  1. `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx::MessageBubble`:
     - bubble 容器下挂 flex row:`<time>HH:mm</time>` + `<TokenChip>` 同行(仅非 user / status==completed)
     - 用 `Intl.DateTimeFormat('en-US', { hour:'2-digit', minute:'2-digit', hour12:false })` 格式化 `message.created_at`
  2. `src/IM/frontend/src/features/chat/v2/components/token-chip.tsx`:确认 70%/90% 染色规则(已部分支持 warn/critical),把 context 百分比 `ctx <%>` 文案补齐(若 message 元数据含 `prompt + completion` / `model.context_window` 比例,worker 在 message 对象上取)。
  3. `src/IM/frontend/src/features/chat/v2/components/avatar.tsx::colorForSeed` 改为对 agent 返回统一青色 `oklch(0.52 0.14 180)`(可保留 user hash);加 `status?: 'online' | 'offline'` prop,渲染小圆点(8×8 absolute 右下,白边)。
  4. `src/IM/frontend/src/features/chat/v2/components/conversation-sidebar.tsx` 行内移除 `<KindBadge>`;Avatar 传 status 渲染圆点(从 `participant.online` / `agent_status` 读)。
- 验证:
  - vitest `message-pane.test.tsx`:每 bubble 含 `<time>` HH:mm + TokenChip 在 bubble 下方 + warn/critical class 触发(token usage > 70% / 90% 比例)
  - vitest `conversation-sidebar.test.tsx`:不含 KindBadge text 'Agent';Avatar 含 status dot
  - vitest `avatar.test.tsx`:agent kind = 统一青色

### R7 — Mobile Chat 专用 thread 视图(紧凑 header) (R11-8)

- 步骤:
  1. `src/IM/frontend/src/features/chat/v2/chat-page.tsx`(或同层): 当 `useIsMobile()` 且 `activeConvId` 存在,渲染 `<MobileThreadView>` 替代 sidebar+narrow 退化布局。
  2. `<MobileThreadView>` 顶部紧凑 header:`<button aria-label="Back">‹</button>` + `<Avatar>` + `<title>` + `<NodeChip>` + `<button aria-label="Config">⚙</button>` + 全屏 MessagePane;`Back` 点击 `setActiveConvId(null)` 回 mobile 列表。
  3. mobile chat 列表(no activeConvId)沿用现有 sidebar 风格全屏列表。
- 验证:
  - vitest:mock `useIsMobile = true` + active conv,断言 Mobile thread 组件渲染 + 不渲染桌面 sidebar
  - 浏览器 375x812:进直聊看到紧凑 header,无 sidebar

### R8 — Shell polish(internal 徽标 + UserMenu ▾ + 底部 tab emoji + unread badge) (R11-9)

- 步骤:
  1. `src/IM/frontend/src/app/shell/app-shell.tsx` Brand 段:`nano IM` 后挂 `<span class="text-[10px] bg-bg-soft rounded px-1">internal</span>`。
  2. `user-menu.tsx`:按钮内 avatar + name 后加 `▾`(`<span aria-hidden>▾</span>`)。
  3. 底部 mobile tabs:每 tab label 前挂 emoji icon(💬 Chat / 🤖 Agents / 👤 Me);Chat tab 含 unread badge(从 conv unread 聚合 — 若现有 store 无,worker 加一个最小 selector 或暂占位红点,留 issue 不做完整 unread 实时计数,避免越界)。
- 验证:
  - vitest `app-shell.test.tsx`:顶栏含 'internal'
  - vitest `user-menu.test.tsx`:含 chevron `▾`
  - vitest mobile tab 渲染含 emoji

### R9 — build + dist 自验 + 双 viewport 截图 + progress.md Evidence 段

- 步骤:
  1. `cd src/IM/frontend && npm install --no-audit --no-fund && npm run build`
  2. grep `dist/assets/*.js` 关键串:`internal` / `Total nodes` / `pill-selector` / `MobileThreadView` 等
  3. 启 IM service / Gateway / Kernel(若 team-lead 已起则复用);浏览器 1440x900 + 375x812 双 viewport 各页截图;并排 prototype-vs-actual
  4. 写 `progress.md`:每 roadpoint 一段(Context/Decision/Rationale/Evidence/Rollback/Commits)
- 验证:
  - build green;dist grep 命中
  - 5 页 × 2 viewport = 10 张 actual 截图;对应 10 张 prototype 截图(可复用 R11 evidence 目录的 proto/)
