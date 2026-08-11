# gateway (personal_assistant) - Workflows Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Gateway 在 Agent 启用 Workflow 时为其所有人工对话入口提供相同运行语义

#### Scenario: Web IM 发起 Workflow
- **GIVEN** Agent 已启用 `Workflow`
- **WHEN** Web IM 用户亲自明确要求运行 Workflow
- **THEN** Gateway 以可信人工来源把消息交给 Agent，并把 async launch、显式状态查询结果和终态完成消息送回该会话

#### Scenario: 外部 IM 发起 Workflow
- **GIVEN** 同一 Agent 已启用 `Workflow`
- **WHEN** 飞书等外部 IM 的已认证用户亲自明确要求运行 Workflow
- **THEN** 使用与 Web IM 相同的 tool、审批、运行、控制、resume 和完成语义

#### Scenario: 非人工自动消息不触发关键词 opt-in
- **WHEN** heartbeat、cron、后台通知、webhook 或 Agent 转发包含 `ultracode`
- **THEN** Gateway 保留其非人工来源，关键词本身不激活 Workflow

### Requirement: Gateway 只在当前 Agent 运行配置启用 Workflow 时提供专属 prompt 和命令

#### Scenario: 启用后的下一轮完整出现
- **GIVEN** Agent 配置已成功加入 `Workflow`
- **WHEN** 该 Agent 的既有聊天开始下一轮新回复
- **THEN** Gateway 采用含 Workflow tool 的完整新配置，并允许 `/workflows`、ultracode 与命名 Workflow

#### Scenario: 取消后的下一轮完整消失
- **GIVEN** Agent 配置已成功移除 `Workflow`
- **WHEN** 该 Agent 的既有聊天开始下一轮新回复
- **THEN** Gateway 不再提供 Workflow tool、reminder、ultracode mode/command、命名 Workflow 或新运行管理入口
- **AND** 当前有效模型声明 selectable reasoning 时，普通 `/effort <level>` 继续由 Gateway 作为会话命令处理；它不启动 Workflow
- **AND** 旧 run 只保留通用终态消息，用户仅可对已知 task id 使用既有 `task_stop`；Workflow 专属 query/control/saved discovery 一并消失

#### Scenario: 会话 effort 从有效模型能力解析
- **GIVEN** 人工用户的当前会话有效模型声明 selectable reasoning levels
- **WHEN** 用户输入 `/effort <level>`
- **THEN** Gateway 只接受该模型声明的 level，并将它作为不回写 Agent 配置的 session override 用于后续请求
- **AND** 无效值或不支持 selectable reasoning 的模型得到可理解回复，不改变既有 session runtime
- **AND** 只有 Workflow 已启用且模型支持 `xhigh` 时，Gateway 才额外接受 `ultracode` 并开启 standing Workflow mode

#### Scenario: 通过 Workflow config 命令调整规模 guideline
- **GIVEN** Agent 已启用 `Workflow`
- **WHEN** 人工用户执行 `/config workflowSizeGuideline` 并选择 unrestricted、small、medium 或 large
- **THEN** Gateway 保存该值，并从下一轮起用于 Workflow tool description 与运行反馈
- **AND** 未设置时使用 medium

### Requirement: Gateway 从 Workflow 运行真源响应查询与控制

#### Scenario: 显式查询运行状态
- **WHEN** Web IM 或外部 IM 的人工用户执行 `/workflows` 查询
- **THEN** Gateway 返回查询时的当前 run 状态，并把结果作为该 channel 的普通回复返回

#### Scenario: 断线后重新查询
- **GIVEN** Gateway 或 channel 在 Workflow 运行期间断线
- **WHEN** 连接恢复后用户再次执行 `/workflows`
- **THEN** 返回 SDK 真源中的当前状态，不依赖断线期间的实时事件补发

#### Scenario: 命令控制同一运行
- **WHEN** 人工用户通过 `/workflows` 对 run 或 Agent 发起 pause、resume、stop、restart 或 save
- **THEN** Gateway 操作指定 run，并把结果或稳定错误作为普通回复返回

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
