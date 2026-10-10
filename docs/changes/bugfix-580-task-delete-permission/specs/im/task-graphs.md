# im task-graphs delta

## MODIFIED Requirements

### Requirement: 公司任务可共同维护且删除须明确授权

#### Scenario: 全员经 Agent 维护
- **WHEN** active 成员交办创建、修改或明确删除任务
- **THEN** 有任务能力的有效 Agent 可以维护公司任务，不增加任务管理员审批；写入保留真实 Agent、可核实发起人及实际来源，不能伪造。
- **AND** 来源聊天及受保护附件继续按对象权限投影，不能借变更信息泄漏其原文。

#### Scenario: 明确删除与冲突重试
- **WHEN** 用户明确指定删除范围或确认 Agent 说明的删除范围
- **THEN** 经 [Gateway 统一工具权限流程](../gateway/task-graphs.md) 获准后，仅删除相应图或子树，其他任务不变；旧链接明确不可用。
- **AND** IM 继续核实调用主体与资源访问资格，不通过用户消息的措辞或本轮消息是否存在再次裁决删除授权。
- **AND** 写操作保持原子 revision 检查，过时请求不覆盖更新，同一写入重试不重复执行或改写原来源，删除回执也可核实。
