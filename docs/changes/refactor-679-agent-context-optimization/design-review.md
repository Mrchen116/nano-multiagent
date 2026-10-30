# refactor-679 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（独立 reviewer，继承调用方模型）
- review_mode: `full`
- mode_reason: 首次 Gate 2；覆盖已确认 motivation、完整 design、全部 delta-spec、M1 和实际产品接线。按 `agent-context-review` Mode A 同轮审查 Context 消费链。
- started_at: `2026-10-30T16:15:27+08:00`
- completed_at: `2026-10-30T16:20:45+08:00`
- duration: `PT5M18S`
- timing_scope: 上述时间为已记录的最终核定窗口；之前的只读取证未独立计时，不将此 duration 解释为本轮全部阅读耗时。
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，`28a8473e87aef0863108fa1a667e28eb002cd9d5`
- frozen_scope: 已提交 `motivation.md`；未提交 `design.md`、`specs/gateway/{task-graphs,agent-capabilities}.md`、`specs/im/task-graphs.md`、`M1-context-flow/.gitkeep`。
- design_sha256: `fa76b0ffba3775322de7f0ab773a5ebbc48046b75aeab94b187f30afa1a6be22`
- boundary: 只读源码、锁定依赖公开接口及文档；未实施、未运行模型、未启动服务、未部署。只新增本报告，不改受审产物、不建分支、不提交。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

五项产品原则、提示归属、原生扩展点和基本职责划分已经收口。仍须补齐两项会影响实施路线的消费边界：恢复时如何确认同一业务消息已经追平，以及撤销资格时如何清除已注入原生队列但尚未消费的内容。完成修订后复审，不应将本轮当作 Gate 2 Approved。

### Coverage 与证据

#### 需求与用户约束

- 以 [motivation.md](motivation.md) 中的确认记录为准：Nano 自有提示英文、保留独有信息和用户配置、内部对象重建不生成额外 Task 提醒、变化采用所属聊天消息、续跑保留必要规则和全部本人 doing/waiting、两类 Schedule/Task 提醒分别成立、操作成功后的实际交付提醒保留。`design.md:64-86,150-210` 对这些决定均有明确落点，不以减字数作为验收。
- `design.md:78` 明确不回填已保存 `custom_prompt`；`design.md:24-27,42,218,236` 保留 DSH 公开接口、既有 Memory/History 所有权和本轮不部署边界。feat-676 仅作为相关 active unit，没有据其目标推断 main 已实现。
- 新消息的可见性与自动开工分开，todo/paused 不因消息本身变成 doing；`/stop`、拒绝动作、独立工作及原生短跑限制仍需保留。两条 WARNING 均直接关联已经确认的离线恢复/访问撤销要求，不新增产品规则。

#### 现状、实际组装与架构判断

- 核对了 IM 默认 PA 指导及 dsh-integration 的 `agent-config.ts`、`global-mode.ts`、`personal-security.ts`、`policy/sources.ts` 和相关 Feature 接口。固定来源规则、PA 特有代表权限、Global 显式交付与 Feature 行为分配到现有 owner，优于新增统一 Prompt 管理层；未要求迁移用户文本。
- 首次排序方案有真实公开能力依据：锁定 `@deepseek-ai/dsh-agent@0.2.1-alpha.1` 的 `PreStepDecision` 包含 `kind=enter/messages`；原生 loop 在 `preStep` 默认分支把 runtime context 加入候选消息，`dsh-tool-skill` 的两个 pre-step listener 在 `await next()` 后追加目录/显式 Skill 内容。因此外层 waterfall 可以重排最终 `decision.messages`，不需 private import。实现仍须用实际注册组合验证外层关系，不以手拼数组代替。证据：`packages/dsh-integration/src/agent-config.ts:94-140`；锁定依赖 `dsh-agent/lib/types/runtime-types.d.ts:92-100`、`dsh-agent-loop/lib/index.js:902-927`、`dsh-tool-skill/lib/index.js:804-870`（后两处只读依赖取证，不是允许的 import 路径）。
- Task 消息由 IM 的 Task 写入事务形成，再复用现有 `persistTaskNotice`/relay，职责正确。当前 `task-notifications.ts` 确实只覆盖部分分配和状态事件；扩展业务字段/关系比较而排除 revision/updated_at，能避免无关技术变化制造提醒。证据：`apps/im-server/src/task-notifications.ts:6-40`、`task-graphs.ts:840-841,886-887,960-977`、`messaging.ts:565-600`。
- TaskExecutionDriver 保留当前责任核对、续跑、拒绝动作及运行限制；删除 `shown` 缺失/变化产生模型快照的路径，与首文档相符。`task.execution.changed` 留作内部重新判定合适，但不能代替消息的已交付证明。证据：`packages/dsh-integration/src/task-execution.ts:89-153,174-203`。
- Schedule 删除的产品事实与原生调度职责分离可行。UI 路由经 Node 调用 `CronOwners.command('delete')`，Agent 当前使用原生工具；让两者汇入 PA 的有界删除操作、由 dsh-integration 调公开 Schedule API，依赖方向合法。小型 intent 记录用于删除结果未知和通知恢复，有明确必要性；无需另造调度器。`catalog/history`、持久 input evidence 可作为恢复材料。证据：`apps/im-server/src/control-routes.ts:547-558`、`apps/node/src/main.ts:284-292`、`packages/dsh-integration/src/features/cron.ts:1-26`、`cron-owners.ts:63-91`、`index.ts:650-695`、`input-evidence.ts:1-44`。
- 现有成员广播和 Inbox 撤销并非已经完成新设计所需的统一消费清理，见 R1-W2。持久 relay 也没有“连接 ready 即追平”的保证，见 R1-W1。

#### Agent Context Review — Mode A

实际覆盖 Consumer 为 Global 根、PA 根、SingleThread、内部 child 和审批消费者；Surface 为固定提示、运行环境/Skill 目录、Task 系统消息、续跑/等待修复/交付提醒、工具反馈，以及这些内容在恢复后的来源。

- **来源与组装**：共享来源规则与 PA/Global 特有语义分开；Task 标题/正文为数据，结构化 `human_control` 才能投影为认证控制事实。设计没有把整条系统文案或 `role=user` 升为真人权限；审批需单独获得所需来源解释。当前 `policy/sources.ts:167-181` 确实有特殊控制投影，因此修改该投影是实际必要接线。
- **发现与可行动性**：Task 概要有标题、graph/node、固定聊天、入口、等待安排及运行限制，正文和讨论按需读取；Skill 保留目录及加载入口；waiting 修复区分 missing/inactive/expired/mismatch/unavailable，不把查询失败说成删除。Before/After 和动态英文样例足以说明目标语义，实际措辞仍需信息归属对照验收。
- **更新与组合**：消息正文提示读取最新要求；续跑保留用户明确要求的行动规则；交付提醒只投影本次具体任务，固定聊天/子 Agent 汇报路径/未知发送语义保留。Schedule 用户删除提醒与 Task 修复不是同义内容，设计正确保留两者。正常 occurrence 已排入同 Session 时避免另一轮修复的决定有 catalog/history/input evidence 支撑。
- **保留、失效与恢复**：设计区分持久摄取、注入和实际消费；不以 submit 成功当已读，消费确认缺失按稳定 ID 核对。两个未闭合点是“尚未到 Node 的变化何时算补齐”和“已离开产品 Inbox、进入原生队列的内容如何撤销”，具体见 Issues。
- **Validation**：M1 W1-W5 要求真实 assembler/pre-step/serializer、消息事务/relay、实际消费与 Schedule storage；R1-R6 覆盖代表性模型行为、交付和权限。原生换窗与摘要模式、child 来源、Feature/Skill 开关均进入验证范围，没有用轨迹或单条字符串代替最终 provider 请求。本轮仅判断设计和接线，不声称模型已正确理解或真实请求顺序已通过。

#### Delta-spec、milestone 与验收前置

- 三份 delta 的 canonical target 正确。Gateway 的两个 MODIFIED requirement 保留停止延迟消费、首次 waiting/校验失败、安静等待及定时复查的原有场景；原“外部变更与冷恢复”改为业务消息恢复，是本 unit 明确的实质变化。IM 的改派、逐层暂停/关闭和向上结果反馈场景均保留，增加当前负责人、正文/关系/资格覆盖有首文档依据。
- Gateway ADDED 的续跑与交付细化没有取消 current spec 的固定聊天、等待时间上限、停止和拒绝保护；能力 delta 将独立 Schedule 用户删除通知放在能力契约中，而不是错误地依附 Task。
- 一个 M1 串行覆盖消息生产、消费、去重和提醒，范围虽跨包但接口彼此关联，没有并行编辑冲突。两轨退出标准可追溯到首文档；须按下列问题补充恢复/撤销的具体前置和验证分支。
- 没有客户端布局或交互组件修改，新增系统消息沿既有聊天渲染；本轮不适用新原型 must-match。端到端 runbook 明确隔离 IM/Node、真实模型和最终请求，未把功能验证推迟到生产。没有历史数据搬迁/一次性生产业务操作，省略 `deployment-prompt.md` 合理。

### 历史问题闭环

首次审查，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 恢复顺序缺少可确认的业务消息追平边界，无法支撑首个步骤必见离线撤回

- **Severity / evidence**：WARNING；设计缺少完成判据与现有 relay 异步行为为 **CONFIRMED**；按当前接口直接实施会让首个步骤越过撤回的具体运行后果为 **PLAUSIBLE**，本轮未运行复现。
- **位置**：`design.md:131-144,150,216`；Gateway delta“外部变更与离线恢复”；M1 R2/R3、W3。
- **Context Surface / expected**：Task 业务消息、重启/断连恢复与原生待执行输入。Global/SingleThread 在恢复后的首个有效步骤，需要先知道离线期间的撤回/改派/暂停，再据此决定后续动作。
- **Observed / evidence**：设计写出“恢复已摄取未消费消息 → 补接服务端 relay → 核对当前责任 → 判定正常续跑”，但没有定义谁确认“补接”完成、等待到哪个事件位置，或原生待执行输入何时允许进入下一步。现有 `RelayDelivery.drain` 一次在途最多 32 条、查询 256 条，异步按 Agent 分配窗口；`ready` 不携带追平水位。Channels 分别以异步回调处理 `onFrame` 和 `onState`，Node 的 ready/onReady 随即调用 Task/产品恢复。参见 `apps/im-server/src/relay-delivery.ts:20-47`、`packages/channels/src/index.ts:221,297,383`、`apps/node/src/main.ts:124-138,316-323`。原生 Session 中也可能已经有持久输入，恢复产品 Inbox 的顺序不等于控制了它的执行边界。
- **成立机制与影响**：断连期间 A 被撤回，但该系统消息还在 IM 重放窗口之后；Node 先恢复旧普通输入或接到新的独立消息。当前快照已经不含 A，而设计又移除了根据快照产生私下责任变化文本的路径，此时模型仍可能只见历史中的 A。最终补到消息只能保证“稍后可见”，不能兑现当前明确承诺的“恢复后首个有效输入/最近下一步骤可见”，可能在撤回后继续发起 A 的动作。
- **必要改进**：明确同一业务消息的追平/消费准入方案及 owner。例如由 IM 给出有界恢复位置并确认相关消息已由 Node 持久接收，或按当前 Task 版本定向补取缺少的原消息；相关原生步骤在这个条件满足前不能越过。不能把 socket ready、`session.ensure` 或当前责任读取成功当成消息已追平，也不能用另一份私下快照修补。明确暂不可核对时的限制及独立工作处理。
- **验收补充**：隔离验证重放超过一个 32 条窗口、撤回消息后到、旧原生输入已持久排队/新的普通输入先到两种路径；首个被允许执行的相关步骤必须已经包含同一撤回事实，且不新造重复消息或唤醒。设计无需规定具体算法代码，但必须给实施者明确完成判据。

#### R1-W2 — 失权清理只指向不存在的通用成员接线，未覆盖已持久注入的原生消息

- **Severity / evidence**：WARNING；现有清理范围及设计缺口为 **CONFIRMED**；未消费正文在失权后进入模型的运行后果为 **PLAUSIBLE**，本轮未运行复现。
- **位置**：`design.md:135-146`，尤其“既有成员变更接线负责清除尚未消费的失权内容”；IM delta“成员失去任务处理资格”；M1 R2/R6、W3。
- **Context Surface / expected**：成员撤销、Inbox 直接 Context 投影、原生持久 next-step/next-turn 队列。受影响主体应只消费最小撤销事实，尚未消费的标题/正文/成员等失权内容不应随后进入 Context。
- **Observed / evidence**：设计在 idle 时即把完整 Task 消息持久 `inject`，但撤销段只把清理交给“既有成员变更接线”，未给出原生队列的撤销或消费前复核 owner。main 的成员移除只是删 participant 并通过 `membership()` 向 browser 广播；不是普通 Agent 的清理回调。PA 的 `refreshPersonalSources()` 只调用 `Inbox.revokeSource()`，后者删除产品 SQLite 的 reads/fragments/inbox/snapshots/targets，不操作原生输入。参见 `apps/im-server/src/messaging.ts:297-303,810-821`、`gateway.ts:182-200`、`packages/personal-assistant/src/global-agent.ts:274-285,384-385`、`inbox.ts:185-199`。而 `packages/dsh-integration/src/index.ts:850-882` 的 inject 已保存到独立原生 Session 队列，submit 仅校验 Agent lifecycle，不等价于会话成员资格校验。
- **成立机制与影响**：完整系统消息已注入但 Agent 尚未唤醒，随后被移出群。即使新最小撤销投影送达、产品 Inbox 已清理，旧完整消息仍可与下一有效输入一起被原生消费；重启还会恢复这份队列。它违反设计自身“清除尚未消费的失权内容、只给必要撤销事实”的承诺。仅在 `prepareSystemContext` 检查资格也不足，因为资格可能在 prepare/inject 与真正消费之间变化。
- **必要改进**：把撤销接线明确为本 unit 新增/扩展的职责，覆盖普通 Global、PA 和 SingleThread；定义 source/消息 ID 到原生待消费输入的映射，以及撤销通知落地时和恢复/消费前的处理。可通过 dsh-integration 的公开原生 inbox 能力移除/替换尚未消费输入，或在原生准入点过滤并保存撤销终态；处理后不能让 input-evidence/产品重试再补注入原正文。保持已实际消费历史的既有语义，不要求擦除旧历史；保留最小撤销事实。
- **验收补充**：完整 Task 消息已 inject、未消费时撤销资格，随后普通输入唤醒；在 inject 后/撤销后分别重启；同时验证普通 Global、PA、SingleThread 的清理接线和去重。最终 provider 请求仅含允许的最小撤销事实，不包含此前尚未消费的失权标题、正文或成员数据。

### Recommendations

无额外可选建议。本轮只要求关闭以上两项已确认需求的消费边界，不扩展为通用事件总线、通用 outbox 或新的 Agent Loop。

### Author Resolutions

- **R1-W1 — accepted**。现有 relay 窗口和 ready 回调不能证明原消息已经到齐，问题成立。design「有界追平与原生步骤准入」明确 IM 原消息索引及固定 through、PA 分页持久摄取、dsh-integration 在每次候选步骤前完成准备后准入；失败时保留待处理并限制相关动作，不用平行责任快照补洞。Gateway delta 与 M1 验证补入窗口后到、旧原生输入、新输入先到、初始化衔接分支。
- **R1-W2 — accepted**。现有 revokeSource 只清 SQLite，原生 inject 有独立持久队列，原设计归属断言不准确。design「成员撤销与未消费原生输入」明确本 unit 新增跨模式撤销接线、产品消息到原生 ID 映射及 revoked 终态，使用公开 inbox.remove 并 flush，pre-step 对已 claim 候选再次过滤；终态优先于恢复补投，已消费历史不改写。IM/Gateway delta 和 M1 验证补入 inject／撤销后重启及三种模式。

以上修订未改变五项已确认产品决定，未引入通用事件总线或第二份消息正文。等待独立复审，当前不宣称 Gate 2 通过。

## Round 2

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（与 Round 1 相同的独立 reviewer，继承调用方模型）
- review_mode: `full`
- mode_reason: 本轮虽由两项旧问题触发，但新增 `task.context.sync` 与 `session.revoke_inputs` 跨包共享接口，并改变原生 pre-step 的准入流程；不按仅核文案的 closure 放行。重新覆盖完整目标方案，重点验证新增消费边界与原有停止、交付、配置和恢复规则的组合。
- started_at: `2026-10-30T16:25:47+08:00`
- completed_at: `2026-10-30T16:29:47+08:00`
- duration: `PT4M`
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，`28a8473e87aef0863108fa1a667e28eb002cd9d5`，与 Round 1 相同。
- frozen_scope: `motivation.md`、修订后的 `design.md`、三份 delta-spec、`M1-context-flow/.gitkeep`，以及 Round 1 后追加的 Author Resolutions。
- design_sha256: `f59d0dcf9dffbce1935c626fc27d9aee77443a2c081065438e134908d0295150`
- gateway_task_delta_sha256: `09ff439e2bc0f3b6ac1b43ef5eb9464c1680907b0833e699134f1c8c864ad24b`
- im_task_delta_sha256: `cb9dc93a0f79b06324fa8bc355c585ed60b95c9687e659f23a18d47d06dda6fe`
- boundary: 仍为实施前文档审查；只读实际源码/公开依赖类型，不运行模型或服务、不部署。仅追加本轮报告，保留 Round 1 和 Author Resolutions 原文。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2 均在设计层关闭；未发现新的实质设计问题。Gate 2 文档审查通过，不表示实施、真实 provider 请求、模型行为或部署验收已经完成。

### Coverage 与证据

#### 完整方案与 retained 证据

- **需求及用户约束**：重新核对完整 design 与首文档。五项机制、英文自有提示、保留用户配置与独有信息、无变化不提醒、独立工作及授权边界均未改变。`motivation.md`、Gateway 能力 delta 和 M1 占位文件哈希与 Round 1 相同。`retained_from: Round 1` 的首文档覆盖及非目标判断继续成立，理由是用户原则与这些产物未变。
- **固定提示/环境/Skills**：`design.md:64-109` 保持原有归属和公开 waterfall 排序设计；运行环境/目录仍为动态消息，Skill 显式调用正文不参与排序。原始来源、工具/Feature 分离、PA/Global/child 交付职责不受本轮共享协议修改。`retained_from: Round 1` 的真实 prompt 组装入口和原生 listener 证据；本轮代码与锁定依赖版本均未变。
- **Task 生产和提醒**：`design.md:111-142,171-233` 仍由 Task 写入事务生成一份业务消息；正文变化给读取入口，续跑保留必要规则和全部本人任务，Schedule 删除/等待修复/实际交付仍分别承担各自事实和行动指导。新同步只补取原消息，不重新制造私下快照。`retained_from: Round 1` 的 TaskGraphService、CronOwners、工具 deferContext 和原生 Schedule 接线证据。
- **架构**：IM 持有原消息及单调索引，PA 持有产品摄取/消费/撤销位置，dsh-integration 使用公开原生接口执行准入和队列移除，职责没有跨包倒置。新增索引只保存定位和接收者/投影类别；产品映射不复制正文。它们直接解决异步 relay 无追平位置和原生队列独立持久化两个已确认缺口，不构成第二份 Task 状态、第二套调度器或通用事件总线。

#### 新共享接口及实际接线可行性

- `design.md:146-155` 明确了 `task.context.sync` 的 after/through、同一切点分页、全部持久摄取后的完成条件以及消费游标分离。主动 relay 与补取按原 ID 合并，每个候选步骤都走准备接口，因此不再依赖 ready/onReady 的先后顺序。切点后的新变化落入后续步骤，不要求等待永远移动的全局空队列。
- `design.md:153,155` 明确不可用分支：不将失败当空责任，不放入尚待资格复核的内容，不启动相关 Task 自动步骤；只保留可独立处理的输入并给出运行限制，否则 reject 且保持待处理，不热循环。既有 /stop fence 仍先恢复，原生短跑和运行错误处理保留。
- 反向准备调用与后续有界撤销 RPC 可以复用现有双向 stdio 能力。`packages/dsh-integration/src/rpc.ts:13-24,83-106` 对 handler 和响应独立分发；`apps/node/src/main.ts:374-396` 已有 PA 产品服务和 `product.task_execution.snapshot`/`product.call` 接线。该证据确认无需另加内核 HTTP 服务，也不需要让 PA import DSH；不是新增协议实现已经通过测试的声明。
- 锁定 `@deepseek-ai/dsh-agent@0.2.1-alpha.1` 的公开 `Inbox` 类型声明了 nextTurn/nextStep、`remove` 和持久 splice，`PreStepDecision` 允许替换候选消息，见 `lib/types/runtime-types.d.ts:40-99`。只读实现也确认 `remove` 经 `splice` 修改队列，而 claim 在 pre-step 前提取消息。因而“队列内 remove + 已 claim 候选过滤”的两段处理有实际接口依据，不依赖 private import。

#### Agent Context Review — Mode A

- **Consumer 与来源**：Global、PA、SingleThread 共用同步和撤销 owner；内部 child/审批消费者仍沿设计原有 delegation/来源投影，不将追平位置或 revoked 记录暴露为新的模型指令。`human_control` 的宿主认证边界、源消息 ID 和最小撤销投影的限制保持。
- **选择、交付与消费**：先固定当前步骤的事实切点、补齐并持久记录原消息，再把需要消费的业务事实纳入该步骤；已候选输入复用原 ID。received/accepted 与真正 consumed 仍分开，消费确认缺失按原生证据修复，未引入同一消息的另一份责任提醒。
- **失效与恢复**：`design.md:161-169` 把原来错误归给既有接线的清理明确改为本 unit 新增职责。先保存 revoked 和原生 ID 映射，再清产品缓存、移除并持久化原生输入；已 claim 的候选在 pre-step 再筛掉。任何中间失败都由准入继续阻止相关 ID，恢复补投服从 revoked 终态。已实际消费历史不删除，避免把权限撤销扩大为历史擦除。
- **组合与限制**：固定 through 是本步可审查的事实切点；更晚的变更经下一步处理。这样既能界定“最近下一步骤”，也避免为追求绝对即时性而暂停全部独立工作。设计未宣称取消已经发生的工具副作用，仍保留来源、停止与授权规则。
- **验证**：`design.md:282-285` 将窗口后到、旧原生输入/新普通输入、inject 后重启、撤销后重启、已 claim、三种模式及同步失败纳入既有 M1 R2/R3/R6、W3。最终请求检查与实际模型行为仍是实施期退出标准；本轮没有运行这些用例，因此结论限定为设计闭合与公开接线可行。

#### Delta、milestone、迁移与体验

- Gateway delta `:13-18` 增补“连接就绪/责任查询不代替追平”和“未消费失权内容不进入模型”；IM delta `:37-41` 增补撤销、重启/重试不可重新注入和历史保留。这些是原确认需求的可观察边界，未把 seq/cursor/内部状态字段写成用户 API。
- M1 仍是一条串行实施链，未改变跨包分工或引入并行冲突。`design.md:282-283` 将两项关闭所依赖的验证明确关联退出标准，非笼统“补测试”。
- `design.md:155,259,283` 规定既有未完成 Task relay 以原 ID 幂等登记索引后才开放准入，既有消费历史不重放；初始化衔接和失败分支在隔离副本验证。这属于随产品初始化/恢复完成的索引衔接，不要求用户执行生产一次性业务操作，仍无需另写部署提示词。
- 没有新增客户端布局/交互方案；系统消息沿既有聊天能力展示，`retained_from: Round 1` 的前端适用性判断和隔离验收前置继续成立。本轮未新增生产测试、额外重启演练或新 Gate。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据与判断 | 状态 |
|---|---|---|---|
| R1-W1 | accepted；新增 IM 有序原消息索引、固定 through 分页、PA 持久游标和每步准入 | `design.md:146-155` 现在给出明确 owner、追平完成条件、普通/自动/恢复输入的共同准入和失败处理；`design.md:282-283` 覆盖超过 32 条窗口及旧/新输入先到。保留同一原消息，没有用平行快照绕过问题。 | **closed（设计层）** |
| R1-W2 | accepted；新增跨模式撤销接线、产品到原生 ID 映射、revoked 终态及队列/候选清理 | `design.md:161-169` 覆盖队列内、已 claim、持久化失败与恢复补投；公开 `Inbox.remove` 和 `PreStepDecision.messages` 支持该职责。`design.md:283` 与两份 Task delta 约束实际请求和重启结果。 | **closed（设计层）** |

### Issues

无新增 CRITICAL / WARNING；无仍开放的历史问题。

### Recommendations

无额外建议。按现有 M1 实施与验收即可；不要因本轮设计通过而省略实际消费、撤销及恢复的证据。

### Author Resolutions

- 接受 Round 2 的设计层结论：R1-W1／R1-W2 已关闭，无新增 finding 或 recommendation，无实质异议。核对本轮公开接口依据、共享 owner、消费切点与两轨退出标准后，Gate 2 文档门禁通过。
- 本轮审查后仅追加本段收口记录；首文档、design、delta 与 milestone 骨架无后续实质变化，retained 依据为 Round 2 冻结范围及哈希。实现、实际请求和用户行为尚未验收；本轮只交付设计。
