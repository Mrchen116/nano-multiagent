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

- Context: runtime 可以先进入 connected，随后 cache commit 失败；IM 旧投影只比较 observed channel revision，因而会把未持久化的配置显示为 applied。Gateway cache 只保留上次成功 manifest，进程若在人工 Retry 前重启还会启动旧配置。
- Decision: IM projection 以 node manifest applied head 为 current barrier，并把 current head 的结构化 apply error 暴露给 channel API；Gateway outbox 额外保存仅含 envelope 的 retry manifest，连接内对同 revision 做固定次数退避重试，重启时在启动旧 cache 前优先恢复 retry manifest，成功后才替换 committed cache、推进 local head并清 retry slot。
- Rationale: observed runtime 与 durable desired 是两条独立事实；只有两者都覆盖当前 revision 才能声称“当前配置已应用”。把 retry snapshot 持久在同一 0600 cache owner 中，既不泄漏明文，也避免进程重启把用户期望回滚。
- Evidence:
  - Tests: channel control / cache / status / reconcile 聚焦集合 → `42 passed`；`test_channel_apply_failure_projection.py`、`test_channel_apply_failure_recovery.py` 与 bounded connection retry 回归 → `5 passed`；focused Ruff、`git diff --check` → passed。
  - Entry: IM store 记录 current connected status 后接收 `cache_commit_failed` result，重新构造 store（等同页面/API reload）仍返回 `sync_state=failed + apply_error`；同 revision applied 后才清错。Gateway 首次 revision 2 commit 故障后重建 manager，启动证据只出现 `build:cli_new/start:feishu:agent-a`，cache/head 收敛到 revision 2且无 plaintext。
  - Frontend State Matrix: apply error 数据面已进入公开 channel response；具体卡片优先级和 viewport 归 R5。
  - Browser QA: 归 R5 统一完成。
  - E2E/Regression: `tests/unit/IM/test_channel_apply_failure_projection.py`、`tests/unit/personal_assistant/test_channel_apply_failure_recovery.py`、`tests/unit/personal_assistant/test_channel_status_protocol.py::test_retryable_manifest_is_reapplied_online_with_bounded_same_revision_retries`。
  - Visual/Interaction: 归 R5。
  - Prototype Comparison: 归 R5。
- Rollback: 回退 R4 的 test/fix/docs commits。
- Commits: C1=`695db273e`，C2=`577f14a85`。

## R5 — 离线 stale UI

- Context: API 能在节点离线后把 observed 标为 stale，但卡片仍直接以旧 `connection_state` 渲染 connected/limited/failed；而且节点状态 websocket 可能先于 channel query 失效，缓存中的 `status_stale=false` 会短暂继续冒充 current success。R4 新增的 durable apply error 也尚未进入前端类型与失败详情。
- Decision: 状态优先级调整为 manual reconnect → durable apply failed → desired pending/disabling → live node offline → observed runtime；只要实时 node 已离线，任一缓存 observed 都降级为 `Node offline + Last known status`，并使用最后状态时间。失败详情优先显示 channel `apply_error`，中英文文案同步补齐。
- Rationale: node online/offline 是“当前能否连接”的实时 authority，observed 只是在该边界内解释最后一次运行结果；因此不能等待 channel query 再次取得 `status_stale=true` 才撤销 connected。desired/apply 结果仍先于 stale snapshot，避免遮蔽用户尚待应用或持久失败的操作状态。
- Evidence:
  - Tests: `vitest run agent-channels-panel.test.tsx agent-channels-diagnostics.test.tsx agent-channels-provider-registry.test.tsx` → `19 passed`；`npm run build` → passed。
  - Entry: `AgentChannelsPanel` 在 node websocket 投影为 offline 时立即撤销 cached connected；参数化回归覆盖 connected、limited、failed，另覆盖 pending desired 与 durable `cache_commit_failed` 的优先级。
  - Frontend State Matrix: online connected 保留 current success；offline observed 统一为 last-known；pending 仍显示等待节点应用；apply failed 仍显示具体错误；limited 的最后已知标题保留权限受限语义。
  - Browser QA: 真 IM + 真 Gateway 高位端口先呈现 Feishu Connected；停止 Gateway 后同页自动出现 offline banner，卡片徽标变为 Node offline，正文为 `Last known status: Connected (node offline; not a current connection)`。唯一 console 503 来自预期的离线 capabilities 请求，无前端异常。
  - E2E/Regression: `agent-channels-panel.test.tsx` 包含 cached `status_stale=false` 但实时 node offline 的回归，防止 websocket/channel-query 失效时序复发。
  - Visual/Interaction: Playwright CLI 在 desktop 与 375×812 均确认单列卡片、离线横幅、last-known 时间和 Edit/Disable/Delete 动作可见；临时截图按任务约定未入库。
  - Prototype Comparison: `#channel-connected` 在线结构不变；离线态沿用 `#channel-pending/#channels-mobile` 的横幅、卡片和响应式层级，并只增加 last-known 降级说明。
- Rollback: 回退 R5 的 test/fix/docs commits。
- Commits: C1=`a65fee48c`，C2=`60bfa2879`。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-connected/#channel-limited` | 在线 current 信息结构 | 真 Gateway connected 后停止；同卡片降级为 offline last-known | 1440px，connected→offline | pass | 原型未定义 stale 专属文案，补充明确的非当前连接说明 |
| `prototype.html#channel-pending/#channel-failed` | pending/failed 优先级与可操作信息 | Vitest 参数化覆盖 pending/apply failed 优先于 stale | 1440px | pass | — |
| `prototype.html#channels-mobile` | 375px 单列与操作可用 | 真页面卡片、横幅、状态时间和动作均可见 | 375×812，offline stale connected | pass | — |

## R6 — 有界 status incarnation 与全量门禁

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待补。
- Rollback: 回退 R6 的 test/fix/docs commits。
- Commits: 待补。
