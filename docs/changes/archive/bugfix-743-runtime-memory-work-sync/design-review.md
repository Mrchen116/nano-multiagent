## Round 1

- Reviewer target: `/root/design_review`，独立审查 `a2c98e7cc`。
- review_mode: full
- mode_reason: 首轮。覆盖历史驻留、Work 数据面和双向 stdio 生命周期。
- started_at: 2026-11-09T19:33:34+08:00
- completed_at: 2026-11-09T19:35:30+08:00
- duration: 116 s
- Verdict: Issues Found，0 CRITICAL / 4 WARNING

### Coverage

- 从 `apps/node/src/main.ts:378` 的 Global 产品组装和 `packages/dsh-integration/src/client.ts:20` 的正式 Nano profile 核对了实际落点。锁定版 DSH 的公开 `sessionQuery.observeSession` 在 projection cache 未挂载时会从原生事件 hydrate，原生轨迹继续经过现有绑定和查询层。未见审批证据需要依赖缓存成为事实来源。涉及冷标题或子目录的模型消费验证可以复用现有入口，比较实际工具结果与原生记录。
- 工具冻结记录适合继续复用原格式和 `RecordWrites`。公开 `JsonStorageBackend.kv` 打开 per-record 单元可定点写删；批量读由 `loadAll` 单独触发。一个 Nano adapter 足以拥有定点读取和按键枚举，免去全域打开。旧文件继续可读，无需一次性迁移。普通删除仍需验证停挂缓存后按目标身份移除旧记录和备份。
- 活会话的公开 `Session.eventAt` 和 `snapshotEvents(from,to)` 可以避免在 Nano 层先复制整段历史。锁定版 JSONL 的 `SessionHandle.read(offset,length)` 底层仍可能读取并解码整个冷日志；设计已披露这一原生读成本。Work 的分页证据应分开测量原生日志读取、页装配和实际 stdio 字节。冷观察只按条数缓存，冷查存在单日志体量带来的峰值。
- 采用现有 Node ledger、Inbox SQLite、独立中心 ACK 及真实 native seq，职责方向与架构一致。对照 `work-projection.ts`、`presentation.ts` 和 current IM Work 契约，delta 锚定了正确的 Requirement 并保留已有三个 Scenario。跨页工具配对、用量与 fallback 结束去重依赖持久的未完逻辑轮上下文，需与 checkpoint 一起在真实产品链路验证。单个 milestone 可完整承载；产品旅程应覆盖中心 Work 的既有读取结果、跨页恢复、停用与权限负例。页面行为沿用当前契约，无需要提前对齐的原型。未运行实现或生产服务。

### Issues

- **R1-W1 — Work 页预算遗漏随历史增长的回复数据。** `design.md` 的页预算只约束所选 own 事件及工具展示。现有 `packages/dsh-integration/src/index.ts:191`、`:511`、`:523`、`:531` 对整个会话的 fallback runs 做 JSON hash、clone 并传输，根读还携带审批历史，子读会为整个可达目录生成回复行；`model-fallback.ts:29` 的 pending run 可含原始消息正文。即使只追加一条事件，长会话仍能反复序列化整份 sidecar 或生成超过页上限的空目录页。明确所有 Work 相关回复的包络及游标上限，按相关切点有界传递模型变化和必要目录，分离消费者不需要的审批数据，并避免每页或 settled 检查重算整段历史。用已有大元数据、仅追加一条和仅模型状态变化三种条件检验实际帧大小与配对。
- **R1-W2 — 根观察兼任实时业务证据，单次返回部分页会改变现有调用语义。** `packages/personal-assistant/src/single-thread.ts:257` 一次观察后即决定交付；`global-agent.ts:599` 和 `:696` 的非 Global Task Graph 与发消息路径分别依赖当前人类输入与工具调用证据；`:362` 的后台唤醒只需状态。原设计只描述 Work 页消费。若原方法统一改为一页，这些现有路径会在当前证据位于后页时使用旧数据；若保留原调用语义，它们还会生成旧的大帧。明确各入口是消费有界页到需要的证据、使用定点证据，还是只读状态。超过 Work 页上限的旧事件也不能阻塞这些实时入口。隔离验收应让当前证据落在后页。
- **R1-W3 — 停用最终页缺少可重试的确认协议。** `apps/node/src/main.ts:525` 目前从一次 `disableAgent` 结果保存终态再向生命周期返回确认；`packages/dsh-integration/src/index.ts:838` 缓存整个 disable promise，并且普通 Global 恢复跳过 disabled Agent（`global-agent.ts:395`）。把终态快照直接截成一页会在后续页尚未持久提交时确认停用，断开后普通恢复无法补齐；复用旧 promise 也不能按新 checkpoint 取得下一页。设计需要明确定义可重试的 cleanup 回执和停用后的只读分页入口，说明最终目标切点、断线重进，以及 Work pending 与生命周期确认各在哪一步更新。至少验证停用前尚有多页及第一页提交后断线。
- **R1-W4 — 本地 RPC close 不会触发当前 supervisor 重连。** `packages/dsh-integration/src/rpc.ts:59` 只关闭本地 readline 并拒绝 pending，不拥有或关闭 stdio；`client.ts:173` 的 supervisor 以子进程退出为恢复触发。若队列上限或 drain 故障只走 `RpcPeer.close`，父子可能维持进程存活而无法再次处理请求。明确过载与写故障如何到达实际连接/进程生命周期，关闭时释放 drain 等待和排队工作。隔离测试须触发上限或写故障并观察 supervisor 重新可用、从已提交页继续，不能只测 write 返回 false 后恢复 drain。

### Author Resolutions

- W1 accepted：改为整页计费和目录续读，按页携带相关公开 model run；Work 根读取不携带审批列表。
- W2 accepted：专用 Work 页与既有证据读区分；状态独立读取。
- W3 accepted：取消/释放与冷 Work 读分开，停用结果不携带全历史；保持范围和可重试位置。
- W4 accepted：明确关闭和故障如何抵达 RuntimeClient 与 supervisor。

## Round 2

- Reviewer target: `/root/design_review`，独立复审 `9b45b4d29`。
- review_mode: delta
- mode_reason: Work 私有接口、停用确认与 stdio 故障连接有实质修订。原生审计、工具冻结存储、delta-spec 与单 milestone 保留 Round 1 覆盖。
- retained_from: Round 1
- started_at: 2026-11-09T19:36:41+08:00
- completed_at: 2026-11-09T19:37:51+08:00
- duration: 70 s
- Verdict: Issues Found，0 CRITICAL / 3 WARNING（3 项沿用，1 项已关闭）

### Coverage

- 新版为 Work 设独立根入口，以可信绑定和目录校验读范围；预算纳入目录、presenter 与精简模型元数据，保留显式 throughSeq / more。根审批继续由原证据入口持有。传输端单个 Work 读取跨写屏障、独立 dispatch 和故障信号到子进程退出，闭合 Round 1 的响应侧和进程所有权缺口。
- 对照实际入口，复核了请求侧位置、Global 工具证据、Node 生命周期与 supervisor 恢复。没有改变首文档和用户可观察 delta，上一轮的原生轨迹和存储设计判断仍适用。本轮为设计复审。

### 历史问题闭环与 Issues

- **R1-W1 — still-open。** Author Resolution 增加了完整回复预算、目录 anchor、增量模型摘要和独立审批路径，回复侧的问题关闭。请求仍缺边界。`packages/personal-assistant/src/global-agent.ts:830` 的 `workPositions` 将所有子执行的 checkpoint 和模型版本装进请求，`:406` 的 settled 检查与 `:909` 的目录补传共用；新版没有规定该参数如何随 anchor 分页。若直接复用，宽目录每页重复序列化整份位置，单个请求仍随历史子执行数增长。明确一次请求携带的位置上限及 settled 检查的有界取法，以跨多目录页的宽目录覆盖请求和回复实际字节。
- **R1-W2 — still-open。** Author Resolution 保留单线程及非 Global 的旧证据语义，并把后台唤醒改成只取状态。Global 的 Task Graph 和发送仍分别在 `global-agent.ts:603`、`:697` 等待 `reconcileRoot`。新版 `design.md:13` 明确超限页停在原位置，若历史超限记录在当前调用证据之前，Work 补传失败会让后续 Global 发消息和 Task Graph 一起失败。明确 Global 取当前工具调用、轮次及来源证据的有界路径，使它可独立于 Work 补传前缀成功；验收应覆盖超限旧记录及其后的实时调用。
- **R1-W3 — still-open。** Author Resolution 将 cancel/flush/dispose 与有界冷读分开，并按 Agent、revision、稳定切点校验。新版 `design.md:15` 依赖重试停用流程，但 `apps/node/src/main.ts:132` 的 runtime-only 重连只触发常规产品恢复，`global-agent.ts:395` 会跳过 disabled Agent；生命周期同步在 IM relay ready 触发（`main.ts:289`）。若已写生命周期 stopped proof，同 revision 的下次同步也只重报 disabled（`apps/node/src/agent-lifecycle.ts:44`、`:69`）。明确生命周期回执与 Work 完成标记的各自时点、哪个持久状态标记未补完，以及 supervisor 重连时的重入点。验证 IM relay 一直在线、停用第一页已提交、DSH 进程断开后自动恢复的场景。
- **R1-W4 — closed。** Author Resolution 已规定写故障、排队溢出及关闭时释放队列与未决调用，并让 `RuntimeClient` 把真实链路故障接到子进程退出和已有 supervisor 恢复（`design.md:16`）；正常 shutdown 和双向独立 dispatch 保留。落地后复用慢写和 supervisor 重连验收。

### Author Resolutions

- W1 accepted：分页目录与单目标事件请求分开，根探测只带根 cut。
- W2 accepted：保持既有可处理记录能力，超常规预算的单项独占，不引入会阻断后续取证的新门槛。
- W3 accepted：本机保存原执行进程的 revision-scoped cleanup receipt，先于分页且独立于已停证明；就绪后异步重试，以免等待正在启动分区的同一停用任务。

## Round 3

- Reviewer target: `/root/design_review`，独立复审 `80a0fb55f`。
- review_mode: delta
- mode_reason: 复核 Round 2 留项及相应目录请求、页预算和本机停用回执改动。
- retained_from: Round 1（历史驻留、审计与 delta-spec）；Round 2（响应包络、stdio 故障恢复及 R1-W4）。
- started_at: 2026-11-09T19:38:01+08:00
- completed_at: 2026-11-09T19:39:00+08:00
- duration: 59 s
- Verdict: Approved，0 CRITICAL / 0 WARNING

### Coverage 与历史问题闭环

- **R1-W1 — closed。** Author Resolution 将目录发现与单子会话分页分开。`design.md:12` 规定目录请求只带当前 anchor、子事件请求只带可信 child ID 和单会话位置，`session.work.check` 只带根位置。方案消除了 `global-agent.ts:830` 的全量位置表进入 Work 检查和补传请求的路径；Round 2 确认的回复预算保留。验收仍须用宽目录检验双向帧边界。
- **R1-W2 — closed。** Author Resolution 移除了新硬上限。`design.md:13` 允许超过常规页预算的完整单条独占一页，消除历史记录被新门槛拒绝后阻断 Global 工具证据路径的问题。单线程及非 Global 维持原证据契约，中心 16 MiB 规则照旧。实现验收应覆盖后页业务证据、单条超常规页预算及中心行为。
- **R1-W3 — closed。** `design.md:15` 要求冷页前先保存与原执行进程和停用 revision 对应的本机 cleanup receipt。旧执行进程 cleanup 成功的证据由此能跨 DSH 重启保留，仍按 `apps/node/src/agent-lifecycle.ts:102` 的安全意图验证原身份；新管理进程可从已提交 cut 接续，最后一页提交前不写最终已停证明。分区 runtime 就绪后异步重试未确认 revision，不等待 relay 重连，也不会将等待当前启动的停用操作放回启动屏障。实现验收须覆盖同一次机器启动、原进程 cleanup 成功且第一页已提交后 DSH 断线，以及旧进程没有 cleanup 证据时仍不确认的原边界。
- **R1-W4 — closed，retained from Round 2。** Transport 约定未变。

### Issues

无。本轮判断为设计可实施；运行证据留在 M1 隔离验收。

## Round 4

- Reviewer target: `/root/design_review`，独立复审 `eac2f5b56`。
- review_mode: delta
- mode_reason: Work 页生成从一条串行通路改为根与子两条通路。复核根取证、页驻留和共享写出屏障。
- retained_from: Round 3（审计、存储、游标、停用恢复、delta-spec 及此前问题闭环）。
- started_at: 2026-11-09T20:04:23+08:00
- completed_at: 2026-11-09T20:04:53+08:00
- duration: 30 s
- Verdict: Approved，0 CRITICAL / 0 WARNING

### Coverage

- `global-agent.ts:599`、`:693` 的 Global Task Graph 和发消息仍等待 `reconcileRoot`。其实际请求 `session.work.root` 与目录、子事件读在 `packages/dsh-integration/src/index.ts:544` 分配到不同通路。根处理可以在子会话等待冷读时开始。权限和持久切点约定沿用已批准版本。
- `packages/dsh-integration/src/rpc.ts:157` 将各通路的占位保留到共享 FIFO 的写出屏障完成，`:109` 在写端阻塞时停止后续序列化。根与子各最多物化一页，实际写入仍受同一个 writable 的 drain 约束；反向调用、控制处理和关闭恢复沿用原方案。更新后的 `rpc-backpressure.test.ts` 覆盖输出停住时根页仍能生成、同一子通路的下一页仍等待以及 FIFO 次序。本轮以源码和验收方法为设计证据。
- R1-W1 至 R1-W4 保留已关闭状态。未发现新的设计问题。

### Issues

无。
