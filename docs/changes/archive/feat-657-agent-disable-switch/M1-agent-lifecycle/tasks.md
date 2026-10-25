# M1 · Agent 生命周期闭环

- [x] IM 持久真人控制、CAS/幂等、Task 冻结和协议代次门控。
- [x] Web 与 iOS 独立生命周期入口、短状态、未确认停止禁止启用。
- [x] 每 Agent 独立 home/process 与零 Agent control host；离线迁移 plan/apply/verify。
- [x] Node 启动权威同步、原始代次、取消/重新启用屏障、未知清理证据保留。
- [x] PA 输入、输出、外部渠道、Heartbeat、Task 恢复屏障。
- [x] DSH 所有受管 owner 清理、冷恢复屏障和最后增量 Work 历史整体验证。
- [x] 完整 daily 场景、iOS 三页实际检查、独立产品/静态门禁。
- [x] final sync、spec 归并、本地等价检查和完整归档。

交付通过 Ready PR 的远端完整 CI 收口，不自动 merge；PR 与最终 head 由交付回复记录。

## 回归测试归属

既有 RuntimePartitions、Supervisor、Task、Cron、单会话/Global、外部渠道与前端设置回归保留；分区 fixture 改为普通 Agent 独立 host，旧共享 ordinary host 断言改写。新增生命周期 authority/controller 测试保护持久代次与恢复边界，原生进程测试保护公开 RPC 的资源清理证据；迁移测试保护持续可用的离线部署命令与严格归属验证。最终 Work 历史测试只验证停机增量与无业务副作用，不重复正常 Work 投影全套。
