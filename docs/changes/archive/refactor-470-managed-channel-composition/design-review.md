# Design 评审：refactor-470-managed-channel-composition

**结论**：Approved

**核实台账**（逐条核过的承重原子；证据为 reviewer 自行追到的生产代码、canonical spec 或首文档）：

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：`main.py` 3987 行、`build_runtime()` 927 行且混合装配与策略 | 直接核文件、函数边界和局部定义 | ✓ `main.py` 当前 3987 行，`build_runtime` 为 `main.py:2060-2986`；credential、provider、status、bootstrap、register-ready 等局部函数均位于该函数内（`src/personal_assistant/main.py:2244-2689`）。 |
| 现状：`GatewayRuntime` 是生产 runtime owner | 从模块入口正向追生产 wiring | ✓ `main()` 经 foreground/background lifecycle 调到 `build_runtime()`，返回对象实际执行 `GatewayRuntime.run_forever()`（`src/personal_assistant/main.py:912-999,1519-1562,2971-2986,2989-3078`），不是测试旁路。 |
| 现状：runtime resource graph 是成熟整体 | 核启动、关闭与 shared deadline | ✓ static/managed channels、IM watchdog、heartbeat、Kernel、cron、delivery 的启动与关闭顺序由同一类持有（`src/personal_assistant/main.py:925-1147`），符合整体迁移而不拆算法的前提。 |
| 现状：process lifecycle 是成熟整体 | 从 CLI 的 start/stop/restart 追到进程控制 | ✓ CLI 命令直达 foreground/background/stop/restart（`src/personal_assistant/main.py:3051-3071`）；config lock、PID/process birth、signal、状态采纳和升级停止集中在 `main.py:1519-1805,3521-3959`。 |
| 现状：heartbeat runner、IM bootstrap、Kernel adapter 都是生产使用的成形模块 | 核类边界与构造点 | ✓ 三者分别定义于 `main.py:350-540,543-780,1808-2000`，并由真实 `build_runtime` 构造注入（`main.py:2161-2166,2631-2635,2898-2916`）。 |
| 现状：managed-channel integration policy 滞留 composition | 从 manifest、provider worker 到上行结果正反追踪 | ✓ key/store、private skill activation、provider factory、manifest apply、status/metadata、ACK/retry、reconnect、legacy bootstrap 和 register replay 均在 `main.py:2244-2689`，直到 `main.py:2762-2771,2921-2956` 才装入 manager/transport。 |
| 现状：存在 nullable IM 构造环 | 核对象创建顺序与 closure 捕获 | ✓ `im_connection_manager` 先设为 `None`（`main.py:2174`），status/result/register-ready closure 在对象构造前捕获它（`main.py:2365-2375,2583-2604,2662-2689`），实例到 `main.py:2921` 才赋值。 |
| 现状：skill activation 穿透 private API | 核调用点与被调定义 | ✓ `_activate_feishu_skill` 直接调用 `_local_agent()` / `_enable_created_skill_for_agent()`（`main.py:2333-2343`），二者是 `gateway/agent_config_sync.py:302,377` 的 private 方法。 |
| 现状：38 个测试文件依赖 `personal_assistant.main` 表面，另有 location-sensitive contract | AST/文本全量扫描而非抽查 | ✓ 38 个 `test_*.py` 通过 import、importlib 或 monkeypatch 引用该模块，另有共享 runtime test helper；`test_personal_assistant_main_contract.py:13-16` 与 `test_gateway_inbound_ownership_contract.py:122-213` 明确把 runtime/kernel adapter 位置写在 main。设计以 38 为测试基线并要求剩余文件全部对账（`design.md:30-33,498`），不会再按旧 24 漏算。 |
| 约束：PA 只能经 `agent.sdk` 使用 Kernel | 全量核生产 import 与顶点规约 | ✓ PA 当前生产路径未 import `agent.core` / `agent.platform`；硬规则见 `SPEC.md:163-168`，设计在 `design.md:37-38` 明确保留。 |
| 约束：`ChannelManager` 是动态 runtime/generation 唯一 owner | 核 canonical 与 live state | ✓ canonical 明定唯一 `ChannelManager`（`docs/specs/gateway/external-channels.md:230-236`）；真实 `_active/_desired`、cutover、reconnect、close 在 `gateway/channel_manager.py:198-239,347-545,698-790`。 |
| 约束：store 与 IM transport ownership 不复制 | 核 durable outbox 与 wire owner | ✓ reconcile/status outbox 在 `gateway/channel_manifest_store.py:288-460`；register gate、single wire owner、pending FIFO、correlation 与 reconnect 在 `ws/im_connection.py:296-320,687-760,1366-1415`。设计把 mailbox 限定为 ephemeral wake-up（`design.md:132-137,156-162,289-297`）。 |
| 约束：bootstrap handshake 与 legacy YAML importer 是不同能力 | 追 wire request/result 和本地 provider/cleanup | ✓ transport 在 `ws/im_connection.py:827-872,1382-1415` 处理 `channels.bootstrap.request/result` 与 correlation；旧 YAML 读取、seal、cleanup 是 `main.py:2462-2545` 的独立 provider/callback。设计按此边界只删后者（`design.md:176-205`）。 |
| 约束：旧 standalone YAML 仍可作为 static channel 启动 | 追 config parser 到 static registry | ✓ parser 接受 `appSecret` 或 `credentialRef`（`config/local_store.py:1021-1030`）；static registry 对带 `appSecret` 的 `feishu:*` 构造 adapter（`main.py:3098-3146`），所以删除 managed importer 不会删除 standalone 启动能力。 |
| 复用：manager 四个生命周期入口真实可用 | 核方法与 production caller | ✓ `start_cached/reconcile/reconnect/close` 位于 `gateway/channel_manager.py:246,347,500,545`，生产分别从 runtime、manifest apply、targeted reconnect 与 shutdown 调用（`main.py:973-974,2454-2460,2615-2629,1028-1033`）。 |
| 复用：store/apply 已覆盖持久化与解析 | 核真实实现 | ✓ durable reconcile/status 位于 `channel_manifest_store.py:288-460`；credential 解封后的 payload→manifest→manager 流程已在 `gateway/channel_manifest_apply.py`，生产由 `main.py:2454-2460` 调用。 |
| 复用：IM manager 已拥有 channel wire/FIFO | 核 constructor、frame dispatch 和 send ownership | ✓ current typed handlers 在 `ws/im_connection.py:150-158,238-293`，channel frame dispatch 在 `687-903`，唯一 business wire owner/correlation 在 `1366-1415`。 |
| 历史：refactor-461 的 lifecycle 不变量必须保留 | 对照历史设计与当前实现 | ✓ 历史明确不重排 producer/channel/kernel/cron/IM 关闭顺序（`docs/changes/archive/refactor-461-dead-kernel-subprocess-seam/design.md:329`）；当前实现见 `main.py:1000-1147`，本设计只移动物理归属（`design.md:223-225,357-367`）。 |
| 历史：refactor-463 的 concrete owner / 无 re-export 模式可复用 | 对照历史设计与现有 owner | ✓ 历史要求 concrete owner、测试真实 owner、main 不留 private re-export（`docs/changes/archive/refactor-463-inbound-pipeline-ownership/design.md:59,125,163`）；本设计在 `design.md:227-243` 延续同一约束。 |
| 历史：feat-464 已选 `ChannelManager` 为唯一动态 lifecycle owner | 对照历史设计、canonical 与代码 | ✓ 历史决策原文见 `docs/changes/archive/feat-464-im-channel-settings/design.md:194-220`，canonical 与当前代码均已落地；本设计没有再造 runtime map。 |
| 决策 1：`compose_gateway(config) -> GatewayRuntime` 为单装配入口 | 核是否拍死、是否与入口目标一致 | ✓ 返回型、原子失败和 main 委托均明确（`design.md:123-130,167-168,207-243,247-257`）；worker 无需猜多个 composition 入口。 |
| 决策 1：`ManagedChannelControl` 三入口 + immutable bindings | 核接口、调用方和隐藏复杂度 | ✓ `start_cached/connection_bindings/close` 已拍死，bindings 对应 manifest/reconnect/ACK/status/register-ready，control 内组合 manager/store/key/apply/provider/activation（`design.md:125-142,247-287`）。 |
| 决策 1：mailbox 仅承载 typed status/metadata | 对照 worker-thread producer、持久化与断线重放 | ✓ provider worker 确会在线程回调 status/metadata（`main.py:2345-2386`；`gateway/channel_manager.py:698-773`）；status 先落 store、metadata 先落 manifest，register-ready 可重投影。设计只允许两个 typed emission，禁止 durable/ACK owner（`design.md:132-137,156-162,278-294`）。 |
| 决策 1：`fatal_owner_mismatch` 同 receive stack 关闭 | 追 current close-before-flush 顺序 | ✓ current handler 在 `main.py:2567-2588` 同步 close，frame owner随后才可能 flush（`ws/im_connection.py:883-903`）；最新版明确让 handler 返回 `CLOSE_CONNECTION`，由 IM receive owner 先 `await close()` 再 return（`design.md:160-162,284-297,329-333`），首轮 CRITICAL 已实质关闭。 |
| 决策 1：`retryable_store_busy` 保持 store request-id 权威 | 核现有 ACK 推进和新边界 | ✓ store 仅在当前 request 上产生 `next_payload`（`channel_manifest_store.py:421-460`），现有代码发送前重核 pending 状态（`main.py:2592-2613`）；设计仍由 control 调度且以 store request id 判定（`design.md:329-333`），没有复制 retry owner。 |
| 决策 1：公开 skill activation operation | 核是否消除 private 穿透且不造假协议 | ✓ 只给 concrete `IMAgentConfigSync` 增加 `ensure_agent_skill_enabled`（`design.md:163-164`），正对 `main.py:2333-2343` 的穿透点，不引入单实现 Protocol。 |
| 决策 1：不造 provider plugin / generic event bus | 核真实变化驱动与 YAGNI | ✓ 当前 provider factory 只有真实 Feishu 分支（`main.py:2388-2434`）；设计明确拒绝 provider protocol 和通用 dispatcher（`design.md:144-152,170-174`）。 |
| 决策 2：删除 legacy importer/export 和专用 callback | 对照真实符号与删除清单 | ✓ 清单覆盖 main provider/state/cleanup、local-store migration、export script、专属测试，以及 `IMConnectionManager` 的 provider/applied constructor field 和 callback type（`design.md:184-200`；现状 `main.py:2462-2545,2954-2955`、`ws/im_connection.py:157-158,259-292,827-872`）。不留 no-op callback/alias。 |
| 决策 2：保留 bootstrap wire 后协议仍闭合 | 从 IM register 后 bootstrap 正向追完整 request/result | ✓ IM 在 head 未初始化时下发 request（`src/IM/ws/gateway_handler.py:414-426`）；空 `items` 被 store 合法初始化为空 manifest（`src/IM/infra/channel_control_store.py:346-380`）；IM 回 `channels.bootstrap.result` + manifest（`gateway_handler.py:1333-1359`）；Gateway 的 result correlation 后继续调用同一 manifest handler 并回 reconcile result（`ws/im_connection.py:844-867,1382-1415`）。设计保留这四段、只把 request provider 内联为空 items并删除 cleanup side effect（`design.md:196-200,295-300,495`），协议无断口。`design.md:259-260` 的 “bootstrap use case”由 `apply_manifest` 承接 result manifest，不表示保留 provider callback。 |
| 决策 2 与 motivation clean cutoff 一致 | 逐项对照 Q4、目标、影响和迁移策略 | ✓ Q4 原话与解释已记录（`motivation.md:30-32`）；目标状态、影响范围和 migration 明确 legacy 是唯一退休行为（`motivation.md:44-50,113-120,122-129`）。首轮首文档冲突已关闭。 |
| 决策 3：真实 owner 模块布局 | 将每个目标模块映射到真实生产职责 | ✓ runtime/process/bootstrap/kernel/heartbeat 均对应现有内聚类/块；managed control 对应唯一散落策略；模块职责表与图一致（`design.md:87-119,207-231`）。 |
| 决策 3：`ConnectionReadyCoordinator` 独立拥有跨 owner register-ready 顺序 | 对照现有 callback 的真实变化轴 | ✓ 当前 `_reconcile_on_connect` 确实串行编排 node binding、degraded heartbeat、channel replay/activation/result、agent reconcile（`main.py:2637-2700`）；最新版将它放在 `gateway.connection_ready`，同时把 HTTP-only `im_bootstrap` 限为 binding client（`design.md:218-220,335-355`），首轮归属 WARNING 已关闭。 |
| 决策 3：current sender 消除 on-connected nullable 捕获 | 核调用栈和所需能力 | ✓ callback 当前从 register ACK receive owner 调用（`ws/im_connection.py:792-803,1461-1468`）；真实用途只有 `send_json` 与 `has_pending_request`（`main.py:2662-2689`）。设计把当前 sender 显式传入且只开放这两项（`design.md:337-349`），数据流闭合。 |
| 决策 3：`main` 仅实现 CLI，不保留事实 re-export | 核 Python import 表面与 contract 可守性 | ✓ 模块限定调用、`__all__=["main"]`、按真实 owner 迁测试和反向 architecture contract 均已明确（`design.md:213-243,447-457`），不会留下旧 namespace shim。 |
| Spec Q1：完整覆盖 Candidate 05 | 对照三个决策和 milestones | ✓ managed ownership 在 D1/M1；runtime/kernel/heartbeat 在 D3/M2；process/bootstrap/ready 在 D3/M3；composition/main/tests 收口在 M4（`design.md:123-243,493-498`）。 |
| Spec Q2/Q3：验收成本由 Agent 按受影响面控制 | 核 runbook 分层 | ✓ 最窄 unit/integration + architecture + 全量 non-e2e + 三条关键 e2e + 条件式真实 Feishu，未要求人工重验全部 Gateway 契约（`design.md:404-484`），符合 `motivation.md:24-29,52-54`。 |
| Spec Q4：clean cutoff 且不留旧尾巴 | 核设计所有保留/删除/guardrail | ✓ D2 删除 provider/applied type、migration、script、专属测试；M1 和 architecture grep 要求旧符号归零，standalone static 与 bootstrap wire 明确保留（`design.md:176-205,447-457,495`），与 `motivation.md:30-32,124-129` 一致。 |
| Req 1 / S1：在线保存热连接、真实终态、skill 保持 | 追 D1、M1、runbook 和 canonical | ✓ control 覆盖 apply/provider/status/activation；M1 与真实 smoke 验 online/reconnect（`design.md:139-164,302-327,459-484,495`）；canonical 锚点为 `external-channels.md:238-242,267-271`。 |
| Req 1 / S2：无效配置真实失败且隔离其他 Bot | 核失败路径、唯一 manager 与 fixture | ✓ fail-closed result、targeted manager ownership与无效凭据/多 Bot fixture 均明确（`design.md:329-333,483-484,495`）；canonical 为 `external-channels.md:278-301`。 |
| Req 1 / S3：disable/delete/replace 只作用目标且不清历史 | 核 manager cutover、验证和 canonical | ✓ ChannelManager 继续唯一执行目标 cutover，fixture 明列 disable/delete/replace（`design.md:139-142,483-484`）；canonical 要求 runtime/cache identity 与历史分离（`external-channels.md:250-253`）。 |
| Req 2 / S1：IM 离线 cached startup | 核启动序列和真实 smoke | ✓ managed cache 在 IM watchdog 前启动（`design.md:357-361`），runbook 第 4 步要求不可达 IM 下真实消息往返（`design.md:476-478`）；canonical 为 `external-channels.md:244-248`。 |
| Req 2 / S2：重连收敛、未确认结果重放且旧状态不覆盖 | 核 store、connection-ready 和 FIFO | ✓ store 仍是 durable authority，ready coordinator重放 pending status/metadata/reconcile 并保留 generation/request-id guard（`design.md:132-162,329-355`）；canonical 为 `external-channels.md:255-265,303-306`。 |
| Req 3 / S1：start/stop/restart 不变 | 核 module move、shutdown与 e2e | ✓ process lifecycle 整体迁移，M3 覆盖重复启动/stop/restart，runbook执行 restart continuity（`design.md:215-225,404-445,497`）；canonical 为 `service-lifecycle.md:14-59`。 |
| Req 3 / S2：auto-bind 不变 | 核 bootstrap owner和测试 | ✓ IM bootstrap client整体迁移且仍由 register-ready 调用，M3与 `test_auto_bind.py` 覆盖（`design.md:218-225,337-355,422-427,497`）；canonical 为 `service-lifecycle.md:151-169`。 |
| Req 4 / S1：heartbeat 有内容冒泡、无内容静默 | 核 runner 迁移、验证与 canonical | ✓ runner 只物理迁移，M2要求原行为与 shutdown 测试；full non-e2e 兜底（`design.md:220-225,404-445,496`）；canonical 为 `heartbeat-cron.md:60-68`。 |
| Req 4 / S2：cron 定时/手动同语义且隔离 | 核 scope、回归与 canonical | ✓ cron service 算法不改，M2迁相关 tests，critical cron e2e列入 runbook（`design.md:404-445,496`）；canonical 为 `heartbeat-cron.md:29-34,41-58,75-78`。 |
| 范围/非目标：不改 IM、Kernel、CLI、外部 channel 协议，不新增 provider/UI | 核新增接口和 delta 声明 | ✓ 所有新接口均为 PA 内部；D1拒绝 provider plugin，D3不越过 SDK，无前端路径；bootstrap wire schema保持不变（`design.md:144-174,207-243,369-381`）。 |
| 影响分类：行为重验 vs 仅 import 迁移 | 核 tests 与 runbook | ✓ channel/runtime/lifecycle/bootstrap/heartbeat/cron 有聚焦行为测试；inbound/permission/delivery 等只迁 import 后由全量 non-e2e守护（`motivation.md:113-120`；`design.md:404-457`），没有虚增人工旅程。 |
| 迁移 1：行为切片、每片可验证回退 | 核四个 M 的退出标准和 rollback | ✓ 每个 milestone 都有 `[reviewer]` 与 `[worker]` 两轨，风险表允许单 M revert（`design.md:383-401,486-498`）。 |
| 迁移 2：单 owner、无 shim/flag/双写 | 核 D1/D3 guardrail | ✓ control 不复制 manager/store/FIFO，main 不 re-export，legacy callbacks直接删除，architecture grep守旧符号归零（`design.md:139-168,184-200,227-243,447-457`）。 |
| 迁移 3：成熟模块整体迁移 | 核模块表和 M2/M3 | ✓ 明示不重写算法，M2/M3以整类/整生命周期移动为范围（`design.md:223-225,496-497`）。 |
| 迁移 4：测试随 owner 迁移且不放宽 size guard | 核 M 范围和最终 gate | ✓ 各 M 同步迁对应测试，M4对38个 test baseline及剩余 helper全量对账，最终运行 test-size contract（`design.md:404-434,493-498`）。 |
| 迁移 5：代码回滚、不改写用户数据 | 核风险表与数据边界 | ✓ manifest/cache/key/session/message/PID/config schema均不迁移，回退为 milestone commit revert（`design.md:383-401`）；legacy cutoff明确禁止新版主动删明文字段。 |
| 迁移 6：legacy 截止不续命 | 核删除清单与发布前置 | ✓ migration、cleanup、export、provider/applied callbacks及专属测试全部纳入 M1删除，发布说明要求需 managed control 的旧部署先迁移（`design.md:176-205,495`）。 |
| Delta-spec：纯内部重构无 delta | 对照全部 canonical 与唯一退休行为 | ✓ managed/lifecycle/heartbeat/cron current behavior均保持；legacy standalone YAML/export 被 canonical 明确排除（`external-channels.md:230-236`）；没有 schema/API/wire/UI delta，`design.md:369-381` 的 no-delta 判定成立。 |
| M1：managed-channel control ownership | 核拆分依据、范围、双轨退出 | ✓ 是一个完整 ownership 切片；legacy callback删除与新 binding 形态同属该 seam，先后分开会制造短命接口。online/offline/replay与实现 guard都可验（`design.md:486-495`）。 |
| M2：runtime-side deep modules | 核是否横切、可回退性与退出标准 | ✓ 是三个现成深模块的整体物理迁移，不拆算法/测试；串行避开 shared main seam，reviewer/worker 两轨完整（`design.md:488-496`）。 |
| M3：entry-side lifecycle modules | 核是否横切、owner与退出标准 | ✓ process lifecycle、HTTP bootstrap和register-ready coordinator按各自真实owner迁移，组合后独立保住 start/stop/restart/auto-bind/reconnect（`design.md:488-497`）。 |
| M4：composition/test surface closure | 核最终独立价值、范围和退出标准 | ✓ 只在前三个 owner到位后收口 composition/main并完成全量测试表面对账；不是“最后补测试”，而是最终可观测架构门禁（`design.md:488-498`）。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | `ManagedChannelControl` + `ChannelManager` + store + IM manager | ✓ 走完无存活发现。control拥有跨 credential/provider/activation/status 的集成策略；manager仍唯一持有 runtime map；store仍唯一持久化 outbox；IM manager仍唯一持有 wire/FIFO。组合后无反向 Kernel 依赖或重复 state owner（`design.md:123-168`；`channel_manager.py:198-239`；`im_connection.py:296-320`）。 |
| 归属 | `im_bootstrap` 与 `ConnectionReadyCoordinator` | ✓ 走完无存活发现。HTTP/node binding留在 `im_bootstrap`，跨 owner register-ready 顺序单独落 `connection_ready`；二者变化轴和依赖方向已分开（`design.md:207-225,335-355`）。 |
| 归属 | runtime/process/kernel/heartbeat 物理迁移 | ✓ 走完无存活发现。目标模块与当前成形职责一一对应，main仅保留命令入口；没有把 lifecycle policy放入 composition或无领域 helper（`design.md:207-243`）。 |
| 该不该存在 | `ManagedChannelControl` | ✓ 删除测试不成立：删掉会把 `main.py:2244-2689` 的 credential/provider/status/activation/reconnect策略重新摊回 composition；三个公开入口隐藏的复杂度显著大于接口。 |
| 该不该存在 | typed upstream mailbox | ✓ 删除测试不成立：真实 provider worker thread 需要跨线程投递（`main.py:2345-2386`，现用 `send_json_threadsafe`）；mailbox切断 nullable connection 捕获且不承诺 durable语义。同步 close已排除在 mailbox 外。 |
| 该不该存在 | `ConnectionReadyCoordinator` | ✓ 删除测试不成立：当前 `main.py:2637-2700` 有稳定的跨三个 owner 顺序与错误隔离；删除会让同一编排回流 composition。它不是为未来多态制造的 factory/Protocol。 |
| 该不该存在 | provider plugin / generic event bus / compatibility layer | ✓ 走完无存活发现。design主动拒绝三者并要求旧 alias/callback归零（`design.md:144-174,184-200`），没有假想接缝或迁移尾巴。 |
| 深还是浅 | control三入口 + typed bindings | ✓ 三入口隐藏 manifest解析、key、provider preflight、activation、status/outbox/replay、manager lifecycle；不是对现有方法一一转发。bindings 是 transport所需的一组窄 use case，不暴露 control内部状态（`design.md:123-168,245-300`）。 |
| 深还是浅 | bootstrap 直回空 items | ✓ 没有以 no-op provider 包一层旧行为；transport直接完成当前协议初始化，result manifest复用 `apply_manifest`，删除了一层而未另造抽象（`design.md:176-205,295-300`）。 |
| 深还是浅 | owner module set | ✓ 每个新增文件都有独立状态/生命周期或稳定跨 owner顺序；design明确禁止 `composition_helpers.py` 和一函数一文件（`design.md:207-231`），未发现浅 wrapper。 |
| 治本还是补丁 | nullable closure、private API、test service locator | ✓ 直接移除 connection反向捕获、增加 concrete public operation、让测试改从真实 owner import，并用 contract阻止回流（`design.md:123-168,227-243`）；不是在 main 上叠 adapter。 |
| 治本还是补丁 | legacy migration 截止 | ✓ 删除 provider/applied type、迁移函数、export脚本与专属测试，同时保留仍有现行初始化作用的 wire handshake；没有把旧路径改名续命（`design.md:176-205,447-457,495`）。 |
| 治本还是补丁 | process/runtime模块移动 | ✓ 成熟模块整体迁移且原 shutdown/startup顺序有 contract与测试守护；不会为了降行数拆成共享状态或薄 helper（`design.md:207-243,357-367`）。 |

## Issues

无。核实台账无存活缺陷，四个架构进攻角度也未发现会让 worker 走偏、orchestrator 派错或形成长期架构债的问题。

## Recommendations

无。该设计可放心进入 `change-orchestrator`。
