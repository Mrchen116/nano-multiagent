# feat-645 设计评审

## Round 1

### Metadata

- reviewer target：`/root/design_review_645`，独立于设计作者；未修改受审产物或产品代码。
- review_mode：`full`。
- mode_reason：首次 Gate 2，覆盖需求、当前组装路径、全部设计决定、原型、delta-spec 和唯一 milestone。
- started_at：`2026-10-23T22:58:02+08:00`（精确计时采集点；此前阅读及原型走查已经开始，起始时间未单独采集）。
- completed_at：`2026-10-23T23:02:28+08:00`。
- duration：精确计时段 4 分 26 秒；全轮包含此前未计时的阅读、代码核查和浏览器走查，不将此值冒充全轮耗时。
- 基线：受审设计声明 `1fce5eb1b4692fa2764b9a59acd604241b2edb64`；开始时 main 为 `236a4698c`，收尾时为 `e7f8249d26287dbaccde298365323c70e3cd5fc8`。核对期间 main 新增的差异只有 bugfix-644/646 文档，不改变本轮核实的产品代码。保留其他聊天的工作；本轮仅新增本文件，不建分支、不提交、不操作生产。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

依赖表、默认 Task→Cron、共享依赖保护和配置 operation 复用方向成立。仍有一处实际发布路径没有在设计中完成工具/Feature 分离裁决，以及两条旧生命周期契约没有进入 delta；这会使实施者保留相反行为或在验收时面临双重契约。

### Coverage 与证据

#### 需求与决定

完整读取 `spec.md`、`design.md` D1–D6、`deployment-prompt.md`、四份 delta、原型与 `design-evidence/README.md`，核对用户第 7 项已被第 8 项替代、第 9 项是当前 Task/Cron 原则。设计没有保留自动暂停、自动删除安排或 Task/Goal 双写；部署 prompt 只授权在未来获准部署时做一次性补齐，没有产品启动自动迁移。

六项直接依赖有实际依据：Memory/Skill 工具要求读取当前文件，Skill 管理另用 `skill`；交互指导要求 `nano-interactive-ui`；Heartbeat 读取 HEARTBEAT.md。默认 Task 展开 Cron、关闭 Task 不级联关闭 Cron、最后依赖关闭才取消共享 read/skill，均在设计明确且在原型可走通。Global/Personal 的固定工具与上下文四工具分开，未把全部默认工具变成不可取消项。

#### 实际组装与职责

- `apps/node/src/main.ts:25–43,356–377`：Node 读取真实配置并组装 `ConfigurationOperations`，其 persist/apply 连接 `NodeConfiguration` 和 runtime RPC；不是仅存在于测试的路径。
- `packages/personal-assistant/src/configuration.ts:33–74`：已有 per-Agent chain、write-ahead receipt、fingerprint、恢复；当前 persist 在 apply 前，设计将拒绝条件前移有必要。
- `apps/im-server/src/server.ts:177`、`control.ts:162–460`、`gateway.ts:48`、`task-graphs.ts:552–590`：真实 HTTP 配置和 Task owner 共用 IM SQLite；Task 目前同时按 Feature 与工具做身份门槛。设计区分普通工具操作与自动 execution/scopes，并在真实任务事务处查 pending operation，落点正确。
- `packages/dsh-integration/src/agent-config.ts:89–178`、`capabilities.ts:61`：实际 preset 插件生灭、prompt 过滤及 ToolSelection 存在 Feature 否决；静态工具贡献与 Feature 行为拆分能消除此门槛。
- `packages/dsh-integration/src/index.ts:239–310,503–590`、`cron-owners.ts:47–100`、`features/cron.ts`：确认 initialize、catalog preview、apply、手动 run、wait inspect 和 per-Agent service 的真实门槛。设计列出了 service 由工具/active 安排保留、preview 隔离及恢复次序，不只是改 `/capabilities` 投影。
- `knowledge/runtime.ts:36,183–205,227–297,341–344` 与 PA `heartbeat.ts:14–83`：active work、Feature subscription、pending admission 确实存在。按 Agent/能力保护比“Agent 整轮 running 就禁改”合适；现有取消语义仍需 W2 收口。
- `PersonalAssistant.send` 与 `GlobalAgent.send` 是交互消息真正的发布前入口，现有 Feature 检查未被设计明确覆盖，见 W1。

架构判断：依赖纯数据与集合 reducer 应由 product-contracts 持有，Node 投影真实目录，IM 保有 Task 与配置 operation 权威，runtime 保有 native Schedule/工具执行事实，PA 保有 Heartbeat admission；这些职责符合 `SPEC.md`。复用已有 operation 行作为 Task fence、CronOwners chain 及局部 reservation，较新增锁表、迁移框架或每步规则引擎更合适。新增 prepare/usage 是真实保存竞态需要的有限机制，当前未发现应阻断的额外抽象。已有历史配置由部署操作处理，不能用 validator 顺带自动修复。

#### 原型与体验

reviewer 自己新建后台浏览器标签，访问作者只读静态服务 `http://127.0.0.1:48645/prototype.html`；未控制用户/作者标签，未停止作者服务。独立观察实际渲染后操作：

| 路径 | 独立观察与用户效果 |
|---|---|
| 默认桌面→关 Cron | Task/Cron 均开启；点击 Cron 保持开启，局部 Toast 说明先关任务图，焦点仍在 Cron。原因与操作位置能对应。 |
| 无任务→关 Task→关 Cron→单开 schedule_create | Task 工具取消、Cron 先保留；再关 Cron 后六项取消；单开 create 只亮该工具，未反开 Cron。用户能完成同一草稿中的独立选择。 |
| 关 Memory→关 Skill 创建 | 先保留共享 read；最后依赖关闭后 read 取消；交互式回复仍需要的 skill 保留。 |
| Web 390 画布，有 doing/waiting→关 Task | 两行 Toast 紧跟任务图条目，未盖住开关；Task 保持开，反馈直接给出下一步。 |
| Web 768 画布，有 active 安排→关 Cron | 开关保持开，反馈在对应条目下，不需要回看屏外说明。 |
| iOS 意图模式→关受保护 Task | 原型使用单独 Form 行和 Toggle 外观；反馈在当前行后，未覆盖 Toggle。仅证明 HTML 设计意图，不声称原生焦点/VoiceOver 已通过。 |
| 先关 Task，模拟保存前新增责任→保存 | Task 与工具恢复，保留未保存状态，显示冲突原因；没有伪称保存成功。 |

桌面截图观察时浏览器 viewport 为 1280×720；768/390 使用原型实际 container 宽度，不宣称本轮已独立切换浏览器 viewport。对照作者三宽度证据说明及当前样式的 container-query 后，关键局部关系已有足够设计证据。另只读查看 bugfix-644 的 `baseline-desktop.png` 作为当前白色卡片、顶部身份/保存与配置分区的参考，并核对 Web `features/settings/agents/agent-{create,detail}-page.tsx`、Swift `AgentConfigView.swift` 的真实控件；不把其他 unit 的 E2E 或产品结论据为本轮验收。

原型的 Toast 出现后会消失，源码为 2000ms + 150ms 淡出、重复点击重置同一 timer；本轮未做精密延时测量。没有发现需要阻断的纯视觉问题。原生 iOS 的焦点、VoiceOver、安全区仍按 M1-W3/R2 在实施后验证。

#### Delta、milestone 与前置

四份 delta 均镜像正确 canonical 路径。逐条对比 MODIFIED 标题及 Scenario 集合，没有未知目标或遗漏原 Scenario；旧白名单 Requirement 用 REMOVED+ADDED 替换时保留其原场景。仍缺 W1/W2 指出的相邻契约修改。

唯一 `M1-capability-contract/.gitkeep` 与设计单 milestone 一致，无提前编造 tasks/progress。M1-R1–R5/W1–W5 覆盖静态闭包、真实调用、并发两种次序、跨语言 fixtures、原型对照及部署 prompt 副本验证。Runbook 指定隔离 IM/Node、测试账号、模型来源和 iOS 局部验证，不借生产代验；本轮未启动产品栈、调用模型或运行模拟器，不把未来资源检查写成已完成验收。

### 历史问题闭环

首次评审，无历史 issue 或 Author Resolution 可核实。

### Issues

#### R1-W1 — 交互式回复的实际发布门槛尚未纳入工具/Feature 分离

- 位置：`design.md:76,104–122,260–270`；`specs/gateway/agent-capabilities.md` 的工具独立行为条目。
- 证据：`packages/personal-assistant/src/global-agent.ts:495–502` 的 `send` 先将 Personal Agent 交给 `PersonalAssistant.send`，普通发布随后按 `intelligent_ui === false` 拒绝 interactive 参数；Personal 路径在 `personal-assistant.ts:105–111` 有同样拒绝。两处都位于真实 `send_message` 发布链路，工具已选也不能越过。canonical `docs/specs/gateway/agent-capabilities.md:802–807` 仍明确“取消勾选后发布接口拒绝新卡片”。
- 问题：D3 表述 send_message 各自正常操作、仅不附带交互式回复策略，且工具不能受额外 Feature 门槛；具体落点却只明确 Task/Memory/Skill/Cron，没有裁决 send_message 的 interactive 参数是否完整保留，以及这两个 PA 检查如何改变。delta 也没有修改当前发布拒绝契约。工具列表测试或普通文字发送都不能发现此残留门槛。
- 后果：实施者可能保留现有 PA 检查，导致关闭 Intelligent UI 后即使 send_message 仍为固定/独立启用，工具部分合法参数仍因 Feature 被拒；也可能自行删除检查，却与未修改 canonical 相反。
- 需要：按已确认“工具完整操作、Feature 仅额外行为”的原则明确新卡片发布与主动呈现策略的边界，写出两条 PA 发布路径的改动/保留决定并同步对应 canonical delta。补一个 Feature 关、send_message 开、显式合法 interactive 调用的预期结果与验收点，同时保留原审批、schema 与历史卡片权限。无需重新询问已经确认的一般原则。

#### R1-W2 — 在途维护关闭的新拒绝语义没有替换旧取消契约

- 位置：`design.md:78–81,153–177`；`specs/gateway/agent-capabilities.md` 的 MODIFIED 范围。
- 证据：新设计要求已接受 Memory/Skills/Heartbeat 工作期间拒绝关闭，保持配置与工作不变。canonical `agent-capabilities.md:650–659` 的“Feature可独立启停并撤销其后续影响”仍允许关闭时已有工作被接收，并采用卸载 pending；同文件 `958–974` 的联合复盘 Requirement 明确把“其中一项能力在运行期间关闭”列为取消/部分成功场景。代码 `knowledge/runtime.ts:205,341–344` 在 Feature subscription dispose 时取消对应 active review，说明旧语义有真实实施依据。
- 问题：这两条既有 Requirement 都没有出现在 delta 的 MODIFIED/REMOVED，归并后会同时保留“拒绝关闭、工作不受影响”和“配置关闭导致在途复盘取消”的相反用户预期。design 的“保留联合复盘”不能代替对其关闭场景的调整。
- 后果：按旧 current scenario 实施或验收会继续允许关闭并取消维护；按新 scenario 实施则无法满足未被修改的旧场景。容易将应当区分的正常配置关闭、显式取消和节点退出混在一起。
- 需要：为这两条 Requirement 提供完整 MODIFIED delta，明确普通配置关闭的占用拒绝；保留真实显式取消/失败/进程停止时已有成功事实与计数收口语义，不借本 unit 重做复盘状态机。对应验收明确“关闭尝试不触发 cancel”，与独立取消场景分开。

### Recommendations

- **R1-R1（可选）**：`design.md:175` 写作 `cron.enabled`，实际低层 RPC 名为 `schedule.enabled`（`packages/dsh-integration/src/index.ts:543`）。修订时使用实际名称，方便实施者覆盖该旁路；整体内部入口收口决定已经存在，此处单独不阻断。

### 结论与后续范围

请作者只修订上述设计接线、delta 与对应验收点，末尾追加 Author Resolutions；无需先实施产品来证明这些设计问题。复审可先按 delta 检查 W1/W2 及相关发布/生命周期消费者；若依赖表、关闭机制或 milestone 有实质扩展，再扩大范围。本轮未执行部署 prompt、未修改配置、未提交代码。

### Author Resolutions — Round 1

- **R1-W1 — accepted**。实际核对 PA `PersonalAssistant.send` 与 `GlobalAgent.send` 的 intelligent_ui 判断，确为选中工具的额外发布门槛。design D3 明确两路径移除该判断、保留 schema/审批/权限/receipt/渠道降级，补 M1-R3/W2 的真实 interactive 发布验收；agent-capabilities delta 完整修改 Intelligent UI Requirement 并加入单工具显式 interactive Scenario。没有扩大为自动开启交互指导。
- **R1-W2 — accepted**。核对 KnowledgeRuntime subscription cleanup 调用 cancel 及 current 两条生命周期 Requirement，存在真实冲突。design D5 明确 prepare 拒绝且不得先 dispose/cancel；delta 完整修改 Feature 启停、联合复盘两条 Requirement，保留原 Scenario 并区分普通配置关闭、显式取消、失败和进程停止；M1-W2 增加关闭不触发 cancel 与既有成功事实/计数收口验证。无复盘状态机重做。
- **R1-R1 — accepted**。design D6 低层入口名修正为实际 `schedule.enabled`；收口决定保持不变。

本次未修改首文档、依赖表、UI 原型、部署提示词或 milestone 划分；修改范围为 design D3/D5/D6 与 M1 对应验收文字、gateway agent-capabilities delta 及本 resolution。请求 reviewer 自主判断复审范围。

## Round 2

### Metadata

- reviewer target：`/root/design_review_645`，沿用 R1 独立 reviewer，未参与作者修订。
- review_mode：`delta`。
- mode_reason：两项发现的修订明确了真实 interactive 发布路径及正常配置关闭与显式取消的边界，属于有界设计与契约变化；不能只检查文字是否出现。展开 D3/D5/D6、对应三条 MODIFIED Requirement、M1-R3/W2 及其真实代码消费者；其余范围保留 R1 证据。
- retained_from：Round 1。首文档、六项依赖、默认/共享规则、原型及交互、部署 prompt、milestone 划分未改变；没有需要重复渲染的 UI 变化。
- started_at：`2026-10-23T15:04:46+00:00`。
- completed_at：`2026-10-23T15:06:08+00:00`。
- duration：82 秒。
- checkout：main `e7f8249d26287dbaccde298365323c70e3cd5fc8`；核对 `1fce5eb1b` 至当前 apps/packages/src/IM 无产品代码差异。另聊天 bugfix-644 的 dirty 文件不在本轮修改范围。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

本轮确认设计与契约闭环，未宣称产品功能已经实施或运行验收通过。

### Coverage 与闭环证据

| 历史项 | Author Resolution | 本轮独立核实 | 状态 |
|---|---|---|---|
| R1-W1 | D3 明确移除两条发布路径的 Feature 硬拒，并补契约与验收 | `design.md:118` 明确 `GlobalAgent.send` / `PersonalAssistant.send` 的处置，保留 schema、身份/会话权限、审批、来源、渠道降级和 receipt；delta `agent-capabilities.md:5–16` 完整修改原 Requirement，区分主动指导与显式合法参数，保留历史卡片权限；M1-R3/W2 覆盖真实发布与额外指导不恢复。重新阅读 `global-agent.ts:495–530` 与 `personal-assistant.ts:105–128`，确认所指门槛位于真实路径且周边校验不需移除。 | closed |
| R1-W2 | prepare 拒绝普通关闭，不通过 dispose/cancel 结束已接受工作；完整修改两条旧契约 | `design.md:166–179` 保留原配置/订阅，并与已有 admission reservation 衔接；delta `agent-capabilities.md:18–51` 保留原 Scenario，改正关闭期间在途工作语义，另补联合复盘期间关闭被拒，显式取消/失败/进程停止仍保留成功事实与周期规则。重新核实 `knowledge/runtime.ts:199–205,341–348` 的 dispose/cancel/stop，D5 已明确在 dispose 前拒绝正常配置关闭；M1-W2 明确验证关闭不触发 cancel。 | closed |
| R1-R1 | RPC 名改为 schedule.enabled | `design.md:179` 与 runtime `index.ts:543` 对齐，内部 apply 收口决定未扩大。 | closed |

架构复核：发布参数合法性和权限仍由原 PA 路径承担，仅移除工具可用性的额外 Feature 门槛；未新增第二个发布入口或权限模型。维护关闭保护仍属于既有配置 prepare 与 KnowledgeRuntime 使用状态边界，显式 cancel/stop 继续复用原逻辑；未把配置关闭扩展为取消业务工作的快捷入口。两项修订没有新增通用机制、持久配置真相或产品迁移。

契约复核：重新比较四份 delta 中全部 12 条 MODIFIED Requirement 的 canonical 名称及旧 Scenario 集合，目标均存在且原 Scenario 名称均保留；新增三条完整条目没有残留“发布接口拒绝新卡片”或“其中一项能力在运行期间关闭”旧条件。M1 仅补充同一交付内的验收结果，没有新增 milestone 或改变既有依赖与隔离前置。

R1 原型、当前界面依据和跨端限制仍有效；本轮不重复浏览器操作，不扩张为真实后端/iOS 体验验收。没有执行全仓 docs-check，也不将作者报告的其他 unit 尚未落地链接当成本 unit 的验收结果。

### Issues

无新增问题；R1 两项 Warning 均关闭。

### Recommendations

无新增建议；R1-R1 已处理。

### 结论

当前冻结设计可以交接实施；用户当前仅授权设计，本轮没有执行实施、生产配置或部署 prompt。以后若改变本轮已确认的工具发布边界、关闭保护或依赖集合，应按实际影响复审；纯文字和归档变化可按 workflow 记录 retained。
