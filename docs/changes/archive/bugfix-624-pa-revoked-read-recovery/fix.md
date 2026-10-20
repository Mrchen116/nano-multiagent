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

## M1-fix — 修复与验证

- 实现 commit：`c6370007a9541887466903eeaba79aa2534812d0`；executed_base / effective_base：`5adb013c2fd7357f2590cf1c7ba551f38bbc673f`；validated_at：`2026-10-20T04:53:00Z`。
- `revokeSource` 在删除 Inbox 行之前，使用 saved fragment 的 seq 关联 Inbox 的 agent/target，清除对应 read，不依赖旧正文形状，也不影响其他 Agent 的同名来源。
- `commitRead` 遇到已不存在的 Inbox 行，回滚整个事务并返回 false。恢复调用方继续后续事件，被撤销消息不会进入已消费或 ingestion 状态；有效 read 的原有完整性验证不变。
- 失败复现：两条新增回归在旧实现均抛出相同 payload 异常，原有 9 条通过。修复后 Inbox 11/11 通过，覆盖旧投影撤销、跨 Agent 隔离、混合页事务回滚和有效消息重新读取消费。
- 本地构建、typecheck、后端 471/471（106 files）、Python 62 passed / 31 deselected、Ruff 和 format 全部通过。前端目录及锁文件相对 PR #373 完全未变，复用该相同源码的 936/936 与 critical audit 通过证据；远端 PR CI 再跑完整前端门禁。iOS 无改动。
- 生产数据库一致副本重放：在 Mini 的受限部署备份目录分别复制出 before/after 两份数据库；旧模块处理 69 个真实孤立 read 时 69 次抛错，修复模块 0 次抛错、69 次返回 false、0 次消费成功。未对 live SQLite 执行清理或修复脚本。
- 独立 [code review](code-review.md) 为 pass，无 findings；最终仅补充证据和移动归档目录，代码审查有效性 retained。no spec delta：现有来源撤销与持久恢复契约已覆盖，本次恢复契约实现，不改 canonical spec。
- 原始日志与数据库保留在权限受限的本机临时/部署备份目录，不提交用户内容、凭据、运行数据。该副本验证不等于真实运行中的 PA 回复已经恢复；生产修复部署与主人消息交付仍需后续验收。
