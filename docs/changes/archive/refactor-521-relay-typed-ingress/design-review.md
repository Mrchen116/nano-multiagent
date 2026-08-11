# Design Review: refactor-521-relay-typed-ingress

## Round 1

### Metadata

- reviewer: `/root/session_continuity`
- review_mode: `full`
- mode_reason: R1 恒为 full；本轮从首文档、canonical specs、真实生产 wiring 与相关历史重新建立完整台账，并执行全部四个架构进攻角度。
- started_at: `2026-08-10T09:44:44+08:00`
- completed_at: `2026-08-10T09:52:50+08:00`
- duration: `8m06s`

### Verdict

Changes requested — 1 CRITICAL / 3 WARNING

### Coverage

- 首文档与方案：完整读取 `motivation.md`、`design.md`；本 unit 无 delta-spec 文件，方案显式声明四包 `no spec delta`。
- canonical 契约：核对 `docs/specs/gateway/{routing-delivery,relay-protocol,external-channels}.md`、`docs/specs/im/{gateway-relay,conversations-messages}.md` 与 `AGENTS.md` 包边界。
- 生产调用链：从 `IMConnectionManager._listen_once()` 的 `relay.message` 分支进入 `WebRelayAdapter.accept_relay()`，再经 `ChannelAdapter.start(on_inbound)` / `InboundDispatcher` / `InboundPipeline` / `SessionRunCoordinator` / `runtime_delivery`；另从 `FeishuAdapter` 正向追到同一 callback，并复核 external shadow saga/recovery 与 reply/session 持久化投影。
- 历史：核对 archived `refactor-454` 的 typed handoff 原决策、`refactor-463` 的单值 façade、`refactor-480` 的 run-delivery owner、`bugfix-471` 的 provider-stable identity 与 durable shadow、`bugfix-508` 的 Web group `/new` 边界；复核 active `refactor-478`、`refactor-482` 的范围交集。
- R1 逐项覆盖下列五类承重原子，并独立执行归属、存在性、深浅、治本性四角度进攻；没有把 design 自身引用当成现状证明。

### 核实台账：现状断言

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| S1 `InboundMessage` 是 channel callback 与 pipeline 的单值 interface | `channels/base.py:23-46,85,101-109` 定义 value 与 `InboundHandler`；`gateway/bootstrap.py:67-86` 把同一 callback 交给 registry 中每个 adapter；`inbound_dispatcher.py:37-72,138-157` 只接收并转发一个 message。 | 成立。生产 seam 确实是单值 callback。 |
| S2 `InboundEnvelope` 没有跨越生产 seam | `web_relay_adapter.py:213-230` 构造 envelope，却调用 `callback(inbound_envelope.message)`；`ws/im_connection.py:933-935` 忽略 `accept_relay()` 返回值；wrapper 的直接断言集中在 `test_gateway_web_relay_adapter.py:126-164`。 | 成立。它是返回值/测试表面，不是生产 handoff。 |
| S3 typed facts 当前藏在私有 metadata，并有 legacy derive | `gateway/runtime_protocol.py:13,57-90` 显示私有 key、attach/read 与 fallback；`93-150` 从普通 metadata 重建 external/shadow facts。 | 成立。typed 与 metadata-derived 两条 authority 并存。 |
| S4 生产确实走拟改组件 | `composition.py:554-561,696-703` 装配真实 pipeline/dispatcher/runtime；Web relay 从 `im_connection.py:933-935` 进入，Feishu 从 `channels/feishu/adapter.py:374-411,413-470` 进入同一 callback。 | 成立，不是测试专用死实现。 |
| S5 pipeline/coordinator/shadow/delivery 各有既有 owner | `inbound_pipeline.py:63-76,104-190` 只做 route/gate/shadow/dispatch；`session_run_coordinator.py:113-129` 拥有 admission/terminal；`shadow_sync.py:54-86` 与 `shadow_saga.py:207-227` 拥有 shadow；`runtime_delivery/context.py:230-334` 拥有每-run context。 | 成立，与 refactor-463/480 当前落地一致。 |
| S6 当前业务性 `web_relay` 判断确有分散 | 生产精确命中为 `inbound_pipeline.py:197,310`、`runtime_delivery/context.py:412,420`、`runtime_delivery/background.py:235,252`、`runtime_delivery/observer.py:232`；registry/config 另有 `channel_manager.py:409-412` 的合法 adapter identity。 | 事实成立；但哪些必须迁、哪些合法保留未在设计里逐项拍死，见 R1-W2。 |
| S7 `personal_assistant` 包依赖边界 | `AGENTS.md:5-12` 禁止产品包绕过 `agent.sdk`，也禁止 IM 与 PA 互相 import；本设计没有引入跨包 Python 类型。 | 成立。 |
| S8 单值 `handle_inbound(message)` 是既有稳定 façade | archived `refactor-463.../design.md:109-117,278-291` 明确保留该 façade；当前 `inbound_pipeline.py:104-190` 与 dispatcher wiring 一致。 | 成立。D1 延续历史裁决。 |
| S9 run delivery 不能回流到 ingress owner | archived `refactor-480.../design.md:32-46,93-167` 把 context、ordering、task settlement 与 cleanup 留在 runtime delivery；当前 composition 仍注入唯一 store。 | 成立。方案表述上没有搬走 delivery policy。 |
| S10 四类 identity 必须分离 | canonical `external-channels.md:93-123` 区分触发源与回复去向；`im/conversations-messages.md:180-194` 区分 IM conversation 与 external identity；当前 `session_keys.py:1614-1643` 只以 typed external identity 建 external session key。 | 成立。D3 的方向受现有契约驱动。 |
| S11 provider-stable event identity 是 typed normalization fact | canonical `relay-protocol.md:186-220` 要求 adapter 提供 typed identity且禁止 chat/text fallback；Feishu 当前在 `adapter.py:397-408,456-467` 构造 `ExternalInboundEventIdentity`，saga 在 `shadow_saga.py:224-246` 直接消费。 | 成立；但当前 top-level identity 与 `RuntimeProtocolFacts.external_event_identity` 并存，目标接口未拍死唯一 authority，见 R1-C1。 |
| S12 native Web group 与 external-shadow-through-IM 的 `/new` 必须区分 | canonical `routing-delivery.md:53-88` 只允许 native Web IM 的精确裸 `/new` 全群触发；当前 `inbound_pipeline.py:287-323` 同时检查 `web_relay`、external marker 与 mention/reply。 | 成立，D3 的正交事实是必要的。 |
| S13 external shadow recovery 是真实 producer | `shadow_sync.py:446-495` 从 durable canonical payload 重建 `InboundMessage` 与 runtime facts，再重放 sync；它不是 channel adapter callback，却会构造同一事实集合。 | 成立；design 已列入 producer inventory。 |
| S14 facts 当前被显式排除在持久化/public metadata 外 | `session_keys.py:1590-1611,1646-1661` 和 `shadow_saga.py:268-289` 通过 strip/projection 落库；`shadow_sync.py:105-118` 同样先 strip。 | 成立。删除 helper 后必须继续用结构投影，而不是序列化整个 facts value。 |
| S15 active unit 交集 | `refactor-478.../design.md:15-35,304-320` 处理 control RPC、明确不是 `relay.message`；`refactor-482.../design.md:11-36,697-704` 只改 frontend owners。 | 关系判断成立；没有生产文件语义交集。 |

### 核实台账：关键决策

| 决策 | 完整性 / 自洽 / 依据核实 | 结论 |
|---|---|---|
| D1 保留单值 `InboundMessage` | 真实 callback 只有一个 value；删除仅测试可见 wrapper 不增加第二 seam，并延续 refactor-463。 | 成立。 |
| D2 facts 与 normalized message 同层 | 避免 `channels.base -> gateway` 反向 import 的方向正确；但方案没有给出准确的目标 type/field/requiredness，并把 post-ingress shadow state 一并归到 channel interface 层。 | 被 R1-C1 阻断；另见 R1-W1。 |
| D3 分开 transport origin 与 external identity | canonical group gate、shadow reply routing、external continuity 都要求二者正交；拒绝单个 `is_web_relay` bool 是合理方向。 | 概念成立；具体 representation 与合法组合未拍死，归入 R1-C1。 |
| D4 同一 M1 删除 wrapper/key/fallback | 内部单仓无旧 consumer，原子 replace 比双读兼容更安全；当前 wrapper/attach/derive 的删除测试成立。 | 方向成立；必须先补齐 R1-C1 的唯一 authority/migration matrix，否则 worker 不知道 top-level identity 与 scalar projection应删还是留。 |
| D5 合法 adapter identity 保留 | 不扩成 ChannelManager/capability graph 符合 YAGNI；但当前七处判断没有被逐项分类。 | 部分成立，见 R1-W2。 |

### 核实台账：首文档约束

| spec 原子 | 覆盖与冲突检查 | 结论 |
|---|---|---|
| 澄清：Agent 自主收敛，最终只交 PR review | design 无待定用户问题，采用行为不变单 M1 与最终真栈验收。 | 覆盖。 |
| Requirement 1 / direct Web IM | D1-D4 保留 relay dedup、callback、session/run/delivery owners；canonical `routing-delivery.md:31-51` 要求原 Agent/会话路由。 | 覆盖。 |
| Requirement 1 / group trigger + silence + bare `/new` | D3 与风险表锁定 native/external 区分，M1 reviewer exit 引 motivation；canonical `routing-delivery.md:53-88`、IM provisional discard `gateway-relay.md:130-138` 是可验结果。 | 覆盖。 |
| Requirement 2 / external reply + shadow ordering | D2-D4、数据流和 run-delivery 风险保留 Feishu normalization、shadow sync/saga 与 runtime owner；canonical `external-channels.md:93-123,127-193`、`relay-protocol.md:186-220` 给出可观察顺序与 offline 行为。 | 覆盖。 |
| Requirement 2 / disconnect/replay | 保留 Web relay SQLite dedup（`web_relay_adapter.py:37-124,213-243`）和 external durable saga；M1 reviewer exit 明确断线/重放。 | 覆盖。 |
| 影响范围：只改 Gateway ingress/delivery consumer | M1 范围限于 PA channel/gateway/tests，未改 IM wire、frontend、agent.sdk。 | 不越界。 |
| 非目标：不改 IM WS / provider / SDK / frontend | active 478/482 与当前范围无语义交叉，design 明示 no wire/schema change。 | 不冲突。 |
| 迁移：一次切换、无长期双读 | D4 与单 M1一致。 | 覆盖。 |
| 回滚：整体 revert，不恢复第二套长期语义 | 风险段明确无数据迁移、整体 revert。 | 覆盖。 |

### 核实台账：delta-spec

| 包 | 核实 | 结论 |
|---|---|---|
| gateway | 本次意图是内部 carrier/owner cutover；motivation 四个 Scenario 全要求现有可观察结果不变，未提出新 behavior。 | `no spec delta` 正确。 |
| im | 不改 wire、持久化或客户端消费；canonical 仅作回归基线。 | `no spec delta` 正确。 |
| kernel | 不改 `agent.sdk`、session/transcript 或 Kernel event contract。 | `no spec delta` 正确。 |
| cli | 不在调用链或文件范围内。 | `no spec delta` 正确。 |

### 核实台账：Milestone

| Milestone | 垂直性 / 举证 / 范围 / 退出标准 | 结论 |
|---|---|---|
| refactor-521-M1 typed-ingress-cutover | 单 M1 有明确原子切换理由：producer、consumer、fallback 删除不能分层交付；范围虽跨约 15 个生产文件和测试，但属于一个 interface cutover，不存在可独立交付的第二用户价值。退出标准同时有 `[reviewer]` 四个行为场景和 `[worker]` 删除/不泄漏/测试门禁。 | 拆分成立；实施准入仍被 R1-C1 阻断，R1-W2 未关闭前残留清单也不可验。 |

### 整体判断

- 上层架构总览清楚：真实 seam 是 adapter callback，目标是一个 normalized message，而不是新增 wrapper/port；人能快速理解方向。
- 数据流主干闭合：raw relay/provider → adapter normalization → dispatcher/pipeline → shadow enrichment → coordinator/runtime delivery；没有第二 callback、第二 receive loop 或 delivery policy 回流。
- 方案最大的缺口恰好在本 unit 的中心接口：文档只描述“有一个 facts value”和“至少有哪些事实”，没有把最终 value shape、唯一 authority、合法组合与 enrichment 边界写成 worker 可互操作的契约。因此当前不能交给 orchestrator 实施。
- 风险/回退基本写实；review runbook 尚未对齐当前 worktree/Feishu canonical 操作入口，见 R1-W3。

### 架构进攻

| 角度 | 主动攻击与证据 | 结论 |
|---|---|---|
| 归属 | transport origin、relay identity、external conversation/event identity 自然由 adapter normalization 产生，放到 normalized ingress interface 顺依赖方向；但 `shadow_saga_id` / `ShadowConversationRef` 是 `InboundPipeline._sync_external_shadow_message()` 调用 `IMShadowConversationSync` 后才产生（`inbound_pipeline.py:192-235`; `shadow_sync.py:83-123`），不是 channel adapter 事实。把整组 current `RuntimeProtocolFacts` 移进 `channels.base` 会让低层 channel contract 承担 Gateway post-ingress 生命周期词汇。 | 基础 seam 正确，post-ingress ownership 有长期扩张风险，见 R1-W1。 |
| 该不该存在 | 删除 `InboundEnvelope` 后生产 callback 不需要替代 wrapper；让 `InboundMessage` 直接携带 typed ingress value 确实消除一层只供测试观察的间接层。新增 port、factory 或 protocol 都没有必要，方案也未添加。 | 通过；wrapper deletion test 成立。 |
| 深还是浅 | 单纯把 9 个 optional facts 从 metadata 搬进一个未定义的 dataclass，会把字符串 bag 换成 optional-field bag，却不消除 `external_event_identity`、`external_source`、`shadow_saga_id/ref` 的重复 authority/非法组合。当前 top-level identity 在 `channels/base.py:46`，facts 又在 `runtime_protocol.py:38-48`；shadow saga 直接读前者（`shadow_saga.py:229-246`），run delivery 读后者（`runtime_delivery/context.py:351-420`）。 | 中心接口未深到能隐藏组合规则，见 R1-C1。 |
| 治本还是补丁 | D4 选择一次切掉 hidden key、derive fallback 与 wrapper，而不是再叠一层兼容，方向上直达根因；D5 也避免机械清零合法 adapter identity。 | 通过，但必须用 R1-W2 的逐点分类防止迁移只做字符串替换。 |

### Issues

- [R1-C1][CRITICAL] [决策 1-4 / 接口与数据流]: 中心 typed ingress interface 没有被定义成可实施契约。`design.md:72,80,88,112-139` 只说 facts 是 `InboundMessage` 的“显式组成”、字段“至少”表达若干事实，却没有拍死：字段名与准确类型、container 是否必填、absence/default 语义、transport origin 的 representation、Web native / Web shadow / Feishu / recovery 的合法组合，以及 shadow sync 后 enrichment 的准确输出。更关键的是，当前 `InboundMessage.external_event_identity`（`channels/base.py:46`）和 `RuntimeProtocolFacts.external_event_identity`（`runtime_protocol.py:46`）已经是两份表示，`RuntimeProtocolFacts.external_source` 又与 nested `external_identity.external_source` 重复；方案既要求 facts 包含 provider identity，又没有说明 top-level 字段删除还是投影保留。不改时，两个 worker 可以分别实现 `message.protocol`、`message.ingress_facts` 或 flatten fields，并对 top-level identity、scalar metadata、shadow saga/ref 做不同取舍；测试迁移也会各自固化不同 authority，正好重建本 unit 要消灭的双语义。请在 design 中给出准确 value/interface 签名、producer/absence matrix、单一 authority 规则和 enrichment contract，再进入实施。
- [R1-W1][WARNING] [决策 2 / 架构进攻·归属]: 方案把 current `RuntimeProtocolFacts` 整体移到 channel ingress interface 层，但其中 `shadow_saga_id` 与 `ShadowConversationRef` 是 Gateway shadow owner 在 callback 之后创建的状态（`inbound_pipeline.py:192-235`; `shadow_sync.py:83-123`），Feishu adapter 在 normalization 时不可能提供。长期代价是 `channels.base` 会随 Gateway shadow/recovery/delivery 生命周期继续膨胀，低层 adapter/tests 被迫学习 post-ingress 词汇，反向侵蚀 refactor-480 的 delivery owner。请把 adapter-produced ingress facts 与 Gateway-produced shadow enrichment 分层表达（例如 ingress value 留在 channel seam，shadow result 进入 Gateway request/context），或给出同样能保持 owner 单向依赖的明确归属论证；不要仅以“都要跟消息走”作为同层理由。
- [R1-W2][WARNING] [决策 5 / M1 退出标准]: “合法 adapter identity 保留”仍停在原则，方案没有逐项分类当前七处 `web_relay` 判断。`inbound_pipeline.py:197,310` 与 `runtime_delivery/context.py:412,420` 明显是在代理 transport capability；`runtime_delivery/background.py:235,252` 和 `observer.py:232` 则混有持久 reply target / outbound adapter routing，可能属于 D5 允许的真实 identity。若不先列出 `位置 → 当前语义 → typed replacement 或合法残留`，worker 会被迫猜：激进实现可能破坏 restart 后 background/control reply routing，保守实现则会把目标业务 proxy 留下却仍宣称退出标准通过。请把这七处以及 `channel_manager.py:409-412` 的合法 managed-channel guard 列成穷举表。
- [R1-W3][WARNING] [Runbook for Reviewer]: runbook 不能按当前 canonical worktree contract直接执行：命令使用未定义的 `REPO_ROOT`、`REVIEW_ROOT`、`MAIN_CONFIG`，而 `docs/development/worktree-runtime.md:23-37,45-76` 规定 `WT_ROOT`/main venv 初始化，并要求真实 Feishu 验收走专用 `e2e-up.sh --feishu` 与 `e2e-feishu-probe.py`，不能靠任意本机 config/现有 Bot 猜环境。不改会让 reviewer 要么命令立即失败，要么错误接入非隔离 channel，最终 external Scenario 无法形成可信 Gate 3 证据。请改为可复制的变量初始化、trap cleanup、`--feishu`/profile preflight 与 probe 命令。

### Recommendations

- [R1-R1] 在 `motivation.md` Relations 中补记直接 predecessor `refactor-454` 与 `bugfix-471`；当前 design 已依赖二者的裁决，关系表缺失会降低后续归档检索质量。
- [R1-R2] 接口补齐后，让 callback seam 的 contract test 直接断言 `seen[0]` 携带 canonical typed value；删除只验证 `accept_relay()` 返回 wrapper 的测试，保持 replace-don't-layer。

### Author Resolutions

- [R1-C1] accepted — 决策 1-4 与接口段新增准确的 `InboundIngress`/`IMRelayIngress`/`RoutedInbound`/`GatewayShadowState` shape、required/default/absence、合法组合、producer matrix、单一 authority 与 enrichment contract；删除 top-level event identity 和全部 legacy derive。
- [R1-W1] accepted — adapter-produced facts 只留在 `channels.base`；saga/ref 明确保留在 Gateway-owned `GatewayShadowState`，pipeline 后组成 `RoutedInbound`，不回写 message。
- [R1-W2] accepted — 新增八个 production 判断的穷举表，四处 ingress business proxy typed 化，三处 persisted outbound identity 与一处 managed-channel guard 明确保留，并要求最终 residual 清单。
- [R1-W3] accepted — runbook 现在初始化所有变量、注册 cleanup trap，并分别给出 default Web 与专用 `--feishu` stack、identity-checked probe 命令。
- [R1-R1] accepted — motivation Relations 补记 refactor-454 与 bugfix-471。
- [R1-R2] accepted — M1 退出标准要求 callback carrier contract、producer matrix、invalid combination 与 replace-don't-layer 删除证据。

## Round 2

### Metadata

- reviewer: `/root/session_continuity`
- review_mode: `full`
- mode_reason: 初读修订可界定为 R1 issue closure，但作者把中心接口从一阶段 facts 改成 `InboundIngress + RoutedInbound/GatewayShadowState` 两阶段跨模块 contract，并要求所有 request/lifecycle handoff 随之迁移；这属于核心边界、数据流和共享接口的高风险变化，因此本轮直接升级为 full，重跑全部五类承重原子与四个架构进攻角度。
- started_at: `2026-08-10T10:03:32+08:00`
- completed_at: `2026-08-10T10:10:06+08:00`
- duration: `6m34s`

### Verdict

Changes requested — 1 CRITICAL / 0 WARNING

### Coverage

- 首文档与方案：完整复核当前 `motivation.md`、修订后的 `design.md`、R1 全文与 Author Resolutions；本 unit 仍无 delta-spec 文件。
- canonical 契约：重核 `docs/specs/gateway/{routing-delivery,relay-protocol,external-channels}.md` 与 `docs/specs/im/{gateway-relay,conversations-messages}.md`，覆盖 Web relay 幂等、群聊 `/new`、静默 provisional 回滚、external reply/shadow/recovery 和 provider-stable event identity。
- 生产调用链：重新从 WebRelay/Feishu adapter callback 正向追到 dispatcher、pipeline shadow sync、四类 request、coordinator lifecycle、`RunDeliveryContextStore`、external control/mirror 与 reply/session/saga 持久化；并核对 recovery replay 的独立 producer 路径。
- 历史与边界：复核 archived refactor-454、refactor-463、refactor-480、bugfix-471、bugfix-508 的直接裁决，以及 `AGENTS.md` 包依赖红线；当前修订未改变 motivation 的需求、非目标或单 M1 范围。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 给出准确 carrier、producer matrix、单一 authority 与 enrichment contract | `design.md:114-186` 已拍死 `InboundIngress`、`IMRelayIngress`、`RoutedInbound`、`GatewayShadowState`、absence/组合和 producer matrix；`design.md:98-102,169-174` 也删除 top-level event identity、hidden key 与 derive fallback。但 target `ShadowConversationRef` 未重定义/删字段，仍与新增 `GatewayShadowState.saga_id` 重复同一 saga authority，见 R2-C1。 | partially closed；仍阻断 |
| R1-W1 | adapter facts 与 Gateway shadow state 分层 | `design.md:80-86,137-146,169-172` 把 raw ingress 留在 `channels.base`，把 callback 后才产生的 saga/ref 放进 Gateway-owned state；这与当前 `inbound_pipeline.py:192-235`、`shadow_sync.py:83-123` 的真实产生时点一致。 | closed |
| R1-W2 | 穷举八处 production 判断 | `design.md:188-201` 精确覆盖 pipeline 两处、runtime context 两处、background 两处、observer 一处和 channel-manager 一处；独立 `rg` 还确认 `composition.py:744` 属于该段明示保留的 adapter composition identity。 | closed |
| R1-W3 | 修正隔离 E2E runbook | `design.md:227-248` 初始化 `REPO_ROOT/WT_ROOT/NANO_MAIN_ROOT`、设置 cleanup trap，并分别使用默认 stack 与 `--feishu` + probe；与 `worktree-runtime.md:23-37,39-76` 一致。 | closed |
| R1-R1 | 补直接历史关系 | `motivation.md:3-8` 已列 refactor-454 与 bugfix-471。 | closed |
| R1-R2 | callback carrier 与 replace-don't-layer tests | `design.md:203-208,250-256` 已要求从 callback seam 断言 canonical value，并删除 wrapper/helper 测试与实现。 | closed |

### 核实台账：现状断言

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| S1 production ingress 是单值 callback | `channels/base.py:23-46,85,101-109` 定义 `InboundMessage`/`InboundHandler`；WebRelay `accept_relay()` 在 `web_relay_adapter.py:213-230` 调 callback，Feishu 在 `adapter.py:397-411,456-470` 调同一形状。 | 成立；D1 落在真实 seam。 |
| S2 `InboundEnvelope` 没跨生产 seam | `web_relay_adapter.py:161-175,213-230` 显示 wrapper 仅为返回值，callback 仍取 `.message`。 | 成立；删除 wrapper 不需要替代 channel callback。 |
| S3 current facts 有 hidden key 与 derive 双读 | `runtime_protocol.py:13,38-48,57-90,93-150` 同时保有 attached typed value、metadata derive 与重复 scalar identity。 | 成立；D4 的原子切换有事实基础。 |
| S4 shadow state 是 callback 后事实 | pipeline 在 `inbound_pipeline.py:192-235` 调 `sync_user_message()` 后才 attach saga/ref；sync 在 `shadow_sync.py:83-123,223-239` 产生 anchored ref 或 pending error。 | 成立；两阶段 owner 必要。 |
| S5 request/lifecycle 当前只传 message | `inbound_models.py:15-77,116-118` 的四类 request 和 lifecycle callback 都携带 `InboundMessage`；`lifecycle.py:29-50`、`context.py:336-420` 随后从它重取 protocol。 | 成立；修订要求传 `RoutedInbound` 命中真实下游。 |
| S6 native Web relay 的 IM delivery target 可由 relay + IM conversation 投影 | 当前 `context.py:358-367` 在无 external shadow ref 时，用 relay task 与 `message.external_chat_id` 构造 delivery target。 | 成立；producer matrix 不必给 native Web 伪造 Gateway shadow state。 |
| S7 Feishu 与 recovery 都是 provider identity producer | Feishu 在 `adapter.py:397-408,456-467` 构造 event identity；recovery 在 `shadow_sync.py:446-495` 从 durable canonical payload 重建 external/event identity。 | 成立；matrix 覆盖两个真实入口。 |
| S8 current saga/ref 关系包含重复 saga field | `runtime_protocol.py:27-34` 的 `ShadowConversationRef` 本身含 `shadow_saga_id`；`shadow_sync.py:223-227` 写它，pipeline 又在 `inbound_pipeline.py:227-233` 把它复制到 parallel `RuntimeProtocolFacts.shadow_saga_id`。 | 成立；修订尚未拍死如何消除该最后一处双 authority，见 R2-C1。 |
| S9 `web_relay` 判断可穷举 | production equality guards 位于 `inbound_pipeline.py:197,310`、`runtime_delivery/context.py:412,420`、`background.py:235,252`、`observer.py:232`、`channel_manager.py:410`，另有 composition identity `composition.py:744`。 | 修订表与真实命中一致。 |
| S10 scalar projection 与 typed carrier 的 persistence 边界真实存在 | `session_keys.py:1590-1661` 构造 reply/session projection；`shadow_saga.py:224-289` 保存 canonical inbound；当前均 strip private facts 后再显式落 scalar。 | 成立；D4 删除 strip helper 后仍须保持结构投影。 |
| S11 runtime delivery typed owner 不应回流 ingress | `context.py:326-420` seed per-run typed state，observer 只读该 state；archived refactor-480 将它定为唯一 delivery authority。 | 成立；修订只投影、不搬 delivery policy。 |
| S12 包依赖与历史 façade 约束 | `AGENTS.md` 禁止 PA/IM Python 互相 import，refactor-463 保留 `handle_inbound(message)`；本设计只在 PA 内部移动 typed values且不改 façade 参数。 | 成立。 |

### 核实台账：关键决策

| 决策 | 完整性 / 自洽 / 依据核实 | 结论 |
|---|---|---|
| D1 单值 `InboundMessage.ingress` | field 名、owner、default 与 producer obligation 已拍死；不会重建 wrapper 或第二 callback。 | 成立。 |
| D2 adapter ingress / Gateway shadow 两阶段 | 依赖方向与生产产生时点一致，`RoutedInbound` 确实跨 request/lifecycle seam；但 nested `ShadowConversationRef` 的 target shape 未收口。 | 主方向成立；被 R2-C1 阻断。 |
| D3 transport 与 external identity 正交 | `im_relay` 与 `external_conversation` 分离，matrix 覆盖 native Web、external-through-IM、Feishu、recovery、generic；与 group gate/external reply canonical 一致。 | 成立。 |
| D4 同一 M1 删除 legacy authority | top-level event identity、`RuntimeProtocolFacts`、private key/helper/fallback 均列入删除，并禁止整体 typed value 落库。 | 大部成立；遗漏 current ref 内 saga duplicate，见 R2-C1。 |
| D5 保留合法 adapter identity | 精确残留表避免把 outbound routing/managed guard 误改为 capability；范围没有扩成 ChannelManager 重构。 | 成立。 |

### 核实台账：首文档约束

| spec 原子 | 覆盖与冲突检查 | 结论 |
|---|---|---|
| 用户原话：Agent 自主完成，只交 PR review | 方案无待确认项，单 M1 + runbook/两轨退出可直接交 orchestrator。 | 覆盖。 |
| Web IM direct 路由/回复 | carrier 不改 route priority、session key、relay receipt 或 reply target；canonical `routing-delivery.md:20-26` 与 `gateway-relay.md:65-81` 保持。 | 覆盖。 |
| group gate、裸 `/new` 与 silence | D3/matrix/`web_relay` 表显式保持 native/external 区分，回归 `routing-delivery.md:53-88` 与 provisional discard `gateway-relay.md:130-138`。 | 覆盖。 |
| external reply/shadow ordering | Feishu external identity/event、pending/anchored shadow state和 delivery projection均保留；对齐 `external-channels.md:93-193`。 | 覆盖。 |
| disconnect/replay 幂等 | relay task/idempotency required，recovery 从 canonical saga payload重建；对齐 `relay-protocol.md:74-85,186-220` 与 `gateway-relay.md:65-81`。 | 覆盖。 |
| 范围/非目标 | 未改 IM wire/provider contract、agent.sdk、frontend 或 ChannelManager 架构。 | 不越界。 |
| 单次迁移/整体回退 | D4 与单 M1 无长期双读，风险段明确整体 revert且无 schema migration。 | 覆盖。 |

### 核实台账：delta-spec

| 包 | 核实 | 结论 |
|---|---|---|
| gateway | 全部目标是内部 carrier/authority cutover，motivation 的四个产品 Scenario 均要求行为不变。 | `no spec delta` 正确。 |
| im | 不改 relay wire、REST/WS payload、SQLite 或 frontend consumer。 | `no spec delta` 正确。 |
| kernel | 不改 `agent.sdk`、Kernel session/run 或 transcript contract。 | `no spec delta` 正确。 |
| cli | 不在调用链或文件范围。 | `no spec delta` 正确。 |

### 核实台账：Milestone

| Milestone | 垂直性 / 举证 / 范围 / 退出标准 | 结论 |
|---|---|---|
| refactor-521-M1 typed-ingress-cutover | producer、consumer、fallback 删除与 persistence guard 是同一 authority cutover，拆开会产生双读；范围覆盖所有 current runtime-protocol consumer，退出同时含四个产品旅程与 carrier/deletion/residual/persistence/test worker gates。 | 单 M1 合理；R2-C1 关闭前 carrier 的 saga authority 退出标准仍不可唯一实施。 |

### 整体判断

- 修订后的上层结构清楚：adapter normalization 只产 raw ingress，Gateway shadow sync 再产 state，随后统一进入 coordinator/runtime delivery；人可以直接判断 owner 方向。
- 数据流覆盖 callback、run/control requests、lifecycle、per-run delivery 和 recovery；R1-W1/W2/W3 已有可执行闭环。
- 仍有一个位于中心接口内部的单一-authority缺口：新增 state 的 `saga_id` 与被“复用”的 current ref 字段表达同一事实，target design 未声明删除/迁移哪一个。它会让两个独立 worker 产出不兼容的 carrier，因此尚不能进实施。

### 架构进攻

| 角度 | 主动攻击与证据 | 结论 |
|---|---|---|
| 归属 | `InboundIngress` 只含 adapter/recovery normalization facts，`GatewayShadowState` 只在 pipeline 调 shadow owner 后出现；依赖始终是 Gateway → channel value，没有 channel → Gateway 反向 import。 | 通过；R1-W1 已关闭。 |
| 该不该存在 | 删除 `InboundEnvelope` 后让 callback 直接交 `InboundMessage` 可减少死 wrapper；删除 `RoutedInbound` 则四类 request 与 lifecycle 必须各自平铺/配对 message + shadow，重新制造可错配的平行参数。 | 两个 deletion test 均成立，新增第二阶段 container 不是 YAGNI。 |
| 深还是浅 | `InboundIngress` 用三个正交 optional 子值和 producer matrix 隐藏 provider/transport 组合，明显比 metadata bag 更深；但 `GatewayShadowState.saga_id` 若与 `ShadowConversationRef.shadow_saga_id` 并存，调用方仍要维持 equality invariant，接口没有真正隐藏 saga 组合复杂度。长期代价是 control idempotency、pending boundary 与 mirror output 可各自读取不同 saga。 | 未通过，见 R2-C1。 |
| 治本还是补丁 | 同一 M1 删除 wrapper、hidden key、derive 与业务 provider proxy，且对合法 routing identity 做穷举保留；没有兼容层或 capability graph 特例。 | 通过；方向直达根因。 |

### Issues

- [R2-C1][CRITICAL] [决策 2、4 / 接口与数据流]: 新 `GatewayShadowState.saga_id` 尚未成为可实施的唯一 saga authority。修订在 `design.md:137-146` 定义 `GatewayShadowState(saga_id, ref)`，并要求 anchored state 同时携带“该 ref 对应的 saga id”，但没有重定义 `ShadowConversationRef` 的 target shape，也没有在 D4 的删除清单中移除其 current `shadow_saga_id` 字段。当前类型确实在 `runtime_protocol.py:27-34` 自带该字段，sync 在 `shadow_sync.py:223-227` 写入，pipeline 又在 `inbound_pipeline.py:227-233` 复制到 parallel saga field。若 worker 按“复用 ShadowConversationRef”保留现状，新 state 会继续有两份可漂移的 saga id；若 worker按“单一 authority”自行删字段，则其 owner、所有构造点和相应 deletion test 都是未声明猜测。两种实现会直接影响 control operation id、pending config boundary 与 external output mirror 选用哪条 saga，无法互操作。请拍死 target `ShadowConversationRef` 的准确字段/owner，并明确二选一：推荐删除 ref 内 `shadow_saga_id`，只由 `GatewayShadowState.saga_id` 承载且加 absence/match deletion contract；或改写 state 使 saga 只有一个权威位置。关闭后 R1-C1 才算完整闭环。

### Recommendations

- 无新增非阻断建议。

### Author Resolutions

- [R2-C1] accepted — `ShadowConversationRef` target shape 固定为 Gateway-owned `(conversation_id, im_message_id)`，两字段 required；删除旧 `relay_task_id`/`shadow_saga_id`。`GatewayShadowState.saga_id` 是唯一 saga authority，并拍死 empty/pending/anchored 三态与 invalid ref-without-saga。native Web relay 与 external shadow 分别投影 `IMRelayTarget`/`ExternalShadowTarget`，避免继续把 relay identity 塞进 shadow ref；M1 增加 deletion/absence/operation-id/promotion/mirror contracts。

## Round 3

### Metadata

- reviewer: `/root/session_continuity`
- review_mode: `delta`
- mode_reason: 本轮语义修订可封闭在 R2-C1 对应的 `ShadowConversationRef` target shape、`GatewayShadowState` 三态、saga authority 和 run-delivery stage projection；没有改变需求范围、owner 边界、canonical behavior 或 milestone 拆分，因此以 Round 2 的 full inventory 为基线，只重查 changed atoms、上下游影响与受影响架构角度。
- started_at: `2026-08-10T10:14:07+08:00`
- completed_at: `2026-08-10T10:15:55+08:00`
- duration: `1m48s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- changed atoms: `design.md:97-103` 的删除边界、`design.md:113-155` 的 ref/state/target 精确契约、`design.md:176-196` 的消费/deletion/producer contracts、`design.md:260-266` 的 M1 退出增量。
- 上游重查：current shadow sync 的 empty、pending exception、anchored ref 与 durable saga record；下游重查 control operation id、pending boundary、external output mirror、lifecycle → `RunDeliveryContext` 投影及 observer 的 per-run authority。
- `retained_from: Round 2` — motivation、canonical specs、D1/D3/D5、`web_relay` 穷举、runbook、no-spec-delta 与单 M1 均未变化；Round 2 full 台账和已关闭的 R1 issues 继续有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | 固定 ref 为 `(conversation_id, im_message_id)`；state 独占 saga；删除旧 saga/relay fields；分型 run target并补 deletion contracts | `design.md:99,142-155` 现在完整定义 owner、字段、requiredness、三种合法 state 与唯一 saga authority；`design.md:184,266` 把旧字段删除及 operation-id/promotion/mirror 单权威写入可验退出。不存在 worker 仍可合法保留 ref 内 saga/relay 字段的第二种实现。 | closed |

### Delta 核实台账

| changed atom | 上下游与现状证据 | 结论 |
|---|---|---|
| `ShadowConversationRef(conversation_id, im_message_id)` | current ref 在 `runtime_protocol.py:27-34` 混入 relay/saga；但 durable external anchor 实际只有两项：`shadow_saga.py:65-74` 仅在 conversation/message id 都存在时返回 ref，`shadow_sync.py:218-235` 也先校验两者再 record。删除 optional relay/saga fields 与真实 external anchor 契约一致。 | 精确且可实施。 |
| `GatewayShadowState` empty/pending/anchored 三态 | current pipeline 的 skip/无 identity 返回 message（`inbound_pipeline.py:195-200,216-217`）、`ShadowSyncPendingError.saga_id`（`203-215`）和 anchored ref（`218-235`）恰好映射三态；禁止 ref-without-saga 消除 R2 指出的非法组合。 | 闭合，无第四种生产状态。 |
| saga 唯一 transient authority | current pipeline 把 `shadow_ref.shadow_saga_id` 复制进 facts（`inbound_pipeline.py:227-233`）；target 删除 ref 字段后，control id、pending boundary和 mirror 都从 `routed.shadow.saga_id` 投影，M1 明确 deletion/contract tests。 | R2 双 authority 已消失。 |
| native relay / external shadow 分型 target | current `context.py:358-367` 用同一 `ShadowConversationRef` 同时表达 external anchor和 native relay provisional target；target `IMRelayTarget(conversation_id, relay_task_id, im_message_id)` 与 `ExternalShadowTarget(ref)` 分离二者，而进入 context 后仍由 refactor-480 的 `RunDeliveryContext` 独占 run-time mutation。 | 分型解决旧 ref 过载，不新增平行 delivery owner。 |
| durable promotion/recovery | pending boundary 已把 scalar saga id durable 写入 SQLite（`session_keys.py:1210-1225`），anchor 后 `promote_pending_boundary(shadow_saga_id, ref)` 以该 durable projection完成恢复（`1236-1297`）；design 禁止的是从 ref/metadata回推 saga，不是禁止 durable saga/store 持有其主键，也不把 `GatewayShadowState` 整体落库。 | 与 recovery/persistence contract 不冲突。 |

### 受影响的架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 | ref 只保留 shadow-sync 确认的 IM anchor，saga 留在 Gateway state，relay 留在 adapter ingress；三类事实的 producer/owner 不再互相污染。通过。 |
| 该不该存在 / deletion test | 删除 `GatewayShadowState` 会让 pending saga 与 optional ref重新成为可错配平行字段；删除 `IMRelayTarget`/`ExternalShadowTarget` 的区分又会迫使 native relay 把 relay id 塞回 shadow ref。两层分型都在集中复杂度，而非只搬位置。通过。 |
| 深还是浅 | 调用方只面对三态 state 或已经投影好的 per-run target，不再维护 `state.saga_id == ref.shadow_saga_id` equality invariant；context seed 后 observer只读 context。R2 的浅接口问题已治本。 |
| 治本还是补丁 | D4 与 M1 明确删除旧字段、构造点、equality tests和 fallback consumers，并以 absence/deletion contracts 防回流；没有保留兼容 alias 或双读期。通过。 |

### Issues

- 无。

### Recommendations

- 无新增非阻断建议；可以进入 `change-orchestrator`。
