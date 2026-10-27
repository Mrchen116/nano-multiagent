# Design Review — feat-659 Agent Context Engineering

## Round 1

### Metadata

- reviewer: `/root/design_review`，独立于首文档与设计作者；未参与受审产物编写。
- target: `docs/changes/feat-659-agent-context-engineering/` 的 `spec.md`、`user-request.md`、`design.md` 与 `M1-context-engineering/.gitkeep`。
- baseline: `main@8e4054197908a1a433f748525c9650a831a950b6`；design 与 M1 骨架为未提交产物。
- review_mode: `full`
- mode_reason: R1 首次独立审查，无前轮证据可继承；覆盖全部需求、设计决定、运行路径、delta 与 milestone。
- started_at: 2026-10-25T20:00:42+08:00
- completed_at: 2026-10-25T20:03:28+08:00
- duration: 166 seconds（记录时间区间，不含前置入口读取）。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案能在现有开发流程和运行接线中实施。审查通过的是设计及其验证计划；不表示新增规范/Skill 已实现，也不表示三个试点或真实模型行为已经验收。未执行产品运行、模型请求、部署或生产消息发送。

### Coverage 与证据

**需求与开发者消费链路。** 对照 `user-request.md` 的八类 Surface、完整生命周期、组合一致性、两种 Review 模式、七个 change-* 接入点和三个真实 nano 案例，`design.md` 的关键决策、接口与数据流、Agent Context 设计及 M1 退出标准均有承接。五组原则将必要性/可获得性、语义/行动、来源/信任/优先级、生命周期/组合、效率/验证集中维护；按实际影响选择链路，纯 CSS 等反例不触发完整 Context Review。开发 Agent 是本 unit 的直接消费者，设计已说明其发现、加载、报告归属与后续证据失效路径，不把新文件存在当成使用成功。

**当前流程与职责。** 已读取七个现有角色的 SKILL.md，并核对 `docs/development/change-workflow.md` 的实施方式、独立门禁和角色边界。默认 simple 路径确实由主 Agent 直接实施；原 orchestrator 的 worker 仅条件派发。因此同时接入两个 orchestrator 与 impl-worker 是必要覆盖。设计/代码 reviewer 调用新 Skill 的相应模式，verifier 核实现与设计及 evidence 一致性；结果留原报告，未新增审批 Gate 或强制 Context 专职 Agent。Full 零终端用户面采用 verifier + code review，符合当前 workflow；独立静态审查者承担本次方法试运行复核，不与产品体验 reviewer 混淆。现有 code-review 的 JSON 必需字段与 CONFIRMED/PLAUSIBLE 状态可保留，附加 Context 字段不需要替换既有格式；REFUTED 不进入存活问题列表，符合当前候选闭环。

**实际生产入口与证据 seam。** 独立追读了以下拥有者，未仅据文件名判断：

- `apps/node/src/configuration.ts::runtime` 生成 AgentConfiguration；`packages/dsh-integration/src/agent-config.ts::attach/attachAgent/setConfiguration` 安装 GlobalMode、Feature、Persona 与 Skills，并在 `system-prompt/assemble` 过滤禁用 section/context。`capabilities.ts::ToolSelection` 及 `apply/skillCatalog` 使用实际原生工具限制与 FileSystemSkillProvider。配置预览与目录存在不等于下一次请求正文，设计对此区分正确。
- `packages/dsh-integration/src/global-mode.ts` 注册真实 inbox/send_message 工具及来源规则；Inbox read 经附件 admission 后返回实际 content，并调用 `inbox.prepare`。`packages/personal-assistant/src/global-agent.ts` 生成不含新消息正文的系统 wake，读取路径进入 `inbox.ts::read`，持久事件经 `commitRead` 确认消费；工具引用投影由 PA store 的 toolReferences 承担。B 试点有可追踪的 wake → check/read → 模型上下文链路，且可比较通知、真人消息与授权。
- `features/task-graphs.ts` 的工具定义与 `output.render` 输出实际 JSON，并通过动态 context 提醒反馈义务；`task-graph-schema.ts` 已含 action 前提、宿主真实 caller 和依赖方向例子。A 试点可对比实际 schema/result 与状态语义，而非 Web 工具卡片。
- `features/memory-curation.ts` 在 system-prompt assemble 注入快照，按 compaction 序列刷新并继承 fork；`knowledge/runtime.ts` 区分原生 context engine 与 summary 后 used skills 恢复。`agent-context.ts` 默认选择 bundle，`compaction.ts` 优先已有原生 engine，否则退回 summary。依赖 manifest 的 DSH 版本与设计所述一致；不需要新增运行时机制来建立规范。

上述入口与 `docs/specs/gateway/global-agent.md` 的唤醒/授权/持久摄取、task-graphs 的当前工具职责，以及 agent-capabilities 的配置/发现职责相容。设计的调查基线 `50e834116...` 到当前 HEAD 仅新增本 unit 需求文档提交 `8e4054197`，所核实现与流程无相关漂移。

**验证计划的可行性与边界。** 已完整读取 `packages/dsh-integration/tests/llm-attribution.test.ts`：它通过 RuntimeClient 启动真实锁定 DSH，使用本地 HTTP server 捕获 adapter 发出的 body，并核对 system、tools、messages 与父子 session headers；模型回复由 fixture 生成。因此它能作为序列化请求证据和试点复用入口，不能证明真实模型选择、理解或后续行动。`docs/development/llm-integration.md` 现有 session/raw 入口及 `src/llm-attribution.ts` 的请求归属支持后续真实联调；只读查看 LLM_PROXY handlers 确认存在转换后的 upstream_request_obj 捕获接线，但本轮未读取私人日志，也未证明某次任务的 provider 请求已取得。设计明确区分 preview、adapter 捕获、provider 请求与行为，环境缺失时记录具体缺口，符合原需求；实际实施必须按所用协议确认代理入口与上游转换后的请求层级。

A/B/C 有不同 Surface 与具体检查对象，非触发反例有明确预期；memory/换窗仅在可复用时追加，未把可选场景变成额外 Gate。真实试点使用隔离 workspace、home/session/身份，必要时走已有 daily E2E，结束清理；不动生产身份。现有 `scripts/docs-check`、本机 Skill `quick_validate.py` 与既有窄测试可执行相应检查；validator 仅证明格式，真实方法效果由实际审查及独立复核承担。此分工符合 `testing.md` 的长期测试准入，避免逐句静态文本断言。本轮为设计审查，未重复运行现有测试或把测试源码视作通过结果。

**方法来源与架构判断。** 核对 [Agent Skills Specification](https://agentskills.io/specification)、[MCP Tools 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)、[Anthropic mcp-builder](https://github.com/anthropics/skills/blob/main/skills/mcp-builder/SKILL.md) 和 [Context Engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) 的官方入口；本机 `/Users/czj/.codex/skills/.system/skill-creator/SKILL.md` 也确有渐进披露、真实行为验证与独立 forward-testing 指导。设计采取其方法而不引入 MCP 协议或固定评测数量，范围合理。规范放 development，程序放 Skill，观察步骤放 llm-integration，具体产品语义回链 current specs，符合 `documentation-system.md` 的权威分工。复用现有 runtime hooks、事件和代理日志比新增 Snapshot 平台更符合本任务，未发现应由产品运行时承担却转嫁给模型的新增职责。

**delta、milestone 与边界。** `no spec delta` 合理：本次只改变开发规范与 Coding Agent 程序，不改变终端用户行为、产品权限或 DSH API。单 M1 是完整可交付的纵向范围，无并行写冲突；骨架仅 `.gitkeep`，未提前制造执行记录。长期规范/索引归并、完整证据字段、七角色接入、试点与质量门禁都有退出标准。无需前端原型或部署迁移；回退只撤入口和方法接入，不涉及数据迁移。

### 历史问题闭环

R1，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1（可选）**：在最终独立试运行中，将一个小型设计输入明确交给新 Skill 的 Design Review 模式，再将一个真实代码/请求输入交给 Implementation Review 模式，并记录各自实际输出。现有 A/B/C 偏重当前运行实现，加入这一轻量配对能更直接证明两模式的输入和证据边界被正确消费；不需要新增 Agent、Gate、独立报告或永久测试。设计现有“两模式 + 独立试运行复核”已足以指导实施，本建议不阻断。

### Author Resolutions

- R1-R1: accepted。试运行分别给出 Design 与 Implementation 输入，记录两模式的证据边界；属于既有两模式验证范围的具体化，不改变设计、milestone 或 Gate。其余覆盖与 Approved 结论无异议。
