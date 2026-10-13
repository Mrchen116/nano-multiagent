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
