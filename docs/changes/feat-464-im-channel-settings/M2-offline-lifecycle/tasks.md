# feat-464-M2: 离线收敛、迁移与完整生命周期 — Tasks

> 对齐: ../design.md v10

## 目标

让 external channel 在节点离线、Gateway/IM 重启、旧 YAML 迁移、启停/重连/删除与 ACK 丢失下仍按完整 manifest 收敛；真实 Agent detail → 通道入口持续展示“已保存”和“已应用”的差异，并只在 runtime/removal result 确认后进入停用或空态。

## 退出标准

- [ ] M2-E1：节点离线时新增、修改、启用、停用、删除均保存并显示“等待节点应用”，覆盖 offline create→delete-before-first-sync、reload removal pending、zero-item removal/result 后才空态。
- [ ] M2-E2：节点重连后无需再次保存，完整 manifest 自动收敛为真实终态。
- [ ] M2-E3：停用确认后实际停止收发，observed 后才显示已停用；重新启用无需重填 secret 并进入 connecting。
- [ ] M2-E4：手动重连展示稳定 connecting/reconnecting 与结果；离线时返回可理解反馈；credential/Bot/worker failure 可操作。
- [ ] M2-E5：删除确认后保留 removing 卡片，stop/cache failure 可见且同 revision 可重试；applied 后才移除卡片且影子会话/历史不级联删除。
- [ ] M2-E6：旧 YAML 首次上线自动 bootstrap，人工 bind-confirm 保持同一 WS 即触发且最多一次；初始化后空 manifest 不复活删除配置；IM 离线可从密文 cache 启动。
- [ ] M2-E7：重复/stale manifest、离线最终态、半迁移失败、node/key mismatch、原子文件、export-legacy、delete-no-cascade、per-token outcome 跨 revision/retention 终态、e2e key/cache 隔离清理全部受测。
- [ ] M2-E8：原型 `#channel-pending/#channel-actions/#channel-disabling/#channel-disabled/#channel-deleting/#channel-reconnecting/#channel-failed` 有真实浏览器证据与逐项对账。

## 测试策略

- 被测行为（来自退出标准）：M2-E1..M2-E8；HTTP DELETE/PATCH/action 与 Gateway WS 是跨边界入口，Agent detail → 通道页是真浏览器入口，旧 YAML/export 是 CLI/配置入口。
- 已有测试在：`tests/unit/IM/test_agent_channels.py`、`tests/im_service/integration/test_agent_channels_api.py`、`tests/integration/test_channel_reconcile.py`、`tests/unit/personal_assistant/test_channel_manager.py`、`tests/unit/personal_assistant/test_local_store.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`、`im-agent-config-api.test.ts`（扩展）；无持久 manifest/outbox 与 export 覆盖，新建 `tests/unit/personal_assistant/test_channel_manifest_store.py`、`tests/integration/test_channel_bootstrap.py`，理由：这是新持久化协议/迁移入口，现有测试文件已接近职责或行数边界。
- 落层/目录/marker：纯 store/cache/manager 在 `tests/unit/`，marker 无；HTTP/WS/bootstrap 在 `tests/integration/` 与 `tests/im_service/integration/`，marker 无；真 Gateway/浏览器旅程为 durable 临时验收证据，不新增永久 e2e 文件。
- 可选依赖 importorskip：无；项目环境已安装 cryptography、lark-oapi、Playwright CLI/Chromium。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器交互仅经 Playwright CLI session；截图、snapshot 摘要、console/network/DB/runtime/cleanup 报告落 `M2-offline-lifecycle/evidence/`。

### 用户路径分类

- `critical-path`：离线保存 → 重连自动应用；停用/启用；重连；删除 pending/failed/retry/applied；用 HTTP/WS/frontend regression + 真栈浏览器验收。
- `bug-regression`：offline create→delete-before-sync、result ACK 丢失、retention 后 terminal、manual bind 同 WS bootstrap、空 manifest 不复活。
- `visual-only`：offline banner、状态 pill、确认框与动作层级；用 desktop screenshot + Prototype Comparison。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | connected 卡片动作菜单与编辑入口 |
| loading | 复用 M1 query loading；本 M2 回归不改变 |
| empty | removal applied 之后才进入空态 |
| error | reconnect offline、delete stop/cache failed、credential/Bot/worker failed |
| disabled | disabling 与 observed disabled 分开；re-enable connecting |
| submitting | disable/delete confirm 后 mutation disabled/pending |
| permission denied | N/A，权限诊断归 M3 |
| long content | actionable failure 文案可换行、不遮挡动作 |
| missing/nullable data | observed 缺失投影 pending；removal 无 secret/config 明文 |
| mobile viewport | N/A，完整 375×812 归 M3；M2 保持动作可换行 |
| desktop viewport | 1440×1000 覆盖全部 M2 must-match 锚点 |
| dark mode（如项目支持） | N/A，当前产品/原型仅 light |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| encrypted cache/outbox 原子性与 mismatch | unit + Gateway restart integration | 是 |
| removal pending/failed/retry/ACK retention | store/unit + HTTP/WS integration | 是 |
| legacy bootstrap/credentialRef/export | unit + same-WS bootstrap integration + CLI smoke | 是 |
| offline lifecycle UI | frontend interaction regression + 1440px 真浏览器 | 交互是，截图否 |
| 停用/删除实际阻断收发与历史保留 | manager/HTTP integration + 真栈 DB/runtime | 是 + durable evidence |
| worktree key/cache 隔离清理 | e2e script contract + 真脚本 cleanup | 是 + durable evidence |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `#channel-pending` | must-match：desktop + node offline；“节点上线后自动应用”；无内部 revision；M2-E1/E2 | 1440×1000 真入口截图 + DOM/DB 对账 | worker |
| `#channel-actions/#channel-disabling/#channel-disabled` | must-match：disable confirm → pending/disabling → observed disabled；re-enable → connecting；delete confirm；M2-E1/E3/E5 | 确认框、disabling、disabled、re-enable 截图与网络报告 | worker |
| `#channel-deleting` | must-match：offline reload pending + stop failure/retry + applied 后空态；M2-E1/E5/E8 | 删除 confirm、pending reload、failed/retry、empty 截图与 receipt DB 对账 | worker |
| `#channel-reconnecting/#channel-failed` | must-match：stable reconnecting + actionable credential/Bot/worker failure；M2-E4 | reconnect/failure 截图 + API/console/network 报告 | worker |
| provider icon、阴影和过渡时长 | may-adapt | 沿用现有 IM token/card density，记录偏离 | worker |
| 未来 provider 与 Web IM | out-of-scope | DOM/截图确认未出现 | worker |

## Roadpoints

### R1 — Gateway 密文 manifest、可靠 outbox 与完整调和

- 状态: DONE
- 步骤: 新增原子 `ChannelManifestStore`（node/key header、applied head、per-token result/status outbox），扩展 `ChannelManager` 支持 cached startup、stale/retry、explicit removals、stop/cache failure 与同 revision 重试。
- 验证: 最窄 manager/store unit tests；M2-E2/E3/E5/E7 的 Gateway 侧。

### R2 — IM removal receipt、生命周期 API 与可靠 result ACK

- 状态: DONE
- 步骤: 实现 DELETE/reconnect/removal retry、pending/failed/applied view、zero-item removals、per-token ACK 与 retention/applied-head terminal，接入 WS correlated result。
- 验证: IM store/HTTP/WS integration；delete-no-cascade、offline create→delete、reload、同 revision retry 与 ACK replay。

### R3 — 旧 YAML bootstrap、credentialRef/export 与 e2e 隔离

- 状态: DONE
- 步骤: 实现 same-WS bootstrap request/response、IM 初始化事务、权威 cache 后移除 appSecret/写 credentialRef、半迁移回退、export-legacy；让 e2e-up/down 隔离并清理 key/cache。
- 验证: bootstrap integration、local config/export CLI tests、script contract；M2-E6/E7。

### R4 — 前端离线投影与生命周期交互

- 状态: DOING
- 步骤: channels API/model 增加 removal/actions；页面增加 offline banner、pending/disabled/reconnecting/deleting/failed 卡片、停用/删除确认与 retry。
- 验证: frontend interaction tests + build；M2-E1/E3/E4/E5。

### R5 — 真栈浏览器证据与总门禁

- 状态: TODO
- 步骤: 按 runbook 用高位隔离 IM/Gateway + headed Chromium 驱动离线/重连/启停/重连/删除旅程，落七锚点 evidence，核对 history/secret/outbox/key/cache/PID 清理。
- 验证: M2-E1..M2-E8 证据表；最窄、frontend、non-e2e、Ruff、build、test contract 全绿。
