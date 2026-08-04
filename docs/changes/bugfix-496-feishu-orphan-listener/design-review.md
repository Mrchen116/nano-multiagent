# Design Review: bugfix-496-feishu-orphan-listener

## Round 1

### Metadata

- reviewer: `/root/bugfix_496_design_reviewer`
- review_mode: `full`
- mode_reason: 首轮审查且不存在历史 Round；按 Gate 2 规则完整核对五类承重原子与四个架构进攻角度。
- started_at: `2026-08-04T11:47:01+08:00`
- completed_at: `2026-08-04T11:59:27+08:00`
- duration: `12m26s`

### Verdict

Approved — 0 CRITICAL / 2 WARNING

按 reviewer 判据，方案没有会令实现建立在错误生产路径上、破坏既有架构边界或迫使 worker 猜核心架构的 CRITICAL；父进程 sentinel 方案可以进入实现。按仓库 Gate 2 的更严格闭环条件，仍需把下列 2 个 WARNING 修订并复审至 `0 WARNING` 后才算通过门禁。

### Coverage

- 受审产物：`incident.md`、`design.md`、`specs/gateway/external-channels.md`、`M1-parent-liveness/.gitkeep`。
- canonical：`docs/specs/gateway/spec.md`、`service-lifecycle.md`、`external-channels.md`，以及 IM 侧 `docs/specs/im/agents-nodes.md` 的节点离线与 channel last-known 契约；delta 写法按 `docs/specs/CONTRIBUTING.md` 核对。
- 生产路径：从 `process_lifecycle.run_gateway_foreground()` / `compose_gateway()` 正向追到 `GatewayRuntime → ManagedChannelControl → ChannelManager → FeishuAdapter → FeishuClient → FeishuWorkerRuntime → WSClient.start()`，并反查正常 shutdown、background/foreground 信号语义、cache 恢复和状态投影。
- 测试与复现：逐读 `tests/unit/personal_assistant/test_feishu_worker_runtime.py`；本轮独立运行现行 owner `os._exit(23)` 探针，确认 worker 仍存活且 `PPID=1`，定向回收后运行该文件得到 `6 passed`。
- 外部事实：只读核对 Issue #230；核对当前 `.venv` Python 3.12.9 的 `multiprocessing` 实现与 [Python 3.12 multiprocessing 官方契约](https://docs.python.org/3.12/library/multiprocessing.html)；只读确认 `ssh mini` 可达、三项验收文件 mode `0600`、cache/node/key 匹配、一个启用的 Feishu channel 且 envelope 可解密，未输出凭据内容。
- 本轮未实施代码、未修改受审产物、未启动或停止生产 Gateway。

### 现状断言核实台账

| ID | 承重原子 | 本轮结论与独立证据 |
|---|---|---|
| A1 | `FeishuWorkerRuntime` 是实际 listener 进程 owner，负责 spawn 与 stop/join/terminate/kill。 | 成立。唯一类定义及非 daemon spawn 在 `src/personal_assistant/channels/feishu/worker.py:219-266`，真实 `start/stop` 在 `:294-365`；全仓检索没有第二个同名实现。 |
| A2 | 产品 managed-channel 生产 wiring 真正到达该 runtime，不是测试死实现。 | 成立。`compose_gateway()` 创建并注入 `ManagedChannelControl`：`src/personal_assistant/gateway/composition.py:501-518,606-619`；control 唯一 provider factory 创建 `FeishuAdapter`：`src/personal_assistant/gateway/managed_channel_control.py:143-156,364-407`；adapter 创建 `FeishuClient`：`src/personal_assistant/channels/feishu/adapter.py:107-124`；client 创建并启动 `FeishuWorkerRuntime`：`src/personal_assistant/channels/feishu/client.py:182-215`。 |
| A3 | child 最终阻塞在飞书 SDK `WSClient.start()`，不能依赖 target 正常返回感知 owner 死亡。 | 成立。生产 target 在 `src/personal_assistant/channels/feishu/client.py:653-700` 构造 SDK client、发布连接状态后调用阻塞 `client.start()`；当前 bootstrap 只设置 ready 后同步调用 target：`src/personal_assistant/channels/feishu/worker.py:199-216`。 |
| A4 | parent 存活时正常 close 已经通过 managed owner 回收 worker。 | 成立。Gateway shutdown 先 close managed channels：`src/personal_assistant/gateway/runtime.py:306-343`；control 下沉到 manager：`src/personal_assistant/gateway/managed_channel_control.py:160-168`；manager 遍历 active runtime：`src/personal_assistant/gateway/channel_manager.py:545-553,877-890`；adapter/client/runtime 的 stop 链见 `src/personal_assistant/channels/feishu/adapter.py:182-195`、`client.py:217-225`、`worker.py:316-365`。 |
| A5 | background 与 foreground 最终运行同一 Gateway/worker 路径，但信号清理能力不同。 | 成立。foreground 从同一 builder 创建 runtime：`src/personal_assistant/gateway/process_lifecycle.py:135-165,823-827`；background 只是用 `--foreground` 再启动同一入口并建立独立 session：`:705-730`；信号时只有 `pgid == gateway pid` 才 `killpg`，否则只杀 Gateway PID：`:634-650`。因此 worker 内 owner-liveness seam 同时覆盖两种启动形态。 |
| A6 | `ChannelManager` 只知道本进程 active 集合，cache 恢复会创建当前 worker，不会发现上一 Gateway 的孤儿。 | 成立。`_active/_desired` 均为进程内 dict：`src/personal_assistant/gateway/channel_manager.py:214-226`；cache 恢复逐项 `_replace_runtime()`：`:246-307`，没有系统进程扫描或跨进程 owner registry。 |
| A7 | 现有测试证明正常 stop、双 Bot 隔离、背压、drain/drop、card RPC 与 worker crash，但未覆盖 owner 先死亡。 | 成立。现有六组测试完整位于 `tests/unit/personal_assistant/test_feishu_worker_runtime.py:90-284`，所有 cleanup 均由仍存活的测试进程调用 `runtime.stop()`；本轮该文件 `6 passed`。独立最小探针让真实 owner `os._exit(23)` 后观察到 worker 仍存活且 `PPID=1`，随后只定向回收该 PID。 |
| A8 | 标准库已经给 spawn child 暴露精确 parent sentinel，无需新增业务 heartbeat pipe。 | 成立于当前运行环境。当前 Python 的 `parent_process()` 和 `_ParentProcess.join/is_alive()` 分别在 `/Users/czj/miniforge3/lib/python3.12/multiprocessing/process.py:51-55,364-389`，POSIX spawn 把 parent sentinel 传入 bootstrap：`/Users/czj/miniforge3/lib/python3.12/multiprocessing/spawn.py:98-127`；官方文档也明确 `Process.sentinel` 可由 `multiprocessing.connection.wait()` 等待。runtime 已显式固定 `spawn`：`src/personal_assistant/channels/feishu/worker.py:238-266`。 |
| A9 | sentinel 改动可以封闭在 worker 深模块内部，不要求 Gateway/ChannelManager/public API 传 liveness handle。 | 成立。调用者只依赖 `FeishuWorkerRuntime.start/stop/pid/is_alive`：`src/personal_assistant/channels/feishu/worker.py:284-319`；生产调用链没有消费 child liveness handle。把 watcher 放在 `_worker_bootstrap()` 可直接覆盖默认 target 和测试 target。 |
| A10 | canonical 已覆盖节点 offline/last-known、正常 stop/cache/multi-Bot；缺口是 Gateway 死亡后 Feishu listener 不残留。 | 成立。正常服务 stop 在 `docs/specs/gateway/service-lifecycle.md:14-50`；cache、停删、重放与多 Bot 隔离在 `docs/specs/gateway/external-channels.md:230-277`；IM 节点超时与 channel last-known 在 `docs/specs/im/agents-nodes.md:242-255,288-339`。三处均没有 owner 死亡后 child 自动退出条目，新增 target 选 `gateway/external-channels.md` 语义最窄。 |
| A11 | feat-464 引入点与后续 recovery 补丁的历史描述准确。 | 成立。`3577ad1127` 引入 `worker.py`、非 daemon spawn 与 `ChannelManager`；`b945519861` 修改 worker join/terminate/kill 和 manager recovery。当前代码证据仍分别见 `worker.py:261-266,321-365`。 |
| A12 | 验收外部资源已经落实，不需要用 fake 冒充真飞书旅程。 | 基础前置成立：本轮只读确认 mini 可达，config/key/cache 均 mode `0600`，manifest node identity 与 config 一致、key id 一致、一个 Feishu channel envelope 成功解密。平台会话、Bot 与权限仍按 runbook 在实际验收时做 live check；设计没有把 fake 测试当真栈替代。 |

### 决策核实台账

| 决策 | 拍板 / 歧义 / 自洽 / 驱动 | 结论与证据 |
|---|---|---|
| D1：child watcher 等待 multiprocessing parent sentinel | 明确选 sentinel、明确安装位置在 `_worker_bootstrap()`、明确无 sentinel 时 fail closed；与禁止 PID 扫描/heartbeat pipe 一致。 | 成立。真实缺口位于 `worker.py:199-216`，runtime 固定 spawn 于 `:238-266`；标准库 parent sentinel 事实见 A8。watcher 先于 ready/target 是必要边界，且不会扩散 public interface。 |
| D2：owner 消失时进程级立即退出，正常关闭仍走现有 stop | 明确区分异常 owner-death 与 graceful stop 两条路径，明确异常路径不发最终状态、不等待 SDK/Python cleanup。 | 成立。parent 存活时当前 stop 链可用（A4）；owner 已死后 IPC 消费者也已消失，进程级退出直接释放 socket/IPC，未与 incarnation/status 因果契约冲突。唯一验收精度缺口见 R1-W2。 |
| D3：真实 owner→worker 回归，不加产品测试开关 | 测试接口、异常动作、外部断言、定向 cleanup、idle 反例均已拍板。 | 成立。现有 spawn harness 与 `pid/is_alive` seam 在 `tests/unit/personal_assistant/test_feishu_worker_runtime.py:23-87`、`worker.py:284-303`；本轮使用同一类两级进程探针重现现状，证明该测试形状能击中根因。 |
| D4：只扩 Gateway external-channel 契约 | 明确 gateway 有 delta，其余包 no spec delta；没有改变 IM/前端字段或现有状态语言。 | 成立。可观察增量属于运维者/Feishu 用户面对的 Gateway listener 生命周期；IM 的 offline/last-known 已由 `docs/specs/im/agents-nodes.md:242-255,288-339` 覆盖。delta target 与 `docs/specs/CONTRIBUTING.md:114-157` 一致。 |

四项决策之间没有互相冲突：D1/D2 定义产品内部 seam，D3 证明 parent-death 与 idle 两个相反边界，D4 只把最终可观察保证写入 Gateway 契约。

### incident / 需求约束核实台账

| ID | incident 承重原子 | design 覆盖与结论 |
|---|---|---|
| S1 | Q1：修复前移到 Gateway 退出，不以下次启动扫描为主要机制。 | D1/D2 直接绑定 owner 生命周期，接口流第 6 步明确重启不扫描；覆盖且不冲突。 |
| S2 | Q2：崩溃、`SIGKILL`、`os._exit` 等无法执行 cleanup 的退出也覆盖。 | D1 等待 OS parent sentinel，D2 使用 child-side 进程级退出，D3 指定 owner 无 cleanup 回归；覆盖。 |
| S3 | Q3：复用现有通道页状态，不新增 idle watchdog。 | D1 watcher 永久阻塞 sentinel、不观察入站；D4 no IM/frontend delta；覆盖。 |
| S4 | 用户场景：正常停止、重启、异常死亡都不遗留 listener。 | D2 + runbook 步骤 4/5 + M1-E1/E2；设计语义覆盖，runbook 可复现性见 R1-W1/R1-W2。 |
| S5 | 用户场景：节点离线显示现有 offline/last-known，重启后连接与消息稳定恢复。 | D4 锚定 current IM 契约，runbook 步骤 5/6 与 M1-E3/E4；设计方向覆盖，但用户页面旅程未闭合，见 R1-W1。 |
| S6 | 用户场景：安静 channel 不误报，用户无需再手杀 `PPID=1`。 | watcher 只等 sentinel，D3/M1-E4/E6 明确 parent 存活空闲不退出；异常自收敛后无需启动扫描或人工恢复。 |
| S7 | Requirement/Scenario：正常 stop/restart 后旧 listener 消失且新 Gateway 接管。 | D2 保留现有 stop，delta scenario 1、M1-E1、runbook 步骤 4 对应；覆盖。 |
| S8 | Requirement/Scenario：Gateway 异常死亡后旧 listener 不再占连接/收消息。 | D1/D2、delta scenario 2、M1-E2/E5、runbook 步骤 5 对应；覆盖，验收上界见 R1-W2。 |
| S9 | Requirement/Scenario：异常退出重启后连续消息全部一次回复并同步 shadow。 | delta scenario 3、runbook 步骤 6、M1-E3 对应；覆盖，执行证据链见 R1-W1。 |
| S10 | Requirement/Scenario：Gateway offline 时页面不把旧 connected 冒充当前状态。 | D4 复用 `docs/specs/im/agents-nodes.md:318-334`，M1-E4 声明 reviewer 退出；没有新实现越界，但 runbook 没有实际页面观察步骤，见 R1-W1。 |
| S11 | Requirement/Scenario：空闲不触发降级、退出或重连。 | D1/D3、delta scenario 4、runbook 步骤 7、M1-E4/E6 对应；覆盖。 |
| S12 | 不变量：一 Bot 一 listener，多个 Bot 隔离。 | worker 仍一 runtime 一 Process：`worker.py:261-266`；manager 每 channel 单 active：`channel_manager.py:222-226`；设计不改接口，M1-E6 保留双 Bot 回归。 |
| S13 | 不变量：replace 先停旧 runtime，再启新 runtime。 | 仍由现有 manager owner 执行，`src/personal_assistant/gateway/channel_manager.py:877-890` 为停用原语；design 明确 manager grounding-only、M1-E6 保留替换/stop 回归。 |
| S14 | 不变量：正常 listener 可 stop/join，cleanup 不残留 worker。 | D2 明确保留当前 `worker.py:316-365`，M1-E1/E6 覆盖。 |
| S15 | 不变量：status 按 incarnation/sequence 保持因果顺序。 | 未改 context/status frame：`worker.py:23-50,62-138`；owner-death 不向已死亡 owner 发送伪 terminal status，避免旧 sequence 污染。 |
| S16 | 不变量：cache 离线启动、热调和与主消息路径保持。 | 变更只在 child bootstrap；`channel_manager.py:246-307` cache path、composition/control wiring不变；M1-E3/E6 复核。 |
| S17 | 在范围：后台/前台正常与异常退出均联动。 | 两种启动都进入同一 foreground runtime（A5），liveness 绑定真正 Gateway child；覆盖。 |
| S18 | 在范围：保持现有节点/channel 状态语言。 | D4 no IM/frontend delta，canonical evidence 见 A10；覆盖。 |
| S19 | 在范围：父无法 cleanup 的回归，同时保住 close/replace/disable/delete。 | D3 + M1-E5 针对 parent-death；M1-E6 明列既有回归；覆盖。 |
| S20 | 非目标：启动扫描/识别/清理历史孤儿。 | D1/D2 治退出根因，接口流第 6 步与回退段明确禁止扫描；未越界。 |
| S21 | 非目标：idle watchdog 或由无入站推断故障。 | watcher 只等 sentinel；delta scenario 4 与 M1-E4/E6反向把守；未越界。 |
| S22 | 非目标：改变飞书消息、shadow、审批、诊断语义。 | product diff 范围只含 worker 与 worker tests；D4 no IM/frontend delta；未越界。 |
| S23 | 非目标：牺牲 cache 自治或多 Bot 隔离。 | D1 为每个现有 worker 内部 seam，不集中 listener、不依赖 IM；未越界。 |
| S24 | 非目标：为没有 listener child 的其他 channel 预造通用机制。 | 修改归属固定在 Feishu worker，无新跨 provider abstraction；未越界。 |

### delta-spec 核实台账

| ID | delta 原子 | 结论与证据 |
|---|---|---|
| Δ1 | `ADDED Requirement: 托管飞书 listener 不得脱离 Gateway 存活` | 用法正确。canonical 没有同名或同义 owner-death guarantee；现有正常 stop 与 managed reconcile 不被替换，因此是平行新增，不应写 MODIFIED。target `gateway/external-channels.md` 比 service-lifecycle 更贴近 Feishu 专属行为。 |
| Δ2 | 正常停止/重启回收旧 listener | THEN 是运维者可观察的进程/连接结果，没有函数调用或日志串；忠实投影 S7。 |
| Δ3 | 无 cleanup 异常终止时 listener 有界退出 | THEN 是运维者可观察的进程/连接结果，忠实投影 S8；“有界”缺少可验上界，见 R1-W2。 |
| Δ4 | 异常退出后重启恢复稳定消息路径 | 用户可观察 reply 与 IM shadow 结果完整，保留“不随机缺失或重复”，忠实投影 S9。 |
| Δ5 | 正常空闲不改变 listener 状态 | 用户可观察连接状态，防止误做 idle watchdog，忠实投影 S11。 |

offline/last-known 没有重复写入 Gateway delta 是正确的：该行为未变化且已经由 IM canonical `docs/specs/im/agents-nodes.md:318-334` 完整拥有。canonical 合并时需按现行规则把 Gateway entry 的 External Channels Requirement 派生计数从 12 更新为 13，但这不是额外行为 delta。

### Milestone 核实台账

| Milestone | 形状 / 范围 / 两轨退出 | 结论 |
|---|---|---|
| `bugfix-496-M1 parent-liveness` | 单一 worker seam + 同一 interface 测试 + gateway delta；范围只写 `worker.py`、worker test、delta，其他组件 grounding-only；E1-E4 为 reviewer，E5-E7 为 worker。 | 单 M1 有充分反拆分理由，属于端到端垂直切片，没有并行交集或横切拆分。worker/reviewer 两轨齐全，E5/E6 能证明异常 owner-death 与 idle 反例。E1-E4 的真实旅程与 runbook 证据链尚需按 R1-W1 补齐；E2/E5 的时间判据尚需按 R1-W2 定量。目录仅含 `.gitkeep` 符合设计阶段规则。 |

### 整体判断

- 上层可读性成立：架构总览把唯一变化收敛为“child 内 watcher 等 parent sentinel”，两张图与 D1/D2 一致；决策结论先行，没有被 grounding 细节淹没。
- 接口与数据流闭合：sentinel 来源是 spawn bootstrap，消费方是 worker watcher，出口是进程级退出/OS 释放 socket；正常 stop 继续由 manager owner 调现有 interface。没有新增无人调用的接口或调用方期待却缺失的字段。
- 文档结构齐：标题、对齐、branch、空 Changelog、delta、Runbook、Milestones 均存在；没有模板注释、TBD 或待定架构板。
- 风险与回退写实：竞态、异常 cleanup、平台/start method、真 Bot 接管窗口和 fallback pipe 都有对应处理；回退没有偷偷恢复启动扫描/idle watchdog。
- 常驻服务 runbook 列出了 Gateway/IM 启停与基础健康命令，外部 key/cache 前置已落实；但完整 reviewer 旅程仍有 R1-W1 的可执行性缺口。

### 架构进攻

| 角度 | 主动攻击与结论 | 证据 / 长远代价判断 |
|---|---|---|
| 归属 | watcher 最自然归属 worker bootstrap，而不是 Gateway runtime、ChannelManager、IM 或通用 channel 层。 | parent sentinel 只在 spawn child 内天然可得（A8），阻塞 SDK 也在同一 child（A3）。上移会迫使外层了解 child handle 并扩大依赖；当前方案遵守 PA 内部分层且不触及 `agent`。未发现错放归属。 |
| 该不该存在 | 删除 watcher 后，现行 owner `os._exit` 探针稳定留下 `PPID=1` worker；因此该职责不可删。单独 liveness pipe 可以表达同义事实，但会新增两端句柄与 context 字段。 | 本轮独立复现证明删除测试失败；标准库已提供同语义 sentinel。一个 daemon watcher 是闭合阻塞 SDK 与 owner-death 并发的最小新增，不是为未来多态预造抽象。 |
| 深还是浅 | 外部 `FeishuWorkerRuntime` interface 保持不变，新增复杂度全部藏在现有深模块；没有 wrapper/factory/protocol。 | 调用者继续只见 `start/stop/pid/is_alive`（A9），实现内部吸收 spawn/OS wait/立即退出细节，接口显著小于隐藏实现。未发现浅封装或重造已有模块。 |
| 治本还是补丁 | 方案让“owner 存活”直接成为 listener 存活条件，修的是生命周期根因；没有以启动扫描、App ID hardcode、idle reconnect 或共享设施特例掩盖双连接症状。 | 现状复现的决定性事实是 owner 消失后 child 继续存活（A7）；sentinel 正面表达该事实。启动扫描会留下误杀/归属债，idle watchdog 会误判正常安静 channel；方案已显式拒绝。未发现补丁式绕路。 |

### Issues

- [R1-W1][WARNING] [Runbook for Reviewer / M1-E1～E4] 真栈验收链没有精确闭合。当前健康检查只证明 IM OpenAPI 可访问和 `.gateway.pid` 对应进程存活（`design.md:142-148`），步骤 4～7 只用散文要求“restart / connected / 记录唯一 listener / 查看 shadow / 离线状态”，没有给出当前 Gateway PID 的权威来源、channel connected 与 listener 数量的具体观察命令、IM shadow 去重证据入口；同时 `design.md:148` 明确“不启动前端”，但 M1-E4 又要求 reviewer 覆盖“用户打开通道页看到 offline/last-known”（`design.md:190-193,202-208`）。不改会让产品 reviewer 被迫自行猜 PID/API/页面路径，或只用日志/进程内部事实冒充用户页面与 shadow 旅程，orchestrator 无法可复查地判定 E1～E4 是否退出。请把正常 restart、异常 kill、当前 PID/worker 身份、channel status、shadow 消息和 offline channel-page 观察串成可直接执行的命令/UI 步骤；若页面必须验收，就不能同时声明不启动客户端面。
- [R1-W2][WARNING] [决策 2 / delta Δ3 / M1-E2、M1-E5] “立即退出 / 有界时间内”没有任何可验的上界。delta、runbook 与 milestone 都未规定从确认 owner 已死亡到 worker 身份消失最多允许多久；现有测试 helper 的 3 秒默认值（`tests/unit/personal_assistant/test_feishu_worker_runtime.py:23-29`）也没有被 design 采纳为契约。不同 worker/reviewer 可以分别接受亚秒、5 秒或几十秒，慢 watcher 仍可能在窗口内抢飞书事件，却被写成通过。请在 design、delta 与两轨退出标准中统一一个有依据的上界，并让测试与真栈等待只在该上界内断言 worker 自行退出，超时后的定向 cleanup 不能计作成功。

### Recommendations

- [R1-R1] 修订 R1-W1 时优先复用现有 `.gateway-state.json` 的 PID + process-birth 证据和 IM channel API/真实页面，而不是引入新的 debug endpoint 或进程发现产品接口。
- [R1-R2] worker 实现宜使用标准库公开的 `multiprocessing.connection.wait([parent.sentinel])`（或 `_ParentProcess.join()`）等待，并用明确的全进程退出原语兑现 D2；不要让 watcher thread 自身返回被误当成 listener 进程退出。

### Author Resolutions

- [R1-W1] **accepted** — 当前 background launcher 已把 `pid + process_start + config_path` 原子写入隔离 config 同目录的 `.gateway-state.json`；IM 已有 `GET /im/v1/agents/{agent_id}/channels`、`GET /im/v1/conversations` 与 `GET /im/v1/conversations/{id}/messages`，真实页面入口为 `/settings/agents/{agent_id}`。修订 `design.md §Runbook for Reviewer`：隔离 Gateway 改用 background lifecycle state 作为权威身份，增加可复制的认证、channel status、listener PID、shadow 去重步骤，并构建、真驱动现有通道页观察 offline/last-known；同步收紧 M1-E1～E4。
- [R1-W2] **accepted** — parent sentinel 无轮询，事件就绪后只需一次线程调度和进程退出；采用现有 worker 测试 `_wait_until` 的 3 秒默认预算作为 owner-death 上界。统一修订决策 2、数据流、delta、Runbook 与 M1-E2/E5：从确认原 Gateway process birth 消失起 3 秒内，原 worker process birth 必须消失；超时后的定向 cleanup 只用于清场，不计成功。
- [R1-R1] **accepted** — 按建议复用 `.gateway-state.json` 与 current IM HTTP/UI interface，不增加 debug endpoint、process registry 或产品测试开关。
- [R1-R2] **accepted** — 该建议与决策 1/2 一致；实现范围保持“公开 sentinel wait + 全进程退出”，不把 watcher thread 返回当成 listener 退出。

## Round 2

### Metadata

- reviewer: `/root/bugfix_496_design_reviewer`
- review_mode: `delta`
- mode_reason: 本轮把 owner-death 验收收紧为统一 3 秒上界，并补全 reviewer 的身份、API、页面与 shadow 证据链，属于可枚举的设计语义与验收流变化；incident 范围、sentinel 核心架构、包边界、public interface 和单 M1 形状均未改变，因此无需升级 full。
- started_at: `2026-08-04T12:09:04+08:00`
- completed_at: `2026-08-04T12:13:40+08:00`
- duration: `4m36s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R1 的两个 WARNING 都已在 design、delta 与两轨退出标准中闭合；修订后的方案可以进入 `change-orchestrator`。

### Coverage

- 本轮重查 changed atoms：决策 2/3、接口与数据流第 5 步、Gateway delta 的异常退出 Scenario、Runbook 全链与 M1-E1～E5。
- 上游重查：R1-W1/W2 对应的 incident 用户场景、正常/异常退出边界和 offline/last-known 体验；下游重查：current Gateway lifecycle state、managed-channel bootstrap、channel API、真实 Agent channel 页、conversation/message API 与 worker test harness。
- `retained_from: Round 1 —` 现状断言 A1～A12、决策 1/4、incident S1～S24 中未被上述 changed atoms触及的覆盖、delta Δ1/Δ2/Δ4/Δ5、M1 单里程碑形状，以及归属/该不该存在两个架构进攻角度仍有效；本轮没有改变生产 wiring、模块职责、需求范围或 shared contract。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-W1 | accepted：复用 `.gateway-state.json`、current IM HTTP/UI interface，并补齐真实页面与 shadow 旅程。 | `design.md:142-329` 已给出 IM/Gateway 启停、PID + process birth、唯一 direct spawn child、channel stale/connected、真实 `/settings/agents/{agent_id}` 页面和三 nonce history 断言。生产事实闭合：lifecycle state 原子写入并按 birth 校验于 `process_lifecycle.py:145-168,626-661`；fresh IM 会通过 cache bootstrap 重封并建立 authoritative channel 于 `channel_manifest_store.py:125-175`、`IM/ws/gateway/channel_control.py:82-104,168-197`；channel API 在 `IM/api/routes/agent_channels.py:47-59,117-131`；页面以 node offline 覆盖旧 connected 并显示 last-known 于 `agent-detail-page.tsx:1499-1503,1646-1653`、`agent-channels-panel.tsx:175-219`；shadow conversation/message 字段与 timeline 包装于 `IM/api/routes/web_im.py:155-169,291-302`、`IM/api/routes/messages.py:123-135,430-473`。reviewer 不再需要猜入口或用内部日志冒充用户旅程。 | closed |
| R1-W2 | accepted：统一采用确认 owner birth 消失后的 3 秒上界，cleanup 不计成功。 | 决策 2/3 与数据流已统一在 `design.md:70-82,92-101`；真栈断言在 `:253-291` 只接受原 worker PID 不存在或 birth 改变并以 3.0 秒超时失败；M1-E2/E5 在 `:344` 使用相同起点、身份与 cleanup 排除。delta 的异常退出 THEN 在 `specs/gateway/external-channels.md:15-19` 同步为消费者可观察的 3 秒结果。该预算也与现有 `_wait_until(timeout=3.0)` harness 一致：`tests/unit/personal_assistant/test_feishu_worker_runtime.py:23-29`。 | closed |
| R1-R1 | accepted：不新增 debug/process-discovery 产品接口。 | Runbook 只组合现有 lifecycle state、channel/conversation/message API 与已构建页面；`design.md:78-90,149,207-329` 继续明确不增加产品测试开关、debug endpoint、持久 registry 或前端变化。 | closed |
| R1-R2 | accepted：公开 sentinel wait + 全进程退出。 | 决策 1/2 仍明确 watcher 等待 multiprocessing parent sentinel，触发后使用不等待 Python/SDK cleanup 的进程级退出：`design.md:62-76`；M1-E5 把外部 process birth 消失作为退出，不把 watcher thread 返回当成功：`:344`。具体实现仍由 worker 在 M1 落地并受 E5/E6 验收。 | closed |

### Changed atoms 与波及链

| Changed atom | 本轮核实 | 结论 |
|---|---|---|
| C1：决策 2 把“立即/有界”定量为 3 秒 | 起点是确认原 Gateway process birth 消失，终点是原 worker process birth 消失；预算明确包含 sentinel 唤醒、线程调度、进程退出和外部观测，正常 stop 路径不变：`design.md:70-76`。 | 决策已拍死、与 D1/D4 自洽；worker 无需猜时间语义。 |
| C2：决策 3 改为两级真实 owner → worker 回归 | fake 只替换外部 Feishu target 且保持阻塞；owner 以无法 cleanup 的方式退出，外部按 birth + 3 秒断言，定向清场不计成功，并保留 idle 反例：`design.md:78-84`。现有真实 spawn seam 与 3 秒 helper 在 `test_feishu_worker_runtime.py:23-36,76-87`。 | 击中 owner 先死的根因，不靠产品测试开关或进程组清理造绿。 |
| C3：接口与数据流同步 3 秒保证 | 异常路径仍完全封装在 `FeishuWorkerRuntime` 内，只把可观察退出上界补到第 5 步：`design.md:92-101`。 | 不新增 public API/config/schema/wire/UI，调用方和依赖方向未改变。 |
| C4：delta 异常退出 THEN 定量 | `specs/gateway/external-channels.md:15-19` 写的是 Gateway/worker 原进程身份在 3 秒内消失以及旧 listener 不再占连接/收消息，没有内部函数、类或日志断言。 | 忠实投影 incident 的异常 owner-death 场景，仍是 Gateway external-channel 的最窄 ADDED 契约。 |
| C5：Runbook 建立 identity → status → page → message 证据链 | `design.md:142-329` 先隔离 IM/Gateway 与真实 Bot，再用 `.gateway-state.json` PID + birth 锁定 Gateway、唯一 direct spawn child 锁定 listener；正常 stop、`SIGKILL`、stale API、真实 channel 页、重启和三 nonce history 依次取证。background launcher会清除不匹配的 stale state：`process_lifecycle.py:218-245`；IM channel projection 以 node online/offline 产生 `status_stale`：`channel_control_store.py:1330-1385`。本轮额外跑过 cache re-seal 与 stale projection 的 focused tests，`4 passed`。 | R1 缺失的真实消费者入口与可复查命令已闭合；没有新增诊断产品面。 |
| C6：M1-E1～E5 收紧两轨退出 | `design.md:344` 把 reviewer 的正常 stop、异常 kill、三 nonce、真实页面/idle，以及 worker 的两级 spawn 回归分别写成可观察的 process birth/API/UI/history 或实现层测试证据；E2/E5 同用 3 秒和 cleanup 排除。 | reviewer/worker 两轨仍齐全，单 M1 范围和文件归属未漂移。 |

### 受影响的架构进攻

| 角度 | 本轮攻击与结论 | 长远代价判断 |
|---|---|---|
| 深还是浅 | 修订没有为了可观测性给产品增加 debug endpoint、process registry 或 test flag；reviewer 只在外部组合已有 lifecycle state、HTTP API 和真实页面。worker public interface 仍是 `start/stop/pid/is_alive`，3 秒语义由外部 birth 观察。 | 若把取证能力塞入产品会扩大常驻维护面；当前方案避免该税，并保持 owner-liveness 复杂度封装在 worker 深模块。 |
| 治本还是补丁 | 3 秒从 owner identity 消失直接量到同一 worker identity 消失；重启验收先证明旧 listener 消失，再证明新 listener 唯一与三条消息无丢重。stale lifecycle state 只由现有 birth 校验清理，不扫描或猜测历史 Python 进程。 | 证据链直接验证“listener 不能脱离 owner”根因；没有留下启动扫描、idle watchdog 或共享设施特例的归属债。 |

### Issues

- 无。

### Recommendations

- 无。
