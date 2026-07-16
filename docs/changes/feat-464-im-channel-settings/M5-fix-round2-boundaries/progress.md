# M5 — Progress

## R1 — 统一 Gateway 上行身份边界

- Context: 原实现只在少数 channel handler 检查 `(websocket, node_id)`，heartbeat/report/waiter/streaming 等帧可由已认证的另一 owner socket 通过 payload 选择目标 node；未绑定时注册的 socket 还会在后续他人绑定后被当作合法 key 来源。
- Decision: 所有非 `node.register` 帧在业务 handler 前统一从当前 websocket 反查唯一注册连接，校验 token owner、连接 owner、持久 owner及 payload node，并把可信 node 写回 payload；bind 初始化在注册 key/下发 manifest 前重校验 owner，失败时删除 key、移除连接并以 1008 关闭 socket。
- Rationale: 以 socket 注册关系而不是不可信 payload 作为路由 authority，才能让所有现有和未来业务帧默认继承同一 tenant 边界；bind 后复核关闭了 pre-bind race。
- Evidence:
  - Tests: `pytest -q tests/im_service/integration/test_gateway_auth_boundary.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_channel_status_broadcast.py tests/unit/IM/test_streaming_chain.py tests/integration/test_channel_reconcile.py tests/integration/test_channel_bootstrap.py` → `68 passed`；ruff focused → passed。
  - Entry: FastAPI `/im/ws/gateway` 真实 websocket 入口分别用 Alice/Bob bearer、两个 live node 验证：伪造 Bob node 的 heartbeat 被 1008 拒绝，Bob DB/广播序列不变；伪造 result 不释放 Bob waiter；Bob pre-register/Alice bind 后连接和 key 均被逐出。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 永久回归 `tests/im_service/integration/test_gateway_auth_boundary.py`，覆盖 HTTP auth + websocket + SQLite + bind callback 的真实组合入口。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 的 test/fix/docs commits。
- Commits: `d75825abf`（C1 red），`5bef039ef`（C2 green）。

## R2 — 统一脱敏运行时配置 owner

- Context: legacy bootstrap 原先只把脱敏后的 channels 写到磁盘，Agent config sync、IM token rotation 与 Feishu first-sender binder 仍各自捕获启动时 `LocalConfig`，后续任一写盘都会把旧 `appSecret` 整份带回。
- Decision: 在 Gateway composition root 建立单一 `RuntimeConfigOwner`，所有长期 config writer 都在同一重入锁内从最新不可变快照执行 transform；敏感写回统一经无备份、原子 `0600` writer，只有 durable save 成功才发布内存快照。
- Rationale: 根因是多个 writer 各自拥有可写的陈旧整文档副本，而不是 migration writer 自身不安全；统一 owner 从源头消除 lost update 和 secret resurrection，并保留 immutable config 的既有模型。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_gateway_build_runtime.py tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py tests/unit/personal_assistant/test_channel_legacy_migration.py` → `22 passed`；focused Ruff → passed。
  - Entry: regression 依次通过 migration、Agent config 持久化、refresh-token rotation 和 ownerOpenId binding 的真实文件写入口；递归扫描临时 config 目录无 `legacy-secret`，最终 YAML 只含 `credentialRef` 且 mode `0600`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_channel_legacy_migration.py::test_migrated_secret_never_returns_from_later_runtime_writers`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 的 test/fix/docs commits。
- Commits: C1=`0dc67c0f5`，C2=`522a8d7db`。

## R3 — Manifest 全量预校验与原子失败

- Context: applier 把缺失/非数组 `channels` 当空数组，并静默跳过非 mapping channel/removal；完整 snapshot 因此被截断后仍进入 manager，旧安全 runtime 会被当作 desired removal 停止并提交新 cache/head。
- Decision: 增加无副作用 prepare 阶段，严格验证顶层 owner/node/revision、必需 `channels[]`/`removals[]`、每项完整 wire shape、generation 和 node scope；结构全部通过后才解封全部 credentials，最后才允许调用唯一 lifecycle owner。
- Rationale: complete manifest 是 replace-all 契约，任何“跳过坏项继续”的解析方式都会把数据错误转成删除指令；原子 fail-closed 必须发生在生命周期和 cache 边界之外。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_channel_credential_recovery.py tests/integration/test_channel_reconcile.py tests/integration/test_channel_bootstrap.py tests/integration/test_channel_removal_reconcile.py` → `18 passed`；focused Ruff → passed。
  - Entry: 永久 regression 先运行并缓存 `ch-a`，再从真实 reconcile applier 入口分别提交 missing/non-array/non-mapping channels/removals、incomplete removal 和 opener failure；全部返回 `retryable_failed`，adapter events 仍只有 `start`、cache bytes 不变、applied head 保持 revision 1。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_channel_credential_recovery.py` 的 malformed/open failure 参数化回归。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R3 的 test/fix/docs commits。
- Commits: C1=`454e63cd6`，C2=`bc4379156`。

## R4 — 应用失败投影与有界同 revision 重试

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待补。
- Rollback: 回退 R4 的 test/fix/docs commits。
- Commits: 待补。

## R5 — 离线 stale UI

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence:
  - Tests: 待补。
  - Entry: 待补。
  - Frontend State Matrix: 待补。
  - Browser QA: 待补。
  - E2E/Regression: 待补。
  - Visual/Interaction: 待补。
  - Prototype Comparison: 待补。
- Rollback: 回退 R5 的 test/fix/docs commits。
- Commits: 待补。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-connected/#channel-limited` | 在线 current 信息结构 | 待补 | 1440px | 待补 | — |
| `prototype.html#channel-pending/#channel-failed` | pending/failed 优先级与可操作信息 | 待补 | 1440px | 待补 | — |
| `prototype.html#channels-mobile` | 375px 单列与操作可用 | 待补 | 375x812 | 待补 | — |

## R6 — 有界 status incarnation 与全量门禁

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待补。
- Rollback: 回退 R6 的 test/fix/docs commits。
- Commits: 待补。
