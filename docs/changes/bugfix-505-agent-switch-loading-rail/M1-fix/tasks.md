# bugfix-505-M1: Agent 切换加载与导航栏修复 — Tasks

> 对齐: ../fix.md

## 目标

修复桌面 Agent 详情切换时 pending / initial-error 状态丢失 Agent 左栏、加载态粗糙，以及深色 rail 中 Agent 身份行对比度不足的问题；移动端继续使用既有单栏详情流程。

## 退出标准

- [ ] 桌面 Agent 详情在初始 pending、请求失败和正常完成状态都保留同一个 `AgentsRailDesktop`。
- [ ] pending 使用克制、可识别为加载中的面板内状态；initial error 在同一内容面板内提供失败信息和重试。
- [ ] rail 的 normal / hover / active Agent 身份行在深色背景上保持可读，active 仍清楚表达当前项。
- [ ] mobile viewport 不显示 desktop rail，既有表单和交互不变。
- [ ] 定向回归、前端 build 与真实浏览器桌面/移动验收通过，证据落在本 milestone 目录。

## 测试策略

- 被测行为（来自退出标准）：`AgentDetailPage` 的 desktop pending / initial-error 状态保留 rail，mobile pending 不渲染 desktop rail；`AgentsRailDesktop` 的 normal / hover / active 行使用明确的深色背景可读前景语义。
- 保护的回归风险与可观察 seam：从 React 页面/组件渲染结果观察 rail、内容状态、重试入口和响应式隐藏 class；从真实浏览器观察最终布局、对比度与 hover/active 视觉。
- 已有保护与处置：`agent-detail-page.test.tsx` 保护正常详情业务流，`agent-create.test.tsx` 保护创建页 desktop rail；两者 keep。新建 `agent-detail-loading-shell.test.tsx` 与 `agents-rail-desktop.test.tsx`，因为既有 detail 文件已超过 1000 行且没有 pending/error shell 或 rail 视觉语义 owner。
- 落层/目录/marker：`src/IM/frontend/src/features/settings/agents/` colocated Vitest/jsdom，marker：无；这是能直接暴露组件状态丢壳和 class 语义回归的最低层。真实视觉另以浏览器截图验收，不重复落库 E2E。
- 可选依赖 importorskip：无（Vitest 前端固定依赖）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 Web IM 桌面 loading/error/loaded 与移动 loading 截图及 console/network 检查记录，保存到 `M1-fix/evidence/`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 正常详情内容与交互 | `agent-detail-page.test.tsx` | keep | 正常 detail 业务风险仍在；新增文件只补异步壳层，不重复正常业务断言 | 定向 Vitest |
| 创建页连续 desktop rail | `agent-create.test.tsx::shows the desktop agent rail...` | keep | 创建页继续复用同一 rail，当前行为不变 | 定向 Vitest |

用户路径分类：`bug-regression`（shell preservation）+ `visual-only`（loading polish / rail contrast）。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 既有正常 detail 测试 + desktop 浏览器截图 |
| loading | desktop/mobile 组件回归 + desktop 浏览器截图 |
| empty | N/A；Agent detail 无独立空态 |
| error | desktop initial-error 组件回归 + desktop 浏览器截图 |
| disabled | N/A；本修复不改表单控件 |
| submitting | N/A；本修复不改保存流程 |
| permission denied | N/A；归入既有 query error，非本修复独立状态 |
| long content | 错误详情容器可换行的浏览器检查 |
| missing/nullable data | initial pending 和 initial error 无 detail data 的组件回归 |
| mobile viewport | loading 不出现 desktop rail，保留单栏内容状态 |
| desktop viewport | loading / error / loaded 均保留 rail |
| dark mode（如项目支持） | N/A；rail 本身固定深色，按既有产品视觉验收 |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| pending / error early return 卸载 desktop rail | Vitest 页面回归 + 真实浏览器状态截图 | 是（Vitest） |
| mobile 被误加 desktop rail | Vitest 页面回归 + mobile viewport 浏览器检查 | 是（Vitest） |
| plain full-screen loading 与 error 脱离详情面板 | DOM 状态语义 + 真实浏览器截图 | DOM 是，截图为 durable evidence |
| normal / hover / active 行对比度不足 | rail 组件 class/交互语义 + desktop 截图 | 语义是，视觉截图为 durable evidence |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| 派发中的 frontend reference contract | Desktop Agent detail transitions, loading, and initial-error states retain the existing `AgentsRailDesktop`; normal/hover/active identity rows readable against the dark rail; mobile hides desktop rail | desktop loading/error/loaded + mobile loading 截图和 Prototype Comparison | worker |

## Roadpoints

### R1 — 固化异步壳层回归并实现连续 desktop shell

- 状态：TODO
- 步骤：先以 pending、initial-error、mobile pending 用例复现 desktop rail 丢失，再把详情状态放入统一 responsive shell，加入面板内 loading/error 状态。
- 验证：新增页面回归由红转绿；定向运行 `agent-detail-loading-shell.test.tsx`。

### R2 — 修正 rail 身份行视觉语义

- 状态：TODO
- 步骤：先以 normal / hover / active 行前景和背景语义用例复现低对比度，再用既有 dark rail 色系调整文字、hover、active 表达。
- 验证：新增 rail 组件回归由红转绿；定向运行 `agents-rail-desktop.test.tsx`。

### R3 — 真实浏览器验收与交付门禁

- 状态：TODO
- 步骤：隔离启动 Web IM，覆盖 desktop loading/error/loaded 与 mobile loading，检查 console/network，并保存 durable screenshots；运行相关 Vitest 与 build。
- 验证：证据写入 `M1-fix/evidence/`，所有退出标准闭环。
