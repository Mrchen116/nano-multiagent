# bugfix-468-M1 — Progress

## R1 — 删除 PillSelector useDefaultOn 语义并清理 create 页传参

- Context: design 决策 1：detail 页删除 `useDefaultOn` 语义，`PillSelector` 空名单 = 全不亮；`useDefaultOn` prop 整体删除。
- Decision: 从 `PillSelector` 删除 `useDefaultOn` prop、`emptyMeansDefault` 分支及 `default_on` 字段使用；`agent-create-page.tsx` 同步清理传参。
- Rationale: `useDefaultOn` 只剩 detail 页一个真实消费者，prop 本身成为“空名单=默认全开”的语义残留，删之避免次误用；create 页预选走自己的 `defaultNames()`，不受影响。
- Evidence:
  - Tests: `npm run test -- src/features/settings/agents/agent-tools-pill.test.tsx src/features/settings/agents/agent-create.test.tsx` → 2 passed / 10 tests。
  - Entry: 前端组件测试（AgentDetailPage 渲染 + 点击）。
  - Frontend State Matrix: N/A（本 R 只改组件内部语义）。
  - Browser QA: N/A（R3 统一做）。
  - E2E/Regression: `agent-tools-pill.test.tsx` 回归空名单/非空名单/切换三种状态。
  - Visual/Interaction: N/A（R3 统一做）。
  - Prototype Comparison: N/A。
- Rollback: `git revert c639dd817`。
- Commits: C1=`8c82d56a4`, C2=`c639dd817`。

## R2 — 删除 detail 页 allowlistUserTouched 及物化分支

- Context: design 决策 1 连动简化：`allowlistUserTouched` 及两处「空则物化默认集」分支失去存在意义；空名单下开启 requires_tool feature 时只追加该工具本身。
- Decision: 删除 `allowlistUserTouched` 状态与 reset 逻辑；feature toggle 与 pill onChange 均直接操作 `draft.tool_allowlist`，不再物化 `default_on` 集合。
- Rationale: runtime 自 PR #195 起已按「空=零工具」执行，UI 唯一职责是反映存储；继续物化默认集会在保存时把空名单变成非空名单，与真值语义冲突。
- Evidence:
  - Tests: `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx` → 1 passed / 28 tests。
  - Entry: 前端组件测试（AgentDetailPage feature toggle + save）。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A（R3 统一做）。
  - E2E/Regression: `agent-detail-page.test.tsx` 回归「空 allowlist + cron 只追加 cron_tool」「空 allowlist + heartbeat 不改变 allowlist」。
  - Visual/Interaction: N/A（R3 统一做）。
  - Prototype Comparison: N/A。
- Rollback: `git revert efa83ab7c`。
- Commits: C1=`ed30e726e`, C2=`efa83ab7c`。

## R3 — 全量测试、构建与浏览器验收

- Context: milestone 退出标准要求 `npm run test` 全绿、`npm run build` 通过，并用真栈浏览器覆盖四种状态。
- Decision: 跑全量 vitest → 生产构建 → `scripts/e2e-up.sh` 起隔离栈 → Playwright 登录后拍摄四种状态截图。
- Rationale: 前端改动不能只看组件测试；空名单/非空名单/清空保存刷新/create 预选必须在真实浏览器与真实 Gateway 数据下验证。
- Evidence:
  - Tests: `npm run test` → 64 passed / 605 tests；`npm run build` → tsc + vite build 成功。
  - Entry: 真栈 IM (`http://127.0.0.1:53722`) + Gateway (`wt-bugfix-468-M1-98490`) + Chromium。
  - Frontend State Matrix: default（非空名单显示存储值）、empty（空名单全不亮）、mobile viewport（375×812）、desktop viewport（1440×900）。
  - Browser QA: 登录 → `/settings/agents/default-agent`（非空）→ `/settings/agents/plato`（空）→ default-agent 清空所有 tools 保存并刷新 → `/settings/agents/new` 选择节点观察预选。无 console error / failed network request（截图前检查）。
  - E2E/Regression: N/A（本项目前端无 browser E2E 套件，组件测试 + 真栈截图验收）。
  - Visual/Interaction:
    - `evidence/01-non-empty-desktop.png`：read/write 选中，其余未选中。
    - `evidence/02-non-empty-mobile.png`：read/write 选中。
    - `evidence/03-empty-desktop.png`：plato 所有 tools 未选中。
    - `evidence/04-cleared-refreshed-desktop.png`：default-agent 清空保存刷新后所有 tools 未选中。
    - `evidence/05-create-preselect-desktop.png`：create 页 tools 按 default_on 预选（cron 未选中）。
  - Prototype Comparison: N/A。
- Rollback: `git revert 8ca1226f4` 后重新跑 e2e-up/build。
- Commits: 本 R 无新增代码提交；测试与证据已落盘。
