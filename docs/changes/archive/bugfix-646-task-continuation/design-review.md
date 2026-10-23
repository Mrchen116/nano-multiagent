# bugfix-646 Design Review

## Round 1

### Metadata

- reviewer target: 独立 reviewer `/root/design_review_646`，继承派发方模型与 effort；未参与受审设计编写。
- review_mode: full
- mode_reason: 首轮 Gate 2；覆盖 incident、设计、全部 delta、M1 骨架，并从实际产品组装与锁定 DSH 公开 API 核实关键假设。
- started_at: 2026-10-23T22:49:11+08:00
- completed_at: 2026-10-23T22:53:20+08:00
- duration: 4m09s（以首次记录的时钟为计时起点，前置阅读不计入此时长）。
- validated_at / executed_base: main `236a4698c7a8a2d03efa00c35049914d2422771d`。派发记录为 `fea4bfcfe`；实际新 HEAD 仅追加 bugfix-644 文档提交，本轮依据实际文件独立审查。受审 design/deltas 为下列未提交文件；未修改其他 unit 或实现、未提交/推送。

受审文件 SHA-256：

| 文件（相对本 unit） | SHA-256 |
|---|---|
| incident.md | `78d6da96aa4c3641435df907cc40b1c2d977fe817a76a6d3d2e07bf7747eabc5` |
| design.md | `b21e68f4429d7a894f8b14ffca0124bd3bb15ac768b34d9377496652b4d4fd4b` |
| specs/gateway/global-agent.md | `feb7948d02a2de2a6fc93d0806ecee02d2490a463c0a32ad5d532eea00e69124` |
| specs/gateway/task-graphs.md | `4bda17ff529b48e6261a2b1b7a3c2add1c327140b62463a645915f5ed24c0dee` |
| M1-continuation/.gitkeep | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 未通过。**

整体责任分配与用户方向一致，但成功状态变更后的反馈依赖了不存在的 mutation 返回字段，拒绝恢复投影也依赖了快照没有提供的内容；这两处需要先关闭接口决定。Global delta 另有未授权的既有契约丢失。

### Coverage 与证据

1. **需求与范围。** 已逐项核对 incident 的多责任推进、合法替代、真实 waiting、一小时上限、固定原聊天反馈、失败诚实性、相关恢复及 Global 非空私有收尾。design 第 36–48 行与目标整体一致；没有引入 Task 预算、第二循环、审批豁免、人类专属恢复或替其他聊天选择收件人。feat-645 配置映射、生产部署、历史超长 waiting 迁移继续在范围外。
2. **真实组装。** `packages/dsh-integration/src/index.ts:164` 实例化 TaskExecutionDriver，`agent-config.ts:168` 注册 TaskGraphs feature；`product-bridge.ts` 沿绑定身份调用产品 RPC，`packages/personal-assistant/src/global-agent.ts:440–460` 将真实 Task command 返回包装为 `{ok,result}`。`packages/personal-assistant/src/task-execution.ts:24–45` 产生责任快照。没有把测试替身当作产品入口；但 mutation 结果的字段断言不成立，见 R1-W1。
3. **原生接口与架构判断。** 锁定安装包 `@deepseek-ai/dsh-tools@0.2.1-alpha.1` 的 package exports 对外暴露主入口；其 `lib/types/index.d.ts:216–239` 的 ToolExecutionInput 提供 name、arguments、callId、agent，`:299–312` 提供 ToolRunContext.deferContext，`:412–445` 区分 canonical success/value 与 failure。`@deepseek-ai/dsh-user-approval` 的 ApprovalRequestEvent 只有 toolName/可选 callId 等，不含完整参数；因此动作级拒绝记录应从 tools 事件或关联到该公开执行事实取得，不能把 approval/request 当有完整 args 的接口。公开能力足以实现设计，无需 private import 或补丁。Task 事实与 waiting 校验留在 IM、产品身份/投递留在 PA、原生 admission/提示留在 integration，符合 SPEC.md 的职责与依赖方向。复用原生 inbox、Schedule、现有 publication 优于新增调度器、投递账本或 Task phase 镜像；私有抑制状态应只表达 admission，不成为第二份业务真相。
4. **参考基线。** 只读核实本地 DSH checkout 为 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，阅读 goal-round-driver `src/prompt.ts` 与 tool-goal `src/wrapup.ts`。检查当前工作区/工具结果、具体推进并验证以及工具后 deferContext 均有真实来源；没有照搬上游“停止后所有工具禁止、只向用户收尾”的单 Goal 语义，符合本 unit 多 Task 与固定所属聊天约束。
5. **waiting 与失败链。** IM `task-graphs.ts:500–525` 先查询真实 Schedule evidence，`:801–810` 在同步事务内检查，`:448–464` 失败回滚；在这两个既有位置加 cap 能保持原子性。integration `index.ts:550–558` 已按 agent/session、active 与 scheduledAt 核验，普通 Schedule API 无需全局加限。PA `global-agent.ts:495–594` 已持有 prepared/sending/confirmed/held/unknown 与查询确认链；设计保留未知结果和原请求身份，不将等待失败伪装成功。driver 当前 `task-execution.ts` 的普通输入清除和同名成功清除确实存在，修正具有实际依据；内容级恢复的取证接口仍需明确，见 R1-W2。snapshot unavailable、flush 和 agent 错误要按设计保留为运行故障，而非空责任或业务成功。
6. **delta 与消费者。** Task delta 锚定 Gateway current 的自动推进/等待/审批交付契约；IM 页面未增加新的设置交互，无须以原型补足前端设计。Global MODIFIED 命中了正确 Requirement，但未完整保留未修改的空响应恢复行为，见 R1-W3。现有 IM waiting 展示及本人/会话边界不应被本次误改。
7. **验收与 milestone。** M1 仅有 `.gitkeep`，单 milestone 覆盖这条纵向链路合理，未预填实施记录。runbook 的 `e2e-up.sh --main-config`、专用 nano 用户、独立 node identity/workspace/home 等与脚本真实能力相符（脚本第 181–202 行重新物化隔离配置）。通过真实模型和 API 验证聊天历史、Task 与工具结果，对无客户端变化的本 unit 足够；它不是当前已通过的产品验收。必须落实同图双任务、跨聊天原目标、首次/续期、提前恢复、停止后定时器、反馈未知和普通参数修复；本轮不启动产品栈、不声称真实模型旅程通过。两个接口修订后，相关回归应覆盖其失败路径。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 成功提醒消费的 mutation 返回字段不存在

- 位置：design.md:13、40、53。
- 证据：`apps/im-server/src/task-graphs.ts:345–361` 的 `summary()` 只有 graph/root/revision、根节点摘要和入口，没有 `nodes` 或 `conversation_id`；apply 在 `:782–786` 返回该摘要加 `client_refs/changed_ids`，`:810` 再合并的仍是 summary。PA `global-agent.ts:455–456` 只是原样包装，`tool-references.ts:111` 也未补齐字段。设计声称“原返回协议不变”却直接读取 `result.nodes` 和固定聊天无法成立，且根摘要不能代替被改子节点。
- 后果：实现若遵循当前稿，会漏掉子节点 waiting/in_review/done 提醒，或在无法取得权威目标时错误使用最近聊天，核心反馈旅程无法落地。
- 关闭要求：选定一个真实可用的取证接口并写清责任归属，例如成功 apply 后按同一产品身份读取图，或显式给 mutation receipt 增加最小服务端投影；说明读取失败、状态已再次变化、receipt 重放时哪些内容可以作为本次成功事实，不能以请求参数推定已经提交的状态或固定收件人。保持写入已成功这一事实，即使后续读取失败也不能把成功写入重新解释为未提交。验收至少覆盖子节点、跨聊天和取证失败。

#### R1-W2 — 拒绝恢复要求的“实际内容变化”不在保留形状的 snapshot 中

- 位置：design.md:44、52。
- 证据：`packages/product-contracts/src/task-execution.ts:19–29` 的 TaskResponsibility 仅有 title/status/revision/conversation/wait/resume_request 等字段；PA `task-execution.ts:36` 显式裁去其他节点内容。设计要求排除整图 revision、纳入“实际内容变化”，同时声明 snapshot 对外形状不变，却未指定另一个可观察的内容版本或读取通道。
- 后果：修改同一任务正文/约束但标题、status、wait 不变时，责任投影仍完全相同，真实相关变化不能解除旧阻挡；如果实施者反向使用整图 revision 弥补，则同图其他节点修改又会无条件恢复旧拒绝，重现所修问题。
- 关闭要求：明确“实质变化”的可获取字段及缺失内容的处理方式，并选定能区分同节点内容修改与无关节点修改的证据来源；可以扩充最小投影或复用现有读取能力，但不能只在文案中承诺。至少要求一对回归：旧被拒绝任务正文变化允许重新评估；同图其他节点变化不解除该屏障。重新评估不等于审批授权。

#### R1-W3 — Global MODIFIED delta 丢失既有空响应重试与耗尽失败契约

- 位置：specs/gateway/global-agent.md 的“模型空返回”Scenario。
- 证据：canonical `docs/specs/gateway/global-agent.md:257–259` 明确“使用运行时既有重试策略恢复，耗尽后报告失败”；本次替换正文仅要求“作为空响应失败处理”，未保留恢复策略。incident 和 design 均未授权改变既有空响应重试机制。
- 后果：按 MODIFIED 整段归并后，这一既有用户可观察保证会从 current spec 消失，下游可能把第一回空响应直接当最终故障而仍声称满足新契约。
- 关闭要求：保留原空响应重试、耗尽失败语义，仅在内部收尾场景补充 Global/SingleThread 与交互卡片的模式区别；除非确有新的用户决定，不扩大本 unit 范围。

### Recommendations

#### R1-R1 — 在实施落点中注明生成提示的源文件

design 已要求 shared 提示与 Skill 同步；建议明确 `scripts/generate-interactive-ui.ts:12` 的 Skill 前言和 `src/IM/frontend/src/features/chat/interactive/catalog.tsx:64` 的 composition guide 都含 NO_REPLY，生成器同时输出 integration prompt 与 Skill。应改源并重新生成，避免只改生成物后被后续生成覆盖。此项是实施定位建议，不另行阻断。

### Author Resolutions

- R1-W1 accepted：design 关键决策 3 / 接口与数据流采用 IM 提交事务内最小 `result.feedback`，随 receipt 持久化，包含固定 conversation_id 与成功 changed nodes；不追加依赖 get 的取证环节。写入 unknown 不注入成功；重放和后续变更有明确语义。scope 与 M1 同步扩充此落点。
- R1-W2 accepted：TaskResponsibility 最小投影保留现有节点 updated_at（IM list 已返回，PA 之前裁去）；拒绝恢复比较节点字段，排除图 revision，分别测试本节点正文修改和其他节点变化。无需新持久版本或加载所有正文。
- R1-W3 accepted：Global MODIFIED delta 原样保留空响应重试与耗尽失败 Scenario，仅修改私有收尾模式区分。
- R1-R1 accepted：design 涉及范围明确 catalogue.tsx 和 generate-interactive-ui.ts 两个源头及重生成产物；无客户端交互变更。

以上为接口事实修订及遗漏修复，incident 和用户决定不变；受审 design 与 Global delta 冻结后交独立复审。

## Round 2

### Metadata

- reviewer target: 原独立 reviewer `/root/design_review_646`；未参与受审设计修订。
- review_mode: full
- mode_reason: 虽由 R1 findings 驱动，实际修订新增共享 TaskResponsibility 字段及 IM mutation feedback 返回，并扩充 M1 范围，依 skill 对共享接口/milestone 变化执行 full；旧轮证据可复核且源码基线未变，不机械重跑无关调查。
- started_at: 2026-10-23T22:56:31+08:00
- completed_at: 2026-10-23T22:58:28+08:00
- duration: 117s
- validated_at / executed_base: main `236a4698c7a8a2d03efa00c35049914d2422771d`；实现仍未开始，本轮仅审设计。仅追加本报告，未提交或改动其他文件。

受审文件 SHA-256：

| 文件（相对本 unit） | SHA-256 |
|---|---|
| incident.md | `78d6da96aa4c3641435df907cc40b1c2d977fe817a76a6d3d2e07bf7747eabc5` |
| design.md | `86dfde51ce9c29123604911dd9565299d72e6d772bd930e3a218702962a7c371` |
| specs/gateway/global-agent.md | `17097a6111e3c253d4082f059ed5b3ecd32e5ed55e24cf1574fdd1e5bf6ca562` |
| specs/gateway/task-graphs.md | `4bda17ff529b48e6261a2b1b7a3c2add1c327140b62463a645915f5ed24c0dee` |
| M1-continuation/.gitkeep | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

三个 R1 WARNING 均关闭；接口事实已纠正，设计可以进入实施。此结论不代表实现、真实模型验收或生产部署已经完成。

### Coverage 与证据

- **需求、范围及决策完整性：** 重读 incident 全部 Requirement/Scenario 与最新 design。事实推进、合法替代、一小时首次/续期、固定原聊天、非空私有收尾、独立任务继续及故障停止仍全部映射到 design 第 36–55 行；没有借反馈投影增加自动外发旁路，没有恢复预算、第二 Agent Loop、审批白名单或历史迁移。incident 与 Task delta 哈希未变，用户约束 retained_from: Round 1。
- **实际组装与公开 API：** 复核 integration `index.ts:164`、`agent-config.ts:168` 的真实 driver/feature 装配；`ProductBridge` 与 PA Task command 包装保持原身份链；`tool-references.ts:111` 的结果投影保留新增对象字段，不会裁掉 feedback。锁定公开 `ToolRunContext.deferContext` 文档仍明确在最终 tool/result 后追加上下文，支持本方案；R1 的事件参数/原生 inbox 和 Schedule 证据 retained_from: Round 1，源码与依赖未变。
- **新共享接口与架构职责：** feedback 在 IM 事务中产生，复用现成 receipt JSON，不新增表、第二份发送状态或额外查询失败依赖。IM 的 `task-graphs.ts:801–814` 已有真实 wait 规范化、保存和 receipt 顺序；`:918–921` 持久化整个 result，`:639–643` 在权限及请求哈希核对后原样重放，因此可以让反馈表达该次提交事实而非伪称最新状态。PA 仅透传；integration 仅提示；实际发送、审批和确认仍由原链路执行，责任归属合理。
- **恢复投影：** 独立核实 `task-graphs.ts:269–284` 的 update_task 将本节点加入 changed，`:316–329` 只为 changed 节点更新 updated_at；`:958–963` 的 list 从节点 n.updated_at 覆盖图摘要时间，execution 分支 `:585–588` 复用此 list。新设计可通过 PA 保留这个现成字段区分正文编辑与其他节点变化，不需加载所有正文或新建持久版本。updated_at 仅用作重新评估信号，设计明确保留独立审批；它不被当作新授权。
- **失败/恢复及等待边界：** 成功反馈只取已校验写入值；unknown 不注入，旧 receipt 不驱动重开，已确认相同交付不重发，符合 incident。业务校验可修复、共享运行错误停止自动调度、拒绝动作记录与新输入处理分离，未因两处接口修订被改回旧逻辑。waiting cap 仍落在异步 evidence 与同步事务复检，普通 Schedule 不受 Task cap；相应证据 retained_from: Round 1。
- **delta 与既有行为：** Global 空响应 Scenario 已与 canonical 第 257–259 行一致保留，内部收尾场景只增加模式区分。Task delta 的四个 ADDED Requirements 与既有 Gateway current 的责任、waiting、停止和交付链没有冲突。无客户端体验变化；catalogue 仅作为模型指导文本源修改，不需新增视觉原型。
- **M1、可验证性与 runbook：** M1 现在明确包括 product-contracts 字段、PA 保留、IM 提交反馈和生成源，边界与实现责任匹配；骨架仍仅 .gitkeep。design 第 52–53 行明确新增同节点正文/同图其他节点成对回归，以及子节点、跨聊天、失败未知、receipt 重放和更晚状态覆盖。runbook 的真实模型双任务、等待恢复、提前回复、停止与不刷屏旅程保留；隔离脚本核验 retained_from: Round 1。审批/持久化故障仍要求永久测试证据，正常旅程仍需真实 provider，不能以此设计审查代替。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核实与结论 |
|---|---|---|
| R1-W1 | 采用事务内最小 result.feedback，保存进 receipt；明确 unknown/重放/后续变更 | design:40、53 已指定固定 conversation_id、changed waiting/in_review/done 节点及校验后的 wait；真实事务、receipt 和 PA 透传均支持该形状。**closed** |
| R1-W2 | TaskResponsibility 保留节点 updated_at，排除整图 revision，增加成对回归 | design:44、52 与真实 list/execution 的节点时间来源一致，PA 原裁剪位置已明确，M1 包含共享字段落点。**closed** |
| R1-W3 | 保留原空响应重试、耗尽失败 Scenario | 最新 Global delta 与 canonical 原 Scenario 一致，不扩大失败策略变更范围。**closed** |
| R1-R1 | 明确 catalogue 和生成器两处源头、重生成产物 | design:13 记录 `catalog.tsx`、`generate-interactive-ui.ts`，M1 同步纳入。**addressed** |

### Issues

无未解决 CRITICAL / WARNING。

### Recommendations

无新增建议。

## Round 3

### Metadata

- reviewer target: 原独立 reviewer `/root/design_review_646`；本轮只审实施期设计补充，不承担实现或测试结果审查。
- review_mode: delta
- mode_reason: 有界补充原审核模型参数选择、Task 拒绝归属规则和验收健康入口；不改变公共数据结构、产品目标、审批规则或 milestone 划分。依据派发要求仅复核这三处及新增 capability delta，Round 2 未受影响结论保留。
- started_at: 2026-10-23T23:34:26+08:00
- completed_at: 2026-10-23T23:36:09+08:00
- duration: 103s
- validated_at: `unit/bugfix-646`，HEAD `1d8508030fa329d0b56db383aaf470b0460f9ece` 加本轮设计补充工作区；位置 `.worktrees/unit-bugfix-646`。源码 dirty 保留，本轮没有审查或更改这些实现 diff。
- reviewed SHA-256: design.md `a9be545fcaa00061dc1483840e53db932dcb7e0b58a7ce23144894f13112a82c`；specs/gateway/agent-capabilities.md `8e3b12d5a91fc1cff39415548363b43270ac18e30bcb931f3a848ec017e4d043`。
- effective_through: `e2219e12b89b581fbd1808ad768f78c72090c081`；主任务提交后复核两份受审设计文件哈希均未变化，因此保留本轮设计结论，不扩展为对该实现提交的代码评价。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

三处设计补充可以实施。Round 2 对原有 Task/Global 设计的批准保持；本轮不替代代码审查、测试、真实模型验收，也不表示获准生产部署。

### Coverage 与证据

1. **审核模型推理能力。** design Changelog 和新 capability delta 明确支持 low 时仍用 low，否则使用原模型 default/首档，未声明可调能力不强设 low；保留相同 provider/model、完整适用证据、判定规则与失败分流。当前 canonical `docs/specs/gateway/agent-capabilities.md:163–175` 将 reasoning 能力归属到精确模型；同文 `:557–560、573–576` 要求超窗与无有效判定继续原失败路径、不换审核模型。新增 ADDED Requirement 与这些契约一致，也不触碰 feat-645 的 Feature/Tool 开关。
2. **能力来源与职责。** 锁定 DSH 公开 `dsh-llm/lib/types/types.d.ts:340–357、381–383、493–494` 提供精确 provider/model 的 efforts、defaultEffort 及请求 reasoningEffort；已有 `personal-security.ts:119` 的 disclosure 选择规则是可复用先例。以公开模型元信息选择合法参数，不需修改 adapter、模型目录或安全规则。HEAD 原 Nano classifier `:28` 的 low 硬编码也证明该修订有具体落点。本轮将“真实模型验收发现错误”视为 implementation.md 的来源记录，没有重跑该实验或将其当作已验收结果。
3. **依赖端点与删除范围。** `features/task-graph-schema.ts:95、176–180` 明确依赖操作使用 from/to；现有 IM `task-graphs.ts` 对该操作将两端加入 changed，因此拒绝归属包含两端符合真实操作影响。相同文件 `:721–757` 的 delete 按 container 后代展开，而 TaskResponsibility 仍不带层级关系；只凭最小快照不能可靠定位删除后代。设计使用“当前图责任批次”而非伪造精确节点集，保留其他图与新增独立责任、新输入及当前轮合法替代，不改业务状态、不当作授权。复用已有批次屏障比为拒绝归属新增层级查询/缓存更适合当前需求；其范围代价已明确为同图当前批次的保守自动抑制。
4. **Runbook。** `apps/im-server/src/control.ts:716–724` 实际注册 GET /im/v1/agents，先验证 user(req)，并返回带 node_status 的本人可访问 Agent 投影。用认证该路由确认服务与节点，再确认真实聊天可响应，能够执行；不再依赖不存在的 openapi 入口。该修订只是修正验收入口，不降低真实模型与用户可见结果的要求。
5. **retained_from: Round 2。** 事务内 feedback/receipt、节点 updated_at 投影、waiting 一小时首次/续期、固定所属聊天交付、Global/SingleThread 收尾区别、停止与恢复、产品身份/审批链及原有真实旅程均未被本轮设计补充改变。R1 三个 issue 的已关闭证据继续有效。没有扩大到生产操作、历史迁移或审批策略改写。

### 历史问题闭环

- R1-W1 / R1-W2 / R1-W3：保持 closed；本轮未改变各自已批准的解决方案。
- R1-R1：保持 addressed。
- 本轮无新历史待关闭项。

### Issues

无 CRITICAL / WARNING。

### Recommendations

无新增建议。

## Round 4

### Metadata

- reviewer target: 原独立 reviewer `/root/design_review_646`。
- review_mode: delta
- mode_reason: 仅审新增“真实验收发现的交付与停止接线补充”的三个 SingleThread 接线设计及其失败/验证边界；不审实现 diff，不重开原全量设计。
- started_at: 2026-10-23T23:58:20+08:00
- completed_at: 2026-10-24T00:02:14+08:00
- duration: 234s
- validated_at: `unit/bugfix-646` HEAD `97be7854e9956e599eea42ed9e1d9988548dc8c4` 加受审 design 工作区。
- reviewed SHA-256: design.md `539167d44bd4003d8c24ef6393956d89d9d98c8c511f7c0b0ff4cffe4d89016c`。
- 只追加本报告；依派发要求本轮不提交。真实产品失败描述来自派发及设计来源记录，本轮未独立重跑产品旅程。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

SingleThread query 和已确认发送后的 sentinel 处理方向可行；stop 的可信事实注入方向合理，但 inject 的排队语义与现有 fence 恢复接线存在顺序缺口，需先关闭 R4-W1 再实施相应停止补充。Round 2/3 未受影响的结论 retained。

### Coverage 与证据

1. **SingleThread query。** IM `apps/im-server/src/work.ts:488–509` 已校验 node/agent，并仅对 Global 查询要求已登记 global_main session；后续仍通过真实用户/Agent 会话可见性处理。PA query 仅在 Global ensureAuthority，符合现有 IM 职责，修复无关注册前置不等于放宽聊天 ACL。需保留 SingleThread 正常 info/read/send 前置查询、Global ensure 和无权限聊天拒绝的验证；派发中“44 测试通过”仅作为实施方结果，本轮不复述为独立验收。
2. **停止事实与来源。** `TaskExecution.stop` 当前已有 durable control intent、block、cancel keepInbox、drain、IM pause receipt 和解除 block；IM `pauseExecution` 原请求键可重放暂停数。以稳定 ID 复用 session.submit、在通知持久化前不完成 intent，能保留失败后重试而无需新增状态表。宿主已核实 actor/message/time/scope 的 task-human-control 适合作为停止事实；`policy/sources.ts:164–165` 已识别该来源，但首部说明目前只描述 UI resume，实施时需如设计所说同时说明 stop 撤销与原消息时间，不能将一般 system 文本视为人类授权。SingleThread 普通消息已有 `single-thread.ts:126–129` 的原发生时间，故旧排队答复可与停止时间比较。公开 inject API 的排队而非已消费语义仍需补足顺序保证，见 R4-W1。
3. **发送确认与 sentinel。** `global-agent.ts:579–585` 在实际确认 publication 后持有 call/session/turn、目标及服务端 conversation_id，可在既有 command/事件账本上表达同 turn 同绑定聊天已交付，不能只凭 send 调用或 target 字符串推断。`single-thread.ts:223–229` 已有 card sentinel 处理，`:398–415` 在 card 已交付时等待 final 而不流出后续文字。新的文本规则需同时覆盖这一流式边界与 final 判定，保留 final prose、不同目标、unknown/held/failed、已展示审批；不得先流出 NO_REPLY 再仅删除 final。这是当前补充“不能公开泄露哨兵”的验证切面，不要求新增交付账本。
4. **范围与 retained_from。** 原 Task 状态/一小时安排、固定聊天反馈、审批规则/模型与失败分流、SingleThread 来源权限和 Global 非空私有收尾不变；Round 2/3 对上述项的证据继续有效。stop 新增的权威事实来自已存在真人控制入口，不把自动 Schedule 或 Task snapshot 升级成人类授权。没有生产操作或新循环。

### 历史问题闭环

R1-W1 / R1-W2 / R1-W3 继续 closed；R1-R1 继续 addressed；Round 3 无遗留问题。本轮新问题见下。

### Issues

#### R4-W1 — inject 持久化不能保证解 fence 后旧输入先看到停止事实

- 位置：design.md 新增“真实验收发现的交付与停止接线补充”第二项。
- 证据：锁定 DSH `dsh-agent/lib/types/runtime-types.d.ts:200–209` 定义 inject 为下一 pre-step 的排队上下文，不自行唤醒；`integration/index.ts:644–661` 在 inject 后 flush；`input-evidence.ts:13–18` 的 accepted 仅需出现 inbox/spliced，不要求 user/message 或模型已经消费。当前 `TaskExecutionDriver` 把 task-human-control 也放入 ordinary，blocked 分支 `task-execution.ts:62–64` 调用 restore；`:174–175` 将这些消息统一 prepend 到 next-turn。
- 具体失败路径：停止通知已 inject，flush/解除 fence 之间到达一次正常唤醒，原生 pre-step 领取旧 ordinary 和注入通知；fence 拒绝该步后，把两者依次恢复为 next-turn。解除 fence 后旧答复可先作为独立普通轮次进入模型，控制通知留到下一轮。即便稳定 ID 的 accepted/durable 已成立，原始“旧答复不能在停止后被当作恢复”的失败仍可能出现。
- 关闭要求：明确一个原生 admission 顺序保证，使可信 stop 事实在解 fence 后首次可执行模型步之前或同批可见。可保留控制消息的 next-step 身份/顺序或采用等效既有 admission 约束；不能仅以 accepted+flush 为模型已知证据，也不能以删除全部旧输入解决。记录 notify 失败/重试、重启后 pending 与完成 intent 的恢复边界。
- 必须验证：用真实 native inbox/pre-step 测试旧答复已排队、stop inject 已接受、fence 内发生一次被拒绝 admission、解除 fence 后第一次实际模型请求含 stop 事实且旧答复未被升级为恢复；同时验证该通知持久化失败仍 pending、稳定 ID 重试不重复，后续新的明确真人恢复仍可处理。无需为这项增加第二调度器或新状态表。

### Recommendations

无新增可选建议。

## Round 5

### Metadata

- reviewer target: 原独立 reviewer `/root/design_review_646`。
- review_mode: delta
- mode_reason: 依派发仅复核 R4-W1 对应的 next-step 恢复规则与原生竞态验证补充；其余段落沿用 R4/Round 2/3 的有效证据。
- started_at: 2026-10-24T00:02:38+08:00
- completed_at: 2026-10-24T00:03:35+08:00
- duration: 57s
- validated_at: `unit/bugfix-646` HEAD `97be7854e9956e599eea42ed9e1d9988548dc8c4` 加受审 design 工作区。
- reviewed SHA-256: design.md `8bfc23de6ebb93e4c661a7c3bc0bcf459f3f074e5b1b549385ff691fa556d758`。
- 只追加报告，不提交；不审本轮并行变化的实现或测试文件。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R4-W1 的设计解决方案已闭合。新增 SingleThread 三项接线补充可以进入后续实施与验证；本轮没有声称竞态已经由代码或真实产品测试消除。

### Coverage 与历史问题闭环

- **R4-W1 — closed。** Author Resolution 来源为派发方明确接受 finding 的消息及 design 新增停止段落末尾：不能将 inject+flush 等同模型可见；fence 拒绝已领取的批次时，把 task-human-control 保留/恢复为 next-step，其他 ordinary 保持 next-turn；要求解 fence 后第一个模型步同时看到停止事实与旧输入。
- 独立核对公开 `dsh-agent/lib/types/runtime-types.d.ts:43–59`：原生 inbox 暴露 nextTurn、nextStep 及 prepend(target,message)，故设计可在既有 restore 处保留队列类别；`:200–209` 的 inject 定义本就使用 next-step，不需新增 RPC、调度或持久表。R4 的实际遗漏是把控制通知转换到普通轮次，此修改直接关闭该路径。
- 补充保留原 pause receipt → inject+flush → 完成 stop intent/解 fence 的顺序，以及通知失败继续 pending/fence、同 receipt 与稳定 input ID 重试；新规则不会以 accepted 代替已可见，也不删除无关旧输入。已有 pending 控制恢复机制继续承担重启恢复，后续原生测试须同时核对通知失败与首个实际模型请求。
- 验证标准足够具体：fence 内先发生一次实际 pre-step 领取与 reject，再解除 fence，检查第一个实际模型输入包含可信停止通知，并验证旧答复不能表示新的恢复；后续明确真人恢复仍有效。此项检验真实队列边界，不能以模拟 submit 返回 accepted 替代。
- **retained_from: Round 4。** SingleThread conversation query 的模式资格/ACL，confirmed 同目标同 turn 的显式交付、流式及 final sentinel 处理，来源时间说明与审批保留均未修改；R4 除此 issue 外的覆盖继续有效。原 Round 2/3 未受影响设计结论保留。

### Issues

无未解决 CRITICAL / WARNING。

### Recommendations

无新增建议。

## Round 6

### Metadata

- reviewer target: 原独立 reviewer `/root/design_review_646`。
- review_mode: delta
- mode_reason: 仅复核真实 Task 系统通知独立轮次的静默收尾及其来源判定；RelayInput 是声明既有可选线字段，不新增协议或权限。其余设计与 R5 结论保留，不审实现。
- started_at: 2026-10-24T00:20:57+08:00
- completed_at: 2026-10-24T00:22:18+08:00
- duration: 81s
- validated_at: `unit/bugfix-646` HEAD `91c4fb9800a27f617225785b7e4fa341d0d83015` 加本轮两份受审文档工作区。
- reviewed SHA-256: design.md `497af8dd52108d12e09af2f0d8995cf4a617c477570420ffe93885e5c6012723`；specs/gateway/task-graphs.md `7354502b8d3cd1498dff69c631e334b2d473ba7541b7c59a1a14dda8832ad79e`。
- 仅追加报告，不提交；未操作、重启或连接正在验收的栈。独立轮次泄露的现场事实由派发方提供，本轮以真实生产接线核实其设计前提，不将该现场陈述当作本轮独立产品验收。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

使用宿主来源字段限定 Task 纯通知轮次，再复用已有自动轮次展示路径，能补足跨轮 sentinel 泄露而无需跨轮借用历史送达记录。该结论允许进入实施与相关复验，不表示实现或产品验收已通过。

### Coverage 与证据

1. **来源字段真实存在。** `apps/im-server/src/task-notifications.ts:37` 产生 kind=task_graph 的系统通知元数据；`messaging.ts:636–639` 的 persistTaskNotice 以 sender_type=system 插入并进入 relay；同文件 `:344–345` 从 system_notice_json 投影 system_notice，`:648–652` 把真实 message 对象放入 Relay payload。故为 RelayInput.message 声明可选 system_notice（可为 null）只是补足已有字段类型，不需要新增服务端消息标记或平行事件通路。
2. **范围与来源边界。** 设计同时要求本轮全部输入 sender_type=system 且 system_notice.kind=task_graph，不能凭正文、仅凭 kind、仅凭 direct 或历史送达记录判断。真人伪带同名 notice、其他 system 及混入真人的轮次不满足新增条件。系统通知仍按原系统来源进入模型/审批，不因此取得人类授权；Global 收尾规则不变。
3. **复用路径与用户代价。** `single-thread.ts:232–243` 已按当前 turn 的输入集合计算 heartbeatOnly，在无可见/待展示审批时延后自动轮次占位，并对 NO_REPLY 静默结算；有意义正文仍进入普通交付。把满足上述精确条件的纯 Task 通知纳入这一现成路径，避免直聊先展示占位/哨兵再删除，也不依赖上一轮 interactive-delivered 标记。已展示审批须继续保留，不能随静默清除；普通有意义 final 继续发布。这是展示归类，不停止任务处理、不增设调度。
4. **delta。** 新增“直聊 Task 系统通知的静默收尾”Scenario 准确表达宿主来源、NO_REPLY、无可见审批与有意义正文边界；与 canonical Gateway Task “自动续跑保留原有产品交付与审批链”兼容。未把某个系统通知当作任务已完成，也未改变已有等待/停止/恢复契约。
5. **必要验证切面。** 实施应覆盖真实 system/task_graph 正例；sender_type=user 且伪带同 notice、其他 system、混合真人输入的反例；同任务通知发生在新的 turn 且无本轮 send 标记仍安静；有效正文、可见审批及已有 pending 审批路径保持。该集合可用既有原生输入/交付测试设施验证，并由产品 reviewer 复核纯通知结束后的实际直聊无哨兵，不能只断言布尔分支。
6. **retained_from: Round 5。** 原 SingleThread 同轮 confirmed 交付、query 模式资格、stop 控制通知 next-step 规则及其竞态回归要求保持；Round 2/3 的其余设计批准继续有效。本轮没有重新审阅这些未修改内容或扩大生产范围。

### 历史问题闭环

R4-W1 保持 closed；R1-W1 / R1-W2 / R1-W3 继续 closed；无新增待闭环 issue。

### Issues

无 CRITICAL / WARNING。

### Recommendations

无新增建议。
