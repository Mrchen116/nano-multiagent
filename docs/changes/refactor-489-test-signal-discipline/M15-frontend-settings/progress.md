# refactor-489-M15 — Progress

## Baseline / Audit

- Claim: M15 当前 25 个 settings test files 可运行，但混有 mock shape、旧 prototype/CSS/元素缺席、milestone 命名与跨文件重复断言；真实 account/policies/agent/node/channel/realtime 风险可在同域更直接的 interaction/API-state tests 中保留。
- Baseline: `origin/unit/refactor-489@8ceeb39eb`。
- Method: 读取 motivation/design/M1 处置规范、testing 与 IM current specs；枚举 25 files / 6036 lines / 132 tests；按测试名、SUT、用户/API seam 和重复 owner 审计；复用主仓 frontend `node_modules` 的 ignored symlink 运行全域。
- Result: 基线 PASS，`25 passed` files、`132 passed` tests（6.37s）。输出同时暴露大量 React `act(...)` 与无效 user-stream fetch 告警，主要来自只渲染旧布局/缺席状态但不建立完整交互 seam 的测试。
- Limit: 本 milestone 零 UI delta，不以真实浏览器或截图重新验收视觉；完成标准是保留可重复的 interaction/API-state regression 并让 build/全域 Vitest 通过。

## R1 — 删除设置壳、mock 与历史视觉终态

- 状态: DONE
- Context: settings 树含 mock fixture 字段 shape、旧二级导航缺席、mobile DOM 缺席、node 不请求 agent list，以及 Account/Nodes/Agents list 的旧 prototype 卡片、CSS class、icon/KPI/chevron 等交付终态；这些断言不经过当前保存或 API 状态 seam。
- Decision: 删除 4 个纯终态文件；Account 收敛为加载后保存与 Discard，Nodes 收敛为在线创建入口、alias PATCH、status/error/empty，Agents list 收敛为列表打开详情、empty 与 load-error retry。移除退役 endpoint 负断言和 CSS palette 检查。
- Rationale: 页面布局或某元素“不存在”会被任何等价 UI 重构击穿，却不能证明设置可用；同一渲染成本应观察用户能否改值、提交、进入对象，或从失败恢复。删除项对应的产品风险要么不存在，要么归 M16 app/router/responsive owner。
- Evidence:
  - Tests: Account/Agents list/Nodes/Policies 5 files、9 tests 全绿（1.91s）。
  - Entry: jsdom 从真实 app routes 进入 `/settings/account`、`/settings/agents`、`/settings/nodes`、`/settings/policies`；执行输入、选择、保存、Discard、打开详情和 Retry。
  - Frontend State Matrix: default、empty、error、disabled（offline node / clean form）、submitting 后回显；visual/mobile N/A（无 UI delta）。
  - Browser QA: N/A；仅测试资产改动，未改组件或 UI。
  - E2E/Regression: 保留 page-level interaction regression；未新增浏览器 E2E，因没有产品行为变化。
  - Visual/Interaction: 交互由 Testing Library role/label 驱动；无截图或 reference。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `7c51d7058`。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 合并 Agent form/API 的 feature、allowlist、preview 与历史迁移重复。

## R2 — 合并 Agent 配置与 API 重复保护

- 状态: DONE
- Context: Agent tests 同时从 selector、feature panel、create/edit/detail 整页重复证明 allowlist/features，详情页还保留旧 heartbeat/cron 卡片、历史 milestone 终态与静态 i18n；API tests 则以重复 case 和退役 endpoint 负断言扩大噪声。
- Decision: 让 API adapter 负责 endpoint/auth/normalization，selector 负责选择交互，create/edit/detail 负责各自的提交与错误路径，feature panel 以两条完整 toggle 交互守 heartbeat/cron 可见状态，prompt preview 各入口只守自身请求。删除整页 pill 重复和静态 i18n 文件；详情测试由 29 条收敛为 15 条，feature panel 由 7 条收敛为 2 条。
- Rationale: 每个风险只保留最接近故障源且仍能观察用户结果的 owner，可避免同一 form 重构同时击穿多组文件；table case 仍覆盖 heartbeat cadence 的有值/缺省 normalization，而不复制 setup。
- Evidence:
  - Tests: Agent create/edit/detail/features/allowlist/API 与 settings API 共 7 files、43 tests 全绿（2.95s）。
  - Entry: jsdom 真实 create/edit/detail routes 与组件交互；API adapter 直接观察 account、agent config、heartbeat/source/skills/channel 请求与 normalized response。
  - Frontend State Matrix: default、empty、error、disabled、submitting、conflict、offline 与 nullable cadence；visual/mobile N/A（无 UI delta）。
  - Browser QA: N/A；仅测试资产改动，未改组件或 UI。
  - E2E/Regression: 保留 create/edit/save/refetch、direct chat、skills usage、prompt preview、feature-tool linkage 与 empty allowlist regression。
  - Visual/Interaction: Testing Library 以 role/label/pill selection 驱动交互；无截图或 reference。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 提交。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R3 审计 channel/realtime owner，并运行 settings 全域、build 与 scope 门禁。

## R3 — 收敛 channel 状态并完成全域门禁

- 状态: DONE
- Context: channel slice 的 Feishu lifecycle、诊断、离线 desired state、删除恢复与 realtime cache 都是 current 风险；其中一条测试只锁 mobile CSS/bottom-sheet class，另一个文件用未进入 current catalog 的 Webhook provider 重复 create/edit/diagnostics。
- Decision: 保留 Feishu 添加、编辑、secret replacement、连接/失败/last-known、诊断 unknown-vs-missing、删除与 retry recovery；保留 agent/node WS event filtering 与 cache/page 状态更新。删除 mobile class 终态与假想 Webhook provider 文件，并清理保留测试中的 milestone fixture 名和 CSS class 断言。
- Rationale: current spec 明确本期 catalog 只有 Feishu；通用 provider 数据模型仍由 Feishu 的完整 create/update/status 请求经过，虚构第二 provider 不代表可交付用户路径。响应式视觉没有产品 delta，应由真实 UI 验收或 foundation owner，而不是 class 名承担契约。
- Evidence:
  - Tests: channel/realtime 定向 5 files、24 tests 全绿（1.56s）；最终 settings 全域 18 files、79 tests 全绿（4.05s）。
  - Entry: `AgentChannelsPanel` 经过真实 Feishu add/edit/connect/fail/offline/remove/retry 状态；WS consumer 接收 channel/node status event 并更新 query cache 与 Nodes 页面。
  - Frontend State Matrix: default、empty、error、disabled、submitting、offline/last-known、limited/unknown diagnostics、deleting/retry 与 realtime flip 均保留；mobile/desktop visual N/A（无 UI delta）。
  - Browser QA: N/A；派发 reference contract 与 design 都标明零 UI delta，本 milestone 只改测试资产。
  - E2E/Regression: settings Vitest `18 passed / 79 passed`；production build `tsc -b && vite build`，501 modules transformed，通过，仅有既存 chunk-size warning。
  - Visual/Interaction: 交互测试通过按钮、表单、dialog、alert 和可见状态驱动；已移除 CSS class/bottom-sheet 终态，无截图或 prototype。
  - Prototype Comparison: N/A。
  - Scope: 开工基线 `8ceeb39eb` 为 `25 files / 6036 lines / 132 tests`；rebase 到 `5dbf1b23f` 后最终为 `18 files / 4226 lines / 79 tests`。`rg` 确认 settings tests 不再含 milestone/bugfix 命名或 CSS class 断言；相对最新 unit base 仅 M15 文档与 settings test 文件变化。
  - Docs/Diff: `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` 通过（220 maintained Markdown sources、65 required routes）；`git diff --check` 通过。
- Limit: Vitest 输出仍含基线已有的 React `act(...)`、jsdom WebSocket/user-stream fetch 与 `--localstorage-file` 告警；本 milestone 不改 M16-owned harness 或产品源，未把这些环境输出提升为行为失败。build 的大 chunk warning同样是既存非阻塞项。
- Rollback: 回退 R3 提交。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: 集成到 `unit/refactor-489`。

## Promotion Candidates

None.
