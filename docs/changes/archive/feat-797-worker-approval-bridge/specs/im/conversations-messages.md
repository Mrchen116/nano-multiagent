## ADDED Requirements

### Requirement: 外部 Worker 的人工审批归主人私聊

#### Scenario: 由群聊或跨聊天根会话发起委派
- **WHEN** 有人值守的 Global 或 PA 的外部 Worker 需要人类审批
- **THEN** 系统只向该 Agent 与主人在 Nano IM 的私聊投递可识别 Worker 和实际动作的审批卡；只有已认证的主人可以答复。一个决定至多放行原调用一次。
- **AND** 原调用结束、过期或取消后，卡片回复不能启动或恢复执行。
