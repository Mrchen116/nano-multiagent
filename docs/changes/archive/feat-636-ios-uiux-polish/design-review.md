# Design Review

## Round 1

- reviewer_target: `/root/uiux_design_gate`（独立 reviewer）
- review_mode: `full`
- mode_reason: 首次 Gate 2；覆盖全部需求、设计决定、接口接线、delta、milestone 与受影响前端流程。
- started_at: `2026-10-22T10:13:50+08:00`（首次独立原型渲染；此前已完成文档准备读取）
- completed_at: `2026-10-22T10:22:00+08:00`
- duration: 约 8 分钟（渲染与审查阶段）
- baseline: `d846b015b8774461bb26b172e458443ce1eb071d`；detached HEAD；开始时仅本 unit untracked，无产品 diff。
- Verdict: **Issues Found — 0 CRITICAL / 4 WARNING**

### Coverage 与证据

已读 `spec.md`、`design.md`、`delta-spec.md`、`prototype.html`、`prototype-review.md`，以及 current 的 `ios-client.md`、`personal-agent.md`、`agents-nodes.md`、`task-graphs.md` 相关契约。核查真实组装入口，并亲自用独立 Playwright CLI session `feat636gate` 在 HTTP 原型上操作；未复用作者浏览器会话。先观察画面及操作，再核对作者结论。

独立对照了基线报告 `/Users/czj/.codex/artifacts/ios-uiux-20261022/review.md` 及真实截图 `37-default-tasks-restored.jpg`、`29-real-agent-create.jpg`、`26-work-tool-expanded.jpg`、`20-task-structure.jpg`。这些支持默认字号任务密度、创建先呈现技术字段、Work 标题副作用和结构缺少总览的现状；基线没有双端 PA 列表复现画面，U6 目前仍是用户反馈加源码证据。

本轮独立截图在 [design-gate-r1](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r1/)；它们是设计原型证据，不是 SwiftUI 产品通过证据：

| 需求/决定 | 独立观察与真实接线判断 |
|---|---|
| U1 创建 | 1440×1080 浏览器内的 390px 原型先显示名称、用途、说明，模型紧随其后；高级设置可展开，信息优先级比基线明确。实际入口为 `AgentsView → AgentCreateView`，仍可复用 `AgentDraft.payload`、capabilities 和现有 pending/reconcile。新用途只预填说明、不触发任务的边界清楚。截图：`feat636-gate-create.png`。模型连续流程缺口见 W2。 |
| U2 普通 Markdown | 实际消息使用 `MarkdownView → MarkdownBlockView`；列表的 `HStack/children` 与普通 text 分支是本轮正确落点，保留 AST、复制与表格横向滚动合理。大字号具体画面尚无原型样本，见 W4；不能把之前交互卡片证据用于此项。 |
| U3 Work | 原型在线/主执行状态紧凑，轮次与可换行结果优先，技术详情折叠，减少了首屏诊断负担。真实 `AgentWorkView → AgentWorkTurnView/AgentWorkItemView → JSONDetailView` 确实内嵌；`CommonViews.swift:16–22` 的 title 是已定位副作用。移除通用内容组件的导航职责、由调用页面声明标题是正确职责划分。仅使用已有 title/output/summary，不新增摘要服务。截图：`feat636-gate-work.png`。 |
| U4 群策略 | `AgentConfigView.swift:141–144` 只有大写三种 tag，而 `apps/node/src/configuration.ts:55,80` 将 lowercased always 映射 always，其余 mention_only，证实 manual 当前空白与设计映射依据。保留原始值直到主动选择、不新增运行时不支持选项的决定合理。真实语义不应因 UI 修复改变。边界画面见 W4。 |
| U5 任务 | 取消卡内大分隔、合并负责人/来源，使同宽原型能比较更多标题；计数保留已加载范围，不改后端分页正确。真实入口 `TasksView/TaskGraphView` 已持有分组、数据、selected sheet 与 `NativeTaskLayout`，可复用布局和权限。状态定位、总览到详情的交互未完成设计展示，见 W3。截图：`feat636-gate-tasks.png`、`feat636-gate-status-locate.png`、`feat636-gate-structure.png`。 |
| U6 双端 PA | 原生原型“我的个人助手”分区容易辨认，实际点击直接进入配置；桌面 Web 示意在搜索下和普通列表上方显示明确入口，符合查找目标。实际 Web `AgentsListPage → listPublicAgents → contacts` 和原生 `AgentsView` 当前都没有本人 PA binding 读取；`personal-agent-api.ts` 的 GET 返回 binding.agent_id，可在列表层读取并去重，复用现有配置路由/AgentConfigView，职责无需下沉到联系人或排序服务。失败不能阻塞普通列表的决定清楚。截图：`feat636-gate-pa-config.png`。Web 窄屏及异常状态缺口见 W4。 |
| 五项细节 | design 决定 7 覆盖中文术语、单主保存/dirty 放弃、持久标签、Agent 长名称换行、任务“关闭”。可复用现有 SettingsFeedback/nanoUnsavedChanges，无需通用新表单框架；部分必须对照的画面缺口见 W4。 |

**架构判断：** IMClient 继续负责认证与请求；专用 wire types 承接非秘密 setup 快照和草稿；页面负责呈现与操作跟踪；模型验证、revision 与依赖裁决保留 Node 权威。沿用现有 IM → gateway request → Node ModelSetup 路径，不引入网络栈、DSH import 或第二套运行循环。模型元数据应沿用现有 Web `serviceDraft/newServiceDraft` 的字段含义；复用语义比抽取跨语言新机制更合适。设计唯一未闭合的接口承诺是 W1。

**delta：** 两个 ADDED requirement 分别锚定 `docs/specs/im/ios-client.md` 的原生呈现，以及 `docs/specs/im/personal-agent.md` 的双端本人入口；没有 MODIFIED 删减既有 Scenario。模型权限、保存与失败语义引用现有 agents-nodes，任务权限与分页不变，canonical target 选择可接受。

**milestone 与用户约束：** 单阶段 M1-experience 对应 A–F，覆盖 U1–U6 与五项细节，无并行共享文件冲突。交付要求同条件真实截图、默认 large 与 accessibility-medium 分开、用户确认后才提 PR；不部署生产、不装用户手机、无真实付费模型要求，都已进入设计。原生 API 管理是本轮范围，既有 Web 订阅授权不要求扩展到原生。

**验收前置：** worktree、Xcode 构建脚本、隔离 e2e-up/down 与公开 fixture 路径存在；本轮只读确认 Xcode 下 iOS 26.4 与 `Nano UIUX 636` 专用模拟器可用。无生产账户或外部凭据依赖；本地协议端点可以验证 API 保存/失败流程。本轮未启动真实服务、未构建/安装 App，不把这些资源检查写成实施验收。运行时需按 runbook 实际隔离、清理。

### 历史问题闭环

R1 首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — “只取消本页 operation”的承诺无法由现有接口兑现

- 位置：`design.md:17,27,36`；`apps/im-server/src/onboarding.ts:38–51`；`apps/node/src/model-setup.ts:15–18,53–55`。
- 证据：设计约定“页面取消请求只取消当前跟踪操作，不取消他人操作”，且全是客户端、不新增后端机制。实际 setup 请求白名单没有 operation ID；Node 的 cancel 直接 abort 当前共享的 `this.abort`。客户端跟踪返回 operation.id 只足以避免误显示成功，不能把 cancel 绑定该 ID。现有 Web 也发送裸 `{action:'cancel'}`，不能把复用它当作更强保证。
- 后果：worker 按文档可写出一个看似满足“本次操作”的按钮，但实际取消的是节点当时的当前操作；这与明确写下的边界不同。
- 有界修订：在客户端范围内明确取消的含义与离开页面规则，例如只停止本页等待/保留草稿，说明节点操作仍需重读确认；若必须中断远端且只限特定操作，则需要先把 operation fence 纳入实际接口与范围。不能只用“发送前重读状态”声称具有接口没有的绑定保证。

#### R1-W2 — 模型服务主流程尚不能按产品路径评审，且添加模型实际损坏

- 位置：`prototype.html:3,5–6,13`；`design.md:27,45`；`prototype-review.md:5`。
- 独立操作：创建页 → 管理这台电脑模型服务 → 编辑 → 添加模型 → 测试并保存。添加模型按钮直接显示 `')\">＋ 添加模型`，点击产生 `Invalid or unexpected token`，没有新增字段；测试失败提示出现且原输入保留。证据：[模型失败画面](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r1/feat636-gate-model-failed.png)，CLI console `.playwright-cli/console-2026-10-22T02-13-50-360Z.log`。
- 其余关键缺口：没有“我的 → 本人设备”常驻入口画面；返回按钮总是去 Agent 列表，无法评审编辑回列表及返回创建后的连续操作；添加和编辑落到同一个预填编辑页。冲突时如何核对最新配置与草稿、操作处理中/取消、移除依赖/离线恢复目前只有原型外侧一句规则，无承担判断与恢复的实际区域。
- 后果：本轮新增原生核心能力在提交、比较与返回处仍需 worker 自行设计，must-match“连续路径及真实反馈清楚”缺少可对照依据。测试失败一个状态不足以证明主要流程设计已收口。
- 有界修订：修好添加模型；补最小连续入口/返回与明确的添加状态，以及代表性的处理中、冲突比较选择、在用依赖和离线保留画面。可以用原型外模拟控制触发、不接后台，不要求提前实现 Node 或调用真实模型；无需重建无关“我的”功能。

#### R1-W3 — 任务“定位/结构总览到详情”显示与动作不符，不能作为 M1-D 对照

- 位置：`prototype.html:7–8,13`；`design.md:30,47`。
- 独立操作与画面：点击“待确认 1”后第一个标题变为“待确认 1”，下面仍是原来的三条待办/暂缓任务，没有定位到相应组。点击第三卡“查看”可进入结构页；点击“详细视图”与“完成情况”后仍是相同三张总览小节点，节点本身为不可操作 div，无法按画面提示打开详情。证据：[状态选择后](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r1/feat636-gate-status-locate.png)、[详细视图/完成情况点击后](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r1/feat636-gate-structure.png)。
- 后果：目前不只是按钮未连后台，而是不能判断到底在看哪个状态，亦看不到总览与可读详情之间的层级关系；实施者可能把示意小卡当作完成方案，未解决基线的一屏看不清结构与进入内容的问题。
- 有界修订：状态按钮实际滚到对应组或使用确定且标明的定位结果；用现有样例展示完成情况紧凑行、可辨认的结构总览、一个节点进入真实样式详情/返回，以及详细视图的可读状态。保持原分组/依赖图含义，不要求扩展任务功能。

#### R1-W4 — 原型契约要求的窄屏与局部关键状态尚未呈现/验证

- 位置：`design.md:48–50`；`prototype-review.md:3–5`；`prototype.html:2,10–12`。
- 证据：作者只记录 1440×1080 创建/任务画面。独立在 390×844 渲染后，看到缩窄的原生示意和原型外壳，Web 区仍明确标为“桌面布局”；没有 Web 窄屏自身的列表→配置呈现。原型也没有 PA 读取失败/无 PA 的可见区分；未展示普通 Markdown 长列表在默认/大字号下的容器、已填系统策略字段与单主保存/dirty 放弃，以及长 Agent 名称/元信息的大字号样本。配置示意只呈现正常策略，不能核对 manual 与未知原值的呈现。证据：[390 渲染](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r1/feat636-gate-390.png)。
- 后果：这些已声明为 must-match 的项没有足够前端对照，worker 对错误与空态的布局、窄屏内容关系、局部标签及换行仍可能走偏；“原生控件可适配”不能替代这些尚未画出的状态。
- 有界修订：Web 390 用自己的布局展示一次 PA 列表到配置/返回；PA 失败与空态可以共用局部状态样本。其余局部修复只需在实际宽度和相邻控件内补充代表性前后/多状态样本，默认与大字号分别实际渲染并记录。无需完整复制 App，也不要求此阶段生成每项真实产品 before/after。

### Recommendations（不阻断）

- R1-R1：runbook 中 Web `npm ci && npm run build` 明确工作目录为 `src/IM/frontend`，并给 `simctl` 命令使用与 build.sh 相同的 `DEVELOPER_DIR`。本机裸 xcrun 当前会找不到 simctl；指定 Xcode 后已确认可用。它不构成硬件/资源缺失。
- R1-R2：前后密度比较保留真实 SwiftUI 默认 `.body` 字体与相同内容；当前 HTML 15px 小字只说明内容关系，不能沿用“约四卡”直接声称真实 iOS 密度结果。

### 本轮边界与后续

只新增本报告，未改产品、设计或其他 unit 文档，未建分支/提交/PR。独立截图移动到仓外 artifacts；已关闭自己的 `feat636gate` 浏览器。未操作作者 `feat636` 会话及其 HTTP 服务、模拟器或其他进程。

四项 WARNING 收口后可按真实修改范围做一次 delta/closure 复审；没有因颜色、圆角或个人风格偏好提出阻断。实施与真实模拟器/浏览器验收仍须在 Gate 2 完成后独立进行。

### Author Resolutions — R1

- R1-W1 accepted：现接口无 operation fence，不增加后端机制。design 决定2改为“停止等待”只停止本页轮询、保留草稿，明确远端验证可能继续，重读终态前禁再次保存；不调用裸远端 cancel。
- R1-W2 accepted：原型重建可操作最小连续路径（我的→模型服务→本人设备→列表→新增/编辑→返回）。添加模型使用状态化字段，新增从空草稿开始；补处理中/停止等待/失败/冲突比较/依赖与离线的可见反馈区；异常状态控制在原型外。
- R1-W3 accepted：状态按钮定位实际分组，结构总览/可读详细/完成情况切换真实改变内容，节点可进入完整任务详情并返回。
- R1-W4 accepted：增加 Web390 自身 PA 列表→配置→返回；原型外可切无PA/读取失败、默认/大字号、未知策略、已填策略表单和 dirty 放弃/保存反馈；长Agent名称允许自然增高。
- R1-R1 accepted：runbook 明确 frontend cwd 与 DEVELOPER_DIR。
- R1-R2 accepted：HTML 卡片数量只说明信息关系，真实密度由相同 fixture 的 SwiftUI 默认 large 前后图判断，不能将 HTML 数量作为产品结果。

本轮 design/spec/delta 范围未扩大。spec与delta不变；prototype交互和design取消含义修订，交回独立 reviewer 根据真实影响选择复审范围。

## Round 2

- reviewer_target: `/root/uiux_design_gate`（与 R1 同一独立 reviewer）
- review_mode: `delta`
- mode_reason: 原型重建了多个有界流程，超出只核文字 resolution 的 closure；需求、canonical delta、核心接口和 milestone 未改变。复查取消决定及全部变更前端路径；架构/current 代码事实按下述 retained 继承。
- retained_from: `Round 1`；未变的 current 契约、IM→Node setup 数据链、Markdown/Work/任务真实入口、PA binding 权威、权限及验收资源已具证据，无产品 diff，继续有效。
- started_at: `2026-10-22T10:26:14+08:00`
- completed_at: `2026-10-22T10:33:00+08:00`
- duration: 约 7 分钟
- baseline: `d846b015b8774461bb26b172e458443ce1eb071d`；仍仅本 unit untracked。
- Verdict: **Issues Found — 0 CRITICAL / 1 WARNING**

### Coverage 与新增证据

重读修订后的 design、prototype、prototype-review 与 R1 Author Resolutions，确认 spec/delta/milestone 语义未扩大。使用新的独立 Playwright session `feat636gate2`，重新 HTTP 渲染并实际操作，证据保存在 [design-gate-r2](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r2/)。已查看本轮代表性截图，不以 DOM/脚本存在替代画面判断。

- **模型路径（1440×1080 内 390px 原型）：** 从底部“我的”→模型服务→Mac mini→添加服务，空草稿可辨认；输入“旅行模型”、自定义地址、travel-model 后新增第二个 fast-model 成功，无 R1 添加模型语法错误。进入处理中→停止等待，明确说明远端可能仍在进行，输入保留且保存 disabled；失败/离线提示也保留相同草稿，反馈与表单相邻。返回回到服务列表，移除依赖区显示了恢复动作。截图 `model/stopped/failed/offline/dependencies`。旧 W2 的主要入口、状态和返回缺口已补；内容对应尚有一项实质问题，见 R2-W1。
- **任务：** “待确认 1”实际滚动到包含“发布十月产品更新说明”的对应分组，原待办标题未被改写。周末出行的查看入口→结构总览→详细视图，节点变为可横向阅读的大卡；完成情况切换成紧凑三行，状态/负责人/详情动作可比较；从完成情况或结构节点进入同一正确任务标题的完整详情，关闭/返回回到子任务。截图 `task-locate/graph-detail/progress/node`。这足以指导缩略总览、正文阅读与详情的关系；真实 SwiftUI 布局与依赖箭头仍按原设计保留并在实施验收核实。
- **Web 390×844：** 原型已提供手机 Web 自身列表→PA 配置→返回的全宽状态，搜索、本人分区和其他列表的主次可辨认。PA 读取失败显示独立重试区，普通列表继续出现；重试恢复本人区。无 PA 则是不同的说明，普通列表同样可用。截图 `web-list/web-config/pa-error/pa-empty`。它们说明目标关系，不宣称是当前 Web 的实拍或新的导航系统。
- **局部状态：** 同宽默认/大字号普通列表问题均完整显示；大字号 Agent 长名称自然增高而非单行省略；未知策略显示原值及保留含义；已填系统策略仍有持续标签，dirty 才出现放弃，右上唯一保存后有明确反馈。截图 `message-default/message-large/agents-large/policy-unknown/form-dirty/form-saved`。这是设计样本通过，不能替代默认 large/accessibility-medium 的真实模拟器验收。
- **R1 建议：** runbook 已明确 Web cwd 与 Xcode DEVELOPER_DIR；作者 resolution 明确 HTML 卡片数不能充当真实密度结果。

**相邻真实接线补查：** 主代理补充桌面详情/创建/公开资料还组装 `AgentsRailDesktop`。本轮亲自核实 `agents-rail-desktop.tsx` 的独立 public-agents query、search、`selectAgent` 回调，以及 `agent-{detail,create,profile}-page.tsx` 的真实使用位置；创建页 `useBlocker` 负责未保存站内离开拦截。为兑现同一“Web Agent 侧栏”语义，需要 AgentsListPage 与 AgentsRailDesktop 都呈现本人入口并去重。主代理提出复用一个小型入口组件、共享同一 personal-agent query，沿用既有选择回调/Router 的做法与职责相称，无须新增列表服务或路由机制。把这两个组装入口及组件纳入 design 文件范围属于现状/落点补全，不改变本轮体验语义，不另报 blocker；实施前由 author 追加事实，并在真实验收覆盖从详情/创建页切换到 PA 及原离开保护。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-W1 | 不调用远端裸 cancel；停止本页轮询，保留草稿，终态前禁新保存 | design 决定 2 已明确；实际停止等待后提示准确，保存 disabled；不再承诺当前 API 没有的 operation fence | closed |
| R1-W2 | 重建模型连续路径、合法多模型、新增空草稿及主要恢复状态 | 入口/返回/添加/处理中与恢复区域已实际操作成立；比较和目标身份仍有不对应，见 R2-W1 | still-open（范围已缩小） |
| R1-W3 | 实际分组滚动、结构/完成情况/详情切换与节点详情 | 实际操作与内容对应，见本轮任务证据 | closed |
| R1-W4 | Web 窄屏、PA 空/失败、字号及字段/策略局部样本 | 所需代表性样本已渲染走查，内容层级可指导实施 | closed |

### Issues

#### R2-W1 — 模型流程的比较摘要、编辑目标与依赖目标仍不对应（延续 R1-W2）

- 位置：`prototype.html:14,27,33,38–39`。
- 独立操作与画面事实：
  1. 新增草稿已输入 **旅行模型 / https://models.example.com/v1 / travel-model、fast-model**，触发版本冲突后，反馈区却声称“你的草稿：团队模型”；最新配置只显示另一名称和模型数量，没有可用于判断的地址、协议或模型 ID。[冲突画面](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r2/feat636-r2-conflict.png)。
  2. 返回“团队模型”服务列表再点其“编辑”，页面仍装入上一个未保存的**旅行模型**草稿，无法辨认正在编辑哪项已保存服务。[编辑目标](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r2/feat636-r2-edit-target.png)。
  3. 从“研究助手 · 配置”依赖恢复按钮进入后，名称和描述实际是**我的 PA**。[依赖目标](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r2/feat636-r2-dependency-target.png)。
- 用户代价/未修后果：这些动作承担“核对后重试”和“先修改受影响助手”的关键选择。当前内容关系让用户不能判断要覆盖哪套连接、正在编辑哪项服务、是否进入了应修改的助手；不能把这组样本当作已闭合的原生流程对照。问题是实际显示与操作对象不一致，不是要求真实后端或完整数据持久化。
- 最小闭环：给新增/编辑各自明确的快照/草稿，编辑从所选服务加载；冲突区显示当前真实草稿与一套有区别的最新配置（名称、地址/协议、模型 ID，密钥只显示保存状态），两种选择实际保留/替换相应内容；依赖入口携带并展示研究助手的身份。可继续使用确定性演示数据，不增加产品范围或抽象。修正后仅需复查这一段，无须重走已关闭的任务/PA/字号路径。

### Recommendations（不阻断）

- R2-R1：为模型验证补一个明确成功终态样本，沿用 design 中成功才清草稿、显示已保存并回到服务列表的决定；它有助于 worker 对照反馈位置，不要求原型真实验证 API。
- R2-R2：作者按本轮相邻接线补查更新 Web 文件范围即可；无需为两个列表组装点新增一个泛化列表框架。
- R2-R3：主代理随后指出健康探针需从 `/openapi.json` 改为 `/health`。已亲自核实 `apps/im-server/src/server.ts:268–269` 注册 `/health`、`/healthz`，本源码没有 `/openapi.json` 路由。author 应纠正 runbook；这是可明确落实的命令纠错，不是验收资源缺失，也不要求重开设计 Round。

### 本轮边界

只追加本 Round，保留 R1 和 Author Resolutions 原文；未改产品/设计、未提交。截图已移到仓外 artifacts，已关闭 `feat636gate2`；作者会话、HTTP 服务和模拟器未操作。旧问题已有三项关闭；剩余仅模型关键内容对应的一项，后续宜做有界 closure，不扩大为全产品或风格复审。

### Author Resolutions — R2

- R2-W1 accepted：冲突区直接显示当前草稿名称与实际模型ID，并显示最新配置具体名称和模型ID；从服务列表重新编辑重建对应已保存服务草稿；未保存返回先给“继续编辑/放弃并返回”，避免串用草稿。依赖链接传实际助手名称进入对应配置，不进入我的PA。
- 接线事实补充：design 加入 AgentsRailDesktop 与复用本人PA入口，保留 onSelectAgent 离开拦截；健康命令更正为实际 /health。均已被 R2 独立核实，不改变体验/接口范围。

本次只修原型模型内容对应关系及上述事实；spec/delta保持不变。交回 closure 核对。

## Round 3

- reviewer_target: `/root/uiux_design_gate`（同一独立 reviewer）
- review_mode: `closure`
- mode_reason: 仅核对 R2-W1 的模型内容对应与离开恢复；无需求、接口或 milestone 变化，不重跑已关闭的任务、PA、字号等路径。
- retained_from: `Round 1`、`Round 2`；既有架构、契约、真实组装入口及已关闭问题的证据仍适用。
- started_at: `2026-10-22T10:35:15+08:00`
- completed_at: `2026-10-22T10:37:26+08:00`
- duration: 2 分 11 秒
- Verdict: **Approved — 0 CRITICAL / 0 WARNING**

### 历史问题闭环与实际证据

已读 R2 Author Resolutions 及实际变更的 `openModel`、`backPage`、`openConfig`、冲突反馈/选择。用独立 Playwright `feat636gate3` 在 1440×1080 中重新渲染 390px 原型，实际完成以下操作并查看截图；仅测试此段设计，没有真实后台或 App 通过的含义。

| 原 issue | 本轮独立核实 | 状态 |
|---|---|---|
| R2-W1 / R1-W2：冲突内容对应 | 编辑团队模型，输入旅行模型、不同 API 地址、travel-model，触发冲突后摘要实际显示旅行草稿及 travel-model/fast-model；最新配置显示团队共享模型、地址与 research-model/fast-model，差异可辨认。选“保留草稿”后名称、地址、模型仍为旅行草稿；选“用最新配置替换草稿”后变为完整最新名称、地址、两项模型 ID/显示名，密钥输入为空。 | closed |
| R2-W1：重新编辑串用草稿 | 返回先显示继续编辑/放弃并返回；继续编辑保留内容；再次返回并放弃后回到服务列表，重新点编辑恢复团队模型及 research-model/fast-model，不携带旅行草稿。 | closed |
| R2-W1：依赖目标错误 | “研究助手 · 配置”实际进入名称为研究助手的配置，原模型/推理入口可达，不再显示我的 PA 身份。 | closed |

本轮开始时额外实际点击了“用最新配置替换草稿”，发现最初修订只换名称、仍留 travel-model。已当轮向 author 反馈同一旧问题；author 将按钮改为完整 `replaceDraftWithLatest()` 快照后重新冻结。本 reviewer **刷新原型后重新执行两种选择**，最终截图及表单内容证实上述关闭结论。没有将中途失败结果当通过，也未因此扩展审查范围。

最终证据位于 [design-gate-r3](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r3/)：`feat636-r3-retained-final.png`、`feat636-r3-replaced-final.png`、`feat636-r3-leave.png`、`feat636-r3-reedit.png`、`feat636-r3-dependency-target.png`。其中未带 `final` 的最初 replaced 截图保留为当轮修正前证据，不用于最终通过。

design 已补上 R2 核实的 AgentsRailDesktop 真实组装范围与 `/health` 命令；均为事实纠正，语义与接口范围未变。R1-W1/W3/W4 按 R2 closed 继承；所有阻断已关闭。可选建议 R2-R1 不升级为新门禁。

### Issues

无。

### Recommendations

无新增建议；实施继续按既定 M1 与真实客户端 runbook 核验。原型通过仅表示方案已足以指导实施；真实隔离 IM/Node、iOS 模拟器与 Web 的逐项 before/after 及用户确认后才提 PR 的要求保持。

### 本轮边界

仅追加本 Round，未回写历史、未改设计/产品、未提交。截图移到仓外 artifacts，自己的 `feat636gate3` 浏览器已关闭；其他会话、HTTP 服务和模拟器未操作。

## Round 4

- reviewer_target: `/root/uiux_design_gate`（独立 reviewer）
- review_mode: `delta`
- mode_reason: 用户追加原生消息元信息分层需求；仅审单聊/群聊身份、时间分隔与状态呈现及其 M1-G 投影，不重审已通过的 U1–U6。
- retained_from: `Round 1–3`；未受影响需求、模型/PA/任务方案及原型结论保持。当前已有实施提交 `b1d926f279f54dbc1690ef726529255ba9c6f498`，本次消息增量尚未实施。
- started_at: `2026-10-22T12:02:16+08:00`
- completed_at: `2026-10-22T12:04:14+08:00`
- duration: 1 分 58 秒
- Verdict: **Approved — 0 CRITICAL / 0 WARNING**

### 覆盖、真实对照与独立渲染

已读本次 spec 的用户原话及“消息内容与会话元信息分层”Requirement、design 追加消息布局与 M1-G、delta-spec 新增 ios-client Requirement、局部原型及作者走查记录。

先查看真实原始截图 [before/09-markdown-default.png](/Users/czj/.codex/artifacts/feat-636-uiux/before/09-markdown-default.png) 与大字号 counterpart：消息气泡首行确实同时放置发送者、时间和“已完成”，交互卡片同样重复这一行；这占据正文前的阅读顺序。原截图是滚动中的真实客户端，不把其屏外内容当丢失，也不重新裁决此前字号问题。

随后用独立 Playwright session `feat636gate4` 实际 HTTP 渲染 `chat-metadata-prototype.html`，观察默认单聊/群聊，点击大字号开关并复查，再在 390×844 窄宽渲染。独立截图：[默认](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r4/feat636-r4-default.png)、[大字号](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r4/feat636-r4-large.png)、[390 窄宽](/Users/czj/.codex/artifacts/ios-uiux-20261022/design-gate-r4/feat636-r4-390-large.png)。

体验判断：

- 单聊标题已提供对方身份，气泡直接从正文开始；头像保留身份线索。正文和结论不再需要越过重复名字/完成标签，符合本次用户指出的阅读负担。
- 群聊两名不同助手的名字分别位于对应头像旁、气泡上方，名字与正文的归属清楚；自己的消息依靠右侧方向与青绿色区分。没有因移除气泡内元信息而使多人内容难辨认。
- 首条 10:11 与间隔后的 10:18 以居中独立行分隔，相近消息之间不重复时间；时间与任一发送者的气泡解耦。跨日使用日期加时间已在 design 明确，原型未展示跨日具体样本，本轮不宣称已观察其实际格式或分组算法；这是 M1-G 明确需要的真实/窄回归，规则本身已足以指导实施。
- 正常完成消息没有“已完成/已发送”噪声；进行中提示紧邻所属消息下方，失败提示以图标与红字可辨认。大字号正文自然增高，群聊身份与状态仍能对应，不依赖记忆屏外名字来判断作者。

### 真实接线、职责与契约

已核实 `ConversationView.swift:28–64` 从 store 时间线组装消息/配置边界并驱动 ChatMessageView，且会话已经有 `type`、`is_observer`、`can_write` 与 participants。相邻消息的首条/至少 5 分钟/跨本地日期分隔应由这个有完整列表上下文的呈现层计算；消息视图只接收对应展示决定，调整身份、气泡与下方状态/用量的关系，不更改 store、消息排序或后端时间字段。

`ChatMessageView.swift:27–87` 的名字/时间/状态首行确为当前落点，正文、InteractiveCard、附件、process、ChatPermissionCard、usage/elapsed 是独立已有分支。把正常元信息移出正文前沿可以复用这些分支，不需要新消息 schema、发送机制或公共组件框架。只读 Agent 协作虽为 direct 类型，仍要按 `is_observer` 保留双方外置名字；只读、权限卡及重试可用条件继续沿用，不能用会话人数判断群聊。

时间格式需要符合 design 的完整日期/时间语义：现有 `NanoTimestamp` 对非今天只显示月日，不能原样挪到新分隔行就声称保留历史消息时分。已有 `nanoDate`/日期格式能力可直接复用；M1-G 应核对首条、相邻间隔不足 5 分钟、恰好/超过 5 分钟、跨日，以及加载历史后的分隔。此处是已决定规则的实施验证投影，无需新机制或额外设计门禁。

delta 锚定 `docs/specs/im/ios-client.md`，是原生呈现增量，不修改消息服务与其他端业务契约，也未删除已有 Scenario。M1-G 已将两类会话实拍与时间/状态回归纳入局部复验；默认/辅助字号、用量/过程/权限/不确定发送及系统任务通知的原契约保持。沿用当前隔离 IM/Node 与模拟器资源即可，无新凭据/硬件前置；本 reviewer 未操作 Simulator、未启动其他服务。

### 历史问题、Issues 与 Recommendations

R1–R3 无重新打开项。本轮无 CRITICAL、WARNING 或新增可选建议；方案可进入该局部实施与真实客户端验收。Approved 仅覆盖设计，不是新增消息布局的产品验收通过。

### 本轮边界

仅追加本 Round，未修改设计或源码、未提交。已在渲染完成后关闭自己的 `feat636gate4` 浏览器 session，未关闭用户原有 Chrome、未操作父代理 Simulator；读取已有截图没有新增窗口。独立截图已移至仓外 `design-gate-r4`。逐项真实 before/after 与用户确认后才提 PR 的约束保持。

### Author final assessment

R3 Approved 已核实；未解决实质问题为零。进入实施，首文档、设计、delta与原型此后无未经审查的实质变化。保留用户确认后才提PR的交付限制；只做本地工作。

## Round 5

- reviewer_target: `/root/uiux_design_gate`（独立 reviewer）
- review_mode: `delta`
- mode_reason: 用户新增 PA 行一致性反馈改变既有呈现决定，按有界视觉/交互 delta 核对；不是仅文字 closure，不重审其他已验项。
- retained_from: `Round 1–4`；PA 本人绑定、优先分区、整行直达配置、搜索/去重、权限、读取失败恢复及草稿离开保护的语义保持；其他功能和消息增量的设计结论不重新打开。
- started_at: `2026-10-22T14:23:05+08:00`
- completed_at: `2026-10-22T14:25:57+08:00`
- duration: 2 分 52 秒
- baseline: `d6db6a47597acec6e8994b0f9c96c4c25c41fcde`；本轮开始时 spec/design/prototype 已有待审修改，产品源码未因该视觉反馈改变。
- Verdict: **Approved — 0 CRITICAL / 0 WARNING**

### 覆盖与独立证据

读取用户原话及 spec/design 新增的 PA 行校正、修订后的决定 6，并核查原型 agents 页与桌面侧栏。先查看真实 [桌面基线](/Users/czj/.codex/artifacts/feat-636-uiux/before/24-pa-row-web-desktop.png)、[窄屏基线](/Users/czj/.codex/artifacts/feat-636-uiux/before/25-pa-row-web-mobile.png)、[原生基线](/Users/czj/.codex/artifacts/feat-636-uiux/before/26-pa-row-ios.png)：PA 确实使用独立浅绿卡片/底色、不同头像与边距关系，并在姓名旁增加 Configure/配置。桌面 240px 侧栏尤其因额外动作挤压姓名；这是同一列表里的实际层级和密度不一致，不只是颜色偏好。

接管父代理已经建立的**唯一 headless session `feat636pa`**，不新开浏览器、不操作别的 session。实际点击 iOS PA 演示控件，观察默认行与相邻短名称行；点击 PA 整行进入配置，确认名称为我的 PA 后返回；切换大字号再复查；切到 Web PA 并在 390×844 中再次进入配置/返回。亲自查看以下截图：

- [默认与桌面侧栏](/Users/czj/.codex/artifacts/feat-636-uiux/prototype-pa-row-review-default.png)
- [整行配置结果](/Users/czj/.codex/artifacts/feat-636-uiux/prototype-pa-row-review-config.png)
- [大字号](/Users/czj/.codex/artifacts/feat-636-uiux/prototype-pa-row-review-large.png)
- [Web 窄屏](/Users/czj/.codex/artifacts/feat-636-uiux/prototype-pa-row-review-web-mobile.png)

画面判断：PA 保留在“我的个人助手”分区，仍容易定位；头像/两行文本/内边距与相邻短名称行使用同一行关系，去除特别底色、边框卡片及可见 Configure 后，没有另造一个占空间的主操作。整行进入配置的动作可用，返回回到列表。大字号长名称自然占更多行，PA 没有用固定高度或专属按钮压缩其身份文字。原型只证明该内容与交互决定，不证明真实 Web/SwiftUI 的最终行高或系统控件形态。

### 真实接线与职责判断

已读现有 `agent-row.tsx`：它已经统一 index/sidebar 与 detail/create rail 的头像、两行文本、桌面/窄屏 padding、min-height、节点/在线线索、active 背景和 aria-current，整行调用 `onSelect(agent_id)`。让 PA 入口直接复用此组件，比继续在 `personal-agent-entry.tsx` 维护专属 Avatar/identity/action 样式更简单，也能避免以后两个行实现再次漂移。保留本人分区和既有查询/匹配/去重职责，不需要重写列表或新增服务。

已核实两个真实组装点 `AgentsListPage`、`AgentsRailDesktop` 都调用 `PersonalAgentEntry`；后者 `selectAgent` 已接受 onSelectAgent 回调。实施时将当前 isMobile/activeId 与所需已有 Agent/contact 信息投影到同一个 AgentRow，保留原回调，才能同时兑现“同一行样式”和已选状态/草稿保护。无需从公开可见性推导管理权限，也不能为了样式另读他人配置。

原生 `AgentsView` 当前 PA 的 40pt 头像、额外 vertical padding、专属底色/配置文本，与普通 NavigationLink 的内容和 row insets 分开，是真实维护落点。将 PA 与普通行提取为**同一个小型行内容布局**、共用 insets，PA 的 destination 仍为 AgentConfigView、普通行仍为 Profile，职责与本次要求相称；不需要通用表单/列表框架。系统 NavigationLink 箭头与辅助说明可继续表达可点击性，可见“配置”字样不再承担必需信息。

spec 与 design 的用户反馈、决定 6 和局部 must-match 已明确覆盖桌面 index、详情/创建侧栏、Web 窄屏及原生；原 M1-E 追加局部复验即可。delta 的长期消费者结果（本人优先区、直接配置、权限/失败边界）不变，无须另造 canonical requirement。既有隔离服务和设备资源足够，本轮不新增外部前置。

### Issues、历史闭环与验收投影

无 CRITICAL / WARNING；R1–R4 没有重新打开项。这次取代的是早期“独立 PA 卡片/配置字样”的视觉决定，保留其可发现性与直接导航目标；不以旧 Approved 抵消用户这次反馈。

M1-E 局部实施验收需在真实客户端对照默认短名行高、长名/大字号的自然增高、Web active、整行目标与返回，并保留已有搜索/错误/权限/草稿保护结果。无需为纯文案或数值样式写镜像测试。Approved 是方案足以指导此项修正，不代表本次产品变更已验收。

### 本轮边界

只追加本 Round，未改 spec/design/prototype 或源码、未提交。`feat636pa` 已在完成操作后关闭，复查关闭返回 `Browser 'feat636pa' is not open`；未操作 Simulator、未启动服务、未触碰其他任务浏览器。截图保存在仓外指定目录。其他已验结论与用户确认后才提 PR 的要求保持。

### Round5 Author retained note

R5 后仅将 delta-spec 既有「双端查找」一句同步为已审的普通行样式、整行配置和无额外 Configure，与 R5 已审 spec/design/prototype 一致，无新增决定、接口或旅程；由本轮 corrected-delta 纳入静态复核，不另触发设计复审。


## Final sync — retained（2026-10-22）

- 用户已确认本轮效果并要求提 PR。
- validated_at: `09eb0e45855705e76bad50419df34e51141534f6`（最新 PA 行 delta；此前 full 的实际执行版本见上文）。
- executed_base: `d846b015b8774461bb26b172e458443ce1eb071d`。
- effective_base: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`；effective_through: `aa63af9b5f5856533df2419d200237fccc599f54`，及随后仅作相同 delta 的 canonical 归并、unit 归档和交付记录的提交。
- main 增量仅为独立 feat-635 的设计/需求/原型与证据，没有产品代码、当前 specs、依赖或 CI 改动。逐项核对无影响本报告的范围、交互、权限与测试前提，保留前述 full 与最新局部通过结论；不把本次 retained 判断描述为重新执行全部门禁。
- corrected delta 保持此前独立逐项核对通过的原文，按所属 area 归并 canonical；不引入新的产品要求。
