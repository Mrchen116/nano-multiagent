# M4 — Progress

## R1 — Gateway WS 身份边界与原子 bind

- Context: `/im/ws/gateway` 之前不校验 bearer，任意连接可用同一 `node_id` 覆盖内存 socket 与 credential key；bind 则在四个 repository commit 之间执行 owner guard，两个 owner 可同时通过。
- Decision: WS 入口只接受 bearer token，将认证 owner 注入 `GatewayHandler`；`node.register` 在写 socket/key/DB 前对 durable node owner 做 fail-closed 校验。新增 `BindingStore`，使用独立连接和 `BEGIN IMMEDIATE` 在读取 owner 前抢占写事务，并原子提交 bind/node/profile/default-entry。
- Rationale: 身份必须由传输边界派生而非 frame 自报；bind 的授权检查与写入必须属于同一 transaction owner，进程内锁无法覆盖多个 IM worker。
- Evidence:
  - Tests: `pytest -q tests/im_service/integration/test_gateway_auth_boundary.py tests/im_service/integration/test_bind_atomicity.py tests/im_service/integration/test_account_binding_api.py tests/im_service/contract/test_account_binding_contract.py tests/im_service/unit/test_gateway_handler.py` → 54 passed。
  - Entry: 两个真实注册用户 token 驱动 `/im/ws/gateway`；缺 token 在 node row 创建前 1008，错误 owner 收到 `gateway_owner_mismatch` 后 1008，原 connection owner/key 不变。
  - Frontend State Matrix: N/A（传输与存储边界）。
  - Browser QA: N/A（无 UI 变化）。
  - E2E/Regression: `test_cross_owner_concurrent_bind_has_one_atomic_winner` 用两个独立 SQLite connection 同时 confirm，证明一胜一 409 语义、同 owner 幂等，channel/head/key/removal 密文字节完全不变。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 同时回退 WS owner 注入与 `BindingStore`；不可只回退其中一个，否则会分别重新开放 socket takeover 或 bind TOCTOU。
- Commits: C1 `12681ca99`；C2 `8766659d9`。

## R2 — Credential re-entry 与本地 secret 安全写

- Context: manifest 解封失败时旧代码从 complete snapshot 中省略该 channel 后仍调用 reconcile，等价于删除；cache key mismatch 更在 `ChannelManager` 构造/startup 阶段抛错，阻止 Gateway 连 IM。legacy cleanup 还会先把含 secret 的主配置复制到普通 backup；export 则写完才 chmod。
- Decision: 新增 fail-closed manifest applier：任一 item key/envelope/open 失败即整份返回 `retryable_failed`，不调用 lifecycle reconcile、不提交 cache/applied head，并为目标 generation 上报 `credential_reentry_required`。foreign-key cache 原字节 0600 quarantine 后开放新的状态 outbox，使 Gateway 可继续连 IM。legacy cleanup/export 统一改用预创建 0600 temp、fsync、atomic replace、目录 fsync 且无 backup 的 sensitive writer。
- Rationale: complete-manifest 协议不能在部分解码后执行；旧密文既不能弱解密也不能覆盖，只能保留证据并向权威控制面请求重新输入。明文文件的权限必须在首次可见前确定。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_channel_credential_recovery.py tests/unit/personal_assistant/test_sensitive_local_config.py tests/unit/personal_assistant/test_channel_manifest_store.py tests/unit/personal_assistant/test_channel_legacy_migration.py` → 12 passed；另 `test_channel_reconcile.py/test_channel_manager.py/test_channel_status_outbox.py/test_gateway_im_resilience_e2e_wrapper.py` → 13 passed。
  - Entry: 单项 wrong key 的 revision 2 返回 retryable failure，revision 1 safe runtime 不 stop、cache/applied head 保持；cache key loss 不调用 opener，旧 cache 字节完整移入 `.credential-reentry.*`，startup 返回 failed recovery snapshot 而非抛错。
  - Frontend State Matrix: error 状态由稳定 `credential_reentry_required`/message 驱动；真实浏览器留 R6。
  - Browser QA: R6 执行真实产品恢复路径。
  - E2E/Regression: legacy CLI 回归确认最终 0600；sensitive writer 故障注入确认 destination 原字节与零 temp/backup plaintext。
  - Visual/Interaction: R6。
  - Prototype Comparison: `#channel-failed` 的稳定原因 contract 已由 wire 状态满足，视觉证据留 R6。
- Rollback: applier、quarantine 与 sensitive writer 必须成组回退；只回退 quarantine 会重新阻断连接，只回退 applier会重新把 desired 误删。
- Commits: C1 `26785d798`；C2 `b5275e125`。

## R3 — Provider preflight、metadata replay 与 activation retry

- Context: managed Feishu 只做 scope probe，invalid credential/Bot disabled/WS endpoint 错误最终都变成 `runtime_start_failed`；bot metadata 在 factory 阶段调用 binder，但 active generation 尚未建立，必然被拒；metadata 无 durable replay；skill activation 即使 HTTP 失败也被永久 memoized。
- Decision: 增加 provider-owned 三段 preflight（tenant token → bot info → SDK 同源 `/callback/ws/endpoint`），按飞书官方 code 映射 secret-free 稳定状态。factory 通过 `ProviderRuntimeBuild` 把 preflight metadata 带到 generation cutover 后，manager 更新 active spec、cache 并发送；IM 重连从 cache 重放。activation 仅成功才 memoize，失败不阻塞 runtime，并在 reconnect 重试。
- Rationale: provider 才拥有错误语义；runtime manager 只透传稳定 code/message。metadata 必须先关联已接纳 generation 才能 CAS，durable cache 是离线重放权威。activation 属附加能力，瞬态同步失败不应让监听器不可用。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_feishu_preflight_and_metadata.py tests/unit/personal_assistant/test_channel_manager.py tests/unit/personal_assistant/test_channel_manifest_store.py tests/unit/personal_assistant/test_gateway_im_config_sync.py` → 38 passed。
  - Entry: 10015 或带 `app secret invalid` 语义的 10014 → `feishu_invalid_credentials`；其余 10014 → `feishu_app_disabled`；230006 → `feishu_bot_disabled`；WS endpoint 非零 → `feishu_long_connection_unavailable`；错误文案不含 secret。
  - Frontend State Matrix: provider-specific status code/message 已进入既有 failed card；浏览器留 R6。
  - Browser QA: R6。
  - E2E/Regression: initial bot metadata 在 revision 1 cache 可见，模拟 IM offline 后调用 reconnect replay 得到同 generation patch；activation 第一次失败仍 applied，第二次 reconnect 成功且后续幂等。
  - Visual/Interaction: R6。
  - Prototype Comparison: `#channel-failed/#channel-reconnecting` wire contract 已满足，视觉证据留 R6。
- Rollback: preflight、runtime build、cache metadata 与 replay 应整体回退；只保留 preflight 会再次丢 bot identity，只保留 replay 会继续重放空 metadata。
- Commits: C1 `002407f82`；C2 `17aa5b4c7`。

## R4 — Worker 生命周期、背压与真实停用收敛

- Context: runtime candidate 在 `start()` partial failure 或 registry registration failure 后只从 map/registry 摘除，从未 stop；FIFO backpressure 只给 child 设置一个 SDK listener 不消费的 event，可能留下孤儿进程。`reconnect/reconcile/status-result/close` 虽是 async API，实际在 Gateway event loop 内同步 join；disable 又先发旧 incarnation 的 revision-N disabled，再发新 incarnation seq=1，IM 因果投影会收到两个互相冲突的终态。
- Decision: 所有 lifecycle async API 统一用 `asyncio.to_thread` 承载同步 per-channel lock 和 stop/join；candidate 只要已构造，后续任何失败都 best-effort invalidated-stop。worker start 自身也在 ready/thread 初始化失败时自回收，并在 terminate 后仍存活时 kill。`event_backpressure/worker_crashed` 由独立 supervisor 以 100/200/400ms 三次有界重启，第四次只回收不再重启；desired spec 独立保留，用户可 manual reconnect。disable 只在旧 PID 回收后发布一个新 generation、新 incarnation、seq=1 的 disabled barrier。
- Rationale: 生命周期 owner 必须同时拥有 candidate、active 与失败路径；仅发 terminal status 不等于关闭阻塞的 SDK WebSocket。stop/join 放到后台线程使 heartbeat/ACK 继续调度；retry budget 按连续未 connected 的 generation 计数，连接成功才清零，既避免紧循环也保留人工恢复入口。disabled 是一个未启动的新 observed instance，而不是旧 worker 的迟到状态。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_channel_lifecycle_failures.py` → 6 passed；真实 spawn child 覆盖 partial start、registry failure、non-cooperative backpressure、三次 retry budget、人工恢复、event-loop 30ms heartbeat 与 disable/re-enable 单 barrier。
  - Entry: backpressure 初始 listener + 3 个 retry PID 全部 `is_alive=False`，registry 为空且 600ms 后无额外 listener；同 desired 的 manual reconnect 建立唯一第 5 个 stable listener。
  - Frontend State Matrix: disabled 现在只有 revision-N/new-incarnation/seq=1 `instance_started=true`；真实卡片投影留 R6。
  - Browser QA: R6 执行 connected → disabled → enabled。
  - E2E/Regression: worker/manager focused 回归 16 passed；channel reconcile/removal/status/IM resilience 回归 49 passed；Ruff 与 `git diff --check` 通过，测试后无 `feishu-worker-*` 残留进程。
  - Visual/Interaction: R6。
  - Prototype Comparison: wire 因果已满足 `#channel-disabling/#channel-disabled` must-match；视觉对账留 R6。
- Rollback: supervisor、candidate cleanup、worker self-reap 与 async lifecycle seam 必须整体回退；只回退 supervisor 会重新留下 backpressure child，只回退 desired retention 会让 retry budget 耗尽后无法人工恢复。
- Commits: C1 `2cd48facc`；C2 `b94551986`。

## R5 — 前端 provider registry 真分派

- Context: 原 `CHANNEL_PROVIDERS` 只驱动 picker 的一行展示；picker 占用判断、表单字段、validation、create/update payload、连接/删除卡片摘要、诊断链接和 Feishu group effect 全部仍写死 `feishu/app_id/app_secret`。把第二 provider 加进数组会被 Feishu 占用一起禁用，即使进入表单也会错误提交为 Feishu。
- Decision: 新建 typed `ChannelProviderDescriptor`，集中描述 provider identity/icon/i18n、guide、config/credential fields、credential reset、validation/wire key、card/removal summary、diagnostic console/scope/effect override 与 connecting detail。panel 只接受 registry，按 resource/dialog 的 provider id 解析 descriptor；picker 唯一性按 provider 独立计算，create/update 统一经 descriptor serializer。生产 registry 仍只发布 Feishu；Vitest 注入完整 Webhook fixture。
- Rationale: provider 分支不能散落在 presentation 与 mutation 中，否则“在 picker 新增一项”会产生可选择但不可用的假扩展。声明式 field/wire schema 让 form、validation 与 payload 使用同一来源；provider-owned diagnostics 阻止非 Feishu 通道继承开放平台链接或特殊 effect。
- Evidence:
  - Tests: `agent-channels-provider-registry.test.tsx` 3 passed，覆盖 Feishu 已占用时 Webhook 仍可选、Workspace/API Token 独立表单与 validation、create/update `workspace_slug/api_token` payload、card summary 和 Webhook diagnostics；明确断言无 `app_id/app_secret`、无飞书链接/群背景 effect。
  - Entry: 生产 Feishu 既有 wizard/card/disable/delete/reconnect 7 tests 全绿；provider registry + i18n 合计 16 tests passed。
  - Frontend State Matrix: picker、create/edit、connected/limited card 与 provider-specific remediation 已由 descriptor fixture 覆盖；其余真实状态留 R6。
  - Browser QA: R6 复验 production-only Feishu registry 的 desktop/mobile 路径。
  - E2E/Regression: `npm run build`（tsc + Vite）通过；panel 生产组件不再出现 `provider: "feishu"`、`app_id/app_secret` 或 Feishu URL 硬编码。
  - Visual/Interaction: provider icon/label/summary、guide link、field labels 和 diagnostics link 均来自 descriptor。
  - Prototype Comparison: Feishu descriptor 保留原型飞书 picker/form/card；测试 provider 证明架构路径不依赖飞书外观。
- Rollback: registry schema、panel dispatch、credentials input 扩展与 i18n generic title 应整体回退；只回退 serializer 会再次提交错误 provider，单独回退 card/diagnostics 会恢复 Feishu 内容泄漏。
- Commits: C1 `55553386b`；C2 `742db037c`。

## R6 — 独立真实旅程与全门禁

- Context: DONE；隔离高位 IM + 真 Gateway + 本机真实飞书应用 + Playwright 重新执行 Round 1 主旅程。真实服务额外暴露 bot info 为 top-level `bot`、错误 secret 返回 10014/`app secret invalid`，以及 invalid cached provider 在连 IM 前中止三个 mock 未覆盖缺口；总门禁又发现旧 Gateway WS 测试夹具仍无 token/owner。
- Decision: preflight 同时接受官方 live top-level 与既有 nested bot shape；credential 分类结合 code 与 secret-free message 语义；cached provider start failure 保留 desired 并继续连接 IM。旧 WS/handler regression 全部改为显式 bearer/owner，不为通过测试放宽生产认证边界。
- Rationale: 真服务响应而不是 mock shape 才是 provider contract；10014 在 tenant-token endpoint 的具体 message 比 generic code 表更精确。cache 中的坏 provider 是需要控制面修复的 desired state，不应阻断控制面连接。测试夹具必须服从新认证边界，不能靠 handler 空 owner 绕过。
- Evidence:
  - Tests: `pytest -q -m "not e2e"` → 3447 passed / 1 skipped / 20 deselected；frontend 67 files / 620 passed；build 444 modules；Ruff PASS。Gateway handler 70 passed，所有真实 `/im/ws/gateway` 测试文件 71 passed。
  - Entry: connected → disabled 2.357s；无需 secret re-enable → connected 2.822s；真实错误 secret 显示 `feishu_invalid_credentials` provider 文案，恢复后 Connected；offline create/update/disable/enable 分别在 Gateway 返回后自动 applied。
  - Frontend State Matrix: desktop connected/failed/pending/disabling/disabled/empty、history；mobile 375×812 connected/picker 全部目检，无遮挡、内部 revision 或 secret。
  - Browser QA: 15 张真实入口截图与 JSON 结果见 `evidence/summary.md`；在线主旅程 console error 0，offline 旅程 mutation 均 200 并在重启后收敛。
  - E2E/Regression: 删除 200 后 channel resources=0，生产 conversation/message API 与浏览器仍可见原 history；cache/stop failure + same-revision retry 由真实 store/HTTP/WS integration 重跑；key/cache/config 0600、secret/SQLite/evidence scan 0 hit。
  - Visual/Interaction: 1440×1000 与 375×812 均目检；provider picker 生产环境只有 Feishu，失败原因、离线 banner、动作和历史正文可读。
  - Prototype Comparison: `#channel-pending/#channel-connected/#channel-disabling/#channel-disabled/#channel-deleting/#channels-empty/#channel-failed/#channels-mobile` must-match 状态均有当前或永久证据；may-adapt 继续沿用 IM token/card 体系。
- Rollback: R6 的三项 live 修复分别依赖 R3 provider seam、R2 cached recovery 与 R1认证边界；回滚必须同时移除相应 regression。截图/JSON 可单独移除，不影响运行时。
- Commits: live bot shape C1/C2 `b3847a34a`/`9cf53f7d5`；credential 语义 C1/C2 `d17d2773c`/`f636c0b29`；cached startup C1/C2 `77acec914`/`b823b0b36`；认证夹具 `0ffbd46e8`；evidence/C3=本提交。

### Current-HEAD cache-failure sign-off supplement

- Context: 原 R6 对 cache/stop failure 的最终说明仍引用永久 integration tests 和 M2 旧截图，不能独立证明当前 M4 HEAD 的生产前端、真实 HTTP、IM store 与 Gateway cache 在同一浏览器旅程内保持一致。
- Decision: 增加显式环境门禁的 `channel_cache_commit_failure.py` 验收夹具，只让第一次含 removal 的 `ChannelManifestStore.commit_manifest` 失败，随后的真实 retry endpoint 使用原 store；在隔离 IM/Gateway 中只创建 `enabled=false` 通道，避免启动 provider worker 或触达真实飞书。
- Rationale: cache 写故障需要发生在 production store seam 才能同时观察 IM receipt/head、Gateway cache、HTTP resource 和浏览器投影；一次性门禁夹具提供确定性，又不把故障开关注入生产配置/API。
- Evidence:
  - Entry: production baseline `6bc146c3c`；真实 `DELETE ...?channel_revision=1` 返回 200，receipt revision 3 随 cache failure 进入 `failed/cache_commit_failed`。
  - Frontend State Matrix: 删除失败卡片、具体 cache error、`Retry apply` 在整页 reload 后仍可见；失败前后都不显示 empty；retry applied 后才显示 empty。
  - Browser QA: `r6-current-head-cache-failure.png`、`r6-current-head-cache-failure-reloaded.png`、`r6-current-head-cache-retry-applied.png` 已用 1440×1000 原图目检通过。
  - E2E/Regression: retry `POST .../actions/retry` 返回 200；IM manifest head 从 `3/2` 收敛到 `3/3`，removal receipt 从 failed 收敛到 applied，Gateway cache 从 revision 2/旧 channel 收敛到同一 revision 3/零 channel；未分配 revision 4。
  - Safety: fixture 必须显式设置 `NANO_MULTIAGENT_TEST_ALLOW_FAULT_INJECTION=1`；隔离 config 只含 `web_relay`，待删通道为 disabled，无 provider worker/外部请求。
- Rollback: 删除验收夹具及本节 evidence 即可；production runtime 无新增 fault switch 或行为变化。
- Commits: fixture `a85ebdf0c`；evidence/C3=本提交。
