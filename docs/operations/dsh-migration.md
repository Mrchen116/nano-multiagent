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

首次迁移完成后，将已核对的候选状态和原生插件声明安装回原 owner 根。候选中的 autostart 默认关闭；核对节点 ID、owner、workspace、IM URL、模型/代理和通道归属后才恢复原自启意图。同一飞书 Bot 不能同时由新旧节点监听。

按 [Gateway](gateway.md) 启动当前 Node，确认 DSH ready、owner 对齐、双节点 online、原附件/历史可见、真实 Web/飞书往返和主动任务状态。`readyForCutover` 只表示候选资产通过转换检查，不代替服务验收。若切换失败，先停新实例；保留其运行数据，按备份恢复旧代码与旧状态，避免把两个版本的数据库混用。
