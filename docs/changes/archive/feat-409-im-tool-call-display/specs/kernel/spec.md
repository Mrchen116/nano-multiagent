# kernel Specification (delta for feat-409-im-tool-call-display)

> 视角:本 delta 主语为 `agent.sdk` 消费者(订阅会话事件流的产品),不是 IM 终端用户。
> IM 终端用户视角的展示验收见 im delta 与 spec.md【验收标准】。

## MODIFIED Requirements

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `agent` 等基础工具,默认启用工作区安全约束;所有工具执行经
工具注册表分发。应用经 `build_kernel(tools=…)` 追加原生工具、`create_session(enabled_tools=…)` 选子集;
工作区 `<repo_root>/.nano/tools` 下的同名工具可 override 内置(replace 语义,不致装配崩溃)。

> 变更点(对 canonical):工具清单示例由 `task` 订正为 `agent` —— `task` 工具已退役(feat-337
> task→agent 改名收尾,#83),其实现与 presenter 一并删除;子 agent 派发由 `agent` 工具承担。

#### Scenario: bash 工具输出超限被截断且暴露完整输出路径
- **WHEN** 经内核运行的一次 `bash` 工具产生超过上限的输出
- **THEN** 工具结果标记 `truncated` 为真,并提供可取完整输出的路径

#### Scenario: bash 工具超时/被信号中断转为明确错误
- **WHEN** 一次 `bash` 执行超时或被信号中断
- **THEN** 工具结果暴露稳定的超时/信号细节(而非静默挂起或丢失)

#### Scenario: 会话可用工具集可查询
- **WHEN** 消费者 `kernel.list_session_tools(session_id, workspace_root=...)`
- **THEN** 返回该会话可用工具的描述信息

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示(`tool_start`/`tool_end` 携带的 presentation:`visible`/`label`/`summary`/
`detail`)由该工具自身的 `presenter`(SDK-owned `ToolPresenter`,缺省即无)决定;未带 presenter 的工具
走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具,其 presenter 随对象一起生效,无须额外注册步骤。
`ToolPresenter` / `ToolPresentationEvent` 在公共表面。内置工具 `read` / `write` / `edit` / `bash` /
`web_fetch` / `agent` / `memory` / `skill_manage` / `task_stop` 均自带 presenter,其 `tool_end` 事件
携带结构化 `detail`(而非默认的截断参数);`detail` 中的大字段(stdout/stderr/diff/content)受硬上限尾
截断,截断时 `detail.truncated` 为真。

> 变更点(对 canonical):presenter 覆盖范围从 read/write/edit/bash/web_fetch 扩到含
> `agent`/`memory`/`skill_manage`/`task_stop` —— 这四个原走默认渲染(消费者只能拿到截断参数),
> 现各自产结构化 detail。新增下方两条 Scenario,原有两条保留。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具,消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的
  `visible`/`label`/`summary`/`detail`

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具(如 MCP / 工作区运行时发现的工具)
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation(可见 + 名称 + 截断后的参数),
  不因缺 presenter 而丢失事件或报错

#### Scenario: agent 工具的 detail 含完整派发 prompt
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `agent` 工具被调用派发子 agent
- **THEN** 其 `tool_end` 事件的 `detail` 含完整(不截断)的派发 `prompt`,以及子 agent 的执行结果
  (前台完成时为结果文本、后台/续传时为产物文件位置)与状态

#### Scenario: memory / skill_manage / task_stop 产结构化 detail
- **WHEN** `memory` / `skill_manage` / `task_stop` 任一被调用
- **THEN** 其 `tool_end` 事件的 `detail` 为该工具的结构化结果(写入的记忆 / 操作的 skill /
  停止的任务),而非默认的截断参数串

#### Scenario: 工作区 DIY 工具自带 presenter 被认
- **GIVEN** 用户在 `<repo_root>/.nano/tools` 放置一个工具类,并在其对象上声明了 `presenter`
- **WHEN** 该工具被运行时发现并调用
- **THEN** 其 `tool_start`/`tool_end` 事件的 presentation 为该 DIY presenter 产出的
  `summary`/`detail`(不被剥离、不退回默认渲染),与内置工具同等透传

#### Scenario: 内置工具 summary 为人话而非裸状态码
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `bash` 工具被调用且其参数含 `description`
- **THEN** 该工具事件的 `summary` 为 `description` 文案(`description` 为空时降级为命令首段),
  而非仅 `exit=… elapsed=…ms` 这类裸状态串
- **AND** 折叠态展示无须消费者按工具名二次派生文案——`summary` 即工具自带的人话摘要
