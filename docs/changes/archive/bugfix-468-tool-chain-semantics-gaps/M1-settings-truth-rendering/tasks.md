# bugfix-468-M1: settings-truth-rendering — Tasks

> 对齐: ../design.md v1

## 目标

让 Agent 设置 detail 页的 Tools 面板严格按存储真值渲染：空 `tool_allowlist` 不再显示为“默认全开”。同步从 `PillSelector` 删除 `useDefaultOn` prop，消灭次误用隐患；create 页预选行为保持不变。

## 退出标准

- [x] `pill-selector.tsx` 不再导出/使用 `useDefaultOn`，空 `selected` 时全部 pill 不亮。
- [x] `agent-detail-page.tsx` 删除 `allowlistUserTouched` 及两处「空则物化默认集」分支；空名单下开启 requires_tool feature 时只追加该工具本身。
- [x] `agent-create-page.tsx` 清理 `PillSelector` 的 `useDefaultOn={false}`。
- [x] settings/agents 目录内相关测试断言与新语义一致。
- [x] `npm run test` 全绿；`npm run build` 通过；detail 页不再引用 `useDefaultOn`。
- [x] 真实浏览器验收四种状态：存储非空显示存储值、存储空全不亮、清空-保存-刷新后保持全不亮、create 页预选不变。

## 测试策略

- 被测行为（来自退出标准）：
  1. 空 `tool_allowlist` 时所有 tools pill 显示未选中。
  2. 非空 `tool_allowlist` 时按存储名单显示选中。
  3. 用户点击 pill 可正常切换选中/未选中。
  4. detail 页空名单下勾选 requires_tool feature，PATCH 只含该工具。
  5. detail 页空名单下勾选无 requires_tool feature，`tool_allowlist` 仍为空。
  6. create 页初始仍按 `default_on` 预选工具。
- 已有测试在：
  - `agent-tools-pill.test.tsx`（扩展）：覆盖行为 1/2/3。
  - `agent-detail-page.test.tsx`（扩展）：覆盖行为 4/5，调整旧断言。
- 落层/目录/marker：组件测试在 `src/features/settings/agents/*.test.tsx`，无 e2e marker。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器 QA 截图落 `evidence/`。

前端 UI milestone 额外填写：

用户路径分类：bug-regression（历史 UI 语义缺陷修复）。

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 真栈：detail 页空名单全不亮 / 非空名单显示存储值 |
| loading | 已有组件测试覆盖，不动 |
| empty | 真栈：清空-保存-刷新后保持全不亮 |
| error | 已有组件测试覆盖，不动 |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | N/A |
| missing/nullable data | N/A |
| mobile viewport | 真栈截图覆盖 375px |
| desktop viewport | 真栈截图覆盖 1440px |
| dark mode（如项目支持） | N/A |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 空名单显示成默认全开 | `agent-tools-pill.test.tsx` 回归 + 真栈截图 | 是 |
| detail 页保存时错误物化默认集 | `agent-detail-page.test.tsx` 回归 | 是 |
| create 页预选行为被误改 | `agent-create.test.tsx` 现有用例断言保留 + 真栈验证 | 否（已有覆盖） |
| 响应式布局/样式走样 | 真栈截图覆盖两种 viewport | 否 |

Prototype / Reference Contract：N/A

## Roadpoints

### R1 — 删除 PillSelector useDefaultOn 语义并清理 create 页传参

- 步骤:
  1. C1: 修改/新增 `agent-tools-pill.test.tsx` 中断言，使其在空 `tool_allowlist` 时期望所有 pill 未选中。
  2. C2: 删除 `pill-selector.tsx` 的 `useDefaultOn` prop、`emptyMeansDefault` 逻辑及 `default_on` 相关注释；保留 `PillOption` 最小字段。
  3. C2: 删除 `agent-create-page.tsx` 中 `PillSelector` 的 `useDefaultOn={false}`。
  4. C3: 更新 `progress.md`。
- 验证:
  - `npm run test -- src/features/settings/agents/agent-tools-pill.test.tsx` 绿。
  - `npm run test -- src/features/settings/agents/agent-create.test.tsx` 绿（预选行为不变）。

### R2 — 删除 detail 页 allowlistUserTouched 及物化分支

- 步骤:
  1. C1: 修改 `agent-detail-page.test.tsx` 中 cron/heartbeat bugfix 相关断言：空名单下勾 cron 只保存 `["cron_tool"]`；勾 heartbeat 仍为空。
  2. C2: 删除 `agent-detail-page.tsx` 的 `allowlistUserTouched` 状态、reset 逻辑、两处 default_on 物化分支；feature toggle 只在空名单下追加 requires_tool 本身；onChange 中 `removed` 直接从 `draft.tool_allowlist` 计算。
  3. C3: 更新 `progress.md`。
- 验证:
  - `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx` 绿。

### R3 — 全量测试、构建与浏览器验收

- 步骤:
  1. 跑 `npm run test` 全量。
  2. 跑 `npm run build`。
  3. 起隔离真栈（`scripts/e2e-up.sh`），验证四种状态并截图到 `evidence/`。
  4. 补齐 `progress.md` 与 `tasks.md` 状态；提交 docs。
- 验证:
  - `npm run test` 64 files / 604+ tests 全绿。
  - `npm run build` 无 TS/构建错误。
  - evidence/ 下有四张截图及 viewport 说明。
