# gateway (personal_assistant) - Workflows Specification

> 对齐: feat-517
> 上级: [gateway (personal_assistant) Specification](spec.md)

## Purpose

Web 与外部 IM 的 Workflow 来源、能力开关、运行时查询控制、权限路由与投递契约。

## Requirements

### Requirement: Gateway 在 Agent 启用 Workflow 时为其所有人工对话入口提供相同运行语义

#### Scenario: Web IM 发起 Workflow
- **GIVEN** Agent 已启用 `workflow`
- **WHEN** Web IM 用户亲自明确要求运行 Workflow
- **THEN** Gateway 以可信人工来源把消息交给 Agent，并把 async launch、显式状态查询结果和终态完成消息送回该会话

#### Scenario: 外部 IM 发起 Workflow
- **GIVEN** 同一 Agent 已启用 `workflow`
- **WHEN** 飞书等外部 IM 的已认证用户亲自明确要求运行 Workflow
- **THEN** 使用与 Web IM 相同的 tool、审批、运行、控制、resume 和完成语义

#### Scenario: 非人工自动消息不触发关键词 opt-in
- **WHEN** heartbeat、cron、后台通知、webhook 或 Agent 转发包含 `ultracode`
- **THEN** Gateway 保留其非人工来源，关键词本身不激活 Workflow

### Requirement: Gateway 只在当前 Agent 运行配置启用 Workflow 时提供专属 prompt 和命令

#### Scenario: 启用后的下一轮完整出现
- **GIVEN** Agent 配置已成功加入 `workflow`
- **WHEN** 该 Agent 的既有聊天开始下一轮新回复
- **THEN** Gateway 采用含 Workflow tool 的完整新配置，并允许 `/workflows`、ultracode 与命名 Workflow

#### Scenario: 取消后的下一轮完整消失
- **GIVEN** Agent 配置已成功移除 `workflow`
- **WHEN** 该 Agent 的既有聊天开始下一轮新回复
- **THEN** Gateway 不再提供 Workflow tool、reminder、ultracode mode/command、命名 Workflow 或新运行管理入口
- **AND** 当前有效模型声明 selectable reasoning 时，普通 `/effort <level>` 继续作为 session 命令处理，不启动 Workflow
- **AND** 旧 run 只保留通用终态消息，用户仅可对已知 task id 使用原生任务控制；Workflow 专属 query/control/saved discovery 一并消失

#### Scenario: session effort 从有效模型能力解析
- **GIVEN** 人工用户当前会话的有效模型声明 selectable reasoning levels
- **WHEN** 用户输入 `/effort <level>`
- **THEN** Gateway 只接受该模型声明的 level，并把它作为不回写 Agent 配置的 session override 用于后续请求
- **AND** 无效值或不支持 selectable reasoning 的模型得到可理解回复，不改变既有 session runtime
- **AND** 只有 Workflow 已启用且模型支持 `xhigh` 时，Gateway 才额外接受 `ultracode` 并开启 standing Workflow mode

#### Scenario: 通过 Workflow config 命令调整规模 guideline
- **GIVEN** Agent 已启用 `workflow`
- **WHEN** 人工用户执行 `/config workflowSizeGuideline` 并选择 unrestricted、small、medium 或 large
- **THEN** Gateway 保存该值，并从下一轮起用于 Workflow tool description 与运行反馈
- **AND** 未设置时使用 medium

### Requirement: Gateway 从 Workflow 运行真源响应查询与控制

#### Scenario: 显式查询运行状态
- **WHEN** Web IM、原生iOS或外部IM的人工用户执行`/workflows`查询
- **THEN** Gateway返回查询时新Workflow运行真源的当前run状态，并以该channel的普通回复返回；中断或未知如实显示。

#### Scenario: 断线后重新查询
- **GIVEN** Gateway或channel在Workflow运行期间断线
- **WHEN** 连接恢复后用户再次执行`/workflows`
- **THEN** 返回新Workflow运行真源中的当前状态，不依赖断线期间的实时事件补发。

#### Scenario: 命令控制同一运行
- **WHEN** 人工用户通过`/workflows`对run或Agent发起pause、resume、stop、restart或save
- **THEN** Gateway操作指定run，并把结果或稳定错误作为原channel的普通回复返回，不影响其他run或误操作普通对话回合。

### Requirement: Workflow 子 Agent 的权限请求回到原人工会话

#### Scenario: Web IM 批准子 Agent 工具
- **GIVEN** Workflow 子 Agent 的工具调用需要人工确认
- **AND** parent foreground turn 已在 async launch 后结束
- **WHEN** parent 会话来自 Web IM
- **THEN** Gateway 用 terminal 前保留的 conversation/message anchor，把批准请求按 request id 幂等追加到原 Workflow launch assistant message
- **AND** 浏览器重连后仍从该已有 message 看到同一张卡，用户决定交回同一个 pending request

#### Scenario: 同一会话的多个 Workflow 权限不串消息
- **GIVEN** parent session 的后台 subscriber 已存在，且两个 Workflow 分别从两条 assistant message 启动
- **WHEN** 两个 run 的子 Agent 各自发送 permission request 并稍后 resolved
- **THEN** Gateway 按 workflow run id、agent call id 与 request id 把每组事件幂等更新各自 launch message
- **AND** 不使用首个或最新 launch 作 fallback，两个 run 终态后各自清理 binding

#### Scenario: 权限或终态早于 launch anchor 不丢失路由
- **GIVEN** Workflow tool result 以非展示 machine metadata 关联 parent tool call 与 Workflow run
- **WHEN** child permission request 或 terminal event 比 Web launch anchor 先到 Gateway
- **THEN** Gateway 按 machine correlation 暂存 request/resolved 或 terminal tombstone，anchor 到达后原序投递或清理
- **AND** 通用 `tool_end.run_id` 仍仅表示 parent foreground run，不被误当 Workflow run id
- **AND** terminal 只由 Workflow manager 在收口 pending broker request 后发布，不 relay 成 IM Workflow event

#### Scenario: 飞书批准子 Agent 工具
- **GIVEN** parent 会话来自飞书等支持原生批准的外部 IM
- **WHEN** Workflow 子 Agent 请求权限
- **THEN** 原生批准卡出现在原聊天，点击结果解析到同一个 pending request

#### Scenario: 无人值守运行不挂起
- **WHEN** 非交互来源的 Workflow child 遇到需确认工具
- **THEN** Gateway 不发送无法响应的批准卡，结果遵循既有 unattended permission policy

### Requirement: Gateway 对 Workflow 完成、显式查询和后台噪声采用不同投递节奏

#### Scenario: 运行中不逐 Agent 刷屏
- **WHEN** Workflow 中间阶段、Agent 和日志持续更新
- **THEN** Web IM 与外部聊天都不为每项自动发送消息；用户通过 `/workflows` 普通回复按需查看

#### Scenario: 终态只投递一次
- **WHEN** Workflow 完成、失败或停止
- **THEN** Gateway 向原会话投递一次主 Agent 的普通综合回复，并为 Web IM 同消息携带一条与 task notification 同源的 Workflow 后台返回
- **AND** 后台返回保留最终 result 或 error、task/run identity、usage、duration、diagnostics 与 resume 提示，不改写原 launch tool row
- **AND** 重连或 shadow replay 不重复发送同一终态

#### Scenario: 显式 /workflows 查询与控制
- **WHEN** 人工用户在 Web 或外部 IM 输入 `/workflows` 及其 action
- **THEN** Gateway 以该 channel 已有普通消息形态返回 run 列表、详情或控制结果，语义与 CLI 一致

### Requirement: Workflow采用JavaScript且保留保存命名与一层嵌套

#### Scenario: 并行与流水线编排
- **WHEN** 已启用Workflow的人工会话明确启动JavaScript流程
- **THEN** 可并行执行真实子Agent、传递前序结果、记录阶段并返回结构化结果。

#### Scenario: 保存与按名调用
- **WHEN** 助手保存个人或项目Workflow并按名传入参数运行
- **THEN** 定义可发现和复用，同名项目定义按原优先级使用；不要求继续维护旧Python编排格式。

#### Scenario: 一层嵌套
- **WHEN** Workflow调用一个保存的子Workflow
- **THEN** 支持一层嵌套并共享父运行限制；子流程再次嵌套被拒绝，不能绕开停止、规模或预算。

### Requirement: Workflow保留暂停及指定子任务重启

#### Scenario: 暂停并继续
- **WHEN** 用户暂停正在执行的Workflow
- **THEN** 不再派发新子任务，已有子任务可以完成；用户继续后同一运行恢复派发。

#### Scenario: 重启选中的运行中子任务
- **WHEN** 用户只重启某个正在执行的子任务
- **THEN** 旧尝试被取消并收拢，新尝试替换它；其他子任务不重跑，迟到旧结果不覆盖新结果。

### Requirement: Workflow可复用同主会话已完成的相同调用前缀

#### Scenario: 从相同前缀继续
- **WHEN** 用户在同一主会话恢复Workflow，前面调用与已保存的完成部分一致
- **THEN** 复用连续相同的已完成前缀，从第一个变化点继续；不因仅展示标签变化而重跑实际相同工作。

#### Scenario: 服务重启后显式恢复
- **WHEN** 服务重启后用户恢复新系统已持久完成的Workflow前缀
- **THEN** 仍可读取并复用终态结果，不伪装恢复任意运行中的JavaScript栈；跨主会话拒绝错误复用。

### Requirement: Workflow父子工作共享主轮次输出预算

#### Scenario: 多流程及替换尝试累计
- **WHEN** 父Agent、多个Workflow及其子任务/替换尝试在同一主轮次消耗输出token
- **THEN** 实际消耗共同累计，重放结果不重复累计；耗尽后不派发新child，无预算配置时不额外加此上限。

#### Scenario: 后台结果和审批仍归原启动会话
- **WHEN** Workflow前台启动回复已结束，而子任务请求人工批准或运行完成
- **THEN** 仍通过原启动消息/聊天处理对应审批和最终结果；只有成功持久的结果才可报告跨重启可恢复，取消请求的迟答不执行工具。
