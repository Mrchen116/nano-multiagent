# refactor-655: 工作记录增量恢复与累计用量汇总退役 — 技术方案

> 对齐: motivation.md（含 2026-10-25 同一 unit 追加确认）

## Changelog

## 现状分析

### 涉及范围

- Node 生命周期会调用 UsageReports；PA 从 usage.read 扫描 native session，并经 node.report 存入 IM 累计表。消费者核查及原始 M99/M137/M143 设计见 motivation。
- GlobalAgent 已把产品事件写入 InboxStore journal；WorkSync 用独立 HTTP 通道从中心 ACK 继续发送；IM 保存 sessions/turns/items 并给 Web/iOS 分页读取。处理与传输已有职责边界，缺的是持久处理位置。
- GlobalAgent root 恢复会重新遍历 NodeStore 全部 events；childCursors 和 childModelVersions 仅进程内。DescendantReader 缓存 catalog 和 revision 亦仅进程内；其根观察与 workflow.read 还可能连带读取完整正文及预算来源。
- Work 页原生轨迹是另一个按需入口，当前 JSONL read(offset) 先读取解码全文再 slice，不能宣称范围查询等于范围 I/O。

### 既有约束

只使用 DSH 公开 exports，不 fork/patch/private import。PA/IM 不导入 DSH；产品 journal 只保存可展示事实。保留用户现场，不删除已有累计数据；生产部署另行授权。现有 tool/approval/receipt 权限路径和工作执行模型不变。

### 可复用能力

- 用现有 InboxStore journal 去重、WorkSync ACK 和 IM Work 表；增加小型处理 checkpoint，不能另建完整事件仓。
- 用 sessionPersistence.stat 的公开轻量元数据和 append-only 契约识别冷历史变化。revision 仅同一 service instance 可比，不能把它当跨重启指纹。当前 JSONL 的 sizeBytes + 不变 header 身份可作为同一存储对象 append-only 前缀见证；优先使用可用 eventCount。未知/缺少见证时重新观察该 session，不能假定完整。
- 改 DescendantReader 以持久化关系/catalog 元数据；继续由公开 sessionQuery 提供正文。模型回退与 Workflow 归属来自已有小型 domain 记录，读取展示归属不调用预算重新计量。
- 原生 session.ensure 仍负责真正继续执行时的恢复；轻量历史检查不能触发 ensure，也不能替代在途执行的原生恢复。

### 相关历史

refactor-460 删除累计 UI；refactor-581 保留生产者。perf-650 优化进程内累计读取，但没有产品消费者；bugfix-643 的 DescendantReader 只避免同进程重复冷读取。本次替代累计优化方向，并补全工作记录跨重启处理位置。

## 架构总览

累计链整体退役。Work 保持 `原生事实 → PA 产品投影 → 持久 journal → WorkSync → IM Work 表 → 分页客户端`。新增持久处理 checkpoint 位于 journal 所在 SQLite；DSH 侧仅保存关系/catalog 和原生前缀见证。处理成功与传输 ACK 分别推进。完成的冷执行通过元数据检查，实际变更或未完成执行才读取正文；客户端查看现有记录不访问原生日志。

## 关键决策

**删除累计汇总的全部运行消费者，不删除仍在使用的原生用量和父子归属。** 删除 usage.read、UsageReports、usage outbox、node.report handler、累计查询与新库建表。保留聊天气泡、Work、Workflow budget，以及 reporting_enabled 设置。本次不做无关设置清理。

**处理 checkpoint 随产品记录持久化，传输位置继续归 WorkSync。** checkpoint 至少含 session/root、observedThrough、可重放的未完成逻辑轮次起点、modelVersion。完成轮次不重复投影；进行中的轮次允许从其起点幂等重放，以保持工具配对、模型回退和 Token 计算上下文。不得推进至尚未保存的展示事实。

**关系/catalog 持久化但不持久化完整原生正文副本。** 复用 DSH storageDomain 公共设施保存每 session 的父子边、catalog、原生 cursor、轻量前缀见证。live 事件及 catalog 观察更新已知 root 映射；session.event 和 model.changed 都能在父 session 卸载后找到受信 root。首次升级缺少 checkpoint 时允许一次受控补建，之后普通重启不再全树正文重建。

**冷检查与执行恢复分离。** 已有完成 checkpoint 且无原生新增、待处理输入/控制/审批/交付的全局 root 可延后 session.ensure；原生在途或新输入照常恢复。每个已知子执行仍可作轻量 stat，不靠“已同步过”永久忽略后续改变。根、子和 catalog 都检查，避免原生追加后产品尚未写入的崩溃窗口。

**保持实时投影与现有查询。** 工具开始和结束继续触发增量 reconcile 与 WorkSync。实时路径只处理新片段及未结束轮次，完成旧轮次不反复遍历。历史补建独立于新输入及必要控制，不能阻塞主发送路径。中心分页仍直接读取产品表；原始轨迹仍按具体执行查询。

## 接口与数据流

### DSH integration

- DescendantReader 接收消费位置，返回变更子执行与 throughSeq；持久 catalog 恢复后，元数据见证一致且消费位置已覆盖时返回空事件，不打开正文。
- 为 root 恢复提供受信绑定下的轻量 Work 检查（例如 `session.work.check`），返回是否有未处理正文/未结束执行及可用关系状态；不 hydrate Agent，不暴露任意 session。GlobalAgent 只在检查不能证明完成、或产品仍有执行义务时走原有 main/ensure/reconcile。
- 前缀见证必须与同一次观察 cut 一致：观察前后在同一实例核对 revision，且 live flush 成功；并发追加导致不一致时不记录“完整”见证。跨重启只比较公开的持久大小/计数与不变 header，不复用进程级 identity/revision。
- 冷模型回退投影从现有持久 ModelRun 记录读取，不能因为 agent 未 attach 返回空列表而强制全历史重放。Workflow 子归属读取持久 run 元数据，不调用 spent。执行预算路径继续使用原实现。
- 归属关系来自受信绑定的原生 catalog 或 live parent 链，不采纳继承前缀中的无关 catalog；诊断分支不伪造成功或越权。

### PA checkpoint 与 journal

- InboxStore 增加小型 work projection checkpoint 表及批次提交方法。稳定 event_id 继续为 `session:runtime:seq` 或现有业务键。先写产品记录再提交处理位置；以同库事务完成无网络的投影批次，网络回执独立保留已有 outbox 语义。
- root 的已接收 native cursor（NodeStore）不能替代 Work 处理位置。两库之间崩溃后，从 NodeStore 已持久但未投影的部分补齐；原生已写、NodeStore 未写时由原生见证变化检出。
- 子执行保存 observedThrough/modelVersion 和未结束轮次边界，替换内存 childCursors。不把子执行继承上下文写进 NodeStore 或 journal。收到变更正文时仅投影缺口和开放轮次；失败不提交新的 checkpoint。
- 模型回退可能改变逻辑轮次的映射；开放逻辑 run 覆盖其所有物理 attempts。modelVersion 改变时允许重放受影响逻辑 run，稳定 event_id 保证不增重复。
- 新增 processing pending 标记只表示展示记录尚待核对，不表示原生执行失败。崩溃后保持 pending，成功核对完成再清除。恢复与实时触发共用每 root 串行 drain，主与子继续独立，避免历史读取挤占发送。

### 同步状态与客户端

- 复用 WorkSync HTTP 请求携带 journal 已产生的最高序号和是否仍在处理缺口；中心保存同 node/journal/注册 epoch 的进度声明，结合 through_seq 得出 `current | catching_up | unknown`。缺少新 epoch 的声明和离线时是 unknown，不能把旧 ACK 当成最新完整。
- Work API 增加可选记录同步状态；未升级客户端忽略新字段，未升级服务端时新客户端按 unknown 解释。这里只为升级期正常 JSON 字段缺省，不保留已退役累计协议。
- Web/iOS 在现有 Work 状态位置显示一行：补齐时“工作记录正在补齐，当前显示已保存内容。”；在线但未确认时“当前显示已保存记录，最新进度尚未确认。”；完整时不加干扰提示。离线沿用现有提示，不叠两条。
- 不新增统计口径、按钮或阻断遮罩。现有轮次、工具状态、主子导航、分页和原生轨迹不重排；记录刷新沿用当前持续查询机制。状态不进入普通聊天。

## 前端原型

[prototype.html](prototype.html) 仅展示 Work 记录模式现有工具栏、最近用量、工作轮次与新增状态行；native 模式和工具明细沿用现状。Web 桌面与窄屏同一行自然换行；iOS 在现有状态说明区采用原生正文/次要文字，不引入新卡片。目的只是辨认当前看到的是已保存记录和是否仍在补齐。

| 区域 | 对齐级别 | 用户结果 | 验证 |
|---|---|---|---|
| 状态行 | must-match | catching_up / unknown 可辨认，current 隐藏，离线不重复 | M1 reviewer/worker |
| 最近已报告的主上下文 | must-match | 最近已报告语义及数值保留 | M1 reviewer |
| 主子过程、分页、原生轨迹 | may-adapt（实现不重排） | 持续更新和既有阅读位置保持 | M1 reviewer |

2026-10-25 已在 IAB 实际渲染约 319px 窄屏并切换四种状态：两条在线说明自然换行，current 隐藏状态行，离线仅一条说明，统计和工具/分页入口仍在。截图保存在本机 `/Users/czj/.codex/reports/refactor-655/prototype-narrow.png`（不提交缓存）。对照当前 Web toolbar/callout 与 iOS 状态说明的位置，仅增同级文字，不改变列表结构。桌面完整产品视觉留给 M1 验收；本轮窄屏是新增文本最容易拥挤的范围。

## 契约层增量 (delta-spec)

- IM auth-tenancy：移除累计 metrics 的示例与 owner 查询场景，其他授权契约完整保留。
- IM agent-work：新增持久记录增量恢复和同步状态场景，既有工具/统计/轨迹契约不变。
- Gateway service-lifecycle：退役累计协议，通用断线示例换成有效请求；其他恢复职责不变。

## 风险与回退

- 首次升级缺少元数据会做一次历史补建，部署记录必须区分 bootstrap 与正常重启；不能以旧库首启代表优化失败，也不能把首启开销隐去。
- 对实际改变或进行中的原生 session，公开 JSONL API 仍可能读/解码完整正文（含继承前缀），范围 slice 仅减少处理/传输量。这是剩余上游能力限制；本次保证不变完成历史不读正文，不声称任意原生范围读已成为 O(delta)。
- stat 见证缺失、不可比或变化时只恢复该不确定分支，不能跳过潜在缺口。元数据版本变化做显式重建，不静默信任未知版本。
- 回滚须成套恢复旧 Node/IM，保留新小型元数据表及旧累计表，不 DROP；旧版本可忽略新状态字段。

## 一次性部署迁移

见 [deployment-prompt.md](deployment-prompt.md)。停止旧节点上报后协调更新；首次补建完成后再测普通重启。本次仅副本验证，不执行生产。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 检查 |
|---|---|---|---|
| 隔离 Node/DSH + IM | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$WT_ROOT"` | 隔离 IM /openapi.json，真实消息及 Work API |

**Review 驱动方式**：真栈。数据不变性通过客户端同一消息/Work/分页接口及真实 DSH 驱动；新增状态行需实际浏览器桌面/窄屏验证。iOS 采用模型解码/视图定向编译核对同字段和语义，新增纯状态文字不要求重复完整双端业务旅程。

**验收前置**：仓库 Node 24/pnpm、主仓 .venv；可用的隔离 fake Anthropic provider fixture 提供确定计数及工具/子执行；不得连接生产身份。原始详情必须走公开 trajectory 查询。计数在测试包装公开 persistence/sessionQuery seam，分别统计正文获取次数、实际原生事件数与产品投影事件数；不把 stat 次数混入正文读取。可复用本机 recovery-plan/replay 调查资料，生产数据不提交。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-retire-and-recover | 累计退役与 Work 持久增量恢复 | 无 | 无 | integration、PA、Node、IM、Web/iOS 状态行、相关测试和 canonical | [reviewer] 真栈主子工具实时开始/完成/失败、参数结果、Token 和历史重启前后一致；补传状态明确，消息/控制不被历史阻塞；分页及原始详情可用。[worker] 删除链无生产引用；保留 Workflow budget、聊天气泡；native→journal→ACK 各崩溃窗口无丢失重复；完成历史增长后的普通重启正文读取为零（不含实际需执行的主会话 hydration），只变更分支补读；首次升级/回滚副本验证；窄测试、本地 CI、独立门禁及远端 CI 通过。 |
