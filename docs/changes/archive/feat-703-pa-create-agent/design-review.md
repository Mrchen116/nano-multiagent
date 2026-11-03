# feat-703 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design_review_703`，独立 reviewer；非方案作者。
- review_mode: `full`
- mode_reason: Gate 2 R1；首次完整审查首文档、design、delta-spec 与 milestone，并执行 Agent Context Review Mode A。
- started_at: `2026-11-03T16:33:11+08:00`（结论整理阶段起点；此前已读取受审材料与 owning code）
- completed_at: `2026-11-03T16:34:42+08:00`
- duration: `91 seconds`（结论整理阶段）
- validated_at: `2026-11-03T16:34:42+08:00`
- executed_base: `5b333d28e78f04476f5d4ba5be89c86678b6b85e`，detached HEAD；开始时工作区 clean。
- reviewed_scope: `spec.md`、`design.md`、`specs/gateway/personal-agent.md`、`specs/im/personal-agent.md`、`M1-create/.gitkeep`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案具备可实施的职责分工、用户行为边界和恢复路径。以下为设计判断，不表示聊天创建能力已实现或已通过真实模型验收。Recommendations 为实施建议，不作为额外 Gate。

### Coverage 与证据

#### 现状与实际组装入口

- `apps/im-server/src/control-routes.ts:201-225` 的 node capabilities 路径经 owner 验证、`catalogReads(ctx)`、绑定/连接 fencing 后投影候选；`255-315` 的创建路径使用共享 `configurationOperations(ctx)` 队列，冻结省略 Skills 的默认值、补齐 Feature 依赖并匹配 pending create。design 要求提取这些语义为 Web/PA 共用能力，现状依据成立。不能只复用最底层 `ops.create` 而遗漏准备与目录投影；方案已明确保留这些语义。
- `apps/im-server/src/configuration-assembly.ts` 以 ImContext 为作用域共享 `ConfigOperations`；`control.ts:175-253,314-348,424-500` 持有 per-Agent 队列、持久 operation、Gateway 回执和 profile commit。新增关联表只建立 PA 请求到实际 operation 的索引，不复制 apply 状态机；预分配 operation ID 是对现有插入路径的有界扩展。
- `packages/dsh-integration/src/product-bridge.ts` 注入真实根 session/Agent/owner，`packages/personal-assistant/src/global-agent.ts:469-503` 复核绑定并路由产品调用；`personal-assistant.ts:23-29` 经 Channels 发出 host-only PA 请求。`apps/im-server/src/gateway.ts:420-423` 将 pa.* 交给 `PersonalAgents.handle`，后者经有效节点 binding 派生 owner。方案的原生工具 → 产品层 → 中心 authority → 目标节点配置链可在当前架构内接通，无需 PA/IM import DSH。
- `apps/im-server/src/personal-agent.ts:141-162,279-283` 的 `ownerMessage` 排除代发，要求可信主人、PA participant 及 DM/明确寻址群聊，同时检查当前读取资格。design 复用该来源检查、将原话语义交给主 PA 与普通工具权限，符合 current PA 契约；不错误声称 ownerMessage 本身能证明“同意创建”的文本语义。
- `apps/node/src/configuration.ts:105-112` 为实际 Agent 配置 Skill 选择及随包目录；`packages/dsh-integration/src/personal-security.ts` 已以 PA 配置注册来源工具和固定身份指导。`capabilities.ts:59-77` 负责工具选择和 child 限制。新增工具必须沿这些真实装配面注册与隔离，不能只在测试或目录里存在；design 的分层拒绝和原生请求证据要求覆盖了这一点。

#### 需求、决定与职责

- 用户明确交办、先问清相关选项、接受推荐后不重复批准、本机推荐/明确选机不替换、长期独立 Agent 及当前聊天反馈，均由设计流程 1–5 与 M1 退出标准承接。
- 用户选定的 1 Skill + 1 固定短 schema 工具已收口；options/create/status 共入口，不引入通用搜索、动态工具挂载、DSH 升级或客户端改造。
- 新 Agent 配置由 IM 既有管理面与 Gateway 配置 owner 处理；Skill 负责行动指导，工具负责已声明动作。共享服务提取避免 Web/PA 双份默认与校验逻辑，新增表的维护成本限于请求关联，未发现会迫使下游另建状态机的设计缺口。
- 同 key 冲突、实际 operation 绑定、未知结果查原操作、Gateway apply 后 IM commit 才返回 created，覆盖重复/重启/ACK 丢失及同 ID 无关 Agent 的误认风险。提交前撤回与已接受操作的实际状态被区分，未承诺不存在的撤销能力。

#### Agent Context Review — Mode A

Consumer 为主 PA；涉及工具定义/结果、Skill 发现/正文、来源消息和普通历史恢复。审查版本即 executed_base 的设计材料。

- **可发现与渐进披露：** 常驻入口保留 Skill 加载及最少约束；字段解释与节点真实候选由 options 提供。普通聊天不自动展开向导。Skill 沿现有选择/禁用机制，无法加载时明确说明，未通过默认注入全文规避禁用。
- **参数来源：** owner/binding/epoch/session 来自宿主；目标节点来自 options 的 owner-scoped 目录，配置来自真实候选与用户选择；source_message_id 来自普通 Inbox/历史中的原消息。request_key 是同次业务请求关联，不能退化成每次 tool call 都改变的执行 ID；方案已要求同次请求/恢复保持不变。
- **来源与权限：** options 不是创建授权，观察、他人消息和 PA 代发不能建立新授权；runtime、PA 产品层与 IM 各自承接主 PA/owner/节点边界。child 和普通 Agent 无此管理能力。
- **结果及下一步：** not_started/pending/created/rejected 区分未开始、未知/待确认和真实完成；pending 必须查原 key/operation。字段错误保留原因，不能通过自动换节点或新 key 绕过。工具历史、Skill 和请求关联的恢复分别沿既有机制，未将历史资料当成新增授权。
- **验证：** design:79、M1 退出标准要求原生请求中的 schema、Skill 目录/正文、结果与实际产品状态，并要求正常聊天输入的真实模型旅程；fixture 不替代模型选择证据。这足以使交付与行为在实施后被独立检查。
- **限制：** 本轮未生成最终工具/Skill 文案，未启动模型或服务；参数填写、schema 稳定及历史恢复的实际行为仍须实施后证据证明。没有把设计可行性推断成模型已可靠执行。

#### Delta、milestone 与验收前置

- 两份 delta 均为 ADDED Requirements，分别锚定现有 Gateway/IM `personal-agent.md`；未替换原有 Requirement，故无遗漏 MODIFIED 旧 Scenario 问题。既有普通 Agent 创建契约仍由 `im/agents-nodes.md` 承载，不重复维护。
- M1 是单一用户闭环，包含共享 Web 创建/目录回归、来源/child/越权、同 key 与恢复、原生 Context 和真实模型行为证据；`M1-create/` 仅 `.gitkeep`，未提前伪造 tasks/progress。
- 无 Web/iOS 页面变化；既有聊天、Agent 列表与配置页为消费者入口，无需新原型。未进行视觉/产品实现验收。
- Runbook 采用隔离日常模板和现有聊天 HTTP 接口驱动真实 PA，保留真实模型、数据/端口/workspace/身份隔离及停服要求。没有把未完成验收推迟生产或要求生产写入演练。
- 新表走既有 schema 初始化，无一次性人工迁移、依赖升级或旧 Prompt/Skills 覆写；不要求 deployment-prompt.md。回退保留已创建 Agent、工作区及回执，边界合理。

### 历史问题闭环

R1，无历史问题。

### Issues

无。

### Recommendations

#### R1-R1 — 实施时显式区分目标电脑与 PA 传输身份

- 位置：`design.md:59-69`；`packages/personal-assistant/src/personal-assistant.ts:23-29`。
- Context Surface：工具参数 → host-only PA 请求；目标电脑是模型从 options 选择的对象，PA 所在电脑是可信宿主身份。
- 证据与影响：现有 `PersonalAssistant.request` 在展开 args 后写入宿主 `node_id`；直接把工具的目标 `node_id` 原样传入该 helper 会被覆盖。设计已明确“可信身份和创建请求分开”，因此这不是尚未收口的产品/架构决定，但实施不能忽略该适配。
- 建议：在新动作的传输适配中把目标放到独立字段（例如 `target_node_id`），保持 envelope 的 `node_id` 为 PA 宿主；增加本人另一在线节点的 options/create 成功验证，确认显式选择跨过 helper 后仍指向该节点。不能为目标选机改写 principal 或绕过当前 binding authority。
- evidence_status: CONFIRMED（现有 helper 的覆盖行为）；未声称未来实现已经存在错误。

### Author Resolutions

- R1-R1: accepted。产品层将工具的目标 `node_id` 映射为 `target_node_id`，传输的 `node_id` 仍由 PersonalAssistant.request 注入真实 PA 所在节点；IM 单独校验目标节点归属。M1 增加本人另一节点的成功创建覆盖。该项是已批准身份/目标分离的接线澄清，不改变设计接口、范围或权限。
- R1 已核实，无存活 CRITICAL/WARNING；保留 Approved 结论。后续实质变化按影响复审。
