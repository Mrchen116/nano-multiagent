# Design 评审：refactor-463（第三轮 closure review）

**结论**：Approved

三轮审查中的问题已全部闭合。生产消费者清单完整；accepted-root/queue/subscriber/delivery 与 internal-handler/heartbeat/cron 形成一张可 seal/drain 的资源图；80% child absolute deadline 来自 refactor-461 的真实 parent grace 且在任何 await 前只计算一次；catalog revision 同时约束 reuse/create/conversation-bind 写回；normal submit→active marker 与 stop/steer 在同一 transition lock 内线性化。设计可交 `change-orchestrator` 实施。

## 核实台账

### 现状断言与既有约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 生产入口是 `build_runtime()` 构造 Gateway 入站对象图 | 从 `main()` 正向追 runtime 构造与 `GatewayRuntime` 注入 | ✓ 生产确经 `build_runtime()` 构造 pipeline、dispatcher、internal dispatch、Kernel 与 runtime（`src/personal_assistant/main.py:3570-3590`），不是测试旁路。 |
| `InboundPipeline` 1,962 行且同时拥有 route/session/run/media/subscriber 状态 | 行数与字段/主路径核对 | ✓ 当前文件确为 1,962 行；route/queue/active/stop/image/subscriber/terminal 逻辑均在同类中（`inbound_pipeline.py:244-674,777-864,1030-1623`）。 |
| `main.py` 4,376 行且构造后写六个 pipeline 私有字段 | 行数与 wiring 核对 | ✓ 当前 4,376 行；六处 post-wiring 位于 `main.py:3122,3237-3277`，scheduler/shim 另读 `_agents/_run_queue`（`:3550-3559`）。 |
| config/shadow sync 是业务 adapter 而非 composition 细节 | 追入口、状态与 HTTP 行为 | ✓ `_IMConfigSyncClient` 自己做 fetch/normalize/persist/retry（`main.py:328-485,861-927`）；shadow sync 自己做 conversation/message HTTP 协议（`:981-1080`），迁出合理。 |
| Internal dispatch 与 CronRunner 是 binder/catalog 真实消费者 | 追生产构造和调用 | ✓ internal dispatch 直接持 store/startup workspace 并 bind/append（`gateway/internal_dispatch.py:28-45,101-170`; `main.py:3570-3577`）；CronRunner 直接 `find_direct_by_agent`（`scheduler/cron_runner.py:72-98,222-238`; `main.py:3338-3343`）。修订把两条生产旁路都纳入 M1。 |
| `SessionRunQueue._active_sessions` 泄漏给 scheduler | 追 wiring | ✓ `main.py:3556-3559` 把私有 queue 注入 heartbeat；design 改成 coordinator `is_session_busy` 命中真实旁路。 |
| subscriber 集合/生命周期由 pipeline 裸 dict 承担 | 追 ensure 与 shutdown | ✓ pipeline 自行维护每 session subscriber，并无 Gateway shutdown close（`inbound_pipeline.py:1345-1451`）；单 subscriber 自己只拥有一个 reconnect task（`background_session_events.py:90-116`）。 |
| observer 存在不受 dispatcher 管理的 detached delivery tasks | 全目录搜索 task 创建点 | ✓ observer 有 external mirror、skill、delta、terminal、reconcile/finalize 等裸 `create_task`（`runtime_delivery/observer.py:244-271,323-325,638-674,800-846,880-904,976-1048,1150-1189`）。 |
| 测试 private surface 统计为 32 / 18 / 108 | 独立 `rg` 计数 | ✓ 32 个测试文件引用 `InboundPipeline`；18 个文件、108 处命中 pipeline private access，与 design 现状一致。 |
| 产品只能 import `agent.sdk` | 对照顶点约束与设计模块位置 | ✓ `AGENTS.md`/`SPEC.md` 的依赖硬规则要求如此；新增模块均在 `personal_assistant.gateway`，设计未引入 core/platform import（`design.md:25-29`）。 |
| `handle_inbound()` 是稳定 channel 入口 | 追 dispatcher | ✓ 当前 `_InboundDispatcher` 只调用该入口（`main.py:1779-1812`）；D1 保留相同 façade。 |
| queue/steer/stop/drain/terminal 共享并发不变量 | 追 live lock 与 cleanup | ✓ active check→prepared fallback、normal queue、stop marker 与 terminal finally 互相依赖（`inbound_pipeline.py:317-525,1030-1111,1458-1623`），不能拆成独立 handlers。 |
| live config 必须覆盖消息/heartbeat/cron/internal dispatch | 追当前 live dict 与启动快照 | ✓ pipeline/scheduler/shim 共享 live `_agents`，但 internal dispatch 仍是启动 snapshot（`main.py:3550-3555,3570-3576`）；修订后的统一 catalog 范围正确。 |
| binding 是 SQLite production + memory test adapter，格式不改 | 追 production store | ✓ production 用 SQLite store，key/reply context 持久化在既有表（`session_keys.py:170-256`）；memory/SQLite 两实现都是真 seam。 |
| 既有 delivery seam 应复用 | 追 callback 归属 | ✓ lifecycle 已统一 accepted/running/terminal relay；background 已统一 IM/external visible text，observer 已做事件翻译。新 tracker 只补 task ownership，不重写 routing，边界合理。 |
| refactor-461 parent grace 只是 launcher 强杀宽限 | 核 461 worktree config 与 stop | ✓ config doc 明示 parent grace（`.worktrees/unit-refactor-461/src/personal_assistant/config/local_store.py:274-286`），parent 从发 SIGTERM 后按同值计时再 SIGKILL（`.worktrees/unit-refactor-461/src/personal_assistant/main.py:2789-2829`）。 |
| refactor-462 与 Gateway binder/coordinator 正交 | 对照 462 owner | ✓ 462 的 `ConversationSession`/Executor 拥有 Kernel conversation mutation/permit/task；产品只见 SDK（`docs/changes/refactor-462-kernel-session-aggregate/design.md:61-91,144-179,188-199`）。463 只拥有 Gateway channel binding 与产品 admission。 |
| 测试 400 行与行为替换规则 | 对照 testing guide | ✓ `docs/TESTING_GUIDE.md:35-47,72` 支持 interface behavior 测试、去重和 400 行软上限。 |

### 决策、接口与数据流

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| D1：pipeline 只保留 route/gate/shadow/ignored chatter | 删除测试 + 生产调用链 | ✓ 删除 façade 会把同一入站边界决策摊回 channel；继续保留 session/run/media state 才会浅。D1 的边界与 `handle_inbound` 生产入口一致（`design.md:102-110`）。 |
| D2：concrete `LiveAgentCatalog` + frozen revision snapshot | 核是否深、是否假 Protocol | ✓ 多线程/多消费者需要 copy-on-write publication；删除后会恢复裸 dict。只有一个 production 实现且不造 Protocol，深度成立（`design.md:112-122`）。 |
| D2：persist → publish → no-await invalidate | 核 reuse/create/conversation-bind 竞争窗 | ✓ request 携 revision；binder 复用只接受同 revision，create await 与所有 repository write 前后都核 generation/current，cleanup 不误删新 binding（`design.md:121,131-135`）。新 config + 旧 binding reuse、create writeback、semantic bind writeback 三类窗口均已关闭。 |
| D3：binder 唯一拥有 resolve/reuse/create/validation/reply/invalidate/reverse/canonical/conversation bind | 对照所有 production store 调用方 | ✓ pipeline、delivery、scheduler、fork、config sync、internal dispatch 均被纳入；repository 不再导出（`design.md:125-139,195-209`）。 |
| D3：InternalDispatch 改 catalog+binder；Cron/heartbeat 改 canonical binder lookup | 对照 live signatures | ✓ 修订接口正面替换 `session_store + agent_workspace_roots` 与 `find_direct_by_agent` 两条旁路（`design.md:134`; live 证据见上），M1 也列文件和测试。 |
| D4：coordinator 唯一拥有 queue/steer/stop/terminal | 核 owner 聚合与 public surface | ✓ 五类状态共享 per-session transaction；`dispatch/stop/is_busy/begin_shutdown/drain` 隐藏的规则显著多于接口（`design.md:138-156`）。 |
| D4：normal submit→active marker 对 stop/steer 线性化 | 对照 SDK sync submit 与 live race | ✓ 设计明确同一 transition lock、无 await/第二把锁，submit 抛错不发 marker；stop/steer 也取同锁（`design.md:146-150`）。当前 live 的 submit 后再 await lock 窗（`inbound_pipeline.py:511-525,1041-1064`）不会被照搬。首轮 Issue 5 已关闭。 |
| D4：steer fallback parts 恰好消费一次 | 对照 live group/image path | ✓ 同锁 active check→drain/download→steer，失败转 queue 复用 prepared parts（`design.md:146-148`; live `inbound_pipeline.py:317-443,717-767`），不重复 drain/download。 |
| D4：stop mark→interrupt→append→original consumer reconcile | 对照 Kernel 语义与 462 边界 | ✓ 设计保留既有顺序并把 reconcile 留给 stream owner（`design.md:149-150`）；Kernel interrupt 同步 terminal/park pending（`.worktrees/unit-refactor-461/src/agent/core/runs/registry.py:300-324`）。 |
| D5：image resolver 拥有 fetch/limit/validation/MIME/failure | 删除测试 | ✓ 这是完整媒体策略；coordinator 只拥有调用时机与失败投递，未暴露浅 builder（`design.md:158-164`）。 |
| D6：subscriber manager ensure-once/seal/Kernel 后 close | 对照 subscriber 真语义 | ✓ 既有 subscriber 是后台结果唯一 consumer（`background_session_events.py:118-169`）；修订明确 seal 不 cancel、Kernel close 后再 stop/callback drain（`design.md:166-170`）。首轮 subscriber-before-Kernel 问题已关闭。 |
| D6：delivery tracker 覆盖所有 observer detached coroutine | 全量搜索 + owner/data flow | ✓ D6 明示 observer 中所有裸 task 改走 composition-root singleton tracker，producer 结束后 close-and-repeat-drain（`design.md:172`）；M2 范围含 `observer.py`，首轮遗漏已关闭。 |
| D6：dispatcher roots + queue workers 有各自 owner | 对照 current detached roots/workers | ✓ dispatcher 同时追 loop task 和 thread-safe future；queue/coordinator 追自己的 per-session worker（`design.md:174`），正面覆盖 `main.py:1805-1812` 与 `run_queue.py:41-68`。 |
| D6：queued-before-submit 处置 | 核 admission 状态机 | ✓ pending FIFO item 摘除并走既有 failed lifecycle；transition 中队首跨完 submit-or-rollback；已 marker run 交 Kernel close（`design.md:176,182-185`），首轮 undefined policy 已关闭。 |
| D6：从 parent grace 派生一次 80% child absolute deadline | 核真实数据源、建立时点与 timeout 传播 | ✓ `GatewayRuntime` 持有 `LocalConfig`（461 `main.py:1883-1917`），能读取真实 `config.gateway.shutdown_grace_seconds`；`request_shutdown` 首次记录起点，cleanup 在任何 await 前只算一次 absolute deadline，settle/Kernel/各 consumer/delivery 共用 remaining helper（`design.md:183-191`）。 |
| D6：Kernel close 能封 submit并产生 terminal | 追 SDK/Registry/Executor | ✓ `Kernel.aclose()` 先 Registry DRAINING，再由 Executor cancel/drain targets（461 `kernel.py:1641-1666`; `executor.py:255-293`）；TargetCompletion 再写 cancelled/failed terminal（`registry.py:440-483`），Gateway consumers 必须在此时保持存活，设计主顺序正确。 |
| D7：composition root 一次构造、仅 provider 合法晚绑定 | 核对象可用顺序 | ✓ catalog/binder/tracker/coordinator/pipeline/dispatcher 的顺序闭合；IM manager provider 是真实 live resource seam；无 setter/private bag（`design.md:190-204`）。 |
| D8：public behavior/interface 测试与 deletion guard | 核是否只换 private 名 | ✓ route、catalog/binder、internal dispatch/cron、coordinator、image/subscriber、shutdown、build-runtime 均有公开观察面，并明确删除对等 white-box（`design.md:206-219`）。 |
| D8：历轮问题都有 race/shutdown exit | 对照 M1-M3 | ✓ reuse/create/internal-ack/fork-await race、submit-marker race、queued failed、subscriber-after-Kernel、active heartbeat/internal handler、observer task drain、单 deadline与单项 timeout 均列 exit（`design.md:216-220,388-390`）。 |
| D9：LOC 是结果，不造薄模块 | 对照目标与 deletion test | ✓ 预计缩短建立在 owner/interface 删除上；明确禁止复制函数、共享 dict/lock、手排顺序（`design.md:221-225`）。 |
| 稳定接口集合 | 两个 worker兼容性检查 | ✓ catalog/binder/coordinator/resolver/subscription/tracker/pipeline/dispatcher 的调用方和 ownership 对齐；deadline 明确为同 loop absolute monotonic time（`design.md:227-277`）。 |
| normal/steer 时序图与 state diagram | 对照 D4 | ✓ 图中 transition lock、prepared fallback、terminal cleanup 与正文一致（`design.md:279-332`）。 |
| config update 数据流 | 对照 D2/D3 | ✓ publish 是配置线性化点；resolve/create/conversation-bind 都用同一 snapshot revision。Internal dispatch stale 保留已完成 ack/append 但不落库；fork stale 返回失败走既有 IM rollback（`design.md:121,131-137,342-344`）。 |
| 风险与回退 | 逐项核控制是否落到 milestone | ✓ steer/stop/config/binding/background/producer seal/deadline/image/461/462/薄搬运均有对应回退，且无 schema migration/flag（`design.md:355-370`）。 |
| reviewer runbook | 核常驻服务重启/健康检查 | ✓ 有隔离 e2e-up/down、health check 和关键用户旅程（`design.md:364-372`），满足常驻服务设计要求。 |

### motivation / spec 约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Relations：Depends on 461；related 460/462 | 核冲突与 owner 边界 | ✓ 461 改同一 `GatewayRuntime/main.py`，作为实施基线必要；460 只作 Web IM continuity 回归；462 只改 Kernel 内 owner（`motivation.md:3-6`; `design.md:55-61`）。 |
| 澄清：只治理候选 4、排除候选 8、独立 spec/design/review | 对照原话与设计范围 | ✓ daemon/PID/readiness/timing migration 均未被 463 重做；本报告是独立 reviewer 输出（`motivation.md:20-28`）。 |
| Req 路由：直聊正确 Agent/原目标 | 映射 D1/D2/M1/M3 | ✓ route priority 与 original reply target 均保留；M1/M3 reviewer 轨覆盖（live `inbound_pipeline.py:777-864,603-627`）。 |
| Scenario：重启续接原会话 | 映射 D3/SQLite | ✓ binder 不改 key/schema/reply context，继续复用持久化 row（`session_keys.py:170-256`; M1 exit）。 |
| Scenario：未知 Agent 拒绝 | 映射 D1/catalog | ✓ `require` 保持失败边界，M1/M3 覆盖；不建立 fallback route。 |
| Scenario：动态配置下一轮/heartbeat/cron 生效 | 映射 D2/D3/M1 | ✓ catalog snapshot 覆盖所有消费者，reuse/create/semantic-bind 写回统一受 revision+generation 约束；stale row 不会在重启后复活（`design.md:121,131-137`; M1 exit）。 |
| Scenario：Agent 工具投递同步正确直聊历史/动态 workspace | 映射 D2/D3/internal dispatch | ✓ M1 明确改 catalog+binder 并移除 startup workspace snapshot（`design.md:134,201,380`）。 |
| Req 群聊：未点名只积累背景 | 映射 D1 | ✓ pipeline 仍在 session allocation 前 gate/append（live `inbound_pipeline.py:281-315`）；M3 reviewer 轨覆盖。 |
| Scenario：点名带入背景与 sender 顺序 | 映射 D4 | ✓ coordinator transaction 保留 destructive drain 与 prepared parts（live `inbound_pipeline.py:717-767`）；M3 覆盖。 |
| Req 并发：同 session FIFO/跨 session 并行 | 映射 D4 | ✓ 保留 per-session queue 算法并变为 coordinator 私有（`run_queue.py:12-68`; `design.md:142`）。 |
| Scenario：运行中插话及时采纳 | 映射 D4 | ✓ steer admission 与 race fallback 同锁，M3 race exit 覆盖。 |
| Scenario：活动 `/stop` | 映射 D4 | ✓ submit-marker 与 stop 同锁，mark→interrupt→append→reconcile 顺序完整。 |
| Scenario：空闲 `/stop` | 映射 D1/D4 | ✓ 群 idle 在 binding 前零副作用，direct 返回既有友好提示（`design.md:149`; live `inbound_pipeline.py:1041-1080`）。 |
| Scenario：quiet alive 不误杀、stall 释放 queue | 映射 coordinator watchdog | ✓ liveness/terminal/finally 归同 owner，M3 reviewer/worker 轨覆盖（live `inbound_pipeline.py:1458-1579,640-674`）。 |
| Req 图片：成功 | 映射 D5/M2 | ✓ typed resolver 保留 raw/test 和生产 fetch/validate，M2 reviewer 轨覆盖。 |
| Scenario：下载/超限/损坏失败 | 映射 D5/coordinator | ✓ failure 在 submit 前走原 visible control reply，不写 Kernel history（`design.md:160-164`; M2 exit）。 |
| Req 投递：中间/最终不重漏、NO_REPLY 不泄漏 | 映射 existing observer + D4/D6 | ✓ event translation不重写，detached sends纳入 tracker，M3覆盖 NO_REPLY/terminal。 |
| Scenario：后台任务回原会话且不重复 | 映射 D3/D6/M2 | ✓ subscriber 保持至 Kernel terminal，dedupe/replay不顺改；M2 reviewer 轨覆盖。 |
| Scenario：外部/影子 trigger-source 边界 | 映射 D1/existing delivery | ✓ shadow sync 与 external mirror规则复用，M3 reviewer 轨覆盖。 |
| Scenario：IM 离线外部 channel 可用 | 映射 best-effort shadow/delivery | ✓ 不改变 IM best-effort 与 external outbound，M2/M3/runbook 覆盖。 |
| Req lifecycle：启动/停止/重连遵循 461，不增进程/config/readiness | 映射 dependency/D6 | ✓ 不动 parent daemon/PID/readiness/config面；80% 是 child 内部常量。O(1) seal→Kernel close→consumer/delivery drain只深化 461 明确留给后续 unit 的 child resource order（`design.md:179-191`）。 |
| Scenario：停止时 accepted work 有明确结局 | 映射 D6/M2 | ✓ dispatcher/internal handler/heartbeat/cron/subscription/coordinator先同步 seal；queued/transition/active分别 failed、settle、交Kernel terminal；Kernel后并发 drain所有consumer，最后delivery→IM（`design.md:179-193`）。 |
| Scope：只改 Gateway inbound 子图及直接 wiring/tests | 检查模块与依赖 | ✓ 未改 IM/channel protocol、SDK 或持久化格式；internal dispatch/cron/observer 属真实 inbound 协作者，纳入不越界。 |
| Non-goal：不新增功能、不改协议/schema/readiness | 检查 D1-D9/delta | ✓ 所有变更均是 ownership/close grounding；无 operator config 与 wire/schema delta。 |
| 迁移 1：以 461 为基线 | 映射 branch/milestone | ✓ 三个 M 均从 refactor-461 开始，避免同时改旧 composition root。 |
| 迁移 2：完整行为切片、单 owner、无双写 | 核 M1-M3 | ✓ 三 M 串行，每步删除旧 owner；M2 queue resource语义由 M3 原样私有化。 |
| 迁移 3：删除 private wiring/wrapper/shared dict | 核 D7/D8 exits | ✓ architecture guard 与删除标准明确。 |
| 迁移 4：public 测试替代 white-box | 核 D8 | ✓ 明确不是 108 处一比一迁成新 private access。 |
| 迁移 5：原子回退、无长期 flag/shim | 核风险表 | ✓ 每 M 可 revert，无数据 migration/双写/compat alias。 |

### delta-spec 与 milestones

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| kernel: no spec delta | 对照 SDK/462 | ✓ 仅消费现有 SDK，不改 Kernel observable。 |
| im: no spec delta | 对照 node/relay protocol | ✓ frame、ack、shadow、dedupe 均不改。 |
| gateway: no spec delta | 对照 canonical lifecycle/routing | ✓ canonical 已承诺“先停 producer→Kernel终态→最后资源”和 route/delivery 不变量（`docs/specs/gateway/service-lifecycle.md:14-20`; `routing-delivery.md:14-20,143-191`）；本 unit 只兑现既有行为。 |
| cli: no spec delta | 查 scope | ✓ 不在调用面。 |
| M1：live agent + Gateway session ownership | 核垂直性、范围、两轨 | ✓ internal dispatch、cron、heartbeat、fork、delivery、config sync 全在范围；reuse/create/internal-ack/fork-await 四类 race 与 stale rollback 都有明确 exit（`design.md:388`）。 |
| M2：image + background + ingress resources | 核垂直性、shutdown 图、两轨 | ✓ internal handler/heartbeat/cron/accepted root/queue worker/subscriber/delivery task均入台账；任何 await前建 deadline、O(1) seal、settle→Kernel→并发 consumer drain→delivery→IM 顺序与 timeout isolation 都有 exit（`design.md:389`）。 |
| M3：SessionRunCoordinator + final façade | 核原子边界、两轨 | ✓ queue/steer/stop/terminal 共享一状态机；submit-marker race已拍死，M2 close语义只私有化不重写。 |
| 三个串行 milestone 是否允许 | 核硬拆分举证与范围交集 | ✓ >1,200 LOC、>20 files、三个可独立替换 owner，命中单 worker窗口；因共同改 composition root 明示串行且每步单 owner。这是纵向 ownership slice，不是数据/业务/测试横切（`design.md:374-382`）。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | Catalog / Binder / Coordinator | ✓ live config与channel binding属于 Gateway产品层，run admission/stop属于 Gateway session状态机；都只依赖 `agent.sdk`，不下沉或反向依赖 Kernel。 |
| 归属 | refactor-461 / 462 边界 | ✓ 461保留 parent daemon/PID/SIGKILL ownership，463只深化 child inbound close；462拥有Kernel conversation/resource permit，binder不复制它。 |
| 归属 | producer seal/drain | ✓ dispatcher/internal-handler/heartbeat/cron/subscriber/coordinator 各自拥有 O(1) admission flag，`GatewayRuntime` 只排全局拓扑与 deadline；owner 不外泄 task集合，composition root也不替模块实现内部 drain（`design.md:179-193`）。 |
| 该不该存在 | LiveAgentCatalog | ✓ 删除会让消息/scheduler/shim/internal dispatch/config sync重共享裸 dict；不是 getter wrapper。 |
| 该不该存在 | GatewaySessionBinder | ✓ 删除会让 resolve/validation/reverse/canonical/conversation/fork散回多调用方；memory/SQLite 是两个真实 adapter。 |
| 该不该存在 | SessionRunCoordinator | ✓ 删除会重建 queue/active/steer/stop/watchdog/reconcile多 owner；是最深模块。 |
| 该不该存在 | Resolver / SubscriptionManager / TaskTracker | ✓ 三者分别拥有完整 media policy、跨 session subscriber set、detached delivery task set；删除后不变量重新散开，均非假想多态。 |
| 深还是浅 | pipeline façade + existing runtime_delivery | ✓ route/gate紧邻且无长期 state；delivery事件语义原样复用，只增加 concrete task owner，认知面收敛。 |
| 深还是浅 | binder revision协议 | ✓ `ConversationBindResult(bound|stale)` 把 internal-ack/fork-await 后的写回竞争隐藏在 binder，调用方只处理 typed result；repository/current/generation 不泄漏（`design.md:131-137,244-285`）。 |
| 治本还是补丁 | candidate 4 总体 | ✓ 状态、接口、composition、测试同时收口，不以拆文件/LOC冒充治理。 |
| 治本还是补丁 | shutdown absolute deadline | ✓ shutdown起点在 request时记录，所有逻辑 seal不 await，settle/Kernel/AppRunner/heartbeat/cron/roots/workers/subscribers/delivery都消费同一 absolute deadline；单项异常不跳过其他收拢，parent SIGKILL只保留最终 hard bound（`design.md:183-191`）。 |

## Issues

- 无。

## Recommendations

- 可进入 `change-orchestrator`。实施时按 M1 → M2 → M3 串行推进，不要把 M2 已拍死的 queue seal/drain 语义在 M3 另写一套。
- shutdown 测试要保留 active heartbeat 与 in-flight internal HTTP handler 两个真实阻塞桩；它们是验证“Kernel close 不被 producer join 卡住”的关键门禁。
