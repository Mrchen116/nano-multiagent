# feat-667: PA 服务指导与轻量主动准备（A+B）— 技术方案

> 对齐: [spec.md](spec.md)。后续用户确认 A+B 合并；本版本取代此前 A 仅三份文本、B 后续独立交付的约束。

## Changelog

## 现状分析

基于 main `9151dcefa` 核对。这里只记录本次决定需要的现状，不把 #414 的新增机制当作 main 已有行为。

- `apps/im-server/src/personal-agent-defaults.ts` 在首次创建 PA 时写入可编辑 custom_prompt；既有实例不补写。`nano-ongoing-work` 已记录持续事项、执行者 ID、更正、等待与取消；新增 `nano-proactive-care` 可由既有随包 Skill 安装与发现机制加载。
- DSH 锁定版本的公开 subagent 配置默认 `maxDepth: 1`；`packages/dsh-integration/src/client.ts` 的 `prepareProfile` 尚未覆盖它。原生后台执行、同 ID 发消息/接续、下级执行及结果回传机制已有；`trajectory-runs.test.ts` 已使用公开 profile patch 验证嵌套与冷恢复。
- `agent-config.ts` 在 preset 挂载 GlobalMode。`global-mode.ts` 同时注册 Inbox、conversations 与包含公开/内部两种参数的 send_message；子 Agent 也能看到。`global-agent.ts` 调用边界拒绝子 Agent 的 Inbox/conversations，却未统一禁止其公开 send_message。工具描述中的 root-only 不是注册限制。
- `send_user_message` 已由 `attachAgent` 只向主 PA 注册，ProductBridge 与产品入口还有身份检查；保持而非重建。原生 `send_message(agent_id, message)` 负责内部通信，不能随公开发送一起删除。
- Task 已持久保存负责人及状态；现有机制支持会话持久化、同 ID 冷恢复和主 Agent 责任恢复，不承诺所有中断执行自动重跑。当前无需新增执行绑定字段。
- 相关入口：current `gateway/personal-agent.md`、`global-agent.md`、`agent-capabilities.md` 与 `task-graphs.md`。#414 代码和旧 workspace 仅保留为基线，不合并、不迁移、不读取旧试用数据。

## 架构与范围

继续使用消息 → 主 Agent → 原生子 Agent/已有工具与 Skill → 主 Agent 交付的链路。单 M1 一并交付 A 的三份产品文本和 B 的最小配置/注册修正；没有新的 Agent loop、数据库、调度器或执行管理器，没有客户端改动。

| 范围 | 变更落点 |
|---|---|
| A 默认服务与方法 | `personal-agent-defaults.ts`、`nano-ongoing-work/SKILL.md`、新增 `nano-proactive-care/SKILL.md` |
| B 委派深度 | integration `client.ts` 的公开 profile patch |
| B 主/子工具与指导 | integration `global-mode.ts`、`agent-config.ts` 的注册与提示作用域；PA `global-agent.ts` 的既有产品入口身份检查；必要的既有工具选择接线 |
| 验证与契约 | 相关既有测试、unit 真实旅程证据，以及本 unit 下 gateway delta-spec |

DSH 只经 integration 公开接口接入，不 fork/patch/private import；不改变并发数、Task schema、来源授权、消息摄取或现有恢复生命周期。普通 shell/文件工具、Skills 继承与其既有权限继续使用，不搬入 #414 的 personal-delegations 白名单，也不新增按事项沙箱。

## 关键决策

### A：服务指导与轻量私人准备

默认指导简述“小事直接处理、长事持续负责、重要观察可核对并私人准备、已处理/无新价值保持安静”；复杂方法按需加载两个 Skill，不将手册全部常驻。

ongoing-work 复用既有工作记录与 Task：记录实际执行者 ID，长事项使用可续跑的原生子 Agent；更正传给原执行者，主 PA 接住新输入。用户要求停止时，主 PA 根据记录中断对应执行者并核对状态；用户明确接续时，由主 PA 联系原执行者。Task 的负责人仍是主 Agent，不新增 bind_execution/child_id 协议。晚结果不是恢复授权；需要跟进下级时通过原执行者及现有管理工具协调，不声称暂停 Task 会自动硬停止整棵执行树。

proactive-care 由主 PA 使用获准 Inbox/conversations 核对原话、责任和后续状态，在私人范围准备实际草稿；读取不全则说明覆盖限制。已处理或无新价值不重复催办，不把观察到的承诺当成外发许可。暂不引入独立观察者角色，也不向子 Agent 开放会话查询例外。

默认值只用于新 PA；已有自定义/清空和 Skill 禁用保持。沿用安装器、同名用户 Skill 优先级与现有配置入口，不新增服务模式配置。

### B：原生委派深度增加一层

在 `prepareProfile` 的既有公开 patch 中设置 `{id: 'subagent', config: {maxDepth: 2}}`。主 Agent 深度 0、一级执行者 1、下级执行者 2；普通 spawn/fork 不得继续创建深度 3。普通与 PA 的 host 共用此默认值，不新增 PA 特例，不增加 `maxActiveSubagents`，保留调用方既有显式 profile patch 语义。

这是配置变更；已有执行、Skill 消费、后台响应和同 ID 恢复不重写。二级创建成功仍不等于真实任务交付，需验证实际执行与逐级回传。

### B：产品通信与读取只提供给主 Agent

| 能力 | 普通 Global 主 Agent | 主 PA | 一级/二级子 Agent |
|---|---|---|---|
| inbox、conversations | 按现有选择与权限 | 按现有选择与来源权限 | 不注册 |
| send_message 的 target/text 公开发送分支 | 保持 | 保持 | 不注册此分支 |
| send_user_message | 不提供 | 保持原有主 PA 专属 | 不注册 |
| send_message 的 agent_id/message 内部通信 | 原生规则 | 原生规则 | 保留原生规则 |

使用宿主已有 Agent/session origin 与主绑定判断角色，不能由模型文本、自称角色或工具参数提升权限。将 Global 产品工具和主 Agent 专用提示从所有后代共享的 preset 注册位置收敛到主实例作用域，复用 `attachAgent` 现有主 PA 注册模式；普通子 Agent 保留 DSH 原生内部 send_message 的定义及执行，不挂载合并后的公开 schema。实现时从实际模型请求核实 native spawn、fork 和恢复路径没有继承根工具或误删内部工具。

沿现有产品入口检查补齐 Global 子 Agent 公开发送拒绝；保留已有 Inbox/conversations 与代表发送检查，避免恢复旧上下文或直接调用绕过注册边界。无需新建权限服务。非 Global 的产品通信行为不在本次扩大修改范围。

同步调整主 Agent 专属的 Inbox 消费、面向用户确认/进度/交付提示，使其只进入主 Agent 的当前组装；子 Agent 只按内部任务向父级回传。保留实际适用的来源、授权及个人安全约束。既有历史不重写，恢复后重新组装当前工具和指导；旧历史内容不恢复工具权限。

## Agent Context 与数据流

- **Consumer**：主 PA 消费默认 Persona、两份按需 Skill 与产品工具；普通 Global 主 Agent 保持自身指导并可消费 ongoing-work；所有 Global 后代消费内部工具与实际可用的 Skill，不注入要求其对外回复/消费 Inbox 的主 Agent 指令。
- **Lifecycle**：首次创建保存 custom_prompt → Persona 组装；随包安装 → Skill 发现/选择/禁用 → 正文加载。角色由宿主建立，新建、fork、同 ID 恢复均按当前角色提供工具；配置更新不补回清空值或禁用 Skill。文件、Memory 与 fork 历史继承机制保持，不把最小交接建议宣传为硬隔离。
- **Before/After**：子 Agent 之前看到 send_message 的 target/text 与 agent_id/message 两分支、Inbox/conversations 及主 Agent 发言指导；之后只看到内部通信分支与适用指导。主 PA 则增加有价值的私人准备方法。没有新增观察者工具或授权来源。
- **Interactions**：Task 状态、停止与显式恢复语义仍以现有系统为准；PA 根据当前状态协调执行者。固定安全与披露审核继续适用，内部 accepted 回执不等于外部 sent。没有 records、personal_context、personal_attention、query_receipt_id 等新协议。
- **Validation**：检查最终 provider request 的实际 schema、系统指导、Skill 描述/正文和工具回执，再核对真实用户结果。覆盖普通 Global/PA、主/一级/二级、spawn/fork、恢复、自定义/空 prompt/禁用 Skill；不同维度用最窄工程测试验证，不机械执行完整笛卡尔积或全模型评测。

## 契约层增量 (delta-spec)

- `gateway/personal-agent.md`：默认服务、持续工作、轻量私人准备，保留用户选择。
- `gateway/global-agent.md`：主 Agent 独占产品聊天工具，子 Agent 内部回传及请求资料。
- `gateway/agent-capabilities.md`：默认允许两层原生委派、普通第三级拒绝；明确默认深度与权限独立。
- IM、Task 数据协议无增量，不提前改 current specs。

## 风险与回退

主要风险是主/子注册作用域误继承、误删同名内部通信、主指导仍注入后代，以及模型未正确消费方法。沿实际请求与真实旅程验证；关键失败保留未通过，不能以提示词或 fixture 通过替代结果。既有子 Agent 曾依赖公开产品工具的流程改为向主 Agent 回传，这是本次明确收窄。

回退相关配置/注册/文本提交即可撤回代码行为；已保存的新 PA custom_prompt 仍由主人按原入口修改或清空，不全局重写。没有 schema 迁移；既有会话、Task 与恢复机制不变。

## 一次性部署迁移

无。本轮不部署生产，不接触 #414 迁移 workspace。C 领域 Skills、D 文件交付仍是后续范围。

## Runbook for Reviewer

在实施 worktree 中执行，先构建受审版本，使用 Node 24 与仓库 Python 环境。验证根目录专用于本片：`mkdir -p /tmp/pa667-review`。不得使用 #414 旧试用数据。完整启动命令 `PATH=/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin:/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --profile daily --wt /tmp/pa667-review`；停止使用相同 PATH 执行 `./scripts/e2e-down.sh --wt /tmp/pa667-review`。端口从该目录 `.e2e-ports.env` 读取，`GET /health` 验 IM 就绪，现有节点状态接口确认隔离节点在线。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM 与节点/DSH | 上述 e2e-down | 上述 e2e-up | IM health + 节点在线 |

**Review 驱动方式**：端到端真栈；本片不改客户端，可使用 Web 客户端实际使用的用户登录、聊天发送/读取及 Agent 配置接口。不得以直接调用 DSH 内部入口代替用户旅程；原生能力探针可补充但不能替代产品验收。

**验收前置**：本机现有 LLM_PROXY 4000 与 daily 模型可用；先做小请求核实，保留 provider payload/工具回执证据，失败则报告外部阻塞。合成测试账号、观察会话、资料和两项独立工作均在隔离 IM/workspace 创建；不需要外部消息、日历或生产账号。观测通知沿用当前十分钟合并节奏，可由主人正常来信引用已积累背景触发读取，不修改产品时间常量。无前端原型。

**验证计划**：
1. 同 runtime/模型/工具配置、新鲜 workspace，用 main 文案与候选各运行小事直答、长事更正、观察承诺准备三个有限对照；保留输入及真实结果，不从单次差异推导提升率。
2. 单独用实际 Agent/模型核实 Skill 读取、二级委派及结果返回；工程检查普通第三级拒绝。至少一次产品旅程使两项工作实际并行：更正 A 回原执行者、等待期间回答短问题、只停 A 而 B 继续交付，再由主人明确要求接续 A，核对原执行者接续与状态。每项按输入→工具回执→实际结果给证据，不用提示词要求当成功证明。
3. 观察承诺生成有内容的私人草稿且不对外发送；追加已处理消息后不重复催；无新价值静默；来源不完整时不宣称全覆盖。
4. 检查新 PA 默认指令、已有自定义、清空指令和禁用 Skill 保真；正常工具/固定安全边界仍在。既有测试先窄后扩，文本修改不新增镜像实现的字符串快照测试。

5. 在普通 Global 与 PA 的实际模型请求中检查：主 Agent 产品工具仍可用，一级/二级及 fork/恢复后的子 Agent 不出现 Inbox/conversations、代表发送或公开 send_message 参数，但能向父级/下级进行原生内部通信。工程测试直接调用受限产品入口应拒绝；子 Agent 请求资料和回传成果后由主 Agent 实际读取/交付。不得以仅工具名称过滤断言代替同名 send_message 分支检查。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | A+B 服务方法与主从协作 | 无 | 无 | 三份产品文本、integration profile/工具及提示注册、既有产品入口检查、相关测试、unit 证据与三份 gateway delta | [reviewer] spec 全部场景具有真实产品结果：小事直答、跨事项更正/停止/明确接续、等待可响应、二级执行逐级交付、子 Agent 请求资料与内部回传、私人准备与安静、用户选择保持。[worker] 最窄相关测试及构建通过；深度 2 可执行且普通深度 3 拒绝；普通 Global/PA 的主/子 schema 与当前提示、fork/恢复权限及内部通信取证；实际 Skill 消费、回执和有限基线对照可追溯。关键失败保持未通过，不宣称 M1 完成或 Ready。 |
