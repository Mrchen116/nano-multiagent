# bugfix-621 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review_621`（独立 reviewer）
- target: `bugfix-621-pa-feishu-owner`，HEAD `9fa676f00da46100d62074cb9276301f3295fec2`；实现基线 `0fa706a67`
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖 incident、design、全部 delta、M1 与真实组装入口。
- started_at: `2026-10-20T09:49:00+08:00`（报告记录开始；此前已完成源码读取）
- completed_at: `2026-10-20T09:49:18+08:00`
- duration: 报告记录 18 秒；源码阅读时间未单独计时。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING**

### Coverage 与证据

- **当前生产入口与根因**：`apps/node/src/main.ts:276` 装配 ExternalChannels，并把 `personalDelivery` 接到 GlobalAgent；`packages/channels/src/feishu.ts:81` 的真实 SDK 回调保留首次合法来信绑定。`external.ts:91-96` 在 PA 入站中先 await 混合 flush 后直接 receive，而 `global-agent.ts:132-180` 另从持久 observation 接入；所述双入口及输出错误传播方向与代码一致。`messaging.ts:499-520` 的可信 external-incoming、`conversation-actions.ts:20` 的路由提供现有镜像入口，无需新执行循环。
- **主人身份与原始授权**：`personal-agent.ts:25-41` 已有节点绑定与源访问权威；`:108-115` 当前排除 sender_source_id，`:152-165` 当前只查询 canonical Web 主人 DM，设计复用服务端判定分别修复这三处是合理归属。现有 `incomingExternal` 校验 direct source 与 sender_source_id，channel 绑定与 app 身份可复用。方案没有把模型声明或正文作为主人证据，群聊不升级为私聊；符合确认范围。
- **外发与平台目标**：`personal-actions.ts:16-23` 验证当前 channel/source，真实 chatId 来自 `external.ts:187-203` 的本地 ExternalChat；`personal-assistant.ts:164-188` 是既有独立审查与 SDK dispatch 衔接。返回 owner_private 并保留 ExternalStore confirmed/unknown 足以复用现有交付状态。当前 shadow 回复地址在到达这一边界之前仍有未闭合分支，见 R1-W1。
- **单入口和恢复**：设计明确中央原始消息 ID、持久事件、输入镜像与输出 flush 分离，覆盖旧输出失败和重放。实施需兑现 `global-agent.ts:151-156` 的 observation 资料构造，保留真实来源、发送者和时间；这属于已明确要求的接口实现，不另设新需求。一般 Agent 既有 receive 不需改为中央准入。
- **架构判断**：身份与授权属于 IM PersonalAgents；实际平台地址、发送回执和输入输出恢复属于 PA ExternalChannels/ExternalStore；DSH 只执行既有主会话/调度。复用三者优于另加主人注册流程或调度服务，也符合 `SPEC.md` 的包依赖与唯一执行运行时约束。中央离线时 PA 保留输入是当前 PA 准入事实的明确化，一般 Agent 离线自治仍须保留。
- **契约增量**：两个 delta 的 canonical target 均存在，新增跨渠道交办、实际送达、单一接入与失败隔离匹配消费者行为；外部渠道 MODIFIED 条目未保留原 Scenario，见 R1-W2。现有 `docs/specs/gateway/personal-agent.md` 已规定主人私聊免 PA 审核，与此次具体化不冲突。
- **Milestone 与验收**：单一 M1 串行修改 IM 与 PA，没有并行编辑冲突；退出条件包含真实飞书用户来信、回复、一次性提醒实际送达和 Web 回归，并把非主人/群、原始授权和失败去重交给定向回归，范围合适。无客户端 UI 改动，不要求原型验收。已确认本地探针和专用配置文件存在；本 reviewer 未启动测试栈，未声称已验证真实收发。
- **验收资源补充**：主 agent 在本轮提供了新的资源核查结果：专用 `e2e-feishu-testagent` Bot/app 已验证，user refresh token 过期；已登录的本机飞书客户端存在“测试agent”私聊，可用该客户端发真实用户消息，Bot API 读取回复和提醒。此为作者提供的前置证据，本 reviewer 未独立操作客户端。该方式仍符合真实 SDK 入站要求，最终 runbook 应以此已可用驱动替换“有效用户 API 授权”的失效假设，不把 API token 续期当成必要产品改动。

### 历史问题闭环

首轮，无历史 issue。

### Issues

#### R1-W1：shadow 地址尚未在 PA send_message 分派层进入飞书发送路径

- **位置**：`design.md:32,40`。
- **证据**：设计决定 observation 以中央 shadow conversation 作为回复地址，并只在 ExternalChannels 的 `agent.message` 接口扩展 shadow 解析。实际 `global-agent.ts:325` 会优先调用 `PersonalAssistant.send`；`personal-assistant.ts:113-119` 仅 external 前缀直接发送 `agent.message`，中央 `c_*` shadow 由 `resolve` 原样返回。随后 `:135-145` 进入无 transport 的 `pa.action.prepare` 与披露审查，允许后在 `:155` 提交 IM 消息，根本未调用 ExternalChannels 的 agent.message。因此仅完成所列 alias 扩展，按 Inbox 来源地址回复仍可能遭披露审查，或只写进 IM 而没有飞书平台发送。
- **未修后果**：新主入口可成功读入主人请求，但自然地向 shadow 地址回复/定时提醒时，无法兑现本次最核心的“原单聊送达且免披露审查”。
- **所需收口**：在设计中明确 PA send_message 的目标归一化责任：在选择 Web/外部发送分支前，通过已有可信映射识别 shadow 对应的 external target，再进入既有 external delivery 和 owner_private 判断。不能仅放宽 IM shadow 写权限或要求模型自行换地址。验证应直接用 observation/Inbox 提供的 shadow target 调用 send_message，确认返回真实平台回执；external target 与 Web canonical target 同时回归。

#### R1-W2：MODIFIED 离线契约遗漏现有两个 Scenario

- **位置**：`specs/gateway/external-channels.md:20-22`。
- **证据**：`docs/specs/CONTRIBUTING.md:133-154` 要求 MODIFIED 为完整替换条目；当前 canonical `docs/specs/gateway/external-channels.md:393-407` 包含普通 Agent 的飞书 1:1 离线回复和群 @Bot 离线回复两个 Scenario。delta 仅保留一句概括，没有任何 Scenario。
- **未修后果**：按既定归并规则会删除未改变的普通 Agent 离线验收场景，也没有把 PA 等待中央恢复的新增分支落成可验收契约。
- **所需收口**：保留并限定原有两个 Scenario 为普通 Agent；补充 PA 中央不可用时持久保留、恢复后单次接入的 Scenario。无需扩展离线执行能力。

### Recommendations

无额外产品范围建议。验收驱动资源按上文补充事实更新即可，不需要为了过期 user token 新增认证机制。

### Author Resolutions

- R1-W1 — accepted。design 接口与数据流明确 PersonalAssistant.send 分派前使用 NodeStore 可信 alias 归一化，并要求 shadow target 真实平台回执回归。ExternalStore.chat 已支持 shadow 查找，不重复新增。
- R1-W2 — accepted。MODIFIED 完整保留普通 Agent 两个离线 Scenario，并补充 PA 中央恢复单次接入 Scenario。
- 验收前置 — accepted。runbook 记载真实客户端可替代用户 API 发送；用户已主动协助续期专用 profile 授权。

## Round 2

### Metadata

- reviewer: `/root/design_review_621`（与 R1 相同的独立 reviewer）
- target: HEAD `869cdf6108481c77f9977a9c0b8cce79f485faf6`
- review_mode: `closure`
- mode_reason: 相对 R1 的实质修改限于既定目标归一化落点、遗漏 Scenario 的恢复与验收资源澄清；未改变需求、职责边界、执行主链或 milestone，按旧问题闭环复核。
- started_at: `2026-10-20T09:52:49+08:00`（本轮证据确认时间）
- completed_at: `2026-10-20T09:53:02+08:00`
- duration: 13 秒；此前已读完本轮文档 diff。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- 已检查 `9fa676f00..869cdf610` 全部文件差异，只有 design、external-channels delta 和审查记录；incident、global-agent delta、M1 和实现未改。
- retained_from: **Round 1**。主人绑定、原始授权、单入口、失败隔离、免披露审查的可信边界、普通工具权限与架构职责保留 R1 已覆盖证据，修订未扩大相关范围。
- runbook 已纳入真实飞书客户端发送的替代路径，仍要求 SDK 入站、真实模型执行、回复与提醒平台回执/读取。主 agent 另报告专用 CLI 授权已由用户续期且缺失 scope 为空；该状态是作者本轮提供的前置事实，本 reviewer 未自行认证或执行收发，不把授权完成当成产品验收完成。

### 历史问题闭环

#### R1-W1 — closed

- **Author Resolution**：在 PersonalAssistant.send 选择 Web/外部分支前使用 NodeStore 既有 alias 归一化 shadow target，并直接回归 Inbox shadow target 的平台回执。
- **本轮证据**：`design.md:40` 已明确该责任和处理顺序。`store.ts:76-77` 的 `aliasConversation` 持久保存按 agent 隔离的 alias→canonical 映射，`:93-94` 已有同方向查询；`external.ts:241` 在镜像创建后写入 shadow→external 映射；`external-store.ts:25-27` 原本就支持 shadow 查找。该方案能在原先 `personal-assistant.ts:113-119` 分支之前解决地址，复用现有外发边界且保留 Web canonical 路径，不再依赖模型主动更换地址。
- 当前 NodeStore 的 canonicalConversation 为 private，实施需将既有查询封装为可供 PA 调用的受限方法；这是已确定职责内的小接口落实，不构成额外设计决定或新的阻断。

#### R1-W2 — closed

- **Author Resolution**：完整保留普通 Agent 两个离线 Scenario，补充 PA 等待中央恢复的单次接入场景。
- **本轮证据**：`specs/gateway/external-channels.md:24-34` 保留原 1:1 与群 @Bot 的 WHEN/THEN/AND，GIVEN 明确普通 Agent；`:36-39` 定义 PA 本地持久保留、中央恢复后授权可验证再单次接入。满足 MODIFIED 完整替换规则，也与 design 的中央准入决定一致。

### Issues

无未关闭问题。

### Recommendations

无。Gate 2 通过仅表示设计可实施；真实飞书收发、一次性提醒送达及权限回归仍须按 M1 验收。
