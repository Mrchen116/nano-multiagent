# 已有终态消息的历史幂等键

适用于升级前已积累 message_delta_idempotency 的中心 SQLite。新服务自动回收此后结束的 running 消息，历史整理可在获授权部署的维护窗口进行。owner 为 IM 部署执行者。

1. 在中心服务停止写入后，用 SQLite backup 保存完整业务库。在备份可读且 integrity_check 为 ok 后操作。核实部署版本包含终态清理 trigger，并使用该实例的实际数据库路径。
2. 记录下列 SELECT 的数量，以及 running 消息的 key 数、messages 与 conversation_events 总数。目标计数为零时跳过删除。仅删除与 completed/failed 消息关联的键。

```sql
SELECT count(*) FROM message_delta_idempotency WHERE message_id IN
  (SELECT id FROM messages WHERE delivery_status IN ('completed','failed'));
BEGIN IMMEDIATE;
DELETE FROM message_delta_idempotency WHERE message_id IN
  (SELECT id FROM messages WHERE delivery_status IN ('completed','failed'));
COMMIT;
```

3. 再查目标计数应为零，其余三项计数应与操作前一致。事务提交前可回滚；中断后重查目标计数即可判断是否需要继续。核对失败时保持服务停写，从备份恢复；核对通过按正常部署顺序启动并检查健康。SQLite 可复用释放的页，文件大小不作为完成判据。功能、重试和故障回归在隔离库完成。记录计数与完成时间到部署记录。
