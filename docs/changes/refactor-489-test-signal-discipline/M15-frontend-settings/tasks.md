# refactor-489-M15: frontend-settings — Tasks

> 对齐: ../design.md 的 refactor-489-M15 行与决策 1、2

## 目标

保留设置页用户交互、API 成功/失败状态与 realtime 更新的最低层 Vitest 保护；删除 mock shape、旧原型布局、元素缺席和跨文件重复断言，使失败直接指向仍存在的设置风险。

## 退出标准

- [ ] Account、Policies、Agent、Node 与外部 channel 的读取、编辑、提交、失败/空态和 realtime 状态仍有直接行为保护。
- [ ] 不再以历史 milestone 名、CSS class、旧页面/控件缺席、mock fixture 字段或假想 provider 固化当前实现。
- [ ] 同一 allowlist、feature、prompt preview、鉴权或 i18n 风险只在最低合适 seam 保留一次。
- [ ] settings 全域 Vitest、frontend build、diff/scope 检查通过；不修改产品源或相邻 milestone。

## 测试策略

- 被测行为（来自退出标准）：用户能加载并修改 account/policies/agent/node；提交 payload 与成功、冲突、离线、空态、失败重试可观察；channel lifecycle/diagnostics/removal recovery 与 node/agent realtime 状态正确。
- 已有测试在：当前 `src/IM/frontend/src/features/settings/**/*.test.{ts,tsx}` 25 文件（改写、合并或删除）；不新建测试文件。
- 落层/目录/marker：前端 Vitest/jsdom 组件与 API adapter 测试，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；本次零 UI delta，不启动浏览器或保存视觉证据。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Account / Policies 读写与表单回退 | `account-page.test.tsx`、`policies-page.test.tsx`、`im-settings-api.test.ts` | rewrite-merge | 保留编辑、提交、Discard 与 API endpoint/auth；删除旧卡片布局、CSS、缺席控件和退役 `/users` 的重复负断言 | scoped Vitest |
| 设置 shell、mock 与旧 prototype 终态 | `settings-mock-contract.test.ts`、`settings-scroll-layout.test.tsx`、`settings-shell-mobile.test.tsx` | delete | mock fixture shape、历史 sub-nav 缺席与 viewport DOM 缺席不是当前用户/API seam；路由与 responsive shell 由 M16 foundation owner 负责 | tracked-reference + scoped Vitest |
| Agent 列表/创建/编辑/详情用户路径 | `agents-list-page.test.tsx`、`agent-create.test.tsx`、`agent-edit.test.tsx`、`agent-detail-page.test.tsx` | rewrite-merge | 保留打开、创建、保存、校验、冲突、错误、技能统计与直接聊天；删除 prototype 布局和历史迁移终态，合并 preview/features 重复 | scoped Vitest |
| allowlist、feature 与 prompt preview | `allowlist-selector.test.tsx`、`agent-tools-pill.test.tsx`、`agent-features-panel.test.tsx`、`agent-prompt-preview.test.tsx` | rewrite-merge | selector 直接守选择行为，详情页守保存 round-trip；删除整页 pill 重复，features 由每类一条完整交互覆盖，preview 请求每入口一次 | scoped Vitest |
| 设置页中文文案 | `agents-i18n-switch.test.tsx` 及 list/detail/create 中重复文案断言 | delete / rewrite-merge | 静态卡片标题与按钮翻译重复且绑定文案；全局 locale 切换由 M16 owner，M15 保留业务状态而非翻译快照 | scoped Vitest |
| Agent API normalization / endpoints | `im-agent-config-api.test.ts` | rewrite-merge | 保留 heartbeat cadence、source selection、skills usage 与 channel resource seam；用 table case 合并相同 normalization 分支 | scoped Vitest |
| Node 状态、编辑与 realtime | `nodes-page.test.tsx`、`nodes-page-status.test.tsx`、`nodes-page-ws.test.tsx`、`nodes-page-agents.test.tsx` | rewrite-merge / delete | 保留在线节点创建入口、alias PATCH、状态/错误/空态与 WS 翻转；删除 KPI/icon/mobile/CSS、控件缺席和“不请求 agent list”实现断言 | scoped Vitest |
| 外部 channel lifecycle 与恢复 | `agent-channels-*.test.tsx` | keep / rewrite-merge | 当前 Feishu 添加/编辑/状态/删除/诊断/恢复是独立用户风险；删除 responsive class/bottom-sheet 静态断言，合并仅服务假想 provider 的重复路径 | scoped Vitest |
| Agent/node realtime cache | `agent-status-ws-consumer.test.ts`、`nodes-page-ws.test.tsx` | keep | 分别直接守事件过滤/cache 更新与页面可见状态，是最低层 realtime 风险 owner | scoped Vitest |

### Frontend QA 分类

- 用户路径分类：test-asset refactor；无 UI delta。保留的 interaction/API-state regression 继续覆盖既有 normal-ui 与 bug-regression 风险。
- Browser QA：N/A；本 milestone 不改组件、样式、路由或产品源，design 明确零用户面且派发 `frontend_reference_contract=N/A`。

| 状态 | 覆盖计划 |
|---|---|
| default | 保留 account/policies/agent/node/channel 成功加载与提交 |
| loading | 现有 async query 到可交互状态的 `findBy*`/`waitFor` 覆盖；不单测框架 spinner |
| empty | 保留 agents/nodes/channels/skill usage 空态 |
| error | 保留 agent load/save/conflict、channel diagnostics/removal、node error |
| disabled | 保留必填校验、离线 node 与 provider uniqueness 等业务禁用 |
| submitting | 保留 mutation 调用与提交后状态；不固定瞬时按钮 class |
| permission denied | N/A（设置域由 bearer/owner API contract 负责，前端无独立状态） |
| long content | 保留 channel diagnostics/error detail；视觉溢出 N/A（无 UI delta） |
| missing/nullable data | 保留 heartbeat、skill usage、node/channel nullable 状态 |
| mobile viewport | 删除旧 prototype DOM 缺席断言；无 UI delta，不新增视觉覆盖 |
| desktop viewport | 保留交互组件测试；无 UI delta，不新增视觉覆盖 |
| dark mode | N/A（本 milestone 不改视觉） |

Prototype / Reference Contract：N/A（design 与派发均无前端原型/reference，且无 UI delta）。

## Roadpoints

### R1 — 删除设置壳、mock 与历史视觉终态

- 状态: DONE
- 步骤: 删除 mock/sub-nav/mobile/node-agent 缺席测试；把 account/nodes/list 收敛为真实交互和 API 状态。
- 验证: R1 scoped Vitest；确认保留 account save/discard、node edit/status/empty、agent list/open/error/empty。

### R2 — 合并 Agent 配置与 API 重复保护

- 状态: TODO
- 步骤: 合并 normalization cases、feature/allowlist/preview 重复，删除静态 i18n 与历史迁移断言；保留 create/edit/detail 保存与错误状态。
- 验证: Agent/API scoped Vitest，行数与测试清单对账。

### R3 — 收敛 channel 状态并完成全域门禁

- 状态: TODO
- 步骤: 保留 current channel lifecycle/diagnostics/recovery/realtime，删除 responsive class 和无 current provider 路径的重复；运行 settings 全域、build、scope/diff。
- 验证: settings Vitest、`npm run build`、tracked-path/scope、`git diff --check` 全通过。
