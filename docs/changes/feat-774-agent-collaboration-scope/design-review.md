# feat-774 独立设计审查

## Round 1

- Reviewer target 为 `/root/design_review`，基线为 `develop` 的 `ea30aea76`，受审对象为本地本 unit 的 spec、design、八份 delta、部署提示词及 M1 目录。
- `review_mode` 为 `full`。这是首次评审，涉及新收件规则、原生请求边界和两个客户端。
- `started_at` 为 `2026-11-18T17:05:20+09:00`，`completed_at` 为 `2026-11-18T17:10:16+09:00`，`duration` 约 4 分 56 秒。
- **Verdict — Issues Found，2 CRITICAL / 2 WARNING。**

### Coverage

- 从 `apps/node/src/main.ts` 的 relay、`pa.observations.available`、FeishuConnection 和 configuration prepare/apply 跟到 IM 的 `Messaging.enqueueRelays`、`RelayDelivery`，以及产品包的 GlobalAgent、InboxStore、SingleThread。来源包核实平台或会话事实，在 product-contracts 共享纯分类，产品包各按既有会话边界定时和持久交付，职责与现有组装匹配。复用 Inbox 快照、待提交 inputs 和 DSH 公开 hook 可避免增加执行循环。收件、发言前复核和命令授权分开也有必要。
- 按新建默认、双方私聊/群、PA 参与/旁观、期限与高优同至、空闲与忙碌、源撤销及重启逐项对照。单一端到端 M1 能覆盖跨包动线，退出标准有 worker/reviewer 分工，目录已有 `.gitkeep`。实际请求、对账回执、控制时钟及独立聊天触发计数可检验合并目标。收紧成功的可证边界和飞书身份还需按以下发现补足。
- Context 设计样例能让 PA 先读 14:37 的主人私聊，也能辨认 14:32 群里的 @ 目标，两个 target 可直接用于 read。十分钟采用准入时间，展示采用原消息时间，两个时钟职责清楚。实际旧源字段有下述例外。SingleThread 同群正文的切分、真实作者和触发来源在实施时需要用同一出站请求与审批实际读取的原文核对。
- Web `agent-detail-page.tsx` 的现有 select 与 iOS `AgentConfigView.swift` 的 Picker 足以承载两个档位。本次沿用现有位置和保存路径，无需为这次选择器替换另制可交互原型。尚无目标构建画面，视觉与操作证据留在 M1。
- 八份 delta 的路径和 MODIFIED 标题核对了对应 current 的配置、回执、Global/PA、路由、外部渠道和注册快照。不同的批次实现可满足大部分行为条款。飞书条款有反例，见 R1-W2。部署提示词将旧库副本、迁移中断和重复执行安排在隔离环境，生产有操作收敛、离线节点清单、分端备份、有限只读核对与匹配版本恢复。实施交付时需按承诺补全已验证语句和旧输入对账；飞书绑定的历史来源同时受 R1-C1 影响。

### Issues

**R1-C1 · 既有飞书自动绑定不能证明来信者就是 Agent 创建者。** `design.md` 的「身份事实与优先级」把已绑定 `owner_open_id` 用作仅限本人的凭据，`deployment-prompt.md` 保留现有绑定。生产组装使用的 `packages/channels/src/feishu.ts:86` 会将首个 live 消息发送者绑定为主人，包括第一个在群里发言的人。`apps/im-server/src/channels.ts:594` 持久化该 ID，不记录其来自创建者认证。于是默认团队模式期间由同事先发一条消息，再切仅限本人，同事便能以“已绑定”身份私聊通过。收紧时禁止未来自动绑定挡不住这个序列。需要确定什么证据足以用于私人收件，以及没有该证据的旧绑定如何处理。保留团队渠道的旧投递关系与权威身份可以分别实现。隔离验收应包含先由非主人产生团队自动绑定、再收紧并分别尝试双方私聊。

**R1-C2 · `pre-step` 复核与真实发出之间的请求及工具结果仍可越过收紧边界。** `design.md` 的「切换时停止积压」指定 `inbox.remove` 和 task-context 的 `agent/pre-step`。当前锁定的 DSH `dsh-agent-loop` 在 `preStep` 取出候选后，`step` 还会 `await prepareRequest`，然后把候选追加到 `user/message` 历史，再调用 provider stream。此时清队列已触及不到该候选。另一个入口是 `packages/dsh-integration/src/global-mode.ts:75` 的 Inbox `read/check` 工具结果，正文、图片或摘要可在工具阶段生成后等待下次请求，`agent/pre-step.messages` 只包含本步新领的输入。方案写了“按实际请求定序”，但没有指明谁能冻结或等待这些已越过 hook 的交付、如何恢复已追加但未发出的历史。请给出基于公开接口可行的申请/放行与配置成功次序，覆盖两条通路以及带有无关任务的混合请求。验收时在 pre-step 已通过、provider 尚未收到请求的窗口，以及 Inbox 工具已取数、下次请求尚未发出时切换，检查成功时刻后的真实请求和重启后的结果。

**R1-W1 · 现有读取顺序会把渠道收件时间当作原发送时间。** `design.md`「模型实际看到的内容」指向现有 Inbox read 的多渠道时间解析。`packages/personal-assistant/src/external.ts:107` 在飞书 `create_time` 无效时把 `Date.now()` 写进 `message.created_at`；镜像也传此字段。`packages/personal-assistant/src/inbox.ts:499` 优先选这个值。直接复用会使原发送时间未知的消息排在真实消息之前，并使同一条消息在恢复路径上看似有可靠时间。需要规定原始时间可信性的来源与跨镜像保留方式，说明旧条目在仍有原始时间或无法区分补值时如何投影；隔离用例应走缺失/无效渠道原时间的实际适配链。

**R1-W2 · 外部渠道 delta 对镜像、同群批次和命令的适用范围相互冲突。** `specs/gateway/external-channels.md` 的「飞书对话同步到内部 IM」总述仍要求未 @ 群消息写入群背景，按此验收会把“在仅限本人时正确镜像群聊、但没有写入 Agent 背景”的实现判错。「飞书群聊背景上下文等价内部 IM 群聊」又将两种模式均写为“后续同会话高优或十分钟”，漏掉全局根由 B 群高优立即带出 A 群背景的情形。相邻 current 的「群聊新控制命令要求明确 @Bot」仍以已删除的 MENTION 配置为前置（`docs/specs/gateway/external-channels.md:236`）。请明确无条件可镜像与按档位/模式收件的各自条件，修订受影响命令场景；用跨群 Global、同群 SingleThread、仅限本人三种结果对读。

### Recommendations

**R1-R1 ·** 切换到「仅限本人」会永久跳过未递送积压。现有设计只规定帮助文字说明谁能私聊。可在用户改选该项时用一句话说明“尚未递送的团队消息会跳过，切回后也不会补发”，沿用现有保存动作。

### 历史问题闭环

首轮，无前轮 Resolution。本轮证据为现有组装源码、锁定的 DSH 运行时及目标设计，尚未执行产品或部署验证。

### Author Resolutions

- **R1-C1 accepted.** 飞书首次发言人的自动绑定会持久化，不能作为私人收件的身份证据。design「身份事实与优先级」、外部渠道 delta、部署清单和 M1 改为创建者显式确认的 app 范围身份，独立验证旧绑定与创建者不同的序列。
- **R1-C2 accepted.** pre-step 后仍有请求准备与工具结果。design「切换时停止积压」补入 llm/stream 放行与配置保存定序、未出站工具/图片的逐来源处理、重启持久判据和实际 provider 挂起测试。
- **R1-W1 accepted.** 新旧飞书输入仅以可核验的原始发送时间参与聚合，原始时间的可空值穿过镜像；隔离测试覆盖 Date.now 展示补值与原时间缺失。
- **R1-W2 accepted.** 外部渠道 delta 已收窄镜像、背景、两种工作模式的跨群条件并补入命令完整条款。
- **R1-R1 accepted.** 配置选择器在改选时说明旧积压将跳过，沿用原保存动作。

## Round 2

- Reviewer target 为 `/root/design_review`，基线为 `develop` 的 `ea30aea76`。
- `review_mode` 为 `delta`。飞书创建者身份配置与 DSH 请求放行是有界但实质的设计变化，本轮追到通道 manifest、模型请求生成及适配器调用；摘要、设置、迁移与 M1 核对对应改动。
- `started_at` 为 `2026-11-18T17:16:14+09:00`，`completed_at` 为 `2026-11-18T17:18:02+09:00`，`duration` 为 1 分 48 秒。
- **Verdict — Issues Found，1 CRITICAL / 0 WARNING。**

### Coverage 与历史问题闭环

- **R1-C1，accepted，closed。** 设计将私人收件身份改为经创建者认证、限定 agent 与 app 的显式声明。现有管理路径 `apps/im-server/src/channels.ts` 按 owner/agent 查询，通过 per-node manifest 分发，能承载该配置。`im/agents-nodes` 明确缺省与换 app 时的反馈，`gateway/external-channels` 与部署提示词均保留团队自动绑定的原用途。M1 包含同事先发言的反例。
- **R1-C2，accepted，still-open，见 R2-C1。** 登记输入和工具结果来源、以 provider 响应区分已交付与未交付、配置成功前等待已放行的交接，解决了原来时序和覆盖对象不清的问题。新的最终投影落点与锁定版本接口存在直接矛盾。
- **R1-W1，accepted，closed。** 新飞书事件的可空原始 `create_time` 贯穿节点、镜像、中心和 Inbox。旧条目只有在平台原件或原 `source_timestamp` 有可靠值时参与聚合；M1 明确检查缺失和非法时间经过镜像仍为 null。
- **R1-W2，accepted，closed。** 修订后的飞书 delta 允许仅限本人时照常镜像，对 Global 明确任意聊天的高优均可带出背景，对单会话限定原聊天，并保留外部控制 Requirement 的其他 Scenario。
- **R1-R1，accepted，closed。** 改选时展示积压跳过及切回后的后果；可沿用选择器现有保存动作。
- `retained_from: Round 1`。首文档、分类、定时、其他 delta 和单 M1 分工均沿用前轮证据。目标构建、实际 provider 请求和部署仍属于实施期验收。

### Issues

**R2-C1 · `llm/stream` 不能把改写后的请求副本传给现有 adapter。** `design.md`「切换时停止积压」第 75、79 行指定在 `next()` 前替换 messages。锁定的 `@deepseek-ai/dsh-agent-loop` 的 `buildRequest` 会对消息逐个 `deepFreeze`、对数组和整个 options `Object.freeze`。`@deepseek-ai/dsh-llm` 的 `lib/types/index.d.ts:45` 明确约定 `next: () => AsyncIterable<StreamChunk>`，实际 `lib/index.js:2365` 的终点通过闭包将原 options 交给 `adapterStream`。仓内 `InboxDelivery` 可观察请求与响应，但监听器内复制并编辑 messages 后调用 `next()`，原 adapter 依然会收到原内容。对旧请求全部拒发又会丢掉混合请求内的合法工作。请改用已确认支持的公开写入或重建边界，并说明已冻结的请求如何被拒发及重建、合法工具 call/result 如何配对及如何保留原有回执。可优先核对公开 `Session.append` 的模型 surface replacement 和重新构建请求能力；这是一条待作者核实的路径。现有 M1 挂起原生请求、比对实际 provider body 的窗口足以用于实施验收。

### Recommendations

本轮无新增可选项。

### Author Resolutions

- **R2-C1 accepted.** 已核对本仓锁定的 dsh-llm 的冻结请求与零参数 next、dsh-session 的 registerMessageProjection、原生 image-offload 注册范例，以及 dsh-agent-loop 在 error finish 和 agent/request-error 返回 retry 后重新执行 prepareRequest/buildRequest 的路径。design「切换时停止积压」改在可重放的 session surface 投影，最后的 waterfall 只放行或拒发，含合法内容的过时请求由原生 loop 重新构建并保留工具配对。

## Round 3

- Reviewer target 为 `/root/design_review`。基线 `develop` 的 `ea30aea76`。
- `review_mode` 为 `delta`。R3 替换了 R2-C1 的原生请求处理机制，集中复核消息投影、请求拒发、重建与恢复。
- `started_at` 为 `2026-11-18T17:21:40+09:00`，`completed_at` 为 `2026-11-18T17:22:17+09:00`，`duration` 为 37 秒。
- **Verdict — Approved，0 CRITICAL / 0 WARNING。**

### Coverage 与历史问题闭环

- **R2-C1，accepted，closed；R1-C2 同时 closed。** 已沿锁定的 DSH 版本核实三步。首先，`SessionStore.registerMessageProjection` 为 live、restore 和 fork 注册插件事件解释器。`SessionMessageProjection.project` 按原事件序号返回保留身份的不可变消息。原生 `dsh-compaction-image-offload` 用同一接口投影 `user/message` 和 `tool/result`，提供保留 toolCallId 并更新文本、图片的实例。设计以持久取消成员确定允许内容，保留原审计记录。
- 其次，最终 `llm/stream` 遇到过时的冻结请求时结束本地 attempt，跳过通向 adapter 的 `next()`。锁定的 `dsh-agent-loop` 在 `step` 中处理 error finish 时先记录 `assistant/attempt`，经 `agent/request-error` 收到 `{kind:'retry'}` 即重新调用 `prepareRequest` 和 `buildRequest`。`buildRequest` 再读 `session.deriveMessages()`；`firstAttempt` 此时已为 false，原输入不会重复追加。这个次序可同时保留混合请求的合法消息与工具配对，阻止旧对象出站。
- 最后，唯一聊天触发被撤销时走静默退出；已投给 provider 的工作仍按原交接顺序处理。实施期挂起窗口、实际 provider body、有效响应回执、并发工具与复开后去重均有 M1 取证安排。上述结论为设计可实施性判断，运行行为以 M1 结果为准。
- `retained_from: Round 2`。飞书创建者身份、原始时间、外部渠道 delta、设置说明和迁移无需重开；其余需求及 M1 范围沿用前轮证据。

### Issues 与 Recommendations

无未解决发现，无新增建议。

### Author Resolutions

R3 无待处理 findings。独立审查核对的原生投影与请求重建路径和设计一致；真实 provider 请求及重启用例由 M1 验收。受审设计产物此后无改动。
