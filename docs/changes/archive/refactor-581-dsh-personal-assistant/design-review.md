# refactor-581 Design Review

## Round 1

### Metadata

- reviewer: Codex independent reviewer `/root/design_gate2`
- target: `refactor-581-dsh-personal-assistant`，正式入口 `design.md`
- review_mode: `full`
- mode_reason: 首轮 Gate 2；跨执行运行时、产品节点、IM 后端、历史及扩展资产，需要完整核对需求、组装入口、职责、delta 和阶段退出条件。
- started_at: `2026-10-09T17:08:08+08:00`
- completed_at: `2026-10-09T17:17:41+08:00`
- duration: `PT9M33S`
- Nano source baseline: `4915c44cb7f7b829414a19087877ad9b73d69ea1`（已存在的 `origin/main`）；写作 checkout 为 `main@76fe1d7e7c2a4d07da06453fd2b4658749bb6f87`，保留所有已有 dirty/untracked。
- DSH source baseline: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，本地 HEAD 与 origin/master 一致、工作区干净。
- frozen input: `/tmp/refactor-581-design-r1-sha256.json` 的 13 份文档，写报告前复算均未变化；M1—M5 各仅有 `.gitkeep`。本轮只新增此报告。
- evidence boundary: 文档及固定基线源码审查；未运行接入、模型、平台、真机或生产验收。作者提供的本机资源预查作为验收准备资料使用，不升级为本 reviewer 的运行证据。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

职责与迁移方向可成立，三个未闭合点需要在实施前修订：已有 Cron 的停用门禁、跨模型 fallback 的完整请求重装配路径、Workflow MODIFIED delta 的既有场景保留。修订不要求当前设计阶段实现后端，也不要求重新询问已确认的产品取舍。

### Coverage 与证据

本轮读入 motivation、design、target-architecture、workflow-control-design、migration-plan、capability-plugin-map、pending-decisions、architecture-options、五份 gateway delta 及五阶段目录。Q1—Q21 作为用户决定记录，R1—R12 / S01—S32 作为结果基线；早期 architecture-options 已显式降为比较历史，未用其旧结论覆盖正式设计。

| 覆盖范围 | 独立核对与判断 |
|---|---|
| R1—R2：三客户端、双节点、global/single_thread、Inbox 与群复核 | target §3、6、8 明确产品业务 owner、受信任身份、两种输出去向、摄取回执及 dispatch 前复核。对照 current `global-agent.md`、`routing-delivery.md`、`relay-protocol.md`；最新 Swift `AgentContractsTests.swift` 从 `origin/main` 读取，确有显式空选择和配置协议保护。设计没有因本地旧 checkout 缺 iOS 就删掉原生客户端。 |
| R3：原生工具、两层扩展、真名单、升级 | capability §4.3、7.1—7.2 将包安装与启用分开，workspace 持久声明由可信绑定装配；明确 restrict 不过滤本层注册、需注册过滤和执行 guard。符合原生命名/schema 与无旧 alias 的决定；不是重建旧工具执行器。S05/S06/S07/S32 在 M3 有退出位置。 |
| R4、R11：输入、停止、后台结果与真实交付 | target §7.2—8.4、11 区分产品接受、DSH flush、摄取、执行终态、平台回执。DSH `core/session/src/index.ts:1178` 的 flush 返回真实 listener 参与情况；`core/agent/src/consumed-work.ts` 及持久 inbox splice 支持区分 claim/取消/终态。方案没有把 idle 当完成，也不把普通 jobs 的进程内结果当跨重启持久邮箱。稳定 input ID、结果补读、外发未知与原操作键补查由接入/产品承担，边界合理。 |
| 顶层 SessionController 与原生 schedule 冷恢复 | 独立核对 DSH `api/session-controller/src/index.ts:105` 的服务依赖、`commands.ts:105` 的 create/adopt、`agent.ts:381` 的 composeAgent、`agent.ts:423` 的 persisted preset 恢复。稳定命名 preset 加业务绑定先就绪，再装 Controller/Schedule 的顺序有源码依据；`schedule/src/runtime.ts:101` 直接 resolve 同一会话、followup schedule 来源并检查 flush。未发现需要恢复临时 setup 闭包的错误假设。停用控制另见 R1-W1。 |
| R5：Workflow 完整控制 | workflow-control-design 选择一个自有 provider，logical call/attempt 与真实 child 分离，结果先持久再交给脚本/交付；暂停 gate、旧 attempt 收拢、开始序号/完成序号、连续前缀、嵌套共享限额均有明确规则。DSH `workflow/src/runtime-types.ts`、公开 `WorkflowEngine`、`PtcRuntime`、`SubagentRuntime` 足以作为替换 provider 的执行基础；stock handle 确只有 result/cancel/dispose。token-meter settlement/retry 替换口径与设计相符，未把流样本重复累计。无需另写 Agent loop。 |
| R6：Auto 与子任务审批 | capability §7.4—7.5 明确一个 consumer，默认 Nano、可配置 DSH 规则，共用专用审核模型/可信来源/产品分流。源码 `experimental/auto-review/src/index.ts:178,361,624,678` 的私有来源/快照及固定模型路线支持“需要有界派生，不能纯配置”的判断；`permission-presets/src/index.ts:307` 只有一个 Auto 注册槽。初始化 child policy、delegation 提示、原 launch anchor 路由均列入，未将普通 child 和 Workflow child 的审批能力混为一谈。 |
| R7：知识维护 | capability K01—K10、target §10.4 和 M3 保留记忆受控更新、使用统计、阈值维护、归档/生成启用、后台成功事实及配置调和；DSH 文件/Skill/child/jobs 只作执行基础。未把无原生对应误判为可退役，也未把未完成研究目标当 current。 |
| R8—R9：定时与 Heartbeat | 主会话定时、过期一次性补发是已确认变化；Heartbeat busy-skip/activeHours/HEARTBEAT_OK 保留产品 owner。原生 schedule 是唯一 timer/安排库的选择合理，但 per-agent 停用目前未闭合（R1-W1）。手动运行与产品执行历史明确是补迁，未把原生 delivery history 误称执行成功。 |
| R10：模型、配置、新历史、非聊天资产 | 配置有效 revision、消息点配置、显式空与默认发现、模型上下文窗口、旧聊天排除均有落点。原生 SessionController fork 可复制事件前缀并 mount preset；原生 session query 能观察新历史，故新历史能力有可用基础。完整跨模型重装配尚未选路径（R1-W2）；fork 与蒸馏入口细化列为建议 R1-R2。 |
| R12：终态、运维、数据切换 | migration §4/7/8 保留身份、绑定 created_at、凭据密钥、未消费 Inbox、未知外发与未完成 operation；单消费者切换、新写入后回滚对账清晰。M5 明确独立 TS IM 终态与旧 Kernel/CLI 不可达；保留 PA/IM 运维入口。计划、实现、PR/CI、部署、真机/真实平台证据没有混称。 |
| Delta 与前端 | 五份 delta 指向正确 gateway canonical area；IM/Web/Swift 不另改线协议和布局，原生工具元数据由既有通用界面消费。本轮没有新页面/导航/表单设计，故不要求静态页面原型；实施若新增交互必须补真实增量原型并复审。Workflow MODIFIED 场景有实质收窄（R1-W3），其他已确认语义变化不按“零差异”强行恢复。 |
| Milestones / Runbook | M1 真 DSH 单聊链 → M2 多模式/渠道 → M3 能力/知识/历史 → M4 Workflow → M5 TS IM 与退役，按可运行阶段划分，有依赖/文件范围和双轨退出要求；不是机械横切。最终树必须回验适用 S01—S32，旧 IM 的阶段证据不能代替 M5。pnpm build/test 是待建立入口且已注明，不能误当当前已通过。飞书 scope 与 iPhone tunnel 待恢复属于实施验收前置，有取得路径；设计阶段不据此阻断。 |

**架构判断：** IM 持有中心业务、节点持有接入/Inbox/配置/投递、DSH 持有执行、integration 持有上游接线与明确缺失的政策，这个分工比把整个 Gateway 放进插件更能保持业务可用性。每 owner 节点一个 DSH 子进程的额外 IPC/持久回执成本有实际生命周期收益，且没有虚称 OS 安全隔离。Workflow 自有 host/guest 的维护量由已确认四项控制驱动；知识和 Auto 扩展也有具体缺口依据。保留两套业务 Inbox/执行 inbox 有不同职责，不是重复调度。需要避免的新增维护正是 R1-W1/W2 所要求登记的有限上游扩展，不能留到 worker 在“必须原生”和“必须保留”之间自行猜测。

### 历史问题闭环

无既往 Gate 2 Round。文档中早期独立技术核查不作为本轮 Approved 的替代。审查期间作者补充指出 Workflow delta 和状态措辞残留；本 reviewer 对照 current 独立核实，未修改冻结受审集，也未将作者提出的未来修订视为已关闭。

### Issues

#### R1-W1 — 原生 schedule 的 per-agent 停用/重新启用接线缺失

- 位置：`target-architecture.md:424-432`；`specs/gateway/heartbeat-cron.md:19-26`；`design.md` M2。
- 证据：设计要求关闭对应 Agent 后不创建定时运行、重新启用沿错过时间规则恢复。固定基线 DSH `packages/schedule/schedule/src/runtime.ts:85-157` 的 due/next 只看任务 `status === 'active'`，随后直接 `sessionController.resolveAgent → followup → flush`。`schedule/src/index.ts:213-380` 的公开 create/list/catalog/history/delete/update 没有 per-agent enable gate 或可逆 pause；`stopSessionTasks:430` 是删除 active 任务，不能充当保留安排的停用。隐藏工具或关闭创建能力不会阻止已有任务继续触发。
- 未修后果：M2 可以完成“原生 timer 会运行”却在用户关闭 Cron 后仍执行工作；用删除/重建任务补救又会丢原安排身份与历史，违反 R8/S23。
- 需要修订：选定并写明实际准入边界。可采用同一原生 ScheduleService/runtime 的有限宿主 gate 扩展，按可信 session→productAgent 绑定过滤 disabled 任务的 due/next，配置改变触发重驱动；明确保留任务/到期信息、冷启动先加载开关、停用与入队的先后边界、已持久入队不伪装撤回。登记补丁范围和升级验证，仍保留唯一 timer/安排 owner。也可给出有源码依据的等价公开方案；不能只重复“旧开关映射新 owner”。

#### R1-W2 — fallback 已识别公开接口不足，但尚未选定完整重装配方案

- 位置：`target-architecture.md:446`；`capability-plugin-map.md:245-251`；`design.md` M3。
- 证据：目前写的是“完整重组若需上游扩展须明确列出”，并未列出选定的扩展或等价执行路径。DSH `packages/core/agent-loop/src/agent.ts:405-408` 在同 step retry 的 while 之前计算 `renderedPrompt`；`agent.ts:547-585` 的 `agent/request` 改的是 LlmCallConfig，并不重新执行 prompt assembly。正常 error finish 的 `request-error` 分支在 `agent.ts:490-508`，准备阶段及 stream 抛错不都经此分支。`core/agent/src/model-selection.ts:83-111` 还捕获 assembled selection。现有源码因此只能支持“能换请求路由”，不能支持文档承诺的完整 prompt/容量/effort 同步切换。
- 未修后果：worker 容易在失败后的同一次请求只换 model，沿用旧模型 prompt/容量或漏掉一种失败入口；也可能为补齐保证自行改 loop 大片代码。两者都违背 R10/S25 及减少自研内核的目标。
- 需要修订：在设计中选择一个有界机制，给出“可用性失败 → 确认尚无真实公开输出 → 选择备用 → 完整重装配 → 发起备用请求”的执行路径，说明同模型 retry 优先级、准备/stream/finish 三类失败如何汇合、已公开输出后怎样终止、粘性何时提交。若需要上游公开 hook，应明确 hook 的调用边界、输入/结果及 Nano policy 的职责，而不是留条件句；无需本轮实现或运行它。

#### R1-W3 — Workflow MODIFIED delta 丢失未批准改变的命令与回复契约

- 位置：`specs/gateway/workflows.md:5-13`。
- 证据：current `docs/specs/gateway/workflows.md:55-68` 的同名 Requirement 有“显式查询运行状态”“断线后重新查询”“命令控制同一运行”三个 Scenario，明确人工用户执行 `/workflows`，并以原 channel 的普通回复返回结果/稳定错误。delta 将其合成两个泛化场景，删掉了该 Requirement 中的既有入口和呈现保证。用户批准的是执行器/脚本语言变化，正式设计同时声明沿用客户端交互。
- 未修后果：归并 MODIFIED Requirement 时这些细节会消失；worker/reviewer 可按新泛化文本认为只提供新内部查询接口就已满足，而旧 `/workflows` 普通消息旅程失去本条保护。
- 需要修订：保留三个原 Scenario 及未变的命令/普通回复条款，只将 SDK 真源改为新 Workflow owner，并增补 iOS/中断状态等实际变化；不要以摘要重写整个 Requirement 取代保留未改变场景。顺带逐项对照其他 MODIFIED Requirement 的旧场景，区分明确批准改变与应保留部分。

### Recommendations（不阻断）

- **R1-R1**：清理 capability-plugin-map 开头“仍待决”、pending-decisions 末尾“仍需落入正式需求/设计”、workflow-control-design §8 的剩余分支状态。正式入口已足以确定优先级，本轮不把这些历史措辞升级为未决产品问题。
- **R1-R2**：新历史接入落笔时，明确优先采用公开 `sessionController.fork({sessionId, atSeq})`（`api/session-controller/src/commands.ts:221-285` 已保留 preset 并执行 compose），不要把底层 `sessions.fork` 当成完整产品创建路径；继续补消息锚点/配置快照和失败绑定清理。蒸馏可读导出建议标明生产者及更新时机：DSH JSONL persistence 默认 Zstandard 编码，而现有 distiller 要可读 `source_jsonl_paths`；可用公开 session query 生成受控导出或明确选择可读存储配置。它们已有可用公开基础，不要求为此改造历史引擎或兼容旧聊天。
- **R1-R3**：实施时对原生 schedule 的入队 flush 与安排 receipt 提交之间故障做定向验证，并明确产品 trigger identity 与原生 message ID 的对应；保留设计已经区分的入队、执行、交付事实，不把原生 delivery history 升格为普遍 exactly-once 保证。

### Author Resolutions

- **R1-W1 — accepted.** 终态架构§10.1明确采用同一ScheduleService/runtime的有限宿主enabled门禁与配置重驱动：可信绑定、启动顺序、due/next过滤、串行配置生效、followup前复核、保留任务与原生补发、已入队不撤回均有约定。同步design决策9/M2、能力地图S1和迁移计划C7；不再声称不需要任何schedule扩展。门禁不另建timer/安排库，也不改变Q11b的过期策略。
- **R1-W2 — accepted.** 终态架构§10.2选定原生agent-loop有限请求失败/重装配公开契约，定义prepare/stream/finish汇合、同模型retry优先、可用性和本轮公开输出资格、reassemble输入/结果、完整模型/prompt/容量/effort重装配、输入/工具不重放、成功结算后粘性和补丁退役边界。同步能力地图§7.6/L2、迁移计划C5及design M3。不是当前已有API，也未宣称实现或联调通过。
- **R1-W3 — accepted.** workflows delta恢复canonical三个Scenario及人工`/workflows`入口、原channel普通回复/稳定错误，仅把SDK真源替换为新Workflow owner并补原生iOS/中断事实。其他MODIFIED逐项复核：relay保留原场景与RPC不读transcript边界；heartbeat-cron的会话/过期变化来自Q20，未改Heartbeat任务/节律/静默/无人值守规则。
- **R1-R1 — accepted.** 清理能力地图、决定记录、Workflow§8的已过期问卷状态，并更新文件工具Q21处置。历史architecture-options仍保留比较过程和非权威标识。
- **R1-R2 — accepted.** 终态架构§7.1指定Controller.fork作为新分支主入口，保留消息点配置和失败绑定清理；定义新历史导出器及成功持久化后的原子更新/seq边界，prompt RPC只解析路径，未就绪明确失败，不读取正文。
- **R1-R3 — accepted.** design M2加入原生schedule flush/receipt之间故障及trigger/message对应验收，沿用持久接收/执行/交付分界，不承诺通用exactly-once。

本轮修订只涉及设计文档；未改产品代码或current specs。提交独立复审，范围/模式由reviewer依实际差异决定。

## Round 2

### Metadata

- reviewer: Codex independent reviewer `/root/design_gate2`（与 Round 1 相同）
- target: `refactor-581-dsh-personal-assistant`，正式入口 `design.md`
- review_mode: `delta`
- mode_reason: 修订已选定 schedule 与 fallback 的有限扩展，不能只按文字 closure；本轮展开这些接口及配置、历史、退出条件的波及范围。用户需求、职责/部署、Workflow 控制机制和 M1—M5 拓扑未改变，且 Round 1 源码证据仍可直接复核，无需重开 full。
- started_at: `2026-10-09T17:21:17+08:00`
- completed_at: `2026-10-09T17:23:19+08:00`
- duration: `PT2M2S`
- source baseline: retained_from: Round 1，Nano `4915c44c`、DSH `5badb150`；继续在保留 dirty 的 `main@76fe1d7e` 只写审查报告。
- frozen input: `/tmp/refactor-581-design-r2-sha256.json`，13/13 文件哈希匹配；相较 R1 有 7 份文件变化，其余 6 份未变；五阶段目录仍各仅 `.gitkeep`。
- evidence boundary: 本轮为设计差异及对应源码接线审查；未实现新增 hook/补丁，未运行产品、LLM、飞书、真机或部署测试。作者的链接检查只作为文档自检记录，不替代本轮判断。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

Round 1 三个问题均关闭。新设计为已确认能力选择了可实施的有限扩展边界，尚无会让下游实质走偏的未解决问题。Approved 仅确认设计可进入实施，不表示新增扩展已存在或真实运行验收已通过。

### Coverage 与证据

| 本轮变化及波及范围 | 独立核实 |
|---|---|
| Schedule 停用门禁、配置生效及原生恢复 | target §10.1 已明确由同一 ScheduleService/runtime 引入宿主 enabled 判定与配置重驱动，过滤 due 与 next、保留任务身份/到期/历史。重新核对 `schedule/src/runtime.ts:85-163` 和 `index.ts:462`：原有扫描、resolve/followup 和 serialize 边界可承载该有界扩展。冷启动先绑定/开关、有效 revision 在运行时确认后发布、followup 前复核与已准入输入边界均明确；没有删除/重建任务或第二 timer。design 决策9/M2、capability S1、migration C7 同步，原主会话/过期补发决定未改变。 |
| Fallback 请求失败与重装配 | target §10.2 已将 prepare、stream、finish 汇合限定为模型可用性失败，排除取消、持久化及工具业务错误；同模型 retry 优先，再由 Nano policy 返回 terminate/reassemble。重新核对 DSH `agent-loop/src/agent.ts:268-285,405-408,475-508,547-585`：将失败处理和重装配放在 attempt 边界可避免重新 claim 输入及重做工具，修订没有把原 preStep 整段重跑当方案。完整 selection/assembly/render/容量/effort、同一 turn/step/revision/预算、整轮公开输出资格、成功结算后粘性与失败 usage 均已规定。扩展明确是待实施公开契约，未冒称 stock API；M3 及能力地图/迁移计划同步。 |
| Workflow delta | 对照 current gateway/workflows 的原 Requirement，修订恢复三个 Scenario、人工 `/workflows`、run/Agent 控制及原 channel 普通回复/稳定错误；只替换运行真源并补 iOS/真实中断。Workflow 四项控制、保存嵌套和后台审批机制未变化。 |
| 新历史与导出 | target §7.1 选择 Controller.fork，可信 fork operation 在 preset 装配前提供历史配置，成功后提交业务绑定、失败回滚。对应 `api/session-controller/src/commands.ts:221-285` 的真实 prefix/compose/create 路径已在 R1 核实。导出器与 prompt RPC 分工清楚：持久边界后的受控 JSONL/seq 清单由 integration 生成，RPC 只解析资格/路径，未就绪拒绝部分结果。公开 `session-query/src/index.ts:140` 的 observation 与 session flush 原语存在；导出应按记录的持久边界截取，不能把 live query 的未持久尾部当成功导出，此约束已由文中的边界/清单要求覆盖。 |
| 建议与阶段证据 | 过期问卷表述已清理，M2 新增 schedule flush/receipt 故障及 trigger/message 对应检查。M2/M3 增加的是原需求的实际退出证据，不新增独立平台或用户选择；M5 最终树与真实三端验收要求保持。 |

**retained_from: Round 1。** 需求 Q1—Q21 / R1—R12 / S01—S32、三客户端与双节点、产品/运行时职责、受信任来源、输入持久 ACK、Inbox 摄取、发送与审批、两层工具/Skill 名单、知识维护、Workflow 控制/预算、非聊天资产、切换回滚及前端无新页面判断沿用 R1 证据。理由是本轮 hash 与正文核对未发现这些边界改变；变化部分及受影响的配置/新历史/M2/M3 已在本表重新审查。未修改的四份 gateway delta 和 motivation 保持 R1 冻结内容。

**架构判断：** 两处上游补丁分别补入“宿主能否准入”和“失败后重新装配一次请求”，Nano policy 仍决定业务开关及模型选择，DSH 仍拥有唯一 timer、loop、stream、工具和结算。维护成本现在有明确边界与上游等价接口出现后的退役条件；为已确认的现有行为承担这项成本合理，不要求再造兼容工具全集或第二套执行器。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据与状态 |
|---|---|---|
| R1-W1 | accepted：原生 schedule 内有限 enabled gate/重驱动 | target §10.1 的准入、due/next、持久安排与配置生效边界，以及 M2 实际停用/冷恢复/启用验收，完整覆盖原问题。**closed**。 |
| R1-W2 | accepted：选定原生 loop 失败汇合/重装配契约 | target §10.2 五步契约与补丁范围，design M3、capability §7.6/L2、migration C5 一致，不再让 worker 自行选择核心路径。**closed**。 |
| R1-W3 | accepted：恢复原三个 Workflow Scenario | delta 保留命令和普通回复，运行真源变更与正式设计相符。**closed**。 |

R1-R1/R2/R3 均已采纳并核对；它们在 R1 不是阻断项，本轮也未派生出新的阻断问题。

### Issues

无。

### Recommendations（不阻断）

无新增建议。按已写入 M2/M3 的接入和故障边界实施、验证即可；不为假想边界继续扩展设计。

### Author Resolutions / retained

- 本轮无Issues及新增Recommendations，author无实质异议。
- R2后仅在design、motivation、target-architecture、workflow-control-design、capability-plugin-map、migration-plan同步Approved状态、阅读入口及Changelog，删除“未定稿/待审”的过期叙述；不改变需求、架构、接口、delta或里程碑。保留Round 2结论与全部证据，不开启新Round。
- 文档完成只代表完整迁移重构计划通过设计审查；实施、PR/CI、真实平台/设备验收与生产部署尚未执行。


## Round 3

### Metadata

- reviewer: Codex independent reviewer `/root/design_gate2`（与 Round 1/2 相同）
- target: `refactor-581-dsh-personal-assistant`，正式入口 `design.md` 及其配套设计、五份 delta。
- review_mode: `full`
- mode_reason: Q22 撤回两处上游补丁，Q23 新增独立 Feature 生命周期，影响运行组装、存储、配置和 fallback 核心边界；不能沿用 R2 的补丁路线放行。本轮同时纳入 Q24 对 Workflow 的纠正和 §5.5 对原 S07 工具/Skill 选择的细化。
- started_at: `2026-10-09T17:55:39+08:00`
- completed_at: `2026-10-09T18:03:46+08:00`
- duration: `PT8M7S`
- source baseline: Nano `4915c44cb7f7b829414a19087877ad9b73d69ea1`；DSH `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。写作 checkout 仍为保留 dirty/untracked 的 `main@76fe1d7e`。
- frozen input: 更新后的 `/tmp/refactor-581-design-r3-sha256.json`，写报告前独立复算 13/13 匹配；包括 Q24、五项 Feature、Workflow 常规工具和工具/Skill 选择补充，以及仅对真实缺口补 guard 的最简机制修订。早先六项 Feature 草稿不作为批准版本。
- evidence boundary: 文档与固定基线源码审查；未实现或运行 Nano↔DSH 接入、LLM、客户端、平台、真机及生产验收。本轮只追加本报告，不修改设计或产品代码。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

当前版本通过 Gate 2。它以公开服务隔离/插件生命周期解决 Cron 停用，以多个原生 turn 的产品归属和公开装配事件解决 fallback，已经撤回 R2 的源码补丁前提。五项 Feature 与常规 Workflow 工具分开，工具/Skill 选择保留真实可用性约束。结论仅为设计可进入实施，不表示这些集成链已验证运行成功。

### Coverage 与证据

本轮覆盖 motivation 的 Q1—Q24、R1—R12 / S01—S33，design、target-architecture、workflow-control-design、migration-plan、capability-plugin-map、pending-decisions、architecture-options 和五份 delta。未变化的 current 行为与 Nano 装配入口继续以 R1 已记录的固定基线源码为证据；本轮重新检查其与新生命周期/模型机制的交叉边界，不因历史 Approved 跳过新增约束。

| 覆盖范围 | 独立核对与判断 |
|---|---|
| R1—R2、R4、R11：产品骨架、消息与真实交付 | 三客户端、双节点、global/single_thread、可信来源、群发言复核、Inbox 摄取与外发事实仍由产品持有；§5.4 将已接收工作和持久交付留在独立 run/shared owner，Feature 卸载不销毁结果或审批。DSH sessions/consumed-work/flush 接线与 R1 固定源码相符，logicalRun→nativeTurn 只是运行归属，不另建执行 loop。 |
| R3 / S33：五项 Feature | target §5.4、motivation Q23/Q24、能力 delta 及 M2/M3/M5 一致。五项仅为 Task Graphs、Memory Curation、Skill Creation、Cron、Heartbeat；Workflow 未新增 Feature 开关，M4 已移除 S33。数字人 owner、会话可用性 scope、已接收 run scope 分离，pending/effective、on→off→on、重启和 A/B 隔离有退出标准。Cordis `context.ts:110` 的公开 isolate、`fiber.ts:260` 的异步 dispose、effect/on/注册 disposer 支持所选生命周期。 |
| R3 / S05—S07、S32：工具/Skill 选择与扩展 | target §5.5 区分候选目录、持久名单和实际 DSH scope，default 与显式空不混同，Feature 联动和 child 交集保留。独立重读 DSH `core/tools/src/index.ts:696,1097,1231,1356,1407`：restrict 不代替本层注册过滤，但 get/schema/execute 使用同一有效视图，不可见工具返回 UNKNOWN_TOOL。因此优先原生注册/卸载/查找约束，已覆盖入口不叠加 guard；仅实际缺口才使用 `1136,1519` 的公开 guard（在 pre-execute/审批之后、工具 body 之前单调拒绝）；`core/tools/src/ptc.ts` 的子派发经过同一 prepare/guard 链。`skill/skill/src/index.ts:390,551` 提供 provider disposer 并合并 global/scope；`tool-skill/src/index.ts:134,141,173` 的加载/命令使用同一 list/get。受控 profile 只装筛选 provider 才能成立；文档明确拒绝任意第三方绕过注册，采用公开适配，不再提修改 registry。文件读取和已有上下文边界已如实说明。 |
| R5：Workflow 四项控制 | 自有 provider 仍按公开 WorkflowEngine/PTC/subagents 组合，实现 logical call/attempt、派发 gate、持久前缀及共享预算，真实 child 由 DSH 拥有。§1 已去除复制派生上游实现的路线，stock 仅作行为参考。常规工具选择只阻止后续启动，既有 run 查询/停止、审批和终态交付保留；无新增产品开关。fallback 多 native turn 共用产品预算，不清零父子用量。此前控制/身份/持久结果源码判断仍适用。 |
| R6：Auto 与审批 | Nano 单 consumer 复用公开 gate/approval/LLM，规则可选、专用模型、可信来源和无人值守分流不变；stock 私有快照不被导入或替换。Workflow child 通过 awaited agent/created 设置初始 policy，并同步 delegation 提示和原启动消息路由。独立核对 `core/agent/src/index.ts:550` 的串行 created 生命周期，新的 Feature/模型插件不会要求复制 child provider。 |
| R7：记忆与 Skill 自动维护 | 原 K01—K10 的受控写入、统计、归档、阈值触发与配置调和保留。Memory Curation/Skill Creation 各自拥有工具、提示和触发 disposer，共享算法/记录不擅自触发已关闭能力；Skill Creation 关闭不关闭已有 Skill 选择/加载。文件与写入事实保留，在途维护按取消/原子写边界收口，M3 覆盖。 |
| R8—R9：零补丁 Cron 与 Heartbeat | target §10.1 选择每 productAgentId 唯一长期 Schedule owner，共享 agents/sessions/controller/persistence，隔离 schedule/storage/storageDomain/storage.backend.json 与稳定 root。独立核对 Cordis isolate/service 匹配、registry 的插件实例、Schedule 构造驱动及 effect 清理、storage-domain 的独占 open/close 和 storage-json 的 root/backend：只隔离 schedule 确实不足，完整 realm 有实际依据。`await fiber.dispose()`停止 timer、排空已接受工作及管理链、关闭 domain 后才 effective；重挂保留安排并沿原生补发。`tool-schedule/src/index.ts:435` 的 inject 会随服务撤回/恢复注册。关闭期间只通过公开 scheduleDomain 只读且与启用串行，不能临时挂 scheduler。Heartbeat 保留产品忙时/时段/静默策略和可撤销订阅。 |
| R10 / S25：零补丁 fallback 与模型装配 | target §10.2 不再承诺同 step 重装配。独立核对 `agent-loop/src/agent.ts:183` 的 idle maintenance、followup wake latch、错误 turn 结束及 pending 路径：observer 不能 await whenIdle，受管异步任务再进入 maintenance 的顺序正确。inbox.remove 是公开接口，原输入已入账与 claim 后 prepare 失败分别处理，取消/新输入/flush 与最后 pre-step guard 约束明确。`model-selection.ts:83`、`system-prompt/src/index.ts:589`、Cordis `events.ts:234` 证明后装 prepend 外层 waterfall 在 await next 后覆盖最终变量/请求的顺序；函数 section 先求值的限制也写明。只替换模型通知，不删人工/工具上下文。旧 header 可能影响首次 pre-step 已明确接受，以新请求 header 后原生 overflow 恢复，不冒称切换前必已预压缩。原生 retry 优先、可用性资格、真实发布边界、持久映射、成功粘性和逻辑预算均有 M3 验证。 |
| R10、R12：新历史、数据与退役 | Controller.fork、历史配置/锚点、持久边界受控导出仍保留 R2 明确路线。旧聊天不转换；账号/密钥、workspace、配置/未完成 operation、Inbox 和未知外发仍按迁移表逐类保存/对账。单消费者切换、写入后回滚、独立 TS IM 终态及旧 Kernel/CLI 不可达未被插件约束削弱。 |
| Delta、前端与里程碑 | 五份 delta 仍锚定正确 gateway canonical area；Workflow MODIFIED 的三个旧 Scenario、人工 /workflows 与原 channel 回复保持。新增 Feature Requirement 与 S33 对齐，不把 Workflow 当 Feature。工具/Skill 保留既有分组/Allowlist 交互，本轮无新页面或布局变更，故无需新视觉原型；本结论不替代实施时三端实际界面验收。M1—M5 仍按可运行纵向阶段，M2/M3 分担五项启停，M4 验 Workflow，M5 验最终树/零补丁依赖和全部适用旅程；飞书/真机/生产前置及证据等级保持。 |

**架构判断：** IM/节点持有业务身份和资产，DSH 持有执行与原生服务，Nano 插件负责产品政策和公开接线，依赖方向未变。按数字人隔离 schedule 存储是原生固定 domain 与独立卸载所需的具体成本，不是增建每会话进程池；没有复制 timer/安排引擎。fallback 增加的是有限候选、持久归属和准入控制，原生 loop 仍完成每次请求/工具/结算。五项 Feature 复用稳定底座而分别撤销贡献，工具/Skill 选择集中在同一装配 owner，避免每插件自建配置来源。自有 Workflow 控制代码由已确认功能缺口驱动，不能由“插件友好”推断成无需维护，但也不需要修改或复制上游执行内核。

### 历史问题闭环

| Issue | Author Resolution / 本轮变化 | 本轮证据与状态 |
|---|---|---|
| R1-W1 | R2 的上游 enabled gate 被 Q22 撤回；改为原生服务公开卸载/重挂。 | 服务 realm、独立 root、异步 disposal、重启开关及 tool inject 的源码链闭合；原安排保持和补发规则明确。**closed（以本轮路线替代 R2 依据）**。 |
| R1-W2 | R2 的 loop reassemble 扩展被 Q22 撤回；改为同 logicalRun 的多个原生 turn。 | idle/maintenance、wake latch、持久消息分流、外层 waterfall、公开输入移除及原生 overflow 路线可由公开接口组成。**closed（以本轮路线替代 R2 依据）**。 |
| R1-W3 | 恢复原三个 Workflow Scenario。 | 当前 delta 仍保留命令/回复，Q24 仅纠正 Feature 分类，不削弱原控制路径。**closed**。 |

R2 的 Approved 是历史补丁方案结论，不用于证明 Q22 合规；本轮结论独立覆盖替代路线。审查过程中 Workflow 六项 Feature 误读和复制派生残留均已在最终冻结输入中纠正，不留作实施时临时裁决。

### Issues

无。

### Recommendations（不阻断）

无新增建议。按 M2/M3 已明确的原生生命周期、名单和 fallback 故障边界完成实施验证，不将设计源码证据升级为运行或真机验收。


### Author Clarification after Round 3 — retained

用户指出：“没必要吧，上下文里有，但是实际没有，自然会有报错给agent反馈吧”。作者接受，删除能力地图T06/§7.1等残留的额外名单guard设计。名单通过装配和继承过滤落实到原生有效工具集合，调用交给DSH的UNKNOWN_TOOL反馈。依据本轮已独立核查的core/tools/src/index.ts:1231,1356：get/schema/execute共享有效视图。本次仅落实R3“原生已覆盖不叠加guard”的结论，选择保证不变，状态同步为R3 Approved；retained本轮证据，不新增Round。产品身份、审批及其他业务约束不属于该名单去重调整。未实施或运行验收。
