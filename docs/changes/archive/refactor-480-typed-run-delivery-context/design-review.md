# Design 评审：refactor-480-typed-run-delivery-context（v2）

**结论：Approved**

v2 已关闭上一轮的两项 CRITICAL 和一项 WARNING。方案现在把生产 observer 的完整事件面、await/detach 所有权、IM 离线分支、外部 shadow partial order、process-scoped task tracker 及 shutdown drain 拍成封闭契约；同时把 owner-direct terminal 输出收窄为精确 frozen projection，并为 relay/owner-direct 两类运行指定唯一、幂等的 cleanup owner。未发现仍会让 worker 自行发明并发、终态或调用方协议的设计缺口。

## 核实台账

| 原子项 | 核实动作 | 结论与证据 |
|---|---|---|
| 原始诉求与自主推进边界 | 对照 motivation 原文、澄清记录与单 M1 方案 | ✓ unit 仍是独立架构重构单元，设计无待用户逐项拍板的 TBD；单 M1 给出了明确范围与双轨退出标准（`motivation.md:11-24`; `design.md:241-247`）。 |
| 澄清 Q2：不重做 delivery owner | 从决策和依赖方向反查归属 | ✓ 所有新增/删除 seam 均留在 Gateway `runtime_delivery` 及其真实 scheduler/composition caller；没有把 policy 回流到 IM transport、inbound pipeline 或 kernel（`design.md:34-46,69,93-167`）。 |
| 现状痛点：typed + legacy 双 authority | 全仓追 `RunDeliveryContextStore`、mapping façade、terminal stream | ✓ 当前 store 同时维护 `_contexts` 与 `_legacy_contexts`，observer 经 `RunDeliveryRuntimeView` 字符串读写，stream 又转回 legacy dict（`context.py:101-203,205-322,351-366,456-459`; `stream.py:16-30,136-170`）。设计对现状判断成立。 |
| 删除测试：legacy seam 是否有独立生产价值 | 搜索 `_legacy_contexts`、`runtime_view`、`to_legacy_dict` 与 dict fallback 的生产使用点 | ✓ 未发现需要保留 legacy representation 的独立生产消费者；删除后复杂度不会等量搬到调用方。D1 直接删除 mirror/façade/fallback，而非叠第三层 adapter（`design.md:48-53,93-97`）。 |
| 生产 composition：唯一 store | 正向追 composition 到 relay、observer、heartbeat、cron | ✓ composition 创建一个 `RunDeliveryContextStore`，同一实例传给 cron、relay lifecycle、observer 与 heartbeat（`composition.py:266-282,416-458,528-545`）。D1 的 single typed map 与真实装配吻合。 |
| 生产 relay 链 | 追 accepted seed、observer、terminal lifecycle | ✓ relay accepted 在 stream 前 seed；kernel event 逐条进入 observer，返回 coroutine 时由 coordinator await；terminal lifecycle 最后 discard（`session_run_coordinator.py:439-505,959-1055`; `lifecycle.py:31-47,143-216`）。设计没有发明测试旁路。 |
| 生产 owner-direct 链 | 追 heartbeat/cron 到共享 stream helper | ✓ heartbeat 与 cron 都经 `stream_run_to_completion()`；heartbeat 是 terminal context 的唯一真实消费者，只判断 resolved conversation，cron 仅读 status/final_text/error（`heartbeat_runner.py:196-263`; `cron_execution_service.py:355-392,516-557`）。 |
| typed target 的领域边界 | 核 `RunDeliveryTarget` 及 canonical owner-direct/shadow 约束 | ✓ `shadow`、`owner_direct`、`none` 是显式 variant，owner proactive run 不伪装 shadow（`context.py:18-56,324-349,368-454`; `docs/specs/gateway/heartbeat-cron.md:19-34,60-93`）。 |
| 每 run 单 context、seed 不覆盖 | 核当前 store 与 D1/D5 | ✓ 当前 `seed()` 保留 live entry（`context.py:357-366`）；设计继续由 store 负责 seed/get/take/discard，并要求 shared atomic pop（`design.md:93-97,155-178`）。 |
| 领域 mutation 是否足够深 | 对照当前 19-key translator 与状态组合 | ✓ ack backfill、bubble replace、external text、visibility/discard、rolling 都包含复合不变量。D2 禁止万能 setter，能把字符串真假值和合法跃迁隐藏在领域动作后（`context.py:59-137,140-189`; `design.md:99-101,171-178`）。 |
| observer owner 与 handler 粒度 | 穷举生产 observer 分支并做模块归属攻击 | ✓ 保留单一 `observe(event)` orchestration owner，按稳定事件族拆 handler；handler 不各持 map/subscriber/task set，避免“一 event 一类”的浅抽象（`observer.py:130-195,337-391`; `design.md:103-107`）。 |
| `skill_created` | 追 IM gate 前后顺序 | ✓ 当前 side effect 在 connected gate 前交 tracker（`observer.py:337-366`）；matrix 明确“IM 离线仍执行、`to_thread` 交共享 tracker”（`design.md:118-120`）。 |
| `run_status(running)` | 追 turn-start ACK 与 owner-direct lazy path | ✓ 普通 target 必须 await ACK 后回填 message id，owner-direct 等首个可见正文；matrix 保留 ordering-critical awaitable（`observer.py:392-433`; `design.md:121`）。 |
| `assistant_message` / reasoning | 追 silence、visibility、lazy ACK、roll 与普通 delta | ✓ matrix 明确先做 typed mutation；lazy start/missing start/换泡返回 awaitable，普通正文与 reasoning 交 tracker（`observer.py:435-766`; `design.md:122`）。没有把所有 I/O 错误统一 inline await。 |
| `turn_end` | 追 discard、normal completion、external final 与 offline 分支 | ✓ matrix 区分 ordering-critical discard 与 detached completion；先同步清理状态/判 discard，外部主路径不受 IM offline gate 阻断（`observer.py:768-856`; `design.md:123`）。 |
| `run_heartbeat` | 追 relay liveness canonical 与实现 | ✓ 仅在已有 message id 且 IM connected 时发 liveness，不改正文/context，并交 tracker（`observer.py:858-878`; `design.md:124`; `docs/specs/im/gateway-relay.md:125-152`）。 |
| `tool_start` / `tool_end` | 追 in-flight 状态先后与投递 owner | ✓ matrix 分别要求先同步登记/移除 in-flight tool，再构造 side effect；IM/external awaitable 交 tracker（`observer.py:880-1022`; `design.md:125-126`; `docs/specs/im/tool-timeline.md:14-44,187-227`）。 |
| `permission_request` / `permission_resolved` | 追 external first-wins、IM card 与 offline gate | ✓ external sender 不受 IM connected gate 影响，IM card 仅在可连时投递，全部异步 side effect 有 tracker owner（`observer.py:1024-1089`; `design.md:127-128`; `docs/specs/gateway/external-channels.md:151-180`）。 |
| `injection_consumed` | 追 steer roll 的用户可见顺序 | ✓ 保留同 run，旧泡完成后 ACK 新泡并回填 id，返回 ordering-critical awaitable（`observer.py:1091-1135`; `design.md:129`; `docs/specs/gateway/routing-delivery.md:107-143`）。 |
| `run_terminal_reconcile` | 追异常终态清理与 observer/context owner 边界 | ✓ 先同步清 reasoning/in-flight，再为未闭 tool/bubble 构造确定 terminal payload；side effect 交 tracker，context 留给 lifecycle/stream cleanup（`observer.py:1137-1231`; `session_run_coordinator.py:1018-1055`; `design.md:130`）。 |
| 未列 event 的语义 | 检查 dispatch 是否仍有隐式 fallback | ✓ matrix 明确封闭，未列 event 只能 explicit no-op/diagnostic，不能借 fallback 进入任一 handler（`design.md:115-116`）。 |
| await/detach 双执行所有权 | 对照 observer 返回契约、coordinator await 与 tracker | ✓ D3 明确：只有 ACK/roll/discard 等后续事件依赖的新状态返回 awaitable；普通 message/tool/permission/end/reconcile/liveness 交 process tracker（`observer.py:151-155,197-205`; `session_run_coordinator.py:993-996`; `design.md:109-130`）。 |
| process-scoped tracker | 追创建、注入与任务生命周期 | ✓ composition 创建唯一 tracker并注入 observer/runtime（`composition.py:424-458,606-620`）；tracker负责 admission、异常隔离、deadline drain 与 leftover cancel（`task_tracker.py:13-96`）。设计明确原样保留，不允许 handler 自建 untracked task（`design.md:109-113`）。 |
| shutdown drain 顺序 | 追完整 shutdown resource graph | ✓ 当前先 seal producer、关 kernel、drain consumer，再 `RuntimeDeliveryTaskTracker.close_and_drain()`，最后 drain/close IM transport（`runtime.py:315-440`）；设计与 M1 退出标准保留此 partial order（`design.md:45-46,109-113,219-225,247`）。 |
| 外部 shadow durability partial order | 追 prepare、external sender、IM mirror 的真实执行顺序 | ✓ 当前先同步 `shadow_output_prepare`，mirror 与 coroutine external sender登记进 tracker，IM mirror 不阻塞外部主路径（`observer.py:234-272`）。D3 精确规定 prepare 先于二者、sender 与 mirror 之间无 await 依赖，tracker覆盖所有已接收 async side effect（`design.md:132-135`）。 |
| IM 离线外部自治 | 对照 observer gate 与 canonical | ✓ external context 可绕过 IM connected gate，外部 reply/permission 路径继续，shadow mirror best-effort（`observer.py:362-391,1024-1089`; `docs/specs/gateway/external-channels.md:182-218`; `design.md:120-130,132-135`）。 |
| terminal DTO 的必要信息 | 从所有生产 consumer 反推最小投影 | ✓ heartbeat 只需知道是否解析出 conversation，cron完全不读 context（`heartbeat_runner.py:232-254`; `cron_execution_service.py:516-557`）。D4 固定为 frozen/slots `RunDeliveryTerminalProjection(resolved_conversation_id: str | None)`，没有泄漏 target/bubble/rolling/external marker（`design.md:137-153`）。 |
| `StreamRunOutcome` exact contract | 核字段名、类型与三态 | ✓ 最终字段固定为 `delivery: RunDeliveryTerminalProjection | None`；missing run 与“存在但未建立 visible conversation”可区分，conversation id 做 strip/None 归一化（`design.md:141-151,178`）。旧版字段名/type歧义已消失。 |
| owner-direct cleanup | 追 stream normal/error/close 路径 | ✓ 当前 finally 已是 cleanup owner（`stream.py:61-118`）；D5 将其拍成同步原子 `take()`，completed/failed/cancelled/iterator exception/early close 均先删 live entry，再立即生成最小 projection（`design.md:155-161`）。 |
| relay cleanup | 追 lifecycle terminal 与重复/missing 语义 | ✓ lifecycle仍是唯一 owner；`discard(run_id) -> bool` 对 completed/failed/cancelled、重复 terminal 和 missing entry 幂等 no-op，并与 `take` 共用内部 pop primitive（`lifecycle.py:31-47`; `design.md:163-166`）。 |
| cleanup 后 detached task 安全 | 检查 payload capture 规则 | ✓ D5 禁止 detached task在 cleanup 后重读 live context，只能捕获已构造 payload/不可变 projection；observer自身永不删除 context（`design.md:163-167`）。这关闭了 tracker drain 与 terminal pop 并存时的生命周期悬空点。 |
| 普通 owner 对话验收 | 将 motivation Scenario 映射到 matrix/canonical | ✓ turn-start ACK、stream delta、visibility、completion 各有明确 typed mutation和 await/detach owner（`motivation.md:43-47`; `design.md:121-123`; `docs/specs/gateway/routing-delivery.md:14-53`）。 |
| shadow 与 rolling 验收 | 将 Scenario 映射到 partial order 与 roll handler | ✓ shadow target、durable prepare/external/mirror partial order、bubble roll/steer ACK 均有唯一落点（`motivation.md:49-51`; `design.md:122-123,129,132-135`）。 |
| IM 离线外部 channel 验收 | 将 Scenario 映射到 offline gate | ✓ external reply/permission不依赖 IM connected，shadow mirror 仍为 best-effort detached（`motivation.md:53-56`; `design.md:123,125,127-128,132-135`）。 |
| 工具、权限与 liveness 验收 | 将两个 Scenario 映射到封闭 matrix | ✓ tool/permission 的状态顺序与 terminal owner逐项列出；`run_heartbeat` 是独立必保分支（`motivation.md:58-66`; `design.md:124-128`）。 |
| IM 离线 skill-created 验收 | 将 Scenario 映射到 gate 前 side effect | ✓ matrix与风险测试要求覆盖该路径（`motivation.md:68-70`; `design.md:120,219-223,247`）。 |
| 终态与 shutdown 验收 | 将两个故障 Scenario 映射到 D3/D5/resource graph | ✓ relay/owner-direct 两类终态、异常 reconcile、take/discard 幂等和 tracker-before-transport drain 均有 exact contract（`motivation.md:72-80`; `design.md:109-113,130,155-167,219-226,247`）。 |
| 非目标与 delta-spec | 核影响面及 canonical 可观察行为 | ✓ 不改 IM API/wire frame/kernel event contract；kernel、im、gateway、cli 均 no spec delta 合理，因为方案只替换 Gateway 内部 representation，并逐条守住既有行为（`motivation.md:82-92`; `design.md:209-214`）。 |
| 迁移、风险与回滚 | 核是否会留下中间双 authority | ✓ 先固化现有顺序测试，再一次完成 typed-only cutover；风险表覆盖 truthiness、dispatch trace、offline shadow、四类 stream exit、relay重复 terminal 与 shutdown order；回退是整体回滚，不重引双写（`motivation.md:94-96`; `design.md:216-227,241-247`）。 |
| Runbook 与验收前置 | 对照仓库服务约束 | ✓ 使用 worktree `e2e-up/down`、隔离 config/高位端口和真实 Web IM/外部 fixture，给出了停止、启动、健康检查、驱动方式和资源来源（`design.md:229-239`; `AGENTS.md:181-319`）。 |
| CC 对照 | 直接核本机 Claude Code 源码 | ✓ `QueryEngine.submitMessage()` 返回 `AsyncGenerator<SDKMessage,...>`；bridge ingress guard只检查 object 上存在 string `type`，生成的 `SDKMessage` 是 open record（`~/Repos/opensource-hub/claude-code/src/QueryEngine.ts:217-220`; `src/bridge/bridgeMessaging.ts:46-55,224-294`; `src/entrypoints/sdk/coreTypes.generated.ts:348-379`）。v2 已收窄为“内部单一 typed state、边界一次投影”，没有再误称封闭 discriminated union（`design.md:61-69`）。 |
| 聚焦基线验证 | 运行 tracker、shutdown graph、stream、external-visible、heartbeat、cron 现有测试 | ✓ 37 passed；当前调用链与设计引用的 baseline 一致。该结果只证明设计 grounding，不替代 M1 实现后的完整验收。 |
| 上轮 CRITICAL C1 | 逐项复查 event/await/detach/offline/mutation/shutdown 缺口 | ✓ 已关闭。十一行封闭 matrix覆盖全部生产事件族；共享 tracker、外部 shadow partial order、offline gate 和 shutdown drain均被拍死，并进入风险测试与 M1 退出标准（`design.md:103-135,218-226,247`）。 |
| 上轮 CRITICAL C2 | 复查 terminal projection、字段名/type、take/discard、幂等与泄漏 | ✓ 已关闭。frozen DTO、`StreamRunOutcome.delivery` 三态、原子 `take`、幂等 `discard`、共享 pop primitive、两类唯一 cleanup owner及 detached payload约束均为精确 contract（`design.md:137-167,171-178,224-226,247`）。 |
| 上轮 WARNING W1 | 复查真实 terminal caller 与 M1 scope | ✓ 已关闭。现状和 M1 均明确列出 `heartbeat_runner.py` 与 `cron_execution_service.py`/terminal consumer，不再把无关 `runtime_delivery/background.py` 当 typed-store caller（`design.md:19-24,247`）。 |

## 架构进攻

| 角度 | 攻击对象 | 结论 |
|---|---|---|
| 归属是否自然 | typed store、observer orchestration、tracker、relay lifecycle、owner-direct stream | ✓ 都服务于 run-to-delivery 状态和副作用生命周期，继续归 `runtime_delivery`/Gateway composition 自然；IM connection只拥有 transport，scheduler只消费窄 terminal projection。没有反向依赖或第二 owner。 |
| 组件是否该存在 | legacy mirror/façade/fallback | ✓ 不该存在，删除测试通过；它们只复制 state 和转换 truthiness。方案直接删除，不把同等复杂度搬到 caller。 |
| 组件是否该存在 | event-family handlers、process tracker、terminal projection | ✓ 都有独立且稳定的变化轴：事件族隐藏各自状态机，tracker跨调用栈拥有 detached I/O，projection隔离 scheduler 与 mutable run state。删除任一都会把并发/生命周期复杂度重新泄漏给 caller。 |
| 接口够不够深 | domain mutation + closed dispatch + one-field frozen projection | ✓ 外部只看意图动作、一个 observer入口和一个 resolved-conversation 终态信号；字符串 key、bubble ids、rolling guard、shadow marker、task set均留在实现内。接口明显小于隐藏复杂度。 |
| 是治本还是补丁 | typed-only authority 与 terminal cleanup | ✓ 一次删除双写和 dict fallback，不加兼容期；await/detach、offline与durability顺序作为 first-class contract保留；两类终态共享 atomic pop但不混淆 owner。属于删除错误 seam、固化真实边界的治本重构。 |

## Issues

- 无。

## Recommendations

- 无阻断建议。可按 M1 进入实现；实现验收继续以十一类 event trace、真实 IM-offline external 路径、tracker-before-transport shutdown order，以及 completed/failed/cancelled/early-close 的 take/discard 无泄漏为硬闸。
