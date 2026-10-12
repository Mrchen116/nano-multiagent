# gateway/workflows Specification (delta for refactor-581)

## ADDED Requirements

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

## MODIFIED Requirements

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
