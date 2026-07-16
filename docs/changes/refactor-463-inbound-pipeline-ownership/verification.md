# Verification Report: refactor-463

Validated head: `7f95df14972f59065a7ef1fd0431b717f37c07ed`

Review round: 1

Mode: full

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 27/27 tasks；6/6 requirements 有实现投影 |
| Correctness | 17/20 scenarios covered；3/20 在同一 revision 切换边界偏离 |
| Coherence | 有偏离：D3/D4 的 active-run/binding ownership 不闭合，D6/D7/D8 有次要缺口 |

**结论：1 critical issue found. Fix before PR.**

## Completeness

- Tasks: 27/27 标记完成（M1 7/7，M2 12/12，M3 8/8）。源码、永久测试和 durable evidence 均有对应产物。
- Spec 覆盖：motivation 的 6 组 Requirement、20 个 Scenario 全部能映射到生产实现；其中“动态配置在下一轮生效”“运行中插话”“active `/stop`”在配置 revision 于 active run 期间切换时不满足契约，见 CRITICAL-1。
- Delta-spec：`kernel / im / gateway / cli: no spec delta` 的**意图**成立。相对实施基线 `a6c0425818`，变更文件仅为 `src/personal_assistant/**` 24 个、`tests/**` 71 个、unit 文档 13 个；`src/agent/**`、`src/IM/**`、`src/coding_cli/**`、`SPEC.md` 和 `docs/specs/**` 均无改动。CRITICAL-1 的旧控制流也存在于基线，所以它不是 463 新增的用户行为 delta；但 463 的中心目标是把 binder/coordinator ownership 做闭合，当前实现仍未满足批准后的 D3/D4 与既有 current Gateway 契约，不能因此忽略。
- Prototype / Reference 覆盖：N/A；design 未声明前端原型或 must-match reference contract。
- Durable evidence：已审计 M1/M2/M3 四份 evidence。M3 记录真栈 `15 passed, 2 deselected`、slow `1 passed, 1 xfailed`，以及 stop/group/restart/background 子集 `6 passed`；没有把 fake/stub 冒充真栈。现有证据没有制造“active run 中途 publish+invalidate”这一交叉状态，因此不能覆盖 CRITICAL-1。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | `src/personal_assistant/gateway/inbound_pipeline.py:96-141`; `session_run_coordinator.py:333-433,488-522` | `test_inbound_pipeline_runs_four_steps_and_replies_via_origin_channel`; IM roundtrip | covered |
| Gateway 重启后续接原会话 | `src/personal_assistant/gateway/session_binder.py:126-209` | binder reuse、persistent binding、restart critical path | covered |
| 未知 Agent 路由仍被拒绝 | `src/personal_assistant/gateway/inbound_pipeline.py:106-107`; `agent_catalog.py:59-68` | `test_require_rejects_unknown_agent_without_fallback` | covered |
| 动态 Agent 配置在下一轮生效 | `agent_config_sync.py:624-638`; `agent_catalog.py:70-82`; `session_binder.py:126-242` | catalog/binder race 与 live config tests；**缺 active revision 交叉回归** | **偏离：active 时会错配新旧 session** |
| Agent 工具投递仍同步到正确直聊会话 | `internal_dispatch.py:113-200`; `session_binder.py:244-315` | `test_dispatch_handler_binds_direct_conversation_and_appends_history`; stale-ack test | covered |
| 未点名群消息只积累背景 | `inbound_pipeline.py:106-123` | `test_group_message_without_mention_is_ignored` | covered |
| 点名后带入此前群背景 | `session_run_coordinator.py:524-548` | group fanout/sender-prefix；prepared-parts exactly-once | covered |
| 同会话串行且跨会话并行 | `session_run_coordinator.py:139-198,290-363`; `run_queue.py:55-105` | `test_fallback_serializes_same_session_while_other_session_runs` | covered |
| 运行中插话被及时采纳 | `session_run_coordinator.py:139-198` | continuous steer / lost-steer tests；SDK steer contract；**缺 active revision 交叉回归** | **偏离：可生成 orphan + duplicate run** |
| `/stop` 中断活动运行 | `session_run_coordinator.py:200-247` | normal active-stop unit/e2e；**缺 active revision 交叉回归** | **偏离：可 interrupt 新 idle session 而非旧 active session** |
| 空闲会话收到 `/stop` | `session_run_coordinator.py:205-247` | idle direct 与 idle group tests | covered |
| 活着但安静的运行不被误杀 | `session_run_coordinator.py:641-708` | quiet heartbeat 与 real stall/release tests | covered |
| 有效图片正常进入本轮 | `image_attachments.py:49-98`; `session_run_coordinator.py:524-548` | resolver MIME/data-url 与 inbound image tests | covered |
| 图片下载、超限或损坏 | `image_attachments.py:74-98`; `session_run_coordinator.py:545-548,564-633` | fixed download/oversize/corrupt feedback + recovery | covered |
| 中间与最终回复不重不漏 | `session_run_coordinator.py:371-469,471-522,641-708` | lifecycle/output precedence、NO_REPLY、terminal tests | covered |
| 后台任务完成后回到原会话 | `session_run_coordinator.py:387-395`; `background_subscriptions.py:69-144` | ensure-once/replay/dedupe；真栈 background once | covered |
| 外部 channel 与影子会话投递边界不变 | `inbound_pipeline.py:143-174`; `session_run_coordinator.py:488-522` | external/shadow trigger-source 与 Feishu integration contracts | covered |
| IM 离线时外部 channel 仍可用 | `inbound_pipeline.py:143-161`; local outbound path | `test_local_channel_keeps_working_without_im_connection`; M2 live evidence | covered |
| 启动、停止和重连结果保持一致 | `src/personal_assistant/main.py:1058-1275` | runtime lifecycle/resource graph；restart/reconnect durable evidence | covered |
| 停止时已接纳的入站工作有明确结局 | `main.py:1144-1275`; `run_queue.py:112-220`; `session_run_coordinator.py:251-289` | shutdown graph、timeout isolation、active/queued terminal evidence | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 narrow `InboundPipeline` | 是 | `inbound_pipeline.py:55-141` 只保留 route/gate/shadow/delegation，无 run/media/subscriber state |
| D2 concrete revisioned `LiveAgentCatalog` | 是 | `agent_catalog.py:13-105`; config publish protocol `agent_config_sync.py:624-638` |
| D3 binder 唯一拥有 binding 与 stale guards | 部分 | 常规 reuse/create/semantic bind 已集中；但 `session_binder.py:217-242` 删除 active run 仍依赖的 row，而 coordinator marker 不保存该 binding，owner 边界没有闭合 |
| D4 coordinator 原子拥有 queue/steer/stop/terminal | **否** | `session_run_coordinator.py:133,156-174,205-227,359-363`：active marker 只有 run id，steer/stop 却重新向 binder 解析 session，不能代表一个完整 active transaction |
| D5 typed image strategy + coordinator exactly-once | 是 | `image_attachments.py:49-98`; `session_run_coordinator.py:524-548` |
| D6 O(1) seal + one 80% absolute deadline resource graph | 部分 | 顺序和 shared deadline 在 `main.py:1144-1275` 落地；admission timeout 的要求诊断未落地，见 WARNING-2 |
| D7 composition 一次构造，晚绑定只用合法 provider | **否** | `agent_config_sync.py:71-74,313-319`; `main.py:2392-2399` 仍用 mutable callback post-wiring，见 WARNING-1 |
| D8 公共测试面 + architecture deletion guard | 部分 | owner tests/contract 已落地，但未覆盖 CRITICAL-1 的跨 M1/M3 race，也未禁止 WARNING-1 的 callback assignment |
| D9 deep modules，不以 LOC 为 KPI | 是 | catalog/binder/coordinator/subscriber/tracker 均集中真实状态与不变量，未发现只同义转发的新增 façade |

### Prototype / Reference Contract

N/A。

## Independent checks

- `ruff check src tests`：passed。
- owner-focused pytest（catalog/binder/config/internal dispatch/fork/image/subscriber/dispatcher/coordinator/shutdown/tracker/contracts）：`75 passed`。
- SDK public steer contract：`2 passed`，确认 idle `steer=True` 会创建 fresh run，active steer 才返回 `injected=True`。
- `pytest -m 'not e2e' -n 4 --dist worksteal`：原始运行 `3357 passed, 1 skipped, 1 failed`；唯一失败为不在本 unit diff 的真实 `ddgs` 网络探针连接超时。排除该网络探针重跑：`3357 passed, 1 skipped`。
- 只读 stop 诊断：旧 `sess-1/run-1` active → publish/invalidate → `/stop` 新建 `sess-2`；严格 fake 表现为 `KeyError('sess-2')`、`interrupt_calls=[]`，旧 run 最终仍返回 `old still running`。
- 按 SDK 公共 fallback 语义的 steer 诊断：旧 `sess-1/run-1` active → publish/invalidate → 新消息先在 `sess-2` 创建 `run-2`（无人 stream），旧 run 结束后同一消息又普通 submit 为 `run-3`。
- `git diff --check a6c0425818..HEAD`：failed，见 SUGGESTION-1。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — active marker 与 revisioned binding 分属两个 owner，配置更新期间 stop/steer 会操作错误 Kernel session。** 状态序列是：① `session_run_coordinator.py:353-363` 在旧 snapshot 的 `sess-1` 提交 `run-1`，但 `_active_runs` 只存 `session_key -> run_id`（`:133`）；② config sync 在 `agent_config_sync.py:624-638` publish 新 revision，`session_binder.py:217-242` 删除旧 binding；③ coordinator 仍由旧 marker 判定 active，却在 steer (`session_run_coordinator.py:156-174`) 或 stop (`:205-227`) 中按新 snapshot 重新 resolve 出 `sess-2`。生产 SDK 明确规定 idle session 的 `steer=True` 会创建 fresh run（`src/agent/sdk/kernel.py:1071-1075,1090-1110`），因此 coordinator 随后的 queued fallback 会把同一 parts 再 submit 一次，前一个 fresh run 无 stream owner；生产 `interrupt(sess-2)` 则返回 `None`（`:1201-1216`），用户可能收到停止确认而旧 `sess-1/run-1` 继续执行。严格 fake 的 KeyError 只是提前暴露错误 session，不是问题来源。该控制流在基线 `a6c0425818:src/personal_assistant/gateway/inbound_pipeline.py:303-387,1001-1077` 已存在，所以不是 463 新增 delta；但它违反 motivation 的动态配置/插话/active-stop Scenario（`motivation.md:70-78,99-107`）、current Gateway 契约（`docs/specs/gateway/routing-delivery.md:86-122`）以及 D3/D4 对完整 active transaction 唯一 owner 的承诺（`design.md:122-153`）。**正确 owner 建议**：coordinator 的 active marker 必须是完整、不可变的 run-control handle，至少携带该 active run 的 `run_id + kernel_session_id` 以及执行 stop/steer/history 所需的原 snapshot/workspace 事实；active 控制路径只能用 marker 的原 binding，不得重新解析 current revision。新 revision 只影响旧 run terminal 后进入 normal admission 的下一轮。补一条 public pipeline/coordinator 永久回归：旧 revision run active → publish+invalidate → steer 和 `/stop`，断言只 interrupt 旧 session、没有 orphan/duplicate run、history/ack 归属正确，下一次 normal run 使用新配置。

### WARNING（应该修）

- **WARNING-1 — D7 要删除的 mutable callback post-wiring 仍存在。** `IMAgentConfigSync.on_agent_created` 仍是可变的 optional callback slot（`src/personal_assistant/gateway/agent_config_sync.py:71-74,313-319`），`build_runtime()` 构造后再赋值（`src/personal_assistant/main.py:2392-2399`）。这与 `design.md:196-210`“可直接提供的依赖不用 setter/mutable callback bag/None 后补”冲突，也让 M2 `tasks.md:17` 的删除闸不完整。把 dynamic-agent-created 通知作为构造期显式 dependency（或只读 provider）传入，按依赖顺序一次构造；增加 architecture contract 禁止对 owner 实例做 `on_agent_created = ...` 后置赋值。
- **WARNING-2 — admission settle 超时缺少 design 要求的 session/item 诊断。** `design.md:185-192` 要求该阶段超时时记录具体 session/item 后继续 Kernel close；`SessionRunQueue.settle_admission()` 只创建匿名 event waiter，并在 `src/personal_assistant/gateway/run_queue.py:117-142` 抛出通用字符串。shutdown 会继续，功能顺序正确，但现场无法定位卡在哪个 admission。让 waiter 保留 `session_key` 和稳定 item 标识，在 TimeoutError/log 中列出 pending admission；补 timeout 回归断言标识可见且后续 owner 仍执行。

### SUGGESTION（可以修）

- **SUGGESTION-1 — unit diff 未通过 whitespace gate。** `git diff --check a6c0425818..HEAD` 报 `M1-live-agent-session-ownership/evidence/live-stack.md:3`、`M3-session-run-coordinator/evidence/live-e2e.md:3` trailing whitespace，以及 `src/personal_assistant/gateway/shadow_sync.py:122` new blank line at EOF。清理这三处并重跑 `git diff --check`。

# Round 2

Validated head: `78333423bb2fe73b68d3002b24b4b1cba5fb47f6`

Review round: 2

Mode: full

Delta base: N/A

Inherited focus issues: Round 1 CRITICAL-1、WARNING-1、WARNING-2、SUGGESTION-1

Requires full verification: false

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 33/33 tasks；6/6 requirements 有实现投影 |
| Correctness | 19/20 scenarios covered；`send_message` 在 Gateway 重启并复用旧 session 后仍指向旧随机 listener URL |
| Coherence | Round 1 owner 缺口均已关闭；D3/D8 对 process-scoped dispatch capability 的 restart/reuse 边界仍不闭合 |

**结论：1 critical issue found. Fix before PR.**

## Completeness

- Tasks: 33/33 标记完成（M1 7/7，M2 12/12，M3 8/8，M4 6/6）。M4 四个 Roadpoint、永久回归与 durable evidence 均存在。
- Spec 覆盖: motivation 的 6 组 Requirement、20 个 Scenario 都有生产实现与测试投影；其中“Agent 工具投递仍同步到正确直聊会话”在“持久化 session 复用 + Gateway listener 随进程换端口”的合法状态组合下失败，见 CRITICAL-1。
- Delta-spec: `kernel / im / gateway / cli: no spec delta` 的意图仍成立。本轮 `src/agent/sdk/kernel.py` 的变化仅让既有 `enabled_tools=[]` API 保持显式零权限；未改变 IM API、session key、binding schema、reply-context serialization 或 channel 协议。CRITICAL-1 是实现未维持既有重启与工具投递契约，不应写成新 spec。
- Prototype / Reference: N/A；无前端、原型或 must-match reference contract。
- Acceptance artifact: `acceptance.md` 是 M4 修复前的 Round 1 历史输入；其 shutdown/reconnect/send_message finding 已由后续 M4 commits 和本轮独立检查重新对账，不把旧 verdict 当当前 head 证据。

## Round 1 issue closure

| Round 1 finding | Round 2 结论 | 独立证据 |
|---|---|---|
| CRITICAL-1 active marker 只保存 run id，publish 后 stop/steer 错 session | closed | `_ActiveRunHandle` 固定 `run_id + binding + agent`（`session_run_coordinator.py:74-80`）；active steer/stop 只用 handle（`:169-197,217-249`）；`test_active_run_keeps_original_session_across_config_publish` 通过 |
| WARNING-1 mutable `on_agent_created` post-wiring | closed | callback 只在 `IMAgentConfigSync.__init__` 注入（`agent_config_sync.py:72-105`；`main.py:2269-2305`）；architecture contract 禁止旧 assignment |
| WARNING-2 admission timeout 无 session/item identity | closed | queue item 分配稳定 `item-N`，waiter name 含 `session_key`/`item_id`（`run_queue.py:84-98,123-158`）；`test_admission_timeout_names_session_and_stable_item` 通过 |
| SUGGESTION-1 whitespace gate | closed | `git diff --check a6c0425818..78333423b` 无输出 |

## M4 confirmed-mechanism audit

| 机制 | 状态 | 生产边界与独立测试 |
|---|---|---|
| active run-control handle | covered | coordinator 固定原 binding/snapshot，publish 后 steer/stop 仍命中原 session；public coordinator regression 通过 |
| internal dispatch provenance | covered | binder 原子登记/捕获 session provenance（`session_binder.py:317-341`），handler 在 IM await 前捕获并在 await 后沿原 workspace/guard 完成（`internal_dispatch.py:141-223`）；旧 revision regression 通过 |
| fork provenance | covered | fork 通过 `capture_binding_provenance()` 捕获 binding/snapshot/guard（`session_binder.py:343-364`；`main.py:2975-3008`），publish race 不落 stale branch；两条 fork race regression 通过 |
| explicit empty allowlist | covered | Kernel 用 `enabled_tools is not None` 区分空列表与 legacy fallback（`src/agent/sdk/kernel.py:932-969`）；真实 Kernel 集成回归确认 request tools 为 `()` |
| heartbeat revision | covered | tick 从 catalog 捕获 snapshot，heartbeat cache 按 revision 失效并用 `create_agent_session()`（`heartbeat_scheduler.py:287-295,426-475`）；revision regression 通过 |
| old subscriber context | covered | manager callback 闭包持有 request 原 `ReplyContext`（`background_subscriptions.py:168-204`）；binding invalidation 后仍投递原目标的 regression 通过 |
| subscription seal / first foreground terminal | covered | existing ensure 优先于 seal，foreground terminal 使用 typed `SHUTDOWN_SKIPPED`（`background_subscriptions.py:79-119`；`session_run_coordinator.py:415-428`）；首次 terminal 不被反写成 failed |
| buffered terminal handoff | covered | subscriber 在 stop 后完成已 dequeue callback，再退出（`background_session_events.py:138-171,173-232`）；buffered/idle close regressions 通过 |
| cron admission linearization | covered | seal check 与 pending token registration 同一短临界区，drain 等 token settle（`cron_execution_service.py:490-598,620-704`）；blocked lookup race regression 通过 |
| threadsafe root registration window | covered | dispatcher 同时追踪 proxy、真实 loop task 与 registration acknowledgement（`inbound_dispatcher.py:19-30,91-140`）；proxy cancel/registration-window cleanup regressions 通过 |
| internal listener bind readiness | covered | runtime 成功 bind、读实际 socket 后才 publish/ready，bind error 直接启动失败（`main.py:994-1027`）；双 listener 与真实占端口 regression 通过 |
| actual listener URL in reused sessions | **not covered / fails** | 新 session 注入当前 URL，但 binder reuse 分支不刷新已持久化 Kernel metadata；见 CRITICAL-1 |
| IM shadow identity guard | covered | typed `external_identity.trigger_source == "im"` 在 shadow sync 前拒绝（`inbound_pipeline.py:143-172`）；typed guard regression 通过 |
| shutdown accepted terminal + IM ack drain | covered | shared deadline seal → settle → Kernel close → drains → outbound ack → IM close（`main.py:1051-1191`）；primary/steered terminal、outbound ack、resource graph regressions 通过 |
| IM reconnect | covered | heartbeat 在 receive loop admission 后启动（`im_connection.py:427-499`），supervisor 重建异常 maintenance loop（`main.py:1374-1419`）；slow-on-connected regression 与真栈 restart continuity 通过 |
| cron deep owner / config no-op | covered | `CronExecutionService` 持有 submit→delivery→terminal→awareness（`cron_execution_service.py:328-489`）；config durable/live 各自 diff（`agent_config_sync.py:526-542`）；owner-chain/no-op regressions 通过 |

## Correctness

| Requirement / Scenario | 实现与测试投影 | 状态 |
|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | `InboundPipeline.handle_inbound` → coordinator → reply context；direct routing tests | covered |
| Gateway 重启后续接原会话 | persistent binding + Kernel JSONL reload；本轮真栈 critical path `1 passed` | covered |
| 未知 Agent 路由仍被拒绝 | catalog `require()` 与 route guard；unknown-agent tests | covered |
| 动态 Agent 配置在下一轮生效 | config durable/live diff → publish/invalidate；concrete owner v1→v2 test | covered |
| Agent 工具投递仍同步到正确直聊会话 | provenance path 对新 session 正确；**restart 后复用 session 的 dispatch URL 仍是旧端口** | **not covered / fails** |
| 未点名群消息只积累背景 | narrow facade group gate + store append；group tests | covered |
| 点名后带入此前群背景 | coordinator destructive drain + sender prefix；exactly-once tests | covered |
| 同会话串行且跨会话并行 | queue + per-session transition lock；coordinator admission test | covered |
| 运行中插话被及时采纳 | active handle steer + follower lifecycle；continuous/lost-race tests | covered |
| `/stop` 中断活动运行 | active handle mark→interrupt→append→original reconcile；publish race regression | covered |
| 空闲会话收到 `/stop` | coordinator idle direct/group paths；stop tests | covered |
| 活着但安静的运行不被误杀 | liveness stream timeout owner；quiet/stall tests | covered |
| 有效图片正常进入本轮 | typed resolver + coordinator exactly-once；image tests | covered |
| 图片下载、超限或损坏 | typed failure + fixed control reply，不 submit；image failure tests | covered |
| 中间与最终回复不重不漏 | observer/tracker + coordinator terminal; NO_REPLY/failure tests | covered |
| 后台任务完成后回到原会话 | captured subscriber context + dedupe + buffered handoff tests | covered |
| 外部 channel 与影子会话投递边界不变 | typed trigger-source guard + external delivery tests | covered |
| IM 离线时外部 channel 仍可用 | local outbound path不依赖 connected IM；offline adapter tests | covered |
| 启动、停止和重连结果保持一致 | listener readiness + IM supervisor/receive-loop heartbeat；lifecycle/reconnect tests | covered |
| 停止时已接纳的入站工作有明确结局 | queue item terminal、steer follower terminal、delivery+IM ack drain；shutdown tests | covered |

## Coherence

| design 决策 | 遵守? | 代码证据与偏离 |
|---|---|---|
| D1 narrow `InboundPipeline` | 是 | `inbound_pipeline.py:55-172` 只做 route/gate/shadow/group append/delegation |
| D2 revisioned `LiveAgentCatalog` | 是 | copy-on-write snapshot owner 与 concrete config sync 无双源 |
| D3 binder 唯一拥有 binding/stale guard | **部分** | revision/provenance 已闭合；但 reuse (`session_binder.py:165-195`) 未使持久 session 的 process-scoped dispatch capability 收敛到当前 listener |
| D4 coordinator 原子拥有 queue/steer/stop/terminal | 是 | complete active handle、transition lock、follower terminal 与 single cleanup owner 均落地 |
| D5 typed image strategy + exactly-once | 是 | resolver 与 coordinator 调用时机分离，group/image 不重复消费 |
| D6 sealed resource graph + one deadline | 是 | admission、Kernel terminal、consumer/delivery/IM ack 的 owner 顺序和 timeout identity 已闭合 |
| D7 composition 一次构造 | 是 | callback 为构造期依赖；late IM resource 只用 provider；无私有 post-wire |
| D8 公共测试面 + deletion guard | **部分** | owner/public tests 与 contracts 完整；缺“持久 session reuse + listener URL rotation + send_message”永久交叉回归 |
| D9 deep modules, no LOC KPI | 是 | catalog/binder/coordinator/subscription/tracker/cron service 都拥有真实状态与不变量 |

### Prototype / Reference Contract

N/A。

## Independent checks

- Owner-focused pytest（revision/provenance/allowlist/heartbeat/subscriber/cron/dispatcher/listener/reconnect/shadow/config/shutdown/contracts）：`151 passed, 2 warnings`。
- `ruff check src tests`：passed。
- `pytest -m 'not e2e' -n 4 --dist worksteal`：`3390 passed, 1 skipped, 22 warnings`。
- 真 IM + Gateway + Kernel + LLM restart critical path：`test_context_survives_gateway_restart` → `1 passed in 17.76s`；fixture 使用隔离高位端口并完成 teardown。
- `git diff --check a6c0425818..78333423b`：passed。
- M4 新增 9 个 Python test/helper 文件，最大 253 行；`test_new_test_files_under_400_lines` 通过。
- 服务清理：本轮自启 stack 已执行 `e2e-down.sh`/fixture teardown；`.im.pid`、`.gateway.pid`、`.vite.pid` 均不存在，生成的未跟踪 `.gateway-state.json` 已删除。
- 真实 Kernel + `PersistentSessionBindingStore` 只读诊断：第一次 owner 用 URL `:41001` 创建 session；第二套 startup catalog/binder 在同一持久 row 上请求当前 URL `:42002`，结果 `reused=True`，但 `Kernel.get_session(...).metadata.gateway_dispatch_url` 仍为 `:41001`。该诊断未修改源码、测试或配置。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — ephemeral internal-dispatch URL 被持久化进 Kernel session，却没有在 Gateway restart/reuse 时刷新，导致续接会话中的 `send_message` 请求旧进程端口。** 生产 composition 用端口 `0`（`main.py:2215`），listener 成功 bind 后发布本进程实际 URL（`main.py:1001-1022`），coordinator 在新 binding admission 时读取 provider（`main.py:2430-2437`; `session_run_coordinator.py:619-649`）。但 `GatewaySessionBinder.resolve()` 的 reuse 分支只刷新 reply context 与 provenance（`session_binder.py:165-195`），完全忽略本次 `SessionBindingRequest.gateway_dispatch_url`；只有 create 分支才把 URL 写入 Kernel metadata（`:197-212`）。`SendMessageTool` 又在每次执行时直接从 session metadata 读取并 POST 该 URL（`tools/send_message.py:115-156`）。因此 Gateway 重启后可以正确复用原 session/历史，但原 session 的 URL 指向已退出 Gateway 的随机端口；工具会 connection refused，而“缺 URL fail-fast”无法识别 stale URL。本轮真实 Kernel + SQLite 诊断稳定得到 `reused=True / current=:42002 / metadata=:41001`，现有 listener tests只覆盖“新 session 使用当前 URL”和“双 Gateway 不冲突”，没有覆盖 restart reuse。该缺口违反 motivation 的 Gateway 重启连续性与 Agent 工具投递 Scenario（`motivation.md:61-78`），也使 M4 对“endpoint 与每个 session metadata 一致”的退出标准不成立。**正确 owner 边界**：当前 listener URL 是 process-scoped runtime capability，不能只作为 immutable durable session seed。由 binder/composition 与 Kernel SDK 的公开 seam 在复用 admission 时刷新/overlay 当前 capability，或让工具通过 live provider 解析；必须同时保留原 Kernel session/history，不能靠强制新建 session 回避。新增永久交叉回归：端口 A 创建并持久化会话 → Gateway owner restart 发布端口 B → 同 binding 续接 → 真 `send_message` 只访问 B、投递完成且 session id/history 不变。

### WARNING（应该修）

None.

### SUGGESTION（可以修）

None.

# Round 3

Validated head: `41577b479469e6e4325f3ef4e2dd0f12fb7f952f`

Review round: 3

Mode: full

Delta base: N/A

Inherited focus issue: Round 2 CRITICAL-1（Gateway restart/reuse 后 `send_message` 使用旧 durable endpoint）

Requires full verification: false

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 39/39 tasks 标记完成；6/6 requirements 有实现投影 |
| Correctness | 17/20 scenarios covered；同一 terminal-race 根因使 steer fallback 产生 orphan + duplicate run，影响串行、插话与不重不漏 |
| Coherence | Round 2 process-scoped endpoint 缺口已关闭；D4 的 atomic run ownership 与 D8 的 public-SDK regression 仍不闭合 |

**结论：1 critical issue found. Fix before PR.**

## Completeness

- Tasks: 39/39 标记完成（M1 7/7，M2 12/12，M3 8/8，M4 6/6，M5 6/6）。五个 milestone 的 tasks、progress 与 durable evidence 均存在；M3/M4 对“无 orphan/duplicate run”的退出声明在真实 SDK terminal race 下不成立，归入 Correctness/Coherence 的 CRITICAL-1。
- Spec 覆盖：motivation 的 6 组 Requirement、20 个 Scenario 都有生产实现和永久测试投影；“同会话串行且跨会话并行”“运行中插话被及时采纳”“中间与最终回复不重不漏”在同一合法 terminal race 下失败，见 CRITICAL-1。
- Delta-spec：`kernel / im / gateway / cli: no spec delta` 的结论仍成立。M5 把当前 listener URL 作为 process-scoped provider 注入既有 `send_message` 工具；没有改变 binding schema、session key、history、IM API 或 channel protocol。CRITICAL-1 是实现没有满足既有 Gateway 并发/回复契约和已批准 D4，不应改写成新行为 spec。
- Prototype / Reference：N/A；本 unit 无前端、原型或 must-match reference contract。
- Acceptance artifact：`acceptance.md` 是 M4 前的历史输入；Round 3 直接按当前 head、全部 milestone evidence、生产代码和独立测试取证，不复用其中旧 verdict。

## Round 2 focus closure

| Round 2 finding | Round 3 结论 | 独立证据 |
|---|---|---|
| CRITICAL-1 restart/reuse 后旧 session metadata 的随机端口让 `send_message` 请求旧进程 | **closed** | `InternalDispatchEndpoint` 是带锁的 process owner（`internal_dispatch.py:29-51`）；composition 在 Kernel 前构造并把 `current_url` 注入 PA tool（`main.py:2157-2166`; `product.py:375-409`）；listener bind 后 publish、shutdown 开始即 clear（`main.py:1001-1022,1051-1057`）；工具每次调用优先解析 provider，provider 存在但为空时 fail-fast，绝不回退旧 metadata（`tools/send_message.py:97-136`）。永久真实 Kernel + persistent binding + 两个真实 listener 回归保留同 session/history，明确断言旧 A 零请求、新 B 唯一收件（`tests/integration/test_send_message_restart_routing.py:149-234`）；本轮独立重跑通过。 |

## Correctness

| Requirement / Scenario | 实现与测试投影 | 状态 |
|---|---|---|
| 直聊消息仍由正确 Agent 在原目标回复 | narrow pipeline route → coordinator → captured reply context；direct routing/IM tests | covered |
| Gateway 重启后续接原会话 | persistent binding + Kernel JSONL reopen；M5 restart integration 保留 session id/history | covered |
| 未知 Agent 路由仍被拒绝 | catalog `require()` 与 pipeline route guard；unknown-agent contract | covered |
| 动态 Agent 配置在下一轮生效 | revisioned catalog publish + binder generation/invalidation；config/provenance races | covered |
| Agent 工具投递仍同步到正确直聊会话 | live endpoint provider + captured provenance；M5 A→B restart dispatch integration | covered |
| 未点名群消息只积累背景 | pipeline group gate + persistent group store；group tests | covered |
| 点名后带入此前群背景 | coordinator destructive drain/sender prefix/image preparation；exactly-once tests | covered |
| 同会话串行且跨会话并行 | queue/transition lock 对常规路径正确；terminal race 会在 queue slot 外先创建 orphan run、再排队创建 duplicate run | **fails：CRITICAL-1** |
| 运行中插话被及时采纳 | active steer 对常规路径正确；Kernel 已 terminal、Gateway marker 未清时同一插话执行两次 | **fails：CRITICAL-1** |
| `/stop` 中断活动运行 | complete active handle 固定 original binding/snapshot；publish/stop regression | covered |
| 空闲会话收到 `/stop` | coordinator idle direct/group control paths | covered |
| 活着但安静的运行不被误杀 | liveness stream timeout/reconcile owner；quiet/stall tests | covered |
| 有效图片正常进入本轮 | typed resolver + coordinator single preparation | covered |
| 图片下载、超限或损坏 | typed failure + fixed original-channel control reply，不 submit | covered |
| 中间与最终回复不重不漏 | ordinary observer/tracker/terminal path正确；orphan run 无 stream/lifecycle owner且可能重复 history/tool side effect | **fails：CRITICAL-1** |
| 后台任务完成后回到原会话 | captured subscription reply context + replay/dedupe/buffered handoff | covered |
| 外部 channel 与影子会话投递边界不变 | typed trigger-source guard + external delivery tests | covered |
| IM 离线时外部 channel 仍可用 | local outbound path不依赖 connected IM | covered |
| 启动、停止和重连结果保持一致 | endpoint readiness/clear + supervised IM reconnect + resource graph tests/evidence | covered |
| 停止时已接纳的入站工作有明确结局 | queue/dispatcher/Kernel/subscriber/delivery/IM ack ordered shutdown | covered |

## Coherence

| design 决策 | 遵守? | 代码证据与偏离 |
|---|---|---|
| D1 narrow `InboundPipeline` | 是 | façade 只做 route/gate/shadow/group append/delegation，run state 已迁出 |
| D2 revisioned `LiveAgentCatalog` | 是 | copy-on-write immutable snapshots + concrete config publish owner |
| D3 binder 唯一拥有 binding/stale guard | 是 | resolve/reuse/create/invalidate/reverse/canonical/conversation bind 与 provenance 收敛在 binder；M5 endpoint 属 process capability，不再依赖 durable binding refresh |
| D4 coordinator 原子拥有 queue/steer/stop/terminal | **否** | `dispatch()` 对 active marker 调真实 `kernel.submit(steer=True)` 后，在 `injected=False` 时丢弃已创建的 fresh record，只把 parts 交给 queue（`session_run_coordinator.py:169-197,215`）；queue 随后再次 normal submit 并只拥有第二个 run（`:333-391`）。真实 SDK 明确 `injected=False` 代表 freshly created run（`src/agent/sdk/kernel.py:1070-1112`）。 |
| D5 typed image strategy + exactly-once preparation | 是 | resolver typed result；同一 prepared parts 未二次 drain/download（但 CRITICAL-1 会二次执行同一 parts） |
| D6 sealed resource graph + one deadline | 是 | admission/Kernel terminal/consumer/delivery/IM close 的 owner 顺序和具名 timeout 保持闭合 |
| D7 composition 一次构造 | 是 | endpoint/callback/provider 都在构造期注入；合法晚绑定只返回 live resource |
| D8 public tests + deletion guard | **部分** | interface/architecture contracts完整；coordinator fake 的 idle steer 与 SDK contract 不一致，导致 terminal race 的双 submit 未被永久回归捕获 |
| D9 deep modules, no LOC KPI | 是 | catalog/binder/coordinator/subscription/tracker/cron service 均拥有真实状态与不变量 |

### Prototype / Reference Contract

N/A。

## Independent checks

- M5 + coordinator + SDK/architecture focused pytest：`48 passed in 1.47s`。
- `ruff check src tests`：passed。
- `pytest -q -m "not e2e"`：`3394 passed, 1 skipped, 20 deselected, 16 warnings in 121.07s`。
- `git diff --check a6c04258183b89867df6f08f6dcedf125989daf0..41577b479469e6e4325f3ef4e2dd0f12fb7f952f`：passed。
- test naming/size contract：included in focused run；M5 integration file 234 lines，未越过 400-line gate。
- M5 durable evidence：审计 `M5-fix-restart-dispatch-capability/evidence/r2-live-restart-dispatch.md`，真实 Gateway/IM/LLM 的 A→B 重启旅程同时证明 old metadata=A、live endpoint=B、同 session/history 且只投递 B；与永久 integration 的机制一致。
- 真实 Kernel terminal-race 只读诊断：第一 run 已在 Kernel terminal，但 observer gate 让 Gateway active marker 暂未清理；第二 dispatch 后 release 前 registry 已有 `[run1, run2]`，release 后最终为 `[run1, run2, run3]`，三者均 `completed`；第二 `PipelineResult.run_id == run3`，`run2` 无 Gateway stream/lifecycle owner。该诊断使用当前 `SessionRunCoordinator`、真实 `agent.sdk.Kernel`、真实 binder/catalog/router，只用 terminal observer gate 控制竞态，不修改源码、测试或配置。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — coordinator 把真实 SDK 已创建的 steer fallback 当成“尚未 submit”，同一 inbound 因而产生 orphan run + duplicate run。** 合法时序是：① run1 已在 Kernel 进入 terminal，但 coordinator 还在 terminal observer/lifecycle await，故 `_active_runs` 仍保留 run1（`session_run_coordinator.py:409-418,720-766`）；② 第二条消息在 transition lock 内看到该 marker 并调用 `kernel.submit(steer=True)`（`:169-183`）；③ Kernel 此时已无 active run，所以按 public contract 创建并启动 fresh run2，返回 `injected=False`（`src/agent/sdk/kernel.py:1070-1112`；永久 SDK contract `tests/contract/test_kernel_sdk_behavior_contract.py:914-934`）；④ coordinator 忽略 record/run2，只保存 parts 后进入 `_submit_queued()`（`session_run_coordinator.py:184-197,215`）；⑤ run1 Gateway cleanup 释放 queue 后，`_run_turn()` 再 normal submit 同一 parts 为 run3，并只消费/发 lifecycle 给 run3（`:333-391,399-458`）。结果是 run2 已真实执行、写 history 并可能产生工具副作用，却没有 Gateway stream、reply 或 shutdown ownership；run3 又执行相同用户输入。现有 `ControlledKernel` 在 steer 时只返回旧 latest run id 和可配置的 `injected=False`，没有像真实 SDK 一样创建 fresh run（`tests/unit/personal_assistant/_session_run_coordinator_helpers.py:62-82`），因此 `test_fallback_serializes_same_session_while_other_session_runs` 与 `test_steer_race_reuses_group_and_image_parts_exactly_once`（`test_session_run_coordinator_admission.py:47-126`）把错误实现验证成绿。本轮真实 Kernel gate 诊断稳定得到 3 个 completed run，第二结果只认 run3。该路径违反 motivation 的 FIFO/插话/不重不漏场景（`motivation.md:92-102,128-132`）、D4 “fallback 一次”与唯一 terminal owner（`design.md:144-160`），也直接违背 M4 “stop/steer 无孤儿或重复 run”的退出标准（`design.md:394`）。**修复要求**：在产品只能依赖 `agent.sdk` 的边界内，选择并钉死一种原子语义：要么提供 public try-steer-only 操作（注入失败不创建 run），失败后才把 prepared parts 交 FIFO；要么 coordinator 立即接管 `injected=False` 返回的 fresh `RunInfo`，登记完整 active handle，并只消费/收尾该 run，绝不能二次 submit。接管方案还必须证明与旧 run terminal finalization、`/stop`、shutdown 和 follower lifecycle 的顺序闭合。补永久真实 Kernel/public-SDK 回归：用 terminal observer gate 令 run1 已 Kernel-terminal 但 marker 尚存，派发第二条消息，断言总 run 数只增加 1、该 run 恰好一个 stream/lifecycle owner、输入/history/tool side effect 各一次、第二结果返回同一 run id；同时让 coordinator fake 遵守 SDK 的 `injected=False == fresh run` contract，避免继续掩盖生产语义。

### WARNING（应该修）

None.

### SUGGESTION（可以修）

None.

# Round 4

- Validated head: 55617c7b634e86d2c6daed5067e5ce0d50d325be
- Review round: 4
- Verification mode: full
- Delta base: N/A
- Focus issues: Round 3 CRITICAL-1 及其后续 code-review blocker 闭环
- Requires full verification: false

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 64/64 tasks 已勾选；63/64 exit criteria 实质满足；6/6 Requirements 均有实现 |
| Correctness | motivation 的 20/20 Scenarios 均有代码与永久测试对应；另发现 1 条 design/M8 支持路径偏差 |
| Coherence | D1-D9 的所有权边界整体闭合；D4、D8 的 Round 3 缺口已修复，M8 的 no-delivery 终态 owner 仍部分偏离 |
| Regression | 聚焦测试、ruff、测试规模契约与全量非 e2e 均通过 |
| Verdict | PASS |

**结论：No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).**

## Completeness

### Milestone / task audit

| Milestone | checked / total | 实质结论 |
|---|---:|---|
| M1 | 7/7 | catalog snapshot、revision 与 immutable lookup 已落地 |
| M2 | 12/12 | binder 唯一拥有 durable binding、stale guard、provenance 与 reverse lookup |
| M3 | 8/8 | narrow InboundPipeline 只保留 route/gate/shadow/group append/delegation |
| M4 | 6/6 | coordinator 原子拥有 admission、FIFO、steer、stop、terminal 与 shutdown |
| M5 | 6/6 | restart 后 dispatch endpoint 使用 live process capability，不复用 durable stale endpoint |
| M6 | 6/6 | full-stack lifecycle、invalid relay recovery、stop、shutdown 与 cleanup evidence 完整 |
| M7 | 4/4 | typed agent-to-agent shadow 与 canonical session identity 收敛 |
| M8 | 15/15 marked；14/15 satisfied | delivery-present cron/heartbeat 终态与 restricted skills 完整；supported no-delivery cron 路径未观察真实 Kernel 终态 |

任务清单合计 64/64 已勾选。唯一未实质满足的 exit criterion 是 M8 要求 cron 无论 completed / failed / cancelled 都记录真实 Kernel 终态；当前 no-delivery 配置会提前写 completed，见 WARNING-1。

### Requirements / Scenarios

| Requirement | Scenarios | 结论与证据 |
|---|---:|---|
| R1 narrow inbound façade | 3/3 | ownership contract、architecture test 与 route/gate/shadow/delegation 测试覆盖 |
| R2 one live catalog / binder owner | 4/4 | immutable snapshot、revision、two-phase stale guard、restart routing 与 binding tests 覆盖 |
| R3 coordinator atomic run ownership | 4/4 | FIFO、try-steer-only fallback、stop、terminal race、shutdown tests 覆盖 |
| R4 typed delivery / protocol recovery | 3/3 | typed StreamRunOutcome、negative ack dequeue、connection continuation tests 覆盖 |
| R5 canonical external identity / shadow | 3/3 | literal LIKE escaping、IM-origin guard、runtime metadata stripping tests 覆盖 |
| R6 unattended execution capabilities | 3/3 | cron/heartbeat restricted skills、real terminal failure delivery 与 live evidence 覆盖 |

motivation 中 20 个场景均能从生产入口追到永久测试或 M6/M8 durable evidence。没有 delta-spec；prototype/reference contract 为 N/A。

## Round 3 与 code-review blocker 闭环

| 历史 blocker | Round 4 独立结论 | 关键证据 |
|---|---|---|
| steer fallback 产生 orphan + duplicate run | CLOSED | agent.sdk.Kernel.try_steer 只尝试注入且失败不建 run；coordinator 仅在失败后让自己的 FIFO normal submit 一次；真实 Kernel terminal-race regression 断言唯一新 run |
| negative ack 卡住 pending queue | CLOSED | error frame 按原 message_type reject 队首；IMFrameRejectedError 结束对应 future、清 ack 并继续 flush 下一帧；连接不重建 |
| permission wait 被普通 watchdog 误杀 | CLOSED | permission_request 将 watchdog 置为 None，permission_resolved 恢复；回归覆盖跨过普通 timeout 后恢复与再次 stall |
| session LIKE 将 % / _ 当 wildcard | CLOSED | session key 对 !、%、_ 做 literal escaping，所有相关查询显式使用 ESCAPE ! |
| binder 在锁内做 workspace I/O / stale publish | CLOSED | capture revision/generation 后 asyncio.to_thread 校验，回锁复核 candidate identity、revision、generation、catalog；stale operation 不写 durable binding |
| cron 使用 SDK 私有终态常量 / false success | CLOSED for delivery-present path | runtime_delivery 从 agent.sdk 导入 TERMINAL_RUN_STATUSES 并返回 typed StreamRunOutcome；failed run 持久化 failed 且不产生 success awareness |
| agent-to-agent shadow 使用平行 identity 协议 | CLOSED | 复用 external_identity_from_message，限制 IM-origin，并剥离 runtime metadata |
| unattended session 忽略 agent restricted skills | CLOSED | Kernel client shim 将 agent.skills 传入 create_session；空集合保留默认行为；cron/heartbeat 均有回归 |

Round 3 的唯一 CRITICAL 已由 public SDK contract 与真实 Kernel integration 双层钉死，不再依赖违反真实 SDK 语义的 fake。

## Correctness

### 关键用户旅程

- 同 session 并发消息：active run 可注入时只 steer；不可注入时进入 coordinator FIFO，且只 normal submit 一次。
- terminal race：Kernel 已 terminal、Gateway marker 尚未清理时，第二条消息不会创建 orphan run，也不会重复执行输入。
- stop / shutdown：coordinator 持有 active handle、terminal observer 与 follower lifecycle，关闭顺序有界。
- restart dispatch：durable binding 只保存 identity；真实投递 endpoint 从 live catalog 获取，重启后不向旧 endpoint 投递。
- IM error recovery：单帧业务错误只拒绝对应 future，后继合法帧仍在同一连接完成。
- permission lifecycle：等待用户授权期间不受普通响应 watchdog 约束，授权完成后恢复 timeout。
- external identity：LIKE metacharacter 被当作字面值；shadow 只接收合法 IM-origin envelope。
- unattended skills：cron/heartbeat 继承 agent allowlist；delivery-present cron 按 Kernel 真实 terminal status 写历史并对失败回执。

### 当前 main 漂移

unit 分支未包含 origin/main 上 bugfix-465 的 ancestry，但其语义已由新 owner 搬运：permission_request 暂停普通 watchdog，permission_resolved 恢复。当前 coordinator 回归覆盖该行为，因此不是遗漏式漂移。

### Durable evidence audit

- M6 progress/evidence 记录真实 IM + Gateway 的 invalid relay 后同连接恢复、same/new conversation 成功、node online、stop 与 clean shutdown；与当前永久 protocol tests 一致。
- M8 live-cron-failure evidence 使用真实 IM + Gateway + Kernel 和确定性 provider failure，证明 failed cron history、owner failure bubble、无 success awareness，并完成清理。
- M6 最终 refresh 明确在包含 M7+M8 的 unit head 上重跑 focused、ruff 与全量 non-e2e；当前 merge head 再次由本轮独立全量验证。

## Coherence

| design 决策 | 遵守? | Round 4 结论 |
|---|---|---|
| D1 narrow InboundPipeline | 是 | façade 不再拥有 run state、binding repository 或 delivery lifecycle |
| D2 revisioned LiveAgentCatalog | 是 | immutable copy-on-write snapshot 与 revision publish owner 唯一 |
| D3 binder 唯一拥有 binding/stale guard | 是 | resolve/create/invalidate/canonical/reverse lookup/provenance 收敛 |
| D4 coordinator 原子拥有 queue/steer/stop/terminal | 是 | try-steer-only 消除了 Round 3 double submit；fallback 与 lifecycle owner 唯一 |
| D5 typed image strategy + exactly-once preparation | 是 | prepared parts 只消费一次，steer fallback 不二次 download/drain |
| D6 sealed resource graph + one deadline | 是 | admission、Kernel terminal、consumer、delivery、IM close owner 顺序闭合 |
| D7 composition 一次构造 | 是 | callback/provider/endpoint 在 composition root 注入，合法晚绑定只读 live resource |
| D8 public tests + deletion guard | 是 | public SDK contract、ownership tests 与真实 Kernel race regression 同时守护 |
| D9 deep modules, no LOC KPI | 是 | catalog、binder、coordinator、subscription、tracker、cron service 均拥有明确不变量 |

M8 对真实终态 owner 的实现只在 delivery-present 路径闭合；no-delivery 分支提前写 completed，详见 WARNING-1。

## Independent checks

- Focused verification suite（19 个 contract/unit/integration 文件）：118 passed, 2 warnings in 6.52s。
- Ruff：ruff check src tests，passed。
- Test naming / size contract：2 passed in 0.11s。
- Full non-e2e：3417 passed, 1 skipped, 20 deselected, 16 warnings in 107.52s。
- Architecture grep：coding_cli / personal_assistant 未越界 import agent.core 或 agent.platform；binding repository 引用只在 binder owner。
- Worktree source/test 状态：验证期间只读，未修改 production code 或 tests。

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（应该修）

- **WARNING-1 — supported no-delivery cron 配置未消费 Kernel 终态，会把失败或取消的 run 记成 completed。** CronExecutionService 的构造契约明确 stream_delivery 可为 None；production composition 在 owner_user_id 缺失或 observer 不可用时确实传 None。但 execute 路径在 runner.start 返回 run id 后立即写 status=completed、result_summary=no_delivery_path，没有等待该 run 的 completed / failed / cancelled 终态。本轮使用只读 fake runner 让 run 永不提供 terminal，仍稳定得到 completed history，证明这是提前成功而非仅缺少 UI delivery。现有 terminal regressions 都注入 stream delivery，因此没有覆盖该支持路径。这部分偏离 design 的 M8 real terminal owner 决策与 M8 exit criterion，但 delivery-present 的真实用户失败旅程正确，因此定为 WARNING 而非 CRITICAL。**建议修复**：把 mandatory terminal consumption 与 optional IM delivery/observer 解耦；无投递配置也必须经共享 typed terminal consumer 得到 StreamRunOutcome 并持久化真实 status，只有用户消息和 awareness 条件化；增加 no-delivery 下 failed、cancelled、missing-terminal 不得写 completed 的永久回归。

### SUGGESTION（可以修）

- **SUGGESTION-1 — baseline diff 有 3 个 EOF trailing blank-line hygiene 问题。** git diff --check a6c04258183b89867df6f08f6dcedf125989daf0..55617c7b634e86d2c6daed5067e5ce0d50d325be 报告 M8 live-cron-failure evidence、test_runtime_delivery_stream.py、test_unattended_session_skills.py 各 1 个 new blank line at EOF。它们不影响运行语义或测试，但建议 PR 前清理。
