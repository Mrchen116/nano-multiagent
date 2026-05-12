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

