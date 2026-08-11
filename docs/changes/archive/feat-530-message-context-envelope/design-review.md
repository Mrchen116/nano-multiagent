# Design Review: feat-530-message-context-envelope

## Round 1

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 恒为 full；从 unit 首文档、全部 delta-spec、milestone 骨架、current canonical specs 和 Web IM / Feishu 生产 wiring 重建事实基线。`
- started_at: `2026-08-10T16:22:46+08:00`
- completed_at: `2026-08-10T16:30:05+08:00`
- duration: `7m19s`

### Verdict

Not Approved — 5 CRITICAL / 1 WARNING

### Coverage

- 现状台账：9 条涉及范围、8 条既有约束、7 条契约 grounding、7 条可复用能力、4 条既有模式、4 条历史前提，全部逐条核对。
- 决策台账：决策 1–8 全部核对完整性、歧义、自洽性、spec 驱动与现状边界。
- spec 约束：8 条澄清、4 段用户场景、5 个 Requirement 下的 12 个 Scenario、7 条非目标全部对账。
- delta-spec：`specs/gateway/routing-delivery.md` 的 1 个 ADDED Requirement 和 8 个 Scenario 全部核对；`kernel` / `im` / `cli` 的 no-delta 声明也按实际消费者边界核对。
- milestone：`feat-530-M1` 与 `feat-530-M2` 的依赖、范围、两轨退出标准和拆分举证全部核对。
- 生产路径：正向追了 `GatewayRuntime -> start_channels/IMConnectionManager -> WebRelayAdapter/FeishuAdapter -> InboundDispatcher -> InboundPipeline -> SessionRunCoordinator -> agent.sdk -> Runtime/AgentLoop -> JsonlTranscript`，并单独追了 Feishu REST 群历史 catch-up、heartbeat/cron 的 PromptSlots 组装和 PA 可读 `chat_history` hook。

### 现状断言核实台账

| ID | 原子 | 结论与独立证据 |
|---|---|---|
| S1 | `InboundMessage` 是 PA 共用入站接口，当前无发生时间 | 成立；字段仅有 channel/text/sender/chat/routing/metadata/event identity，见 `src/personal_assistant/channels/base.py:23-46`。 |
| S2 | IM relay 已带 `message.created_at`，Web Adapter 丢弃 | 成立；IM 组 payload 见 `src/IM/application/relay_service.py:112-131`，Adapter 只取 id/body/metadata 见 `src/personal_assistant/channels/web_relay_adapter.py:246-297`。 |
| S3 | Feishu live event 有 `create_time`，当前投影类未保留 | 对 live event 成立；`FeishuMessageEvent` 无时间字段，且 live parser 未读取，见 `src/personal_assistant/channels/feishu/client.py:137-166,1089-1138`。但现状分析漏了另一条生产 REST history parser，见 R1-C4。 |
| S4 | Pipeline 是 Web/Feishu 共同 raw/model 分叉 owner | 成立；生产 composition 共享同一 Pipeline/Dispatcher，见 `src/personal_assistant/gateway/composition.py:528-573,696-710`；route/gate/shadow/buffer/dispatch 顺序见 `src/personal_assistant/gateway/inbound_pipeline.py:104-190`。 |
| S5 | Coordinator 共享 group drain、parts、normal/steer | 成立；active path 的 `try_steer` 和 normal path 均走 `_build_message_parts`，见 `src/personal_assistant/gateway/session_run_coordinator.py:232-241,873-885,1125-1167`。 |
| S6 | GroupContextStore 可持久 JSON metadata，不需新表 | 成立；既有 `metadata_json` 列、JSON append/drain 见 `src/personal_assistant/gateway/group_context_store.py:20-38,62-95,116-134`。 |
| S7 | PA prompt 只经既有 PromptSlots | 成立；`prompt_for()` 构造四槽并返回 `PromptSlots`，见 `src/personal_assistant/product.py:291-356`；生产 runtime projection 见 `src/personal_assistant/gateway/session_composition.py:51-87`。 |
| S8 | Core footer 把 session-created 时间写成 Current date | 成立；Runtime 把 `config.created_at` 传入 prompt，见 `src/agent/core/agent/runtime.py:381,509-530`；footer 文案见 `src/agent/core/agent/prompt_sections/core_sections.py:320-346`。 |
| S9 | AgentLoop 有两个 pending consume 点但不产生可持久 user Message | 成立；round drain 直接 append `LLMMessage` 见 `src/agent/core/agent/loop.py:343-376`，terminal re-drain 见 `src/agent/core/agent/loop.py:591-624`。 |
| S10 | PA 只 import `agent.sdk` | 成立且是硬边界，见 `SPEC.md:113-124,148-161`。 |
| S11 | 非 PA 及 PA 非真人消息须保持现状 | 是 spec 约束；但方案对 PromptSlots marker 的选择未闭合，见 R1-C2。 |
| S12 | visible body 与 model parts 已分层 | IM/shadow raw path 成立；shadow 在 model dispatch 前使用 raw message，见 `src/personal_assistant/gateway/inbound_pipeline.py:134-152`，model parts 后续才在 Coordinator 组装，见 `src/personal_assistant/gateway/session_run_coordinator.py:1125-1167`。PA 可读 chat copy 是被漏掉的第三个消费者，见 R1-W1。 |
| S13 | occurrence time 只能一次选择 | 是目标不变量；当前无这个数据，因此必须在 Pipeline 分叉前冻结。 |
| S14 | actual Channel 是逐消息 ingress | 成立；shadow 只共享 session identity，回复路由实际触发源决定，见 `docs/specs/gateway/external-channels.md:93-111`；Gateway 以 message runtime protocol 建共享 key，见 `src/personal_assistant/gateway/session_keys.py:1614-1629`。 |
| S15 | 群聊既有 `[sender]` | 成立；见 `src/personal_assistant/gateway/session_run_coordinator.py:1141-1166,1744-1759`。 |
| S16 | 旧 transcript/buffer 无可靠 context 不回填 | 与现有数据结构相容；buffer metadata 可区分 marker 缺失，transcript 直接回放旧 bytes，见 `src/personal_assistant/gateway/group_context_store.py:116-134` 和 `docs/specs/kernel/context-persistence.md:67-74`。 |
| S17 | stable timezone / dynamic tail 是 cache-safe 约束 | 成立；Kernel skeleton 将 body/custom 置于 stable 区、tail 置于 volatile 尾，见 `src/agent/core/agent/prompt_sections/skeleton.py:90-128`。 |
| S18 | current gateway routing spec 覆盖 route/buffer/steer/restart | 成立；相关 current Requirements 见 `docs/specs/gateway/routing-delivery.md:168-218,249-271`。 |
| S19 | external spec 覆盖 actual ingress/shadow continuity | 成立；见 `docs/specs/gateway/external-channels.md:93-111,268-292`。 |
| S20 | IM 保存 raw body 且 relay 已含 created_at | 成立；见 `docs/specs/im/conversations-messages.md:106-128`和 `src/IM/application/relay_service.py:112-131`。 |
| S21 | Kernel prompt current contract 是 fixed skeleton + PromptSlots | 成立；见 `docs/specs/kernel/prompts.md:14-49`。但该契约不允许 Core 用产品 piece name 重新 gate 自身骨架，见 R1-C1。 |
| S22 | normal user turn 持久/replay 可复用 | 成立；normal input 在进 loop 前 `durable=True`，见 `src/agent/core/agent/runtime.py:546-565`；重启契约见 `docs/specs/kernel/context-persistence.md:67-74`。 |
| S23 | SDK 公开接口当前足够传 model parts | 成立；`submit`/`try_steer` 均接 `parts`，见 `src/agent/sdk/kernel.py:1447-1510`。但用 `PromptText.name` 暗中切 Core policy 不是“接口不变”，见 R1-C1。 |
| S24 | 相关 canonical 无需先修的 route/shadow drift | 未发现阻断本方案的 route/shadow drift；但可读 chat copy 是被遗漏的生产消费者，见 R1-W1。 |
| S25 | 复用 `channel_name` 映射 actual ingress | 成立；Web 固定 `web_relay`，Feishu 是 `feishu:<agent_id>`，见 `src/personal_assistant/channels/web_relay_adapter.py:177-199,281-297` 和 `src/personal_assistant/channels/feishu/adapter.py:397-411,456-470`。 |
| S26 | Adapter 是 provider 时间归一 seam | 对 live Web/Feishu 成立；但 Feishu REST history 也是 Adapter 生产 seam，方案未枚举，见 R1-C4。 |
| S27 | Pipeline admission ordering 可复用 | 成立；见 `src/personal_assistant/gateway/inbound_pipeline.py:104-190`。 |
| S28 | Group metadata round-trip 可复用 | 成立；见 `src/personal_assistant/gateway/group_context_store.py:62-95,116-134`。 |
| S29 | Coordinator ordered parts 可复用 | 成立；见 `src/personal_assistant/gateway/session_run_coordinator.py:1125-1167,1714-1759`。 |
| S30 | Runtime 是 AgentLoop yield 的 transcript owner | 成立；Runtime 消费 loop 并 append transcript，见 `src/agent/core/agent/runtime.py:629-672`。但“append 即 durable”不成立，见 R1-C3。 |
| S31 | runtime reconfigure 可让已有 PA session 获得新 PromptSlots | 成立；Gateway 每次 admission 投影 runtime 并持久替换，见 `src/personal_assistant/gateway/session_run_coordinator.py:855-872,1198-1224`；current contract 见 `docs/specs/kernel/prompts.md:28-45`。 |
| S32 | envelope 应与 `[sender]` 一样是 user-role projection | 成立；既有 sender 就在 Coordinator parts 处理，见 `src/personal_assistant/gateway/session_run_coordinator.py:1141-1166`。 |
| S33 | stable/volatile prompt 分层可沿用 | 成立；见 `src/agent/core/agent/prompt_sections/skeleton.py:90-128`。 |
| S34 | `injection_consumed` 是真 consume 时点 | 成立；两个 drain 后才 dispatch，见 `src/agent/core/agent/loop.py:364-376,617-624,764-792`。 |
| S35 | 旧数据不猜测是既有兼容原则 | 与 append-only/replay 契约一致，见 `docs/specs/kernel/context-persistence.md:60-74`。 |
| S36 | feat-379 建立 prompt skeleton 与 session-created footer | 代码现状成立，见 `src/agent/core/agent/prompt_sections/skeleton.py:99-128` 和 `src/agent/core/agent/runtime.py:381,509-530`。 |
| S37 | feat-447 建立 Feishu/shadow/group seams | 代码现状成立，见 `src/personal_assistant/channels/feishu/adapter.py:227-290` 和 `src/personal_assistant/gateway/inbound_pipeline.py:192-235`。 |
| S38 | bugfix-426/feat-501 建立 steer accept/consume | 代码现状成立，见 `src/agent/core/agent/run_control.py:96-139,161-170` 和 `src/agent/core/agent/loop.py:343-376,591-624`。 |
| S39 | OpenClaw 参考基线 | 本轮不以上游作 current 契约；仅核对被采用机制没有越出 unit spec，用户拍板见 `spec.md:40-50`。 |

### 决策核实台账

| 决策 | 完整/自洽判断 | 证据 |
|---|---|---|
| D1 Pipeline 一次冻结 | 主体成立；Pipeline 确是 raw consumers 与 buffer/dispatch 的共同 seam，且决策不修改 raw text。 | `src/personal_assistant/gateway/inbound_pipeline.py:104-190` |
| D2 Adapter 归一 source time | 不完整；live event 之外还有 REST history catch-up 生产路径。 | R1-C4 |
| D3 稀疏固定 header | 格式、Channel label、sender 顺序和 multimodal 插入均已拍死；但用户可读 chat copy 未被保护。 | `src/personal_assistant/gateway/session_run_coordinator.py:1125-1167`; R1-W1 |
| D4 Gateway startup timezone | 在当前个人单用户 Gateway 约束下成立；没有已存在的通用 PA user-timezone 配置可直接复用。 | `SPEC.md:132-144`; 现有 timezone 配置仅属 heartbeat active-hours，见 `src/personal_assistant/config/local_store.py:196-228` |
| D5 raw/frozen/transcript 三层 | normal submit 与 group buffer 分层成立；对 consumed steer 的 durability 前提错误。 | `src/agent/core/agent/runtime.py:546-565`; R1-C3 |
| D6 PromptSlots marker 选 timezone-only footer | 不成立；一方面让 product-specific name 改写 Core policy，另一方面未定义 human/background 选择边界。 | R1-C1, R1-C2 |
| D7 consume 点先持久 user steer | 目标和 consume 点选择正确，但“yield 后现有 Runtime consumer 即已 durable”与实际代码不符。 | R1-C3 |
| D8 无 SDK/IM/DB/tool 变化 | IM/DB/tool 部分成立；SDK consumer semantics 部分不成立，因为现有 `PromptText.name` 被设计成了未公开的 Core policy switch。 | R1-C1 |

### spec 约束对账

#### 澄清与用户场景

| ID | 约束 | 覆盖判断 |
|---|---|---|
| Q1 | 仅 PA 真人入站；CLI/background/subagent/internal 不变；SDK 最好不碰 | envelope 范围有覆盖，但 background prompt 选择未闭合，且用私有 marker 绕过公开契约，见 R1-C1/R1-C2。 |
| Q2 | provider occurrence 优先，缺失回退 Gateway receipt，按用户时区 | live Web/Feishu 覆盖；Feishu REST history 漏覆盖，见 R1-C4。 |
| Q3 | 只表达平台，不重复 Direct/Group，保留 sender | D3 与 delta 完整覆盖。 |
| Q4 | Channel 是逐消息实际入口 | D1/D3 以 `message.channel_name` 冻结，完整覆盖。 |
| Q5 | envelope 只进模型，Web/Feishu/shadow raw 不变 | IM/shadow 主路覆盖；PA 可读 chat copy 仍会抓 model text，见 R1-W1。 |
| Q6 | PA 去 session-created Current date，只留 timezone；其他产品不变 | 目标有写，但 D6 跨层手段和选择边界不合格，见 R1-C1/R1-C2。 |
| Q7 | 新消息重启稳定，旧消息不猜测 | normal/group 覆盖；consumed steer 的“LLM 前 durable”尚不成立，见 R1-C3。 |
| Q8 | 不新增精确时间工具 | D8 完整覆盖。 |
| U1 | 跨早晚长会话能理解每条时间 | D1–D5 与 delta scenario 覆盖。 |
| U2 | 同一 shadow context 中 Feishu/Web IM 逐消息区分 | D1/D3 与 actual-ingress 集成退出标准覆盖。 |
| U3 | 群聊 sender 保留，不增 Group/Direct，正文 raw | D3/D5 覆盖；chat copy 例外未处理，见 R1-W1。 |
| U4 | 重启续接、旧消息不猜测、非目标不变 | normal/group 覆盖；background prompt 与 steer durability 分别见 R1-C2/R1-C3。 |

#### Requirements / Scenarios

| Requirement | 本轮逐 Scenario 核对 | 结论 |
|---|---|---|
| 每条真人消息发生时间 | 跨时段：D1/D3/D5；source 优先：D2；fallback：D1/D2 | 部分未覆盖；Feishu history catch-up 会丢 source time，见 R1-C4。 |
| 每条真人消息实际入口 | shadow 跨入口：D1/D3；群 sender：D3/D5；私聊稀疏平台：D3 | 覆盖完整。 |
| envelope 不改用户原文 | 原入口查看/复制：D1/D5；shadow 同步/搜索：D1/D5 | 指定的 IM 表面已覆盖；可读 workspace copy 的现有契约未被讨论，见 R1-W1。 |
| 新消息时间/入口稳定延续 | Gateway restart：D5/D7；旧历史不回填：D5 | normal/group 成立；consumed steer 尚缺真正的 LLM-before-durability barrier，见 R1-C3。 |
| 非 PA 入口保持 | Coding CLI：D6–D8；heartbeat/cron/subagent/internal：D6–D8 | 不成立；PromptSlots 共享组装路径下没有可执行的选择契约，见 R1-C2。 |

#### 非目标

| ID | 非目标 | 对账 |
|---|---|---|
| N1 | 不改 CLI/heartbeat/cron/subagent/internal | CLI/subagent 路径可保持；heartbeat/cron 选择未闭合，见 R1-C2。 |
| N2 | 不新增 `session_status` | D8 覆盖。 |
| N3 | 不新增/改变 `agent.sdk` 公共能力与消费者契约 | D6/D7 将现有 `PromptText.name` 变成隐藏 policy switch，实际违反，见 R1-C1。 |
| N4 | 不增 Direct/Group/internal IDs | D3 覆盖。 |
| N5 | 不引入其他 OpenClaw prefix | D3/D8 覆盖。 |
| N6 | 不改 Web/Feishu/shadow 展示复制搜索 | raw shadow 数据流覆盖。 |
| N7 | 不为旧消息补造 | D5 覆盖。 |

### delta-spec 核实台账

| ID | 条目 | 结论 |
|---|---|---|
| Δ1 | ADDED Requirement 的 target/用法 | `gateway/routing-delivery.md` 是最窄 current target，且是真新增并行契约，ADDED 用法正确。 |
| Δ2 | 长会话每条时间 | 消费者可观察，且忠实保留首文档场景。 |
| Δ3 | source 优先/fallback 固定 | 行为表述合格；design 实际漏了 Feishu history 路径，见 R1-C4。 |
| Δ4 | shadow 逐消息 actual ingress | 合格，与 current external-channel continuity 契约兼容。 |
| Δ5 | 群聊 sender/chat type | 合格，是模型消费者可观察结果。 |
| Δ6 | envelope 不污染 visible body | 合格，但 design 未解决 workspace 可读 copy，见 R1-W1。 |
| Δ7 | consumed steer 重启稳定 | THEN 直接要求“`transcript` 中恰好一次”，不是消费者可观察结果，见 R1-C5。 |
| Δ8 | 旧历史不补造 | 合格，忠实保留首文档。 |
| Δ9 | 非 PA 真人入口保持 | 契约表述合格；design 尚不能实现，见 R1-C1/R1-C2。 |

### milestone 核实台账

| Milestone | 拆分/范围 | 两轨退出判断 |
|---|---|---|
| feat-530-M1 | 以 normal/buffer/replay + prompt 为端到端切片，可独立产生用户价值；与 M2 顺序执行，不存在并行 worktree 冲突。多 M 由跨 10+ 文件和后续高风险 concurrency seam 举证，可接受。 | reviewer/worker 两轨齐全且可验；但 Prompt marker 边界和 background 不变的方案本身未成立，见 R1-C1/R1-C2。 |
| feat-530-M2 | 以 active-steer durability 为第二个端到端切片，依赖 M1 是合理的顺序关系，不是数据/业务/测试横切。 | reviewer/worker 两轨齐全；但 `transcript failure-before-LLM` 退出标准与 D7 描述的现有 Runtime 行为矛盾，见 R1-C3。 |

### 整体判断

- 人类上层：架构总览、Before/After、8 个结论和主时序能让读者快速抓住“Adapter 只解析、Pipeline 一次冻结、Coordinator 投影、Kernel 持久”的主线；不存在缺总览或上层被实现细节淹没的问题。
- 数据流：Web live 主路、Feishu live 主路、group buffer 和 normal submit 基本闭合；Feishu REST history source time、background PromptSlots 选择和 yielded steer 的 durable barrier 三处断裂分别见 R1-C4/R1-C2/R1-C3。
- 常规完整性：标题、对齐行、branch 声明、Changelog、风险与回退、常驻 Gateway runbook 都完整；无 TBD 或模板残留。
- 回退：“新 transcript bytes 保留为普通 user text”的回退判断合理，但不能替代实现时的 LLM-before-durable barrier。

### 架构进攻

| 角度 | 进攻结果 | 长期代价/证据 |
|---|---|---|
| 归属 | `PaHumanMessageContext` 放在 PA Gateway 正确；provider parse 归 Adapter、freeze 归 Pipeline、parts 归 Coordinator 也顺着现有依赖方向。但让 Core 识别 `pa.message_context` 是产品语义反向渗入内核。 | Core 会开始累积每个产品的 magic piece name 与 policy branch，破坏“内核眼里没有产品”的长期边界，见 `SPEC.md:113-124` 和 R1-C1。 |
| 该不该存在 | 冻结 object 有 group-buffer/restart/steer 三个消费者，删除它会迫使各分支重新取时钟，因此应存在；新数据库表/工厂/Protocol 均未预造。相反，Core 的 PA-specific marker helper 是为逃避边界契约而引入的隐藏间接层。 | helper 没有降低跨层复杂度，只是把应该明示对齐的 consumer capability 藏到字符串约定里，见 R1-C1。 |
| 深或浅 | PA module 的 `freeze/apply` 两动作隐藏了 source/fallback/timezone/format/sender/multimodal，是有效的 deep module；GroupContextStore 和 ordered parts 也被复用。但 D7 把“生成 Message”与“真正 durable”混成一个浅界面。 | Runtime 实际只把 tool yield 设为 durable；该浅界面会让单测看到内存 history 正确，崩溃恢复却丢 steer，见 R1-C3。 |
| 治本或补丁 | Pipeline 一次 freeze 是治本；用 Core 识别 PA name 同时修 footer 和 steer policy 则是绕过“产品如何诚实选择内核行为”的补丁。 | 下一个产品特例只能继续往 Core 加 name check，且 SDK 契约/预览/指纹行为无法独立说清，见 R1-C1。 |

### Issues

- [R1-C1][CRITICAL] [决策 6/7/8、契约层增量、架构归属/治本性]: 方案把 `PromptText(name="pa.message_context")` 设计成 Core 的隐藏 policy switch：它一方面改写 kernel-owned runtime footer，另一方面选择 consumed-steer persistence，却声称“不改 SDK 消费者契约、无 Kernel delta”。这与 `PromptText.name` 当前只用于 tracing/preview、内核不 re-gate 产品 slot 的公开语义相冲突（`src/agent/sdk/prompt.py:26-45,48-65`），也把 PA 产品知识反向注入了本应产品无关的 Core（`SPEC.md:113-124`；`docs/specs/kernel/prompts.md:14-30`）。不改，worker 会交付一个绕过正式边界的 magic-name 契约，以后每个产品特例都会在 Core 累积同类 branch；而且其他 SDK consumer 只要同名就会触发未公开行为。设计需先返回 spec 边界对齐：要么明确允许一个产品无关、可经 `agent.sdk` 说清的 capability 并写 Kernel delta，要么改变方案以不让 Core 解读 PA-specific name；不能用“private marker”把真实的跨边界契约隐藏起来。

- [R1-C2][CRITICAL] [决策 6、spec Q1/非目标 N1、M1]: 方案没有拍死 `pa.message_context` PromptText 何时出现。当前 `prompt_for()` 是所有 PA session 的共享组装器（`src/personal_assistant/product.py:291-356`），heartbeat/cron 也通过 `InProcessKernelClient -> project_agent_runtime -> prompt_for()` 创建或替换 runtime（`src/personal_assistant/gateway/kernel_client.py:54-106,133-169`），其 metadata 只有 `agent_id`（`src/personal_assistant/scheduler/heartbeat_scheduler.py:451-479`；`src/personal_assistant/scheduler/cron_runner.py:122-131`）；heartbeat 还可复用真人 direct chat 的 canonical session。D6 一处说 `prompt_for()` 加 marker，另一处又说 cron/heartbeat 不带 marker，但没有定义选择事实、生命周期和共享 session 重配置语义。不改，两个 worker 会产生两种不兼容实现：无条件加 marker 会删掉 heartbeat/cron 的现有 Current date，按自行猜测条件则可能让既有真人 session 或 active steer 没有 policy。设计必须明确哪个持久/入站事实选择该行为，以及真人与 background 共用 canonical session 时如何保证非目标。

- [R1-C3][CRITICAL] [决策 5/7、时间与历史判定、M2]: D7 的关键前提“AgentLoop `yield` user Message 后，Runtime 现有 consumer 立即写入 transcript，成功后才继续”不等于“在下一次 LLM 前 durable”。现有 Runtime 对 loop yield 的消息只在 `msg.role == "tool"` 时使用 `durable=True`，user role 仅排队，整个 loop 结束后才 `flush_async()`（`src/agent/core/agent/runtime.py:629-672`）；`JsonlWriter.enqueue_raw()` 是入内存队列即返回（`src/agent/core/session/jsonl_writer.py:27-55`），只有 durable barrier 才保证前序写入完成（`src/agent/core/session/transcript.py:473-495`）。因此 generator 会恢复并发起下一次 LLM，而持久失败可能直到这次 LLM 之后才被观察。不改，崩溃时模型已看到的 consumed steer 仍可从重启历史消失，直接违反 Requirement，且 M2 的 `transcript failure-before-LLM` 退出标准无法按 D7 实现。设计必须明确 Runtime 如何识别该 yield 并在恢复 AgentLoop 前完成 durable barrier，而不是依赖现有 non-durable append。

- [R1-C4][CRITICAL] [现状分析、决策 2、spec Q2/每条时间、M1]: 方案只枚举了 Feishu WebSocket live event，漏了真实生产中的群历史 catch-up。每次群触发前，Adapter 会通过 REST `fetch_group_messages()` 找回漏掉的普通真人消息，再以 `sync_only=True` 送入同一 Pipeline/buffer（`src/personal_assistant/channels/feishu/adapter.py:227-290`）。当前 `_parse_feishu_history_message()` 同样没有保留时间（`src/personal_assistant/channels/feishu/client.py:1141-1176`），而已锁定的 `lark-oapi 1.6.9` REST `Message` 明确提供 `create_time`（`.venv/lib/python3.12/site-packages/lark_oapi/api/im/v1/model/message.py:10-49`）。D2 只规定“读 `event.message.create_time`”，M1 Adapter tests 也只写了 `Feishu create_time`，worker 没有任何指令去扩展 REST parser。不改，群背景消息会把“触发时才被 catch-up 的 Gateway receipt”当成发生时间，即使 provider 已给出真实 source time，直接违反“每条真人消息 source 优先”。设计和 M1 范围/退出标准必须显式包含 live 与 REST history 两个 Feishu parser。

- [R1-C5][CRITICAL] [delta-spec `consumed active steer` Scenario]: `specs/gateway/routing-delivery.md:41-45` 的 THEN 直接要求“`transcript` 中该 user message 恰好一次”，这是内部存储机制而不是 Gateway 消费者可观察结果；首文档的对应场景要求的是“重启后 Agent 仍能依据原时间/入口理解先前消息”（`spec.md:112-123`）。不改，收尾归并会把 Gateway canonical spec 污染成对 Kernel 存储实现的断言；未来只要 transcript 实现替换，即使用户行为不变也会伪造 spec 违约。THEN 需改写为重启后 Agent/model 可观察的稳定历史行为，把 transcript exactly-once 留在 design 与 worker 测试层。

- [R1-W1][WARNING] [现状分析、决策 3/5、raw/model 分层]: 方案只核对了 IM、Feishu 和 shadow body，漏了 PA 另一个现有用户可读持久消费者：`chat_history` hook。Coordinator 把带 prefix 的 parts 交给 Kernel 后，Runtime 在 `input` hook 上报的就是 model-facing `user_text`（`src/agent/core/agent/runtime.py:430-471`）；PA hook 把该 text 原样写入 `<workspace>/.nanoassistant/chat_history/`（`src/personal_assistant/hooks/chat_history.py:70-76,94-120`），而 current spec 将它定义为供用户查看的简化聊天副本（`docs/specs/gateway/routing-delivery.md:323-334`）。不改，实施后 workspace 中的 user `content` 会显示 model envelope，与“只存在于模型上下文”的整体方向不一致；或者这会成为一个未写 delta 的用户可观察变化。设计需决定并写清是否保留 raw chat copy；若保留，必须给出不让 hook 抓到 decorated text 的边界；若有意改变，则需回到 spec 对齐且补 delta。

### Recommendations

- [R1-R1] 在修订 receipt-time 契约时，建议明确“Gateway 收到”是 Adapter/`InboundDispatcher.__call__` 的同步接受时点，还是 event-loop 上 `handle_inbound()` 开始时点；当前 Dispatcher 可跨线程排队（`src/personal_assistant/gateway/inbound_dispatcher.py:37-75`），两者在背压时不等价。
- [R1-R2] 修订后保留当前两 milestone 的端到端切分即可；无需因本轮 issue 再拆 M3。R1-C1–C3 应先在 design 层闭合，不要下沉给 M2 worker 边实施边猜。

## Author Resolution — Round 1

- [R1-C1] **Accepted.** 删除 `pa.message_context` magic-name policy。修订后的 D6 使用 Core product-neutral、default-off、非 UI 投影的 `per_message_time_context` complete-runtime policy；PromptText name只用于 tracing/preview。新增 `specs/kernel/prompts.md` 与 `specs/kernel/context-persistence.md`，同时保持 `src/agent/sdk/` 与公开方法/DTO不变。
- [R1-C2] **Accepted.** policy lifecycle拍死为“所有顶层 PA session projection固定为 true”，不按 human/heartbeat/cron origin切换；这样 heartbeat复用 canonical direct session时不会 reconfigure振荡。只有 Web/Feishu human inbound parts获得 envelope；background/subagent/internal message不获得。PA统一 timezone-only system prompt是 spec Q6，Coding CLI与 subagent不选择 policy。
- [R1-C3] **Accepted.** D7改为明确的 generator barrier：AgentLoop先 yield带 `consumed_pending_user` marker的 core Message，Runtime对该 Message调用 `transcript.append_messages(..., durable=True)`，成功后 generator才恢复、pending才加入 `llm_messages`。writer failure test必须证明下一次 provider call未发生。
- [R1-C4] **Accepted.** D2、主图、风险、runbook与 M1退出标准均显式纳入 Feishu WebSocket live parser和 REST history catch-up parser，两者共用 create-time normalization helper。
- [R1-C5] **Accepted.** Gateway delta改为 restart后 Agent/model仍按原 time/Channel理解、消息既不缺失也不重复；transcript exactly-once仅保留在 design/worker验证层。另增 Kernel persistence delta承载机制层保证。
- [R1-W1] **Accepted.** D5定义 PA chat-history hook的 v1 inverse projection：只对 selected policy + user origin去掉新增 header，保留 current `[sender]`/body/image placeholder。Gateway delta与 M1测试补充 readable-copy场景。
- [R1-R1] **Adopted.** receipt time owner改为 `InboundDispatcher.__call__()` 同步 acceptance、跨线程/loop排队之前；Pipeline不再晚取 fallback clock。
- [R1-R2] **Adopted.** 保留两个顺序 milestone，不增加 M3。

## Round 2

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: `closure → full`；R1 修订不只是措辞闭环，而是新增 Core complete-runtime policy、两个 Kernel delta，并改变共享 feature/持久化边界，命中核心边界与消费者契约的高风险变更条件。
- started_at: `2026-08-10T16:51:52+08:00`
- completed_at: `2026-08-10T16:57:48+08:00`
- duration: `5m56s`

### Verdict

Not Approved — 1 CRITICAL / 1 WARNING

### Coverage

- 完整重读最新 `spec.md`、`design.md`、Gateway/Kernel prompts/Kernel persistence 三份 delta-spec、两份 milestone 骨架，以及 Round 1 的全部 Issue 与 Author Resolution。
- 以 Round 1 的 S1–S39 为现状 inventory，重新从生产 wiring 核实 Web relay、Feishu live/REST history、Dispatcher、Pipeline、Coordinator、PA runtime projection、heartbeat/cron、subagent、Core feature resolution、AgentLoop/Runtime/JsonlWriter barrier 与 chat-history hook；没有继承作者的 closure 结论。
- 逐项重审最新 D1–D9、spec 的 Q1–Q8/U1–U4/五个 Requirements/七条非目标、三份 delta 的全部 Requirement/Scenario，以及 M1/M2 的依赖、范围和双轨退出标准。
- 对新增的 Core policy 与 PA inverse projection重新执行归属、必要性、深浅度、治本性四角度架构进攻。

### 现状断言核实台账

| ID | 本轮核实 | 独立证据与结论 |
|---|---|---|
| S1 | PA 共用入站对象当前无 occurrence/receipt | 成立；`InboundMessage` 仍只有 channel/text/routing/metadata/event identity，见 `src/personal_assistant/channels/base.py:23-46`。 |
| S2 | Web relay 已有 provider time、Adapter 未投影 | 成立；relay payload 已有 `created_at`，Web Adapter 当前仍只投影 body/id/metadata，见 `src/IM/application/relay_service.py:112-131`、`src/personal_assistant/channels/web_relay_adapter.py:246-297`。 |
| S3 | Feishu 有 live 与 REST history 两条真人 parser，均未保留时间 | 成立且修订已完整枚举；两个 parser 见 `src/personal_assistant/channels/feishu/client.py:1089-1176`，catch-up 生产调用见 `src/personal_assistant/channels/feishu/adapter.py:227-290`。 |
| S4 | Dispatcher 是同步 acceptance 边界 | 成立；seal 检查和 loop/thread task 创建都在同一 `__call__()` lock 内，见 `src/personal_assistant/gateway/inbound_dispatcher.py:37-75`。 |
| S5 | Pipeline 是 raw consumers 后、buffer/dispatch 前的共同 owner | 成立；route/gate/shadow 与分叉顺序见 `src/personal_assistant/gateway/inbound_pipeline.py:104-190`。 |
| S6 | Coordinator 的 normal/steer 共用 parts builder | 成立；两条 admission path 均到 `_build_message_parts()`，见 `src/personal_assistant/gateway/session_run_coordinator.py:232-241,873-885,1125-1167`。 |
| S7 | GroupContextStore 可原样 round-trip JSON metadata | 成立；现有 `metadata_json` append/drain 足够承载 frozen object，见 `src/personal_assistant/gateway/group_context_store.py:62-95,116-134`。 |
| S8 | chat-history hook 当前收到 flat model-facing text | 成立；Runtime input payload 只有 `text/images`，见 `src/agent/core/agent/runtime.py:390-449`；PA hook 原样捕获 `text`，见 `src/personal_assistant/hooks/chat_history.py:70-76,94-120`。 |
| S9 | Core footer 使用 session-created time | 成立；Runtime 将 created time交给 prompt context，footer 当前输出 datetime + cwd，见 `src/agent/core/agent/runtime.py:509-530`、`src/agent/core/agent/prompt_sections/core_sections.py:320-346`。 |
| S10 | normal user turn 已在模型前 durable | 成立；Runtime 在进入 loop 前 append `durable=True`，见 `src/agent/core/agent/runtime.py:546-565`。 |
| S11 | 两个 pending consume 点当前直接加入 LLM context | 成立；round-boundary 与 terminal-window 分别见 `src/agent/core/agent/loop.py:364-376,591-624`。 |
| S12 | Runtime 是 loop yield 的 transcript owner | 成立；async-for 每次 yield 后 append history/transcript，见 `src/agent/core/agent/runtime.py:629-672`。 |
| S13 | durable barrier 是真实写入屏障，不是 enqueue | 成立；enqueue 立即返回，而 `durable_barrier()` 等待 FIFO writer，见 `src/agent/core/session/jsonl_writer.py:27-55,73-93`、`src/agent/core/session/transcript.py:473-495`。 |
| S14 | complete runtime features 经 SDK-owned config 持久化和 fingerprint | 成立；`SessionRuntimeConfig.features`、identity 与 metadata 编码见 `src/agent/sdk/runtime.py:17-35,63-105`。 |
| S15 | Core 只解析 registry 中的 feature key | 成立；未知 key 被丢弃，见 `src/agent/core/agent/prompt_sections/wiring.py:120-153`。 |
| S16 | `list_features()` 是公开能力查询且当前只列两项 | 成立；见 `src/agent/sdk/kernel.py:1855-1884`；canonical 要求查询与已装配能力一致，见 `docs/specs/kernel/sdk-boundary.md:120-125`。 |
| S17 | PA 顶层 runtime 都经共享 projection | 成立；human/heartbeat/cron 的生产调用分别落到 `project_agent_runtime()`，见 `src/personal_assistant/gateway/session_run_coordinator.py:1198-1224`、`src/personal_assistant/gateway/kernel_client.py:54-106,133-169`。 |
| S18 | heartbeat 可对齐/复用 canonical session | 成立；因此 policy 按 top-level session固定而非按 origin切换是必要的，生产入口见 `src/personal_assistant/scheduler/heartbeat_scheduler.py:446-500`。 |
| S19 | subagent 不继承父 runtime features | 成立；创建 child 只传 skills、tool allowlist、自己的 prompt seed和 metadata，见 `src/agent/platform/tools/builtins/agent.py:646-703`。 |
| S20 | PromptSlots name 当前不选择 Core policy | 成立；现行 prompt contract 只承诺四槽装配，见 `docs/specs/kernel/prompts.md:14-49`。 |
| S21 | sender 是 Coordinator 的独立 projection | 成立；`_prefix_sender_parts()` 只修改 copied parts，见 `src/personal_assistant/gateway/session_run_coordinator.py:1744-1759`。 |
| S22 | multimodal input 会形成 text fallback + structured parts | 成立；见 `src/agent/core/agent/state.py:33-125`。 |
| S23 | pending LLM message可反投影为 canonical input parts | 成立；string/list 两形态已有恢复 helper，见 `src/agent/core/runs/registry.py:915-921`。 |
| S24 | actual ingress 可由 `channel_name` 决定 | 成立；Web/Feishu adapter name 分别是固定 `web_relay` 与 `feishu:<agent_id>`，现行路由不需读取 shadow 固定来源。 |
| S25 | IM/shadow raw body 与 model parts 已分层 | 成立；shadow 在 Coordinator装饰前消费 raw `InboundMessage.text`，见 `src/personal_assistant/gateway/inbound_pipeline.py:134-152`。 |
| S26 | group buffer/replay 可保存固定 header且旧 row可缺 marker | 成立；JSON metadata 有自然版本边界，不要求迁表或猜测回填。 |
| S27 | startup timezone snapshot 没有现成 PA user-timezone配置可复用 | 成立；现有 timezone 配置只服务 heartbeat active hours，本期使用 Gateway本地时区与个人部署拓扑相容。 |
| S28 | stable PromptSlots 与 volatile user tail 的 cache seam存在 | 成立；固定 skeleton顺序见 `src/agent/core/agent/prompt_sections/skeleton.py:90-128`。 |
| S29 | PA 只能经 `agent.sdk` 调 Core | 成立且是硬边界，见 `SPEC.md:113-124,148-161`。 |
| S30 | SDK canonical 将 features定义为消费者的内核通用 feature开关 | 成立；见 `docs/specs/kernel/sdk-boundary.md:47-73`与 `src/agent/sdk/kernel.py:1100-1133`。这正是 R2-C1 的契约冲突证据。 |
| S31 | Kernel canonical 文档都是 SDK 消费者契约 | 成立；`docs/specs/kernel/{prompts,context-persistence,sdk-boundary}.md` 顶部均明确 CDC 边界，而非私有实现说明。 |
| S32 | workspace chat copy 是用户可读副本 | 成立；current requirement 见 `docs/specs/gateway/routing-delivery.md:323-334`。 |
| S33 | input hook flat text丢失原 part边界/生成 provenance | 成立；payload 不含 per-part metadata，见 `src/agent/core/agent/runtime.py:431-437`，这是 R2-W1 的可逆性边界。 |
| S34 | generator yield 可形成 Runtime-before-resume屏障 | 成立；Runtime 的 async-for body在下一次 `__anext__` 前完成，结合 durable writer可实现 D7 顺序。 |
| S35 | `pending_injection_consumed` 是真实 consume信号 | 成立；仅在 drain 后发送，见 `src/agent/core/agent/loop.py:364-376,617-624,764-792`。 |
| S36 | old transcript直接重放原 bytes | 成立；无需 admission-time重写，符合 append-only兼容。 |
| S37 | Gateway常驻服务 review需真实 IM/Feishu前置 | 成立；本轮 runbook给出 worktree启动/停止/health和真实 Feishu profile，未依赖 test-only实现。 |
| S38 | 两个 milestone 会顺序改共享 session/Kernel seam | 成立；M2依赖M1且没有错误宣称并行，两目录骨架均存在。 |
| S39 | 上游 OpenClaw 仅是参考而非 current contract | 成立；本轮所有结论均回到本仓 spec与生产 wiring核实。 |

### 决策核实台账

| 决策 | 本轮判断 | 证据 / 影响 |
|---|---|---|
| D1 Dispatcher receipt + Pipeline freeze | 完整、无歧义；receipt在 seal 后、排队前固定，raw consumers结束后只 freeze一次。 | `design.md:95-111`；`inbound_dispatcher.py:37-75`、`inbound_pipeline.py:104-190`。 |
| D2 Web/Feishu occurrence normalization | 完整；live 与 REST history 共用 parser，DM/group均投影。 | `design.md:113-120`；两条 parser/生产 catch-up见 S3。 |
| D3 v1 header与parts顺序 | 完整；Channel、sender、image-only与从 raw重建均拍死。 | `design.md:122-134`；现行 sender/parts seam见 S21-S22。 |
| D4 startup timezone snapshot | 完整且有 spec驱动；fallback label、DST、restart语义均确定。 | `design.md:136-143`；spec Q2/Q6。 |
| D5 raw/frozen/readable/transcript分层 | 主路径闭合；chat-history仅有 flat text inverse，不能严格识别“每个生成 header”，见 R2-W1。 | `design.md:145-152`；S8/S32/S33。 |
| D6 product-neutral runtime policy | Core不再解释 PA name，产品中立性改善；但它通过公开 SDK complete-runtime features被消费者选择，又声称不改变 SDK消费者契约，见 R2-C1。 | `design.md:154-163`；S14-S16/S29-S31。 |
| D7 consumed steer durable barrier | 完整且可实施；yield → Runtime durable append → generator resume → LLM append/call顺序明确覆盖两个 drain点。 | `design.md:165-183`；S11-S13/S23/S34-S35。 |
| D8 append-only/cache/rollback | 自洽；只追加新 user tail、旧 bytes不迁移、rollback保留普通 user text。 | `design.md:185-195`；S26/S28/S36。 |
| D9 不增 SDK/IM schema/DB/tool | IM/DB/tool成立；“不改变 SDK consumer contract”与 D6/Kernel delta冲突，见 R2-C1。 | `design.md:197-202`；spec N3。 |

### spec 约束对账

#### 澄清、用户场景与非目标

| 原子 | 核实 |
|---|---|
| Q1 仅 PA真人入站、其余消息不变、SDK不扩张 | human envelope与background/subagent隔离已闭合；SDK消费者契约仍冲突，见 R2-C1。 |
| Q2 source优先/receipt fallback/PA时区 | D1/D2/D4完整覆盖，含 Feishu REST catch-up。 |
| Q3 只加平台、不加Direct/Group/内部ID | D3与Gateway delta完整覆盖。 |
| Q4 actual ingress逐消息决定 | D1/D3按 `channel_name`固定，覆盖 shadow跨入口。 |
| Q5 envelope只进模型、visible body不变 | IM/Feishu/shadow闭合；workspace readable copy有损 inverse风险见 R2-W1。 |
| Q6 PA system prompt timezone-only、其他产品不变 | top-level PA固定policy、CLI/subagent默认off覆盖；选择手段的SDK契约冲突见 R2-C1。 |
| Q7 新消息稳定、旧消息不补造 | D5/D7/D8与Gateway/Kernel persistence delta覆盖。 |
| Q8 不增精确时间工具 | D9完整覆盖。 |
| U1 长会话跨早晚 | 每条固定 occurrence + timezone-only footer覆盖。 |
| U2 shadow中Feishu/Web IM逐消息区分 | Gateway delta对应 Scenario覆盖。 |
| U3 群 sender与visible raw体验 | sender/raw主路覆盖；readable copy例外见 R2-W1。 |
| U4 restart/old-history/non-target稳定 | normal/buffer/consumed steer与default-off路径均覆盖。 |
| N1 不改CLI/background/subagent/internal消息 | envelope与steer persistence均按 USER+selected gate；subagent不继承。 |
| N2 不增`session_status` | 满足。 |
| N3 不新增/改变SDK公共能力与消费者契约 | 不满足；D6与两个Kernel delta新增可经SDK features选择的行为，见 R2-C1。 |
| N4 不加Direct/Group/internal IDs | 满足。 |
| N5 不引入其他OpenClaw prefix | 满足。 |
| N6 不改Web/Feishu/shadow展示复制搜索 | raw path满足。 |
| N7 旧消息不补造 | 满足。 |

#### Requirements / Scenarios

| Requirement / Scenario | 本轮核实 |
|---|---|
| 每条真人消息发生时间 / 跨多个时段 | D1-D5与Gateway delta长会话场景覆盖。 |
| 每条真人消息发生时间 / source time优先 | Web ISO、Feishu live+REST均明确投影并在M1测试。 |
| 每条真人消息发生时间 / receipt fallback | Dispatcher同步accepted时固定，queue/backpressure不污染。 |
| 实际入口 / shadow跨入口 | `channel_name`逐消息冻结，不读shadow固定属性。 |
| 实际入口 / 群参与者 | header后保留既有sender；不重复chat type。 |
| 实际入口 / 私聊稀疏平台 | v1只输出Web IM/Feishu。 |
| envelope不改原文 / 原入口查看复制 | IM/Feishu body始终走raw path。 |
| envelope不改原文 / shadow同步搜索 | shadow在model projection前消费raw body。 |
| 稳定延续 / Gateway重启 | normal/group保存最终bytes，consumed steer先durable再进下一模型请求。 |
| 稳定延续 / 旧消息 | 缺marker保持原bytes，之后新消息才freeze。 |
| 非PA / Coding CLI | default-off且M1/M2均有CLI regression。 |
| 非PA / heartbeat/cron/subagent/internal | message不装envelope；top-level PA仅统一timezone footer；subagent独立runtime。 |

### delta-spec 核实台账

| ID | 条目 | 本轮判断 |
|---|---|---|
| GΔ1 | Gateway ADDED Requirement target | `routing-delivery.md` 是最窄target，新增行为与current route/buffer/steer并行，ADDED正确。 |
| GΔ2 | 长会话各自时间 | 消费者可观察且忠实spec。 |
| GΔ3 | source优先/receipt一次固定 | 已把receipt owner钉在Gateway同步接受，合格。 |
| GΔ4 | Feishu history catch-up | 明确要求provider create time，R1-C4关闭。 |
| GΔ5 | shadow actual ingress | 合格。 |
| GΔ6 | sender与chat type | 合格。 |
| GΔ7 | visible body raw | 合格。 |
| GΔ8 | workspace readable copy | 消费者结果写对；design inverse不严格可逆，见 R2-W1。 |
| GΔ9 | consumed steer restart | 已改为Agent/model可观察且不缺不重，R1-C5关闭。 |
| GΔ10 | old history | 合格。 |
| GΔ11 | 非PA/default behavior | 行为目标合格；SDK policy选择的契约归属冲突见 R2-C1。 |
| PΔ1 | Kernel prompts ADDED Requirement | 消费者可观察；但它实质改变 complete-runtime `features`的可选语义，并与current“feature只含配内置工具通用项”及SDK capability query相交，不能仅以ADDED且no SDK delta收尾，见 R2-C1。 |
| PΔ2 | selected时省略created time | consumer-visible、product-neutral表述合格。 |
| PΔ3 | unselected bytes不变 | 合格。 |
| PΔ4 | PromptText name不选policy | 合格，关闭magic-name边界。 |
| CΔ1 | Kernel persistence ADDED Requirement | durable-before-next-model是SDK consumer可观察新行为；机制表述对准Kernel消费者，但同样触发R2-C1的SDK契约冲突。 |
| CΔ2 | consumed先durable | 可观察且D7可实施。 |
| CΔ3 | FIFO/restart不缺不重 | 合格。 |
| CΔ4 | accepted未consumed/park | 合格。 |
| CΔ5 | default/non-USER不变 | 合格。 |
| ΔN | IM/CLI无delta | body/schema与CLI行为确实不变；合理。 |
| ΔSDK | SDK no-delta | 不成立；新recognized feature key被公开SDK runtime承载、持久返回并改变Core行为，且Kernel canonical本身声明为SDK消费者契约，见 R2-C1。 |

### milestone 核实台账

| Milestone | 拆分/范围 | 两轨退出判断 |
|---|---|---|
| feat-530-M1 | normal/buffer/replay + prompt/cache/readable-copy是可观察垂直切片；显式含Web、Feishu live+REST、Dispatcher、PA projection、Core registry/footer与hook。 | reviewer/worker两轨齐全，包含真实Feishu catch-up、human/heartbeat fingerprint不振荡、CLI bytes与inverse regression；但policy contract须先解决R2-C1。 |
| feat-530-M2 | active-steer durability是独立高风险并发/持久化seam，依赖M1且顺序执行；无并行范围冲突。 | reviewer/worker两轨齐全，两个drain helper、FIFO/parent/image/park/default-off、writer failure-before-provider及reopen integration都可验。保留两个M的举证充分。 |

### 整体判断

- 上层表达清楚：总览、Before/After、主图、九项决策和时序足以让人抓住 Adapter normalization → Dispatcher receipt → Pipeline freeze → Coordinator projection → Kernel durability。
- 主数据流已闭合：Web、Feishu live、Feishu REST history、group buffer、normal submit、active steer、restart与old-data fallback均有唯一 owner。
- top-level PA与subagent生命周期已闭合：human/heartbeat/cron projection固定policy避免canonical session振荡，而subagent创建不复制features；只有human parts获得envelope。
- D7屏障顺序可实施：async generator在yield后停住，Runtime可先同步 durable append，成功后恢复generator；两处drain均在加入`llm_messages`前走同一helper。
- 常规完整性合格：标题、对齐、branch、Changelog、风险/回退、真实服务runbook和两个空milestone骨架均符合流程，无TBD或模板残留。

### 架构进攻

| 角度 | 进攻结果 | 长期代价 / 证据 |
|---|---|---|
| 归属 | source parse归Adapter、receipt归Dispatcher、freeze/inverse归PA module、durability归Runtime/Core都自然；Core policy也已去除PA知识。但把它定义成SDK runtime features可选语义后又称“非消费者契约”，归属声明未对齐。 | 不先对齐会让worker改Core与Kernel canonical，却让SDK canonical/list_features继续否认该能力，形成同一边界两套事实；见R2-C1。 |
| 该不该存在 | `PaHumanMessageContext` 有freeze、buffer/replay、parts、readable-copy多个真实消费者，删除会重复格式与时钟选择，模块有存在价值；没有多造表、工厂或Protocol。 | 未发现YAGNI阻断项。 |
| 深还是浅 | freeze/apply封装隐藏source/fallback/timezone/format/multimodal，接口比实现窄；但仅凭flat string的`strip_v1_headers_for_readable_copy(model_text)`无法保存生成 provenance，是有损浅“逆投影”。 | 有效用户正文行若长得像v1 header会被误删，长期每次格式升级都要继续靠脆弱文本识别；见R2-W1。 |
| 治本还是补丁 | durable consume helper与product-neutral policy本身都在根 owner处解决问题；但用“现有dict所以不算新契约”绕过N3/SDK canonical对齐仍是文档层补丁。 | 收尾时Kernel delta会合入消费者契约，而SDK delta仍声称无变化，归档后事实不可同时成立；见R2-C1。 |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | magic PromptText改为product-neutral runtime policy并补Kernel delta | PA magic name与Core反向依赖已消除；但公开SDK features新增recognized语义与N3/no SDK delta仍冲突。 | partial → R2-C1 |
| R1-C2 | 所有top-level PA固定policy；仅human parts装envelope；subagent不继承 | 三条PA production projection共用相同runtime，heartbeat复用canonical session不会origin振荡；subagent创建确实不复制features。 | closed |
| R1-C3 | yield marker后Runtime `durable=True`，成功才resume | async-generator控制流与writer barrier支持该顺序；D7明确两个drain共用helper并有failure-before-provider测试。 | closed |
| R1-C4 | Feishu live与REST history共用time parser | D2、主图、Gateway delta、风险、runbook及M1均显式覆盖生产catch-up。 | closed |
| R1-C5 | Gateway delta改消费者行为，Kernel delta写机制 | Gateway THEN已改成restart后Agent/model不缺不重；internal transcript断言留在design/test。 | closed |
| R1-W1 | selected user input做v1 inverse | hook条件可由`run_origin`+session features判断，但flat text没有generated-header provenance，严格可逆性未闭合。 | partial → R2-W1 |
| R1-R1 | receipt owner采用Dispatcher同步acceptance | D1与Gateway delta均明确在seal通过后、task/thread queue前固定。 | adopted / verified |
| R1-R2 | 保留两个顺序milestone | M1/M2垂直价值、依赖和双轨退出仍合理。 | adopted / verified |

### Issues

- [R2-C1][CRITICAL] [spec N3、决策 6/9、Kernel delta、SDK no-delta]: `per_message_time_context` 已经不是私有实现细节：设计要求 PA 通过公开 SDK-owned `SessionRuntimeConfig.features` 选择它，该 key 被持久化、参与 fingerprint、可由 `get_session_runtime()` 返回，并让 Core 的 prompt与active-steer persistence产生新行为（`design.md:154-180`；`src/agent/sdk/runtime.py:17-35,63-105`）。两份新增 Kernel canonical又明确把它写成“消费者在完整运行配置中选择”的对外契约，而这些 canonical自身声明只记录经`agent.sdk`依赖的CDC行为。与此同时，spec N3仍禁止新增/改变SDK公共能力与消费者契约（`spec.md:144-148`），design D9仍宣称no SDK delta，current SDK canonical/实现还把features描述为内核通用feature并让`list_features()`只报告`memory_curation`/`skill_creation`（`docs/specs/kernel/sdk-boundary.md:47-73,120-125`；`src/agent/sdk/kernel.py:1114-1133,1855-1884`）；current prompt canonical甚至说内核feature只含“配内核内置工具”的通用项（`docs/specs/kernel/prompts.md:14-21`），新无工具policy却只写ADDED而没有处理这条既有约束。不改，下游worker会按design新增一个真实可选择的SDK语义，收尾却必须同时归并“SDK消费者契约未变”和两条新消费者契约，canonical无法自洽，`list_features()`也会与已装配能力不一致。需先回到spec/契约边界拍板：若接受product-neutral SDK runtime capability，就明确修订N3并补齐/正确MODIFY SDK与prompt canonical（以及是否discoverable）；若N3必须保持，则设计必须给出不经公开SDK consumer features增加语义的PA内方案。不能以“不改`src/agent/sdk/`文件或字段”代替“消费者契约未改变”。

- [R2-W1][WARNING] [决策 5、Interface表、Gateway delta readable-copy]: `strip_v1_headers_for_readable_copy(model_text)` 只有一段flat text，拿不到每个input part的边界或 `_pa_human_message_context` provenance。现行Runtime把所有text/image placeholder先用换行连接，再给input hook只传`{"text", "images"}`（`src/agent/core/agent/runtime.py:390-437`），PA hook也只保存该字符串（`src/personal_assistant/hooks/chat_history.py:70-76`）。因此“去掉每个生成header”只能按文本模式猜：若用户正文某一行本来就以合法 `[Feishu Mon 2026-08-10 09:18 CST]` / `[Web IM ...]` 开头，它与buffer中下一条真正生成的header在flat text里不可区分，inverse会误删用户原文，违反delta对workspace readable copy保持既有正文的要求。不改，M1常规happy-path测试会绿，但合法用户内容在简化副本中发生静默数据损失。设计需把可读raw投影或生成header的位置/provenance带到hook owner，或选择另一个可严格恢复raw readable semantics的边界；不能把无 provenance的regex称为inverse。

### Recommendations

- [R2-R1] 保留当前M1/M2拆分；修订应只解决R2-C1的契约归属与R2-W1的可逆投影边界，不需要新增M3。

## Author Resolution — Round 2

- [R2-C1] **Accepted with explicit boundary correction.** 不再声称 `per_message_time_context` 是非消费者契约。`spec.md` 增加“设计阶段边界裁决”，将 N3收窄为“不新增 SDK方法/DTO/参数/PA-specific API”，明确允许复用 complete-runtime features新增一个 product-neutral能力；设计将其改为 `Kernel.list_features()`可发现、default-off、`requires_tool=None`。新增 `specs/kernel/sdk-boundary.md`，并在 prompt delta中 MODIFIED现有“feature只配内置工具”的冲突 requirement。M1明确包含 `agent/sdk/kernel.py::list_features()` 这一个 SDK implementation触点与 capability contract test。该必要例外将由用户做最终 design review。
- [R2-W1] **Accepted.** 删除 flat-text `strip_v1_headers_for_readable_copy`。Coordinator从同一 raw/parts source同时产生 exact model/readable projection，并在 `submit/try_steer`前写入 composition-owned `ReadableInputProjectionStore`。chat-history hook只在 session + FIFO staged model payload能完整 exact-match时取 readable projection；无 match沿用 payload，绝不解析 header grammar。tentative accept/reject、same-run consumed retire、held/auto-continuation后续 input、用户原文形似 header均写入 interface、风险与 M1退出测试。
- [R2-R1] **Adopted.** 保留现有 M1/M2，不增加 M3。

## Round 3

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: `closure → full`；本轮修订改变了 spec 的设计阶段边界/非目标，新增 SDK shared-contract delta，并用跨线程 provenance store替换原字符串 inverse，命中需求边界、共享契约与数据流高风险变化条件。
- started_at: `2026-08-10T17:10:17+08:00`
- completed_at: `2026-08-10T17:15:14+08:00`
- duration: `4m57s`

### Verdict

Not Approved — 2 CRITICAL / 0 WARNING

### Coverage

- 完整重读最新 `spec.md`、`design.md`、Gateway delta、Kernel prompts/context/sdk-boundary 三份 delta、两份 milestone骨架，以及 Round 2 Issues/Author Resolution。
- 重新从 current canonical与生产 wiring核实 `SessionRuntimeConfig.features` / `FeatureInfo` / `Kernel.list_features()`、Prompt feature requirement、Coordinator normal/try-steer、Core held/auto-continuation、`pending_injection_consumed`、durable writer failure、input hook与chat-history写入顺序。
- 全量重跑 Round 2 S1–S39现状 inventory、D1–D9、spec Q1–Q8/U1–U4/全部 Scenario/非目标、四份 delta与M1/M2；重新执行四角度架构进攻。

### 现状断言核实台账

| ID | 本轮独立核实 |
|---|---|
| S1 | `InboundMessage` current仍无source/receipt字段，见 `src/personal_assistant/channels/base.py:23-46`。 |
| S2 | Web relay已发`created_at`而Adapter未投影，见 `src/IM/application/relay_service.py:112-131`、`web_relay_adapter.py:246-297`。 |
| S3 | Feishu live/REST parser与真实catch-up两路仍成立，见 `feishu/client.py:1089-1176`、`feishu/adapter.py:227-290`。 |
| S4 | Dispatcher seal后、task/thread queue前是同步receipt owner，见 `inbound_dispatcher.py:37-75`。 |
| S5 | Pipeline仍是raw consumer结束后、buffer/dispatch前唯一freeze seam，见 `inbound_pipeline.py:104-190`。 |
| S6 | Coordinator normal/try-steer共用parts builder，见 `session_run_coordinator.py:206-277,820-884,1125-1167`。 |
| S7 | GroupContextStore仍可JSON round-trip frozen metadata，无需新表。 |
| S8 | chat-history仍只收到flat `payload.text`，见 `agent/core/agent/runtime.py:390-449`、`hooks/chat_history.py:70-76`。 |
| S9 | Core footer仍输出session-created datetime + cwd。 |
| S10 | normal user turn仍在loop前`durable=True`。 |
| S11 | pending仍有round-boundary与terminal-window两个consume点，见 `agent/core/agent/loop.py:364-376,591-624`。 |
| S12 | Runtime仍是loop yield的唯一history/transcript owner，见 `agent/core/agent/runtime.py:629-672`。 |
| S13 | writer enqueue非durable，barrier才等待真实写入，见 `jsonl_writer.py:27-55,73-93`、`transcript.py:473-495`。 |
| S14 | public `SessionRuntimeConfig.features`仍持久化、返回并参与fingerprint，见 `agent/sdk/runtime.py:17-35,63-105`。 |
| S15 | Core仍只接受feature registry已知key，未知key会被丢弃，见 `prompt_sections/wiring.py:120-153`。 |
| S16 | current `list_features()`固定只投影两项，见 `agent/sdk/kernel.py:1855-1884`；本unit必须改该生产方法。 |
| S17 | human/heartbeat/cron仍共享PA runtime projection路径，policy固定可避免canonical session振荡。 |
| S18 | heartbeat仍可复用direct canonical session，按top-level固定policy是正确生命周期。 |
| S19 | subagent创建仍不复制parent features，见 `agent/platform/tools/builtins/agent.py:646-703`。 |
| S20 | PromptText name在current contract仍只属于四槽内容，不选择Core policy。 |
| S21 | `[sender]`仍由Coordinator独立projection，见 `session_run_coordinator.py:1744-1759`。 |
| S22 | Core fallback仍将parts按换行连接并给image生成`[image:placeholder]`，见 `agent/core/agent/state.py:33-125`。 |
| S23 | pending LLM string/list仍可恢复成submit parts，见 `agent/core/runs/registry.py:915-920`。 |
| S24 | `channel_name`仍是actual ingress可用事实；无需shadow固定source。 |
| S25 | IM/shadow raw body在Coordinator装饰前消费，raw/model分层成立。 |
| S26 | buffer/replay可保存固定header且旧row自然缺marker。 |
| S27 | 没有更合适的PA用户timezone配置可直接复用，startup snapshot前提未变。 |
| S28 | prompt skeleton的stable slot/user-tail cache seam未变。 |
| S29 | PA只能import `agent.sdk`仍是硬边界，见 `SPEC.md:113-124,148-161`。 |
| S30 | SDK canonical允许消费者经既有features map选择通用feature；新增通用policy可落在同一surface。 |
| S31 | Kernel canonical仍是SDK消费者CDC文档，因此本轮诚实补SDK delta是必要的。 |
| S32 | workspace chat history仍是current用户可读副本，见 `docs/specs/gateway/routing-delivery.md:323-334`。 |
| S33 | current input hook不携带parts provenance；外部store确是避免Core hook contract扩张的可用桥。 |
| S34 | async generator yield仍能形成Runtime append-before-resume屏障。 |
| S35 | `pending_injection_consumed`仍只在pending加入LLM context后发送；D7修订后它更晚于durable barrier。 |
| S36 | old transcript仍按原bytes重放，不经过admission。 |
| S37 | worktree Gateway/真实Feishu runbook仍对准生产wiring。 |
| S38 | M1/M2仍顺序执行；M2会改变M1 provenance store所依赖的consume/failure时序，见R3-C2。 |
| S39 | OpenClaw仍只是参考，本轮结论全部回到本仓current契约/代码。 |

### 决策核实台账

| 决策 | 本轮判断 |
|---|---|
| D1 receipt/freeze | 完整且production seam正确。 |
| D2 provider time | Web、Feishu live与REST history均闭合。 |
| D3 v1 header | Channel/sender/multimodal/raw rebuild均拍死。 |
| D4 timezone snapshot | 完整、稳定且无额外配置扩张。 |
| D5 readable provenance | exact-match/no-regex方向正确，normal/group/reject/held/auto-continuation happy path可实施；但durable failure-before-consumed signal会留下无法退休的accepted record，见R3-C2。 |
| D6 discoverable policy | 已诚实改为public product-neutral feature，default-off/`requires_tool=None`/PA顶层选择/CLI-subagent不选均明确。 |
| D7 durable consumed steer | yield → Runtime durable → resume → consumed event顺序可实施；该顺序与D5的failure lifecycle未闭合，见R3-C2。 |
| D8 append-only/cache | 自洽且未受本轮修订破坏。 |
| D9 SDK单项扩张 | 方法/DTO/参数不增、`list_features()`语义扩张已诚实；SDK MODIFIED delta漏保留current Scenario，见R3-C1。 |

### spec 约束对账

#### 澄清、用户场景与非目标

| 原子 | 本轮核实 |
|---|---|
| Q1 | human-only envelope保持；SDK例外不再伪装为零变化，已单列为待用户final review的边界裁决。 |
| Q2 | source优先/receipt fallback/timezone完整。 |
| Q3 | 只表达平台且保留sender。 |
| Q4 | actual ingress逐消息固定。 |
| Q5 | visible body与shadow raw；readable副本exact provenance目标正确，但failure lifecycle见R3-C2。 |
| Q6 | PA top-level timezone-only，CLI/subagent default-off。 |
| Q7 | new history稳定/old history不补造。 |
| Q8 | 无时间查询工具。 |
| U1 | 长会话跨时段由逐消息time + stable timezone覆盖。 |
| U2 | shadow跨Feishu/Web IM由actual `channel_name`覆盖。 |
| U3 | sender/原文体验覆盖；provenance failure例外见R3-C2。 |
| U4 | restart/old history/non-target行为覆盖。 |
| N1 | CLI/background/subagent/internal message不装envelope。 |
| N2 | 不增`session_status`。 |
| N3 | 已收窄为不增SDK方法/DTO/参数/PA-specific API，并显式豁免一项通用feature能力；文档诚实但最终需求边界仍由用户拍板，本Gate不代批。 |
| N4 | 不加Direct/Group/internal IDs。 |
| N5 | 不引入其他OpenClaw prefix。 |
| N6 | Web/Feishu/shadow visible正文不变。 |
| N7 | 旧消息不补造。 |

#### Requirements / Scenarios

| Scenario | 本轮核实 |
|---|---|
| 长会话多时段 | D1-D6覆盖。 |
| Channel source time | Web/Feishu live+REST覆盖。 |
| 无source时receipt | Dispatcher同步acceptance覆盖。 |
| shadow跨入口 | actual-ingress覆盖。 |
| 群参与者 | header + existing sender覆盖。 |
| 私聊稀疏来源 | 只输出平台覆盖。 |
| 原入口查看复制 | raw body path覆盖。 |
| shadow同步搜索 | raw shadow path覆盖。 |
| Gateway restart | normal/group/consumed durable history覆盖。 |
| old history | marker缺失保持原样。 |
| Coding CLI | feature default-off与CLI regression覆盖。 |
| heartbeat/cron/subagent/internal | message无envelope；top-level PA仅prompt timezone policy固定。 |

### delta-spec 核实台账

| Delta原子 | 本轮判断 |
|---|---|
| Gateway ADDED Requirement | target最窄且ADDED用法正确。 |
| 长会话各自时间 | 可观察且忠实spec。 |
| source/receipt | 可观察且owner精确。 |
| Feishu history catch-up | 生产路径完整。 |
| shadow actual ingress | 合格。 |
| sender/chat type | 合格。 |
| visible body | 合格。 |
| workspace readable copy | THEN正确；design failure lifecycle见R3-C2。 |
| consumed steer restart | consumer-visible且机制下沉Kernel delta。 |
| old history | 合格。 |
| non-PA/default | 合格。 |
| Kernel prompts ADDED Requirement | product-neutral footer语义与default bytes完整。 |
| prompts: selected footer | 合格。 |
| prompts: unselected bytes | 合格。 |
| prompts: PromptText name | 合格。 |
| prompts MODIFIED Requirement | 正确MODIFY current feature Requirement，并保留/改写原tool-gated与product-prompt两个Scenario，新增no-tool policy Scenario。 |
| Kernel context ADDED Requirement | target/ADDED用法正确。 |
| context: durable-before-model | 合格。 |
| context: FIFO/restart | 合格。 |
| context: accept-not-consumed | 合格。 |
| context: default/non-USER | 合格。 |
| SDK MODIFIED Requirement | 修改target正确，新增feature discoverability正确；但漏掉current `无真实 workspace 时只查询共享 Skill` Scenario，见R3-C1。 |
| SDK: capability一致 | 合格。 |
| SDK: policy discoverable/default-off/no-tool | 合格。 |
| SDK: skill_view | 忠实保留。 |
| SDK: shared roots ordering | 忠实保留。 |
| SDK: no-real-workspace shared skills | 未保留，见R3-C1。 |
| IM/CLI no delta | 合理。 |

### milestone 核实台账

| Milestone | 本轮判断 |
|---|---|
| feat-530-M1 | 仍是normal/buffer/replay + prompt/readable-copy垂直切片；新增provenance module、SDK list_features与capability tests已入范围。tentative/reject/held/continuation/no-match/header-shaped raw覆盖充分，但未覆盖same-run consumed retire与normal submit synchronous failure rollback。 |
| feat-530-M2 | active-steer durability仍是合理的第二垂直切片；但它改变provenance retire信号相对writer failure的时序，范围/退出标准没有包含projection store或failure后的store状态，见R3-C2。 |

### 整体判断

- R2-C1的方向性问题已纠正：spec不再声称完全无SDK consumer变化，feature可发现/default-off/no-tool，prompt current冲突用MODIFIED处理，方法/DTO/参数不增。
- R2-W1的原始文本误删已治本：model/readable由同一source双投影，exact provenance/no-match fallback保证header-shaped raw不被猜测删除。
- 两项修订仍各有一个归并/失败边界缺口；它们会让canonical静默丢场景或让长驻provenance FIFO被失败记录污染，因此尚不能进入实施。
- 上层图、接口表、风险、runbook与两M总体仍清楚；没有模板残留或新的无关范围扩张。

### 架构进攻

| 角度 | 进攻结果 | 长期代价 / 证据 |
|---|---|---|
| 归属 | discoverable product-neutral policy归Core/SDK，PA选择与UI隐藏归PA；双投影/provenance归PA composition，都顺着依赖方向。 | 未发现PA反向import Core或Core猜产品。 |
| 该不该存在 | 删除`ReadableInputProjectionStore`只能回到有损regex、扩张Core hook payload或另造Gateway聊天记录写入路径；它有真实跨线程桥接价值，不是纯YAGNI。 | 但存在即必须拥有完整失败生命周期，见R3-C2。 |
| 深还是浅 | `MessagePartsProjection`集中sender/multimodal/model/readable差异，接口有效变窄；store的exact FIFO也比解析header更深。 | D7 barrier failure不发retire signal，暴露出store当前只封装happy-path状态机，见R3-C2。 |
| 治本还是补丁 | SDK边界由“隐藏key”改为公开通用feature是治本；provenance替代regex也是治本方向。 | SDK delta静默删current Scenario会制造归档债；store failure orphan会把一次已知测试故障变成后续所有chat copy的长期污染。 |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | 明确feature consumer能力例外，discoverable/default-off/no-tool，补SDK delta并MODIFY prompts | 边界裁决、feature语义与prompt MODIFIED均成立；SDK delta漏保留一个current Scenario，consumer delta仍不完整。 | partial → R3-C1 |
| R2-W1 | 双投影 + exact provenance store，覆盖tentative/held/continuation/header-shaped raw | 原始误删问题关闭；但same-run durable failure发生在retire signal前，留下无法归类的accepted FIFO record，且milestone未覆盖。 | partial → R3-C2 |
| R2-R1 | 保留M1/M2 | 两M拆分仍合理，不需要M3；需补跨M failure exit。 | adopted / verified |

### Issues

- [R3-C1][CRITICAL] [Kernel SDK delta、R2-C1 closure]: `specs/kernel/sdk-boundary.md` 对 current `Requirement: Kernel 提供单项中立能力查询` 做 MODIFIED 时，保留了 capability一致、`skill_view`、shared-root ordering，并新增了`per_message_time_context` Scenario，却静默漏掉 current canonical 的 `Scenario: 无真实 workspace 时只查询共享 Skill`（current `docs/specs/kernel/sdk-boundary.md:139-142`）。按MODIFIED归并，该Scenario会从canonical消失，等价于本unit无意删除既有`list_shared_skills()`消费者保证；这与feat-530无关，也没有spec驱动。不改，收尾会让R2-C1看似补齐SDK契约、实际同时回归另一项SDK能力。delta必须逐字义保留该Scenario。与此同时，M1不应再声称`agent/sdk/kernel.py::list_features()`是唯一SDK implementation/documentation触点而让public `FeatureInfo`说明继续写“only two general features”（`src/agent/sdk/dto.py:369-380`）；DTO结构无需改变，但相关public docstring/`list_features()`说明应随第三项能力校正。

- [R3-C2][CRITICAL] [决策 5/7、ReadableInputProjectionStore、M1/M2]: store把accepted steer的provenance留到`pending_injection_consumed`才退休；D7则明确先从Core pending queue drain并yield user Message，Runtime执行`durable=True`，成功恢复generator后才发送该consume event（`design.md:153-155,172-179`）。当M2刻意注入的writer failure发生时，generator不恢复、consume event永远不发，但pending已被`drain_pending()`取走，Core terminal settlement也看不到它，既不会held也不会auto-continuation。当前store record只有`session_id/model/readable`且方案没有另一条claimed/failure清理信号，于是该accepted record永久卡在FIFO头：后续normal input无法exact-match，会沿用decorated payload，workspace chat copy重新泄露header；偶然同payload还可能消费错误projection。M1退出标准没有same-run retire/normal-submit failure cleanup，M2范围和writer-failure测试也完全没检查store状态。不改，两个milestone可各自全绿却在明确要求测试的failure seam破坏R2-W1。设计必须拍死accepted record从tentative到committed/claimed/retired或held/continued的完整状态机：至少覆盖normal `submit()`同步失败rollback、try-steer accept/consume与commit竞态、durable barrier失败后的退休/转移，并把projection store的跨M failure断言放进M2；无需因此新增M3。

### Recommendations

- [R3-R1] 保留两个顺序milestone；R3-C1属于M1 contract完整性，R3-C2在M1定义store状态机、M2验证durable-failure交叉即可。

## Author Resolution — Round 3

- [R3-C1] **Accepted.** Kernel SDK MODIFIED delta逐字义补回 current `无真实 workspace 时只查询共享 Skill` scenario，避免归并时删除既有 `list_shared_skills()`保证。D6与M1同时纳入 `src/agent/sdk/dto.py::FeatureInfo` public docstring校正；DTO类型/字段不变，SDK implementation/documentation触点明确为 `list_features()`投影与该说明两处。
- [R3-C2] **Accepted.** D5补齐 PA provenance的 tentative/committed/claimed/retired-or-rejected状态机：normal submit同步失败rollback、input早于normal commit waiter、try-steer accept/reject与consume早于commit tombstone、same-run success retire、held/auto-continuation transfer均有明确归宿。D7不新增hook事件；barrier失败经既有 terminal `run_status.error` 返回稳定 code与本次 USER claim count，Coordinator从既有consumed index精确退休已 drain批次，未 claimed records继续留给held/continuation input。M2加入Core registry error mapping与跨M store断言：writer failure后provider未调用、claimed record已清除、后续normal readable copy不泄露header，未claimed record仍可exact消费。

## Round 4

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: `closure → full`；R3-C2的修订新增了跨 AgentLoop、Runtime、RunsRegistry terminal error、PA Coordinator与composition store的失败协议，并改变M1/M2交界，命中共享契约、跨模块接口、数据流和milestone范围的full条件。
- started_at: `2026-08-10T17:24:53+08:00`
- completed_at: `2026-08-10T17:28:25+08:00`
- duration: `3m32s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 完整重读最新`spec.md`、`design.md`、Gateway delta、Kernel prompts/context/sdk-boundary三份delta、Round 3及Author Resolution、M1/M2骨架。
- 从current canonical与生产wiring重跑Round 3的S1–S39、D1–D9、全部spec约束/Scenario、四份delta、两milestone及四角度架构进攻；重点重新追踪`try_steer → RunController FIFO drain → AgentLoop yield → Runtime durable append → generator resume/terminal error → Kernel.stream → Coordinator consumed index/store cleanup → registry terminal settlement`。
- 本Gate只判断设计文档是否可实施；spec中声明由用户最终拍板的SDK边界例外仍留给用户最终design review，本结论不代替该需求边界批准。

### 现状断言核实台账

| ID | 本轮独立核实 |
|---|---|
| S1 | `InboundMessage`仍是PA共同入站对象且无source/receipt字段，`src/personal_assistant/channels/base.py:23-46`支持D1/D2落点。 |
| S2 | Web relay仍提供`created_at`而Adapter未投影，`src/IM/application/relay_service.py:112-131`、`src/personal_assistant/channels/web_relay_adapter.py:246-297`成立。 |
| S3 | Feishu live与REST catch-up仍是两条生产解析路径，`src/personal_assistant/channels/feishu/client.py:1089-1176`、`adapter.py:227-290`成立。 |
| S4 | Dispatcher seal后、task/thread queue前仍是唯一同步receipt seam，`src/personal_assistant/gateway/inbound_dispatcher.py:37-75`。 |
| S5 | Pipeline仍在raw route/shadow后、buffer/dispatch前拥有共同freeze位置，`inbound_pipeline.py:104-190`。 |
| S6 | Coordinator normal/steer仍共用parts builder，生产入口为`session_run_coordinator.py:206-277,820-884,1125-1167`。 |
| S7 | GroupContextStore现有JSON metadata可承载frozen object，不需新表。 |
| S8 | chat-history input hook仍只见flat text，`agent/core/agent/runtime.py:391-449`、`personal_assistant/hooks/chat_history.py:70-76`；exact外部provenance仍有必要。 |
| S9 | Core footer当前仍渲染session-created datetime + cwd，D6需改真实路径。 |
| S10 | normal user turn仍由Runtime durable写入，D5不另造Gateway transcript owner。 |
| S11 | pending仍在round boundary与terminal window两处drain，`agent/core/agent/loop.py:364-376,591-624`；D7两点共用helper范围正确。 |
| S12 | Runtime仍是loop yield的唯一history/transcript owner，`agent/core/agent/runtime.py:629-672`。 |
| S13 | transcript `durable=True`仍等待JSONL writer barrier，writer failure会沿调用栈冒泡。 |
| S14 | `SessionRuntimeConfig.features`仍持久化并参与完整runtime identity；product-neutral policy可复用既有surface。 |
| S15 | Core flag resolution仍只接受registry已知key，`prompt_sections/wiring.py:118-153`；必须正式注册而不能隐藏key。 |
| S16 | `Kernel.list_features()`当前固定过滤两项，`agent/sdk/kernel.py:1855-1884`；M1列出的生产触点真实。 |
| S17 | PA human/heartbeat/cron仍共用顶层runtime projection，固定policy避免同一canonical session按origin振荡。 |
| S18 | heartbeat仍可复用direct canonical session，top-level policy与human-only envelope分离正确。 |
| S19 | 内置subagent有自己的session metadata/PromptSeed且不复制parent features。 |
| S20 | PromptText name仍只承载内容/追踪，不应选择Core runtime policy。 |
| S21 | `[sender]`仍由Coordinator独立投影，D3/D5可保留current群聊语义。 |
| S22 | Core parts fallback仍含既有image placeholder语义，model/readable双投影必须从同一parts source生成。 |
| S23 | held/continuation仍由pending message恢复submit parts，`agent/core/runs/registry.py:196-201,598-609,915-920`。 |
| S24 | `channel_name`仍是逐消息actual ingress，不需读取shadow固定source。 |
| S25 | IM/shadow在Coordinator装饰前消费raw body，visible/model分层成立。 |
| S26 | group row可持久frozen metadata；旧row无marker自然保持原样。 |
| S27 | PA无更精确的用户timezone配置可复用，startup snapshot边界未变。 |
| S28 | stable PromptSlots与append-only user tail仍是当前cache seam。 |
| S29 | PA只能import`agent.sdk`仍是硬边界；修订没有要求PA import Core。 |
| S30 | SDK current允许消费者通过complete-runtime `features` map选择Kernel通用feature。 |
| S31 | Kernel canonical是SDK consumer CDC，feature目录与terminal error消费者语义均须在delta可见；当前prompts/context/sdk三delta已分别覆盖。 |
| S32 | workspace chat history仍是用户可读副本，`docs/specs/gateway/routing-delivery.md:323-334`。 |
| S33 | current input hook不携带parts provenance，PA composition store仍是避免Core hook contract扩张的最窄桥。 |
| S34 | async generator yield会暂停AgentLoop；Runtime完成append后才请求下一项，D7 barrier顺序可实施。 |
| S35 | `pending_injection_consumed`只在drained items加入model context后发出，`loop.py:764-792`；成功退休信号顺序成立。 |
| S36 | old transcript按持久bytes重放且不经过admission，升级不需要迁移。 |
| S37 | runbook仍对准真实worktree Gateway + Feishu/Web生产wiring。 |
| S38 | M1定义store、M2接入durable consume/failure协议；两M顺序边界与新增跨M测试一致。 |
| S39 | OpenClaw仅是参考；本轮判断均锚定本仓spec/code。 |

### 决策核实台账

| 决策 | 本轮判断 |
|---|---|
| D1 receipt/freeze | owner、时点、raw不变均完整。 |
| D2 provider occurrence | Web、Feishu live/REST、无效fallback完整。 |
| D3 v1 header | Channel/sender/multimodal/幂等边界完整。 |
| D4 timezone | startup snapshot、DST/fixed-offset、重启生效完整。 |
| D5 readable provenance | 修订已闭合tentative→commit/reject、normal early-hook waiter、try-steer early-resolution tombstone、success retire、held/continuation exact resolve及durable failure retire；无regex、无TTL、no-match保持原文。 |
| D6 product-neutral policy | discoverable、default-off、`requires_tool=None`、PA顶层固定选择、CLI/subagent不选、无PA-specific Core判断均明确。 |
| D7 durable consumed steer | `yield → Runtime durable=True → resume → llm append/consumed event/provider`可实施；失败经结构化terminal error在provider前终止。 |
| D8 cache/history/rollback | append-only与mixed old/new保持自洽。 |
| D9 surface控制 | 不增SDK方法/DTO/参数，只扩既有feature目录并校正文档；IM/schema/table/time tool均不扩。 |

### spec约束对账

| 原子 | 本轮核实 |
|---|---|
| Q1 / 非PA边界 | 只有PA真人消息获得envelope；顶层prompt policy与消息origin分开，heartbeat/cron/subagent/internal message不装envelope。SDK必要例外已诚实写入待用户final review裁决。 |
| Q2 | source优先、Dispatcher receipt fallback、PA timezone完整。 |
| Q3 | 仅平台名，保留sender，不重复Direct/Group或内部identity。 |
| Q4 | 同一shadow session逐消息actual ingress完整。 |
| Q5 | IM/Feishu/shadow raw正文与workspace readable projection均不含header；failure路径由R3-C2修订闭合。 |
| Q6 | PA top-level timezone-only footer；未选择policy的CLI保留current bytes。 |
| Q7 | 新normal/group/consumed history稳定，旧history不猜测。 |
| Q8 | 未增加当前时间查询工具。 |
| 长会话早晚/先后 | D1–D6覆盖，session-created stale time被移除。 |
| provider time / receipt fallback | Web、Feishu live/REST与Dispatcher seam覆盖。 |
| shadow跨Feishu/Web | actual `channel_name`覆盖。 |
| group sender / direct稀疏表达 | existing sender + platform-only header覆盖。 |
| 原入口查看复制搜索 / shadow同步 | raw consumer在装饰前，delta与M1旅程覆盖。 |
| restart与旧历史 | normal/group/consumed durable bytes、old marker absence覆盖。 |
| Coding CLI | default-off及byte/steer regression覆盖。 |
| heartbeat/cron/subagent/internal | human-only admission与top-level policy lifecycle分开覆盖。 |
| N1–N7 | 非PA消息、无time tool、SDK surface收窄例外、无Direct/Group/internal IDs、无其他OpenClaw prefix、visible正文不变、旧消息不补造均未越界。 |

### delta-spec核实台账

| Delta原子 | 本轮判断 |
|---|---|
| Gateway ADDED Requirement及10个Scenario | model envelope、source/receipt、Feishu catch-up、shadow actual ingress、sender、visible正文、readable copy、consumed restart、old history与non-PA语义均为consumer-visible且完整。 |
| Kernel prompts ADDED Requirement及3个Scenario | selected footer、unselected bytes、PromptText name隔离完整。 |
| Kernel prompts MODIFIED Requirement | 忠实保留current tool-gated feature与产品PromptSlots两个Scenario，并新增`requires_tool=None` policy Scenario；MODIFIED用法正确。 |
| Kernel context ADDED Requirement及4个Scenario | durable-before-model、FIFO/restart、accept-not-consumed、default/non-USER完整；结构化error code/count是SDK stream消费者可观察结果。 |
| Kernel SDK MODIFIED Requirement | capability text同时包含tool guidance与no-tool runtime policy；feature discoverability/default-off/no-tool Scenario完整。 |
| SDK current Scenario保留 | capability一致、`skill_view`、shared-root ordering和`无真实 workspace时只查询共享Skill`均完整保留；R3-C1已关闭。 |
| IM/CLI no delta | 两者canonical行为不变，no-delta判断仍成立。 |

### milestone核实台账

| Milestone | 本轮判断 |
|---|---|
| feat-530-M1 | 仍是normal/buffer/replay + prompt/readable-copy垂直切片；范围已明确包含`list_features()`与`FeatureInfo` docstring。退出覆盖store tentative accept/reject、normal同步失败、early commit race、same-run retire、held/continuation、FIFO/no-match/header-shaped raw。 |
| feat-530-M2 | 仍是active-steer durability垂直切片；范围已包含Runtime/Loop/Registry error mapping及PA Coordinator/store跨M integration。writer failure退出同时断言provider未调用、精确count、claimed清除、后续normal不泄露、unclaimed held/continuation可exact消费，足以防两个M各自绿但交界失败。 |

### R3-C2失败协议专项核实

- `RunController.enqueue_message()`与`drain_pending()`保持FIFO（`src/agent/core/agent/run_control.py:96-118,161-170`）；PA生产中真人steer只经Coordinator进入，其他父会话通知使用`RunOrigin.BACKGROUND_TASK`（`agent/platform/background_tasks/wiring.py:162-168`）。因此terminal error的USER claim count可对准Coordinator自己的accepted follower FIFO，不会把非USER消息算入。
- Coordinator已有per-run accepted follower序列与成功消费index（`session_run_coordinator.py:196-197,247-249,1557-1577`）；每次成功consume按`user_message_count`推进。失败从该index切取N条，恰好对应已drain但未发success event的USER批次。
- durable failure从Runtime冒泡后，RunsRegistry可用现有结构化`RunRecord.error`并通过`run_status`发布任意mapping（`agent/core/runs/registry.py:523-534,683-710,837-863`）；`Kernel.stream()`保留并flatten该mapping（`agent/sdk/kernel.py:1619-1637`）。无需新增SDK DTO、方法或hook event。
- terminal status先到Coordinator，Registry随后只对controller中**剩余**pending做settlement（`runs/registry.py:511-548,550-609`）。已drain批次由error count退休；writer failure后才accepted、仍在queue的记录不在count内，继续被held/auto-continuation input exact消费，故不会误删。
- try-steer返回到accepted follower登记之间没有`await`（`session_run_coordinator.py:236-249`），store又明确用commit/reject waiter与early-resolution tombstone处理Kernel线程先到的consume/failure；normal input早于submit return同理由waiter闭合。状态均有终点，无永久FIFO head。

### 整体判断

- R3-C1已完整关闭：SDK MODIFIED delta保留全部current Scenario，`FeatureInfo` public docstring和`list_features()`均进入M1，且未新增SDK method/DTO/parameter。
- R3-C2已完整关闭：store的success、reject、held/continuation与durable-failure路径均有可实现的resolution；稳定error code + USER count + existing consumed index足以精确清理drained批次，不会误删terminal settlement仍持有的record。
- 修订没有增加新产品surface、数据库、持久化store、TTL/regex或第三milestone；新增结构化error字段复用既有run-status transport，是解决明确writer-failure seam的最小跨层信号。

### 架构进攻

| 角度 | 进攻结果 | 长期代价判断 |
|---|---|---|
| 归属 | 时间/envelope/provenance仍归PA，durable-before-model与terminal error归Kernel，选择只经SDK existing features；依赖方向正确。 | 未发现PA反向import Core或Core猜PA。 |
| 该不该存在 | 删除provenance store会退回regex、扩SDK hook payload或另造chat-history writer；删除structured failure metadata会使明确writer failure无法释放claimed FIFO。 | 两者均解决真实跨线程/失败边界，不是YAGNI；仍为进程内最小状态与existing error transport。 |
| 深还是浅 | store隐藏双投影匹配、竞态与失败退休；调用侧只stage/resolve/retire。USER count复用现有accepted FIFO，不暴露claim DTO。 | 接口比底层并发实现窄，未形成浅包装；`claim id`留在Kernel私有metadata，不扩消费者surface。 |
| 治本还是补丁 | exact provenance治本避免文本猜测；durable barrier治本避免model看到不可恢复steer；terminal count补齐同一事务的失败分支。 | 无TTL、header grammar特判或Gateway带外append债务。 |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-C1 | 补回`list_shared_skills` Scenario；D6/M1纳入`FeatureInfo` docstring | delta已逐字义保留该Scenario；D6、D9和M1范围/退出均包含两处SDK触点。 | closed |
| R3-C2 | 补全store状态机；以terminal error code + USER count清理claimed批次；M2补跨M断言 | FIFO、成功index、结构化error transport与terminal settlement顺序均可实施且不会误删unclaimed；M1/M2退出覆盖竞态与failure后store状态。 | closed |
| R3-R1 | 保留两个顺序milestone | 修订落在M1 contract + M2 cross-failure seam，无需M3。 | adopted / verified |

### Issues

无。

### Recommendations

- [R4-R1] Gate 2文档质量已通过，可交由用户做最终design review并拍板spec中显式列出的SDK边界例外；用户确认后可进入`change-orchestrator`。

## User Design Review Correction — active-steer durability removed

- 用户指出：“这个跟本需求有啥关联？没这个需求，不也是这样的吗”，并最终裁决“压根不用考虑这个问题，多此一举”。作者确认此前把current active-steer持久化缺口绑定到time/Channel envelope属于范围扩张。
- 当前设计删除整个`durable-consumed-steers` M2、Kernel context-persistence delta、AgentLoop/Runtime/Registry改动、writer-failure协议与claim/provenance失败状态机。active steer仍经Coordinator现有parts builder获得同格式model envelope，但其接受、消费、持久化、失败处理和恢复语义完全保持current行为，本unit不再讨论或验证该通用问题。
- Q7/restart保证收窄到按既有normal transcript与group buffer路径进入可恢复历史的消息。readable projection store只服务current normal `input` hook，不参与active-steer生命周期。`per_message_time_context`只控制session runtime footer省略session-created datetime，不再选择任何消息持久化行为。
- Round 4 Approved基于已删除的M2与失败协议，不能作为当前设计的最终Gate 2结论；需对缩减后的单milestone设计重新review。

## User Design Review Correction — footer feature renamed

- 用户指出`per_message_time_context`名称不符合实际语义；该feature真正控制的是system runtime footer是否包含session创建时间，而不是消息是否具有逐消息时间。
- 当前设计改为`include_session_created_datetime`：`default_on=True`保持Kernel/Coding CLI current bytes，PA所有顶层session显式设为`False`。该开关只控制footer，逐消息prefix仍完全由PA在SDK外构建，active-steer生命周期仍不在范围内。

## Round 5

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: 用户最终design review删除M2、Kernel context-persistence契约与整条active-steer durability/failure数据流，并把Q7及milestone收窄为单M1；这是需求非目标、核心边界、数据流、delta集合与milestone拆分的实质变化，必须full重审。
- started_at: `2026-08-10T17:59:14+08:00`
- completed_at: `2026-08-10T18:02:22+08:00`
- duration: `3m08s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 完整重读最新`spec.md`、`design.md`、Gateway routing-delivery delta、Kernel prompts/sdk-boundary两份delta、单一M1骨架、Round 4与其后的User Design Review Correction；确认Kernel context-persistence delta与M2目录已经删除。
- 从生产入口重新追踪Web relay/Feishu live+REST → Dispatcher → Pipeline raw/shadow/group buffer → Coordinator normal/try-steer共用parts → Kernel normal input hook/chat-history，以及PA runtime projection → Core footer/list_features；没有继承Round 4对已删除M2的结论。
- 全量核对本轮五类承重原子，并对缩减后的新增模块/职责重新执行四角度架构进攻。

### 现状断言核实台账

| ID | 本轮独立核实 |
|---|---|
| S1 | `InboundMessage`仍是Web/Feishu共同PA入站对象且没有source/receipt字段，见`src/personal_assistant/channels/base.py:23-46`。 |
| S2 | Web relay生产payload已有`message.created_at`，Adapter当前未投影，见`src/IM/application/relay_service.py:112-131`、`channels/web_relay_adapter.py:246-297`。 |
| S3 | Feishu live与REST history确有两条生产解析路径，history经`client.py:643`进入`_parse_feishu_history_message()`，对应live/REST parser在`client.py:1089-1176`。 |
| S4 | Dispatcher在seal检查后、`create_task`/`run_coroutine_threadsafe`前拥有同步acceptance seam，见`gateway/inbound_dispatcher.py:37-75`。 |
| S5 | Pipeline先完成external shadow raw sync，再在group buffer或dispatch前分叉，freeze可落在`inbound_pipeline.py:135-183`的共同生产路径。 |
| S6 | Coordinator对active run与normal run都调用同一个`_build_message_parts()`，见`session_run_coordinator.py:206-277,820-884,1125-1167`；active steer只需自然获得新model parts。 |
| S7 | GroupContextStore已有SQLite JSON metadata round-trip，见`group_context_store.py:70-139`；frozen metadata无需新表。 |
| S8 | PA chat-history生产hook只在normal turn的Core `input`事件捕获flat `payload.text`，见`hooks/chat_history.py:14-17,70-77,94-120`。active steer没有独立input hook/user pair。 |
| S9 | Runtime在构造normal turn时先render parts，再dispatch input hook，见`agent/core/agent/runtime.py:391-449`；Coordinator可在同步`Kernel.submit()`前stage exact projection。 |
| S10 | `Kernel.submit()`是同步非阻塞，Coordinator随后在同一session transition内发布active marker，见`session_run_coordinator.py:833-893`；同session第二条消息不会作为并发normal admission覆盖首条的有效mapping。 |
| S11 | normal user turn仍由Runtime按current路径持久，旧transcript按原bytes重放；本unit无需修改AgentLoop/Runtime/Registry。 |
| S12 | current active steer只把Coordinator parts转成pending LLM message并由既有loop消费，见`agent/sdk/kernel.py:1447-1479,1548-1591`、`agent/core/agent/loop.py:364-376,591-624`。 |
| S13 | current canonical只承诺active steer及时采纳/FIFO/sender等现有行为，见`docs/specs/gateway/routing-delivery.md:168-204`；没有本unit需要修复的durability契约。 |
| S14 | Core footer当前无条件渲染session-created datetime + cwd，见`core_sections.py:320-346`。 |
| S15 | Runtime已有resolved feature flags进入`PromptContext`，见`runtime.py:496-534`；footer可只读新flag而不触碰消息生命周期。 |
| S16 | complete-runtime features仍持久化、参与runtime identity/reconfigure，且未知registry key会被过滤；新增正式registry item是必要最小Core触点。 |
| S17 | `Kernel.list_features()`当前固定投影两项，见`agent/sdk/kernel.py:1855-1884`；新增policy必须改该真实公共查询。 |
| S18 | `FeatureInfo` public docstring仍声称“only two”，见`agent/sdk/dto.py:369-380`；M1已包含校正。 |
| S19 | PA的IM toggle payload来自固定`FEATURE_PROJECTIONS`而非自动透传`list_features()`，见`reporter/capability_projection.py:75-112,154-189`；不把internal policy做UI toggle可实施。 |
| S20 | PA human/heartbeat/cron共用顶层runtime alignment，固定选择policy可避免canonical session按origin振荡；只有human admission构建envelope。 |
| S21 | 内置subagent创建自己的metadata/PromptSeed且不复制parent feature，Coding CLI也不选择新default-off key。 |
| S22 | `[sender]`仍由Coordinator parts projection拥有，header可在其后追加而不改group identity。 |
| S23 | IM/shadow在Coordinator装饰前消费raw body，visible raw/model decorated分层仍成立。 |
| S24 | `channel_name`是逐消息actual ingress；无需读取shadow conversation的固定external source。 |
| S25 | old transcript不经过admission，old group row没有新marker；两者自然满足“不猜测”。 |
| S26 | Kernel hook registry允许PA factory注册闭包式setup，`agent/sdk/kernel.py:690-691`；composition-owned store可经M1范围内的`composition.py`/`product.py`注入现有chat-history hook，无需SDK/Core hook扩张。 |
| S27 | worktree Gateway与真实Feishu/Web旅程仍是生产wiring，runbook与改动常驻服务相符。 |

### 决策核实台账

| 决策 | 本轮判断 |
|---|---|
| D1 receipt/freeze | acceptance时点、raw consumer顺序、单次freeze owner均拍死且落在生产路径。 |
| D2 provider occurrence | Web ISO与Feishu live/REST epoch source完整；invalid→receipt规则明确。 |
| D3 v1 header | 平台、时间、sender、multimodal插入与raw rebuild完整，不靠解析正文幂等。 |
| D4 timezone | startup snapshot、IANA/DST/fixed offset、重启生效与无新配置边界完整。 |
| D5 normal readable projection | 单session exact mapping只服务normal input hook；stage-or-replace、exact consume、sync failure rollback、no-match raw fallback均拍死。active steer明确不stage、不参与store lifecycle。 |
| D6 footer policy | `per_message_time_context`仅选择footer是否省略session-created datetime；discoverable/default-off/no-tool、PA顶层固定、CLI/subagent不选均明确，且三处明示不改变消息生命周期。 |
| D7 cache/compat/rollback | stable timezone + append-only user header、old bytes不重写、回滚后v1 header普通重放均自洽。 |
| D8 surface控制 | SDK仅扩既有feature目录与docstring，IM schema/table/time tool均不扩；无AgentLoop/Runtime/Registry改动。 |

### spec约束对账

| 原子 | 本轮核实 |
|---|---|
| Q1 | 只有PA Web/Feishu真人消息获envelope；Coding CLI、heartbeat/cron、subagent/internal message保持current。SDK例外已按用户先前边界裁决诚实限定为product-neutral existing feature surface。 |
| Q2 | source occurrence优先、Gateway acceptance receipt fallback、PA timezone覆盖。 |
| Q3 | 只表达平台，保留existing sender，不重复Direct/Group或内部identity。 |
| Q4 | shadow共享session仍逐消息取actual `channel_name`。 |
| Q5 | IM/Feishu/shadow正文走raw；normal workspace副本用exact readable projection，不猜测剥header。 |
| Q6 | PA顶层footer timezone-only；default consumer保留session datetime + cwd。 |
| Q7 | 最新spec只保证**按既有normal transcript或group buffer路径进入可恢复历史**的新消息；D5/D7、runbook 4与M1 restart退出完全同范围，没有active-steer恢复承诺。 |
| Q8 | 无`session_status`或其他精确时间工具。 |
| 时间Requirement 3 Scenarios | 长会话、provider time、receipt fallback均由D1–D6与M1旅程覆盖。 |
| Channel Requirement 3 Scenarios | shadow跨入口、group sender、direct稀疏表达均覆盖。 |
| 原文Requirement 2 Scenarios | 原入口与shadow raw body不含header；normal readable副本另由Gateway delta覆盖。 |
| 延续Requirement 2 Scenarios | normal/group既有可恢复路径保留frozen bytes；旧历史无marker不补造。 |
| 非PA Requirement 2 Scenarios | CLI default-off；background/subagent/internal无human envelope。 |
| 非目标全集 | 无其他OpenClaw prefix/Direct/Group/internal IDs/time tool/visible body变更；SDK不增方法/DTO/参数；active-steer接受、消费、持久化、失败、恢复全部明确排除。 |

### delta-spec核实台账

| Delta原子 | 本轮判断 |
|---|---|
| Gateway ADDED Requirement | 指向最窄routing-delivery canonical，parallel新增用ADDED正确；prose明确active steer只复用fixed envelope、不改变生命周期。 |
| 长会话Scenario | 用户可观察，覆盖逐消息time与stale footer。 |
| source/receipt Scenario | occurrence优先与acceptance时固定完整。 |
| Feishu catch-up Scenario | 明确REST history使用provider time。 |
| shadow actual-ingress Scenario | 明确逐消息Web IM/Feishu，不读conversation source。 |
| group sender Scenario | 保留`[sender]`且不重复chat type。 |
| visible body Scenario | IM/Feishu/shadow查看复制搜索保持raw。 |
| workspace readable Scenario | 只承诺“PA实际写入一次user input时”不含header，忠实current normal hook边界，不为active steer虚构新pair。 |
| old history Scenario | old transcript/buffer不补stamp，新admission才开始使用。 |
| non-PA Scenario | CLI prompt/message与PA background sources保持current；未残留active-steer durability wording。 |
| Kernel prompts ADDED Requirement及3 Scenarios | policy只控制footer；selected/unselected/PromptText-name三条consumer-visible且明确不改message lifecycle。 |
| Kernel prompts MODIFIED Requirement | 忠实保留current tool-gated feature与product PromptSlots Scenarios，并新增no-tool generic policy Scenario；用法正确。 |
| Kernel SDK MODIFIED Requirement | `list_features()`发现default-off/`requires_tool=None` policy且无独立API/DTO；未选择时只保持default footer，并明确选择与否均不改消息生命周期。 |
| SDK既有Scenarios | capability一致、`skill_view`、shared-root ordering、无workspace时`list_shared_skills()`全部保留，无静默回归。 |
| 删除项核实 | unit中已无Kernel context-persistence delta；IM/CLI继续no delta，和current行为不变相符。 |

### milestone核实台账

| Milestone | 本轮判断 |
|---|---|
| feat-530-M1 | 单一垂直milestone从Adapter时间事实贯穿Gateway model/raw projection、normal readable副本、Core footer与SDK discoverability，具备完整reviewer/worker两轨退出。范围没有AgentLoop/Runtime/Registry或M2；active steer只测共用parts含header，不测持久化/失败/恢复。单M比原两M更符合当前范围。 |

### active-steer范围专项核实

- 最新spec用户场景、非目标，design现状约束/D5/D6、接口表、流程图、风险、runbook与M1均一致：active steer只接收Coordinator共用builder生成的`model_parts`，不产生projection-store record，不新增input hook，不改变pending consume或history行为。
- `per_message_time_context`的接口不再包含durable-before-model语义；prompts与SDK delta都把它限定为footer policy。unit没有context-persistence delta，M1范围也不含`agent/core/agent/{loop,runtime}.py`或`agent/core/runs/registry.py`。
- Q7的GIVEN显式要求消息已经经normal submit或group buffer进入可恢复历史；review runbook与M1同样只验这两条restart路径。Gateway delta中`active steer`与`history replay`仅列为各自遇到时复用同一frozen envelope，并紧接“不改变active steer持久化/恢复语义”，没有承诺active steer一定进入replay。

### normal readable projection专项核实

- stage发生在normal `Kernel.submit()`前，input hook只在该normal run开头读取；Coordinator在同一session transition内紧接submit发布active marker（`session_run_coordinator.py:833-893`），随后消息走try-steer而不是第二个normal slot，因此单session replace不会覆盖一个仍可正常exact消费的mapping。
- exact key使用Core input hook实际看到的完整model fallback；match才返回同源生成的readable fallback并删除，no-match沿用原payload。合法header-shaped用户正文只会出现在readable fallback正文中，store从不按header grammar删除内容。
- Kernel同步拒绝/抛错时rollback；若background input hook已先exact消费，rollback幂等。hook失败遗留的单槽会被下一次normal admission替换，不会误配给不同payload；最坏no-match保留完整decorated payload，不会删用户原文。
- 删除store会迫使PA解析flat header、扩Core input hook contract或迁出current chat-history writer；当前三方法单槽exact store是满足Q5的最小安全桥，不需要旧claimed/consumed/failure状态机。

### 整体判断

- 缩减后的方案已忠实执行用户纠正：active-steer通用持久化问题不再借feat-530扩张，历史/失败协议及M2均彻底移除。
- 上层总览能直接读出“Adapter事实→Pipeline冻结→Coordinator model/readable双投影→normal exact hook→footer-only policy”；接口、流程、风险、runbook、delta与单M1一致。
- 当前Q7范围仍实现用户确认的正常可恢复路径，没有把已存在但与本需求无关的active-steer生命周期缺口伪装为本unit目标。

### 架构进攻

| 角度 | 进攻结果 | 长期代价判断 |
|---|---|---|
| 归属 | provider时间归Adapter、receipt归Dispatcher、freeze/raw-model分层归Pipeline/PA module、final parts/readable bridge归Coordinator/composition、footer语义归Core。 | 顺着`personal_assistant → agent.sdk`依赖方向；无PA反向import Core或Core猜产品。 |
| 该不该存在 | `PaHumanMessageContext`集中source/fallback/timezone/format/multimodal，exact store跨越Coordinator与existing input hook。删除任一都会把规则散回多Adapter/Coordinator或回到文本猜测。 | 两者均有真实复杂度可隐藏；旧M2/claim/error协议已删除，不再为通用问题造抽象。 |
| 深还是浅 | module只暴露freeze/projection，store只暴露stage-or-replace/resolve-exact/rollback；复杂度低于其封装的多source与跨线程时序。 | Core render若未来漂移会安全no-match并由focused tests暴露，不会有损剥正文；没有复制Kernel lifecycle。 |
| 治本还是补丁 | occurrence在事实源归一化、receipt在acceptance冻结、readable从同源projection生成、footer用product-neutral flag选择。 | 没有hardcode PA name进Core、regex strip、TTL、带外transcript append或active-steer补丁债。 |

### 历史问题与用户纠正

| 历史项 | 当前修订 | 本轮核实 | 状态 |
|---|---|---|---|
| Round 4 Approved | User Correction指出其依赖的M2/失败协议属于范围扩张 | Round 4只对旧设计有效；本Round从新inventory full重审，没有继承其结论。 | superseded |
| R3-C1 | SDK delta保留current Scenarios并纳入`FeatureInfo` docstring | 最新缩减未撤销该正确修订，仍完整。 | closed / retained |
| R3-C2及R4失败协议 | 用户删除active-steer durability目标、M2与相关store状态机 | 当前normal-only store不再遇到claimed/consumed/writer-failure seam；不是“保留旧方案后忽略问题”，而是整条非目标设计已消失。 | removed by user scope correction |
| User Design Review Correction | active steer current lifecycle不变；Q7收窄；footer-only；单M1 | spec/design/delta/milestone逐层一致，未发现残余实现范围或恢复承诺。 | applied / verified |

### Issues

无。

### Recommendations

- [R5-R1] 当前Gate 2文档质量已通过；可按用户最终design review裁决进入`change-orchestrator`实施单一M1。

## Round 6

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `full`
- mode_reason: 本轮把共享Kernel feature从理由导向的`per_message_time_context/default-off`改为行为导向的`include_session_created_datetime/default-on`，同时反转PA与默认消费者的布尔方向；该变化触及公共key、registry default、omission semantics、`list_features()`与canonical SDK/prompt契约，closure自动升级为full。
- started_at: `2026-08-10T18:30:16+08:00`
- completed_at: `2026-08-10T18:33:03+08:00`
- duration: `2m47s`

### Verdict

Approved — 0 CRITICAL / 1 WARNING

### Coverage

- 完整重读最新`spec.md`、`design.md`、Gateway routing-delivery delta、Kernel prompts/sdk-boundary两份delta、M1骨架，以及Round 5之后的footer feature用户纠正；旧Round中的旧key只作为不可改写的历史记录处理，不继承其feature结论。
- 从current canonical与生产wiring重新核对Core footer/flag resolution、SDK runtime omission/list_features/FeatureInfo、PA human/heartbeat/cron runtime projection、Coding CLI与subagent默认继承，以及Gateway normal/active-steer共用parts路径。
- 全量复核五类承重原子，并对当前单M1重新执行四角度架构进攻；唯一问题是三处非规范摘要/通用Scenario仍残留“选择/不选择”语言，精确normative Scenarios已经足以锁定实现。

### 现状断言核实台账

| ID | 本轮独立核实 |
|---|---|
| S1 | `CORE_RUNTIME_FOOTER`当前无条件按“session-created datetime → cwd”两行渲染，见`src/agent/core/agent/prompt_sections/core_sections.py:320-346`；新布尔值直接对应一个真实、product-neutral的可省略片段。 |
| S2 | Runtime已将`resolve_flags_from_metadata()`结果放入`PromptContext.flags`，见`src/agent/core/agent/runtime.py:496-534`；footer读取新flag无需修改消息提交、AgentLoop或持久化。 |
| S3 | flag resolution以`FEATURE_REGISTRY.default_on`为基线，再只覆盖metadata中显式bool，见`prompt_sections/wiring.py:118-153`；省略新key天然解析为`True`。 |
| S4 | `SessionRuntimeConfig.features`明确允许`None`表示defaults，fingerprint保留`None`与空map差异，而`runtime_metadata()`把两者都投影为无显式override，见`src/agent/sdk/runtime.py:18-35,63-105`；对本key两者均继承registry `True`。 |
| S5 | PA current runtime与legacy capability projection都从`config.features`复制，见`gateway/session_composition.py:51-103`；方案把internal `False`固定合入这两个共同owner，能覆盖create/reconfigure以及human/heartbeat/cron顶层alignment。 |
| S6 | `Kernel.list_features()`当前显式白名单两项而非自动遍历全部registry，见`src/agent/sdk/kernel.py:1855-1884`；D6/M1准确包含新增固定投影。 |
| S7 | `FeatureInfo` public docstring仍枚举“only two”，见`src/agent/sdk/dto.py:369-385`；M1准确把修正该docstring列为唯一DTO文档触点，不新增字段或类型。 |
| S8 | PA capability UI来自固定`FEATURE_PROJECTIONS`，不是把`list_features()`逐项暴露为toggle，见`reporter/capability_projection.py:75-112,154-190`；新internal policy可discoverable而不成为PA用户配置。 |
| S9 | Coordinator对normal submit和try-steer都复用`_build_message_parts()`，现有normal transition仍在同步`submit()`后发布active marker，见`session_run_coordinator.py:820-893,1125-1167`；feature翻转没有进入该路径。 |
| S10 | Gateway current canonical只承诺active steer及时采纳/FIFO/sender等行为，见`docs/specs/gateway/routing-delivery.md:168-204`；当前unit仍未承诺或修改其持久化/失败/恢复生命周期。 |
| S11 | Web relay已有`created_at`，Feishu live与REST history均有`create_time`解析seam；`InboundMessage`仍没有source/receipt字段，Dispatcher仍在跨loop排队前拥有同步acceptance seam。feature重命名未改变这些Gateway事实。 |
| S12 | chat-history hook仍只在normal `input`事件捕获flat model text，见`src/personal_assistant/hooks/chat_history.py:14-17,70-77`；normal-only exact readable projection设计及active-steer排除项均未受feature变更影响。 |

### 决策核实台账

| 决策 | 本轮判断 |
|---|---|
| D1 receipt/freeze | Dispatcher acceptance、raw consumers后freeze、只取时一次仍完整且生产owner正确。 |
| D2 provider occurrence | Web ISO与Feishu live/REST epoch来源、invalid→receipt fallback不变。 |
| D3 v1 header | actual Channel/time/sender/multimodal次序仍固定；不依赖新Core feature决定消息envelope。 |
| D4 timezone | startup snapshot同时服务header与稳定PromptText；footer feature只决定session-created datetime是否存在。 |
| D5 readable projection | normal-only exact stage/resolve/rollback仍不解析header、不参与active steer lifecycle。 |
| D6 footer policy | key统一为`include_session_created_datetime`；`True`包含session-created datetime，`False`省略；registry/list_features为`default_on=True`、`requires_tool=None`；PA顶层固定`False`，CLI/subagent省略override继承`True`。 |
| D7 cache/compat/rollback | PA只发生一次runtime generation变化；default consumers保持current footer bytes；历史user header与消息生命周期不受flag影响。 |
| D8 surface控制 | SDK无新method/DTO/parameter，只扩既有feature目录与docstring；IM schema、DB、time tool、AgentLoop/Runtime/Registry生命周期范围均未回膨。 |

### spec约束对账

| 原子 | 本轮核实 |
|---|---|
| Q1 + 设计阶段边界裁决 | 真人envelope仍只改PA；最小Kernel例外诚实写为product-neutral existing feature surface。新key/default/PA False/CLI与subagent默认值均明确。 |
| Q2–Q5 | occurrence优先、receipt fallback、actual ingress、模型/可见正文分层不变，且不由footer flag门控。 |
| Q6 | PA所有顶层session显式`False`得到timezone + cwd、无stale session datetime；默认消费者`True`保持current。 |
| Q7 | restart保证仍仅覆盖既有normal transcript/group buffer可恢复路径，旧历史不猜测；没有借feature翻转恢复active steer。 |
| Q8 | 仍无`session_status`或其他精确时间工具。 |
| Requirements全集 | time 3个Scenario、Channel 3个Scenario、raw正文2个Scenario、延续2个Scenario、非PA 2个Scenario均由D1–D8和M1退出覆盖。 |
| 非目标全集 | 无Direct/Group/internal IDs、其他OpenClaw prefixes、IM可见正文变更、新SDK API或active-steer lifecycle承诺；新feature只控制footer。 |

### delta-spec核实台账

| Delta原子 | 本轮判断 |
|---|---|
| Gateway ADDED Requirement及9个Scenarios | time/actual-ingress、Feishu REST、shadow、group sender、visible/readable raw、old history、non-PA语义均未被footer更名改变；active steer继续只复用fixed envelope并紧邻生命周期排除。 |
| Kernel prompts ADDED Requirement | key、`default=True`、显式`False`、cwd保留、PromptText name中立、消息生命周期不变全部准确。 |
| prompts: 显式关闭Scenario | `False → timezone + cwd、无Current date`与PA目标方向一致。 |
| prompts: 省略/显式开启Scenario | 明确`omitted override OR True → current datetime + cwd`，已经钉死Coding CLI/subagent omission semantics。 |
| prompts: PromptText name Scenario | 证明Core不靠`pa.*`名字猜产品，正确保留product-neutral边界。 |
| prompts MODIFIED Requirement及既有Scenarios | tool-gated guidance、product PromptSlots Scenarios均保留；新增no-tool policy合法。其“选择/不选择”表述存在R6-W1歧义，但不推翻上方精确Scenario。 |
| Kernel SDK MODIFIED Requirement | `list_features()`发现新key且`default_on=True/requires_tool=None`；明确省略key保持默认footer、显式False省略datetime，并保留`skill_view`、workspace/shared roots、`list_shared_skills()`全部current Scenarios。 |
| delta集合 | unit仍只有Gateway + Kernel prompts + Kernel SDK三份delta；无需IM/CLI或context-persistence delta。 |

### milestone核实台账

| Milestone | 本轮判断 |
|---|---|
| feat-530-M1 | 单一垂直milestone仍覆盖Adapter/Gateway/readable projection/footer policy。范围明确包含Core registry/footer、`Kernel.list_features()`、`FeatureInfo` docstring与PA runtime projection；退出明确断言新key、`default_on=True`、`requires_tool=None`、PA显式False、CLI省略override，并保留active-steer current-only边界。无需恢复M2。 |

### include_session_created_datetime专项核实

- **key与方向**：spec边界裁决、D6、Interface表、risk、M1、prompts delta与SDK delta均以同一个key表达`True=包含`、`False=省略`；旧key只出现在design changelog和历史Round中，用来记录迁移，不是current承诺。
- **omission**：registry baseline机制使省略key解析为`True`；prompts ADDED Scenario与SDK Scenario均显式写出该事实。Coding CLI和subagent无需增加override即可保持current footer，避免为了“不变”去修改两个consumer。
- **PA固定False**：D6要求runtime/preview对所有顶层PA session固定合入False，且UI不暴露toggle；human/heartbeat/cron共享canonical session时不会按origin振荡，用户Agent配置也不应反向选回True。
- **SDK触点**：新增registry item需要`Kernel.list_features()`白名单投影；`FeatureInfo`只改过时说明。没有新增SDK方法、DTO、field或parameter，符合spec列出的最小边界例外。
- **职责隔离**：Core flag只影响`CORE_RUNTIME_FOOTER`的datetime行；逐消息header仍由PA admission构建，normal/steer接受、消费、持久化、失败和恢复均不读取该flag。

### Gateway与active-steer不受影响专项核实

- Gateway delta、D1–D5/D7、主流程、risk、runbook与M1仍是Adapter事实 → Dispatcher receipt → Pipeline freeze → Coordinator双投影；没有把feature key传入message context module或projection store。
- active steer仍仅通过Coordinator共用parts builder得到同格式model envelope，不stage readable projection、不新增input hook、不修改AgentLoop/Runtime/RunsRegistry，也没有新增恢复验收。
- Q7和M1 restart退出仍只点名normal transcript与group buffer。footer默认值翻转没有扩大或收缩这一保证。

### 整体判断

- 行为导向命名与布尔方向比旧方案更忠实接口事实：default-on让未参与本需求的Kernel/Coding CLI/subagent自然保持current，只有PA顶层显式关闭stale datetime。
- current production flag resolution、complete-runtime持久化/fingerprint以及PA统一runtime projection都能承载该语义，不需要新增SDK surface或消息生命周期协议。
- 一处摘要和一条通用Scenario仍使用旧的“选择/不选择”心智模型，属于可修正文案歧义；精确ADDED/SDK Scenarios及M1退出已经使方案可直接实施，因此不构成CRITICAL。

### 架构进攻

| 角度 | 进攻结果 | 长期代价判断 |
|---|---|---|
| 归属 | footer是否含session-created datetime归Core registry/footer；PA只经现有SDK features选择False；逐消息事实与投影仍归PA Gateway。 | 依赖方向仍为`personal_assistant → agent.sdk → core`，Core不识别PA，CLI/subagent不需要补丁。 |
| 该不该存在 | 一个default-on/no-tool registry item是跨consumer选择现有Core footer行为的最小表达；不用它只能让Core猜PromptText/product或复制footer。 | 没有新增API/DTO/配置UI；状态复用既有完整runtime，抽象成本与行为复杂度匹配。 |
| 深还是浅 | key隐藏footer渲染差异，消费者只提供bool；`list_features()`提供默认与tool依赖事实。 | 接口信息足够，唯一浅点是R6-W1的非精确“选择”措辞，不是实现结构缺口。 |
| 治本还是补丁 | default-on保存current，PA False表达真正产品差异；PromptText只提供timezone而不暗中选择行为。 | 避免旧理由导向命名、product-name sniffing与跨消息生命周期耦合；未引入兼容分支。 |

### 历史问题与用户纠正

| 历史项 | 当前修订 | 本轮核实 | 状态 |
|---|---|---|---|
| Round 5 D6/feature结论 | 旧`per_message_time_context/default-off/PA True`被用户纠正 | current spec/design/deltas/M1已统一新key与反向布尔；本Round取代Round 5的feature专项结论。 | superseded / replaced |
| Round 5 Gateway/active-steer/readable结论 | footer更名不应改变消息路径 | 本轮重新核对Gateway delta、production parts/hook与单M1，未发现范围回膨或残余旧生命周期承诺。 | retained / independently verified |
| User Design Review Correction — footer feature renamed | `include_session_created_datetime`, default True, PA False, no-tool, footer-only | 精确contract与实现触点已闭合；只余R6-W1文案歧义。 | applied with warning |

### Issues

- [R6-W1] **WARNING — 三处“选择/不选择”残余措辞会弱化default-on omission contract。** `design.md:35`称Coding CLI“不选择policy”、`design.md:256`仍把Kernel delta概括为“selected per-message time context”，`specs/kernel/prompts.md:37-40`又用“选择或不选择→应用或省略”描述无工具policy。对于default-on key，“省略override”实际必须应用datetime，只有显式`False`才省略；上述措辞可能让后续canonical合并或测试命名重新滑回旧心智模型。精确prompts ADDED Scenario、SDK Scenario、D6与M1已明确正确方向，所以不阻断实施，但应统一改成“省略override继承registry default；显式True/False决定具体行为”，并在design delta摘要直接点名新key。

### Recommendations

- [R6-R1] 在进入orchestrator前收口R6-W1三处措辞；除此之外，Gate 2文档质量已通过，可交由用户做最终design review并决定进入单一M1实施。

## Author Resolution — Round 6

- [R6-W1] **Accepted.** Design既有约束改为Coding CLI/subagent省略`include_session_created_datetime` override并继承registry默认`True`；delta摘要直接点名新key、omission与PA `False`方向。Prompts MODIFIED的通用no-tool Scenario改为“省略key继承声明的`default_on`，显式`True`/`False`按布尔覆盖”，不再使用default-off导向的“选择/不选择”措辞。

## Round 7

### Metadata

- reviewer: `/root/feat530_design_reviewer`
- review_mode: `closure`
- mode_reason: Round 6仅余R6-W1措辞歧义；本轮三处修订只把既有default-on契约写精确，没有改变key、布尔语义、架构边界、数据流、delta集合或milestone，影响可封闭。
- started_at: `2026-08-10T18:34:43+08:00`
- completed_at: `2026-08-10T18:36:00+08:00`
- duration: `1m17s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R6-W1 | CLI/subagent明确省略override继承registry `True`；design delta摘要点名新key/omission/PA `False`；prompts通用Scenario改为省略继承default、显式bool覆盖 | `design.md:35`现明确Coding CLI与subagent不提供`include_session_created_datetime` override且继承`True`；`design.md:256`准确写出新key、omission、PA `False`与默认consumer不变；`specs/kernel/prompts.md:37-41`明确`requires_tool=None`、省略key继承声明的`default_on`、显式`True`/`False`覆盖且不猜PromptText。三处与D6（`design.md:158-166`）、SDK delta（`sdk-boundary.md:20-23`）及M1退出（`design.md:301`）一致。旧短语搜索无残留，旧key仅保留在changelog中记录更名。 | closed |

- retained_from: Round 6 — 本轮未改Gateway、active-steer、message envelope、SDK surface或milestone语义；Round 6的完整台账与架构进攻未失效。

### Issues

无。

### Recommendations

- [R7-R1] R6-W1已完整关闭，Gate 2当前为0 CRITICAL / 0 WARNING；可交由用户做最终design review，批准后进入`change-orchestrator`实施单一M1。
