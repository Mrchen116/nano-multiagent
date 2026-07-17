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

- Context: 待补充。
- Decision: 待补充。
- Rationale: 待补充。
- Evidence:
  - Tests: 待补充。
  - Entry: 真栈 IM + Gateway + 浏览器。
  - Frontend State Matrix: default / empty / mobile / desktop。
  - Browser QA: 待补充 URL 与操作路径。
  - E2E/Regression: N/A（本项目前端无 browser E2E 套件，组件测试 + 真栈截图验收）。
  - Visual/Interaction: 截图落 `evidence/`。
  - Prototype Comparison: N/A。
- Rollback: 待补充。
- Commits: 待补充。
