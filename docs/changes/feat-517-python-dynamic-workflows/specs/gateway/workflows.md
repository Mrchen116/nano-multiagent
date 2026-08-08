# gateway (personal_assistant) - Workflows Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Gateway 在 Agent 启用 Workflow 时为其所有人工对话入口提供相同运行语义

#### Scenario: Web IM 发起 Workflow
- **GIVEN** Agent 已启用 `Workflow`
- **WHEN** Web IM 用户亲自明确要求运行 Workflow
- **THEN** Gateway 以可信人工来源把消息交给 Agent，并把 async launch 与后续 Workflow 状态送回该会话

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
- **AND** 已在旧轮启动的 Workflow 仍可被用户查看和停止直到终态

### Requirement: Gateway 把 Workflow 运行投影为可恢复、可去重的跨 IM 状态

#### Scenario: 运行进度发送到 IM
- **WHEN** 内核产生新的 Workflow snapshot revision
- **THEN** Gateway 向 IM 发送带 run id、完整 snapshot 和 revision 的运行更新

#### Scenario: 断线后恢复当前状态
- **GIVEN** Gateway 与 IM 在 Workflow 运行期间断线
- **WHEN** 连接恢复
- **THEN** IM 最终得到当前最新 snapshot，旧 revision 不覆盖新状态，也不重复创建 run

#### Scenario: IM 控制请求回到同一运行
- **WHEN** Web IM 用户对 run 或 Agent 发起 pause、resume、stop、restart 或 save
- **THEN** Gateway 经 `agent.sdk` 操作该 run，并把结果/稳定错误回给 IM

### Requirement: Workflow 子 Agent 的权限请求回到原人工会话

#### Scenario: Web IM 批准子 Agent 工具
- **GIVEN** Workflow 子 Agent 的工具调用需要人工确认
- **WHEN** parent 会话来自 Web IM
- **THEN** Gateway 把批准请求送到原会话，并把用户决定交回同一个 pending request

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
- **THEN** 外部聊天不为每项自动发送新消息；Web IM 可接收状态投影，外部用户在 `/workflows` 卡片中按需查看

#### Scenario: 终态只投递一次
- **WHEN** Workflow 完成、失败或停止
- **THEN** Gateway 向原会话投递一次最终结果或错误、usage、diagnostics 与 resume 提示
- **AND** 重连或 shadow replay 不重复发送同一终态

#### Scenario: 显式 /workflows 查询与控制
- **WHEN** 人工用户在 Web 或外部 IM 输入 `/workflows` 及其 action
- **THEN** Gateway 返回适合该 channel 的 run 列表/详情/控制结果，语义与 CLI 一致
