# gateway workflows Specification (delta for refactor-581)

## MODIFIED Requirements

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
