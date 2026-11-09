# bugfix-743：历史按需读取，Work 按持久位置补传

## 决策

### 历史正文归原有磁盘记录

- Nano profile 停挂官方 `session_projcache`，保留原文件和原生 Session 日志。这个域是可重建的 fold 快捷方式，不是审计所有者；公开 query 在无服务时使用官方 projection registry 从精确原生日志 hydrate。Nano 现有 Work/轨迹通过 sessionQuery 和 trusted binding 读取；校验标题/子关系仍能从日志派生。原生 Session 恢复、审核入模与证据文本无变化。已有缓存不在启动时迁移或删除。普通 profile 的永久删除以显式 profile 配置启用，继续按已经证明的范围删除旧 projection 文件及备份；不装缓存也没有新缓存写者可与删除竞争。
- 工具 presenter 的冻结输出不能从今天的定义重建。保留现有 `storages/nano_tool_views/calls/<key>.json` 格式，以已声明的 `JsonStorageBackend` 写原有 per-record 单元；只读当前事件的键，文件路径/格式在一个 Nano adapter 内。保留原写入顺序、失败重试与关机屏障。永久删除等目标写入结束后按会话扫键并删除，不为枚举加载正文。不改上游包或使用私有 import。不进行需要授权的一次性迁移；回退时旧读取者能读相同记录。

### 观察与确认分开

- 私有 stdio 的 Work 读以消费方已处理的 native seq 取 own 事件。主会话由独立的 `session.work.root`（以已有 root binding 校验）读页；`session.observe` 保留单线程投递和非 Global Task Graph/发送的证据契约，后台唤醒改用只取状态的 `session.status`。子会话先从可信根分页枚举原生 catalog（请求只有已遍历的 anchor），再按已发现的可信 child ID 和单会话位置拉取事件页；每个子会话先保存 throughSeq，再拉下一页。新一轮从头校验目录和变更；重连只依赖已持久化的各会话位置。`session.work.check` 的历史检查输入只传根位置；子检查复用分页目录和各个子页，不在每页附全部子游标。只把已发送、持久化的 native 区间标为 throughSeq，未读完显式 more。原生冷观察可能解码单份完整日志；使用官方有界缓存，不在 Nano 再留全量副本。
- 每页的预算包括实际发送的目录项、事件、附带的 presenter 和模型元数据。先按游标选取，再逐条附带相关数据计费。标准 1 MiB / 256 项（包含目录项），超过常规预算的单条完整记录独占一页；内部批次内存上界是一个最大单条和固定预算中的较大值，不设会卡住后续权限取证的新单条拒绝门槛。中心协议既有 16 MiB 单条失败语义保留。只携带与本页或本地未完成逻辑轮相关的模型 run 公共字段，舍弃待重试的模型输入等私有载荷。状态版本按精简 run 逐条更新摘要，无需反复序列化全历史；旧版本摘要仅使首次检查补核。Work 读不附根审批审计列表；原入口保留。Work 请求快照只保留 model/contextWindow，原始日志和原生轨迹不变。实时 `session.event` 只发变化识别和必要来源标识，持久读取是权威。
- 根用已有本地原生事件 ledger，从 Work checkpoint 的逻辑轮起点投影；子执行将未完成逻辑轮前缀保存在 Inbox SQLite，与该页 Work facts/checkpoint 一起提交。工具配对、用量与 fallback 逻辑轮从本地前缀和本页完成，关闭后清理处理上下文。旧 checkpoint 无本地前缀时只补一次未完成轮。模型状态变化但没有新 native seq 时仍用本地前缀重新投影，稳定 event ID 去重；中心 ACK 独立。
- 停用先完成已有 cancel、drain、flush、dispose，确认任务只保存停用结果，不保存整段历史。Node 在开始读取前记录与原执行进程和 revision 对应的本机 cleanup receipt；该凭证只允许下一管理进程继续已证实的清理，不能单独当作已停证明。按已停用的 Agent / revision 校验，同一有界 Work 读面从冷根和可信子目录补到停用后的稳定 cut，无需激活 Agent。Node 按页提交；尚未处理完保持 Work pending，复用现有停用包装器，最终页提交前不返回成功、不发布已停证明。Runtime 就绪后异步对本分区已停用但未确认的 revision 重试停用/补传，等待本机正在结束的同 revision 操作后重试，不依赖 relay 重连。停用确认和 Work 补传均不伪造执行结果；永久删除沿用已停、归属、清理确认边界。
- RPC 发送在 writable 返回 false 后等 drain；有限 FIFO 在可写后才序列化下一帧。Work 页限定单个重载读取并等待该页通过写出屏障再启动下一页；反向调用与控制 handler 保持独立 dispatch。关闭、输入/输出错误或排队溢出清空队列、拒绝未决调用并释放等待者；RuntimeClient 将真实链路故障接到子进程结束与已有 supervisor 恢复（常规 shutdown 不改变），不让 peer 已关闭却宿主仍宣称可用。重连不隐式重发有副作用的请求。

## 本次审查安排

- 实现与契约：审真实 profile/Node 组装、两条游标持久化、停用/关闭、删除和读取范围。验证 inherited cut、冷中断合成结束、失败不推进、跨页工具与 fallback 逻辑轮。
- 性能：相同隔离历史与追加量，记录启动读取/heap 和 Work 返回字节；阻塞可写端，观察 writableLength、帧序和恢复。明确单条与总页界限。
- 用户旅程：以隔离的真实 Node→DSH→Work 写入路径，已有主子内容可读，新工具跨页、断开恢复后正文和关联仍完整；既有权限负例复用/补测。无页面或交互设计变更。若冷标题/子会话展示被模型工具消费，同时核对官方 hydrate 和实际工具结果。
- 风险与回退：无缓存的冷查首次 fold 成本增加，由官方有界冷观察及既有 Work durable catalog 避免不变历史反复重建。回退可恢复旧 profile，原始日志和工具冻结记录仍原位。Node 的额外子工作上下文是派生记录，不影响旧版本读取原日志。

| Milestone | 依赖 / 并行组 | 范围 | 退出标准 |
|---|---|---|---|
| M1-runtime-work | 无 / 单组 | DSH integration、Node、PA 的历史读与 Work 消费；受影响测试 | [reviewer] 长历史、断线、重启、停用下 Work 可恢复且完整，隔离权限仍有效。 [worker] 旧数据留存、定点读写删除、只读所需 seq、字节预算与慢消费者实测；跨页投影与最终游标对账。 |
