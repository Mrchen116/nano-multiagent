# feat-657 一次性部署迁移提示词

本文不授权部署。仅在 feat-657 已实现并通过验收、用户明确授权部署包含实现的版本时，由部署 Agent 执行。当前是设计阶段，迁移命令尚未实现，不可直接执行。

## 适用条件与前提

旧 Node 的 ordinary DSH_HOME 存放多个普通 Agent 的执行数据，PA 已有独立 home；目标是每个产品 Agent 独立 home 和进程，模型管理使用零 Agent control home。共享产品 NodeStore/InboxStore 仍由 Node 单 writer 维护。

实施必须交付 `scripts/migrate-agent-runtime-partitions.ts` 的 `plan/apply/verify` 三步接口和副本测试。该工具仅使用锁定 DSH 的公开 persistence/storage API 与 Nano 自有 domain 定义；不用 shell 文本替换 native JSONL，不猜 private 文件格式。迁移行为固定在本 unit 版本，不在普通启动时自动重扫或兼容旧共享执行。

## 执行顺序

1. 核对部署版本、目标 node/owner/所有 Agent 及现有 PA binding/epoch。在保护目录记录源版本、目标版本、原配置摘要、迁移阶段及备份位置；不提交机器配置或 secret。
2. 在停止服务前准备完整可恢复备份；优雅停止 Node 和所有旧 DSH hosts，核对旧进程/受管后台工作已结束。停止未确认则先处理，不进行双写迁移。关闭该服务的自动拉起，不能一边迁移一边让旧版本恢复会话。
3. 对静止数据再做一致快照：配置、整个旧 DSH_HOME、PA homes、共享 node.sqlite3/global.sqlite3（含一致 WAL/checkpoint）、模型凭据存储、IM 数据库和部署所需版本。workspace 文件只保护不搬动；保留原加密权限。
4. `plan` 从 NodeStore 的全部 binding（不只当前会话）建立 session→product Agent 映射，再沿公开 Session header 的 parentSession、fork lineage 和公开 subagent catalog 补齐后代。PA 按已验证 binding/epoch 独立归属。无法归属或多个 Agent 声称同一可写 session 时列 blocker，不丢弃、不任选一个；操作者根据真实来源核实后再继续。
5. `apply` 写入新 staging homes：通过 `sessionPersistence.list/open(read)` 分页读取源 header/log，以目标 `create/append/flush` 保留 session ID、原 seq、lineage、cwd、模型/工具事实；保留公开 subagent catalog 与其事件来源，重新生成可派生索引。拷贝会话关联附件时校验引用可解析，不修改用户 workspace 路径。
6. 分迁 Nano 自有 domain：history snapshots/overrides/forks、knowledge counters/reviews/facts、workflow runs/budgets/commands、descendant catalog/前缀见证缓存及可读 exports，按 agentId 或已解析 root/session 归属。保留同一 Agent 已不在当前 binding 的历史根。Schedule 自有 owner 目录按 agentId 搬迁并验证 catalog/history；PA 独立 home 可原样转到新布局但不丢 binding/epoch。任何不能归属的非派生记录阻塞 verify。可派生跨进程 revision 见证失效时仅重建该缓存，不改持久业务事实。
7. control home 复制单份模型服务/凭据权威，Agent homes 仅按正常启动协议取得运行快照。共享产品库原地保留所有 journal、处理 checkpoint、transport ACK、输入/交付记录；分区 key 变化只重写已验证的 partition routing 字段，不重置游标。旧记录补初始 lifecycle revision=1，后续停用用真正控制边界失效，不能把未执行旧输入误标为新代次。
8. IM 添加生命周期 schema，现有 Agent 初始 enabled/revision=1；若已有停用记录则保留，不覆盖。停用相关 schema 要先于新 Node 接入；滚动期间未支持 capability 的旧节点不能报告停用完成。
9. `verify` 对账每 Agent 的根/后代数、header/事件序列摘要、附件引用、schedule 定义与历史、非终态 Workflow、knowledge 记录、产品 journal 与 ACK、模型配置，以及其他 Agent 数据未混入。比较旧/新只读 Work 与原生历史样本，不能以“新进程启动成功”代替数据完整性。
10. 只有 verify 无 blocker 后原子写布局完成标记并切换启动入口。启动 control/Node，完成 lifecycle 全量对账，才启动 enabled 产品 hosts；disabled 不启动。按真实用户入口检查历史、新消息、独立 Agent 停用以及重新启用不补跑旧任务。保持旧备份，按部署 runbook 管理后续保留，不在本次迁移自动删除。

## 中断继续、失败与回退

- 工具以 node/Agent/源快照摘要标识迁移；staging 记录每个完整复制单元和验证摘要。重跑只能复用同一源快照，不混入新版本源数据；已有相同目标验证后跳过，不重新追加事件。
- marker 写入前不允许新布局运行；失败保留源及 staging，修复实际 blocker 后从记录继续。marker 已完成时仅 verify，不再次复制或重复执行任务。
- 新进程已运行后禁止把旧共享 home 直接重新挂回，避免双重执行和遗漏新历史。回退需要停止所有新进程、保存新增数据与外发回执，并以完整一致备份恢复配置/产品库/IM 状态及旧 home。存在停用意图时保持服务停止，不能让旧版本忽略开关自行恢复；由部署操作者核实可恢复范围再启动。
- 副本验收包含迁移中断、未知归属、已完成 marker 重试及回退；真实节点迁移另行记录，不以本设计代替执行证据。
