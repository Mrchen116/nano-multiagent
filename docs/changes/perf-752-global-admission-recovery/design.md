# perf-752 · 实施设计

## 热路径

以同一个 DSH `Session` 对象及其原生事件顺序为准。现有 `inputEvidence` 的 reducer 扩展为批量可增量折叠的索引，记录两个当前 inbox、输入位置与当前归属、轮次终态及精简输入 ID。按 Session 实例保存在 WeakMap，首次用实际历史建立，后续使用公开 `snapshotEvents(from)` 从序列位置补增量。只存用于确认的 identity/状态，正文继续由 native Session 所有。保留现有纯折叠作为独立测试 oracle（现有其他调用仍可使用），逐前缀比较新索引；新索引只在 Global 实际输入与查证入口消费。处理多个入队位置、claim 未成 transcript、cancel、重复 ID 与 fallback。RPC 先 flush 再返回 durable ACK。首次激活仍由 DSH 公开 resume 加载目标 Session，保留稳定 Session ID、模型输入与旧原生轨迹；本单元不引入 fork 或私有恢复 API。测冷激活与热接单分别报告。

Global fallback 查证用相同索引，按会话维护输入到最后所属 ModelRun 及活跃运行的索引，避免先枚举全部模型轮次再查证。索引在既有 model sidecar 还原和变更入口维护，保持原先 insertion order 下 findLast 的语义。输入迟加到较早 run 时按 run 首次序而非最后写入时间选择。同一语义的专门 oracle 覆盖该路径。依赖历史正文的罕见 fallback 和其他插件路径保留当前行为；不能把仅输入查证加速写成整个首字已验证。

## 恢复

将 Global 中断子执行检查从 DSH initialize 移到对应根的首次激活。OwnedSessions 在尝试恢复根或带已验证父链的历史 managed child 前，通过同一按根 coalesced 调用确认已有中断事实并写入现有 durable queue。这样排在任何可能覆盖旧证据的 child 激活之前，也排在根第一次模型 step 之前。已有挂起通知始终保留。检查区分缺失/不可读和完成。部分读取时先持久登记已验证结果，但不进入该根首次激活或模型 step；保留原输入和 pending，中断返回可重试的该根错误，后续同根重试。因为 DSH 原生子消息能在根运行后绕开 OwnedSessions 冷启直属子 Agent，所以不能在这个核对屏障前放行根。已消费通知不重复投递。启停 revision 在提交前再校验，失效的调用不提交新通知，之后合法接续重新判断。不可用历史不阻塞其他根，单根永久不可读保持可观测警告。
 
PA 的前台恢复保持当前同根输入收口：已收到的 Inbox read、既有控制、terminal 与 receipt 要在允许再次 wake 前完成。继续等待 `reconcileRoot`，它包含前台持久因果所需的事实；只把无关子执行发现和 Work 补齐移到原 per-root 后台 drain。已知结算且无待办的根不激活，也不在前台扫其子树；未确认的原生事实仍走既有根证据查证。Agent 下一次接续以及 Relay 重投遵守同一根的前台工作，不等其他根的历史。保留原有 stop、disable 和 provider 失败语义。根与恢复义务真实完成以前不宣称 Work 已追平。

## 验收与回退

M1 验收包括现有输入证据逐前缀对照、崩溃/取消/迟到持久回执、真实 DSH 强杀子执行并从首个根 step 验证中断通知、一个长根与无关根并发接单。性能检验固定增量下 4 万和 40 万历史的热路径访问量；冷启动核对未激活旧根不读历史正文。初始子执行检查发生时机可观察但正常下一步收到同一输入，模型可见内容、选择和来源不变，专项核对实际模型请求中的中断 notice 与去重。中断通知持久排队的承诺从节点启动调整到该根首次接续，见 delta。无一次性迁移。保留原始 native 日志、现有 Work 和通知账本，可换回旧二进制。

## Milestone 与能力

| ID | 依赖 | 并行组 | 范围 | 退出标准 |
| --- | --- | --- | --- | --- |
| M1-global-admission | 与 perf-751 使用同一恢复界面 | B | DSH 输入索引、OwnedSessions、Gateway 恢复 | [reviewer] 实际 Relay 收到输入后只执行一次，同一根不会先唤醒已消费交办，中断 notice 在首次接续真正进入模型。无关根不等超长休眠根。[worker] 热路径实际访问只和新事件有关，用 1 个长根加 49 个空闲根复跑注册接单、SIGKILL、启停和故障重试；在根 A 的已知子观察处注入可控等待，期间真实 Relay 向无关根 B 接单并确认，再释放 A 验证中断通知与已消费回执；同时统计 readiness 前后的日志正文读取总次数与字节，证明没有把全量读取偷偷移到后台。中心夹具只需真实用户授权路径，1,000 账号和 Web 读取规模在 perf-753 测，不将 1,000 账号假定为并发。报告 RSS、就绪时间与冷恢复分段。 |

独立代码审查、性能对照、Agent Context 检查和真实 Relay 产品旅程覆盖该表。Agent Context 只校核原有中断通知从真实未完成 evidence 到下一 step；证据包含捕获的模型可见原文、引用的 child ID、回执重试不重发、受禁用根不注入。

## 注册屏障与补齐调度

真实 Node 初次注册先同步写入完整 lifecycle 快照。DSH initialize 仍应用本地持久 stop fences 和冻结 schedule，按 Agent 启用或停止仍各自确认。入站 Relay 在快照可信后等待目标 Agent 自己的 transition Promise，不等其他 Agent 的 apply；没有明确 Agent 的管理帧继续走整节点门槛。RuntimeSupervisor onReady 保留基础 host/setup 可用性确认，把可能激活 Global/child 的 Task recoverStops、Schedule deletion、Task 重放、Global 和外部渠道恢复交给启动后的受管恢复任务。目标 Agent 的 stop/schedule 和 native enable/disable fences 不放松。旧节点 connected 标志仍可等待整代控制收口；已经持久启用、host ready 的 B 可先处理自己的 Relay，A 仍显示其自身恢复。Agent 关闭的末尾 Work recordStopped 只影响该 Agent 的 transition。

每个 partition 的后置恢复 Promise 由 Node 保存并合并，记录该 DSH generation，不把旧进程的恢复结论用于新进程。更新沿现有 admitted 计数，关闭时停止新任务，关闭 DSH/relay 使待处理请求退出，最后在关闭 SQLite 与 channels store 之前等待这批受管任务。外部已接收输入按 Agent 各自重放，单 Agent 顺序不变，一个根失败保留其未确认行并复用该根的有界重试；其他 Agent 仍继续。

同一个根的前台恢复和重试各自合并。这个根的可恢复错误不重复启动其他根的恢复。保留节点断线后旧 Work 最终能补齐的契约。已结算且无待办的冷根不在前台扫描子树，也不在启动阶段并发扫所有旧根。后台只运行一个逐根 Work 目录发现，使用 perf-751 的单次遍历并由已确认的 DSH catalog witness 跳过已覆盖正文；同根前台新输入不等待目录补齐。缺少覆盖或确实变化的原生数据才读正文。验收分别统计就绪前后实际冷日志正文读取量、目录核对与首次有工作根的恢复，不能把整段旧正文扫描移到后台后称为通过。

退出标准补一个 Node 组装验证，证明 supervisor 就绪回调和 Relay 生命周期同步已不等待 Global 重放；两个真实 root 在同一 Relay 的阻塞实验验证 B 可收到确认。该实验的 50 是同一 DSH 的已配置规模，故障注入只让两个根实际接单。
