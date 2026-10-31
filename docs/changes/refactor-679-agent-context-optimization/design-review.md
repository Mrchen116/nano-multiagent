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

## Round 3

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（同一独立 reviewer，继承调用方模型）
- review_mode: `full`
- mode_reason: 用户新增“系统提示词怎么写，在 design 中就要确认”的明确交付要求；新增完整固定正文、动态模板及消费者组合，必须重新审查内容保真与组合，Round 2 Approved 不覆盖新增正文。
- started_at: `2026-10-30T17:04:25+08:00`
- completed_at: `2026-10-30T17:15:06+08:00`
- duration: `PT10M41S`
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，`cdf7e706241c20a0aca33a6764a1c0ac7d6a3ef6`。
- frozen_scope: 未提交的 `motivation.md` 与 `design.md`；其余设计产物沿 Round 2。
- motivation_sha256: `a2e7650cda36a48ce6aac94d592efef2876e309059cca69592ec9518208f2aff`
- design_sha256: `f3a1a861682e5d5a48177eaa7051b3f354862dde789b9d5f64d1abee633b9347`
- boundary: 只读当前源码、文档和锁定接口；只追加报告。未实施、未运行模型、未启动服务、未部署。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

新增正文已显著提高设计交付深度，大部分规则有明确归属且与现状保真。仍有三个会让实施者选择不同语义或遗漏现有信息的缺口；本版新增正文尚不能按“只调整字符串组织与空白”实施。R1-W1、R1-W2 保持设计层关闭。

### Coverage 与证据

- **需求**：核对新增原话与 motivation 解释，确认这是设计正文及分支的收口要求，没有授权改变五项 Task 原则。`design.md:213-240,633-648` 明确唯一正文、保留项和实施限制；因此本轮不仅判断职责合理，也检查真实消费者能否按规定得到完整内容。
- **基线**：比较 `28a8473e8..cdf7e7062`，变化均为本 unit 设计交付文件，没有运行时代码变化。三份 delta 哈希与 Round 2 一致。`retained_from: Round 2`：原消息索引/固定 through、每步准入、跨模式撤销映射及原生候选过滤、自动初始化衔接、隔离 runbook 和 M1 消费链退出标准。新增正文没有撤回这些决定，未重开 R1 问题。
- **P0/P1/P1S/P1C/P2/P3/P3C**：对照 `personal-agent-defaults.ts`、`global-mode.ts`、`personal-security.ts:134-136`、`policy/sources.ts` 和实际 `agent-config.ts:100-139`。默认人格保留主动准备、私人帮助、Skill 发现和结果优先；Global 保留完整 Inbox、长事先反馈、实际交付、私有结尾、子 Agent 管理及拒绝处理；SingleThread 保留 NO_REPLY；PA 的引用/owner_can_read、代表权限、草稿、来源排除、附件和 actor_risk 均有落点。新增 quiet Heartbeat 的显式例外与既有 P7 一致。来源/送达去重总体成立，但 P2 的独立审查消费者遗漏，见 R3-W1。
- **P5/P6**：对照 `features/task-graphs.ts`、`features/intelligent-ui.ts`。Task 空间/成员、真实 creator、显式保存计划、删除范围、revision/request_key、waiting 前提、一小时复查、失败送达、全部状态及固定聊天均保留；root/child 尾段区分公开交付。UI 的选择条件、Skill 加载、ComposeMessage/ToAssistant、私聊/群状态及数据真实性没有被删除。正文不要求修改既有用户自定义文本或 feat-676 Memory 所有权。
- **保留段与审批**：用只读脚本提取正文核对，P7、P8、P9、P11 均与当前定义逐字一致；P10 保留文件指导、原授权延续、限制作用范围和精确待审动作，并加强结构化 human-task-control 边界。实际审批装配比组合表复杂，不能用 P10/P11 概括全部消费者，见 R3-W1。
- **D1-D9**：对照 Global 两种 wake、TaskExecutionDriver prompt/delta、Task 成功后的 deferContext 和 PA snapshot。Task 消息的原文/来源、认证控制、最小撤销投影、全部本人概要、held 限制、Schedule 删除与 Task 修复分离、waiting/结果交付和未知状态整体保留。缺少已核实运行限制分支，且共步组合仍存在自由裁量，见 R3-W2/W3。
- **架构与验收**：文本继续复用现有 section、Persona、Feature、工具结果及 native input，不新增提示管理层或权限机制。`design.md:648` 把定稿一致性并入 W1/W2，最终 provider 请求和真实行为仍是独立证据。新增内容没有客户端布局变化或一次性生产操作，未新增原型/部署要求。本轮未捕获实际请求，不能证明模型已经正确消费。

### Agent Context Review — Mode A

本轮重点覆盖固定提示、动态提醒、共享来源函数和独立审批系统提示；Consumer 包括 Global/PA 根、SingleThread、Global child、CC/Codex 工具审批及 PA input/action 审查。沿实际调用核对来源、组装、触发、必要信息和下一步行动；生命周期机制沿 Round 2 证据。以下 finding 的文档/接口事实为 CONFIRMED；模型会如何误解仍属未运行的风险，不以设计缺口冒充已发生事故。

### 历史问题闭环

| Issue | 本轮证据 | 状态 |
|---|---|---|
| R1-W1 | `design.md:144-155` 仍保留固定 through、持久摄取与每步准入；三份 delta 未变 | closed，retained_from: Round 2 |
| R1-W2 | `design.md:157-169` 仍保留 revoked 终态、公开队列清理和已 claim 过滤；D3 最小投影不附失权正文 | closed，retained_from: Round 2 |

### Issues

#### R3-W1 — 审批组合漏掉实际共享 P2 的消费者，不能按当前表格完成保真替换

- **Severity / evidence**：WARNING / CONFIRMED（装配不一致）；误导审查行为的后果尚未运行验证。
- **位置与 Surface**：`design.md:221-240,307-323,455-473`；独立审批 System Prompt。
- **Expected**：实施者应明确每类独立审查收到哪些定稿段，保留它自己的证据和输出协议，不向只读审查器发送工作 Agent 的执行指令。
- **Observed / evidence**：组合表统一写“既有审批 policy＋P10＋适用时 P11”，未列 P2，也未区分 PA input/action。实际 `policy/classifier.ts:16` 使用 policy＋reviewSourceInstructions＋inboxSourceInstructions＋条件 messageReviewInstructions；`policy/codex-context.ts:35` 同样拼接三项；PA input 的 `personal-security.ts:80-87,109-120` 和 action 的 `policy/codex.ts:73-77` 则使用 **inboxSourceInstructions＋personalReviewPolicy 专用正文/分支**，并非 P10/P11 配方。将共享 inboxSourceInstructions 替换为 P2，会把 `design.md:322` 的“read newer messages…make a new call”同步带给这些独立审查器，尤其 input 消费者没有业务工具；若为遵循表格删掉 P2，又会丢失原有 sender/partial/observer/送达解释。
- **影响**：两种按文档可成立的实现会形成不同审查上下文；“保留原有专用消费者”概述不足以确定共享函数修改的实际边界。实施者必须自行选择删哪些来源语义、保留哪些工作指令，违背本轮正文定稿要求，也可能导致额外拒绝或错误的后续行动要求。
- **必要改进**：分别列出 CC classifier、Codex 工具审批、PA input、PA action 的准确组合，明确 `personalReviewPolicy` 的保留范围以及 P2 是否进入。若分离工作来源段与审查来源段，给出审查分支完整定稿；可复用来源事实，但把“读取并重新发送”的行动语义改成只读判断语义。验收从这四个实际 assembler 捕获系统文本与输出协议，不只测根 Agent section。

#### R3-W2 — 已核实的运行限制没有定稿出口，D9 又只适用于无法核实

- **Severity / evidence**：WARNING / CONFIRMED（必要信息缺少投影）；实际模型失败未验证。
- **位置与 Surface**：`design.md:175,195,479-492,531-583,624-631`；自动续跑、Task 等待修复提醒。
- **Expected**：Task 状态及 Schedule 失效已经核实，但当前能力不能完成修复时，模型应知道具体限制，解释受阻并继续独立工作，不能把已知限制说成查询未知。
- **Observed / evidence**：当前 `personal-assistant/src/task-execution.ts:55` 返回 `reason:'cron_disabled'`；`dsh-integration/src/task-execution.ts:140,190-201,248` 把这个事实随 snapshot 呈现，并据此限制重复续推。目标设计 `:175,195` 仍要求保留运行限制，但 TASKS_JSON、HELD_JSON、REPAIR_JSON 没有承载能力限制的确定分支；LIMIT_JSON 只出现在 D9，而 D9 固定首句是“facts or … permissions cannot be verified”，且代码块外把它限定为独立输入步骤。已核实 Cron 关闭不等于事实无法核实。D4/D7 在该情况下仍无条件要求建立新安排。
- **影响**：删去整份 snapshot 后，这项原有独有事实可能随之丢失；使用 D9 补洞则错误描述为未知。实施者需要另外创造条件和英文正文，模型可能尝试不可用能力或不能准确报告阻塞。
- **必要改进**：增加或明确“已核实运行限制”的完整模板及触发/共步分支，给出数据来源与受影响范围；与 D9 的 unavailable 保持区别。明确 D4/D7 如何带上该限制、如何表达在能力恢复前不能完成的动作，保留既有不热循环和独立工作语义；回归 Cron 关闭且关联安排失效的实际请求。

#### R3-W3 — 共步动态模板要求共享概要，但共享后的数据与拼接规则尚未定稿

- **Severity / evidence**：WARNING / CONFIRMED（设计内部不闭合）。
- **位置与 Surface**：`design.md:479-492,531-556,566-583`，尤其 `:546`；同一步的续跑/到期/修复 Context。
- **Expected**：D4 与 D5/D7 同步出现时仍保留全部本人责任、具体 occurrence 和逐 Task 失效原因，并能直接按设计拼出唯一内容。
- **Observed / evidence**：TASKS_JSON 明确为全部 doing/waiting 概要，CHECK_JSON 又包含到期 Task 当前概要与检查事实，REPAIR_JSON 包含失效 Task 可定位概要和原因；`:546` 同时要求它们“共享一份当前任务概要”，却未规定保留哪个占位、其他占位改成什么结构、组合次序和模式尾段是否只拼一次。当前驱动允许 automatic 与普通 Schedule 输入同批，见 `task-execution.ts:89-100,137-140`，并非只存在于假设中的组合。对“doing A＋到期 waiting B＋失效 waiting C”，实施者必须自行决定移除/合并哪些字段与段落。
- **影响**：逐模板照抄违反明确的去重规则；直接删重复概要可能丢掉全部本人任务、Task 关联或本次检查/修复原因；重复拼模式尾段又恢复了本 unit 要消除的重复。不同实现都需要在定稿之外做语义选择。
- **必要改进**：明确同一步共享概要的数据形状、D5/D7 的专有事实如何按 ID 引用、条件段及唯一尾段顺序，或明确采用另一套完整共步模板。给一个含 A/B/C 的组装例以验证字段完整；不需要增加新调度算法。固定段组合表中 `P5/P6` 的顺序也应与数值 order 的 P6→P5 对齐，避免两套“按顺序”规则。

### Recommendations

无额外可选建议。本轮要求只针对新增正文的真实消费者、原有独有信息及已经要求去重的共步分支；不扩展产品范围或重做已通过的消费链。

### Author Resolutions

- **R3-W1 — accepted**。核对 classifier.ts、codex-context.ts、personalReviewPolicy 和 reviewPersonal/reviewDisclosure 的实际装配后，原表确实遗漏共享来源及 PA 专用分支。design 改为四类准确组合，新增完整 P2R 只读来源正文、P12 common/action 原专用正文，工作 P2 不进入审查器；原输出协议和工具限制保持，M1 增加四类 assembler 捕获。
- **R3-W2 — accepted**。cron_disabled 是已核实限制，不能归为 unavailable。新增定稿 D10、limits 字段与当前 reason 的精确映射，D4/D5/D7 明确遵守不可用能力限制；保留当前 limited 防重复推进和独立 doing 语义，加入实际请求验例。
- **R3-W3 — accepted**。新增共步的唯一 Task reminder 包配方：D10/D4/D5/D7 条件正文固定顺序、一份 task_context 数据、一次模式尾段；checks/repairs/limits/held 通过任务引用关联概要，附 A/B/C 具体夹具。固定段表同步改成与数值 order 一致的 P6→P5。没有新增调度算法或改变已确认产品原则。

新增正文仍待独立复审；Round 3 不作为通过结论。

## Round 4

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（同一独立 reviewer，继承调用方模型）
- review_mode: `delta`
- mode_reason: 本轮是 R3 三项问题引起的有界正文与组合修订：新增审查专用来源段和保留的 PA 专用正文、Cron 关闭限制段及共步配方。没有改变需求、共享产品接口、消费准入机制或 milestone 边界；展开新增正文及其实际消费者，未受影响范围保留 R3/R2 证据，不重做全量审查。
- started_at: `2026-10-30T17:21:06+08:00`
- completed_at: `2026-10-30T17:22:11+08:00`
- duration: `PT1M5S`
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，`cdf7e706241c20a0aca33a6764a1c0ac7d6a3ef6`，与 Round 3 相同。
- frozen_scope: 修订后的 `design.md` 和 Round 3 Author Resolutions；motivation、三份 delta-spec 及 M1 骨架未变。
- design_sha256: `3c208cec4b3e9c8b5f02d73b32dce8a5df5047bd2ba82046b4c537f06a694545`
- motivation_sha256: `a2e7650cda36a48ce6aac94d592efef2876e309059cca69592ec9518208f2aff`，与 Round 3 相同。
- boundary: 仅文档复审和只读源码/正文/夹具核对；未实施、未运行模型、未启动服务或部署。只追加本轮报告。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R3-W1、R3-W2、R3-W3 均在设计层关闭，没有新增实质问题。当前完整正文及组合规则可以作为实施依据；通过的是 Gate 2 文档审查，不是实际请求、模型行为或产品验收。

### Coverage 与证据

- **独立审查消费者**：`design.md:227-230` 分别固定 CC/legacy classifier、Codex 工具审批、PA input、PA action 四种真实配方，与 `policy/classifier.ts:16-18`、`policy/codex-context.ts:30-35`、`personal-security.ts:80-87,109-120`、`policy/codex.ts:73-77` 的实际装配对应。P2R 在 `design.md:328-342` 保留 sender/pa_agent_id、participant/observer、live/restored、partial、认证控制与实际送达语义，并明确仅按审查器允许的证据/只读能力作判断及遵守原输出格式；没有工作 Agent 的发送要求。P10/P11 与各原 policy/output adapter 保持自身适用范围。
- **PA 专用正文保真**：`design.md:494-512` 提供 P12 common/action 完整文本及宿主限定的 REVIEW_KIND。只读提取比较确认：将源码 `${kind}` 对应为设计占位符、归一空白后，common 与 action 都与 `personalReviewPolicy` 原文相同；input 不拼 action，原严格 JSON、证据冻结、缺失证据处理及工具限制没有被“统一审批”覆盖。共享来源常量分为工作和只读审查两种，是现有消费者差异的最小表达，不新增 policy engine。
- **已核实运行限制**：`design.md:528,539,678-686` 为现有 `snapshot.reason=cron_disabled` 提供唯一 reason、blocked_actions、受影响任务引用、检查时间和完整 D10；它明确区分已知能力限制与 D9 的 unknown。D4/D5/D7 在 `:587,602,615` 以 scheduling available 为安排先决条件并服从已核实限制，不再无条件要求不可用动作。现有来源与去重对应 `personal-assistant/src/task-execution.ts:49-55`、`dsh-integration/src/task-execution.ts:137-140,248`；`schedule_create/schedule_update` 是现有能力工具名（`product-contracts/src/capabilities.ts:33`）。修订保留 limited 及独立 doing，不借文案改变 Task 状态或恢复暂停工作。
- **共步配方及数据**：`design.md:514-541` 将 D4/D5/D7/D10 定义为一个 reminder 包的条件片段，确定 D10→D4→D5→D7→一个 TASK_CONTEXT_JSON→唯一模式尾段。数据有一份全部本人 doing/waiting 概要，checks/repairs/limits/held_actions 通过 graph/node 引用它；不存在的旧引用排除并由 D3 表达实际变化。D5 继续同步于原 occurrence，D6 保持独立删除事实。`design.md:688-704` 的 A/B/C 夹具经 JSON 解析及引用核对通过，三项任务不重复，checks/repairs 均能定位任务且不重复标题/聊天；Cron 关闭分支明确只对当时需修复的 C 建立限制，不把 B 正常到期提前当作失效。固定段表的 P6→P5 也与数值 order 一致。
- **验收与适用范围**：`design.md:721` 已将四类真实 assembler、Cron 已知限制、A/B/C 共步及 held_actions 纳入 W1/W2，观察最终系统文本、完整专用输出协议以及单份数据/尾段，保留代表性模型和真实产品验收要求。只读文本比较与夹具检查是本轮设计证据，不代替这些实施期验证。
- **未变范围**：`retained_from: Round 3` 的 P0/P1/P1S/P1C/P2/P3/P3C、P5/P6、P7-P11 及 D1-D3/D6/D8/D9 的未受影响正文保真、用户配置和 Memory 边界继续成立；本轮正文变化没有更改这些职责。`retained_from: Round 2` 的原消息索引、固定 through、每步准入、撤销终态和原生输入清理、隔离 runbook 继续成立。motivation 和三份 delta 的哈希仍与既有记录一致；没有新客户端布局、一次性迁移或生产操作要求。

### Agent Context Review — Mode A

本轮沿两条实际消费链审查：共享来源常量到四类独立审批 System Prompt，以及 Task snapshot/occurrence/repair 到同一步动态 reminder 包。确认来源解释、可用能力、输出协议和下一步动作各自完整，新增文本没有提升来源权限或改变实际工具能力；生命周期和恢复沿 R2 已核证设计。未捕获 provider 请求或运行模型，故结论限于方案可实施与正文组合闭合。

### 历史问题闭环

| Issue | Author Resolution 与本轮核实 | 状态 |
|---|---|---|
| R3-W1 | 接受并拆分四类 assembler；P2R 只读语义及 P12 common/action 完整正文见 `design.md:227-230,328-342,494-512`，与实际入口和原专用文本核对一致 | closed |
| R3-W2 | 接受并新增 D10、精确 cron_disabled 数据映射和各动态段条件句；运行限制、unknown 和原 limited 语义有明确区分，见 `design.md:528,539,587,602,615,678-686` | closed |
| R3-W3 | 接受并固定唯一配方、共享数据和模式尾段；A/B/C 与 Cron 关闭夹具明确，见 `design.md:514-541,688-704` | closed |
| R1-W1 / R1-W2 | 本轮未改变原消息追平/准入或撤销机制，保留 Round 2 关闭证据 | closed，retained_from: Round 2 |

### Issues

无新增 CRITICAL / WARNING；无仍开放的历史问题。

### Recommendations

无额外可选建议。实施按已定稿正文、消费者配方及 M1 验证边界推进；需要改变语义时按设计已有规则处理。

### Author Resolutions

- 接受 Round 4 结论，无实质异议；R3-W1/W2/W3 已关闭，提示词完整正文、准确消费者组合、已知运行限制和共步模板达到本轮设计交付要求。Gate 2 在新增正文复审后通过。
- 受审后只追加本段记录，design 与 motivation 无后续实质变化，保留 Round 4 哈希作为 retained 依据；未将文档比较、JSON 夹具或审批通过当作实际模型行为验收。本轮不实施、不部署。

## Round 5

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（同一独立 reviewer，继承调用方模型）
- review_mode: `full`
- mode_reason: 用户将开发及最终集成基线改为 Memory 分支；新的默认 document memory、来源失效、Dreaming 独立消费者和固定 skill-creator 已改变实际 Context 组合，不能只按文件迁移或旧问题 closure 放行。本轮重新核定全部设计对新基线的适用性，未变核心通过逐文件比较保留既有证据，重点展开 Memory 相关差异。
- started_at: `2026-10-30T20:06:12+08:00`
- completed_at: `2026-10-30T20:08:56+08:00`
- duration: `PT2M44S`
- checkout: `/Users/czj/.codex/worktrees/refactor-679-memory/nano-multiagent`，`codex/refactor-679-on-memory`，HEAD `c2a7fe3c3727db2c557a28915fda6ccee5e4298e`。
- migration_source: main `535a63d847fba1584b36a802c117998409ba3eed` 的全部 7 个 unit 文件；Round 1–4 与 Author Resolutions 原样保留。原实现取证基线 `28a8473e8` 只用于证明未变范围，不作为新 Memory 现状。
- frozen_scope: motivation、design、三份 delta-spec、M1 骨架；接手时 7 文件均已暂存未提交。本 reviewer 只追加本轮报告，不改变暂存区、不提交、不切分支。
- design_sha256: `13ad407e120622719713258ca7b1919f7c2b019788290bab6ce80370cb04d62e`
- motivation_sha256: `e7a1320fbdc365b6f3708917b1459830b76a9762a1fca14abf6c91cb5838d4b6`
- boundary: 只读代码/current specs、Git 对比和正文完整性检查；未实施、未运行模型或产品测试、未启动服务、未合并或部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

迁移后的设计与 Memory 基线相容，没有发现丢失其独有信息或职责冲突的实质问题。Gate 2 设计结论适用于上述冻结版本；本轮文档迁移不表示 refactor-679 已实现，也不构成合回 Memory 或部署的完成依据。

### Coverage 与证据

#### 迁移完整性、用户要求及 retained 范围

- `motivation.md` 逐字保留用户“从最新 unit-feat-676 分叉”及“彻底实现之后……先把设计全部搬过去并核对”的路由纠正。`design.md:11,22-32` 固定父提交、独立分支、完整迁移、后续集成目标及本轮仅文档边界，没有将历史 main 交付方向继续作为实施目标。
- 本 reviewer 通过 Git 目录清单核对迁移前后均为同一组 7 个文件；旧 design-review 和 M1 骨架保持，三份 delta 仅去除 EOF 空行。英文 text 代码块数量不变，仅 P3 和 P9 两块改变，其他固定正文、动态模板及 A/B/C 夹具没有暗中变化。
- 独立比较确认 **21 个原核心文件** 与 `28a8473e8` 逐字相同：IM 默认 PA、Task 通知/事务、messaging、control-routes、relay-delivery；dsh-integration TaskExecutionDriver、Global、sources/classifier/codex-context/codex、CronOwners、Cron/Task Feature；PA Inbox、SingleThread、Store、TaskExecution；Gateway/IM 两份 Task current specs。因此原 Task 消息产生、持久同步/准入、撤销映射、Schedule 删除/等待修复、审批装配和交付的设计可 `retained_from: Round 2/4`。这不是仅凭旧 Approved 放行；本轮另核新增 Memory owner 与这些路径的接点。
- 三份 delta 的 canonical target 和原场景仍适用；Memory 适配保留该分支 current behavior，没有新增 Memory 产品目标，因而不需要把已经存在的 Memory 契约再写成 ADDED。一个 M1 的串行范围、隔离 runbook 和无新增客户端布局判断保持。

#### Memory 动态上下文、PA 来源和任务撤销

- `design.md:27,110,249-260` 正确区分 document 动态 System Prompt context、显式 legacy 快照与待重排的 runtime/Skill 消息。实际 `knowledge/document-memory.ts:31-49` 每次 assembly 从当前库取得版本、资格、入口及失效原因，并提供固定主体库、角色、当前纠正、原 child 更新、唯一写者和实际工具限制；`features/memory-curation.ts:17-31` 仅在 legacy 使用原快照。保持这些 owner 和装配时点，能避免把文档入口误缓存为新的常驻段或混入环境消息重排。
- P3 的新增来源边界 `design.md:382` 与 `personal-security.ts:136` 的 Memory 原正文一致（仅句首大小写适配）：立即停止采用、通知受影响原 child、显式 exclude 的原请求引用、仅 Dreaming 修复、当前对话先用纠正、如实报告待修复范围及不擦除历史。它与 `document-memory.ts:40-48,94-117` 的说明/工具前置相容，没有恢复主 Agent 平行写者或授予来源变化新的业务权限。
- `design.md:184` 明确新 Task 映射须在 Inbox 清理前保存终态，同时保留 `knowledge.sources.pending → pa.sources list → knowledge.sources.sync → revokeSource`。实际 `global-agent.ts:275-294` 串行刷新完整资格集合，含已消费而无 unread 的来源；`:398-405,439-452` 保留 personal-state 和显式来源操作后的同步。Task 原消息追平不能充当 Memory 资格核对；已消费聊天历史保留也不代表可继续采用失效文档结论。
- `memory-documents.ts:145-183` 以 sourcesPending、generation 和版本 basis 决定当前入口是否可采用；`document-memory.ts:73-84` 为普通 child 保持主体固定库，`:43-48` 保留原 child 的当前纠正/停止采用规则。新增 Task 撤销不替代这些文档失效机制，也没有要求清除已消费历史。相关验证已进入 `design.md:781` 的空 unread、版本变化、source sync 和原 child 组合分支。

#### 固定 Skill 与独立维护消费者

- P9 `design.md:488` 与当前 `features/skill-creation.ts:9` 英文原文逐字一致，移除旧版“留给后台 Skill review”的不适用指示。`agent-config.ts:114-124,175-183` 不再因 skill_creation=false 移除该 section，`capabilities.ts:138-161` 将内置 skill-creator 与普通 allowlist/denylist 分开；`design.md:239-249` 的固定组合及其他 Skill/实际工具仍按配置限制与代码对应。
- Dreaming 是独立消费者，`design.md:249,259` 明确不套 P1–P9/Task reminder 或业务工具。`dreaming-agent.ts:42-68` 使用独立会话、完整 nano-dreaming section、显式工具集合和首请求预算，并筛除普通业务 section/context；`:73-96` 继续核当前来源与维护路径。文档动态 context 和普通 child 的规则不被误推广为 Dreaming 父 prompt 继承。
- `dreaming.ts:94-123` 区分自动停用与显式运行，显式请求仍检查生命周期、模式、并发与真实必需工具；`knowledge/runtime.ts:59-80,202-203,268-275` 保留 legacy 的父前缀，并暂停后台 Skill/combined 路径。`design.md:223,257-259,781` 与此一致；本轮不改 Dreaming prompt、输入/容量策略、Memory Skill 正文或写入归属。
- 当前 `dsh-agent`/`dsh-tool-skill` 仍为 `0.2.1-alpha.1`，但 `dsh-agent-context` 已锁定 `0.3.0-rc.6`（package.json 与 pnpm-lock 一致）。设计明确将新锁定版本的换窗/摘要组合验证留在实施期，不把旧依赖上的证据当成本基线已经运行通过。公开接入边界保持，没有 private import 或原生 patch 要求。

#### 验收与范围判断

- `design.md:781` 对应新增影响面，要求真实 document/legacy assembly、无 unread 时的失效信息、Task 准备不短路来源同步、原 child 停止采用、固定 Skill 与工具禁用、Dreaming 自动关闭但读取/显式入口保留。其余 M1 的实际 provider 请求、消息消费、停止/拒绝、交付和真模型要求保持；没有将受影响验证推迟到生产。
- 本轮未新增一次性 Memory 迁移或修改其已有生产流程；refactor-679 原有附加记录表/初始化方案仍按 R2 处理。没有新增 deployment-prompt 或生产功能演练的必要性。
- 本轮执行迁移清单、字节比较、正文保真及 `git diff --cached --check`，结果通过。只读源码/测试定义可支持设计落点，不证明模型已理解、分支已实现或真实产品已验收；这些状态不在本轮结论内。

### Agent Context Review — Mode A

重新覆盖 Global/PA 根、SingleThread、普通 child、四类独立审批，以及新增基线下需区别对待的 document consumer、legacy review 和 Dreaming。重点链路为固定正文→动态文档入口→来源/版本失效→原 child 当前纠正，以及 Task 直接消费/撤销与完整 Memory source sync 的组合。普通工作提示、维护提示、业务消息、持久知识和授权没有混同；新基线独有信息有现存 owner 和明确实施保留项。

### 历史问题闭环

| Issue | 本轮证据 | 状态 |
|---|---|---|
| R1-W1 | 原消息固定 through 与每步准入未变；核心 Task/relay 路径逐文件相同，新文档明确 Task 追平不替代 Memory 来源同步 | closed，retained_from: Round 2 |
| R1-W2 | Task revoke 映射/终态/原生候选过滤未变；新增 `design.md:184` 明确与 Memory 完整 source sync 的清理顺序及职责 | closed，retained_from: Round 2 |
| R3-W1 | 四类审批实际核心装配逐字相同，P2R/P10/P11/P12 正文与配方未变；P3 只影响 PA 工作指导 | closed，retained_from: Round 4 |
| R3-W2 | Cron 当前限制来源和驱动逐字相同，D10 及条件正文未变；Memory 自动开关不替代 Cron 能力事实 | closed，retained_from: Round 4 |
| R3-W3 | 唯一 reminder 包、共享数据、模式尾段与夹具未变；新的文档 context 由原 assembly 独立提供 | closed，retained_from: Round 4 |

### Issues

无新增 CRITICAL / WARNING；无仍开放的历史问题。

### Recommendations

无额外可选建议。本轮设计适配已覆盖实际基线差异；后续按已记录的 Memory 分支集成方向和实施验证边界推进。

### Author Resolutions

- 接受 Round 5 结论，无实质异议；迁移后的文档保留 Memory 分支当前信息与消费边界，Gate 2 对本轮冻结版本通过。受审后仅追加本段，design／motivation／delta-spec／M1 骨架不再改变，保留 Round 5 哈希作为 retained 依据。
- 完整性核对覆盖全部 7 文件；三份 delta 仅 EOF 格式整理，英文正文仅 P3/P9 变化且与 Memory 源码相应段一致，JSON 夹具可解析。21 个相关核心文件与旧设计代码基线字节相同；`git diff --cached --check` 与 `docs-check`（289 maintained Markdown sources、68 required routes）通过。源码／文档核对不作为产品或模型验收证据。
- 当前交付仅为 `codex/refactor-679-on-memory` 上的设计迁移与核对，保留独立 worktree。后续彻底实现、完成适用验证并复核 Memory 最新基线后，才合回 `unit/feat-676`；本轮没有产品代码修改、服务运行、合并或部署。

## Round 6

### Metadata

- reviewer_target: `/root/refactor_679_design_review`（同一独立 reviewer，继承调用方模型）
- review_mode: `delta`
- mode_reason: 限定审查 `design.md` 权威追平与步骤准入中的两段时序修订。产品准备接口、持久消息/撤销模型、权限、正文及 owner 未变；改变的是同一步内准备与原生 assembly 的先后关系，因此展开相关 Context 消费链，未重新接手产品或代码验收。
- started_at: `2026-10-31T15:16:12+08:00`
- completed_at: `2026-10-31T15:17:39+08:00`
- duration: `PT1M27S`
- checkout: `/Users/czj/.codex/worktrees/refactor-679-memory/nano-multiagent`，`codex/refactor-679-on-memory`，HEAD `36cef9604935754e1da0a11b0616e194a0d56523`。
- frozen_scope: `design.md:164-165` 的外层 assembly 准备及 pre-step 候选处理；与 HEAD 的 diff 仅该处一段改为两段。并行工作中的测试、代码审查、verification、acceptance 等产物只作明确引用，不改动。
- design_sha256: `18e2be7bd377b3c090b2f65f07bfe0e7ca4148b415c6500ad21134a84571d579`
- boundary: 只读实际入口、锁定依赖公开类型/行为和已有失败日志；只追加本轮报告。未修改产品代码、未运行测试或服务、未接手并行验收、未提交/合并/部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

把完整来源及 Task 准备前移到本步外层 `system-prompt/assemble` 的 `next()` 前，与锁定运行时的真实顺序吻合，并保留 pre-step 的候选剔除、补入和拒绝职责。未发现本次修订与既有权限、恢复或 Memory 唯一写者设计冲突。该结论只批准设计调整；已有红测仍需在实现后验证通过。

### Coverage 与证据

- **确认问题及证据边界**：`output/refactor-679/pa-empty-memory.log:5-24` 记录跨包原生 fixture 失败：产品查询顺序已是 `pa.sources → task.context.sync` 两轮，但首个捕获请求仍为 `Source generation: 0`、`source_eligibility_pending`，未达测试要求的 generation 1。这是当前 assembly 滞后的直接证据；该测试在 `apps/node/tests/global-inbox-native.test.ts:26-31` 截获 provider 消息，不能描述成真实模型行为失败，也不能凭日志声称第二个请求的所有断言已执行通过。
- **真实运行时顺序**：锁定 `@deepseek-ai/dsh-agent-loop@0.2.1-alpha.1` 的 `lib/index.js:902-924` 明确执行 claim → `systemPrompt.assemble(assembleContextFor(this, signal))` → `runtimeContext.project` → `agent/pre-step`；`:950-978` 在通过后才记录 step/start 并执行模型步骤。当前 `task-context.ts:21-26` 到 pre-step 才准备，而 `knowledge/document-memory.ts:31-49` 在 assembly 中读取当前文档资格和 generation。新设计先准备、再放行 `next()`，让同一次 assembly 的 Memory context 读取同步后的状态，再由原生生成本步快照；无需重造快照或改写模型消息。
- **公开接口与实际 owner**：公开 `dsh-system-prompt/lib/types/index.d.ts:15-27,37-44` 定义 assemble waterfall、scope 和本次显式 signal；公开 `dsh-agent/lib/types/dispatch.d.ts:101-109` 及导出的 `assembleContextFor` 同时提供 agent/scope 和当前 turn signal。外层 prepend hook 可以在 `next()` 前完成原有准备。现有 `index.ts:180,227-230` 由 KnowledgeRuntime 管文档 context、TaskContextDriver 管业务准入，继续由后者承接本次前移最直接，不需要新服务、loop、私有 import 或 DSH patch。依赖源码在本轮仅作为顺序取证材料。
- **同一步临时结果与恢复**：设计规定只处理有直接可信 root binding 且有 turn signal 的 assembly；结果仅在该 Agent 本步暂存，pre-step 取走，下次 assembly 重新准备。锁定原生路径每次 pre-step 前均调用 assembly，因而无需跨步骤沿用旧 through 或把临时缓存持久化。prepare 仍先核对已持久消费证据，再返回尚待呈现的原 ID；准备完成或缓存存在不成为已消费回执。中断后重新准备与原持久 cursor/revoked/consumed 恢复规则一致，原 turn signal 不被留作后续 turn 控制。
- **来源与撤销边界**：`personal-assistant/src/task-context.ts:20-41,65-81` 先调用完整来源刷新，再固定 through/追平；`global-agent.ts:277-299` 仍串行执行 pending → 权威来源集 → sync → Inbox 清理。前移只改变发生时点，不把 Task 追平等同于 Memory 同步。候选已经在 assembly 前 claim，因此保留 pre-step 对候选 ID 的撤销过滤和原文补入是必要的；只调用 inbox.remove 不能替代它。准备限制仍由 pre-step 判定独立输入或 reject，停止 fence、当前 lifecycle 和工具权限没有被准备接口授予或解除。
- **独立消费者与预览**：当前 preview/快照调用 `index.ts:369,389,563,581` 未传 turn signal；设计明确跳过它们，避免 UI 查询触发产品同步。普通 child 和 Dreaming 无自身 root binding，即使 Dreaming 显式 assembly 带 signal 也不进入这条业务准备路径。它们继续按既有固定库动态消费及独立维护 preset 工作；Dreaming 正文、工具、预算和唯一正式写者不变。
- **验证足够且有界**：新增空 unread PA 测试 `global-inbox-native.test.ts:63-77` 验证两次当前 runtime-context 的 generation、排除后失效说明及每步只一次来源/Task 查询，能直接区分“本步已更新”与“下一步才更新”。修订同时保留既有 claimed-candidate 撤销、消费回执丢失后重启、离线及 child 验证；如 `task-context-originals.test.ts:21-51` 已覆盖原 ID/ACK 恢复与 claim 后撤销的观察面。修复后必须运行相关验证，本轮仅核验其设计覆盖，不代报执行结果。

### Agent Context Review — Mode A

本轮沿“完整 PA 来源同步 → 文档动态 context 组装 → 原生 runtime snapshot → Task 候选准入 → 当前 provider 请求”核对来源、时点与失效语义。关键改动修正模型当前可见信息滞后的接线位置；没有更改提示正文、事实权限或持久写者。异常时的限制表达及相关输入拦截保持，不以恢复缓存、socket ready 或已经 claim 推断事实有效。

### 历史问题闭环与 retained 范围

| 范围 / Issue | 本轮依据 | 状态 |
|---|---|---|
| R1-W1 | 固定 through 与持久追平不变；准备前移到 assembly 前，候选仍在准备完成后由 pre-step 准入 | closed，retained_from: Round 2；本轮复核时序 |
| R1-W2 | 原生队列清理及 already-claimed 候选过滤继续由 pre-step 执行，未把 assembly 准备当消费 | closed，retained_from: Round 2 |
| R3-W1/W2/W3 | 四类审批配方、已核实 Cron 限制及共步模板没有本轮变化 | closed，retained_from: Round 4 |
| Round 5 Memory 基线 | document/legacy、完整来源集、原 child 更新、固定 skill-creator、Dreaming 独立 preset/唯一写者均未变；本轮专门补核来源刷新与当前 assembly 的先后关系 | retained_from: Round 5，时序以本轮修订为准 |

### Issues

无新增 CRITICAL / WARNING。旧设计批准不作为本次实现已修复红测或产品验收通过的证据。

### Recommendations

无额外可选建议；停止扩展复审范围，按既定修订和上述最窄相关验证完成实现核对。
