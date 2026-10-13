# Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review`，独立于本 unit 的设计与实现作者。
- target: `refactor-593-skill-denylist`，branch `codex/skill-denylist`。
- review_mode: `full`。
- mode_reason: 首次独立 Gate 2；需要完整核对需求、现状、架构、迁移、两端方案、delta 与 milestone。
- validated_at: `11f3ceafc6ffffc22dfe88b4684bab01d94de957`。
- executed_base: `74bfff7f7118ed040f270491691f31f992393793`。
- started_at: `2026-10-13T22:28:58+08:00`（首个留存的本轮时钟采样；初始文档读取已在该采样前开始）。
- completed_at: `2026-10-13T22:33:36+08:00`。
- duration: 至少 `PT4M38S`；未反推或伪造采样前的起始时间。
- 时序: 本轮发生于实现及作者自检之后。`verification.md:14-16` 明确此前没有独立设计、代码或产品门禁。本报告是真实执行的事后首次独立设计审查，不补称事前 Gate 2 已通过，也不把实现/测试通过作为设计审批。
- 现场: 开始与结束读取时 HEAD 均为上述 validated_at，进入时 worktree clean；本 reviewer 只新增本报告，不改设计、canonical spec、代码或配置，不提交。主会话告知的新 main `d07c7578f` 不属于本轮已执行基线；后续同步须另作失效判断。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING**。

禁用名单的产品决定和核心技术方向可成立；受审资料尚不足以完成 Full Gate 2 的契约、两端体验与验收交接。以下问题均需 author 在原设计资料中闭环后复审。

### Coverage 与证据

#### 需求与用户约束

核对 `motivation.md:5-28`、`design.md:5-17` 和 `verification.md:18-24`，并采用派发中交接的已确认用户决定：Workspace/共享全局均按名称禁用；勾选启用、取消保存禁用；未来新名称默认可用；明确禁用在刷新、重启、同名重建后持续有效；接受共享全局新 Skill 对可访问该目录的 Agent 默认可用。旧 allowlist 只保真迁移当时已有候选，离线保留旧模式直到认证迁移。未扩大到工具权限、自进化 F3/F4 政策、审批分类、空回复或生产部署。

主要决定已收口，没有要求把尚不存在的未来名称都禁用，也没有要求新增目录权限或另一套 Agent Loop。迁移候选历史无法恢复的边界已经诚实写入 verification；这不构成需求缺陷。

#### 现状、产品装配与架构判断

从 `README.md`、`SPEC.md`、`docs/README.md` 进入相关 current specs，并同时读取 executed_base 的旧 `gateway/agent-capabilities.md`，区分旧契约与当前分支中已提前归并的目标条目。

核实实际装配链，而非仅判断被引用文件存在：

- `apps/node/src/main.ts:48-55,84-114,155` 装配 runtime、capabilities/preview、连接后的迁移与恢复；Node 通过 integration client 调用原生能力。
- `packages/dsh-integration/src/index.ts:265-273` 与 `capabilities.ts:59-68,99-118` 区分完整设置候选与会话过滤目录，复用原生文件 provider、watch、roots 优先级以及 list/get 的同一名称判断。迁移取得完整候选，无需绕过 Agent scope 或直接从 IM 读取节点目录。
- `apps/im-server/src/control.ts:787-812` 的迁移入口要求 Gateway 身份、owner/node 归属与 profile version，最终复用既有配置 operation；`packages/personal-assistant/src/knowledge.ts:66-74` 发起迁移。未新增独立持久化/重试通道。
- `packages/product-contracts/src/configuration.ts` 继续 canonicalize mode/names；`apps/node/src/configuration.ts` 映射到 runtime selection。复用既有字段和 fingerprint 是合理的维护取舍，避免第二套配置权威。
- `packages/dsh-integration/src/agent-config.ts:75-85` 复用已有的运行中撤销能力边界；`knowledge.ts:38-63` 保留知识来源与通知。选择可用性由发现和禁用名单共同决定，不再由创建事实扩大配置。
- Web 从 `agent-create-page.tsx` / `agent-detail-page.tsx` 进入 `SkillSourceSelector`；原生从 `AgentsView` / `AgentConfigView` 进入 `AgentEditorFields`。两端并非仅测试中存在的组件。预览与 SlashPicker 消费 mode/names；工具 allowlist 仍独立。

职责应保持：Node 负责本地装配/配置；IM 负责认证、版本化配置权威与 operation；integration 负责原生发现、目录和加载过滤；客户端负责呈现启用选择；知识更新通路负责事实/通知。当前方向在这些边界中可兑现需求。复用既有发现与配置 operation 比另建扫描器、enabled 列表、迁移数据库或 Agent Loop 更简单；本轮未发现需要新增机制的架构理由。

#### 两端实际画面与操作观察

本轮先观察实际渲染结果，再对照作者的一句 UI 描述和组件来源。使用主会话准备的同一 validated_at 隔离服务 `http://127.0.0.1:55948`，测试账号由主会话提供，未接触生产配置。

- Web：登录后从 Agents → E2E Agent → Config 进入实际配置页。1280×720 画面中，Access & Model 内的 Skills 标题、43 selected、默认启用提示、Global 31/31 与 Compatibility 12/12、批量动作及独立 Tool Allowlist 可辨认。来源分组和启用色让用户能将“可用 Skill”与工具选择分别理解。
- Web 草稿：取消 `lark-doc` 后，pill 变灰、总数变 42、Global 变 30/31 mixed，批量动作变 Complete group，并出现 Unsaved changes / Save。恢复同一项后回到 No changes、保存禁用。未点击保存，测试用户配置保持不变。新建页也显示同一提示及默认全选候选；随后 Cancel，未创建 Agent。
- 原生：观察主会话安装的真实 `NanoIM.app`，Simulator `8BD1A09B-7349-44DB-85D3-24B764407C41`。从已登录的 E2E Agent Configuration 画面，使用 AX 滚动容器的 `Scroll Down` 进入 Skills，展开 Skills → Global。画面中先解释新技能默认启用，再按来源展开名称、路径、描述与启用开关；保存维持禁用。未改开关或保存。长路径使每行较高是继承界面的现状，不因本次选择语义改动要求全页重设计。

这些观察支持局部方案能够被理解，不代表真实后端保存/重开、重启、同名重建、离线迁移或全部平台验收通过。尚未观察 Web 窄宽度、原生取消/保存/冲突/缺失候选状态；没有旧版画面可供直接视觉前后比较，旧布局继承仅通过本次 source diff 核对。本轮 tool 截图与 AX 结果存在于审查会话，unit 尚无可复查的画面资产或其设计投影，见 R1-W2。

#### Delta 与 milestone

`rg --files docs/changes/refactor-593-skill-denylist` 仅列出 motivation/design/verification。没有 unit delta、prototype、milestone 骨架或 reviewer runbook。`design.md:13` 有唯一 M1，但退出标准只列 Web 保存重开及部分 runtime/migration 结果，未覆盖本次真实受影响的 iOS 与所有消费者。作者既有测试记录有价值，本轮未重跑；它们无法代替缺失的设计退出条件或真实产品验收。

### 历史问题闭环

无历史 Round，本轮没有可关闭的旧 issue。后续 Author Resolutions 应追加在本轮之后，保留上述原结论。

### Issues

#### R1-W1 — 缺少可审查 delta，current 已提前被目标契约替换

- 位置：`design.md:5-13`；unit 缺少 `specs/`；`docs/specs/gateway/agent-capabilities.md:398-447`、`docs/specs/im/agents-nodes.md:770-775`。
- 证据：与 executed_base 比较，Gateway 中“PA Agent 配置区分默认发现与显式空 Skill 选择”的完整 5 个 Scenario 已被新 Requirement 替换，知识更新 Requirement 也被直接改写；IM 新条目直接追加。unit 没有 ADDED/MODIFIED/REMOVED 投影，也没有说明旧场景哪些被新语义替代、哪些保留为离线旧模式边界。尤其旧空配置、显式清空、蒸馏不可用与运行中回复边界不能仅靠删除旧 Requirement 推断。
- 后果：下游 verifier 无法按受审 delta 确认行为变化边界，canonical 已像 current 一样宣告未完成门禁的目标行为，容易漏掉旧模式/未改变的消费者保证。
- 闭环要求：按 `docs/specs/CONTRIBUTING.md` 为 Gateway/IM 正确 canonical target 补齐 delta，完整保留未改变 Scenario，并明确旧场景的保留、替代或删除依据；在门禁完成前恢复 current/active 的权威分工。不得仅以现有 canonical diff 冒充已审 delta。

#### R1-W2 — 两端体验决定尚未形成可交接的设计契约

- 位置：`design.md:8,17`；unit 缺 prototype/画面证据及 must-match 表。
- 证据：设计仅写保留 Web 分组/勾选/批量交互、iOS 同一勾选语义。没有链接基线或实际渲染证据，没有定义启用提示、单项/分组数量与状态、缺失禁用名称、能力不可用、预览与保存反馈的内容关系；没有将各端 must-match/may-adapt/out-of-scope 与 viewport、真实入口、worker 对照和 reviewer 用户结果对应。本轮两端观察支持正常状态方向，但不能替 author 对未定义状态作决定。
- 后果：实施/产品 reviewer 可以各自把“有开关且 payload 正确”当作完成；暂时缺失名称或保存结果等状态是否可读会依赖实现者临时决定，iOS 尤其没有自己的交接依据。
- 闭环要求：补与本次局部改动相称的原型/状态对照及代表性渲染证据；可利用已有真实客户端画面，诚实标注其为实现后观察，不需重做全页。明确两端沿用/改变的关系、关键状态和 must-match 约束，并把每项映射到 M1 的实现对照与产品结果。未观察状态标明缺口，不用“原生适配”或已通过单测代填。

#### R1-W3 — 验收运行入口与 M1 完整退出条件缺失

- 位置：`design.md:11-17`；`verification.md:5-16`。
- 证据：没有 Runbook for Reviewer 的隔离启停/构建/健康检查、真实 Web/iOS 入口与测试资源说明；本轮所用测试栈和 Simulator 均靠主会话临时补充，未存在于受审资料。M1 范围/退出标准未写 iOS，也没有将 preview、SlashPicker、显式调用、候选缺失后保留禁用、迁移/重试、离线旧模式等需求投影为可观察的退出标准。unit 无 milestone 骨架。
- 后果：下一位产品 reviewer 无法仅凭 unit 安全复现验收环境与必验状态；M1 可在 Web happy path 和单测通过后被判完成，遗漏原生/恢复与消费者一致性。
- 闭环要求：补简短可执行 runbook，写明账号/凭据取得方式、临时端口/数据/workspace/node identity、原生构建安装与入口、测试 Skill/旧模式 fixture、健康检查及清理 owner；无外部资源写无。完善唯一 M1 的两端与上述关键结果退出标准，增加对应骨架即可，不要求机械拆多个 milestone 或预填 tasks/progress。可以引用既有隔离脚本及有效测试结果，避免重复全量验证。

### Recommendations

- R1-R1（可选）：Web Access & Model 仍显示 “Keep allowlists minimal.”，Skills 已改为禁用名单且下方另有 Tool Allowlist。后续可将说明限定到工具，减少两种选择语义并列时的术语负担；本轮实际画面有明确默认启用提示，未见它阻止用户完成局部选择，因此不另列阻断。

### 复审范围建议

author 补齐以上材料后，若仅将既有用户决定、实际画面和原有实现边界明确化，可按 closure 核实 R1-W1/W2/W3；若补材料时改变迁移/运行中生效语义、公共接口、跨端流程或 milestone 实质范围，则按实际 delta 扩大审查。不要求为本轮文件缺口重新跑已有全量测试。

### Author Resolutions after Round 1

- R1-W1：新增 Gateway/IM delta，显式保留离线旧模式、蒸馏禁用和 safe boundary；修正 IM 旧首次编辑/重连条目与新契约冲突。首版提前改动的 current 已恢复，待最终核对后归并。
- R1-W2：design 增补两端内容关系与 must-match 投影，prototype 为明确标注的实现后局部状态对照；原生实际画面存 evidence/native-design.png。原型与产品证据不混用。
- R1-W3：补唯一 M1 骨架及两轨退出标准、两端入口、隔离资源/启停/重启/清理 runbook。

## Round 2

### Metadata

- reviewer: `/root/design_review`，沿用 Round 1 独立 reviewer；未参与设计/实现修订。
- target: `refactor-593-skill-denylist`，branch `codex/skill-denylist`。
- review_mode: `closure`。
- mode_reason: R1-W1/W2/W3 的材料补齐与局部消歧；用户决定、核心字段、发现/过滤职责及单一 M1 未改变。对补明的迁移失败隔离/pending 恢复边界作局部架构核对，不扩大为整套实现审查。
- started_at: `2026-10-13T22:44:34+08:00`。
- completed_at: `2026-10-13T22:47:18+08:00`。
- duration: `PT2M44S`。
- validated_at: `42a02a49ae7f4c52221616d600286bb30aac4cb7`。
- executed_base: `d07c7578f210ee7fe830e2e7de4407209e7c75fc`。
- fix_delta: `11f3ceafc..42a02a49ae7f4c52221616d600286bb30aac4cb7`，核对时扣除已合入 main 的轨迹导航/发布策略变化。
- retained_from: `Round 1` 的用户约束、产品组装入口、原生发现/过滤与配置 operation 责任判断、真实 Web 正常/草稿操作及原生 Skills/Global 观察。核实两个实际 Skills 组件相对 Round 1 无变化；新 main 未改该局部 UI。新基线的 `docs/specs/` 与 HEAD 完全一致，没有保留首版提前归并的禁用名单契约。
- 现场: 开始与结束 HEAD 均为 validated_at，worktree clean；本 reviewer 只向本报告追加本轮，不提交，不改生产或测试用户配置。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

R1-W1、R1-W2、R1-W3 全部 closed。通过范围为设计方案及交接材料，不表示代码/产品门禁已通过，也不补称事前 Gate 2 已执行。

### 历史问题闭环与本轮证据

#### R1-W1 — closed

- Author Resolution：补 Gateway/IM delta、保留离线旧模式/蒸馏禁用/安全边界，恢复 current。
- 独立核对：`specs/gateway/agent-capabilities.md` 正确镜像 canonical target；新禁用名单 Requirement 覆盖未来新名称、同名禁用、scope/precedence、真实候选迁移、创建事实、蒸馏及离线旧模式。旧空名单从“所有未来名称都不可用”改为“当时取消的名称持续禁用，后续新名称可用”，是已确认变化；旧 Requirement 的移除有明确替代。知识更新的 MODIFIED 条目完整保留前台 terminal、重连去重、来源/通知、prompt 继承与 memory/反思周期等未改场景。prompt 缓存前缀 Requirement 保留两个既有场景，并将自动配置写回改为原生发现语义。
- `specs/im/agents-nodes.md` 显式替代旧模式 API Requirement，保留保存后 SlashPicker 更新保证，将只读 mirror 与认证迁移分开。`git diff --exit-code executed_base HEAD -- docs/specs` 成功，证明目标尚未提前写入 current，同时保留最新 main 的 current 更新。
- 结论：契约变化与旧模式边界可供 verifier 对账，R1 所指缺口已闭环。最终归并仍需独立 corrected-delta 核对实际实现。

#### R1-W2 — closed

- Author Resolution：补两端内容关系、must-match 投影、局部原型及真实原生证据，明确实现后时序。
- 独立核对：`design.md` 的前端原型与体验契约区明确 Web 来源分组/pill/计数/混合态/页级草稿反馈，以及 iOS 折叠来源/名称路径说明/开关/顶部 Save；may-adapt 有各端既有呈现依据，未用“平台适配”替代未作决定。缺失禁用名称、目录失败、预览/候选与保存反馈均有 must-match 结果和 M1 双轨投影。
- 本轮逐张查看 `evidence/prototype-selected.png`、`prototype-mobile.png` 和 `native-design.png`。取消态的弱化项、来源计数、未保存提示与 Save 可对应；390px 状态中新的 meeting-notes 保持启用，暂缺 daily-journal-write 的已保存禁用说明可读。原生真实画面与 Round 1 观察一致，默认启用提示在来源与开关之前。局部模拟与真实原生画面标注不同，不混称原生持久化验收。
- 独立以本地 Chrome 新标签页打开 `prototype.html`，操作 daily-journal-write 取消 → 模拟保存 → 候选暂缺 → 复制新名称 → 重开。观察到 2→1 已启用、Workspace 0/1、未保存状态与 Save 联动；后续 meeting-notes 默认启用、暂缺名称的禁用记录保留、重开无更改。模拟共用状态用于两端语义对照，不当作跨客户端同步能力。已关闭本轮创建的标签页，未保存真实 Agent 配置。
- 保留 Round 1 对实际 Web/原生入口的观察；原型中的 checkbox 仅表意，真实原生仍以已观察的系统开关为依据。缺少真实保存/冲突/缺失候选产品观察被诚实保留给产品门禁，不再是未定义设计。
- 结论：本次局部语义变更已有足够的内容关系与状态方案指导下游，R1-W2 closed；无需扩大为全页重设计。

#### R1-W3 — closed

- Author Resolution：补 M1 骨架、两端和消费者退出结果、隔离 runbook 与资源责任。
- 独立核对：`M1-selection/.gitkeep` 存在；`design.md` M1 明确覆盖 Web/iOS、scope、新名称/同名禁用、preview/SlashPicker/显式调用、工具/进化不变，以及 native Session、迁移/CAS/pending/失败隔离、忙碌收紧与 idle 放宽。没有机械拆新 milestone 或补造旧实施过程。
- Runbook 给出专属 checkout、已有 e2e-up/down、动态端口/health、测试身份、两类隔离 Skill roots、单独 Node 重启保留数据库、原生 build root/UDID/入口及 AX 滚动办法；清理由主 Agent 负责，外部账号/真机资源为无。核对 `scripts/e2e-up.sh` 的 `--wt`、health 和 `.e2e-ports.env` 输出、`e2e-down.sh` 以及 `src/IM/ios/scripts/build.sh` 的 build-root 支持，均有实际运行入口。专用栈/原生 app 已在 Round 1 实际使用，不是尚未提供的验收资源。
- 结论：后续 reviewer 能按 unit 找到环境与必验结果；内部协议边界交 verifier，用户旅程交产品 reviewer，R1-W3 closed。

### 局部恢复边界与架构 retained 判断

补明的迁移恢复沿用原目标：失败只保留该 Agent 的旧选择并报告，不能拥有整个 runtime/channel 的恢复成败；pending operation 恢复后以已提交 canonical profile 继续迁移，不能把旧 operation 的成功误报为转换完成。核对 `packages/personal-assistant/src/knowledge.ts` 的按 Agent 隔离及后续重连重试说明、`apps/im-server/src/control.ts` 恢复后重读 profile 的已有 serialized/config operation 接线，以及对应窄回归新增位置。没有第二套迁移存储、配置权威或发现实现；责任与 Round 1 的架构判断一致。

这是设计闭环与接线可行性检查，不宣称上述修复的代码正确性门禁通过；本轮未重跑全量测试，也未等待或替代产品 gate。

### Issues / Recommendations

无新增 CRITICAL/WARNING。R1-R1 的工具 allowlist 说明建议仍为可选，不影响明确的 Skills 默认启用提示或本轮通过结论。

### User scope correction during delivery

用户随后明确：“这玩意哪用前端啊，内部机制调整啊”“赶紧做了逻辑修改就行了啊”。据用户优先指令，停止额外原型、体验契约与产品界面验收；刚新增的演示文件已移除，design精简为内部机制和必要配置语义。Round 1的观察和结论作为实际历史保留；R1-W2及R1-W3中的额外UI设计/验收前置不再是本轮交付要求。delta及内部逻辑退出条件仍须独立核对。

## Round 3

### Metadata

- reviewer: `/root/design_review`，同一独立 reviewer。
- target: `refactor-593-skill-denylist`；review_mode: `delta`。
- mode_reason: 用户在 Round 2 记录完成、交棒前明确取消额外 UI 设计/验收要求；本轮仅核对这一有界范围缩减及其对内部契约/退出条件的影响，保留已发生的 Round 2 历史，不伪造原型要求仍通过。
- started_at: `2026-10-13T22:49:57+08:00`；completed_at: `2026-10-13T22:51:11+08:00`；duration: `PT74S`。
- validated_at: `3c09e7f7ea238e8a780a4eac1a6b6e461b38e142`；executed_base: `d07c7578f210ee7fe830e2e7de4407209e7c75fc`。
- retained_from: `Round 2` 的内部发现/禁用/迁移、正确 canonical target 与配置消费者语义判断；核实 `42a02a49a..3c09e7f7e` 没有源码、测试、delta 变化，current specs 仍与 executed_base 一致。

### Verdict 与问题闭环

**Approved — 0 CRITICAL / 0 WARNING**，限于用户要求的内部机制及必要配置字段语义。

- **R1-W1 closed，retained**：Gateway/IM delta 仍在，旧模式/空名单、真实候选迁移、蒸馏、缓存前缀和消费者一致性均有受审表达；current 未提前归并。精简 design 的“契约增量”仍解释旧场景替代与最终归并时点。
- **R1-W2 no longer applicable**：根据上述用户原话，额外原型、平台体验契约及界面验收已被明确取消。此前真实观察保留为历史；被移除的演示资产不再充当当前交付依据。配置勾选/取消项、暂缺名称保留、两端 mode/names 适配的逻辑语义仍在设计与 delta 中，不因此取消。
- **R1-W3 部分 closed、部分 no longer applicable**：平台 UX/额外产品验收前置随用户要求取消；内部逻辑部分已在当前 M1 列明原生 Session 新文件加载、过滤一致性、重启/同名禁用、default/allowlist/空选择迁移、CAS/镜像、pending 继续、失败隔离以及工具/进化策略不变。M1 骨架保留。精简运行边界继续要求专属 worktree 隔离，并明确主 Agent 起停/清理责任；没有为内部回归增加 UI 环境义务。

### 范围与证据限度

独立阅读 `3c09e7f7e` 的精简设计并核对文件差异。原生 provider/watcher/list/get 和既有 config operation/CAS 继续承担原职责；迁移失败保留旧模式并不影响 runtime/其他 Agent、pending 恢复后继续转换，仍属于原恢复目标。没有因删演示而遗漏内部逻辑决定或新增机制。

本轮没有继续操作浏览器/Simulator、没有等待产品 gate、没有重复全量测试。代码正确性与内部场景回归仍由独立静态审查/verification 判断；设计通过不冒充这些门禁或生产部署。无新增 findings；R1-R1 的界面措辞建议同样不再构成本次范围要求。
