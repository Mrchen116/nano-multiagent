# kernel (agent) - Tools and Hooks Specification

> 对齐: feat-446
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

内置工具、Hook、工具展示、授权可观测性、缓存/思考事件和拒绝语义的对外契约。

## Requirements

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `agent` 等基础工具,默认启用工作区安全约束;所有工具执行经
工具注册表分发。应用经 `build_kernel(tools=…)` 追加原生工具、`create_session(enabled_tools=…)` 选子集;
工作区 `<repo_root>/.nano/tools` 下的同名工具可 override 内置(replace 语义,不致装配崩溃)。

#### Scenario: bash 工具输出超限被截断且暴露完整输出路径
- **WHEN** 经内核运行的一次 `bash` 工具产生超过上限的输出
- **THEN** 工具结果标记 `truncated` 为真,并提供可取完整输出的路径

#### Scenario: bash 工具超时/被信号中断转为明确错误
- **WHEN** 一次 `bash` 执行超时或被信号中断
- **THEN** 工具结果暴露稳定的超时/信号细节(而非静默挂起或丢失)

#### Scenario: 会话可用工具集可查询
- **WHEN** 消费者 `kernel.list_session_tools(session_id, workspace_root=...)`
- **THEN** 返回该会话可用工具的描述信息

### Requirement: Hook 体系对外契约稳定(事件集 + intercept/observe 语义)

内核暴露稳定的 hook 事件集与拦截/观察语义,供产品与工作区注入扩展行为。intercept 事件可改变行为,
observe 事件只观察;单个 hook 异常/超时不中断主流程(fail-open)。

#### Scenario: intercept 事件集与默认 priority/timeout 稳定
- **WHEN** 产品或工作区注册 hook 处理器
- **THEN** intercept 事件恰为 `{input, before_agent_start, tool_call, tool_result}`;observe 事件
  含 `turn_start` / `run_error` 等;默认 priority 为 100、默认 timeout 为 1500ms

#### Scenario: 单个 hook 失败不中断主流程
- **GIVEN** 一个注册的 hook 在执行中抛错或超时
- **WHEN** 对应事件触发
- **THEN** 主运行流程继续(fail-open),其它 hook 仍按 priority 顺序执行

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示(`tool_start`/`tool_end` 携带的 presentation:`visible`/`label`/`summary`/
`detail`/`emoji`)由该工具自身的 `presenter`(SDK-owned `ToolPresenter`,缺省即无)决定;未带 presenter 的
工具走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具,其 presenter 随对象一起生效,无须额外注册步骤。
`ToolPresenter` / `ToolPresentationEvent` 在公共表面。`emoji` 随工具/presenter 走(feat-425):presenter
可在 `ToolPresentationEvent.emoji` 声明工具的折叠行图标,经事件透传给消费者;未声明则为空串,由消费者自行
兜底。内置工具 `read` / `write` / `edit` / `bash` / `web_fetch` / `agent` / `memory` / `skill_manage` /
`skill_view` /
`task_stop` 均自带 presenter,其 `tool_end` 事件携带结构化 `detail`(而非默认的截断参数);`detail` 中的大
字段(stdout/stderr/diff/content)受硬上限尾截断,截断时 `detail.truncated` 为真。自带 presenter 的工具在
`tool_start` 事件中也可携带从入参得出的参数侧 `summary` / `detail`(如命令、prompt、查询词),而
`tool_end` 事件携带参数侧字段加执行结果字段的完整 `detail`;参数侧的大字段与结束态共享同一截断语义。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具,消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的
  `visible`/`label`/`summary`/`detail`/`emoji`

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
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 携带该 `emoji`;presenter 未声明 emoji 的
  工具,事件的 `emoji` 为空串(消费者据此兜底)

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具(如 MCP / 工作区运行时发现的工具)
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation(可见 + 名称 + 截断后的参数),
  不因缺 presenter 而丢失事件或报错;其 `tool_start` 不携带结构化 `detail`

#### Scenario: 工作区 DIY 工具自带 presenter 被认
- **GIVEN** 用户在 `<repo_root>/.nano/tools` 放置一个工具类,并在其对象上声明了 `presenter`
- **WHEN** 该工具被运行时发现并调用
- **THEN** 其 `tool_start`/`tool_end` 事件的 presentation 为该 DIY presenter 产出的
  `summary`/`detail`(不被剥离、不退回默认渲染),与内置工具同等透传

#### Scenario: agent 工具的 detail 含完整派发 prompt
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `agent` 工具被调用派发子 agent
- **THEN** 其 `tool_end` 事件的 `detail` 含完整(不截断)的派发 `prompt`,以及子 agent 的执行结果
  (前台完成时为结果文本、后台/续传时为产物文件位置)与状态

#### Scenario: memory / skill_manage / skill_view / task_stop 产结构化 detail
- **WHEN** `memory` / `skill_manage` / `skill_view` / `task_stop` 任一被调用
- **THEN** 其 `tool_end` 事件的 `detail` 为该工具的结构化结果(写入的记忆 / 操作的 skill /
  查看到的 skill / 停止的任务),而非默认的截断参数串

#### Scenario: skill_view 产出结构化展示数据
- **WHEN** `skill_view` 调用完成
- **THEN** tool result 事件包含可透传给消费者的 summary/detail,summary 表达查看了哪个 skill,
  detail 包含 name / location / content preview / success 或 error 信息

#### Scenario: 内置工具 summary 为人话而非裸状态码
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `bash` 工具被调用且其参数含 `description`
- **THEN** 该工具的 `tool_start` 与 `tool_end` 事件的 `summary` 均为 `description` 文案
  (`description` 为空时降级为命令首段),而非仅 `exit=… elapsed=…ms` 这类裸状态串或开始态显示原始命令

### Requirement: 工具执行事件携带用户授权决策标识

内核经 `agent.sdk` 向消费者发出的工具执行事件，在原有「非成功终态分类」（denied / 超时 / 中断）之外，
新增一个**授权决策标识**：当某次工具调用是经用户在权限确认中显式决策放行或拒绝时，事件携带该决策；
自动放行的调用不携带。该标识独立于既有的终态原因维度。

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
