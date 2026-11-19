## MODIFIED Requirements

### Requirement: 在线 Agent 的工作状态独立反映其记录完整性

- WHEN 其他 Agent 在同一节点回补或上传历史，且目标 Agent 的记录已获中心确认，THEN 头像弹窗显示目标 Agent 的主执行状态和子执行数量，派工图显示目标 Agent 的同步状态。
- WHEN 主执行的记录已确认而该 Agent 的子执行仍在回补，THEN 主执行行可独立显示实际状态，子执行行继续等待可信计数。
- WHEN 回补完成且对应事件已获中心确认，THEN 打开的弹窗显示实际子执行数量，离线或未知期间不得据此推断为零。
