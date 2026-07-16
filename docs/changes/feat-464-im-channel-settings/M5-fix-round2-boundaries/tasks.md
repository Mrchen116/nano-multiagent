# M5: Round 2 boundary hardening — Tasks

> 对齐: ../design.md v12

## 目标

封住 Round 2 verifier 指出的 Gateway 上行身份与 manifest 原子性边界，并把同一批复核发现的明文回流、应用失败投影、离线 stale 展示和状态 outbox 无界增长一起固化为可重复回归。完成后，错误 owner、错误 node、残缺 manifest、缓存提交失败与旧 incarnation 均不会被呈现或推进为成功状态。

## 退出标准

- [x] 所有 Gateway→IM node-scoped 帧在业务分发前统一校验当前 websocket 注册关系、token owner、连接 owner、持久 owner 与 payload node；拒绝路径不改 DB、不唤醒 waiter、不广播。
- [x] 绑定完成后重新校验已注册 websocket；错误 owner 的 socket/key 被逐出且不下发 manifest。
- [x] legacy secret 迁移后，agent 同步、token 刷新和 owner open-id 回写共享同一个脱敏 config owner；后续写盘不恢复 `appSecret` 或含密备份，`credentialRef` 保留且权限为 `0600`。
- [ ] manifest 在任何 reconcile/stop/cache/head 变更前完成全量结构、generation、key、envelope 与 opener 校验；任一成员失败时整个 manifest 返回 `retryable_failed`。
- [ ] cache commit 失败不会投影为已应用/当前连接；错误重载后仍可见，在线按同 revision 有界自动重试，只有 commit 成功才投影 applied；失败结果 ACK 不丢必需 outbox。
- [ ] node offline 且 `observed.status_stale=true` 时，connected/limited/failed 都明确显示“最后已知状态/节点离线”；pending/failed/retry 状态优先级不被覆盖，375px 可用。
- [ ] 新 status incarnation 原子替换旧未确认 barrier/snapshot；旧 outbox 不重放、不无界增长，晚到 ACK 幂等，重启后仍有界。
- [ ] 所有新增永久回归文件不超过 400 行；窄测、非 e2e 全量、前端 test/build/ruff、关键 e2e 与真实浏览器证据完成。

## 测试策略

- 被测行为（来自退出标准）：上行身份零副作用拒绝、绑定后 owner 重校验、legacy secret 不回流、manifest 全量预校验、cache commit 失败投影和有界重试、offline stale 展示、status incarnation 有界替换。
- 已有测试在：`tests/im_service/integration/test_gateway_auth_boundary.py`、`tests/unit/personal_assistant/test_channel_legacy_migration.py`、`tests/unit/personal_assistant/test_channel_credential_recovery.py`、`tests/unit/personal_assistant/test_channel_manifest_store.py`、`tests/unit/personal_assistant/test_channel_status_outbox.py`、`tests/unit/IM/test_channel_status_projection.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-diagnostics.test.tsx`（扩展）；若某文件接近 400 行则按用户可观察行为新建同层测试文件。
- 落层/目录/marker：`tests/unit/`、`tests/integration/`、`tests/im_service/integration/` 与前端 Vitest；关键真实链路使用既有 `e2e` marker/脚本，不新增仅验证 mock 自洽的 e2e。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 IM + Gateway + Vite 高位端口浏览器截图、console/network 检查与 prototype 对照，落在 `M5-fix-round2-boundaries/evidence/`。

用户路径分类：
- critical-path：channel manifest 下发、Gateway 应用、结果回报与状态投影，永久回归 + 关键 e2e。
- normal-ui：离线 stale 状态和失败详情，永久 Vitest + 真实浏览器临时验收。
- visual-only：stale 徽标、详情与 375px 布局，真实浏览器截图。
- bug-regression：Round 2 verifier 与 code-reviewer 发现的所有边界，均落永久回归。

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 已连接在线状态维持既有表现 |
| loading | 不在 M5 改动，复跑既有面板测试 |
| empty | 不在 M5 改动，复跑既有面板测试 |
| error | cache apply failed 显示持久错误；offline stale 不伪装为当前 failed |
| disabled | disabled/disable pending 优先级不回归 |
| submitting | reconnect/retry 投影优先级不回归 |
| permission denied | limited 作为最后已知状态明确标注 |
| long content | 失败详情和 stale 文案允许换行且不溢出 |
| missing/nullable data | status_stale 下缺少 diagnostics 仍有明确 fallback |
| mobile viewport | 375px 真实浏览器截图与 Vitest media-query 覆盖 |
| desktop viewport | 1440px 真实浏览器截图与状态对照 |
| dark mode（如项目支持） | 项目无独立 dark-mode 合同，N/A |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 跨 owner/node 上行绕过 | 真实 websocket integration + handler 零副作用断言 | 是 |
| 残缺 manifest 部分应用 | manager/store unit regression | 是 |
| cache 失败被误报成功 | store + IM projection + reconnect retry regression | 是 |
| 离线旧状态冒充当前状态 | Vitest + 真实浏览器状态矩阵 | 是（截图为一次性证据） |
| incarnation 无界增长 | outbox 文件重载 regression | 是 |

Prototype / Reference Contract：
| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `prototype.html#channel-connected` / `#channel-limited` | must-match：在线 current 状态结构不回归 | 1440px 状态截图 + 文案对照 | worker |
| `prototype.html#channel-pending` / `#channel-failed` | must-match：待应用/失败优先级和可操作信息 | 状态回归 + 1440px 截图 | worker |
| `prototype.html#channels-mobile` | must-match：375px 单列卡片与操作可用 | 375x812 截图 + 交互检查 | worker |

## Roadpoints

### R1 — 统一 Gateway 上行身份边界

- 步骤：在 websocket 业务分发前以当前 socket 为根验证注册 node、token owner、连接 owner、持久 owner 与 payload node；连接管理器为所有上行帧补齐 node_id；绑定后的初始化先重校验 owner，失败则逐出连接和 key。
- 验证：跨 owner/node 的 heartbeat/report/waiter/broadcast/channel-result 请求均被拒绝且零副作用；绑定前注册的错误 owner socket 不获 key/manifest。
- 状态：完成。真实 websocket 回归覆盖跨 owner heartbeat 的 DB/广播隔离、waiter 隔离与 bind 后错误 socket/key 逐出；所有非 register 帧统一经过 socket-rooted guard。

### R2 — 统一脱敏运行时配置 owner

- 步骤：让 migration、agent config sync、token refresh 和 Feishu owner binding 共享线程安全 config owner；迁移成功后原子替换内存快照，所有敏感阶段写盘走安全 writer。
- 验证：迁移后依次触发同步、刷新和回写，主文件及备份无明文 secret，`credentialRef` 与 `0600` 保持。
- 状态：完成。Gateway composition root 只创建一个 `RuntimeConfigOwner`，迁移、Agent sync、token rotation 和 owner binding 均在同一锁内基于最新不可变快照变换；落盘成功后才发布新快照，后续写回不再复活旧 `appSecret`。

### R3 — Manifest 全量预校验与原子失败

- 步骤：拆出严格 validation/prepare 阶段，完整校验顶层数组、每个 channel/removal mapping、revision/key/envelope/opener 后才调用 manager。
- 验证：缺字段、错误类型、多成员后项失败、generation/key/opener 失败全部 `retryable_failed`，旧 runtime/cache/head 不变。

### R4 — 应用失败投影与有界同 revision 重试

- 步骤：IM projection 纳入 manifest head/apply error；retryable result ACK 不清失败 outbox；在线连接对 retryable reconcile 做有界同 revision 重试，成功 cache commit 后再清错并投影 applied。
- 验证：故障注入 cache commit 首次失败、重载、自动重试成功与重启场景，期间 UI/API 从不报 current success，最终仅成功 commit 后 applied。

### R5 — 离线 stale UI

- 步骤：调整连接卡片状态优先级和文案，offline + stale 统一呈现“节点离线/最后已知状态”，保留 pending/failed/retry；补齐 apply error 展示。
- 验证：connected/limited/failed stale、pending/failed precedence、长错误和 375px Vitest；真实浏览器 desktop/mobile 对照 prototype 并记录 console/network。

### R6 — 有界 status incarnation 与全量门禁

- 步骤：新 barrier 原子替换旧 incarnation，清理 legacy retired 结构；晚到 ACK 作为幂等 no-op；重载只保留当前 barrier/snapshot。完成全套 gate/e2e/evidence。
- 验证：连续多 incarnation 不增长、旧 ACK 不解锁、最新 ACK 正常；ruff、非 e2e pytest、前端 test/build、关键 e2e、测试命名/行数 contract 全绿。
