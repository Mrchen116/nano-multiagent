# feat-667 Design Review

## Round 1

### Metadata

- reviewer target：`/root/design_review_667`（独立 reviewer，未参与受审设计编写）。
- review_mode：`full`。
- mode_reason：首次 Gate 2 审查，覆盖首文档、全部设计、delta-spec、M1 骨架与两份用户附件；在同一轮应用 `agent-context-review` 的 Design Review 模式。
- started_at：2026-10-27T12:09:00+08:00（近似，开始时未单独采集时钟）。
- completed_at：2026-10-27T12:12:44+08:00。
- duration：约 4 分钟。
- source baseline：`/Users/czj/Repos/nano-multiagent`，`main`，`69d01e4557bcc87a5f7194dcb947c7473ead20d9`；设计及 delta 为工作区未提交输入。审查只写本报告，不修改受审文件、产品代码、分支或生产数据。
- 受审内容 SHA-256：
  - `spec.md`：`939846cc9e9d89f458bc6584d6ff308a00693683d8ce7a93fcd6eab67d3aa994`
  - `design.md`：`f28d9a7cbd08396330a6be074c726bc814f95f8ce01053709c90b6e9b540b3a4`
  - `specs/gateway/personal-agent.md`：`fe025c8a08e22bbcbc54034c5dd0529cebd005b23944b1e6891127ab87e99c38`
  - `input/split-instructions.md`：`9f699734035ce6d46eacf2ccd37fd23b9868e2705894ac8bc2f12cd66821505f`
  - `input/pr414-review.md`：`e67c56b6f6fb8dbfa4c53d717d126a41ed210e7c0367284e656fabc383d8434c`
  - `M1/.gitkeep`：空文件，目录内无预填 tasks/progress。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

三份产品文本的设计边界可进入实施。此结论仅认可方案及其验证约束，不代表真实原生二级委派、并行更正/停止、等待响应或轻量准备已验收。设计明确要求关键旅程不支持时标 blocker/B，M1 不完成、PR 保持 Draft；不得把本次 Approved 用作产品通过或 Ready 的依据。

### Coverage 与证据

#### 现状与实际产品装配

- 默认指导的真实入口已核对：`apps/im-server/src/personal-agent.ts:319-347` 的 PA 创建路由仅在未恢复既有配置时构造含 `personalAgentDefaultInstructions` 的 candidate；active binding 直接返回。`apps/node/src/configuration.ts:79-105` 将 `custom_prompt` 映射为 `systemPrompt`，携带真实 Skill roots 与选择模式；`packages/dsh-integration/src/agent-config.ts:126-163` 在 Agent 上挂载 Persona/Skills，配置清空会 dispose Persona，不从默认文件回填。因而修改默认文件不等于给既有 PA 自动替换自定义指导。
- 随包 Skill 已接入正式节点启动：`apps/node/src/main.ts:50` 调用 `installBuiltinSkills`；`packages/personal-assistant/src/builtin-skills.ts:18-67` 遍历目录、刷新随包名称。新增目录无需增加注册 API。`configuration.ts:98-105` 将 workspace roots 排在 owner/global roots 前；`packages/dsh-integration/src/capabilities.ts:137-158` 在 list/get 两路过滤 allowlist/denylist，并按 root index 提供 rank。设计对用户选择和原有发现路径的复用有代码依据；随包方法升级仍须与自定义 prompt 保真分别验证，不能声称既有 Agent 的全部行为逐字不变。
- 固定来源/权限规则来自正式 preset，而非默认文案：`agent-config.ts:105-111` 安装 GlobalMode 与 PersonalTools；`personal-security.ts:132-136` 提供可信 owner、participant/observer、原始授权、主 PA 代表发送及披露边界；`global-mode.ts:18-43` 区分公开发送、内部 child 回执与私人草稿。A 不触碰这些接口，私人准备不自动转成外发许可，与现行规则相容。
- 观察数据及唤醒有既有路径：`packages/personal-assistant/src/global-agent.ts:237` 允许主人正常来信时读取已积累背景；`:257-308` 保留背景期限、observer 提醒及无授权升级语义；`:358-404` 摄取观察事件。A 复用这一通路，不需要新 attention/query receipt 服务。
- 已检查现有测试的证据能力：`personal-child-delivery.test.ts:14-34` 使用 fixture 主动 fork、直接执行工具及替代模型 stream；`personal-security.test.ts:69-99` 检查 Skill/普通工具与清空、禁用后的装配。这些可复用作工程回归，但不能证明真实模型会主动读 Skill、继续二级分工或接住并行更正。设计对此已有明确区分。

上述为当前 main 中生产代码路径的静态核对，未连接或检查线上部署版本，未运行生产服务。

#### 用户约束、决定与职责

- 两份附件要求先 A、保留 #414、从 main 拆取；不带入新记忆、统一检索、关注库、执行绑定、文件发布及新调度器。`design.md:19-26,38-46,69-77` 明确保留这些限制，也没有把旧 #414 的白名单执行者作为前提。附件中的旧版本缺陷仅作为范围依据，本轮未将其当作当前 main 的缺陷。
- 首文档七个场景均能映射到验证计划与 M1：小事直答/长事真实结果；两个独立事项中的更正、短问题、单项停止；有内容的私人准备、已处理/无新价值/覆盖不足；自定义、清空、禁用。`design.md:91-101` 要求真实输入、工具回执和用户结果，而非字符串存在或 spawn 成功。
- 架构职责合理：IM 保留首次创建默认值，PA 随包 Skills 持有可复用工作方法，Node 安装与提供配置，integration 继续持有运行时与安全装配。复用 Inbox/Task/Heartbeat/schedule/文件及 Memory，避免为方法指导另建状态权威或执行管理器；没有新增跨包依赖、private import 或第二 Agent loop。
- 单 M1 适合三份紧密相关文本及同组真实旅程验证，拆并行 milestone 无独立交付收益。原生能力不明是已识别的实施验证风险；设计给出失败后保持 Draft 的处理方式，因此不构成需要先暗中扩入 B 的设计空洞。
- 无前端变化，采用实际客户端使用的登录/聊天/配置 API 验收符合本片范围；无需 UI 原型。无部署迁移，回退区分随包文本与已经持久化的新 PA custom_prompt，未承诺回退代码会重写用户配置。

#### Agent Context — Design Review

- **Surface / Consumer**：主 PA 的默认 Persona、按需 Skill 元数据/正文、现有 Inbox 与 conversations 来源、原事项记录及子 Agent 交接。普通 Global Agent 可消费共享持续工作方法；可信身份仍由宿主提供。
- **发现与时点**：常驻指导提供选择原则，复杂工作方法按需加载；默认创建、配置更新、禁用和 Skill roots 均有正式入口。真实模型请求、目录发现、正文读取及工具回执被列入验证与退出标准，未把磁盘文件存在等同于模型消费。
- **语义与组合**：Before/After 将“仅跟进已交办消息”扩展为“重要观察可核对并私人准备”，同时保留不创建新外发授权、核对后续状态、不把确认收到视为交付。与固定安全提示及 Global 显式发送机制无确定性冲突。设计中“子 Agent 只收到所需交接信息”按 `design.md:42,56` 的整体语境理解为交接文案最小化要求，不解释为新增运行时上下文隔离保证。
- **更新与恢复**：原工作记录保留真实执行 ID、当前要求和等待条件；更正/取消回到原事项，晚结果不成为复活理由。当前文件与工具可用性、跨事项真实行为必须由实施证据验证；没有用新 schema 或跨重启保证补齐未知能力。
- **证据状态**：当前装配与验证计划有直接源码/文档依据（CONFIRMED）；候选文字实际进入 provider 请求、模型正确发现 Skill、二级执行返回、并行取消及静默行为仍未验证。本轮无可成立的 Context CRITICAL/WARNING，不从未知模型行为推定缺陷或成功。

#### Delta-spec、验收与回退

- delta 正确锚定 `docs/specs/gateway/personal-agent.md` 的“默认服务指导复用普通配置和 Skill”；完整保留原“用户调整服务方式”“跨轮次持续工作”两个 Scenario，新增“重要观察后的私人准备”。新增行为有默认指导、来源可读和 Skill 未禁用的前提，不改变 IM 配置协议。
- Runbook 使用仓库 e2e 脚本、独立 `/tmp/pa667-review` 数据与合成账号；`scripts/e2e-up.sh:31-35,112-115` 支持由脚本确定代码根、用 `--wt` 指定隔离数据位置。真实模型可用性先做小请求核实，功能及失败分支不推迟到生产；未要求生产写入、迁移或重启演练。
- M1 退出标准明确全部七个场景、真实 Skill/二级委派能力、有限基线对照与选择保真。关键缺口仍阻断完成，与附件要求一致；Draft 中可审阅文本不等于允许跳过 M1 退出条件。

### 历史问题闭环

无历史 Round；无待关闭 issue。

### Issues

无。

### Recommendations

- **R1-R1（可选，证据表述）**：实施记录可单独标记观察准备来自十分钟背景通知还是主人正常来信提前触发（`design.md:89`）。两者均是已有合法入口；后者能证明读取后的准备行为，但不能单独证明到期自主唤醒。保持这一证据边界即可，不要求为 A 修改通知节奏或增加运行时机制。

### Author Resolutions

- R1-R1: accepted。实施证据区分十分钟背景通知与主人来信提前触发；后者不证明定时自主唤醒。不改变受审产品范围、设计或验收要求。
- Author 已核对报告与当前代码；无实质异议，受审文件未修改。Gate 2 R1 retained。

## Round 2

### Metadata

- reviewer target：`/root/design_review_667`，沿用 R1 独立 reviewer。
- review_mode：`delta`。
- mode_reason：新增用户“再增加一层委派”的决定，以及 B 的公开深度配置落点；A 的三份产品文本范围、接口、delta-spec、M1 与验收标准未变。该变化有界，无需重做完整审查。
- started_at：2026-10-27T14:17:18+08:00。
- completed_at：2026-10-27T14:18:43+08:00。
- duration：1 分 25 秒。
- source baseline：`main`，`1e2b6dbf6d1b2590a9cee7a6d09171852814ca41`；工作区仅 `spec.md`、`design.md` 有受审修改。相对 R1 代码基线，HEAD 增量仅为本 unit 设计文档、报告与目录骨架，未修改产品代码。
- 受审版本 SHA-256：`spec.md` = `b58d80500ff1fd60bf4fc231e62a93c3b2f9c63fb0459290946a921c704f9e62`；`design.md` = `01248a6db815027c6e6328bcc01ee94ed0f14c500d0fdd34e3c341261280ff70`。delta-spec 摘要与 R1 一致。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

增加一层的配置决定有锁定依赖与产品装配依据，归属独立 B 的边界明确。A 可按原范围实施，但当前二级旅程仍未通过；本轮没有产品实现或真实二级验证，不授予 M1 完成、Ready 或部署结论。

### Coverage 与证据

#### 新增决定与真实落点

- `spec.md:30-35` 保留用户原话，并明确目标为主 Agent → 一级执行者 → 二级执行者；不强制所有任务分工，也不增加并发配置或权限范围。`design.md` 的新增关键决策将此配置放入 B，A 仍不修改运行时。
- 已独立核对锁定 `@deepseek-ai/dsh-subagent@0.2.1-alpha.1` 的 `lib/index.js:2821-2823`：`maxDepth` 默认 1，`maxActiveSubagents` 为独立配置。`:110-114,400-404` 从持久 header/运行选项取得主 Agent 默认深度 0，创建 child 时加 1，并在 childDepth > maxDepth 时拒绝。因此 maxDepth=2 的含义确为允许深度 2、拒绝普通委派继续产生深度 3。
- 同包 `lib/index.js:2863-2868` 的 `resolveMaxDepth` 在工具未显式配置时读取服务配置。锁定 `dsh-tool-subagent/lib/index.js:269,508-519` 将该值传入原生创建请求；锁定 `dsh-base/cordis.patch.yml:349-390` 注册 subagent 服务及普通 spawn/fork 工具，未另覆写 maxDepth。本结论针对这两条普通工具路径，不将其夸大为任意插件或显式 provider-managed 路径的全局安全上限。
- `packages/dsh-integration/src/client.ts:15-26` 的 `prepareProfile` 使用 `cordis.patch.yml` 公开配置入口，目前只添加 web 与调用者 patch；没有 subagent 深度覆盖。`apps/node/src/main.ts:155` 在 partition 启动时统一调用此入口，未按普通/PA 分设深度，因此 B 的共同默认行为描述正确。
- `packages/dsh-integration/tests/trajectory-runs.test.ts:33-45` 已通过同一公开 profile patch 注入 maxDepth=3 并编排嵌套 fixture。它是既有接入方式的源码证据；本轮未重跑，不把 fixture 编排视为真实模型二级交付成功。

#### 架构、Agent Context 与退出条件

- 新决定复用 integration 已有配置责任，没有 DSH fork/private import、新工具、新执行管理器或 PA 特例。深度变化与并发数量、工具选择、授权/来源规则分别处理，避免用“全部放开”实现二级委派。
- 同轮继续采用 Agent Context Design Review：新增内容明确区分当前只有一层、B 目标两层、模型实际选择与结果返回仍需验证。默认指导及 Skill 不能把未来配置当作当前能力；A 受限时标 blocker/B 的既有要求仍有效。关于子 Agent 上下文继承与交接信息的 R1 解释保持，不新增隔离保证。
- B 的验证要求覆盖真实二级创建、执行、回传、三级拒绝和原有代表发送身份限制。它说明本次新增决定所需的最小证据，不代表 B 的完整实施与验收已发生；其他持续执行问题仍须有证据才进入 B。
- M1、三份产品文本范围、delta-spec 与无部署迁移决定没有改变。新增“B 未落地前 A 二级旅程未通过”与 M1 的 blocker/Draft 约束一致，不是降低验收门槛。

#### 保留覆盖

`retained_from: Round 1`：默认指导创建/更新/清空接线，Skill 安装/发现/禁用，固定身份/来源/披露链，观察读取及通知，七个用户场景、delta 合并目标、隔离 Runbook、回退和无前端结论。理由：本轮 diff 仅增加深度现状与 B 决定，相关产品代码及这些受审设计未改变；R1 原证据仍适用。

### 历史问题闭环

- R1 无 CRITICAL/WARNING，故无阻断 issue 待关闭。
- R1-R1：Author Resolution 已接受并要求区分背景通知与主人来信提前触发。已核对该记录；本轮不改变观察入口，建议在设计层面已处理，真实验收记录留待实施。

### Issues

无。

### Recommendations

无新增建议。

### Author Resolutions

- R2 无 CRITICAL/WARNING 或新增建议；Author 已核对普通 spawn/fork 的深度决定及 B 归属，无实质异议，受审内容未改变。

## Round 3

### Metadata

- reviewer target：`/root/design_review_667`，沿用 R1/R2 独立 reviewer；未参与本轮设计修改。
- review_mode：`full`。
- mode_reason：A+B 合并后产品范围、主/子工具边界、Context 消费者及 M1 退出标准均有实质变化。重新覆盖完整方案；R1/R2 的源码证据仅在当前基线仍成立时复用，不沿用旧结论直接放行。
- started_at：2026-10-27T15:34:56+08:00。
- completed_at：2026-10-27T15:39:34+08:00。
- duration：约 278 秒。
- source baseline：`/Users/czj/Repos/nano-multiagent`，`main`，`9151dcefa0d6200e8a7805e3a70df1b57852a5f1`。受审输入为未提交的 spec/design、新增 global-agent/agent-capabilities delta、原 personal-agent delta 和 M1 空骨架；两份 input 附件与历史报告作为范围与审查历史依据。
- 受审内容 SHA-256：
  - `spec.md`：`e03f40a04b6b338a5415324ef4e62a8da74326052b844b3586123345480e0a0a`
  - `design.md`：`060a68d04a8b95504d079de5b3c1c70a034dab8ee15f7053a6d0eb7e77f59482`
  - `specs/gateway/global-agent.md`：`d267cb1738c79d01e700922abb296fdfedf50a9fdca545e922d07afbdfa8e6fa`
  - `specs/gateway/agent-capabilities.md`：`5ded016b2f68531e20a926c39038ff06d015eda7544ece64077339993c2e454d`
  - `specs/gateway/personal-agent.md`：`fe025c8a08e22bbcbc54034c5dd0529cebd005b23944b1e6891127ab87e99c38`

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本轮认可 A+B 的完整设计：公开配置增加一层委派，Global 主实例持有产品聊天工具，子 Agent 保留原生内部通信，主 Agent 通过已有记录与控制负责停止及明确接续。该结论取代旧轮“B 另片实施”的范围判断。尚无本轮产品实现、实际 provider 请求或真实二级交付证据；M1/Ready 仍以本版退出标准为准，不能把设计通过解释为能力验收通过。

### Coverage 与证据

#### 需求与范围闭合

- `spec.md` 的最新用户原话和整理决定明确覆盖 A+B、默认深度增加一层、普通 Global 与 PA 共用主/子边界、Task 归主 Agent、主 Agent 记录执行者并协调停止/接续、沿用恢复、不引入观察者。`design.md:18-29,33-70` 与之对应，原附件“先 A、B 后续”的顺序已被最新决定明确取代；保留 #414、不整包合并、不迁移旧 workspace 的限制继续成立。
- 全部十个 Scenario 已对上验证：原七项 PA 服务行为保留，新增二级逐级交付、子 Agent 请求资料/内部回传、用户明确接续。设计不把 Task 页面暂停承诺成整树硬停止，也不以“允许再委派”暗示增加并发、全部权限或按事项隔离。
- 单 M1 的范围和退出标准已经随 A+B 同步更新（`design.md:113`）。失败统一保留未通过，不能再把本次 B 的失败推到“后续 B”；后续仅 C/D。当前 `M1/` 仍只有 `.gitkeep`，没有预填实施或验收记录。

#### 实际注册、身份与继承链

- 正式入口 `packages/dsh-integration/src/agent-config.ts:105-111` 在 preset 上挂载 GlobalMode、Feature 与 PersonalTools。`global-mode.ts:15-43` 在这一共享作用域注册 Inbox/conversations 和同时含公开 target/text、内部 agent_id/message 的 send_message，并捕获 nativeSend。因而仅修改工具描述或只按名称去掉 send_message 都不能实现需求：前者没有收窄，后者会损害内部通信。设计明确选择主实例注册、子实例保留原生定义，命中了实际落点。
- `agent-config.ts:126-136` 已在真实 Agent 创建后按 session origin 注册主 PA 专属 send_user_message；`index.ts:237-250` 在 agent/created 中恢复历史配置后统一调用 attachAgent。使用这条现有入口处理新建、fork 与恢复，而非建立另一套子 Agent 管理器，职责合理。仅复用模式仍需通过实际 schema 验证，设计已将其写入退出条件。
- `capabilities.ts:59-74` 的 ToolSelection 在 Agent scope 上处理限制层；`product-contracts/src/capabilities.ts:54-59` 已区分 Global 根固定工具与子角色。设计允许必要的选择接线修正，保留当前用户选择和子 Agent 原生通信，避免把根工具的 fixed 集直接继承给后代。
- `product-bridge.ts:13-29` 由真实执行 Agent 追溯 binding，并传递不同的 sessionId/rootSessionId；`packages/personal-assistant/src/global-agent.ts:410-418` 已据此拒绝子 Agent Inbox/conversations 与代表发送，但未同样拒绝普通公开 send_message。在此既有产品入口补公开发送身份检查，与注册收敛形成闭合链，不需要新权限服务。设计限定 Global，不扩大改变 SingleThread。
- 主 PA 的代表发送在 `agent-config.ts:134`、`product-bridge.ts:21` 和 `global-agent.ts:414` 另有边界；设计明确保留。权限由宿主身份与入口保证，不让模型根据自称角色取得产品能力。

#### 深度、Task 与恢复

- R2 核对的锁定依赖深度语义及公开 profile patch 仍适用：`client.ts:15-26` 当前无深度覆盖；目标只新增 subagent maxDepth=2，保留调用方显式 patch，不改并发。普通 spawn/fork 的根 0、一级 1、二级 2、拒绝 3 属于可执行的配置设计，非 DSH 源码补丁。
- `task-execution.ts:41-42,66-67,85-86` 仅对 bindings 中的主 session 记录自动责任并在 pre-step 处理；Task 工具的产品调用沿 root binding 使用产品 Agent ID（`global-agent.ts` 的 task_graph 分支）。当前产品 Task 与内部 child execution 本来不是同一对象。由主 Agent 记录 child ID、用现有控制接续，不需 schema 或硬绑定，符合用户决定。
- `trajectory-runs.test.ts:33-45,105-139` 包含 fixture 嵌套、同 session ID 后续消息与 cold-wake、进程终止后 unknown 等不同事实。设计沿用这些机制但不宣称全自动重跑；真实更正/停止/接续与短问题响应仍另行验收。当前已有 fixture 不能替代本版真实模型结果，本轮未重跑这些测试。

#### Agent Context — Design Review

- **Surface / Consumer**：主 Global/PA 的产品 schema 与系统指导，子 Agent 的内部 schema、按需 Skill、交接消息、Task 状态和结果反馈。主要新增变化是消费者角色收窄，不能只审 Prompt 字句或工具名称。
- **生命周期**：设计从 preset 共享贡献移到主实例注册，并要求创建、fork、恢复后按可信角色重新组装（`:58-70`）；既有历史不重写。历史里曾出现工具调用不重新授予权限，读取或发送入口仍核实身份。普通文件、Memory、fork 历史继承保持，未作新的硬隔离承诺。
- **一致性判断**：`:62,66` 明确要求所有当前主 Agent 专用公开确认、进度、交付与 Inbox 指导不进入 Global 子 Agent，保留适用的安全规则。这项要求应按整个当前组装解释，包括 PersonalTools 和 Feature/动态反馈，不仅 `nano-global-mode` 一段。已有 `personal-security.ts:135` 含 conversations/公开发送指引，`features/task-graphs.ts:19-20,31-40` 含固定会话交付及动态 task-feedback，`features/intelligent-ui.ts:11-15` 含发送 interactive 的指引。它们是实施时必须对齐本设计结果的既有来源；详见可选定位建议 R3-R1。
- **参数与结果**：内部 send_message 继续使用真实父/子 ID，主 Agent 持有产品目标与权限；子 Agent 需要聊天资料时请求父级，再由主 Agent 查询。内部 accepted 与公开 sent 不混淆，最后结果经主 Agent 实际发送。主/子来源识别与限制由现有机制提供，不新增模型猜测身份字段。
- **验证**：`:70,103-107,113` 要求实际 provider schema、当前指导、Skill 消费、工具回执与用户结果；覆盖普通/PA、两层、spawn/fork、恢复及直接受限入口拒绝。同名 send_message 分支有单独检查，工程 seam 与代表性真实旅程分层，不要求全笛卡尔积。
- **证据状态**：以上现状接线为 CONFIRMED 静态事实，目标消费行为为待实施设计；真实模型能否正确协调两项工作、二级交付、停止后原执行者接续、保持安静仍未验证。本轮没有发现需要额外隔离系统或扩大恢复范围才能满足设计的证据。

#### A、delta-spec、验收与回退

- A 的默认 custom_prompt 创建/配置、Skill 安装/发现/禁用路径仍为 R1 已核实路径；本轮没有把旧 PA prompt 自动改写，私人准备继续由主 PA 基于获准来源核对，既有安全规则与外发审核保持。共享 ongoing-work 方法需适配新的主/子分工，但不新建工作账本服务。
- 三份 delta 锚定正确 canonical area：personal-agent 的 MODIFIED 完整保留旧两个 Scenario；global-agent 的 ADDED 描述角色工具边界及恢复；agent-capabilities 的 ADDED 描述默认深度及显式覆盖前提。现有 Task 负责人、状态和数据协议未改变，无需为“无硬绑定”新增 Task 协议 delta。现有 canonical 未被提前覆盖。
- 基线从 R2 到当前包含 perf-666 的其他变更，本轮已核对实际当前入口；未把这些无关产品改动纳入 feat-667 实施范围。原有隔离 Runbook、合成账号与真实模型前置继续适用，无生产写入、部署或迁移要求。
- 无前端变化，采用实际客户端 API 旅程足够，不要求 UI 原型。回退明确区分代码和持久化 custom_prompt；不声称回退代码会重写用户配置。没有引入一次性数据迁移，毋需 deployment-prompt。

### 历史问题闭环

- R1/R2 均无 CRITICAL/WARNING；没有历史阻断 issue。
- R1-R1 的 Author Resolution 已接受区分十分钟背景通知与主人正常来信提前触发；本版仍有两条入口，该证据区分继续适用。
- R2 的“B 独立、A 三文本”结论因新用户决定被本轮完整范围取代；深度语义、公开配置入口及未经真实验证的事实保留。不是沿用旧 Approved 豁免新范围。

### Issues

无。

### Recommendations

- **R3-R1（可选，实施证据定位）**：可在实现记录里给出一份合成后的子 Agent Context 样本，除了 global-mode 的固定段，额外标明 Task feedback、PA 固定指导及 Intelligent UI 指导的实际处理。上述现有位置说明只移动一段 Prompt 可能漏检；设计已要求所有当前指导与可调用能力一致，因此这是取证定位建议，不要求新增 Gate、改 Task 协议或引入隔离系统。

### Author Resolutions

- R3-R1: accepted。实施取证按本设计既有“当前指导与可调用工具一致”要求，覆盖 Task 动态反馈、PA 固定指导与交互 UI 指导，保留合成后的子 Agent Context 样本；不增加产品范围或新 Gate。
- Author 已核对 R3 报告及本次用户决定，无实质异议。受审 spec、design、delta-spec 与骨架在审查后未修改；R3 Approved 有效。报告整理仅将原 R2 Author Resolutions 移回 R2 末尾，保留原文，不改变审查结论。
