# 一次性迁移已有 Agent 的协作范围

在获准部署包含 feat-774 实现的版本时使用。目标是把升级前存在的 Agent（含 PA）统一设为「团队协作」，不论其旧群回复策略为何。具体存储字段、配置写回方式与升级次序以交付版本为准。

1. 在隔离环境用不同旧策略的 Agent 验证目标版本的转换与恢复。核对 Agent 数量与身份、有效协作范围；模拟迁移中断，确认可以继续，并验证重复执行不会覆盖迁移后用户改选的「仅限本人」。
2. 正式升级前核对版本、部署记录及实际配置来源，列出本次存量 Agent 标识。暂停该环境的配置写入和可能回写旧配置的服务，备份受影响的持久配置并记录恢复位置。对在 IM 与节点均保存配置的 Agent，确认哪一份是权威配置以及何时同步。
3. 在新版开始接收流量和配置编辑前，按目标版本的存储契约一次性转换清单中的旧配置，保留成员关系、主人绑定、PA 来源排除及其他设置。已有迁移记录时先核对现场；中断后只继续处理尚未完成的旧记录，保留已生效的新选择。
4. 按目标版本启动服务并恢复同步。生产以只读方式核对清单覆盖、Agent 标识与数量、中心和节点实际生效的协作范围，以及服务健康。记录版本、迁移数、核对结果与完成时间后结束；完整收件行为使用隔离环境的验收证据。
5. 如核对失败，在恢复配置写入前按部署记录恢复受影响配置及匹配的服务版本，核实健康与原配置后记录失败位置。将备份和实例明细保存在受保护的部署记录中。

## 本设计对应的转换清单

- 旧版本仍在线时，先停止接受配置编辑和新建，查询 IM agent_config_operations、PA 代建和节点 configuration.sqlite3 的未决操作。用旧版原有恢复流程收敛已在执行的操作，防止旧候选和旧 fingerprint 在升级后重新 apply。保留历史终态与幂等凭据。
- 暂停接收聊天的新版本切换期间，做 IM SQLite 一致性备份（含 WAL 中已提交事务）、节点配置和本次涉及的本地收件/队列数据库备份。以升级前的 Agent ID、owner、node 和配置版本作对账清单；包含离线节点，先在清单登记，转换核对后再让该节点恢复服务。
- 在 IM profile 和节点 agents 配置中把旧 group_reply_policy 改为 collaboration_scope=team。SQLite 结构按目标版本的建表声明（默认 team），保留主键、索引和关联；每台机器使用独立事务或文件原子替换。按旧结构或旧键是否仍存在判断是否要转换，已有新字段的合法值保留，特别是用户后来保存的 owner_only。确认中心快照、注册 seed 与节点规范化 fingerprint 一致后恢复新版本配置写入。
- 对升级前已接受的输入保留原消息和实际送达证据。隔离副本验证旧 Inbox 未读、PA 已准备通知、group_background 及 native 已排队的提醒能以稳定 ID 对账。已通知/已消费的行不因新期限重复唤醒；原本未计时的存量普通积压以切换时刻开始首个窗口，已有 PA 期限保留。各节点按下方步骤初始化已有队列。恢复依据每端的独立完成记录，不按「服务能启动」推断迁移已完成。

- 保留既有飞书渠道的 owner_open_id。未绑定的渠道沿用首次实时收信的自动绑定。

#### IM 与节点配置

停止写入后检查 `PRAGMA table_info(agent_profiles)`。在同一 IM 事务中执行以下按列存在性选择的 DDL。第一句只在新列缺失时执行，第二句只在旧列存在时执行。

```sql
ALTER TABLE agent_profiles ADD COLUMN collaboration_scope TEXT NOT NULL DEFAULT 'team'
  CHECK(collaboration_scope IN ('team','owner_only'));
ALTER TABLE agent_profiles DROP COLUMN group_reply_policy;
```

核对迁移清单中每个 ID 和 profile_version，保留已存在的新选择。节点配置按每个 agents[] 条目操作：新键缺失就写 collaboration_scope: team，删除旧 group_reply_policy，保留其他键，校验后原子替换文件。事务提交但部署记录未更新时，按列和键的实际状态复核后继续。

## 单会话节点的离线积压转换

在每个节点停收消息后，用部署记录中的固定切换时刻（Unix 毫秒）、节点数据目录及节点主人 ID 操作该节点的 `node.sqlite3`。从备份建立隔离副本，先用目标版本的 `new NodeStore(path, ownerId).close()` 打开副本以准备 schema；同样操作正式副本时保持服务关闭。核对 `group_background.due_at`、`inputs.native_input_id`、`inputs.scope_blocked` 和 `input_lifecycles.scope_cancelled` 已存在。原生已接受的老输入保留原 inputId 和 sessionId，原消息的回执及 turn 保留原值。

在同一个 SQLite 连接中建立临时表 `cutover_single_agents(agent_id TEXT PRIMARY KEY)`，从部署清单填入此节点应转换且当前有效范围为 team 的 single_thread Agent；将 `:cutover_ms` 绑定为上述固定整数。执行以下事务。第一条 UPDATE 将已有飞书影子聊天归到其规范会话；第二条给未计时的普通实时积压设置第一期截止时间。

```sql
BEGIN IMMEDIATE;
UPDATE group_background AS b
SET conversation_id = a.canonical
FROM conversation_aliases AS a
WHERE b.agent_id IN (SELECT agent_id FROM cutover_single_agents)
  AND a.agent_id = b.agent_id AND a.alias = b.conversation_id
  AND b.conversation_id <> a.canonical AND b.cancelled = 0;

UPDATE group_background AS b
SET due_at = :cutover_ms + 600000
WHERE b.agent_id IN (SELECT agent_id FROM cutover_single_agents)
  AND b.due_at IS NULL AND b.cancelled = 0
  AND coalesce(json_extract(b.payload,'$.metadata.context_only'), 0) = 0
  AND NOT EXISTS (SELECT 1 FROM inputs AS i WHERE i.input_id = b.input_id);
COMMIT;
```

记录每条 UPDATE 的行数并核对仍在等待的各聊天最早截止时间。隔离 SQLite 样例涵盖影子会话、普通积压、原有期限、历史回填、已取消、已交接及清单外 Agent；第一次运行只初始化普通积压的期限，第二次用相同切换时刻运行两条 UPDATE 均为零行。无会话绑定时的恢复、到期合批和去重见 `packages/personal-assistant/tests/single-thread-batching.test.ts`。

### 节点 Global / PA Inbox 的一次性转换

在聊天入口及节点进程停止后，用 SQLite 一致性副本操作。先在备份副本运行新版 InboxStore 的建表初始化，确认出现 `inbox_schedule`、`inbox_batch` 和 `scope_revisions`。已有 `background_wakes` 保留到核对完成。以下临时表、参数和事务使用同一个 SQLite 连接。

1. 将切换时间（UTC epoch 毫秒）绑定到 `:cutover_ms`。建两张临时表。把每条旧未读且已准入的聊天原消息的准入事实填入 `chat_facts`。以新版本对原会话、作者、@、引用和 PA 旁观关系的可信判定为准；`high` 表示须立即提醒，`blocking` 表示直接找 Agent、会阻止向该聊天发言。按同一来源补齐 PA 旧消息 payload 的 `addressed_to_agent`、`addressed_to_owner`、`owner_direct`；普通 Web 来信也补齐 `owner_direct`。历史补取、专用任务上下文、已消费、待审核和失败的输入不录入临时表。已知为飞书展示补值、无法回溯原事件时间的消息在 metadata 中显式保存 `provider_source_time: null`。
2. 在隔离的旧版节点上核对原 session 和 inputId。对 `inbox_notifications` 中仍覆盖未读的记录，逐条用 `session.lookup` 认定原 ID 已接受，或用 `delivered=1` 确认已有实际送达证据。只将这些原 ID 填入 `accepted_notices`。对旧 `background_wakes.submitting_through_seq` 核对原 `inbox-background:<agent>:<seq>`，已接受时保留原通知及原 seqs，尚未接受时让原消息进入下面的新批次。缺少原通知的情况下，核实现场的已确认 wakes.watermark、旧 attention 和 observer 的 notified_through_seq，将能证明已通知的单条原消息记为 `chat_facts.previously_notified=1`。旧提醒已接受且待模型处理时，保留 native 队列与原 inputId。未能区分未接受和已接受的项留在隔离环境继续对账，避免重复发出已接受的一批。

```sql
CREATE TEMP TABLE chat_facts(
  seq INTEGER PRIMARY KEY, high INTEGER NOT NULL, blocking INTEGER NOT NULL,
  previously_notified INTEGER NOT NULL DEFAULT 0
);
CREATE TEMP TABLE accepted_notices(
  session_id TEXT NOT NULL, input_id TEXT NOT NULL, PRIMARY KEY(session_id,input_id)
);
```

填好两表后执行以下事务。重复执行时沿用首次完成记录。在只有新 schema 或完全没有历史数据的节点无需转换。事务前核对 chat_facts 的条数与原库可调度未读范围，确保已覆盖所有已准入聊天。

```sql
BEGIN IMMEDIATE;
INSERT OR IGNORE INTO inbox_schedule(ord,seq,agent_id,due_at,notified)
SELECT i.seq, i.seq, i.agent_id,
  CASE WHEN f.high=1 THEN 0
       WHEN json_extract(i.payload,'$.metadata.personal_delivery')='observer'
         THEN coalesce(b.due_at,:cutover_ms+600000)
       ELSE :cutover_ms+600000 END,
  f.previously_notified OR EXISTS(
    SELECT 1 FROM inbox_notifications n JOIN accepted_notices a USING(session_id,input_id)
    JOIN json_each(n.seqs) members WHERE n.agent_id=i.agent_id AND members.value=i.seq
  )
FROM inbox i JOIN chat_facts f USING(seq) LEFT JOIN background_wakes b USING(agent_id)
WHERE i.consumed=0 AND i.review_state='admitted'
  AND NOT EXISTS(SELECT 1 FROM metadata WHERE key='feat774-inbox-cutover');

UPDATE inbox SET attention=(SELECT f.blocking FROM chat_facts f WHERE f.seq=inbox.seq)
WHERE seq IN (SELECT seq FROM chat_facts)
  AND NOT EXISTS(SELECT 1 FROM metadata WHERE key='feat774-inbox-cutover');

INSERT INTO metadata(key,value)
SELECT 'inbox_sequence',max(coalesce((SELECT max(seq) FROM inbox),0),
  coalesce((SELECT max(watermark) FROM wakes),0),
  coalesce((SELECT max(notified_through_seq) FROM background_wakes),0),
  coalesce((SELECT max(submitting_through_seq) FROM background_wakes),0))
WHERE NOT EXISTS(SELECT 1 FROM metadata WHERE key='feat774-inbox-cutover')
ON CONFLICT(key) DO UPDATE SET value=max(CAST(metadata.value AS INTEGER),CAST(excluded.value AS INTEGER));
INSERT OR IGNORE INTO metadata VALUES('feat774-inbox-cutover',:cutover_ms);
COMMIT;
```

核对新表中每个 Agent 最早未通知期限、已通知消息集合及原冻结通知覆盖集合，确认未读计数未变。原库的待审核消息继续审核后才开始计时；已消费和权限撤销的行不会唤醒。保留既有 wakes.watermark、inbox_notifications、reads、ingestions 和 relay_receipts，用于原 ID 的 native 恢复和送达核对。
