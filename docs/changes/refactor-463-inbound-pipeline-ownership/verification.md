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
