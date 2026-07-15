# feat-464-M3: 权限诊断、异常态与响应式验收 — Tasks

> 对齐: ../design.md v10

## 目标

让已连接飞书通道把应用身份的真实租户授权状态转换为可操作的 complete/limited/unknown 诊断，并让 IM 与 Agent detail → 通道页在乱序、离线、列表失败和 375×812 移动端场景下展示准确、可恢复的状态；最后从真实飞书测试应用证明连接、受限诊断和 stop/restart 均可用且不泄漏 secret、不产生重复 listener。

## 退出标准

- [x] M3-E1：基础链路可用但权限不完整时展示“连接受限”，逐项展示 raw scope、影响和修复方向；缺 `im:message.group_msg` 明确说明群背景上下文不完整。
- [x] M3-E2：scope API/解析失败显示“权限状态暂时无法确认”，不伪造 missing；该状态与 reconnecting/failed 连接故障分层展示。
- [x] M3-E3：channel list 读取失败显示 error 与 retry，不渲染空态。
- [x] M3-E4：真实 375×812 Agent detail → 通道页为单列卡片，添加/编辑/确认使用底部 sheet，关键动作可触达。
- [x] M3-E5：capability catalog 覆盖当前/legacy receive/send/history/reaction/chat 等价集合；仅 `grant_status=1 && scope_type=tenant` 进入 granted set；confirmed unauthorized、user identity、缺字段、未知 enum、API/解析失败分别受测；每个 accepted set 单独满足，只有完整 probe 全不满足才 missing。
- [x] M3-E6：同 revision 旧 incarnation/sequence 不覆盖新状态；offline N barrier 遇到 IM N+1/delete terminal ACK 后释放 FIFO、drop/quarantine 并继续 reconcile/result/status；`status_updated_at` 取 IM 接收时间、offline 标 stale，user-stream 仅失效目标 Agent channels query。
- [x] M3-E7：`#channel-limited/#channels-error/#channels-mobile` 有 durable 真实浏览器证据；Ruff、frontend test/build、`pytest -m "not e2e"` 与测试命名/行数门禁通过。
- [x] M3-E8：真实飞书测试应用完成连接、受限诊断、stop/restart smoke；IM DB、Gateway cache、HTTP、日志和证据无 secret，同一 Bot 无重复 listener。

> M3-E8 证据口径经 orchestrator 批准拆分：真实测试应用已完整授权，live 部分证明官方 complete probe、连接、stop/restart、secret 与单 listener；limited/unknown 通过 production-store → 真 IM HTTP → 真前端取证，不撤销外部权限，也不伪造成 provider live result。详见 `evidence/README.md`。

## 测试策略

- 被测行为（来自退出标准）：M3-E1..M3-E8；Feishu scope list/能力汇总是 provider 逻辑入口，Gateway status → IM WS/HTTP/user-stream 是跨边界入口，Agent detail → 通道页是真浏览器入口，真实 Feishu worker 是 live-critical 外部入口。
- 已有测试在：`tests/unit/test_feishu_client_scopes.py`、`tests/unit/personal_assistant/test_channel_manager.py`、`tests/unit/personal_assistant/test_channel_manifest_store.py`、`tests/unit/IM/test_agent_channels.py`、`tests/integration/test_channel_reconcile.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`、`agent-status-ws-consumer.test.ts`（扩展）；新建 `tests/unit/personal_assistant/test_feishu_capability_diagnostics.py`，理由：每个 catalog accepted set 都需参数化，既有 scope client 文件只覆盖 SDK 归一且新目录行为会超过单文件 400 行；新建 `agent-channels-diagnostics.test.tsx`，理由：既有 panel 测试已 267 行，M3 诊断/错误/移动状态是独立行为并需保持各文件低于 400 行。
- 落层/目录/marker：provider/manager/store 纯行为放 `tests/unit/`，marker 无；HTTP/WS/user-stream 接线放 `tests/integration/` 与既有前端组件测试，marker 无；真实 Gateway/浏览器/飞书旅程作为 durable 临时验收证据，不新增常规 pytest e2e 文件。
- 可选依赖 importorskip：`lark_oapi` 沿用既有 `pytest.importorskip`；前端/浏览器使用项目现有 Vitest 与 Playwright CLI。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：Playwright CLI session 与运行时检查命令；截图、console/network/DB/cache/log/worker/cleanup 摘要落 `M3-permission-diagnostics/evidence/`，临时脚本不提交。

### 用户路径分类

- `critical-path`：真实 connected → limited/unknown → reconnecting/恢复，status user-stream 自动刷新；HTTP/WS/frontend regression + 真栈浏览器 + 真飞书 smoke。
- `bug-regression`：scope name 存在但 grant/user identity 不满足、旧 incarnation/sequence 逆序、offline stale/removed barrier 堵塞 FIFO、list error 被误当空态。
- `normal-ui`：逐项诊断、重新检查/开放平台修复动作；组件交互回归 + 真浏览器。
- `visual-only`：375×812 单列、动作换行与底部 sheet；真实 viewport 截图 + Prototype Comparison。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | connected/complete 卡片继续沿用 M1/M2 |
| loading | channels query loading 文案保持 |
| empty | list 200 empty 才显示空态 |
| error | list 失败 error + retry，禁止空态 |
| disabled | M2 observed disabled 不与诊断混淆 |
| submitting | modal/sheet mutation pending 按钮 disabled |
| permission denied | limited confirmed missing 与 unknown 分开，连接仍 connected |
| long content | raw scopes/effect/remediation 可换行且动作可见 |
| missing/nullable data | missing checks/unknown probe 不猜测权限 |
| mobile viewport | 375×812 单列卡片 + 底部 sheet，动作可触达 |
| desktop viewport | 1440×1000 limited/unknown/list error |
| dark mode（如项目支持） | N/A，当前产品和原型只定义 light |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| tenant grant 归一与 current/legacy OR sets | provider unit 参数化 + 真 Feishu scope response | 是 + durable live |
| structured diagnostics 到 IM HTTP | manager/WS/HTTP integration | 是 |
| status incarnation/barrier/terminal ACK/FIFO | manager/store/IM connection integration | 是 |
| IM status 时间/stale/user-stream 精确刷新 | store + GatewayHandler + frontend consumer | 是 |
| limited/unknown/list error/retry | frontend interaction + 1440px 真浏览器 | 是 + durable screenshot |
| 375×812 单列与 bottom sheet | 组件结构断言 + 真浏览器截图/关键点击 | 是 + durable screenshot |
| 真飞书 stop/restart 与 secret/listener | 真 Gateway/Feishu runtime + DB/cache/log/PID scan | durable evidence |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `#channel-limited` | must-match：limited + unknown checks；逐项 raw scope、影响与修复；缺 `im:message.group_msg` 明确群背景上下文不完整；M3-E1/E2 | 1440×1000 真入口 limited/unknown 截图 + DOM/network/status payload 对账 | worker |
| `#channels-error` | must-match：list error + retry，不渲染空态；M3-E3 | 真入口受控 list failure/retry 截图 + network/DOM 报告 | worker |
| `#channels-mobile` | must-match：Agent detail → 通道，375×812 单列卡片 + 底部 sheet，关键动作可触达；M3-E4 | 375×812 真入口卡片、动作与 add/edit/confirm sheet 截图/交互报告 | worker |
| `#channel-reconnecting/#channel-failed` | must-match 延续 M2；权限 unknown 与连接故障分开；M3-E2 | 诊断卡与连接 pill/动作同时出现的 DOM/截图对账 | worker |
| provider icon、阴影和过渡 | may-adapt | 沿用现有 IM token/card/modal primitives，记录偏离 | worker |
| 未来 provider 与 Web IM | out-of-scope | DOM/截图确认未出现 | worker |

## Roadpoints

### R1 — Feishu 租户授权目录与结构化诊断

- 状态: DONE
- 步骤: 在 provider 层集中实现 grant 归一、current/legacy accepted sets、recommended current scopes、capability 汇总；将诊断从真实 Feishu REST client 接入 managed runtime status，覆盖 M3-E1/E2/E5。
- 验证: scope/client/catalog unit tests + manager/status focused integration；每个 accepted set 单独参数化，confirmed unauthorized/user/unknown 分支齐全。

### R2 — 状态因果、terminal ACK 与 user-stream 精确刷新

- 状态: DONE
- 步骤: 持久化 incarnation barrier/latest snapshot；按 status result outcome ACK/drop/retry/quarantine，确保 FIFO 继续；补 IM CAS/time/stale 与 `agent.channel.status_changed` 精确失效，覆盖 M3-E6。
- 验证: manifest store/manager/IM connection/ChannelControlStore/GatewayHandler/frontend consumer 的 focused unit/integration。

### R3 — limited/unknown/error 与移动端 sheet

- 状态: DONE
- 步骤: 实现通用诊断项、limited/unknown 投影、list error/retry 信息层级与 responsive bottom sheet；补中英文文案和 frontend API types，覆盖 M3-E1..E4/E7。
- 验证: frontend interaction tests + build；桌面与 375×812 真浏览器前置验收。

### R4 — 真栈浏览器、真实飞书 smoke 与总门禁

- 状态: DONE
- 步骤: 用 worktree 隔离 runbook 驱动 limited/unknown/list error/retry/mobile sheet；使用真实飞书测试应用完成连接、受限诊断、stop/restart，核对 secret/listener/cleanup；跑全门禁并落 M3-E1..E8 证据表。
- 验证: durable screenshots/reports + focused/full frontend + Ruff + `pytest -m "not e2e"` + naming/size contract。
