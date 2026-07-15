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
