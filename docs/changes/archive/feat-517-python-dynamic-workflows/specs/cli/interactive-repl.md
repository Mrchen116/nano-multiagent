# cli (coding_cli) - Interactive REPL Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: REPL 提供固定一组斜杠命令管理会话与上下文

REPL 暴露稳定的斜杠命令集合管理会话生命周期、查看工具、压缩上下文、回看历史、管理 Workflow 与退出；斜杠命令不计入对话消息历史。

#### Scenario: 斜杠命令集合稳定
- **WHEN** 用户在 REPL 中查看可用命令
- **THEN** 至少包含 `/help`、`/new`、`/use <id>`、`/session`、`/tools`、`/compact`、`/history [n]`、`/exit`
- **AND** Workflow 启用时还包含 `/workflows`、`/effort`、适用的命名 Workflow 命令与 `/config workflowSizeGuideline`

#### Scenario: /new 与 /use 切换活跃会话
- **WHEN** 用户执行 `/new`
- **THEN** 创建并切到新会话；执行 `/use <session_id>` 则切到指定既有会话，后续消息发往切换后的会话
- **AND** `/new` 不继承上一会话的 ultracode 模式

#### Scenario: /tools 与 /compact 作用于当前会话
- **WHEN** 用户执行 `/tools`
- **THEN** 列出当前会话可用工具；执行 `/compact` 则手动触发当前会话的上下文压缩
- **AND** 无活跃会话时给出可执行提示，而非报栈

#### Scenario: /workflows 查看和控制运行
- **WHEN** 用户输入 `/workflows` 或其 run/action 参数
- **THEN** 终端显示当前会话适用的 Workflow 状态、阶段、Agent、用量、诊断与允许的控制

#### Scenario: /exit 退出 REPL
- **WHEN** 用户执行 `/exit`
- **THEN** REPL 干净退出，退出码为 0，并收拢本进程拥有的前台运行资源

## ADDED Requirements

### Requirement: CLI 默认提供 Workflow 且只对明确 opt-in 或会话 ultracode 编排

#### Scenario: 默认可用
- **GIVEN** 用户未在 config 或环境变量中禁用 Workflow
- **WHEN** 启动交互式 CLI
- **THEN** 新会话工具列表包含 `Workflow`，并可发现 `/workflows`、`/deep-research` 和适用的命名 Workflow

#### Scenario: 普通任务不自动调用
- **GIVEN** 当前 session 未开启 ultracode
- **WHEN** 用户提出普通任务但未亲自要求 Workflow 或多 Agent 编排
- **THEN** Agent 不调用 Workflow；可使用普通工具或先征求用户 opt-in

#### Scenario: typed ultracode 激活当轮
- **WHEN** 交互式用户在当轮输入 `ultracode`
- **THEN** 当轮获得 Workflow opt-in reminder，Agent 使用 Workflow 完成实质任务

#### Scenario: 非交互 --text 不因关键词激活
- **WHEN** 脚本以 `--text` 提交包含 `ultracode` 的内容
- **THEN** 该关键词本身不获得可信人工 reminder
- **AND** 明确的“run workflow”指令仍可作为普通显式请求由模型理解

#### Scenario: session ultracode 模式
- **WHEN** 用户输入 `/effort ultracode`
- **THEN** 当前 session 使用 xhigh effort，并在每个实质任务向模型提供 standing Workflow reminder
- **AND** `/effort high` 或新建 session 后恢复逐次 opt-in

#### Scenario: 配置关闭 Workflow
- **WHEN** global/workspace config 或 disable 环境变量关闭 Workflow
- **THEN** 新会话不含 Workflow tool、reminder、ultracode effort option、命名命令或 `/workflows`

### Requirement: CLI 在主会话可继续使用时呈现并控制后台 Workflow

#### Scenario: 启动后继续输入
- **WHEN** Workflow tool 返回 async launch
- **THEN** REPL 显示 task/run 与 script locator，并继续接受主会话输入

#### Scenario: TTY 进度与快捷控制
- **GIVEN** 有 Workflow 正在运行且终端为 TTY
- **WHEN** 用户打开 `/workflows`
- **THEN** 看到实时阶段/Agent/usage 树，并可用 `p` 暂停或继续、`x` 停止、`r` 重启选中 Agent、`s` 保存

#### Scenario: 非 TTY 显式控制
- **WHEN** 终端不支持交互按键
- **THEN** 用户可用 `/workflows <run-id> <action>` 完成同一组控制，不因降级而失去管理能力

#### Scenario: 完成后收到一次结果
- **WHEN** Workflow 进入终态
- **THEN** REPL 在下一安全输出边界显示一次结果或错误、usage、诊断与 resume 提示

#### Scenario: CLI 重启后显式恢复同会话终态运行
- **GIVEN** 用户退出 CLI，随后重新选择 Workflow 所属的同一 session
- **WHEN** 用户执行 `/workflows <run-id> resume`
- **THEN** CLI 从持久化的原 script 和 args 启动带新 run id 的恢复运行；原 run 仍可查询，新 run 诊断记录 `resumed_from`
- **AND** 若当前 session 不是原 parent session，CLI 显示可操作的归属诊断而不是笼统失败
