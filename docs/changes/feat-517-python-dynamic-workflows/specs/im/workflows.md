# IM - Workflows Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Web IM 只通过现有聊天 surface 呈现 Workflow

#### Scenario: Workflow launch 使用普通工具行
- **GIVEN** 本次 Workflow launch 无需批准或用户已经允许
- **WHEN** Agent 开始执行 `Workflow`
- **THEN** Web IM 按与其他工具相同的工具行显示输入、async launch 结果和审计状态
- **AND** 展开工具行时始终先显示本次输入脚本；工具未返回时不显示结果区，返回后才在输入下方追加启动结果
- **AND** 折叠工具行的说明在调用前后保持为本次 Workflow 的人类说明，不替换为 run id 或状态句
- **AND** 工具行的 completed 只表示后台启动完成；后台 run 的 completed、failed 或 stopped 不回写这条 launch 工具行
- **AND** 不新增 Workflow 专属进度条或详情面板

#### Scenario: Workflow launch 使用通用批准卡
- **WHEN** `Workflow` 启动按当前权限模式需要确认
- **THEN** Web IM 使用与其他工具相同的 inline 批准卡展示工具名、说明、原始参数、问题和 Once、Always、Deny 选项
- **AND** 决定待决期间不提前合成“过程”或 Workflow 工具行；用户允许后由真实 `tool_start` 显示 running 工具行
- **AND** 用户拒绝时不经历 running，但通用工具终态直接显示“已拒绝 / 未执行”的 Workflow 工具行，并且不创建后台 run 或后续 Workflow 终态消息
- **AND** 不增加 Workflow 专属卡型或前端字段解释

#### Scenario: 异步子 Agent 权限卡复用启动消息
- **GIVEN** Workflow launch 的父轮已结束，子 Agent 后续请求权限
- **WHEN** Web IM 收到该通用 permission request
- **THEN** 请求与 resolved 状态都按 request id 幂等更新原 Workflow launch assistant message 中的现有 `PermissionCard`
- **AND** 浏览器重连后从消息历史恢复同一张卡，不新建 Workflow 专属 permission message 或批准卡

#### Scenario: 查询与控制使用普通回复
- **WHEN** 用户执行 `/workflows` 查询或控制命令
- **THEN** run 列表、详情、usage、诊断和控制结果以现有普通消息形态显示
- **AND** 页面不增加独立的常驻 Workflow 状态面板

#### Scenario: 终态使用既有后台消息
- **WHEN** Workflow 完成、失败或停止
- **THEN** 最终结果或错误、usage、诊断和 resume 提示通过既有后台 assistant 消息显示，launch tool row 继续留在历史中
- **AND** 终态消息与 launch tool row 清楚分开，不把数分钟后台运行显示成未结束的前台 tool call

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
- **THEN** 新轮不能启动另一 run，旧 run 仍会通过既有后台消息到达终态
- **AND** 用户可通过现有 `task_stop` 能力停止已知 task，不保留 Workflow 专属控件
