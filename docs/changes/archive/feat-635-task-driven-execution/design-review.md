# feat-635 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design_review_635`（独立 reviewer；未参与设计编写）
- review_mode: `full`
- mode_reason: 首轮 Gate 2，完整核对需求、实际产品组装、公开 DSH 接口、四份 delta、原型与 M1。
- started_at: 2026-10-22T12:15:15.623038+08:00
- completed_at: 2026-10-22T12:22:20+08:00
- duration: 425 秒
- baseline: `main @ 540190927`；受审设计及 delta 为冻结的未提交文件。仓库另有用户 dirty/staged/untracked 内容，本轮仅新增本报告，未修改设计、代码或索引，未提交。
- inputs: [spec.md](spec.md)、[design.md](design.md)、`specs/im/{task-graphs,agents-nodes}.md`、`specs/gateway/{task-graphs,agent-capabilities}.md`、[prototype.html](prototype.html)、[prototype-review.md](evidence/prototype-review.md)、其中六张 PNG、`M1/.gitkeep`。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

Task 唯一持久真相、PA 协调、DSH 原生生命周期驱动和 Schedule 校验的职责划分可成立，已安装公开 API 足以支撑主要方案。尚有两处实际执行链未闭合、一处 delta 冲突和一处等待异常信息丢失，会使实施偏离已确认行为；修订后复审。本轮不要求实现或产品验收先行。

### Coverage 与证据

#### 需求与用户约束

已按 spec 的 Q1–Q16 最新结论核对，未把旧的“doing 内等待”讨论作为要求。七状态/五分组、全部本人且覆盖各层的责任集、todo 分配不开工、waiting 有效安排、消息提前恢复、父子不自动联动、完成/待确认退出、无专属轮数预算、不处理旧数据及 Goal 默认关闭均有明确方案。等待 reason 由模型判断而非新增审核模型，符合范围；自动输入使用系统来源，保留真实身份、PA 审核与原生 Goal 授权边界。Q12 的单项暂缓/关闭及改派在执行中的作用尚未闭合，见 R1-W2。

#### 实际生产组装与职责判断

独立读了以下真实入口，而非仅按设计中的文件名确认：

- [`apps/node/src/main.ts`](../../../../apps/node/src/main.ts) 的 RuntimePartitions 初始化、`SingleThread`/`GlobalAgent` 实例化、`product.call` 注册、onReady/reconnect 恢复。各产品模式确实共享 RuntimePort，PA 分区也在此装配；新增协调应沿该路径进入普通/PA 分区。
- [`packages/personal-assistant/src/global-agent.ts`](../../../../packages/personal-assistant/src/global-agent.ts) 的主 binding、Inbox wake、产品调用和 `/stop`，以及 [`single-thread.ts`](../../../../packages/personal-assistant/src/single-thread.ts) 的聊天绑定、自动出站与审批。这两种出站方式不同，不能只让原生 Agent 跑起来就认为交付链已闭合。R1-W1 指出具体缺口。
- [`session-controls.ts`](../../../../packages/personal-assistant/src/session-controls.ts) 与 [`store.ts`](../../../../packages/personal-assistant/src/store.ts) 已有持久 control intents、串行控制、恢复与回执。复用它们承载停止屏障合理；新增 action 必须在 session.ensure/自动投递前恢复屏障，设计已要求，M1 也有专门竞态验证。
- [`apps/im-server/src/gateway.ts`](../../../../apps/im-server/src/gateway.ts) 的 `task_graph.command`、[`personal-actions.ts`](../../../../apps/im-server/src/personal-actions.ts) 的 prepare/review/commit、[`task-graphs.ts`](../../../../apps/im-server/src/task-graphs.ts) 的真实 Agent/空间/会话资格、事务/revision/幂等回执。设计把 async Schedule 检查放在同步 SQLite 事务外，并要求 PA 审核后对冻结 payload 检查、事务内复核，符合当前组装与不可 await 的事务边界。

架构上应由 IM 保持 Task 状态及权限真相，PA 解析身份、聊天作用域与产品交付，集成层管理原生 Agent 队列和生命周期；当前设计大体遵循此分工。复用 NodeStore 控制、Task 回执、CronOwners 与原生 Schedule，比新增目标存储、提醒系统或 Agent Loop 更简单。最多 60 秒、仅有 waiting 时开启的元数据检查有明确失效检测用途，不属于另造模型轮询器。无须为本需求新增通用能力依赖框架。R1-W1/W2 可在这些既有职责内补齐，不要求大规模抽象。

#### DSH 公开 API 与关键运行边界

核对本仓安装的 `0.2.1-alpha.1` 包声明和实际 JS：

- `@deepseek-ai/dsh-agent` 的公开 `Agent.status`、`inbox.nextTurn/nextStep`、`followup`，以及 `agent/pre-step` waterfall 支持检查/替换进入 step 的消息；`Inbox.remove/replace/prepend` 可保留竞争输入。已安装 goal-round-driver 也使用这些公开能力。设计不必 private import 或 fork。
- `@deepseek-ai/dsh-goal` 根 export 的 `GoalService.disarm(agent)` 确实存在；其职责是撤销 activation，原生 driver 检查 armed。关闭 Feature 时同时撤销自动激活、过滤既有 goal 输入、隐藏工具和 prompt 比只改 allowlist 完整。依赖需按设计声明到集成层，不能跨包导入。
- [`cron-owners.ts`](../../../../packages/dsh-integration/src/cron-owners.ts) 已有 Agent realm、catalog、原 session 约束与关闭时读存储；原生 Schedule catalog 含 status、sessionId 和下一次时间数据，足以实现目标 inspect。一次性提醒已消费与未来有效时间的区分有实现依据。
- [`product-bridge.ts`](../../../../packages/dsh-integration/src/product-bridge.ts) 的既有 call 必须带 ToolRunContext/callId；设计明确另增受信生命周期 snapshot 入口，避免伪造工具调用，合理。
- stop 先持久屏障再取消/核对写入/原子暂停、unknown 不报完成、旧提醒先重读、改派不继承旧 Schedule 写权、普通输入优先均已写明。实际并发正确性应由 M1 的原生生命周期及真栈测试证明，本轮未把设计文字当作测试通过。

#### Delta 覆盖

四个 canonical target 正确，IM/Gateway 消费者视角基本合理；已经修改的 Requirement 保留了原 Scenario，六状态通过 REMOVED/ADDED 改名且保留提交结果/父子语义。Goal 的 IM 配置和 Gateway 执行分层也正确。原生 Schedule 自身语义没有改变，因此 heartbeat-cron 不新增 delta 合理。

但 current IM Task 另有“六状态”及“领取才开工”的保留正文，Gateway 工具契约仍有无条件“记录不调度执行”，本轮 delta 未消歧，见 R1-W3。

#### 原型独立体验判断

使用独立 IAB tab 打开 `http://127.0.0.1:46350/prototype.html`，未使用作者的 Playwright session。先看实际画面，再操作等待详情、暂缓、恢复、关闭，随后切换安排失效、iOS 示意/节点离线与 Goal 开关；读了作者六张截图。独立操作覆盖桌面 Web 1280 宽与 430 宽 iOS 示意容器；390 宽窄屏依据作者已渲染 PNG 复核，本轮没有冒称独立运行原生 iOS。

- 五栏仍是主要阅读结构，进行中两卡分别标推进中/等待中；暂缓后待办从 2 变 3、进行中从 2 变 1，恢复后还原且等待摘要消失。动作反馈与分组变化一致，不需用户记住另一套状态。
- 详情遮罩保留原看板空间和位置；标题、状态、负责人、等待说明、正文、动作顺序清楚。iOS 使用纵向组和 sheet 示意，顶部关闭与内容下方动作已有具体方案；并非只写“原生适配”。与当前 `task-progress.tsx` 的五栏、`TasksView.swift` 的纵向组/sheet、`TaskModels.swift` 的状态消费核对一致。生产画面基线采用作者只读观察记录；本轮未另抓真实私人任务截图。
- 离线画面把业务等待与负责人离线分开，保存的检查时间不冒充执行成功；Goal 默认关闭，实际切开/关后显示下一轮生效反馈，独立 Task 的说明可读。
- 安排失效详情把原业务等待原因和恢复条件替换掉，用户在作出恢复/暂缓决定的地方缺少必要信息，见 R1-W4。该问题来自实际渲染，PNG 与代码相互印证，不是颜色或样式偏好。

原型未证明真实保存、Schedule、分页、动态字号、VoiceOver 或真正 iOS sheet 触感；设计和 M1 已把这些放在真实实现验收，不据此要求设计阶段交付后端。

#### Milestone 与验收前置

单 M1 覆盖跨包共同闭环、没有冲突并行组，`M1/.gitkeep` 骨架存在。R1–R7/W1–W4 将主要用户结果、竞态、公开依赖检查、Web/iOS 真栈与原型对照绑定在一起；不把仅落 waiting 或仅写 driver 当可单独交付成果。Runbook 有隔离启停、构建、健康、版本核对和清理方法。

独立检查 `config/e2e/gateway.yaml` 与 e2e-up 的隔离账号/三个 Agent，`/Applications/Xcode.app` 和 iOS 26.4 simulator runtime 可用，代理 health 返回 200；作者报告已做一次真实模型可调用性检查。资源来源已落实，本轮不额外调用付费模型或启动产品栈。验收必须仍使用独占 simulator/临时 runtime，不碰生产或其他验收实例。无需 Feishu 才能覆盖本期必验旅程；协议边界注入失败不等于真实外部送达，设计已正确限制证据。

### 历史问题闭环

首轮，无历史 issue、Author Resolution 或 retained coverage。

### Issues

#### R1-W1 — 新原生续跑来源没有进入 SingleThread 的出站与审批绑定设计

- 位置：[design.md](design.md) “原生续跑与提示词”（110–136 行）及现状/组装描述。
- 证据：方案直接 `followup` 注入 `source.kind='nano-task-continuation'`。当前 `NodeStore.runtimeInput`（`store.ts:210–226`）只把原生 `schedule` 和 `nano-system/heartbeat` 转为已接纳产品 input；`SingleThread.drain`（`single-thread.ts:205` 起）只迭代这些 input 建立 delivery，`approval`（345–347 行）找不到 delivery 会抛出 `Approval has no product output binding`。当前生产组装没有把任意原生 turn 自动投影为聊天回复的兜底。设计虽列出 store.ts，但只解释 control intents，未明确新来源如何接入这条链。
- 未修后果：SingleThread 的第二轮 Task 可以实际跑工具，却没有其正常结果/模型错误的聊天投递；需要人工权限时也无法绑定审批卡。只在 Global 的显式 send_message 路径验证会漏掉这个问题。
- 要求：明确复用原生 input 记录/回执机制接入新来源及重启重放，区分 Global 显式发言与 SingleThread 出站，决定自动轮次何时保持安静、何时交付有意义结果/阻塞和审批。无需伪造用户或新的 relay 请求。补到 M1 的 SingleThread 自动续跑→人工审批→结果/故障可见用例，不能只验 Task 状态或模型工具调用。

#### R1-W2 — 单项暂停/关闭/改派发生在运行中的下一步约束没有闭合

- 位置：[design.md](design.md) 第 3–4 节，尤其 102、110–112 行，以及第 6 节改派段。
- 证据：变更事件只使 reconcile 失效检查；当前写出的驱动逻辑在 idle 入队，并在 pre-step **针对本插件的输入** 重读。某条自动输入已经被第一步消费后，同一轮后续工具/模型步骤不再携带该输入。UI 此时把 A 设为 paused/closed 或改派，现有方案没有说明怎样让正在运行的普通/后续 step 收到这次责任撤销；“旧负责人下一次 pre-step/工具读取不再获得该责任”只是预期，缺少对应检查或传递路径。`/stop` 的整 session 屏障不能替代单项操作，因为同一 Agent 还可能承担 B。
- 未修后果：用户已暂缓 A，模型仍可按旧上下文继续发起 A 的后续动作，直到整轮自然结束；改派时也可能两边继续工作。与 spec Q12 的“尽快在可中断边界停止该任务、不再发起新的该任务动作”不一致。
- 要求：明确运行中责任变化如何在下一个原生可中断边界进入模型/执行判定，以及如何保留 B 的合法推进。可以复用现有 steer/pre-step，按变化发送精简责任撤销信息；不要求每步注入整份历史或为所有工具新增 Task ID。将“同轮多步执行 A 时 UI 暂缓/关闭/改派，下一边界处理变更且 B 不被无条件停止”列为专门验证。已经越过外部副作用边界的动作仍如实保留。

#### R1-W3 — Delta 归并后仍会保留互相矛盾的开工/状态契约

- 位置：`specs/im/task-graphs.md`、`specs/gateway/task-graphs.md` 的 MODIFIED 覆盖范围。
- 证据：canonical `docs/specs/im/task-graphs.md:262` 的原生编辑 Scenario 明确“保持……六状态”，未被本次 delta 修改；176 行仍写“分配本身不代表……开工；领取才表示接手开始推进”，没有限定 todo，与本期 doing 改派后新负责人自动接续不一致。canonical `docs/specs/gateway/task-graphs.md:106` 的工具参数契约仍无条件保留“记录不调度执行”，需要区分图依赖自动调度与 doing 持续责任，不能靠新 Requirement 隐式覆盖旧断言。
- 未修后果：实施或 verifier 按未修改 canonical 场景判断，会分别得到六状态/七状态、改派还需领取/自动接续、记录不执行/doing 驱动的不同结论。
- 要求：补足相应 MODIFIED Requirement，保留其中并发编辑、权限、显式保存等未改变 Scenario，只修改实际冲突的状态/开工语义；其他“依赖完成不机械启动后继”的约束继续保留，不需要全面重写 Task spec。

#### R1-W4 — 等待安排失效时，详情丢失原等待原因和恢复条件

- 位置：[prototype.html](prototype.html) 第 16 行 `refresh` 的 invalid 分支；安排失效截图（本地证据 `evidence/feat635-web-invalid.png`）；design 的等待详情 must-match。
- 证据：正常详情显示“等待负责人确认预算”和“预算确认后，继续选择供应方案。已在所属会话发出询问。”；切换安排失效后，这两处被“等待安排需要处理”和“关联的定时安排已删除……”完全替换。页面仍直接提供恢复推进/暂缓按钮，只有背景卡片残留简短原因，详情没有原恢复条件。Web 与 iOS 共用这一渲染逻辑。
- 用户代价：Schedule 失效是技术事实，不代表业务阻塞解除；用户在详情决定是否恢复时却看不到仍在等什么及满足什么条件才能继续。窄屏/原生遮罩下也无法靠背景补回这层信息。
- 要求：失效诊断作为等待安排的独立状态呈现，保留原业务 reason/恢复条件；仍显示暂无有效检查，不把旧时间当有效承诺。同步原型和 must-match，并复查失效、离线/unknown 与正常等待三种状态的信息关系。

### Recommendations

无额外建议；本轮只列影响已确认行为及下游一致性的必要修订。

### Author Resolutions

- **R1-W1 — accepted**。核对 `NodeStore.runtimeInput`、`SingleThread.drain/approval/stream` 后确认新来源确实不会自动获得现有投递与审批绑定。design 新增 §4.1：原生 message ID 幂等投影、durable 重放、绑定目的地、纯自动轮次缓冲及 NO_REPLY、强制审批 delivery、失败可见与 Global 显式发送分离；M1-R5/W2 与 Gateway delta 新增相应验收。未另建消息队列或伪造入站 relay。
- **R1-W2 — accepted**。原先仅重查自动输入不能覆盖已进入同轮的后续步骤。design §4 补齐收到变更先标 dirty、RuntimePort invalidate、原生 steer、所有根 Agent pre-step 对 dirty 取最新责任差量的链路；旧 change 输入重建，保留 B/普通输入，已进入执行的副作用不回滚。M1-R6/W2 与 Gateway delta 加运行中单项撤销场景。
- **R1-W3 — accepted**。IM delta 补足“人与 Agent 在相同权限原则下维护任务”“原生任务流程保持统一的信息与编辑体验”两个完整 MODIFIED Requirement，分别限定 todo 分配与七状态；Gateway delta 补足“任务工具公布动作与参数契约”，区分 DAG 不自动开后继与 doing 持续责任。用原 Requirement 全文抽取后局部替换，保留并发编辑、资格、显式保存等全部未改场景；各 MODIFIED/REMOVED 标题已核实唯一锚定 canonical。
- **R1-W4 — accepted**。原型保留业务 reason/恢复条件，新增独立诊断段并增加 unknown 演示；design must-match 与 IM delta 同步。重渲染 Web 1280 与 iOS 390 的失效画面，以及 Web unknown；证据见 `evidence/*-r2.png` 和 prototype-review 的 R2 段。旧截图保留为 R1 历史证据。

以上均为既有需求范围内的方案修正，首文档用户决定、架构责任归属、单 M1 均未改动；需独立复审后才能关闭 Gate 2。


## Round 2

### Metadata

- reviewer_target: `/root/design_review_635`（原独立 reviewer；未参与方案修订）
- review_mode: `full`
- mode_reason: 作者对四项问题作出实质修订，其中包含 RuntimePort 共享接口、运行中责任变化传播、原生 turn 产品投影与 M1 退出条件；因此重新核对完整设计及其波及链路，而非仅按 resolutions 关闭问题。
- started_at: 2026-10-22T12:26:38.199+08:00
- completed_at: 2026-10-22T12:29:56.733+08:00
- duration: 199 秒
- baseline: `main @ 540190927`，与 Round 1 相同；spec 无本轮变更。仅向本报告追加 Round 2，未改设计、代码、索引或其他用户文件，未提交。
- inputs: 重新通读 [design.md](design.md)、四份 delta、Round 1 Author Resolutions 与更新后的 [prototype-review.md](evidence/prototype-review.md)，核对 spec 已确认约束，独立操作更新原型并查看三张 R2 PNG；复查关键原生 API、NodeStore 投影及 SingleThread 审批入口。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

四项旧问题均有具体设计、delta 或可见原型证据闭合。方案可以进入实施；本结论不代表自动续跑、审批投递、并发停止或真实 Web/iOS 已经实现并通过产品验收。

### Coverage 与证据

#### 需求、现状与职责

重新核对七状态/五分组、各层本人责任集合、todo 分配不开工、doing 持续推进、waiting 的真实安排与提前恢复、父子结果整合但不机械联动、待确认/完成退出、单项与会话停止、无 Task 专属轮数预算、不做旧数据迁移和 Goal 默认关闭。修订未改变用户已确认范围；自动来源仍是系统输入，不能取得直接真人授权。

实际组装基线未变，Round 1 已独立读取的 `apps/node/src/main.ts`、GlobalAgent/SingleThread、session-controls/NodeStore、IM gateway/personal-actions/task-graphs 与 CronOwners 仍是当前落点。本轮针对新链路复查 `NodeStore.runtimeInput` 和 `SingleThread.approval`：当前代码确有来源白名单与 delivery 绑定要求，因此 §4.1 的原生 input 投影是必要且落在正确模块的补充。IM 继续持有任务状态/权限真相；PA 负责身份、会话和交付语义；NodeStore 复用既有原生事件与 input/delivery 持久化；DSH 集成层负责公开生命周期和队列。没有新增第二套 Loop、Task 目标库、relay 入站请求或出站队列。

复查已安装公开声明中的 `agent.steer` 和 `agent/pre-step`；它们支持 §4 的变化传递及下一边界校正。Round 1 已核实的 followup/Inbox、GoalService.disarm、Schedule catalog 与受信生命周期 snapshot 能力仍适用。新增 dirty 标记和精简差量有明确用途：让已消费自动输入后的同轮步骤也接到责任撤销，不是每步重放全量历史。全 session stop 仍沿既有持久控制意图和恢复屏障，单项变更不误停 B；已越过副作用边界的动作不承诺回滚。职责和复用程度适当，无需为此建立通用任务工具拦截框架。

等待校验仍在异步路由、SQLite 事务外执行，审核后针对冻结 payload 检查，事务内复核 revision/负责人/digest；幂等重放、unknown、安排消费或删除、改派后的旧安排权限、重启恢复与 Goal 关闭路径均未被修订破坏。Round 1 的实码证据在相同 baseline 下继续成立，本轮未把设计承诺当成已通过的运行测试。

#### 两条新增执行链

- **自动 turn 到产品交付**：§4.1 明确以原生 message ID 幂等投影 `task_continuation`，绑定原会话目的地，不再次 submit；`nano-task-change` 并入已有 turn 时是 context-only，竞争导致独立 turn 时仍投影。Global 保持显式发送；SingleThread 进入既有 drain/prepareDelivery/stream/receipt，纯自动普通输出缓冲至 terminal，NO_REPLY 可保持静默，审批强制取得 delivery，模型故障走可见 notice。来源尚未确认时的早到流、重启重放及已展示审批不被静默覆盖都有说明，消除了只跑原生 Agent 而没有产品绑定的缺口。
- **运行中责任变更**：§4 明确 `task.execution.changed → dirty → RuntimePort task.execution.invalidate → agent.steer`，所有根 Agent pre-step 对 dirty 重取最新责任，不仅处理首次自动消息。过时 change 输入按最新快照重建，只传撤销和仍需推进的 ID，保留普通竞争输入，空闲无责任不新增空 turn。快照失败不沿旧责任继续发起相关动作；已执行副作用与安全边界限制如实写明。

上述约定已足够指导实现与测试，不需要在设计审查阶段展开逐行时序代码。M1 仍需通过真实竞态和第二轮审批/交付证据证明正确。

#### Delta 与 milestone

四份 delta 仍锚定正确 canonical 文件。IM 新增的两个完整 MODIFIED Requirement 分别消除了 todo 分配/doing 改派及原生六状态残留，保留了权限、资格、保存与并发编辑场景；Gateway 的完整工具契约明确 DAG 依赖不机械开后继与 doing 持续责任的区别。运行中单项变化和自动续跑交付/审批已进入消费者可观察 Scenario，Goal 两份 delta 保持原边界。未发现保留的相反断言或删漏无关 Scenario。

单 M1 无并行写范围冲突；R5/W2 明确 SingleThread 第二轮自动推进的人工审批、结果/模型故障与静默行为，R6/W2 明确多步执行 A 期间 UI 暂缓/关闭/改派在下一边界生效且保留 B。原有 waiting、stop/restart、旧提醒、公开依赖、Web/iOS、真模型和证据清理要求仍在。真实验收资源/隔离 runbook 未改变；Round 1 已检查的 Xcode/iOS simulator、隔离 E2E 配置及代理可达性仍为本次设计前置证据，未重复启动产品或付费模型。实施时仍须确认当时资源状态并独占临时运行环境。

#### 独立原型体验

本轮在独立 Chrome tab 打开作者静态服务，未接入作者的浏览器 session；实际看图并切换 Web 有效/失效/unknown 等待，再切换 iOS 交互示意的失效详情。桌面实际 viewport 为 1538×944，iOS 示意容器宽 430；另查看作者新增的 Web 1280 及 iOS 390 PNG。独立 tab 已关闭。

正常等待保留业务原因、恢复条件和有效下次检查；失效画面保留相同业务内容，将“关联安排已删除”放在独立诊断段，并显示暂无有效安排；unknown 仍保留业务内容，保存时间明确标成尚无法确认有效，未冒充未来执行承诺。iOS 示意中原因、恢复条件、诊断、检查状态、任务正文和两个操作均清楚分层，操作可见，没有用背景卡片补足详情信息。原五栏、负责人运行状态分离与暂停/恢复布局未改变，Round 1 已操作的相关路径证据继续适用。must-match 与 IM delta 已同步此信息关系。

可复核证据：Web 失效 R2（本地证据 `evidence/feat635-web-invalid-r2.png`）、Web unknown R2（本地证据 `evidence/feat635-web-unknown-r2.png`）、iOS 失效 R2（本地证据 `evidence/feat635-ios-invalid-r2.png`）。以上是原型内容关系及交互方案证据；原生 iOS 触感、动态字号/VoiceOver、真实后端和投递验收仍由 M1 执行，本轮未宣称验证。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|
| R1-W1 | accepted：补产品 input 投影与分模式交付 | design §4.1、NodeStore/SingleThread 实际入口、Gateway 自动交付 Scenario、M1-R5/W2；原生 message ID 幂等、审批绑定、静默/故障与重启路径已明确 | closed |
| R1-W2 | accepted：补运行中 dirty/invalidate/steer | design §4、公开 steer/pre-step 声明、Gateway 单项变化 Scenario、M1-R6/W2；覆盖已进入同轮的后续步骤，并保留 B | closed |
| R1-W3 | accepted：补完整 MODIFIED Requirement | IM 人与 Agent/原生流程两个 Requirement、Gateway 工具契约；状态、todo 分配、doing 改派与 DAG 语义一致，原有场景保留 | closed |
| R1-W4 | accepted：分离业务等待与安排诊断 | 独立 Web/iOS 示意实际渲染和三张 R2 PNG，design must-match 与 IM delta；正常、失效、unknown 均保留原因/恢复条件 | closed |

### Issues

无未解决 CRITICAL 或 WARNING。

### Recommendations

无额外建议。继续按 M1 验证已明确的运行与客户端边界即可，不追加假想边界工作。

### Author Resolutions

Round 2 结论 accepted，无未解决实质问题或额外建议。作者核对受审文件哈希，除本报告外与 R2 冻结版本一致。

审查后仅将 spec.md 首部状态从“待技术设计”改为“设计通过 Gate 2、待 M1 实施”，添加 design/review 相对链接；需求正文、设计、delta、原型、M1 和证据内容均未变。此为状态归档更新，retained_from: Round 2，不触发设计复审。


## Round 3

### Metadata

- reviewer_target: `/root/design_review_635`（原独立 reviewer；未参与本次方案修订）
- review_mode: `full`
- mode_reason: 用户纠正了 Goal 的产品需求和能力边界，故完整复核受影响的 Goal 配置切面，包括实际装配、工具目录/执行选择、配置生效、双端入口、delta 与 milestone；未改变的 Task 体系不重复审查。
- retained_from: Round 2 的 Task 状态、责任集合、waiting、运行中撤销、产品交付与审批、stop、原型任务面判断；本轮七份 dirty 文档只改变 Goal 配置，未把历史 Goal Feature 通过结论保留为当前证据。
- started_at: 2026-10-22T16:36:02.812+08:00
- completed_at: 2026-10-22T16:39:53.246+08:00
- duration: 230 秒
- baseline: `/Users/czj/.codex/worktrees/unit-feat-635/nano-multiagent`，`unit/feat-635 @ 89a4beeb80ce102e9a0a39acb162bc0f2a34342f`。开始时仅七份澄清文档 dirty，未改产品；本轮只追加本报告，不修改实现、设计、索引，不提交。
- inputs: spec Q16/目标/验收场景、design 决定 7/§7/前端契约/M1、两份 Goal delta 及 current 预览、实际 Node/运行时/Web/iOS 入口、更新原型。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

将 Goal 还原为三个普通可选工具的方案成立；移除 Feature、三工具联动及额外原生生命周期控制符合用户最新澄清。唯一需收口的是配置生效边界：design 已改为普通工具的立即收缩/idle 增加，但 M1 和两份 canonical 的总配置契约仍保留整轮不切换/下一轮整体生效，现有 Goal delta 只引用“普通规则”而没有消歧。

### Coverage 与证据

#### 最新需求与真实产品装配

以 Q16 新增用户原话为准：没有 DSH Goal Feature，总开关不参与授权；默认集不选 `create_goal/get_goal/update_goal`，显式名单逐项有效；选择一个不改变另两个；不改 Goal 原生生命周期，不做历史迁移，不影响独立 Task 责任。新 spec、design §7、两份 Goal Requirement 对这一主体语义一致。

实际链路已核到生产入口：`apps/node/src/main.ts:180–212` 将 Agent/node 能力请求交给原生 `configuration.catalog` 后经 `projectCapabilities` 返回，提示预览另经同一候选配置；`main.ts:356–362` 的 ConfigurationOperations 调用 `configuration.apply`。集成层 `index.ts:311–338` 的 catalog/selection 和 `agent-config.ts` 共用 ToolSelection，catalog 会暂时撤掉本 Agent 限制再列完整原生工具，随后恢复调用限制，因此“默认关闭但目录仍可选择”有真实接线基础，不需要新 Feature 或额外工具注册。

`apps/node/src/capabilities.ts:65` 已把三个 Goal 工具设为 `default_on:false`；待删的是 features 数组中的 dsh_goal。`ToolSelection.selection/refresh` 当前 Feature 硬 gate 与 §7 冲突，设计已要求只在未配置 allowlist 时排除三个工具、显式列表逐项保留；直接工具 dispatch 和配置预览应继续共用这一选择。现有 global 固定基础工具与上下文工具规则不包含 Goal，不会要求三工具联动。

#### 配置生命周期与复杂度判断

独立核对 `ConfigurationScopes.attachAgent/setFeatures/restrictSelection`、`index.ts:configuration.apply` 和 `features/goal.ts`。上一版确实新增 Goal plugin、disarm、goal 消息过滤、prompt Feature gate、retainedGoals 及配置 apply 的 Goal 例外。§7 明确移除这些特例及 `@deepseek-ai/dsh-goal` 直接依赖，保留原生工具与权限，足以指导删除对应专用行为。无 Goal 工具被有效选择时在现有 systemPrompt filter 隐藏 `tool:goal`，不需要改原生 driver、目标 phase 或 Task。职责仍由 Node 投影目录、集成层过滤可调用工具、客户端编辑名单各自承担；相比 Feature 包装，减少了两个配置真相与额外生命周期层，符合本次范围。

普通工具收缩确实位于 `configuration.apply` 的 `whenIdle` 前，完整配置应用位于其后。新设计要求取消立即收缩、新增等待 idle，方向符合现有机制；实现应从**当前有效选择**计算收缩，尤其当前 allowlist 未配置而下次显式选择单个 Goal 时，不能沿用“undefined 就已允许所有工具”的旧假定使新工具提前可调用。这是该明确契约的实施核对点，不要求新增框架或兼容历史 Goal 数据。

工具选择只决定可调用集合，不等于原生 Goal 操作已经获得真人授权。当前 native source/PA 权限边界不在本轮修改范围，未把 Global Inbox 中的人类文本等同于直接 Goal 授权，也未要求为此扩展授权链。

#### Web/iOS 与独立原型体验

核对真实 Web 创建页的 `defaultNames(default_on)`、详情页 `PillSelector` 的单工具列表及 Feature 联动 handler，以及 iOS `AgentConfigView` 的工具 DisclosureGroup/逐工具 Toggle、`AgentDraft.setFeature`。三工具已经可由普通列表表达，删除 dsh_goal 目录项及专用联动即可，不需新配置页面或新控件。原型的 checkbox 代表工具选择语义；真实 Web 沿用既有 PillSelector，iOS 沿用既有 Toggle 和保存流程。

本轮使用独占 **headless** Playwright 会话和临时 `127.0.0.1:46351` 静态服务，先看 1280×850 默认配置画面，再选中仅 get_goal 并保存，确认另外两项未联动；随后切到原型 iOS 示意并以 390×844 看图，再选 create_goal/update_goal、取消 get_goal 并保存。工具名和各自选中状态、保存按钮及反馈在同一可视区域内，没有总开关，也未因窄屏丢失选择信息。此为局部交互方案验证，不宣称真实 SwiftUI、后端持久化或模型调用已通过。

按用户“图片证据不要上库”要求，截图仅保存在仓外 `/tmp/feat635-goal-design-review/`；未向 unit 添加图片。独占浏览器会话与临时 HTTP 进程均已关闭。报告保留文字结果即可。真实两端失败反馈和持久重开按既有流程验收，不要求原型模拟完整后端。

#### Delta、milestone 与验收前置

两份 Goal delta 的新标题和正文与对应 canonical 预览一致，旧 Feature 总开关断言已经替换；Task delta 未变。作为同一尚未交付 PR 内的纠正，保留原 unit 的 ADDED 归并形式可理解，不需要另造兼容层或新 unit。

但 §7 的运行时生效边界没有同步到 M1-R4，且两份 canonical 的通用配置 Requirement 仍无条件要求整轮不切换。新的 Goal Scenario 只说“沿用普通工具配置”，读者会回到互相矛盾的契约。该处会影响实施/verifier 的判据，见 R3-W1。

本次不新增服务、账号或硬件依赖；Task 的原验收资源不重审。实现后的受影响验证应覆盖默认目录/默认可调用集、单项显式选择和取消、双端保存重开、有效 prompt、根/子继承，以及配置运行中撤销/新增时机；不能把历史 Feature 开关截图或 disarm 测试当作这次通过证据。

### 历史问题闭环

R1-W1–W4 在 Round 2 已关闭，未被本次 Goal 配置局部变化重新打开。Round 2 的 Author Resolution 仍为 accepted；其中 Goal Feature、disarm、整体下一轮生效的正面判断已被用户新澄清取代，本轮不沿用。不存在旧 issue 因本轮被静默改写。

### Issues

#### R3-W1 — 普通工具生效边界尚未同步到 M1 与 canonical 通用契约

- 位置：`design.md:192` 对照同文件 M1 表 `:262` 的 R4；`docs/specs/im/agents-nodes.md:55–57`、`docs/specs/gateway/agent-capabilities.md:135–157`，及本 unit 两份对应 Goal delta。
- 证据：新 §7 明确“工具取消选择沿用普通工具立即收缩、新增在 idle 配置边界生效”；真实 `configuration.apply` 也先 `restrictSelection` 后 `whenIdle`。但 M1-R4 仍写“两端 Goal 默认关，主动开启/关闭下一轮有效”；IM 通用 Requirement 明列 tools 并说“已在进行的整轮不切换”，Gateway 通用 Requirement 要求 tools 与其它配置“下一轮新回复整体生效”。新的 Goal delta 仅引用“普通工具配置的生效规则”，没有解除这层歧义。
- 未修后果：实施者或 verifier 可以依据 M1/current spec 保留原来的 Goal 撤销延迟，或依据 §7 立即撤销而被通用契约判错；当前待删的 retainedGoals 特例正好影响这一行为，不能仅视为名词清理。
- 要求：保持用户已经选定的普通工具语义，不引入新 Feature 或新生命周期控制；将 M1-R4 改成无 Feature、三个工具逐项选择/取消、默认集与显式名单、取消立即收缩/新增 idle 生效的可观察判据。对 canonical 中与该既有机制冲突的配置描述做最小 delta 消歧（保留模型/prompt/skills 等不受影响场景），区分可调用工具的撤销边界与完整配置生效。同步 design 中仍以“Goal 开关”概括本轮验收的摘要。无需重审未改 Task 体系。

### Recommendations

无额外建议；本轮不要求改造原生 Goal 或扩大普通工具配置机制。


### Author Resolution — Round 3

- R3-W1 accepted：M1-R4 改为无 Feature、工具逐项选择、取消立即收缩/新增 idle 生效；两份 canonical 通用配置 Requirement 及对应 MODIFIED delta 最小消歧，保留其余模型/prompt/skills 场景。design 的界面和归并摘要同步为工具选择。
- 实施将从当前有效工具选择计算收缩，覆盖未配置白名单时新增单个 Goal 工具不可提前生效的场景。


## Round 4

### Metadata

- reviewer_target: `/root/design_review_635`（同一独立 reviewer）
- review_mode: `closure`
- mode_reason: 仅核实 R3-W1 的局部契约消歧及 M1 修订，未新增产品要求、共享接口或生命周期机制。
- retained_from: Round 3 的实际装配、目录/选择/配置链、职责与复杂度、原型体验和前置判断；Task 判断仍按 Round 3 所列范围保留自 Round 2。原型未改，不重复启动浏览器。
- started_at: 2026-10-22T16:43:46.102+08:00
- completed_at: 2026-10-22T16:43:59.496+08:00
- duration: 13 秒
- baseline: `unit/feat-635 @ 89a4beeb80ce102e9a0a39acb162bc0f2a34342f` 的同一 worktree；作者现有文档及两份回归测试修改保留。本轮只追加报告，不改实现/设计/测试、不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R3-W1 已关闭。受影响 Goal 方案可继续实施；设计通过不代表当前仍带 Feature 的实现或新增红测已经通过验收。

### Coverage 与证据

核对 Author Resolution 与实际文档：design §7、M1-R4、前端/归并摘要已统一为无 Goal Feature、三个工具默认不选且逐项选择/取消、显式名单有效、取消立即收缩和新增 idle 生效。Task 的其它 M1 退出条件未改。

IM 通用配置 Requirement 现在明确完整配置不在整轮中切换，同时列出工具撤销的有限例外；Gateway 通用 Requirement 明确后续 dispatch 撤销、不打断已开始调用、新增等待 idle，且从当前有效选择计算收缩，避免默认未选工具因候选显式名单提前启用。新的 Goal Scenario 引用“普通规则”已有一致指向，不需再增加 Goal 特例。

两份 delta 均新增完整 MODIFIED Requirement。独立按标题抽取比较：delta 与 canonical 预览正文完全一致；IM 原有 11 个 Scenario、Gateway 原有 5 个 Scenario 全文保留，未改变模型/prompt/skills、配置失败/回执/乐观锁等无关契约。只补通用正文中的生效边界，变更范围适当。

本轮不重跑产品或浏览器。作者报告新增目录/选择回归为预期红测，属于后续实施证据，本轮没有将其视为实现通过。图片外移和 Git 历史清理是作者独立交付事项，本轮未修改或新增图片。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R3-W1 | accepted：M1、通用 canonical 与完整 MODIFIED delta 同步消歧 | design §7/M1-R4 与摘要一致；两端通用配置明确工具撤销/新增边界；两份 delta 与 canonical 匹配，16 个既有 Scenario 全文保留 | closed |

R1-W1–W4 继续保持 Round 2 的关闭状态；本轮无新增问题。

### Issues

无未解决 CRITICAL 或 WARNING。

### Recommendations

无额外建议。
