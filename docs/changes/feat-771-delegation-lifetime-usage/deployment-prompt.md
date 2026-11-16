# feat-771 回滚后的条件回填

首次启用时，IM 中心用 SQLite 事务自动建立汇总。只有数据库已包含 `work-lifetime-usage-v1` 迁移标记，且中心又回滚至不维护该投影的旧版并启动过时，部署员在已授权的重新升级中执行以下步骤。Gateway 和节点无需迁移。

1. 停止旧中心，按 IM 数据库运维流程备份 SQLite，并保留备份定位及版本。
2. 在该中心的数据库中执行 `BEGIN IMMEDIATE; DELETE FROM agent_work_lifetime_usage; DELETE FROM schema_migrations WHERE version='work-lifetime-usage-v1'; COMMIT;`。保留会话、轮次和事件。若清除失败，回滚事务并核对旧库后重试。
3. 启动目标版中心，等待健康检查通过。只读确认迁移标记已恢复，并抽查一个已知有历史用量的 Agent，其主卡片累计与已结束主会话轮次一致。若启动失败，先排查并重试目标版事务。需要恢复时使用停写时的备份。
4. 已完成且此后中心一直使用维护累计的版本时，跳过清除。隔离验证覆盖一次正常升级及一次清除后回填。生产核对只读，无需触发模型调用。
