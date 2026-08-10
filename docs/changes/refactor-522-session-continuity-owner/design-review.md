# Design Review: refactor-522-session-continuity-owner

## Round 1

### Metadata

- reviewer: `/root/relay_typed_ingress`
- review_mode: `full`
- mode_reason: `R1 恒为 full；本轮从零核对全部五类承重原子、生产调用链与四个架构进攻角度。`
- started_at: `2026-08-10T09:45:21+08:00`
- completed_at: `2026-08-10T09:53:24+08:00`
- duration: `8m03s`

### Verdict

Approved — 0 CRITICAL / 2 WARNING

方向成立：删除语义不完整的内存 store、把 SQLite 作为 binder 内部 local-substitutable implementation，并原样保留六张表与原子事务，确实能把测试从浅 persistence seam 拉回真实 continuity 行为。两条 Warning 不否定 owner cutover，但应在 author closure 中拍清 boundary-outbox 的最终 seam，并补成可直接执行的恢复验收路径，避免 M1 落成“换了依赖名但没变深”和只验证 Web 主路径。

### Coverage

- Frozen inputs（本轮核实期间 hash 未变化）：`motivation.md` `224a414f...e1`、`design.md` `215260a1...a1b`、Gateway delta `8262ff41...54f`。
- Canonical：`docs/specs/gateway/spec.md`、`routing-delivery.md`、`relay-protocol.md`、`agent-capabilities.md`、`heartbeat-cron.md`。
- 生产入口正向路径：`process_lifecycle._default_build_runtime()` → `composition.compose_gateway()` → `InboundPipeline` / `SessionRunCoordinator` → `GatewaySessionBinder` → `PersistentSessionBindingStore`；另核 `BoundaryOutboxDispatcher`、shadow pending-boundary promotion、external control recovery、heartbeat/cron canonical lookup、fork/distill/internal dispatch。
- 历史：archived `refactor-463`、`feat-501`、`refactor-480`、`bugfix-471`、`bugfix-508`，retired `refactor-481`，active `refactor-478`，以及本次 architecture review 的 session-continuity candidate。
- 现行回归证据：运行 coordinator admission、boundary delivery、external control delivery、persistent store 四组 focused suite，结果 `41 passed`。

### 承重原子核实台账

#### 1. 现状断言与既有约束

| 原子 | 核实动作与证据 | 结论 |
|---|---|---|
| S1 binder 已拥有 binding/identity/control/supersession/canonical lookup 主路径 | 从 `src/personal_assistant/gateway/inbound_pipeline.py:104-185` 正向追到 `session_run_coordinator.py:279-681,1169-1300`，再核 `session_binder.py:249-412,464-704`；scheduler、fork/distill、internal dispatch 的生产 caller 均已调用 binder。 | 成立；“session key resolution”应理解为 key→binding resolution，key 字符串本身仍由 pipeline 在 `inbound_pipeline.py:125` 构造。 |
| S2 private repository 为 16 个 operation family，且公开 memory/SQLite/global store 并存 | `session_binder.py:35-122` 精确枚举 16 个 protocol method；`session_keys.py:102-496,610-1579` 定义两套 class 与全局 instance。 | 成立。 |
| S3 composition 同时持有 binder 与 raw SQLite，outbox/promotion 绕行 | 生产入口 `process_lifecycle.py:824-828` 调 `compose_gateway`；真实 wiring 在 `composition.py:244-258`，outbox 直接拿 store；`composition.py:407-421` 的 shadow promotion 也直接调 store。全 `src/personal_assistant` 搜索无第三个 raw-store 生产 caller。 | 成立，且改动落在唯一生产实现。 |
| S4 memory store 不能表达 crash-safe pending boundary | `session_keys.py:345-375` 只更新 runtime，promotion 固定返回 `None`；SQLite 在 `session_keys.py:1173-1300` 同事务写 pending row 并可原子 promotion。 | 成立；两者已非同语义 adapter。 |
| S5 测试直接认识 store 的规模 | 当前 `tests/**/*.py` 有 40 个文件引用两类 store；精确构造调用为 memory 105、SQLite 35，memory symbol reference 为 150。 | 规模判断成立；design 的“约 140 处构造内存实现”实际更接近 symbol reference，不影响范围判断但建议后续改准。 |
| S6 SQLite 遗留 HTTP Kernel client 描述与字段 | `session_keys.py:610-634,679-693` 仍保留 `_kernel_client`/setter 与旧 HTTP 描述，但真实 `get()` 在 `695-714` 明示 live validation 归 binder；composition `244-257` 也未注入 client。 | 成立，删除安全。 |
| C1 restart 必须复用固定 runtime DB 与同一上下文 | canonical `docs/specs/gateway/spec.md:9-13` 要求进程重启恢复映射；production path 固定为 `composition.py:225,249-257` 的 `runtime_dir/session_bindings.sqlite3`。 | 约束被决策 2/3 与 compatibility matrix 覆盖。 |
| C2 六表/schema/WAL/transaction/serialization 不变 | 六表定义在 `session_keys.py:502-595`；WAL/migration 在 `636-678`；原子 boundary/pending/control/reset transaction 在 `838-1002,1103-1300`；reply JSON 在 `1590-1611`。 | 约束与决策 3、M1 worker 退出标准一致。 |
| C3 `/new`、`/compact`、operation idempotency 与 external pending 继承 feat-501 | 历史 `feat-501/design.md:83-152` 明确 reset visibility fence、FIFO compact、operation ledger、pending external handoff；现行代码在 `session_run_coordinator.py:279-668`，focused admission tests `test_session_run_coordinator_admission.py:147-245,301-352`。 | 成立；设计没有重新分配 control semantics。 |
| C4 coordinator 继续拥有 admission/FIFO/generation/visibility | 当前 coordinator 在 `session_run_coordinator.py:206-277,279-681,778-866,1608-1649` 持有 transition/FIFO/generation；设计决策 5 明确不吸收。 | 成立且与 refactor-463/feat-501 一致。 |
| C5 remote `BoundaryConnection` 仍是真实 port | `boundary_outbox.py:36-41` 是 ACK-gated remote protocol；真实连接由 `connection_ready.py:72-80` 注入，测试 fake 可替代。 | 成立；SQLite 不应替代 remote seam。 |
| C6 不重开 refactor-481、不改 refactor-478 correlation owner | retired `refactor-481/README.md:3-5` 明确只从具体 config incident 重开；active `refactor-478/design.md:102-169` 的 owner 是 IM waiter/PA control codec/transport。522 只与 composition 有机械交集。 | 无冲突。 |
| R1 value objects/key/reply builders 可复用 | `session_keys.py:19-100,1614-1682` 是生产 caller 继续需要的领域值与纯 builder；它们不要求保留 public store class。 | 成立。 |
| R2 binder 现有 domain API 可作为 caller 唯一入口 | ordinary/control/runtime/canonical/fork caller 已经只用 `session_binder.py:249-704,908-987`；唯一缺口正是 S3 两个 bypass。 | 成立，但 boundary outbox 的新增 surface 见 R1-W1。 |
| R3 SQLite `:memory:` / tempfile 是 local substitution | implementation 仅依赖一个 DB path/connection（`session_keys.py:636-678`）；同进程普通行为可用 `Path(":memory:")`，重建与 migration 必须用 temp file。 | 成立；无需保留第二个 persistence port。 |
| R4 outbox ACK/retry state machine 可原样复用 | `boundary_outbox.py:87-170` 已集中 schedule、ACK validation、quarantine、retry；`connection_ready.py:72-80` 保持其连接生命周期。 | 成立；不应把 remote delivery policy并入 binder。 |
| H1 refactor-463 的旧“双真实 adapter”判断是否被合法推翻 | `refactor-463/design.md:131-145` 当时要求两 adapter；其后 feat-501/bugfix-471 增加 pending boundary、control、supersession，且当前 memory promotion 固定 no-op。 | 新证据足以改变旧判断；不是静默违约。 |
| H2 refactor-480 delivery owner 是否被越界 | `refactor-480/design.md:93-167` 固定 `RunDeliveryContextStore`/observer/terminal cleanup owner；522 决策 5 保留 coordinator、remote ACK 和 delivery lifecycle，只移动 local persistence access。 | 无冲突。 |
| H3 bugfix-471 runtime+boundary 原子提交是否保住 | `bugfix-471/design.md:249-289,369-394` 要求 applied runtime 与 anchored/pending boundary 同事务；现实现为 `session_keys.py:1103-1300`。 | 决策 3/调用规则明确原样保留。 |
| H4 bugfix-508 Web 群裸 `/new` 是否仍 per-Agent 隔离 | `bugfix-508/design.md:21-32` 依赖每 Agent relay 与独立 session key；522 不改 relay、key、group gate 或 coordinator。 | 无冲突。 |
| H5 architecture review candidate 是否真实命中当前路径 | report `architecture-review-20260810-082847-9d7a0bec.html:224-265` 指向的 protocol、双实现与 test surface 均在当前代码存在；生产绕行也由 S3 证实。 | 候选事实基础成立。 |

#### 2. 关键决策

| 决策 | 四问核实 | 结论 |
|---|---|---|
| D1 binder 独占 continuity persistence | owner、拒绝项和 migration 都拍死；与 motivation 的“caller 表达 intent”一致；production 两个 bypass 可枚举。 | 方向成立；boundary delivery 的具体新增 seam 仍有浅封装风险，见 R1-W1。 |
| D2 SQLite private/local-substitutable | 构造形态、普通与 restart 测试介质、拒绝通用 port/mock 均无歧义；符合 `codebase-design` local substitution。 | 成立。 |
| D3 schema/data compatibility | 明确 path/schema/table/serialization/migration 一律不动，且 M1 有重开证据。 | 成立。 |
| D4 删除 dead HTTP/public helpers | 仓内 caller 同 M1 迁移、无兼容 shim；删除对象均有当前证据。 | 成立；不越出 repo 内部 API。 |
| D5 coordinator 与 remote delivery owner 不变 | 与 D1 的组合依赖方向为 caller/outbox → binder → private SQLite，未反向依赖 IM、coordinator 或 runtime_delivery。 | owner 结论正确；outbox state operation 粒度需 closure。 |
| D6 修正 `/compact` canonical drift | canonical 当前仍写 busy reject（`routing-delivery.md:120-148`），现行 coordinator/tests 是 FIFO barrier；delta 用 MODIFIED 精确锚同名 requirement。 | 成立，是文档 drift 修复而非行为变更。 |

#### 3. motivation 约束、场景与非目标

| 约束 | design 落点与证据 | 结论 |
|---|---|---|
| 用户授权细节自主、最终只做 PR review | 原话完整保留在 motivation `11-19`；单 M1、无中间产品选择。 | 覆盖。 |
| 同一聊天复用上下文 | D2/D3 + matrix 的 binding resolve/restart；canonical `routing-delivery.md:14-26,235-252` 为行为基线。 | 覆盖。 |
| 不同聊天/Agent 不串会话 | key/identity/serialization 不变；M1 `[reviewer]` 显式含普通隔离。 | 覆盖。 |
| Gateway restart 复用旧会话 | temp-file binder rebuild 与 existing DB compatibility 被 D2/D3、风险段和 M1 覆盖。 | 覆盖；实操命令见 R1-W2。 |
| partial reset/control recovery 只有唯一结果 | control/supersession/pending external 六表 matrix、原事务和 restart critical path 均列出。 | 设计覆盖；Web-only runbook 无法独立驱动全部分支，见 R1-W2。 |
| `/new`、`/compact` 可见历史/结果/后续上下文/幂等不变 | D3/D5 继承 feat-501 原事务和 coordinator，delta 只修 compact drift。 | 覆盖。 |
| busy `/compact` 保持 FIFO，`/new` 可 supersede | D5 + D6；现代码/test 证据 `session_run_coordinator.py:454-630`、`test_session_run_coordinator_admission.py:147-245`。 | 覆盖。 |
| 非目标：不改 SQLite/wire/transcript/frontend/channel 文案 | D3、delta 列表和 M1 范围均未引入这些变化。 | 不冲突、不越界。 |
| 迁移：一次切换、无第二 DB/双写、删浅 seam | 单 M1 与决策 2/4 一致；回滚为整体 revert 且不改数据。 | 覆盖。 |

#### 4. Delta-spec

| 条目 | 核实 | 结论 |
|---|---|---|
| Gateway MODIFIED `用户可安全地手动压缩当前 Agent 会话` | 标题精确锚 canonical `routing-delivery.md:120`；保留空闲、no-op、失败、重放原 Scenario，拆开旧 busy+failure 并用 FIFO、新-session supersede 替换已漂移的 busy reject；THEN 均为用户可观察顺序/上下文/确认，无函数或类名。 | 用法正确，可在收尾归并；kernel/im/cli 确为 no spec delta。 |

#### 5. Milestone

| Milestone | 核实 | 结论 |
|---|---|---|
| `refactor-522-M1 continuity-owner-cutover` | 单 M1 有反向举证：拆 production/test cutover 会保留 public 双 seam；范围虽大但同一 ownership 原子。退出标准同时有 `[reviewer]` motivation 场景和 `[worker]` deletion/schema/test/ruff 证据，不是横切层。 | 拆分与两轨退出成立；恢复旅程的可执行性见 R1-W2。 |

### 整体判断

- 上层可读：总览图、Before/After 与六条一句话决策能直观看出“caller→binder→private SQLite”，未被 grounding 细节淹没。
- 接口/数据流：ordinary/control/scheduler/fork/distill 已闭合；当前两个 bypass 也都被列入迁移。唯一未充分深化的是 outbox 看到的五个持久化动作仍与现 protocol 同构。
- 自洽：无 TBD/模板残留；图、决策、matrix、delta 和单 M1 一致；风险/回退不要求 schema migration。
- 常驻服务：有隔离 stack 命令和 health check，但它们与文中“只重启 Gateway”和 external partial recovery 的验收承诺不完全闭合。

### 架构进攻

| 角度 | 主动攻击与证据 | 发现 |
|---|---|---|
| 1. 归属 | 核依赖方向：route/coordinator/scheduler/fork/distill → binder → SQLite；remote `BoundaryConnection` 与 ACK/retry 保持在 outbox；run visibility 保持 refactor-480 owner。 | 主 owner 放置正确，无跨包/反向依赖；但 outbox durable transition 被 binder/dispatcher 分切，见 R1-W1。 |
| 2. 该不该存在 | 删除 memory store 后，ordinary/restart 行为仍可由 SQLite `:memory:`/temp file 覆盖，复杂度不会回流 caller，故该 adapter 应删。反向删除拟新增的 binder outbox pass-through，现有 dispatcher 的 ACK/retry 状态机并不会消失。 | memory adapter deletion test 通过；outbox pass-through deletion test 未通过，见 R1-W1。 |
| 3. 深还是浅 | binder 的 resolve/reset/runtime/control API 隐藏跨 await guard、provenance、Kernel+SQLite ordering，属于深接口；而 design `123-151` 列出的 ready/ACK/error/defer/next-delay 与当前 `BoundaryOutboxStore` `boundary_outbox.py:15-33` 基本一一同构。 | 主 binder 足够深；新增 outbox surface 可能只是把 store protocol 搬到 binder。 |
| 4. 治本还是补丁 | 一次删除 public dual store、直接使用真实 SQLite，并保留原事务/数据，治的是测试与 production 语义分裂；无 feature flag、双写、deprecated alias。 | 总体治本；没有兼容补丁。验收路径若只走 Web relay，会让 external recovery 的治本证据不足，见 R1-W2。 |

### Issues

- [R1-W1][WARNING] [决策 1 / 决策 5 / 接口与数据流]: 方案把 boundary outbox 的 `delivery_ready / acknowledge / record_error / defer_retry / next_retry_delay` 原样列为 binder 新增操作，却同时声称 binder 只暴露 continuity intent、dispatcher 继续拥有 ACK/retry。当前 `BoundaryOutboxStore` 已恰好是这五个方法（`src/personal_assistant/gateway/boundary_outbox.py:15-33`），状态机在 dispatcher `114-170`；按现文实施，最直接结果是给 binder 加五个一行转发并继续把 backoff policy 参数穿到 SQLite，只把旧 store seam 换了接收者。**不改的长期代价**：binder public surface 会随 delivery retry/quarantine 细节增长，continuity 与 delivery ownership继续分切，下一次改 boundary 状态机仍需同时改 dispatcher、binder、private SQLite，候选承诺的“收窄 16 族 seam”只对测试名义成立。Author 需要拍死一个更深的 boundary transition interface，或明确一个由 continuity module 私有装配、但不把五个存储动作抬到 binder 的内部 collaborator；至少要给出新 seam 的 deletion test，而不是只写“领域命名”。
- [R1-W2][WARNING] [Runbook for Reviewer / M1]: Runbook 声明 restart critical path 必须“只停止/启动 worktree Gateway”，但唯一停止/启动命令是 `e2e-down.sh`/`e2e-up.sh`；前者实际同时停止 IM 并删除 ports/config runtime 文件（`scripts/e2e-down.sh:1-16,23-100`），文档没有可照搬的 Gateway-only restart 命令。更重要的是，Web relay 旅程不能产生 external pending-boundary promotion（production bypass 在 `composition.py:407-421`）或 pending external-control materialization（`external_control_delivery.py:33-75`），而这两条 crash recovery 正是本 unit 要收入 owner 的状态。**不改的坏事**：worker/reviewer 可以用 Web 普通聊天证明 SQLite row 重开，却完全漏测 external anchor/control partial state，仍满足当前模糊的 `[reviewer] partial recovery` 文字。请补 Gateway-only stop/start/health 命令，并为 external partial recovery 指定一个真实外部通道或 deterministic 真栈驱动与明确 crash point/唯一结果观察。

### Recommendations

- [R1-R1] 把现状计数改成“约 150 个 memory-store symbol references / 105 个 constructor calls，35 个 SQLite constructor calls”，避免 worker 把机械迁移量估错；不影响本轮 verdict。
- [R1-R2] 在 outbox seam closure 后，把 stale 的 `heartbeat_scheduler.py:203-210,313-318`、`cron_runner.py:231-236` 和 `external_control_delivery.py:17-19` 中 HTTP/store 术语纳入必要 caller 文档清理；这些不是新架构决策，不应为它们保留兼容 API。

### Author Resolutions

- [R1-W1] accepted — 决策 1/5 与接口段将五个 store-shaped 动作替换成 `next_boundary_dispatch()` + `complete_boundary_dispatch(...)` 两步 domain transition；binder 内部拥有 durable schedule/backoff/quarantine，dispatcher 只拥有 remote send/ACK 分类，并增加旧 protocol/pass-through deletion test。
- [R1-W2] accepted — runbook 增加完整变量初始化、专用 Feishu profile、可复制的 Gateway-only restart helper/判据，并拍死两条 deterministic true-stack external partial-recovery crash journey；不允许普通 Web restart 顶替。
- [R1-R1] accepted — 现状计数改为约 150 个 symbol references、105 个 memory constructor calls 与 35 个 SQLite constructor calls。
- [R1-R2] accepted — caller 文档清理纳入 M1 必要 caller 范围，且不为旧 HTTP/store 术语保留兼容 API。

## Round 2

### Metadata

- reviewer: `/root/relay_typed_ingress`
- review_mode: `delta`
- mode_reason: `本轮语义修订可枚举为 boundary outbox 两步 transition seam、retry ownership、review runbook/partial-recovery 证据路径与两处非阻塞文字修正；motivation、delta-spec、需求范围、核心 owner 与单 M1 结构均未变化。重查发现的可执行性缺口仍封闭在 R1-W2 的测试 seam 内，未扩大到需 full 的生产边界。`
- started_at: `2026-08-10T10:03:35+08:00`
- completed_at: `2026-08-10T10:07:43+08:00`
- duration: `4m08s`

### Verdict

Approved — 0 CRITICAL / 1 WARNING

两步 boundary seam 已真实关闭 R1-W1，不再把五个 store mutation 换名搬到 binder。Gateway-only restart 命令也已闭合；但 external partial-recovery 的 replacement seam 与同一 subprocess restart helper 目前无法同时按文档落地，R1-W2 因此只部分关闭。

### Coverage

- 当前输入：`motivation.md` `224a414f...e1`（未变）、`design.md` `b227e3b2...613`、Gateway delta `8262ff41...54f`（未变）。
- 重查 changed atoms：决策 1/5、boundary interface/deletion test、Runbook、M1 退出标准及其真实生产 wiring；现状计数与 caller 清理只核 author resolution 落点。
- `retained_from: Round 1` — motivation 的 Requirements/场景/非目标、D2/D3/D4/D6、Gateway delta-spec、compatibility matrix 与单 M1 拆分均无语义修订，R1 的完整台账仍有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-W1 | 五动作改成 `next_boundary_dispatch()` + `complete_boundary_dispatch(...)`，binder 持有 durable schedule/backoff/quarantine，并补 deletion test | 当前旧 seam 确为 `BoundaryOutboxStore` 五动作（`src/personal_assistant/gateway/boundary_outbox.py:15-33,114-170`）；修订后 design `75-81,107-113,127-173` 只向 dispatcher 暴露 plan/outcome，retry 参数不再穿透，且明确禁止旧五动作同义 pass-through。删掉两步 operation 会迫使 dispatcher 重新学习 ready/deadline/quarantine，删除测试成立。 | closed |
| R1-W2 | 补变量、专用 Feishu profile、Gateway-only helper 和两条 deterministic true-stack external crash journey | 正常 restart 半边已闭合：helper 实际只终止/重启 Gateway 并复用 config/runtime（`tests/e2e/critical_paths/_im_gateway.py:57-116`），环境变量由 `scripts/e2e-up.sh:349-359` 导出。partial-recovery 半边仍要求同一 helper 与进程内 fake 同时成立，但 helper 固定启动 `personal_assistant.main`，现有 composition 又直接创建 channel registry/outbox，未给 replacement seam；详见 R2-W1。 | partially closed → R2-W1 |
| R1-R1 | 校正 store 引用/构造计数 | design `18-20` 已区分约 150 个 symbol references、105 个 memory constructor calls 与 35 个 SQLite constructor calls。 | closed |
| R1-R2 | 必要 caller 文档同 M1 清理，不保留旧术语兼容 API | 决策 4 的无 shim 原则与 M1 的“必要 binder caller”范围保持一致；未新增兼容 surface。 | closed |

### 本轮 changed atoms 与架构进攻

| Changed atom / 角度 | 重查证据与波及链 | 结论 |
|---|---|---|
| D1/D5 + interface：binder/outbox ownership | 生产现状为 dispatcher 自己持有 retry policy并调用五个 persistence mutation（`boundary_outbox.py:68-83,114-170`）。新 plan/outcome seam 把 durable ready、backoff deadline、ACK 删除和 quarantine 收进 binder；dispatcher 只保留连接生命周期、remote send、matching ACK 与错误分类。上游 `connection_ready.py:72-80` 的 connection epoch/schedule owner 不变，下游 SQLite schema/事务不变。 | 归属自洽，无反向依赖；核心行为边界已拍死。 |
| 删除测试 / 深浅 | 删除旧 protocol 后，调用方只需理解 `Ready/Wait/Idle` 与三类 delivery outcome，不再理解 attempts、deadline、quarantine mutation 或 retry 参数；反向删除两步 seam 会把这些 durable facts重新泄漏给 dispatcher。 | R1-W1 关闭；这不是 repository façade 或浅 pass-through。 |
| 治本性 | policy 随 binder construction 固定，delivery loop 不再同时决定 durable retry schedule；旧五动作 protocol/pass-through 被列为 M1 必删项。 | 没有兼容层、双 authority 或临时补丁。 |
| Runbook / dependency classification | Gateway-only helper 与真实 IM generation 判据可执行；但 design `228,234-239` 同时要求 helper 重启真实 main、production composition、真实 IM 和 replacement adapter。helper `92-105` 固定启动 main；composition `234-258,720-760` 直接构造 registry/outbox，连接仅在 `connection_ready.py:72-80` 由真实 manager 注入。 | 普通 restart 可执行；partial-recovery replacement topology 尚未拍死，见 R2-W1。 |

### Issues

- [R2-W1][WARNING] [Runbook for Reviewer / M1]: 两条 partial-recovery journey 要求“复用 production composition、真实 IM、同一 Gateway restart helper，只替换 remote `BoundaryConnection`/external adapter”，但这几项在现有可执行路径上没有闭合。该 helper 固定以新进程运行 `python -m personal_assistant.main`（`tests/e2e/critical_paths/_im_gateway.py:92-105`）；production `compose_gateway()` 又直接创建 channel registry 与 `BoundaryOutboxDispatcher`（`src/personal_assistant/gateway/composition.py:234-258,720-760`），没有让新进程接收 fake adapter/connection 的入口。文档也没有拍死是用可跨重启存活的进程外 proxy/fake、专用 test launcher，还是新增 composition injection seam；三者会形成不同测试拓扑和 production API 影响。**不改的坏事**：worker 要么自行新增 motivation/M1 未声明的 production test hook，要么退化成只重建 binder/dispatcher 的进程内测试，却仍把它称为“同一 helper + production composition + 真实 IM”，最终无法证明 external pending state 真的跨 Gateway 进程恢复。请在 design 层选择并声明唯一 replacement/restart seam（含新 Gateway 如何重新取得同一个 barrier/fake），并确认它不需要 production failpoint；具体测试代码仍留给 worker。

### Recommendations

- 无额外建议；先关闭 R2-W1 后即可进入实施。

### Author Resolutions

- [R2-W1] accepted — partial recovery 固定为 `tests/e2e/critical_paths/` 内的双 subprocess test launcher；A/B 进程直接装配 production binder/outbox/shadow/control owners，并通过 shared temp runtime 中的真实 SQLite、barrier state 与 fake external chat ledger 重连同一恢复状态。它不复用 `personal_assistant.main` restart helper、不调用或复制 `compose_gateway()`，也不新增 production injection seam/failpoint/proxy。真实 Gateway-only conversation restart 继续由现有 main helper 独立覆盖。

## Round 3

### Metadata

- reviewer: `/root/relay_typed_ingress`
- review_mode: `delta`
- mode_reason: `R2-W1 的修订不是单纯措辞 closure，而是把 partial-recovery 的 restart/replacement topology 改成双 subprocess test launcher；其影响可封闭在 tests/e2e launcher、既有 owner constructors 与证据口径，未改需求、production owner、共享契约、delta-spec 或 milestone。重查未发现影响继续扩大，故无需升级 full。`
- started_at: `2026-08-10T10:11:46+08:00`
- completed_at: `2026-08-10T10:13:53+08:00`
- duration: `2m07s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R2-W1 已由唯一、可实现的双 subprocess topology 关闭。修订明确把真实 `personal_assistant.main` 普通重启和 targeted partial-state 跨进程恢复分成两条互补证据；test launcher 不要求新增 production seam，也没有把 fake external port 冒充真实 provider 旅程。

### Coverage

- 当前输入：`motivation.md` `224a414f...e1`（未变）、`design.md` `32b28409...c2d`、Gateway delta `8262ff41...54f`（未变）。
- 重查 changed atoms：Runbook `235-256` 的 A/B subprocess lifecycle、shared durable/barrier state、production owner constructor seams、composition 复制风险与产品证据归类。
- `retained_from: Round 1 / Round 2` — boundary 两步 transition、ownership、schema compatibility、motivation/delta-spec、单 M1 及此前已关闭项均未变化，既有核实仍有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 固定 tests-only 双 subprocess launcher；A/B 共享 temp SQLite、barrier 与 external ledger；不复用 main helper、不改/复制 `compose_gateway()`；真实 main restart 单独覆盖 | design `235-249` 已唯一拍死 parent/IM/shared-runtime/subprocess A/B topology，且由 durable-commit marker 决定 kill 点；B 从相同文件恢复 barrier/ledger，不依赖已死亡的进程内 fake。`249,256` 明确禁止 production factory/env hook/failpoint/proxy，并将普通真实 main restart 与 partial-state component journey 分开陈述。 | closed |

### 本轮 changed atoms 与架构进攻

| Changed atom / 角度 | 重查证据与波及链 | 结论 |
|---|---|---|
| Restart/replacement seam | A/B 是真实 OS subprocess，共享 `session_bindings.sqlite3`、shadow saga DB、barrier state 与 visible ledger；parent 只在 durable marker 后杀 A，再由 B 重开同一状态。 | 真正验证跨进程 durability，不是同进程重建对象；R2 的 injection 歧义消失。 |
| Production seam / 归属 | 方案只使用现有 constructors/ports：`BoundaryConnection` protocol（`boundary_outbox.py:36-41`）、`IMShadowConversationSync` 的 transport/saga/promote seam（`shadow_sync.py:54-78`）、materializer 的 binder/router/shadow owners（`external_control_delivery.py:14-31`）以及 binder 的 local storage construction。design 明禁改 `compose_gateway()` 或加 test mode。 | 不引入 production-only test hook、反向依赖或新公开 factory；test-only barrier 归 remote fake 所有。 |
| Composition duplication / 删除测试 | launcher 只装配本 unit 受影响的 binder/outbox/shadow/control owner graph，不承接 config parsing、channel registry、runtime lifecycle、heartbeat/cron 等 `compose_gateway()` 职责；删掉 launcher 不会把新 abstraction 留在 production。 | 属于有界 component integration fixture，不是第二套 Gateway composition；没有长期双 owner。 |
| 产品证据口径 / 治本性 | design `256` 明确：真实 main helper只证明普通 Gateway conversation restart；双 subprocess只证明 partial durable state 经 production owners恢复到 fake external chat 与真实 IM shadow 的唯一可见结果。fake external provider 被如实标注，真实 Feishu ingress仍由独立 probe覆盖。 | 证据是可组合而非冒充：没有把 component launcher声称为完整 production Gateway/Feishu journey，也不以 SQLite row 代替可见结果。 |

### Issues

- 无。

### Recommendations

- 无。
