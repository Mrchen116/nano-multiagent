# feat-659: Agent Context Engineering — 技术方案

> 对齐: spec.md；原始需求见 user-request.md。

## Changelog

## 现状分析

### 涉及范围

基线 `50e834116e64e9df5e0783b62259764f02b005b4`。`AGENTS.md` 和两个 docs README 是开发入口；`documentation-system.md` 管仓库知识权威与渐进披露；`coding-guidelines.md` 当前主要管注释/docstring；`change-workflow.md` 管生命周期与角色。`testing.md` 限定有回归价值的测试，`llm-integration.md` 提供 Session 日志，但尚未给最终模型 Context 的审查方法。

现有 design-author/reviewer、impl-worker、code-review、verifier、两个 orchestrator 各管设计、实施、独立正确性与一致性。前端已有按实际呈现审查的明确要求，Context 没有对应的通用消费视角。

当前运行路径（取证入口，不另立产品契约）：

| Surface | 真实生产拥有者 | 当前可观察 seam |
|---|---|---|
| System Prompt / 动态 section | `apps/node/src/configuration.ts::runtime` → `packages/dsh-integration/src/agent-config.ts::ConfigurationScopes` → DSH system-prompt assemble；global-mode、features/* 注册 section/context | configuration.preview / session.capabilities 是预览；llm/stream 是适配前；HTTP 请求是序列化后 |
| Skill 发现、过滤、加载 | `packages/dsh-integration/src/capabilities.ts::skillCatalog/apply` + DSH FileSystemSkillProvider；PA `builtin-skills.ts` | 配置 allowlist、目录、skill 工具结果、下一请求正文；文件存在不证明加载 |
| 工具定义 / 结果 | `global-mode.ts`、`features/task-graph-schema.ts`、`features/task-graphs.ts`；`output.render` | 实际 tools schema + 下一请求 tool result；tool-presentation.ts 是 UI，不等同模型输出 |
| Inbox / IM | PA `global-agent.ts::wake/wakeInput/productCall` → `inbox.ts::read/commitRead` → `tool-references.ts` → integration `global-mode.ts` | system wake、工具 read 后持久化消息、多模态 admission 与原始 source |
| Memory | `features/memory-curation.ts`、`knowledge/runtime.ts` | 会话快照、fork、维护读写、compaction 后刷新与实际注入 |
| History / Compaction | `agent-context.ts`、`compaction.ts` + 锁定 dsh-agent-context@0.3.0-rc.5 / DSH 0.2.1-alpha.1 | 原生 notes/history/new_context、有效上下文与重启；停用 bundle 后旧 summary 引擎 |

current 以 `docs/specs/gateway/{agent-capabilities,global-agent,task-graphs,routing-delivery}.md` 为准；只读依赖代码用于理解，不能引入 private import。

### 既有约束

不改 DSH runtime 和产品行为，不新增 Gate、独立 Context reviewer 角色或独立设计文件。设计与实现审查由现有独立角色执行；严重度沿用 CRITICAL/WARNING/SUGGESTION，证据状态与严重度分开。原始请求与私人消息不入 Git。

### 可复用能力

用现有 LLM_PROXY session/raw 日志及 DSH session/tool 事件；用 `llm-attribution.test.ts` 本地 HTTP provider fixture 捕获真实 adapter 序列化请求，用 task-feedback、communication-native、capabilities、native-human-source、PA inbox/global-agent 测试保护现有行为。真实模型代理健康检查通过；实际任务另行验证，不把在线当模型成功。

不建立 Context Snapshot 服务。现有 preview、stream、wire、行为证据各有边界；若实际缺少上游转换后的 wire，记录盲区并使用代理现有 raw 捕获，不靠 preview 推断。

参考于 2026-10-25 核对：Anthropic mcp-builder 与 evaluation、OpenAI skill-creator（本机安装版与官方仓库）、Agent Skills Specification、MCP Tools 2025-06-18、Anthropic effective context engineering。采用发现性、可执行错误、渐进披露与真实任务评测方法，不采用其固定问题数量、协议或运行时要求。来源链接随通用规范保存；本机 skill-creator 的 forward-testing 指导用于试点。

### 相关历史

当前 task_graph spec 已要求动作参数说明和依赖方向示例；Global Inbox spec 已要求隐藏内部回执/分片字段与保持身份来源；默认 context bundle 与同代配置在 agent-capabilities spec。将这些作为具体例证和契约链接，不重复维护产品规则。

## 架构总览

新增唯一方法权威 `docs/development/agent-context-engineering.md`，新增短程序入口 `.claude/skills/agent-context-review/SKILL.md`。原先仅有普通 API/前端审查，之后由同一设计/代码 reviewer 按实际 Context 影响载入相应模式，结果仍回到原报告。

## 关键决策

**原则集中，程序分离。** 通用规范以五组原则覆盖必要性/可获得性、语义/行动、来源/信任/优先级、生命周期/组合、效率/验证；分 surface 说明差异并提供 nano 反例。Skill 只定义两模式执行和输出，详细观察操作只写 llm-integration，不复制产品 current spec。

**条件触发覆盖默认与原实施路径。** 以最终模型信息及其生命周期是否改变判断，不按文件名。Full design-author 只在相关设计中写 Consumer/Lifecycle/Before-After/Interactions/Validation，并落 milestone；design-reviewer 调 Mode A，code-review 调 Mode B，verifier 核一致性及证据。lite 不增加 design Gate，原本适用的实现/code review 仍覆盖 Context；快速开发由既有 code review 接入。

**组合审查优先于孤立文案审查。** 不要求每个变更填写八类 checklist；选择受影响链路及与既有 prompt、技能、来源和持久状态的实际交互。可靠性/权限约束优先宿主派生和代码保证。

**先证明交付，再判断消费。** 区分源码、装配预览、真实 adapter 请求捕获、真实 provider 请求、模型行为/产品效果。采用隔离合成任务与既有日志；不提交原始请求。不承诺每类变更都跑真实模型，对缺少必要证据的结论不放行，对无关状态不制造测试。

## 接口与数据流

修改范围：AGENTS、两个 README、coding-guidelines（一句边界）、documentation-system（一句权威区分）、change-workflow（条件接入）、testing（观察 seam 链接）、llm-integration（可执行观测步骤）；上述七个 change-* Skill 及 design 模板的条件提示；新增通用规范与 Review Skill。必要时无独立 references，按需直达规范相关小节。

Review 输出保留 caller 既有格式：每个 finding 附 location、surface、expected、observed、failure mechanism、impact、recommendation、severity、evidence status 和 locator/limit；code review 保留原 JSON 必需字段，用附加字段承载 Context finding。REFUTED 留候选闭环不作存活 finding；PLAUSIBLE 只陈述机制和缺失条件，不预测模型一定误解。无 finding 返回空发现并说明实际覆盖/未验证边界，不强迫生成独立报告。

## Agent Context 设计

Consumer：本仓 Coding Agent、设计/代码 reviewer、verifier。此处改变的是开发 Agent Skill context，不是 nano runtime。

Lifecycle：AGENTS 路由 → 现有角色按实际影响选择规范/Review Skill → 读取当次设计、diff 与适用运行证据 → 写回原设计/门禁报告 → 后续复验按 delta 复用证据。规范由 development 维护，历史结论留 unit；变更 scope/version 后旧结论必须重新判定有效性。

Before/After：原 code-review 只明确普通 correctness/调用方；增加“影响模型可见内容或生命周期时，按 agent-context-review Implementation 模式核查实际交付，区分接口设计缺陷和未证实模型行为”。纯 CSS 变化仍只走普通 code review。

Interactions：沿用现有独立角色、severity、报告和测试边界；不让新 Skill 自行派 Agent、批准发布、改 runtime、重写 spec 或强制全量真实模型测试。方法相对于 current 产品事实只提供判断标准。

Validation：检查入口链和语义一致性，运行新 Skill 的真实 nano A/B/C 审查试点和不触发反例；由未参与实现的静态 reviewer 使用最终 Skill 复核案例/新 Skill 行为与一致性，复用已有证据。设计阶段只评估方案与验证计划。

## 契约层增量 (delta-spec)

no spec delta：不改变终端产品或 DSH 公开运行行为。长期开发规范在本 unit 实施后归入 development 权威文件。

## 风险与回退

风险是泛化触发、重复规则、证据越级与隐私泄露；通过 scope 条件、单一权威、原报告承载、明确 evidence 层级和脱敏摘要控制。试点缺陷单独记录位置/影响/范围，不在本 unit 自动修产品。可回退新增入口和 Skill 接入，不涉及数据迁移。

## 一次性部署迁移

无。

## Runbook for Reviewer

无本 unit 改动的常驻服务；试点优先复用原生 RuntimeClient 与真实 HTTP adapter fixture。真实 LLM 场景使用隔离 workspace、runtime home/session/身份，必要时按 `scripts/e2e-up.sh --profile daily` 起专属实例并按 e2e-down 停止；不使用生产身份发送消息。

Review 驱动方式：Full 零用户面，不派产品 reviewer；独立静态 reviewer 做新开发方法的案例试运行复核，不声称验收所有 nano 产品行为。试点 A 检查 send_message 或 task_graph，含成功与失败/未知现有状态；B 检查 wake/check/read 来源及注入顺序；C 检查 prompt 与 feature/skill 开关后最终请求。若可复用，补充 memory 或 context 换窗案例。

验收前置：Node/pnpm 锁定依赖，本机 4000 proxy；模型或环境缺失记录具体错误、已验证层级和未覆盖行为。至少完成三类真实代码路径审查；真实模型请求/行为在可用环境执行，不以不可用为静态证据升级的理由。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 规范、接入与方法试运行 | 无 | 无 | 上述 development/AGENTS/Skill 与 unit evidence | [worker] 唯一规范覆盖八类生命周期与组合反例；短 Skill 两模式与完整 evidence finding 输出；七角色及默认直接实施接入、无新增 Gate；[worker] A/B/C 与不触发反例有可复查证据，真实输入观察路径与限制明确，无原始隐私入库；[worker] docs-check、Skill validator、既有相关窄测试及当前本地/远端 CI；[reviewer] 零终端用户面，不适用产品 reviewer，由 verifier 逐项核对上述开发者场景与证据。 |
