# Design review — feat-589

## Round 1

### Metadata

- reviewer: `/root/feat589_design_review`（独立 reviewer）
- target: `feat-589-subagent-trajectory-navigation`
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖需求、核心运行事实、共享接口、前端连续旅程与唯一 milestone，不存在可 retained 的前轮证据。
- started_at: 2026-10-13T13:09:22+08:00
- completed_at: 2026-10-13T13:16:54+08:00
- duration: 452 s
- baseline: Nano `main` / `b7e367cc0`；DSH 锁定 `0.2.1-alpha.1`，只读参考 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- reviewed_snapshot: 本轮冻结、尚未提交的 `original-request.md`、`spec.md`、`design.md`、`plugin-investigation.md`、`specs/im/agent-work.md`、`prototype.html`、`evidence/*`、`M1-navigation/.gitkeep`。主仓既有大量 dirty/untracked 内容未修改；本 reviewer 仅新增本报告。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 尚未通过。**

公开插件技术路线与职责边界成立；不需要修改 DSH 上游或再向用户征询技术选型。阻断项是原型中尚未一致表达的范围关系，会使实施者对必须匹配的体验产生不同理解。修正对应原型与设计契约、按受影响路径复查即可，不要求重做整个设计或提前完成后端实现。

### Coverage 与证据

#### 需求、决定与架构

- 已完整读取首文档 R1–R7、原始请求、设计、插件调查和 delta。用户要求的主动／后台、普通／fork、并行／重复 epoch／嵌套、持久回看、异常状态、只读、跨屏均分配到 M1；无遗漏的独立开发阶段，也没有并行写同一边界的安排。
- 实际入口核对 `src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx`、`agent-trajectory.tsx` 和 `packages/dsh-trajectory-viewer/src/boot.jsx`：当前宿主按 session 重建单 iframe，查看器固定渲染官方 `trajectory` slot；仅增加外部选择器无法获得受控范围与行内入口。新增独立 `nano-execution` View 并保留官方原件，是对当前缺口有针对性的职责选择。
- 运行事实应由 integration 持有，宿主持有授权及 frame 栈，viewer 持有范围、选择与呈现，product-contracts 只传 JSON DTO。复用现有固定 observer、MessagePort、Session Controller、官方 projection 与图片读取链路，避免另造 Agent Loop、内核 HTTP 或原始日志解码层。保留父 frame 的实际代价是每级保留读取与内存；该设计已明确随 Work 生命周期整体销毁，现阶段没有必要增加另一套恢复状态协议。
- `SPEC.md` 的既有浏览器例外与 design 的更新意图相符；官方 bundle 原样保留，不扩大 PA／IM 的 DSH import 范围。未发现要求 private import、组件复制或修改上游的路径。

#### 公开接口与生命周期

核对锁定安装包的公开 client/type 入口，以及只读参考源码的 `packages/subagent/subagent/src/{types,lifecycle,continuation-activation}.ts`、`packages/subagent/subagent-in-process-driver/src/index.ts`、`packages/core/{agent,agent-loop,session,tools}/src/index.ts`：

- `subagent/start/end` 确实使用同一真实 runId 配对、以直接父 Agent 为 scoped carrier；one-shot 的生命周期 runId 不能替换成 child sessionId。continuable 的一个 run 是 residency epoch，驻留继续收信不构成新 epoch。design 正确处理了这一区别。
- one-shot 创建 Agent 后即可投递 prompt，再发布 start；因此只在 start 时读取最新 seq 会漏前段。公开 `agent/created` 是串行创建通知，`session.seq` 是下一条事件的 offset，公开 `session/event` 同步发布已接受事件；提前记录下界并独立观察尾部，具有可实施的公开路径。
- continuation 会在子对象释放后再发布 terminal edge，故需要事先观察尾部，不能在 end 回调才依赖 `agents.get(childId)`。design 的同步冻结、串行持久写和读取屏障符合这个顺序。
- 工具 around-dispatch hook 支持按异步调用上下文携带 callId；现有 `knowledge/runtime.ts` 已有在真实 `subagents.start('fork', ...)` 周围传入知识维护上下文的落点，后台用途不需要猜测标签。
- `storageDomain`、session slot、官方 trajectory 注入数据和 `loadThrough` 能覆盖设计所需的读写与展示接口；原版 Inspector 不需要私有组件导入。
- 上述是源码可行性判断，**不是新增捕获实现已通过**。起点 offset 与包含式 event seq、setup 期间记录和继承前缀的区分、start 前已观察事件、冷恢复、结束释放及重启后的 unknown，仍必须由 M1-W1 的真实 DSH fixture 证明。现有真实委派日志不能替代这一验证。

只读落点核对 `packages/dsh-integration/src/trajectory.ts`：prepare 已验证 global binding 与持久父链，call 已固定 selected session 并限制方法；在这一 observer 增加 runs 读取合理。子 frame 重新从固定 observer 核验 DTO、账号变化销毁整栈，与已有附件资格边界一致。

#### 前端独立体验观察

实际打开 `http://127.0.0.1:56201/prototype.html`，对照 [当前产品基线截图](evidence/current-desktop.png)，亲自完成以下操作：

- 1280 宽，选中父模型请求并放大至 1.5×，点击真实流中的发起记录进入计算子执行，再进入嵌套核对、逐级返回；父请求仍选中，缩放仍为 1.5×。用途、来源链、返回与状态相邻，路径不依赖顶部选择器，满足主要发现／返回的设计意图。
- 390 宽，进入后台记忆 fork，检查范围条、记录列表、下方检查区及原生明细往返；主要操作没有横向挤出。窄屏的检查区域置于列表之后，有明确的平台布局决定，未用“原生适配”占位。
- 820 宽，切换 fork 会话历史，继承行淡化并标识“继承”；再切换边界未知，终点按钮禁用、提示结束未知。对应实质问题见 R1-W1、R1-W2。
- 视觉与基线对照：沿用浅色紧凑表格及输入／模型／工具色彩，新增发起行把用途放在状态与 fork 标记之前，新增来源链补齐原先选择器缺少的因果关系。保留官方完整明细的方向合理，当前原型只演示入口与返回，不能作为官方检查器保真验收。

本轮未要求保存额外截图，冻结的 [作者走查](evidence/design-walkthrough.md) 与代表性图片提供可复查背景；问题均可按下列操作在冻结原型重现。独立浏览器观察与作者的结论分开判断。

#### Delta、milestone 与验收资源

- `specs/im/agent-work.md` 的 Target 正确指向 current IM Work spec，使用 ADDED Requirements，不误删或替换 current 的其他 Scenario。新增只读／身份变化约束与既有 Work 权限一致。
- M1 的 reviewer 结果与 worker 证据分别覆盖主要 must-match、运行捕获、权限、构建和产品对照；完整官方检查能力仍是退出标准，没有以原型或普通数据列表替代验收。
- Runbook 已给出 IM／Node／DSH 的停止、构建、隔离启动、健康检查以及真实浏览器驱动路径。账号、workspace、模型代理、非管理者测试账号来源可落实；iOS 专属渲染器明确不在本 unit 范围。
- 审查过程中 author 提供备用模型路由成功证据；reviewer 独立只读解压并核对隔离 runtime 日志：parent `ebf7d02e-a87d-4358-9b08-31bc7fdd21d4` seq52 为 subagent 调用，seq53 指向 child `e50982a9-7297-4439-986b-b3b9e85295fc`，seq54 返回 391，seq64 为 completed；child seq19 为 completed。故 **实际模型资源当前可用，不再列为 Gate 2 阻断**。冻结 design 仍写“实施验收前检查实际完成”，应在 author 收口时同步具体隔离路由与证据；不改变真实边界捕获尚未实现的结论。
- 既有前端 number/Timeout 类型错误及全仓 docs-check 的无关问题不归因于本设计，也不据此声称 CI 通过；M1 保留所需构建／CI 门禁。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 范围概览与过程记录没有共同的示例坐标，尚不能指导“自动聚焦本次”的 must-match

- 位置：`prototype.html:24–26`；`design.md:15,74,87`。
- 证据：普通计算子执行顶部为 `12:41:08 → 12:41:16`，但其输入／模型行分别显示 `12:41:02`／`12:41:04`，全部高亮时间轴却结束于 `12:41:20`。fork 切换“查看会话历史”后，同一输入 seq30 的时间因列表索引变化而改变；继承行早于轴起点，范围框仍按固定 33% 开始。点击三类时间带按索引取模选行，不能说明其与对应类型记录及区间的关系。未知状态仍沿用相同闭合高亮框与固定尾端，只有文字变为未知。
- 用户代价：用户无法从画面核对“高亮的这一段”是否对应下方本次过程，尤其 fork 的继承边界与未知尾界只能靠解释文字猜测；实施者无法判断应匹配哪套坐标。这是本 unit 核心信息关系的缺口，不是要求原型接真实后端。
- 要求：用一组自洽的固定示例事件时间／区间驱动范围条、概览与记录；同一记录在本次／历史视图之间保持时间不变，并示明未知尾端如何区别于真实完成终点。复查普通子执行、fork 历史和未知状态，留下修订后的代表性画面即可。

#### R1-W2 — 切入完整会话明细后，“本次执行”控件与计数仍暗示作用于当前明细

- 位置：`prototype.html:9–12,24–26`；`design.md:19,89`。
- 证据：390 宽进入“记忆整理 → 原生明细”，完整会话说明上方仍展示“本次执行 12:41:08 → 12:41:16”和可点击的定位起点／终点／查看会话历史；底部仍为“4 条记录 · 本次执行”。这些按钮实际改变隐藏的导航列表，不会定位当前显示的原生明细。820 宽在导航中显示包含继承行的会话历史时，底部也仍称“8 条记录 · 本次执行”。
- 用户代价：同一屏的范围与计数互相冲突；用户可能把官方完整会话中的内容当成本次工作，或点击定位按钮后看不到当前明细发生变化。仅在演示说明段落中解释完整会话，不足以建立可直接理解的产品作用域。
- 要求：明确区分“保留的来源／本次摘要”和“当前展示范围”。完整会话明细使用相应范围与计数标签；导航专属定位／历史控件需隐藏、禁用并说明，或显式执行“返回本次导航并定位”，选择一种写入 design 并在原型落实。复查窄屏来回切换和 fork 历史，不要求重做官方 Inspector。

### Recommendations

- R1-R1：`plugin-investigation.md` 结尾仍写“尚未形成完整 design、delta-spec、prototype”，与本轮产物不一致；收口时更新为调查快照状态，避免后续误读。不影响技术路线裁决。
- R1-R2：实现时在 DTO 注释明确 startSeq 的 offset/包含式转换、running 已知尾界与完成 endSeq 的含义，并通过已计划的真实引擎 fixture 验证；无需新增一套抽象或兼容机制。

## Author Resolutions — Round 1

- R1-W1：接受。原型改为每条记录持有固定时间；范围条、时间轴、类型轨道及点击定位均由同一坐标生成。普通计算 12:41:08–16、记忆整理 14–20、嵌套核对 11–14。fork 历史在 00–20 轴中显示 14–20 的本次范围；同一 seq 的时间在切换后不变。未知／运行／中断均显示开放虚线尾端，最后已知时间不称为结束。design 同步该信息关系。
- R1-W2：接受。原生明细只保留来源执行摘要，隐藏三个导航专属范围操作；底部标明完整会话，不引用导航计数。返回导航恢复操作与状态；历史计数明确含继承记录。
- R1-R1：接受并更新调查结尾，链接现有设计与审查状态。
- R1-R2：接受，在 DTO 契约明确包含式 start/end、创建时 next offset 与运行中已知尾界区别；沿用 M1-W1 真实引擎验证，不新增抽象。另明确 foreground/background/unknown 字段从真实启动参数或后台上下文取得，以兑现既定主动／后台表达。
- 资源：Runbook 已回填通过独立核实的备用模型与 parent/child seq。原生冷历史和委派呈现现有测试基线通过（`pnpm test packages/dsh-integration/tests/trajectory.test.ts packages/dsh-integration/tests/tool-presentation.test.ts`，2 tests，2026-10-13 13:16），不替代新增实现的验收。


## Round 2

### Metadata

- reviewer: `/root/feat589_design_review`（与 Round 1 相同的独立 reviewer）
- target: `feat-589-subagent-trajectory-navigation`
- review_mode: `full`
- mode_reason: 起初按两项局部体验修正选择 delta；核对后确认新增 delegation 字段和 start/end 定义涉及共享 DTO，故在同一 Round 扩大为 full。重新核对首文档、设计、delta、milestone 和完整数据链路；未变化的源码事实引用 Round 1 的同基线独立核对，不重复无变化的源码调查。
- started_at: 2026-10-13T13:20:29+08:00
- completed_at: 2026-10-13T13:23:59+08:00
- duration: 210 s
- baseline: Nano `main` / `b7e367cc0`、DSH `0.2.1-alpha.1`；本轮冻结修订，无产品代码改动。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

两项原型问题均已闭环。方案足以指导实施；此结论只批准设计，不代表新增起止捕获、跨 frame 生命周期、真实权限或产品验收已完成。

### Coverage 与证据

- 现状与用户约束：重核原始请求与 R1–R7，用户继续授权由 Agent 选择技术路线，保留不修改 DSH 上游、完整检查、只读、跨屏要求。主入口、单次执行／epoch 语义、父子返回与持久回看未缩减。现有单 iframe 与官方 slot 的实际组装事实沿用 Round 1 证据，基线未变化。
- 决定与职责：完整读取修订 design。integration 观察并保存 run、product-contracts 传 DTO、viewer 维护范围与官方投影呈现、宿主持有授权 frame 栈的分工仍闭合。原官方完整视图继续复用，未增加私有导入、上游 fork、第二个 Loop 或执行权限。
- 共享 DTO：新增 delegation 只补充事实呈现，不参与 runId 身份或调度。只读核对 DSH `tool-subagent/src/index.ts` 的真实 `run_in_background` 路由：显式参数／明确后台维护上下文可提供该事实，缺失则 unknown，不从返回快慢猜测。kind 继续表达 tool/memory/skills 来源，因此主动工具调用与后台运行不会被迫共用一个枚举。新增字段经既有 carrier 传输，不扩大 observer scope。
- 起止定义：startSeq 作为 next offset 对应的包含式起点，endSeq 仅终态设置并取最后接受事件；运行中显示官方已知尾部。它与 Round 1 已核对的 session.seq／session/event 生命周期一致，避免把运行中已加载末尾当作完成终点。setup 记录、start 前事件、冷恢复及结束释放的实际覆盖仍由 M1-W1 证明，不以本轮文档定义替代运行证据。
- 接口与授权：trajectory/runs 固定 observer、子 frame 回读核验、只读方法限制、父链授权、身份变化整体销毁的方案未改变；新增 DTO 不绕过图片与原聊天资格判定。
- Delta：重新读取 `specs/im/agent-work.md`，仍准确指向 current Work spec，ADDED 保留既有 Scenario。其完整会话与导航范围不混淆的要求现已得到具体 UI 方案支持。
- Milestone：M1 的 R1–R4 与 W1–W3 继续涵盖完整旅程、状态准确性、并行／重复／嵌套、跨屏权限、构建与独立审查。无新并行冲突或未分配的需求。
- 验收资源：Runbook 已回填 Round 1 独立核实的成功模型路由和 parent/child 证据；同一隔离链路可用于后续真实验收。此前前端类型错误仍被明确记录，没有把基线 Vite 渲染／既有测试冒充新增实现通过。

### 历史问题闭环

#### R1-W1 — closed

Author Resolution：统一固定记录时间、范围及类型轨道关联；历史切换保留坐标；未知／运行／中断采用开放尾端。

本轮独立使用 Chrome 原生界面实际打开冻结原型并操作（原 IAB 会话失效，未把其失败当作视觉证据）：

1. 从普通发起点进入，范围条与轴端同为 12:41:08–16，输入为 08、模型为 09、输出为 16；实际画面不再出现行时间早于本次范围的冲突。
2. 从后台记忆入口进入，默认范围为 14–20；切入会话历史后轴为 00–20，seq30 输入仍为 14。点击“模型 · 12:41:15”轨道后，检查区明确显示“记录 32 · 12:41:15”，对应请求 #4。
3. 切到边界未知，范围条显示终点未知及“最后已知记录 12:41:20”，终点定位禁用，说明标明最后已知不是结束点。独立查看 [820 宽修订画面](evidence/prototype-unknown-820.png)，可见继承前缀在范围外、开放虚线尾端及一致的记录坐标。

坐标与视觉关系已足以指导本次聚焦实现，关闭。

#### R1-W2 — closed

Author Resolution：完整会话模式只保留来源摘要，隐藏导航范围操作，使用完整会话标签；返回保留选择与历史模式。

本轮实际从 fork 历史、已选择 seq32 的状态切入原生明细：顶部变为“来源执行摘要”，定位起点／终点／历史切换均消失，底部为“完整会话 · 记录由原生明细展示”。返回后仍为包含继承记录的历史模式，seq32 的选择、时间与详情保留。独立查看 [390 宽修订画面](evidence/prototype-native-mobile.png)，作用域说明和返回操作均可直接辨认，没有残留本次列表计数。对应决定已写入 design，关闭。

#### R1-R1 / R1-R2 — addressed

调查结尾已改为当前产物链接与尚待实施的证据边界；DTO 起止语义已明确。无需新增机制。

### 体验证据范围

本轮亲自复查了改动后的连续交互，并检查作者留存的 820／390 宽实际渲染图；精确宽度截图由 author 生成，本 reviewer 未在本轮重新设置这两个 viewport。Round 1 的独立跨屏布局与嵌套返回证据仍适用；本轮所改范围标签、操作隐藏与坐标关系已分别具备当前交互和当前画面证据。没有把原生明细占位区域当作真实 Inspector 验收。

### Issues

无未解决 CRITICAL / WARNING，无新增 issue。

### Recommendations

无新增建议。按 M1 已列退出标准实施并验收，尤其不得用 unknown 兜底替代受支持执行的准确边界。

### Author final check

作者已核实两轮 findings、recommendations 及其闭环依据，确认无实质遗留。Round 2 后仅追加本确认，不改变受审方案、原型、delta 或 milestone；Gate 2 对本次提交的设计有效。
