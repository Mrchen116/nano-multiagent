# bugfix-505-M1 — Progress

## 启动证据

- Sync Gate: `unit/bugfix-505`、`origin/unit/bugfix-505` 均为 `058564a0ce643ca0bfda4f1df46ba6116b258d4f`。
- Baseline: `npm test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-create.test.tsx`，2 files / 25 tests passed；存在基线已有 React `act(...)` warnings，无失败。
- Scope: 仅 Agent detail async shell、shared desktop rail 视觉语义、定向测试、M1 过程/evidence 与 lite `fix.md` 回填。

## R1 — 固化异步壳层回归并实现连续 desktop shell

- Status: DONE
- Context: `AgentDetailPage` 在构造 desktop layout 前直接返回初始 loading/error，导致切换 Agent 时连续导航消失；移动端仍须保持单栏。
- Decision: 把无数据 loading、initial error 和不完整 detail 状态统一送入 responsive state shell。desktop shell 先渲染既有 `AgentsRailDesktop`，内容区显示居中的轻量 loading card 或 error card；mobile 只渲染同一内容状态，不渲染 rail。
- Rationale: 修复根因所在的 early-return 边界，复用同一 rail，不复制列表或更改正常详情表单。
- Evidence:
  - Tests: 红测 `agent-detail-loading-shell.test.tsx` 3/3 失败，分别显示 desktop loading 无 rail、desktop error 无 rail、mobile 仍为裸 loading 文本；Green 后 3/3 passed。
  - Entry: 组件入口覆盖 route param `agent-two` 的无数据 pending 与 initial error；真实浏览器入口由 R3 验收。
  - Frontend State Matrix: loading/error/missing data/desktop/mobile 已覆盖；default 保持既有 detail 测试；其他状态 N/A，见 tasks.md。
  - Browser QA: R3 执行。
  - E2E/Regression: `src/IM/frontend/src/features/settings/agents/agent-detail-loading-shell.test.tsx`；`npm test -- src/features/settings/agents/agent-detail-loading-shell.test.tsx`。
  - Visual/Interaction: loading 使用窄幅白色面板、轻边框/阴影和单个 accent spinner；error 使用同一内容区与可重试卡片。R3 保存截图。
  - Prototype Comparison: 派发 reference contract 的 shell/mobile 项在组件层 match；浏览器对照在 R3。
- Rollback: revert 本 roadpoint commit，恢复旧 early returns。
- Commits: `f6e733d1d`
- Next: R2 修正 rail 视觉语义。

## R2 — 修正 rail 身份行视觉语义

- Status: DONE
- Context: normal Agent 名称使用 `oklch(0.18...)` 叠在 `oklch(0.24...)` rail 上，文字比背景更暗；hover 依赖事件改 inline style，active 的背景与 outline 分散在 class/style 两处。
- Decision: normal 名称提升到 `oklch(0.86...)`、id 提升到 `oklch(0.64...)`；active 名称保持白色、id 使用 `oklch(0.70...)`。row 的 normal/hover/active 背景和 active ring 全部用静态 Tailwind class 表达，删除 mouse enter/leave inline mutation。
- Rationale: 深色 rail 上身份文本始终使用亮前景；静态状态 class 同时覆盖鼠标、键盘 focus 和 active，视觉规则集中且可被回归测试观察。
- Evidence:
  - Tests: 红测显示 active row 缺目标 background/ring class；Green 后 `agents-rail-desktop.test.tsx` 2/2 passed，覆盖 normal/hover/active identity colors 与 desktop-only responsive classes。
  - Entry: `AgentsRailDesktop` 的真实按钮行、display name 和 agent id DOM；浏览器入口由 R3 验收。
  - Frontend State Matrix: normal/hover/active/keyboard focus/desktop rail 已覆盖；mobile 由 `hidden lg:flex` 既有响应式语义保持。
  - Browser QA: R3 执行。
  - E2E/Regression: `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.test.tsx`；`npm test -- src/features/settings/agents/agents-rail-desktop.test.tsx`。
  - Visual/Interaction: normal/hover/active 前景与背景 token 已由测试锁定，真实像素与交互截图在 R3。
  - Prototype Comparison: 派发 reference contract 的 rail contrast 语义在组件层 match；浏览器对照在 R3。
- Rollback: revert 本 roadpoint commit，恢复旧 rail 行色值和 inline hover mutation。
- Commits: `195a22809`
- Next: R3 真实浏览器验收、全量定向门禁与 build。

## R3 — 真实浏览器验收与交付门禁

- Status: DONE
- Context: 前端 bug 修复必须从真实 Web IM 入口验证最终 responsive layout、hover/active 对比度和异步状态；所有占用资源必须隔离并回收。
- Decision: 以 `e2e-up.sh` 启动独立 IM/Gateway，Vite 使用独立 `51271` 端口代理到隔离 IM `53119`。真实登录 `nano` 后在 `/settings/agents/e2e` 与 `/settings/agents/e2e-peer` 验收；通过浏览器 route 分别保持 config pending、注入 503 initial error，再恢复真实 200 API 检查正常页。截图保存到本目录 `evidence/`。
- Rationale: 真进程、真认证、真路由与真浏览器能覆盖 jsdom 看不到的最终 CSS、响应式和 shell 接线；网络注入只控制异步状态，不替代正常实际 API 路径。
- Evidence:
  - Tests: `npm test -- src/features/settings/agents/agent-detail-loading-shell.test.tsx src/features/settings/agents/agents-rail-desktop.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-create.test.tsx` → 4 files / 30 tests passed；既有 detail 测试仍输出 baseline `act(...)` warnings，无失败。`npm run build` → TypeScript + Vite build passed（502 modules）。
  - Entry: 真实登录后打开 `/settings/agents/e2e` 与 `/settings/agents/e2e-peer`；正常 config/capabilities/nodes/agents 请求均 200。切换到 pending 的 `e2e-peer` 和 reload 注入 503 的 `e2e` 时，desktop rail 均留在原位；error 的 Retry 可见。
  - Frontend State Matrix: desktop default/loading/error/normal-hover-active、mobile loading、missing initial data、long error detail 均覆盖；其他 N/A 状态未改变。
  - Browser QA: Playwright Chromium，desktop `1440x900` 与 mobile `390x844`；desktop normal、hover、pending、initial-error 及 mobile pending 均实际打开。恢复真实 API 后 console 0 errors / 0 warnings，相关 config/capabilities/nodes/agents 全部 200；状态注入阶段仅有预期 pending 或预期 503。
  - E2E/Regression: 永久回归为两个新增 colocated Vitest 文件（5 tests）；浏览器步骤为一次性交付验收，未新增重复 E2E spec。
  - Visual/Interaction: `evidence/desktop-loaded.png`、`evidence/desktop-hover.png`、`evidence/desktop-loading.png`、`evidence/desktop-error.png`、`evidence/mobile-loading.png`。
  - Prototype Comparison:

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| 派发 frontend reference contract | pending / initial-error retain existing `AgentsRailDesktop` | `evidence/desktop-loading.png`, `evidence/desktop-error.png` | 1440x900 loading/error | match | N/A |
| 派发 frontend reference contract | normal / hover / active identity rows readable on dark rail | `evidence/desktop-loaded.png`, `evidence/desktop-hover.png` | 1440x900 loaded/hover/active | match | N/A |
| 派发 frontend reference contract | mobile hides desktop rail | `evidence/mobile-loading.png` | 390x844 loading | match | N/A |

- Rollback: revert R1/R2 实现 commits；R3 只含 durable evidence 与进度记录。
- Commits: pending (this commit)
- Next: lite `fix.md` 回填、rebase 后门禁与 unit merge。
- Runtime cleanup: Playwright session 已关闭，Vite `51271` 已停止，`e2e-down.sh` 已清理 IM/Gateway PID 与 secret/config，IM `53119` 和 Vite `51271` 均无 listener。
- Environment note: 首次把 `e2e-up.sh` 放在短生命周期 shell 中导致进程在 ready 后被宿主回收；日志证明注册/登录原先为 201/200。改由持久 PTY 持有进程后，真实入口全程通过；未修改产品代码或降低验收标准。

## Promotion Candidates

None.
