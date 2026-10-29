# bugfix-678 一次性部署迁移提示词

仅适用于用户明确授权部署包含本 unit 的已验收实现版本。本文件不是部署授权；当前已通过设计复审，但尚无本 unit 的已验收实现，不可据此执行生产迁移。

## 前提与对象

固定目标 Nano SHA、发布 DSH 版本、Node/IM schema 版本及隔离验收证据后，确认部署目标、实际数据路径和进程 owner。对象仅为本 unit 新增的 Inbox 审核状态、PA 事件处置标记、未消费审核凭证和受影响 provider 重试配置；不改 owner、密钥、workspace、聊天内容或联系人决定。

迁移命令随本版本构建产物交付：先执行 pnpm build；在受管服务停止写入且完成一致性备份后，使用下列命令。PA_AGENT_ID 必须来自当前节点的真实绑定清单，可传多个；不从历史路径推断。schema 的正常创建/新增列由既有迁移机制承担，历史语义整理由部署 Agent 一次性执行，不放进每次启动的扫描/回放。

## 可执行命令

```sh
node apps/im-server/lib/migrate-pa-permissions.js plan IM_DATABASE
node packages/personal-assistant/lib/migrate-input-review.js plan INBOX_DATABASE
node apps/im-server/lib/migrate-pa-permissions.js apply IM_DATABASE
node packages/personal-assistant/lib/migrate-input-review.js apply INBOX_DATABASE PA_AGENT_ID
node apps/im-server/lib/migrate-pa-permissions.js verify IM_DATABASE IM_BACKUP
node packages/personal-assistant/lib/migrate-input-review.js verify INBOX_DATABASE INBOX_BACKUP
```

IM 标识为 `pa-permission-boundaries-v1`，Inbox 标识为 `input-review-v1`。两个数据库各自事务提交；多节点需逐个执行 Inbox 命令，全部 verify 成功前保持服务停止。plan 只读；apply 重跑不会重复失效许可或创建事件。脚本不改 provider 配置，不发送消息、不调用模型。来源访问在事件实际投影时按当前权限重新核对；不可访问只报告 source_unavailable，不读取旧私有正文。

隔离验证见本 unit M1 证据；永久回归分别位于 `apps/im-server/tests/pa-permission-migration.test.ts`、`packages/personal-assistant/tests/input-admission.test.ts`，覆盖终态保留、marker 前事务中断回滚、重复 apply 与备份对比。生产不得用测试脚本替代只读验证。

## 顺序与保留原则

1. 只读核对旧/新版本和范围，暂停相关受管 Node/IM 写入、记录原生命周期，备份数据库及必要配置。备份期间确保 WAL 一致；记录目标 SHA、备份位置和迁移标识，不在仓库保存原始数据。
2. 应用新 schema，先输出状态分组计数与迁移 plan。旧已消费/已结算输入保持原终态，不自动重新准入、重放或恢复被旧 revokeSource 清掉的请求。尚未消费且已有明确准入事实的输入转 admitted；旧 unclassified 或无法证明准入/审核完成的残留转 failed/legacy_unreviewed，生成可发现故障事实，待主 PA 显式判断。不要猜测其为安全拒绝。
3. 旧 incident 的真实 owner/peer 回执完整保留；仅无终态且缺处置回执的事件登记剩余待处理，已有消息不重发。找不到原来源/已撤销访问的事件标不可处理，保留原因，不访问旧私有原文。由模型产生新提醒不属于迁移脚本动作。
4. confirmed/sending/unknown 外发 operation 原样保留，绝不重发。尚未提交的旧 allowed 凭证一次性失效并记录 upgrade_requires_redecision，保留冻结内容和审核审计；取消旧计数/期限后不让旧版本批准自动获得新语义。历史 disclosure_revision/expires_at 列留存但新代码不依赖，不清空其历史值。
5. 保留原 llm-retry 装配，仅新增独立调用恢复插件。核对 Loop 请求绕过补充层，原生恢复没有被替换或叠加。保留用户 provider 策略和密钥，不为本次迁移批量覆写 ordinary/always 设置。
6. 迁移标识与状态更新原子提交；按受管生命周期启动目标版本，保留用户原本暂停/停用状态。节点与服务端必须匹配新契约；不承诺新旧版本混跑。

## 验证与停止条件

- **隔离副本（交付前）**：覆盖旧 allowed/confirmed/unknown、部分 incident 回执、unclassified/consumed、消息来源撤销；验证重复 apply 不变、中途事务失败回滚、升级后实际 PA 处置与模型恢复、旧消息不重放、备份还原。截图与原始内容仅保留本机脱敏证据。
- **生产（部署时）**：只读核对实际 SHA/PID/cwd、schema/迁移标识、上述分组计数、不变量和公开健康；检查旧 confirmed 回执数不减少、unknown 未变可重发、旧消息未变新输入。以部署流程规定的完整健康窗口为结束条件，异常立即停止并保留证据。
- 不发送测试消息、创建任务/卡片或做额外重启演练；功能与失败分支已在隔离环境验证。

## 中断与恢复

以部署记录、事务标识及实际状态判断是否已完成。未提交事务重新 plan/apply；已提交只核结果，不再失效凭证/重复生成事件。若启动前验证失败，可在仍停止写入时恢复同一批数据库与配置并运行旧版本；一旦新版本产生真实数据，不直接覆写备份，先停止写入并保留增量，决定前向修复或有明确数据保全方案的回滚。不能仅换旧二进制并复用新 schema 冒充恢复。
