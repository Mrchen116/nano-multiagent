# Gateway relay protocol delta for bugfix-585

## ADDED Requirements

### Requirement: 断连及重连过程有安全持久诊断

托管 Node 的 gateway.log 记录节点、时间、阶段、可获的关闭码和安全原因、异常类型/分类、重试次数及退避、注册恢复与中断时长。前台运行可通过 stderr 留存同一诊断。不记录凭据、URL 或消息正文，未知远端关闭原因脱敏；不逐条记录正常心跳。

#### Scenario: 维护者追溯连接故障
- **WHEN** 节点发生连接失败、心跳超时或远端关闭
- **THEN** 持久日志可以关联断线、重试与注册恢复；未知原因明确为未知/脱敏，不捏造网络根因。
