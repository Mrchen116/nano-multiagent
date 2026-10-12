# DSH 节点迁移

本操作用于首次从旧 Python Gateway 切到当前 Node + DSH。代码合并、迁移演练和生产切换是三个独立结果；生产操作须有对应授权，并遵循 [舰队部署](prod-fleet.md)。旧会话执行记录不导入 DSH，新会话从新上下文开始，旧 IM 可见聊天历史保留。

## 演练候选

先构建当前版本，再在每台节点分别执行：

```bash
pnpm pa migrate --source-root /absolute/old-owner-root --destination /absolute/new-empty-candidate
```

来源必须是已核对的 owner 根；目标必须不存在。命令只读源数据库，用 SQLite backup 取得快照，在私有 staging 完成转换后发布目标；不会启动节点、覆盖源配置或重放旧聊天。重复执行拒绝已有目标。失败只清理本次新建 staging。

检查 `migration-report.json` 的计数、源/目标绑定和 `blockers`。候选含配置、Node SQLite、保留的密钥/加密通道 manifest、已知原生插件及 `migration-source/` 原业务库快照。workspace 和知识文件仍在原路径；`plugins.json` 声明决定工具是否启用。未知旧 Python 工具/Hook 源文件或非空旧 Cron 文件需要明确转换，不能以加载旧 SDK 的方式绕过。

转换保留原绑定顺序、群上下文、未读 Inbox 的页边界与消费标志、relay 去重和外部事件 identity；执行会话使用新 DSH identity，旧审批和 read receipt 不产生新授权。历史 execution/publication/control/image/read 事实留在源归档，不伪装为新执行。

## 切换前的完成条件

- 两台节点分别核对报告；一个节点通过不代表另一节点通过。
- `outbound_handed_off` 等外发未决记录必须按原操作 ID 核实实际 IM/平台结果；不能重发来试探，也不能直接清空 blocker。
- 先停止旧节点入站并排空在途工作，再取得切换用最终快照；演练时的快照不代表之后没有新消息。
- 保留配置、数据库、附件、身份和通道密钥的可恢复备份；原生产 IM 数据库与持久 JWT secret 继续使用。

### 旧生产数据的额外对账

节点转换命令不会修改生产 IM，也不保证旧版每一种落盘格式都能直接启动。2026-10-12 首次切换实际需要以下有证据的一次性处理；逐项核对真实数据后操作，不对未知记录批量套用：

1. 旧飞书 manifest 的 channel 项可能没有 `node_id`。在候选中补齐已验证的 manifest 根节点 ID，保持 credential envelope、AAD 身份和通道归属不变，并验证原密钥仍能解密。
2. 旧外部聊天的 `target_chat_id` 可能是逻辑 `feishu:…` identity。用原飞书消息查询真实平台 `oc_…` chat ID，仅修正候选 `external.sqlite3` 的投递地址及入站 message.chatId；canonical source、event 和幂等 identity 保持不变。
3. 生产 IM 中 `queued/sent/accepted` relay 会在新节点注册时重发。先逐条核对原始消息和结果；确定属于历史遗留且不得重新执行的记录，备份完整原行后标为 `migration_archived`，保留原 receipt 和消息，不伪造 completed。待处理的真实新请求必须单独对账。已提交的旧审批也须核对，不能成为新 DSH 执行的授权。
4. 旧 `agent_work_sessions.scope=global_main` 会与新 DSH session 冲突。备份 IM 库，按 migration-report 的 Agent/旧 session 映射核对后，将旧登记 scope 和 payload.scope 改为 `legacy_global_main` 并标注迁移前历史，保留全部事件、轮次和子会话。新节点自行登记新的主会话，不将旧 execution 伪装为原生轨迹。
5. IM 保留已有 Agent desired state。按 `apps/node/src/migration.ts` 同一工具映射，仅转换 `agent_profiles.tool_allowlist_json`，使用原值 compare-and-set，保留其他 Agent 字段。
6. 原生模型 provider 必须能取得凭据。已确认免密的非 loopback 代理要显式配置占位 `api_key`，不能仅以 URL 可达或 DSH ready 代替一次真实模型调用。真实需要认证的代理仍使用原有效密钥。

这些处理的原值、平台证据和候选修改报告保存在权限受限的备份目录，不入 Git。先停止相关节点，完成备份和事务更新，再启动并验证真实全局消息、普通消息与外部通道；不得通过重放历史外发来试验。

首次迁移完成后，将已核对的候选状态和原生插件声明安装回原 owner 根。候选中的 autostart 默认关闭；核对节点 ID、owner、workspace、IM URL、模型/代理和通道归属后才恢复原自启意图。同一飞书 Bot 不能同时由新旧节点监听。

按 [Gateway](gateway.md) 启动当前 Node，确认 DSH ready、owner 对齐、双节点 online、原附件/历史可见、真实 Web/飞书往返和主动任务状态。`readyForCutover` 只表示候选资产通过转换检查，不代替服务验收。若切换失败，先停新实例；保留其运行数据，按备份恢复旧代码与旧状态，避免把两个版本的数据库混用。
