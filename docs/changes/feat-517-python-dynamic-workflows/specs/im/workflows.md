# IM - Workflows Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Web IM 持久展示 Workflow 运行并使实时、刷新和重连一致

#### Scenario: 运行中显示紧凑进度
- **WHEN** 当前聊天有 Workflow 正在运行
- **THEN** composer 上方显示名称、当前阶段、Agent 计数、token 与耗时的紧凑进度条
- **AND** 普通聊天消息和输入区域仍可使用

#### Scenario: 打开运行详情
- **WHEN** 用户点击进度条或输入 `/workflows`
- **THEN** 看到运行列表或详情，包含阶段、Agent 状态/任务/结果、日志、usage、耗时、script 与诊断位置

#### Scenario: 刷新和重连
- **GIVEN** Workflow 在页面刷新或网络断开期间继续运行
- **WHEN** 用户回到聊天或连接恢复
- **THEN** 页面恢复最新持久状态，不重复 run、不把完成状态倒退为 running

#### Scenario: 终态历史
- **WHEN** Workflow 完成、失败或停止
- **THEN** 进度详情保留最终结果/错误、usage、诊断和 resume 信息，launch tool row 仍可审计

### Requirement: Web IM 可控制 Workflow run 与选中 Agent

#### Scenario: 暂停和继续
- **WHEN** 用户在运行详情暂停或继续 Workflow
- **THEN** 控件与运行状态在服务端确认后更新，并清楚区分 running 与 paused

#### Scenario: 停止 Agent 或运行
- **WHEN** 用户停止选中 Agent 或整个 run
- **THEN** 对应目标进入明确停止状态，页面不继续显示为运行中

#### Scenario: 重启选中 Agent
- **WHEN** 用户对一个运行中的 Agent 选择 restart
- **THEN** 页面仍在同一 logical Agent 行展示 replacement attempt 与其最终结果

#### Scenario: 保存 Workflow
- **WHEN** 用户把运行保存为 project 或 personal Workflow
- **THEN** 页面显示保存名称/scope，并在后续命令发现中出现

### Requirement: Workflow 启动批准展示脚本计划和真实影响

#### Scenario: 待决批准卡
- **WHEN** Agent 准备启动一个需要批准的 Workflow
- **THEN** Web IM 展示 Workflow 名称、说明、阶段、size/token caution 与查看原始 Python 的入口
- **AND** 选项为本次允许、总是允许或拒绝

#### Scenario: 允许或拒绝
- **WHEN** 用户选择批准选项
- **THEN** 决定提交到同一 pending request；允许后开始运行，拒绝后不启动
- **AND** resolved 结果由 launch tool row 保留已授权或已拒绝的审计状态

#### Scenario: ultracode 或 bypass 无启动卡
- **WHEN** 该次启动按当前权限模式无需 Workflow launch confirmation
- **THEN** 页面不制造额外待决卡，仍显示 async launch 与运行进度

### Requirement: Workflow 命令和 ultracode 入口随 Agent tool 选择完整出现或消失

#### Scenario: Workflow 启用时的 slash discovery
- **GIVEN** 当前 Agent 已启用 `Workflow`
- **WHEN** 用户在 composer 输入 `/`
- **THEN** slash picker 可发现 `/workflows`、`/deep-research`、适用的 saved 与 namespaced Workflow，以及 ultracode/config 入口

#### Scenario: Workflow 禁用时的 slash discovery
- **GIVEN** 当前 Agent 未启用 `Workflow`
- **WHEN** 用户打开 slash picker 或输入相关命令/关键词
- **THEN** Workflow 专属候选不出现，命令不能启动新 run，`ultracode` 不触发 Workflow

#### Scenario: 禁用前已经启动的 run
- **GIVEN** 旧轮已经启动 Workflow，用户随后禁用该工具
- **WHEN** run 尚未终态
- **THEN** 该 run 的进度和 stop 能力继续可见直到安全收口
- **AND** 新轮不能据此启动另一 run

### Requirement: Web IM 的 Workflow 展示在桌面和移动端保持同一信息与可达控制

#### Scenario: 桌面端运行详情
- **WHEN** 桌面用户打开 Workflow detail
- **THEN** 侧面详情保持聊天上下文可见，并提供全部适用控制

#### Scenario: 移动端运行详情
- **WHEN** 窄屏或触控用户打开同一 detail
- **THEN** 详情以单栏可滚动布局呈现同一阶段、Agent、usage 与控制
- **AND** 任何关键操作不依赖 hover 或物理键盘

#### Scenario: 大型运行警告
- **WHEN** Workflow 达到大型运行提示条件
- **THEN** 批准或运行详情显示可理解的规模/token warning 与 stop 入口
- **AND** warning 不遮挡状态或自动改变运行状态
