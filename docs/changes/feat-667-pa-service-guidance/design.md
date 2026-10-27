# feat-667: PA 服务指导与轻量主动准备 — 技术方案

> 对齐: [spec.md](spec.md)

## Changelog

- 2026-10-27 (M1): 用户明确要求增加一层委派；静态确认当前默认深度为 1，将公开配置改为 2 明确为独立 B 的前置范围，A 的产品改动不扩大。

## 现状分析

### 涉及范围

- `apps/im-server/src/personal-agent-defaults.ts`：首次创建 PA 时写入可编辑 custom_prompt；既有配置不补写。当前指导已有来源身份、持续推进与安静通知约束。
- `packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md`：现有跨轮次工作方法，已有原事项记录、子 Agent ID、更正、等待和取消指引。
- 同级新增 `nano-proactive-care/SKILL.md`：只补获准观察后的核对与私人准备方法。
- `packages/personal-assistant/src/builtin-skills.ts` 安装随包 Skill；配置发现、禁用、用户 Skill 优先级沿用原路径，不改安装器。
- 验证落在既有 IM PA、DSH personal-security 与 Skills 测试入口，以及本 unit 的真实旅程证据；没有客户端改动。

### 既有约束

DSH 只通过集成包公开接口使用；不改权限、上下文继承、执行生命周期、任务 schema 或消息摄取。沿用当前来源控制、披露审核和普通工具权限。#414 原分支不改不合并，不读其迁移 workspace。用户配置与生产数据不动。

### 可复用能力

- 用：Global 工具、原生子 Agent、Inbox、conversations、task_graph、现有文件与 Memory、Heartbeat/schedule、真实发送与披露检查。
- 改：上述默认文案与 ongoing-work 方法；不把所有任务强制转换为 Task 或子 Agent。
- 不用：#414 的 personal-delegations、records/v2、personal_context、personal_attention、执行绑定和文件发布服务。A 不增任何运行时接口。
- 已核实锁定 DSH 0.2.1-alpha.1 的公开 subagent 配置默认 `maxDepth: 1`；本仓 `packages/dsh-integration/src/client.ts` 的 `prepareProfile` 未覆盖它，普通 spawn/fork 工具未另设深度上限。已有 `trajectory-runs.test.ts` 使用公开 profile patch 配置深度。工具继承和实际执行尚待真实能力探针确认；现有 `personal-child-delivery.test.ts` 与 `personal-security.test.ts` 只能说明现有测试覆盖，不能证明真实模型端到端成功。

### 相关历史

feat-658 奠定主人身份/来源和当前服务指导；feat-665/#414 的大型实现未合入，作为拆分来源保留。当前 main 的其他 unit 文档不在本片范围。

## 架构总览

保持原消息 → 主 PA → 既有工具/Skill → 实际结果链路。新增的是服务方法，不增加 PA 旁路执行器、数据库或统一检索层。

默认指导简述“小事直接处理、长事持续负责、重要观察可核对并私人准备、已处理/无新价值保持安静”。复杂方法由两个按需 Skill 承担，避免把整份操作手册常驻主提示词。

## 关键决策

**只改三份产品文本，默认单 M1。** 新 Skill 通过现有目录安装与发现，不增加开关、配置页面或后端字段。测试需要的临时数据和取证脚本只服务验证，不进入产品运行时。

**延续现有执行者，权限与能力不能靠文字扩大。** ongoing-work 补充：可独立处理的长事项才派工，记录实际 ID；更正回原执行者；交接只给相关目标、资料和限制；不整段转发私人历史。主 PA 接住新输入，等待事件，不以轮询代替工作。不宣称 prompt 能保证最小权限或隔离；原生缺口留给 B。

**B 的最小前置明确为增加一层原生委派。** 主 Agent 深度为 0，任务执行者为 1，下级执行者为 2。独立 B 在 `prepareProfile` 的现有公开 profile patch 中配置 `{id: 'subagent', config: {maxDepth: 2}}`；不修改 DSH 源码，不新增工具，不改 `maxActiveSubagents`、工具选择、授权或来源规则。该 profile 同时服务普通与 PA 的 DSH host，因此默认深度对两者生效；不新增 PA 特例。B 必须验证第二层真实创建、执行与结果回传，第三层按深度上限拒绝，并检查代表发送等原有身份限制仍有效。A 的二级旅程在 B 未落地前仍未通过；配置改完也不能代替真实模型验收。

**主动性先落在有用的私人准备。** proactive-care 根据观察原话和后续状态判断具体帮助价值，使用现有 Inbox/消息读取核对责任、时间和是否已处理；读取不全时保留覆盖限制。必要时在既有工作记录留下草稿与来源，避免重复；不要求每条观察建任务、写 Memory 或通知。外发必须沿用真实授权与披露检查，观察到的承诺本身不是外发许可。

**有限验证，不制造能力结论。** 原生能力探针与 A 文案效果分开记。关键能力失败时相应旅程标 blocker/B，M1 不宣称通过、PR 保持 Draft 并交付独立 diff 与失败证据；不在 A 修运行时，也不靠放宽标准转绿。这不阻止审阅 A 的独立文本改动。

## 接口与数据流

没有新增 API、数据结构、配置或存储。

主 PA 从可信来源理解请求/观察，按需加载 ongoing-work 或 proactive-care；读取当前可访问的原消息、既有工作记录与结果；能做的小事直接完成，已交办长事项沿用实际执行者，观察线索仅做有依据的私人准备。新进展或需决策时通过既有真实发送路径交付；无新价值静默。完成、取消与更正回到原事项，不另造执行状态。

### Agent Context

- Consumer：主 PA 消费默认指导与 Skill 描述/正文；普通 Global Agent 可按需使用共用 Skill；子 Agent 只收到当前任务所需交接信息，现有运行时继承语义不变。
- Lifecycle：首次创建存 custom_prompt → 既有 Persona 组装；Skill 由随包安装 → 既有发现/禁用过滤 → 模型选择加载。原配置更新与恢复路径不变；清空文案不回填。升级会刷新随包方法，既有自定义 prompt 和禁用选择保持。
- Before/After：从“关注已交办新消息”扩展到“重要观察可先核对并私人准备”，明确不冒充授权、已处理不催；持续工作强调原执行者和真实结果。没有新的硬性运行时保证。
- Interactions：固定个人安全提示仍负责身份、来源及披露；Task/Memory/Heartbeat 等保持原接口与开关；本片不得引用不存在的 records、personal_context、personal_attention、bind_execution、clear_execution、query_receipt_id 或 attention_id。
- Validation：检查真实模型请求中实际进入的文案、Skill 发现/加载与工具回执；随后核对用户实际结果。对自定义、空 prompt 和禁用 Skill 检查配置/组装与真实消费；仅字符串断言不作为体验验收。

## 契约层增量 (delta-spec)

- Gateway：`specs/gateway/personal-agent.md` 修改现有“默认服务指导复用普通配置和 Skill”，保留原用户选择与持续工作契约；新增轻量私人准备情形。
- IM：创建入口和存储语义不变，no spec delta。

## 风险与回退

文案效果具有模型差异；本次只报告已运行场景与实际限制，不声称完整覆盖或统计提升。main 原生子 Agent 若不支持关键链路，记录具体缺口给 B，不扩大 A。

回退三份产品文本即可撤回随包行为变化；已保存的新 PA custom_prompt 由主人按原入口修改或清空，不做全局重写。无 schema 迁移；#414 的旧数据继续隔离保存。

后续最小范围：B 首先落实已确认的深度 1→2；除此之外仅修证据证明必需的持续执行/更正/单项停止/多级协作与权限边界；C 拆领域方法且不依赖新记忆检索；D 单独完成真实文件交付。旧 memory v2 与 personal_context 暂停，不成为这些片的依赖。

## 一次性部署迁移

无。不部署生产，不接触迁移过的旧 workspace。

## Runbook for Reviewer

在实施 worktree 中执行，先构建受审版本，使用 Node 24 与仓库 Python 环境。验证根目录专用于本片：`mkdir -p /tmp/pa667-review`。不得使用 #414 旧试用数据。完整启动命令 `PATH=/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin:/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --profile daily --wt /tmp/pa667-review`；停止使用相同 PATH 执行 `./scripts/e2e-down.sh --wt /tmp/pa667-review`。端口从该目录 `.e2e-ports.env` 读取，`GET /health` 验 IM 就绪，现有节点状态接口确认隔离节点在线。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM 与节点/DSH | 上述 e2e-down | 上述 e2e-up | IM health + 节点在线 |

**Review 驱动方式**：端到端真栈；本片不改客户端，可使用 Web 客户端实际使用的用户登录、聊天发送/读取及 Agent 配置接口。不得以直接调用 DSH 内部入口代替用户旅程；原生能力探针可补充但不能替代产品验收。

**验收前置**：本机现有 LLM_PROXY 4000 与 daily 模型可用；先做小请求核实，保留 provider payload/工具回执证据，失败则报告外部阻塞。合成测试账号、观察会话、资料和两项独立工作均在隔离 IM/workspace 创建；不需要外部消息、日历或生产账号。观测通知沿用当前十分钟合并节奏，可由主人正常来信引用已积累背景触发读取，不修改产品时间常量。无前端原型。

**验证计划**：
1. 同 runtime/模型/工具配置、新鲜 workspace，用 main 文案与候选各运行小事直答、长事更正、观察承诺准备三个有限对照；保留输入及真实结果，不从单次差异推导提升率。
2. 单独用实际 Agent/模型核实 Skill 读取、允许范围内二级委派及结果返回。至少一次产品旅程使两项工作实际并行：更正 A 回原执行者、等待期间回答短问题、只停 A 而 B 继续交付。每项按输入→工具回执→实际结果给证据，不用提示词要求当成功证明。
3. 观察承诺生成有内容的私人草稿且不对外发送；追加已处理消息后不重复催；无新价值静默；来源不完整时不宣称全覆盖。
4. 检查新 PA 默认指令、已有自定义、清空指令和禁用 Skill 保真；正常工具/固定安全边界仍在。既有测试先窄后扩，文本修改不新增镜像实现的字符串快照测试。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 服务指导与轻量准备 | 无 | 无 | 三份产品文本；相关既有测试；unit 证据与最窄 spec 归并 | [reviewer] spec 全部七个场景具有真实产品结果；小事直接完成，跨事项更正/停止不混淆，等待可响应，观察有用准备且不越权，已处理安静，用户选择保持。 [worker] 三份文本无新协议/隐藏运行时改造；相关测试与构建通过；实际模型输入、Skill/二级委派原生能力与回执、有限基线对照可追溯；固定安全/禁用仍有效。关键未支持项保留 blocker/B、不宣称 M1 完成或 Ready。 |
