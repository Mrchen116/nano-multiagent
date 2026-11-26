# Agent Work 行为增量

## MODIFIED Requirements

### Requirement: Web Work 可以从派工关系进入同一工作记录

#### Scenario: 从新一级派工查看关系

- **WHEN** 一级 DSH worker 的首条工作记录明细已同步
- **THEN** 用户从派工关系、活动弹窗、父执行中的派工、追加和来源回传打开该 worker 的同一份持久工作记录。执行节点离线后，Web 与 iOS 均可回看已同步明细。
- **AND** 节点在线时，Web 可从 DSH worker 的工作记录切换至该执行的原生轨迹，查看自身轮次及工具输入和输出。工作记录、原生轨迹和原聊天分别遵循原有访问权限。一级 worker 内部的 helper 不作为该 Work 的可导航子执行。
