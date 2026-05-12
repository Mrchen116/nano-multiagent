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

