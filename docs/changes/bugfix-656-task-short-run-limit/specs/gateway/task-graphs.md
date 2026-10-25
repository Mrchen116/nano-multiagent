# gateway Task Graphs Specification (delta for bugfix-656)

## MODIFIED Requirements

### Requirement: Task 恢复 SHALL 尊重真实运行边界

#### Scenario: 中断与换窗
- **WHEN** 重启或断线恢复可执行性
- **THEN** 按当前真相重新判定 doing、有效 waiting 和待修复 waiting，保留用户暂停及范围边界，不靠旧提示重复行动。
- **AND** 正常上下文换窗不改变状态、不额外创建 Task 续跑。

#### Scenario: 多轮与运行故障
- **WHEN** 多轮后仍有合法有效下一步，或遇到真实运行限制
- **THEN** 除连续短跑的宿主自动续推限制外，不增加 Task 专属轮数、token 或费用上限；真实运行错误如实显示，按既有恢复条件接续，不伪装成完成或用户暂缓。
- **AND** 读取失败不当空责任集，同一不可恢复原因不热循环调用模型。

#### Scenario: 连续短跑与触顶
- **WHEN** 同一 Agent 被宿主自动续推后，主会话不足 3 个原生执行步便再次结束
- **THEN** 连续短跑计数加一；在当前执行进程内达到 256 次后停止该 Agent 的宿主自动续推，任务状态保持，其他 Agent 不受影响。
- **AND** 同一 Agent 的绑定主会话共享计数，子 Agent 步骤与模型请求重试不计入；未触顶时连续执行达到 3 步清零，短的外部执行不清零。

#### Scenario: 触顶后的独立唤醒
- **WHEN** 触顶停推的 Agent 被用户消息、Inbox、Heartbeat、Schedule 等其他机制实际唤醒并进入执行
- **THEN** 清零并恢复被自动续推的资格，不要求该次外部执行满 3 步；后续是否续推仍由当前任务责任、审批与用户停止规则决定。
- **AND** 单纯责任或配置刷新、内部上下文同步、投递重校验、消息入队不解除停推；不制造 waiting、paused 或完成状态。
