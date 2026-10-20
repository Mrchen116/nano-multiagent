# bugfix-624: PA 来源失效后历史 Inbox 读取恢复

## Relations

- Related: feat-623, bugfix-621

## 原始报告

用户要求：“部署到生产”。本问题是在执行该授权后的生产验收中发现，不是新增产品需求。

## 现象 / 复现

2026-10-20 将 PR #373 的 `dea5e853e` 部署到 Mini 后，节点在线且 DSH ready，但 PA 恢复日志报 `InboxStore.commitRead: Cannot read properties of undefined (reading 'payload')`。正式主人私聊的验收输入已进入系统，尚未得到回复。

部署前 SQLite 一致备份含 207 个 Inbox 条目、181 个 saved read，无悬空 read；恢复来源权限后，live Inbox 剩 135 个条目、仍有 181 个 read，其中 69 个 read 的 fragment 指向已删除条目。旧版 read 正文为 `{messages:[{target:...}]}`，没有顶层 target。复现只使用受限数据库副本及合成 fixture，不修改生产聊天或凭据。

## 根因

现行来源撤销原本要使后续读取和消费失效，保留已进入会话的历史事实；feat-623 新增启动时来源重新核验，更容易在升级时触发既有撤销路径。`revokeSource` 只按 read 正文顶层 target 清理，漏掉旧投影中的消息级 target；`commitRead` 又假设 saved fragment 对应的 Inbox 行始终存在，恢复重放因此中断。旧版 `0fa706a67` 已有这两个假设，`f036aedd5` 的启动核验使实际生产历史触发它。

修复必须保证：撤销来源不会重新交给模型或标为消费；历史无效读取不阻断仍有效消息的恢复、交办和回复；有效 read 的完整持久摄取规则、图片和分片验证保持不变。范围仅 Inbox 持久读取失效与对应回归，唯一 M1-fix；无新模型字段、计时策略或权限放宽。current spec 的来源撤销与恢复契约不变，无 spec delta。
