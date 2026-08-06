# bugfix-505: Agent 切换加载与导航栏

## Relations

- Related: bugfix-500, refactor-483

## 原始报告

> 切换的时候，卡住的页面为啥没了左边，而且这个加载页面很丑，不符合商业的IM的设计

> 另一个问题，左边的agent名字和背景，对比度不够，很难看得清，很丑。

截图：

- `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-b65bf1cb-8acf-4394-ac04-7115171c9de4.png`
- `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-5bda6115-41fe-4a6e-9b81-51c354bcd1cb.png`

## 澄清记录

- Q1: 是否将修复范围收口为桌面端 Agent 配置切换的连续导航和左侧 Agent 列表可读性，保留移动端单栏与现有配置表单？
  A(原话): 独立完成这两个问题的修复。并提一个pr，中途spec，design，不需要我人工review。我做最后的pr review
  Agent 解读: 用户授权自行完成截图中两项桌面端体验问题及必要的 spec/design 流程，并以 PR 供最终审阅；不扩大为重做配置表单或其他 IM 页面。

## 现象 / 复现

在桌面端的 Agent 配置页中，从一个 Agent 切换到另一个 Agent 时，新的配置请求尚未返回会显示一整页孤立的“加载 Agent 配置中…”文本。Agent 左侧导航栏同时消失，用户不能继续识别当前产品位置或改选其他 Agent。请求失败时也会出现相同的壳层缺失。

已加载页面的 Agent 左栏中，未选中 Agent 的名称采用了比深色背景更暗的文字色。多个 Agent 同时出现时，名称和 agent id 难以辨认，无法承担持续导航的职责。

复现：在至少有两个 Agent 的桌面 Web IM 中，打开 `/settings/agents/<agent-id>` 后通过左栏切换到另一 Agent，并让后一个详情请求处于 pending；或观察未选中的 Agent 行。

## 根因

`AgentDetailPage` 在 desktop layout wrapper 之前对 loading、initial error 和未完成 detail state 直接 return。因此正常状态才渲染的 `AgentsRailDesktop` 在切换的异步窗口被卸载。该 early-return 在 `038d615a7f` 中引入；`5febbd3c3` 为 Agent 详情/创建页提取连续 desktop rail 时只把 rail 放在正常渲染分支，未覆盖这些早退状态。

`bugfix-500` 的原始设计意图是桌面 Agent 页面保持连续导航、移动端保持单栏。修复必须保持这一不变量：桌面端切换、加载或请求失败时仍可见同一套 Agent 左栏；移动端不出现桌面侧栏。

同一提交新增的 `AgentsRailDesktop` 将未选中名称设为 `oklch(0.18 0.01 240)`，而 rail 背景为 `oklch(0.24 0.012 240)`。深色文字叠在深色底上造成低对比度，且现有测试只断言侧栏存在和可点击，未断言 loading 状态保留侧栏或视觉 token 的可读关系。

实现复核又发现两个同属异步壳层的边界：路由从已加载 Agent A 切到 Agent B 时，页面仍保留 A 的 `draft`；若 B 的首次请求失败，error 分支因旧 `draft` 存在而不会显示，随后落入“不完整详情”的 loading。另一个边界是 desktop state panel 使用 `overflow-hidden`，较长的后端错误详情会把 Retry 裁出可视区且无法滚动。

第二轮复核进一步确认，依赖 `agentId` effect 清理仍不是完整的 Agent 生命周期边界。若 A 的保存请求 pending 时切到 B，同一个 TanStack Query mutation observer 会在 B render 时更新 options，随后 A 的成功回调可能使用 B 的 closure，把 A 的响应写入 B 的 draft、saved 状态与 query cache。并且 effect 属于被动阶段；当 B 已同步命中 cache，页面可先 commit 一帧 `route=B` 与 `draft=A` 的组合，再由 effect 修正。

## 修复

- `AgentDetailPage` 把 initial loading、initial error 和 detail 尚未完整的状态统一放入 responsive state shell。desktop shell 始终先渲染既有 `AgentsRailDesktop`；mobile 继续只渲染单栏内容。
- 原本孤立的 loading 文本改为内容面板内的窄幅白色状态卡，使用轻边框、阴影和单一 accent spinner；initial error 在同一位置展示详情与 Retry。
- `AgentsRailDesktop` 的 normal Agent 名称/id 改为深色 rail 上的亮前景，active 继续使用白色名称与高亮背景；hover、focus、active 背景集中为静态 class，不再由 mouse event 改 inline style。
- `AgentDetailPage` 只读取 route param，并用 `key={agentId}` 挂载实际持有 state/query/mutation 的 `AgentDetailPageContent`。Agent 切换会在 commit 前创建新的 Agent-scoped state 与 mutation observer；旧 Agent 的 pending mutation 无法写入新 Agent 的 draft、saved 状态或 cache，cached/uncached B 都不会渲染 A 的表单。
- state panel 改为自身承担纵向滚动；长错误详情仍完整保留，Retry 可通过内容区滚动到达，desktop rail 不随内容滚动。
- 新增长期回归：`agent-detail-loading-shell.test.tsx` 覆盖 desktop pending/error 保留 rail 与 mobile 单栏；`agents-rail-desktop.test.tsx` 覆盖 normal/hover/active identity color semantics 与 desktop-only responsive class。
- 实现 commits：`f6e733d1d`、`195a22809`；真实浏览器 evidence commit：`27551b89d`。

## 验证

- 修前：新增回归在当前实现上 4 个关键断言失败，直接观察到 desktop pending 无 rail、desktop initial error 无 rail、mobile 仍为裸 loading 文本，以及 active/normal/hover 目标色语义不存在。
- 修后自动化：4 个相关前端测试文件共 30 tests passed；`npm run build` 的 TypeScript 与 Vite build 通过（502 modules）。既有 detail 测试保留 baseline React `act(...)` warnings，无失败。
- 修后真实入口：用 worktree 隔离 IM/Gateway + Vite，登录真实 Web IM 后在 `/settings/agents/e2e` 与 `/settings/agents/e2e-peer` 复走原始症状。desktop `1440x900` 下 pending 与注入 503 的 initial error 都保留左侧 Agent rail；loaded/hover/active 名称与 id 清晰可读；mobile `390x844` pending 不出现 desktop rail。
- 正常真实 API 恢复后，config/capabilities/nodes/agents 均返回 200，浏览器 console 为 0 errors / 0 warnings。可复查截图见 `M1-fix/evidence/desktop-loading.png`、`desktop-error.png`、`desktop-loaded.png`、`desktop-hover.png`、`mobile-loading.png`；逐项对照见 `M1-fix/progress.md`。
- runtime 已清理：Playwright session、Vite、IM、Gateway 均停止，PID/secret/config 已由 `e2e-down.sh` 清理，验证端口 `51271`、`53119` 均无 listener。
- Reviewer fix 红测：在修复前，新增的 desktop/mobile “A 已加载后切到 B 且 B 首次失败”用例都停在 loading，长错误 state panel 也缺少滚动语义；修复后 `agent-detail-loading-shell.test.tsx` 5/5 passed。
- Reviewer fix 回归：4 个相关前端测试文件共 32 tests passed；`npm run build` 通过（502 modules）。既有 detail 测试仍只有 baseline React `act(...)` warnings，无失败。
- Reviewer fix 真实入口：隔离 Web IM 中先让 `/settings/agents/e2e` 真实 200 加载，再从 desktop rail 切到注入 503 的 `e2e-peer`；页面显示 B 的完整错误与 Retry，rail 保持并选中 B，不再展示 A 的表单。`1440x420` 下 state panel 实测 `scrollHeight=638`、`clientHeight=372`，滚到底后 Retry 位于 viewport 内；`390x844` 下仍为无 desktop rail 的单列错误页。注入阶段 console 唯一 error 为预期 503。
- Reviewer fix 截图：`M1-fix/evidence/review-agent-switch-error.png`、`review-long-error-scroll.png`、`review-mobile-error.png`。该轮 Playwright session、Vite、IM 与 Gateway 均已停止并清理。
- Reviewer fix round 2 红测：修前 pending save A→cached B 用例在 A 响应后把 B 页面改成 `Agent One Saved` 并污染 B cache；commit probe 也直接记录到 `{agentId: "agent-two", heading: "Agent One"}`。keyed route boundary 后两个用例转绿，async-shell 文件 7/7 passed。
- Reviewer fix round 2 回归：4 个相关前端测试文件共 34 tests passed；`npm run build` 通过（502 modules）。既有 detail 测试仍只有 baseline React `act(...)` warnings，无失败。
- Reviewer fix round 2 真实入口：隔离 Web IM 中先真实加载 `e2e-peer` 形成 cache，再编辑 `e2e` 并把真实 PATCH 响应延迟 30 秒；保存后立即切回 cached `e2e-peer`。A 的 PATCH 最终 200 后，B 仍显示 `e2e-peer`、rail 仍选中 B、状态为 `No changes`，console 0 errors / 0 warnings。截图：`M1-fix/evidence/review-pending-save-isolated.png`；Playwright、Vite、IM 与 Gateway 均已停止并清理。
