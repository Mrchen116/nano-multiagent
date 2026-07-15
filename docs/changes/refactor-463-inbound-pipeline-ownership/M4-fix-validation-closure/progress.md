# refactor-463-M4 — Progress

## 启动基线

- Context: Round 1 verification/acceptance/code review 已确认 M3 的 owner 迁移方向正确，但 active run、旧 session、unattended session 与显式空权限仍缺少 revision provenance 闭环；M4 从 `9aab3c065` 的批准修复计划开始。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` → `3358 passed, 1 skipped, 22 warnings`（32.05s）。
- Leader alignment: M4 按 A/B/C/D 四组 finding 逐 Roadpoint 完成 TDD 三提交；动态 prompt 只验证公开 `custom_prompt`，不恢复废弃的 `system_prompt`。

## R1 — 闭合 revision/run-control 与权限 provenance

- Context: coordinator active marker 只保存 run id，配置 publish 后 stop/steer 会重新 resolve 新 session；internal dispatch/fork/heartbeat/background delivery 也会在 await 后重新读取当前 catalog/binding，旧 revision 的 work 因而可能被重标、丢失或污染新 session。`Kernel.create_session()` 还用 truthiness 处理 allowlist，使显式 `[]` 退化为产品默认工具。
- Decision: coordinator active marker 升级为持有原 binding 与 Agent snapshot 的不可变 handle，active steer/stop/model/workspace 全部使用该 handle。binder 成为 session/binding provenance 的唯一捕获 owner，原子返回 snapshot + write guard，并为 inbound、fork、heartbeat/cron session 登记来源。internal dispatch 在发 IM 前捕获 origin provenance，缺失时 fail-fast，await 后只用捕获事实完成 semantic bind/history。background subscriber 直接闭包捕获原 `ReplyContext`。heartbeat 专用 session cache按 Agent revision 分代，生产 shim 以专用 `create_agent_session()` 接收捕获 snapshot。Kernel 把 `None` 与显式空 allowlist 分开处理。
- Rationale: 当前 catalog revision 只决定新 admission；已接纳 work 的控制、prompt/tools、历史和投递必须沿创建时 provenance 完成。事实捕获与 stale-write 判定集中在 binder，调用方不再跨 await 拼装 catalog、binding 与 generation。专用 unattended 创建接口不把 Gateway snapshot 参数泄露给通用 kernel-client protocol 或既有测试替身。
- Evidence:
  - C1 red: active publish→stop/steer、旧 session dispatch、fork lookup/publish race、empty allowlist、heartbeat revision 与旧 subscriber reply context 共 6 个稳定失败；commit `6c2bdd88d`。
  - Focused: 相关 coordinator/binder/dispatch/fork/background/heartbeat/Kernel 集成回归 → `37 passed, 2 warnings`；`ruff check` → passed。
  - Full: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` → `3364 passed, 1 skipped, 22 warnings`（33.33s）。
  - Entry: public `SessionRunCoordinator` 测试证明 publish/invalidate 后 steer 与 stop 仍命中原 session；public binder + `InternalDispatchHandler`/fork handler 测试证明旧 session 只使用旧 workspace/revision guard且不能恢复 stale binding；真 `Kernel.create_session(enabled_tools=[])` 集成回归证明 runtime tool registry 为零工具；heartbeat 与 background public owner 回归证明 revision 分代和原 reply context 保留。最终四条隔离真栈旅程在 R4 统一签收。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - Visual/Interaction: N/A。
- Rollback: 回退 C2 `9e300138e` 恢复 M3 末态；C1 可随同回退。R1 没有改变 session key、binding schema、IM API 或外部 channel 协议。
- Commits: C1=`6c2bdd88d`；C2=`9e300138e`；C3=本次 docs commit。
- Next: R2 先以永久红测锁定 subscriber/cron/dispatcher/shutdown accepted-work 的线性化与 terminal delivery，再修复 shutdown resource graph。

## R2 — 闭合 shutdown task graph 与 terminal delivery

- Context: subscriber 在 seal 后无条件拒绝 `ensure()`，stream 已 dequeue 的缓冲事件也会因 stop flag 在 callback 前丢弃；manual cron 的 sealed check 与 pending registration 之间存在窗口；`run_coroutine_threadsafe()` proxy 可在底层 loop task 完成 async cancellation cleanup 前变成 cancelled。queue admission timeout 没有 session/item 身份，且 steer 进入共享 active run 的第二条 relay 只有 accepted、没有随原 run terminal。
- Decision: manager 在同一 async lock 内先识别 existing subscriber，再对新 session 执行 seal gate；subscriber 对已 yield 的一条事件完成 callback 后才响应 stop。cron 在 sealed check 的同一极短临界区登记 admission token，seal 保持 O(1)，drain 等 token 走到 reject 或 execution terminal；validation 期间发生 seal 则返回 `cron_unavailable`，不在 drain 后启动。dispatcher 同时跟踪 thread-safe proxy 对应的真实 loop task，超时 cancellation 只取消/await真实 owner。queue 给每项分配稳定 `item-N`，所有 admission/cancel-lifecycle waiter 带 `session_key` 与 `item_id`。coordinator 在 active transition lock 内登记 steered follower，run terminal 时原子关闭 steer admission并向 primary/follower 分别发 completed/failed lifecycle。
- Rationale: seal 仍只是常数时间 admission switch；耗时 validation/callback/async cleanup 都留在 owner 的 settle/drain 阶段。proxy 不是协程资源终态，真实 loop task 才是。共享 Kernel run 不等于共享 relay task，每一条已发 accepted receipt 的用户消息都必须拥有自己的 terminal receipt。
- Evidence:
  - C1 red: existing ensure、buffered event、thread proxy cleanup、queue timeout identity、steered accepted terminal、cron check/register window共 6 个稳定失败；commit `a304a053e`。
  - Focused: subscriber/dispatcher/queue/coordinator/cron/shutdown/size contract → `59 passed, 2 warnings`；相关 `ruff check` → passed。
  - Full: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` → `3370 passed, 1 skipped, 22 warnings`（32.43s）。
  - Entry: public manager 测试证明 seal 后 existing ensure 幂等且 stop 前已 dequeue 的 terminal event 仍投递；public dispatcher 测试证明 proxy cancel 后 drain 等到底层 cleanup；public cron 测试把 job lookup 固定在竞争窗口，证明 seal 后 drain 不提前返回且该请求不启动；public queue timeout显示 `session_key=sess-admission`、`item_id=item-1`；public coordinator deadline cancellation 对 primary 与 steered 两条 accepted 消息都发 failed。真 SIGTERM + 两条 Web IM 消息的持久对账在 R4 统一签收。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - Visual/Interaction: N/A。
- Debugging note: C1 首版 cron 红测把“线性化”误写成 `request_stop()` 必须等待 job lookup；对照 D6 的 O(1) seal 硬约束后，将判据修正为真正用户可见的不变量：seal 可立即返回，但 drain 不能在 admission token settle 前观察零任务。最终实现没有用大锁包磁盘 I/O。
- Rollback: 回退 C2 `9d1a05170` 恢复 R1 末态；C1 可随同回退。R2 没有改变 IM wire、session key、binding schema 或 cron runs schema。
- Commits: C1=`a304a053e`；C2=`9d1a05170`；C3=本次 docs commit。
- Next: R3 先锁定真实 internal listener readiness/endpoint、IM reconnect supervisor、typed shadow identity 与 concrete config-sync wiring，再修 composition/transport owner。

## R3 — 根治 dispatch readiness、reconnect 与 shadow/config 边界

- Context: composition 固定写入 `127.0.0.1:8089`，runtime 吞掉 listener bind 异常后仍置 ready；`connect_once()` 在长耗时 `on_connected` 对账期间先启动 heartbeat，但 receive loop 尚未运行，register/heartbeat ack 即使已到 socket 也无人消费，最终把健康连接误判为 heartbeat timeout。IM-originated WebRelay typed identity 也会再次进入 external shadow sync；config-sync 的 dynamic-agent callback 仍由 composition 构造后赋值，测试用 `_ownership(pipeline)` 假 owner 掩盖真实 revision/invalidation。
- Decision: `InternalDispatchEndpoint` 成为实际 listener URL 的生命周期 owner；runtime 先成功 bind（生产端口 `0`），从 socket 读取实际端口并 publish，再启动 channel/置 ready，任何 bind 异常直接使启动失败。coordinator 在 session resolve 当下读取 published URL；没有 provider/监听时省略 metadata URL，让 `SendMessageTool` 走既有 fail-fast。IM heartbeat 从 `connect_once()` 移到 `_listen_once()` admission，保证 callback 完成且接收路径已进入后才启动。shadow sync 用 typed `external_identity.trigger_source == 'im'` 拦截。`IMAgentConfigSync` 构造期接收只读 callback；所有 config-sync 测试改用 concrete `LiveAgentCatalog + GatewaySessionBinder`，并以真 v1→v2 publish/invalidation/resolve 覆盖 owner 语义。
- Rationale: “配置端口”不是“已监听 endpoint”；只有 socket bind 成功后的地址才可进入 session capability metadata。heartbeat liveness 同时依赖发送和接收，不能在唯一接收循环尚未进入时启动。配置发布与 binding invalidation 必须由生产 owner 的真实 revision/generation 证明，而不是测试 shim 模拟调用次数。
- Evidence:
  - C1 red: 双 Gateway 动态 URL import/并存、真实端口冲突 readiness、慢 `on_connected` heartbeat race、typed IM shadow guard、mutable callback/测试 shim contract 共 6 个稳定失败；commit `bad87f2f1`。
  - Focused: dispatch/send-message/reconnect/shadow/config-sync/build-runtime/architecture → `104 passed, 2 warnings`；相关 `ruff check` 与 `git diff --check` passed。
  - Real stack: `evidence/r3-dispatch-reconnect.md`。生产 Gateway 实际监听 `60831`，新 session metadata 精确为该 URL；真 LLM tool call `send_message(to=plato)` 返回 `ok=true` 且 IM durable message completed。并行第二 Gateway 无端口冲突；`scripts/e2e-resilience.sh` 的 IM kill/restart 与 Gateway-before-IM 两场景均 PASS。
  - Shadow: typed guard 永久回归不调用 shadow sync；真栈日志无 `RuntimeProtocolFacts` serialization / duplicate shadow warning。
  - Frontend State Matrix / Browser QA / Visual: N/A（无前端变更）。
- Rollback: 回退 C2 `9b70bd65d` 恢复 R2 末态；C1 可随同回退。R3 未改变 IM API、session key、binding schema 或外部 channel 协议；metadata 的 URL 值从固定配置地址收敛为实际 listener 地址。
- Commits: C1=`bad87f2f1`；C2=`9b70bd65d`；C3=本次 docs commit。
- Next: R4 收深 cron/config owner，完成无变化 persist 修复、全量门禁和四条真栈总签收；同时复核本轮 teardown 暴露的 background subscriber deadline warning。
