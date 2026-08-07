# kernel (agent) - Tools and Hooks Specification

> 对齐: refactor-513
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

内置工具、Hook、工具展示、授权可观测性、缓存/思考事件和拒绝语义的对外契约。

## Requirements

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `agent` 等基础工具,默认启用工作区安全约束;所有工具执行经工具注册表分发。应用经 `build_kernel(tools=…)` 追加原生工具、`create_session(enabled_tools=…)` 选子集; 每个 session 的 `<workspace_root>/<workspace_config_dirname>/tools` 下的同名工具可 override 内置(replace 语义,不致装配崩溃)。该 session 的 bash permission policy 从同一 `<workspace_root>/<workspace_config_dirname>/policy.toml` 读取；未指定 `workspace_config_dirname` 时该目录为 `.nano`，不把另一目录（包括旧 `.nano`）当作 fallback。

#### Scenario: bash 工具输出超限被截断且暴露完整输出路径
- **WHEN** 经内核运行的一次 `bash` 工具产生超过上限的输出
- **THEN** 工具结果标记 `truncated` 为真,并提供可取完整输出的路径

#### Scenario: bash 工具超时/被信号中断转为明确错误
- **WHEN** 一次 `bash` 执行超时或被信号中断
- **THEN** 工具结果暴露稳定的超时/信号细节(而非静默挂起或丢失)

#### Scenario: 会话可用工具集可查询
- **WHEN** 消费者 `kernel.list_session_tools(session_id, workspace_root=...)`
- **THEN** 返回该会话可用工具的描述信息

#### Scenario: 自定义 workspace 目录的工具 override
- **GIVEN** SDK consumer 用 `workspace_config_dirname=".consumer"` 构建 Kernel，session workspace 的 `.consumer/tools` 含一个与内置同名的有效工具
- **WHEN** consumer 运行该 session
- **THEN** 该 session 使用 `.consumer/tools` 的 override；另一个 workspace 不受影响

#### Scenario: 自定义 workspace 目录的 bash policy 约束命令
- **GIVEN** SDK consumer 用 `workspace_config_dirname=".consumer"` 构建 Kernel，session workspace 的 `.consumer/policy.toml` 与 `.nano/policy.toml` 对同一 bash command 给出冲突规则
- **WHEN** consumer 通过真实 pre-tool permission chain 请求该 bash command
- **THEN** permission decision 按 `.consumer/policy.toml` 产生，`.nano/policy.toml` 不作为该 session 的 fallback 或第二来源

### Requirement: Hook 体系对外契约稳定(事件集 + intercept/observe 语义)

内核暴露稳定的 hook 事件集与拦截/观察语义,供产品与工作区注入扩展行为。intercept 事件可改变行为, observe 事件只观察;单个 hook 异常/超时不中断主流程(fail-open)。

#### Scenario: intercept 事件集与默认 priority/timeout 稳定
- **WHEN** 产品或工作区注册 hook 处理器
- **THEN** intercept 事件恰为 `{input, before_agent_start, tool_call, tool_result}`;observe 事件含 `turn_start` / `run_error` 等;默认 priority 为 100、默认 timeout 为 1500ms

#### Scenario: 单个 hook 失败不中断主流程
- **GIVEN** 一个注册的 hook 在执行中抛错或超时
- **WHEN** 对应事件触发
- **THEN** 主运行流程继续(fail-open),其它 hook 仍按 priority 顺序执行

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示(`tool_start`/`tool_end` 携带的 presentation:`visible`/`label`/`summary`/ `detail`/`emoji`)由该工具自身的 `presenter`(SDK-owned `ToolPresenter`,缺省即无)决定;未带 presenter 的工具走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具,其 presenter 随对象一起生效,无须额外注册步骤。`ToolPresenter` / `ToolPresentationEvent` 在公共表面。`emoji` 随工具/presenter 走(feat-425):presenter 可在 `ToolPresentationEvent.emoji` 声明工具的折叠行图标,经事件透传给消费者;未声明则为空串,由消费者自行兜底。内置工具 `read` / `write` / `edit` / `bash` / `web_fetch` / `agent` / `memory` / `skill_manage` / `skill_view` / `task_stop` 均自带 presenter,其 `tool_end` 事件携带结构化 `detail`(而非默认的截断参数);`detail` 中的大字段(stdout/stderr/diff/content)受硬上限尾截断,截断时 `detail.truncated` 为真。自带 presenter 的工具在 `tool_start` 事件中也可携带从入参得出的参数侧 `summary` / `detail`(如命令、prompt、查询词),而 `tool_end` 事件携带参数侧字段加执行结果字段的完整 `detail`;参数侧的大字段与结束态共享同一截断语义。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具,消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的 `visible`/`label`/`summary`/`detail`/`emoji`

#### Scenario: 自带 presenter 的工具在执行中即产出参数侧展示
- **GIVEN** 一个自带 presenter 且其展示含结构化 `detail` 的工具(如 `bash` / `agent`)
- **WHEN** 该工具开始执行且尚未结束
- **THEN** `tool_start` 事件的 presentation 携带 `summary` 与只含参数侧字段的 `detail`
- **AND** 该 `detail` 不含执行结果字段

#### Scenario: 工具结束时产出完整展示
- **GIVEN** 同一工具调用已经开始
- **WHEN** 该工具执行结束
- **THEN** `tool_end` 事件的 presentation 携带完整 `detail`,既含参数侧字段,也含执行结果字段

#### Scenario: presenter 声明的 emoji 随事件透传
- **GIVEN** 一个 presenter 在 `ToolPresentationEvent.emoji` 声明了图标的工具(如 `web_fetch` 自带 🌐)
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 携带该 `emoji`;presenter 未声明 emoji 的工具,事件的 `emoji` 为空串(消费者据此兜底)

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具(如 MCP / 工作区运行时发现的工具)
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation(可见 + 名称 + 截断后的参数), 不因缺 presenter 而丢失事件或报错;其 `tool_start` 不携带结构化 `detail`

#### Scenario: 工作区 DIY 工具自带 presenter 被认
- **GIVEN** 用户在 `<repo_root>/.nano/tools` 放置一个工具类,并在其对象上声明了 `presenter`
- **WHEN** 该工具被运行时发现并调用
- **THEN** 其 `tool_start`/`tool_end` 事件的 presentation 为该 DIY presenter 产出的 `summary`/`detail`(不被剥离、不退回默认渲染),与内置工具同等透传

#### Scenario: agent 工具的 detail 含完整派发 prompt
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `agent` 工具被调用派发子 agent
- **THEN** 其 `tool_end` 事件的 `detail` 含完整(不截断)的派发 `prompt`,以及子 agent 的执行结果 (前台完成时为结果文本、后台/续传时为产物文件位置)与状态

#### Scenario: memory / skill_manage / skill_view / task_stop 产结构化 detail
- **WHEN** `memory` / `skill_manage` / `skill_view` / `task_stop` 任一被调用
- **THEN** 其 `tool_end` 事件的 `detail` 为该工具的结构化结果(写入的记忆 / 操作的 skill / 查看到的 skill / 停止的任务),而非默认的截断参数串

#### Scenario: skill_view 产出结构化展示数据
- **WHEN** `skill_view` 调用完成
- **THEN** tool result 事件包含可透传给消费者的 summary/detail,summary 表达查看了哪个 skill, detail 包含 name / location / content preview / success 或 error 信息

#### Scenario: 内置工具 summary 为人话而非裸状态码
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `bash` 工具被调用且其参数含 `description`
- **THEN** 该工具的 `tool_start` 与 `tool_end` 事件的 `summary` 均为 `description` 文案 (`description` 为空时降级为命令首段),而非仅 `exit=… elapsed=…ms` 这类裸状态串或开始态显示原始命令

### Requirement: 工具执行事件携带用户授权决策标识

内核经 `agent.sdk` 向消费者发出的工具执行事件，在原有「非成功终态分类」（denied / 超时 / 中断）之外，新增一个**授权决策标识**：当某次工具调用是经用户在权限确认中显式决策放行或拒绝时，事件携带该决策；自动放行的调用不携带。该标识独立于既有的终态原因维度。

#### Scenario: 用户显式允许的工具调用
- **GIVEN** 一次工具调用进入权限确认（用户需显式决策）
- **WHEN** 用户显式允许后该工具执行
- **THEN** 消费者从该工具调用的执行事件可观察到「经用户授权允许」的标识

#### Scenario: 用户显式拒绝的工具调用
- **GIVEN** 一次工具调用进入权限确认
- **WHEN** 用户显式拒绝该工具调用
- **THEN** 消费者可观察到「经用户拒绝」的标识

#### Scenario: 自动放行的工具调用
- **WHEN** 一次工具调用未触发用户确认、被自动放行
- **THEN** 该工具调用的执行事件不携带授权决策标识

### Requirement: 缓存使用量随 token 用量一并对外

#### Scenario: 一轮含多次模型调用
- **WHEN** 一次助手回复完成
- **THEN** 对外的 token 用量里，命中缓存的输入量、与可用于计算命中率的总输入量，都是这一轮所有模型调用的累计值
- **AND** 跨 provider 口径已归一，命中率 = 命中输入量 ÷ 总输入量，取值落在 0%–100%

#### Scenario: provider 不返回缓存信息
- **WHEN** 上游 provider 的用量里没有缓存字段
- **THEN** 对外的缓存输入量为 0（消费者据此得到 0% 命中率），不报错

### Requirement: 每次模型调用的思考内容随其回合对外

#### Scenario: 一轮含多次模型调用、各自有思考
- **WHEN** 一轮助手回复完成、其中多次模型调用各自产生了思考
- **THEN** 对外可观察到这一轮的多段思考，各段保留其相对于工具调用的先后次序

#### Scenario: 某次模型调用无思考
- **WHEN** 某次模型调用没有产生思考内容
- **THEN** 对外不为该次调用产出思考段

### Requirement: 工具被拒回传给模型的结果按拒绝来源给出语义化文本

当一次工具使用被拒，内核投递回模型的 tool-role 结果内容不再是单一通用字面量，而是按「谁拒的、循环里有无用户可等」给出区分性的语义文本：主会话由用户拒绝 → 指示模型停下并等待用户进一步指示；用户拒绝并附理由 → 在停下指示后附上该理由；策略/分类器自动拒绝 → 指示模型可换工具/换做法或如实上报、但不得恶意绕过；subagent（无人值守的派生运行）内被拒 → 指示其换方法或向上报告限制，而非停下等用户。该文本对 `agent.sdk` 消费者经会话事件流 / 持久化 transcript 的 tool-role 消息内容可见。

#### Scenario: 主会话用户拒绝、未附理由
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel，某轮触发工具许可请求
- **WHEN** 该请求以用户拒绝（无理由）解决
- **THEN** 投递回模型的该工具结果内容表达「用户不愿继续此工具使用、应停下并等待用户指示」，而非通用的 `tool blocked by hook`

#### Scenario: 主会话用户拒绝并附理由
- **WHEN** 该许可请求以用户拒绝且携带一段理由文本解决
- **THEN** 投递回模型的该工具结果内容在「停下等待」指示之后包含该用户理由原文

#### Scenario: 策略/分类器自动拒绝
- **GIVEN** 一次工具使用被内核权限裁决自动拒绝（无逐次用户决定）
- **WHEN** 该次工具使用被拒
- **THEN** 投递回模型的结果内容表达「权限被拒，可用其他正当方式达成或向用户说明，但不得以恶意方式绕过」

#### Scenario: subagent 派生运行内工具被拒
- **GIVEN** 一个受工具执行白名单约束的派生运行（subagent）发起被拒的工具使用（白名单外工具或运行内裁决拒绝）
- **WHEN** 该工具使用被拒
- **THEN** 投递回模型的结果内容指示「换一种方法或向上层报告此限制以完成任务」，而非「停下等待用户」

### Requirement: 显式工具名单的会话在执行层拒绝名单外工具

会话携带显式 `tool_allowlist`(含空名单)时,执行层拒绝名单外的工具调用:工具不产生任何副作用, 调用方收到含「该工具未在本会话启用」语义与工具名的错误结果。名单为 None(未配置)时不做执行层限制。拒绝措辞与权限拒绝、子代理拒绝相区分。

#### Scenario: 显式空名单会话全部工具被拒
- **GIVEN** 会话的 `tool_allowlist` 为显式空名单
- **WHEN** 模型调用任何工具
- **THEN** 工具不执行,返回含工具名与未启用语义的错误结果

#### Scenario: 显式非空名单只放行名单内工具
- **GIVEN** 会话的 `tool_allowlist` 为显式名单 [read, bash]
- **WHEN** 模型依次调用 read 与 edit
- **THEN** read 正常执行,edit 被拒并返回未启用错误

#### Scenario: 未配置名单的会话不限制
- **GIVEN** 会话未配置 `tool_allowlist`(None)
- **WHEN** 模型调用已注册工具
- **THEN** 工具按既有规则(权限门等)正常执行,无执行层额外限制

### Requirement: 工具参数校验错误逐条列出字段名

工具参数校验失败(missing / unexpected / 类型错误)时,错误文本按问题逐条列出字段名:缺失为
`The required parameter \`X\` is missing`,多余为 `An unexpected parameter \`Y\` was provided`,
类型错为 `The parameter \`Z\` type is expected as \`E\` but provided as \`A\``,多个问题组装为
多行错误返回。结构化 details(missing/unknown/field/expected)保持可供程序消费。

#### Scenario: 多个 required 字段缺失
- **WHEN** 模型调用工具时缺失两个以上 required 字段
- **THEN** 错误文本逐条列出每个缺失字段名,不再出现无字段名的笼统文案

#### Scenario: 类型错误列出字段与期望类型
- **WHEN** 模型为某字段提供了错误类型的值
- **THEN** 错误文本包含该字段名、期望类型与实际类型

### Requirement: agent 工具以轻量参数派发真类型子 agent

消费者经会话启用的 `agent` 工具新建子 agent 时，只需提供短描述与任务说明；不必提供 skill 列表、类别别名或前台超时参数。可选 `subagent_type` 从内置真类型中选取；省略时按 `general-purpose` 运行。工具说明向消费者列出至少 `general-purpose`、`Explore`、`Plan` 及缺省行为。各类型在父会话允许的工具范围内提供可区分能力：`general-purpose` 可做修改类工作；`Explore` 与 `Plan` 不能获得会改仓库的写文件类工具，并携带只读角色指引。

#### Scenario: 最少参数新建成功且默认 general-purpose
- **WHEN** 消费者经 `agent` 新建子 agent，只提供 description 与 prompt，不传 skill 列表、类别或前台超时
- **THEN** 派发成功，子 agent 按 `general-purpose` 能力运行

#### Scenario: 工具说明列出可用类型与缺省
- **WHEN** 消费者查看 `agent` 工具的说明
- **THEN** 说明中可获知可用类型至少包含 `general-purpose`、`Explore`、`Plan`，以及不传类型时默认 `general-purpose`

#### Scenario: Explore / Plan 无写仓库工具
- **WHEN** 消费者以 `Explore` 或 `Plan` 新建子 agent
- **THEN** 该子会话面向模型暴露的工具集合不含会直接改仓库的写/编辑类工具（在父会话已启用这些工具的前提下仍被去掉）

#### Scenario: 未知或错误大小写类型失败并可理解
- **WHEN** 消费者以不存在的类型名或错误大小写（如 `explore`）新建子 agent
- **THEN** 该工具调用失败
- **AND** 失败信息指出类型未找到，并列出当前可用类型

#### Scenario: 已删除的仪式字段不可再传
- **WHEN** 消费者调用 `agent` 时仍传入 `load_skills` / `category` / `timeout_seconds` 任一已删除字段
- **THEN** 该工具调用因入参不符合 schema 而失败（不静默忽略）

### Requirement: SDK consumer 的 workspace extension 跟随其选定目录并按 session 隔离

消费者经 `build_kernel(workspace_config_dirname=...)` 选择 workspace config directory 后，内核在每个 session 的 `workspace_root/<workspace_config_dirname>/tools` 与 `hooks` 发现 workspace extension；未提供目录名时为 `.nano`。同一 Kernel 的不同 workspace 不共享彼此的 workspace extension。消费者提供的 global extension roots 仍作为低优先级共享层，workspace extension 可用同名 tool 或 hook file 覆盖它。

#### Scenario: 同一 Kernel 的两个 workspace 使用各自 tool
- **GIVEN** 一个 Kernel 有两个不同 `workspace_root` 的 session，二者的选定目录各含不同 workspace tool
- **WHEN** 两个 session 分别运行并查询可用工具
- **THEN** 每个 session 只看到自己的 workspace tool（以及共享 base），不会调用或展示另一个 workspace 的 tool

#### Scenario: 未指定目录名的 SDK consumer 保持默认 extension 路径
- **WHEN** SDK consumer 不传 `workspace_config_dirname` 而在 workspace 中创建并运行 session
- **THEN** workspace tools/hooks 仍从 `<workspace>/.nano/` 发现
