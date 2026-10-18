# gateway/agent-capabilities Specification (delta for feat-616)

## MODIFIED Requirements

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。公开 Agent profile 提供的提示词文本仅为可见的 Custom Instructions：它作为产品规则后的 `PromptSlots` 追加段出现，不能覆盖公共 PA 提示词，也不走 Kernel 内部完整 override。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。

#### Scenario: 增加工具后继续既有聊天
- **GIVEN** Agent 因未配置某工具而无法完成既有聊天中的任务
- **WHEN** 用户增加该工具后在同一聊天继续
- **THEN** 新回复可使用该工具并理解此前的问题与回复

#### Scenario: 删除工具后保留既成工具历史
- **GIVEN** 既有聊天历史中已有某工具调用及结果
- **WHEN** 用户删除该工具后继续聊天
- **THEN** 新回复不能再执行该工具，但能理解历史调用与结果

#### Scenario: 修改 Custom Instructions、skills 或 features 后继续历史
- **GIVEN** 某聊天已形成历史
- **WHEN** 用户修改会影响后续模型请求的 Custom Instructions、skills 或 features 后发起新交流
- **THEN** 新回复体现完整的新运行配置，并仍能引用修改前历史

#### Scenario: 连续保存多次只采用最终运行配置
- **GIVEN** 某聊天空闲或消息仍在等待处理
- **WHEN** 用户连续成功保存多份 Agent 运行配置
- **THEN** 下一轮新回复使用真正开始时最新的完整配置，不依次重演中间版本

#### Scenario: 配置替换失败不使用混合配置回复
- **WHEN** Gateway 无法把最新完整运行配置持久应用到既有会话
- **THEN** 当前消息以真实失败结束，不以新 model 搭配旧 prompt 或 tools 的混合配置运行

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

本条的静态工具选择规则适用于 `single_thread`。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大静态默认工具、显式空集或子任务限制。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

任务图特性被显式关闭时，`task_graph` 从该 Agent 的有效工具集排除；这一有限例外及预览、下一轮生效规则见 [任务图规范](task-graphs.md)。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述 workspace 自建工具的有限增量外，非空时 Agent 静态工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单的 Agent 会话拒绝一切工具调用
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用工具
- **THEN** 工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态工具只启用该白名单列出的工具；仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="schedule_create"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `schedule_create`；其他原生 `schedule_*` 工具仍需在有效白名单内。停用 Cron 能力后，其调度工具不再可调用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: PA Agent 从有序的工作区与用户级兼容根发现 Skill

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

PA 为某 Agent 解析可选 Skill、prompt preview、下一轮新回复和 `skill` 时，按该 Agent 的真实 Workspace 依次搜索 `<workspace>/.nanoassistant/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`，再依次搜索 `~/.nanoassistant/skills/`、`~/.agents/skills/`、`~/.claude/skills/`、`~/.codex/skills/`。`~/.agents/skills/` 是用户级兼容来源，不新增 `<workspace>/.agents/skills/`。同名 Skill 只采用最先命中的版本；缺失或空的可选兼容目录不影响其他来源。

#### Scenario: 工作区 Claude/Codex Skill 出现在 Agent capability 中
- **GIVEN** 某 Agent 的真实 Workspace 下 `.claude/skills/` 或 `.codex/skills/` 含有效 Skill
- **WHEN** IM 通过在线 Gateway 解析该 Agent 的 capabilities
- **THEN** 该 Skill 成为候选并携带实际命中的 location
- **AND** 同名的较低优先级副本不作为第二个候选返回

#### Scenario: PA 新回复与 capability 使用同一同名覆盖结果
- **GIVEN** 同名 Skill 同时存在于 PA 的多个受支持工作区或全局 roots，且用户在 Agent 配置中选择该 name
- **WHEN** 用户保存配置后在既有聊天开始下一轮新回复
- **THEN** 该轮使用与 capability 中同一优先级、同一 location 的 Skill 内容

#### Scenario: 缺失兼容目录不阻断 PA Agent
- **GIVEN** Agent Workspace 未创建 `.claude/skills/` 或 `.codex/skills/`，或用户主目录未创建 `.claude/skills/`
- **WHEN** Gateway 解析 capabilities、开始新回复或处理 `skill`
- **THEN** 操作正常完成
- **AND** 其他有效 roots 中的 Skill 仍可使用

#### Scenario: 新建页只取得全局 Skill candidates
- **GIVEN** IM 正在为尚无 canonical Workspace 的新 Agent 查询 node capabilities，且 Gateway repo root 中存在工作区 Skill
- **WHEN** Gateway 返回该 node 的创建页 Skill candidates
- **THEN** 返回的候选只来自 PA 的共享全局 roots
- **AND** repo root 或其他未绑定 Workspace 中的 Skill 不作为新 Agent 可选择项

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

Gateway 对 self-evolution review 成功产生的知识更新事实保持 session 级消费，不依赖已经结束的前台 run context。事件无论在前台 terminal 前后到达或经可恢复 stream 重连重放，都保留真实来源与通知，不为新技能修改禁用名单。

后台 Memory/Skill review fork 保留父会话历史，逐字节继承父请求已渲染的 system prompt 和完整工具定义，维护指令追加在继承历史之后；不因后台工具白名单重建请求前缀。白名单在工具执行前独立拦截，工具可见不代表获准执行。这样保留上游前缀缓存的复用条件；实际命中仍以 provider usage 为准，不承诺每次命中。

Memory 注入在首次请求惰性读取，当前会话内保持快照，原生 fork 继承快照，压缩完成后再读取最新内容；禁用 memory_curation 时不读取。后台反思分别按主会话轮次和模型迭代累计，单轮并行工具不放大计数；前台对应维护工具的成功结果重置提醒读数，失败不重置。后台 review 仅完成后推进重置点，失败或取消不消耗提醒周期。

#### Scenario: fast review 与 slow review 使用同一调和结果

- **GIVEN** Agent 的 self-evolution review 成功创建 agent-scope 或 global-scope Skill
- **WHEN** 创建事件发生在前台回答 terminal 之前或之后
- **THEN** 新 Skill 由原生发现变为可用，前后台通知按真实结果投递
- **AND** 已存在的同名禁用选择保持，不因创建事实被覆盖

#### Scenario: 后续前台轮次与 stream 重连不重复调和

- **GIVEN** 同一 session 的持久后台事件消费已建立，随后又完成前台轮次或发生可恢复 stream 重连
- **WHEN** self-evolution 创建事件被实时接收或重放
- **THEN** 同一创建结果不会被前台与后台两条路径重复处理
- **AND** 未禁用的新 Skill 在相关 Agent 的后续 session 中保持可用

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: 全局主 Agent 保留默认工具并具备固定基础能力

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

#### Scenario: 新建全局 Agent 时保留正常执行能力
- **WHEN** 用户新建全局 Agent
- **THEN** 除读取收件箱、查阅聊天、显式发言及委派的固定基础工具外，仍默认拥有现有创建流程提供的工具
- **AND** 不因选择全局模式变成只能统筹、不能正常查询或执行的空工具 Agent

#### Scenario: 固定基础工具与可配置工具区分
- **GIVEN** 用户创建或编辑全局 Agent
- **WHEN** 查看和调整工具配置
- **THEN** `inbox`、`conversations`、`send_message`、`agent` 作为固定基础工具，不可关闭
- **AND** 其他工具继续按现有规则默认选择及配置，单 Thread 模式不因此改变

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: 自建工具支持节点全局与workspace两层

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

#### Scenario: 共享、局部及同名覆盖
- **GIVEN** 本节点owner共享工具和workspace A的同名工具，另有workspace B
- **WHEN** A或B的主会话及被允许的子任务使用工具
- **THEN** A优先使用局部版本，B使用共享版本；A的私有工具不出现在B，工具名单继续限制可用能力。

#### Scenario: 重启和同workspace多会话
- **WHEN** 同一workspace建立多个会话或服务重启
- **THEN** 按该workspace的同一份持久扩展声明装配，局部工具不因为包已安装而自动全局启用。

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。

### Requirement: Auto默认沿用Nano规则且可配置为DSH规则

以下既有完整配置、自动发现、继承及审批场景适用于普通 Agent。personal-role PA 按可信 executionProfileId 应用该域的不可变 ceiling，最终能力为配置与 ceiling 的交集；私人配置变化不向 external/observation 或其派生运行导入私人 instructions、history、memory、skills、插件或任意工具。owner_private 自动工作同样仅使用受控来源和宿主 broker；通用 shell/run_code/任意扩展只能在 owner 明确批准并隔离输入的独立任务执行中使用，不能自动继承 PA 私密上下文。Auto 的 safe/skip/allow/fallback、root/global 固定工具、能力动态发现及后台维护均不得覆盖该上限。

#### Scenario: 默认审核规则
- **WHEN** 用户未选择其他Auto规则
- **THEN** 工具权限审核沿用Nano当前判定规则，保留可信来源、短确认、拒绝计数、人工审批和无人值守分流。

#### Scenario: CC与DSH审核使用去重后的指令和来源明确的历史
- **GIVEN** 当前使用 CC 或 DSH 审核规则
- **WHEN** Agent 在含运行快照、已加载 Skill 或多轮消息的会话中请求执行受审工具
- **THEN** 审核将已加载的项目指令放在独立区，按原生指令更新顺序解释替换与移除；同一指令正文只保留最后一次出现，不重复序列化其 source 元数据。
- **AND** 历史沿用原生有效上下文，省略运行快照和 Skill 正文；保留用户原话及简短来源、工具调用和执行状态，最后一条是完整待审核动作。全局 Agent 私稿不视为已向用户提出的提议。
- **AND** Inbox 结果单独保留宿主提供的发送者、目标、消息标识、分页/部分内容及已有回复关系；只有本进程真实观察的消息具备 live 来源，恢复或继承后失去该来源的内容只作为历史背景。不会根据正文自称身份或补造回复关系。
- **AND** send_message 的结果保留实际状态和投递标识；只有 sent 证明提议已发送，accepted、held_for_revalidation、unknown 或错误不能替代送达。短确认必须结合原发送者与真实聊天理解。
- **AND** 通过 run_code 执行的 Inbox/发送子调用按公开执行事件恢复对应结果；已被原生压缩移出有效历史的调用不会因此重新进入审核。

#### Scenario: CC与DSH审核请求预计超过独立模型窗口
- **GIVEN** 当前使用 CC 或 DSH 审核规则
- **WHEN** 完整审核输入的原生估算值加本阶段输出预留超过审核模型声明的窗口
- **THEN** 不提交该次模型请求，记录为审核不可用并走既有人值守/无人值守分流；不计为安全拒绝，不裁掉授权或待审参数，不切换审核模型。
- **AND** 估算不是供应商精确分词；供应商实际返回的超限或其它错误仍按原失败路径处理。

#### Scenario: 子 Agent 统一采用委派权限
- **WHEN** 普通 subagent、Workflow child 或后台知识维护子任务执行工具
- **THEN** 使用原生 `approval=never`；Auto 放行才可执行，不放行时返回阻断原因交回父 Agent，不发起子 Agent人工审批卡，也不借无人值守 fallback 扩权。
- **AND** 既有工具范围、Auto 规则和父级指令来源继续生效；父级补充指令后的重试仍需重新判定。

#### Scenario: 配置切换规则
- **WHEN** 运维者选择DSH默认规则并重启节点完成生效
- **THEN** 后续工具权限判定使用DSH规则；独立审核模型选择仍按既有契约，不能改用另一条并行审批链或绕开产品来源规则。
- **AND** 配置生效前已发出的审批仍对应原请求，迟答不复活取消调用。

#### Scenario: 规则切换不改变审核模型失败处理
- **GIVEN** 节点配置了独立审核模型
- **WHEN** 该模型在已有重试后仍失败或无有效判定
- **THEN** 不自动换回执行Agent模型复审；有人值守/无人值守分别走既有分流。

#### Scenario: 逐Agent选择与节点继承
- **WHEN** 用户为 Agent 明确选择 CC 或 Codex，或清空选择回到节点继承
- **THEN** 明确选择优先于节点规则；空值沿用节点既有 CC/DSH 规则，不改变 Auto 开关、工具权限、审核模型或其他 Agent。
- **AND** Codex 的证据保留和预算恢复遵循“Codex Auto 按风险与授权进行独立、有界的审查”，不沿用 CC/DSH 的不裁剪超窗处理。

#### Scenario: 下一轮切换保持进行中请求
- **WHEN** 新策略经所属节点成功应用
- **THEN** 既有聊天的下一轮新回复使用该策略并保留历史；正在执行的整轮与已发出的人工审批仍保持原策略和原动作关联。

#### Scenario: PA 配置变化不扩大其他执行域
- **WHEN** owner 开启插件、Skill、memory、自进化或更改 Auto，随后外部消息/观察唤醒、热更新或冷恢复
- **THEN** 按宿主当前 profile/策略 epoch 装配；受限域仍无私料与额外工具，失配不能恢复旧 scope。
- **AND** PA 自动资料通过受控 provenance 写入，后台知识/reviewer/child 也参与撤源失效；外部能力发现仅返回本域公开能力，不返回私人 skill/command/路径。
