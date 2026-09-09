# Design Review: feat-546

## Round 1

### Metadata

- reviewer: /root/feat_546_design_reviewer
- review_mode: full
- mode_reason: 首轮独立审查，没有历史 Round；覆盖全部五类承重原子和四个架构进攻角度。
- started_at: 2026-09-09T18:28:17+08:00
- completed_at: 2026-09-09T10:43:05.000Z
- duration: 14m 48s (888s)
- checkout: /Users/czj/Repos/nano-multiagent，branch main，HEAD 07a4342d4153e06a8e4a2045601a58a27a9aed36；未刷新远端。
- input_state: feat-546 为未跟踪设计目录；其他 dirty/untracked 内容全部保留，只新建本报告，不实施、不提交。
- method: 读取首文档、design、两份组成契约、全部 7 份 delta、acceptance-map、prototype、M1 骨架；从生产入口正向追源码。原型做静态交互/字段核对和 JavaScript 语法检查；没有运行产品旅程或操作生产服务。

### Verdict

Issues Found — **2 CRITICAL / 1 WARNING**。尚不能进入实施。持续主 Session、按需 Inbox、显式发言和独立工作记录的方向成立；需先闭合 canonical 作用域、正文持久摄取证据及 signal 生成条件。

### Issues

- **[R1-C1][CRITICAL] [Canonical delta-spec / D5、D7、D10、D11] 新模式改变现有无条件契约，却只用 ADDED 新条目覆盖。** specs/gateway/global-agent.md:5 和 specs/gateway/agent-capabilities.md:5 均只 ADDED，且没有 routing-delivery delta。current docs/specs/gateway/routing-delivery.md:69–80 要求回原通道及跨聊天并行，:178–205 要求 /new 换会话，:263–299 要求忙时插话摄取/原聊天展示，:344–366 明确“每个聊天只延续自己的历史……不读取其他聊天内容”，:396–410 要求后台综合回复及 sidecar 回原聊天；全局模式有意替换这些语义。current docs/specs/gateway/agent-capabilities.md:221–239 还要求白名单恰为运行工具集、显式空集没有工具，与 runtime-contract.md:27 的固定四项并集冲突。现有代码确实走这些旧行为：src/personal_assistant/gateway/inbound_pipeline.py:178–245、product.py:376–392。应对受影响的最窄 canonical Requirement 用 MODIFIED 明确 single_thread/global 作用域，完整保留原 Scenario，并核对相关 IM 气泡/后台展示契约（例如 docs/specs/im/gateway-relay.md:116–147）是否也需模式限定。不能依赖新 area 隐式凌驾旧规则。**不改：worker 面对互斥验收要求，归并后 current 同时承诺聊天隔离与共享、真白名单与自动扩宽。**

- **[R1-C2][CRITICAL] [D3 / runtime-contract §2 / SDK 观察接口] 消费确认需要的“实际已持久序列化内容”没有可用的观察字段。** runtime-contract.md:78–80 要求 durable append 后按 session_id + call_id + receipt_id + content_digest 确认实际 parts，且序列化失败不确认。真实顺序确为 loop yield → runtime durable append → tool_result hook（src/agent/core/agent/loop.py:618–633、runtime.py:727–732），但 hook 仅传原始 ToolResult.output/error/event_metadata（loop.py:935–971），没有实际写入的序列化内容、其 digest 或序列化成功标识；_serialize_tool_result 还会吞掉 serializer 异常并回退（:1017–1023）。SDK 同形流只有 tool_end 的 presentation/error 等字段，不是原始 tool_result（realtime_stream.py:112–145）。work-trace-contract.md:10–22 只新增初始输入 committed，未定义 tool-result 持久内容证明，也未明确这项提交采用产品 hook 还是 SDK observer。返回中的 receipt/digest 或重算原始 output 不能证明实际持久正文。**不改：可能把已回退或不一致的 tool message 标为完整消费，或因根本拿不到约定字段使消息永久待读。** 请明确一个 SDK/HookAPI 合法出口，由持久写入边界提供实际序列化成功事实与可校验身份/digest，并收口消费 hook 注册位置、serializer fallback 与重启重读行为；无需暴露 core 类型或在 Presenter 中确认。

- **[R1-W1][WARNING] [D2、D5 / runtime-contract §2–3] 背景更新是否推进唤醒 signal 的条件仍有两种读法。** runtime-contract.md:49 允许保存可见普通群更新并记录 requires_attention，:50 随后无条件描述“写 Inbox 条目、target 索引及新的 signal seq”；:110 的 pending 判据仅比较 signal watermark，没有 attention 过滤。按具体状态协议实施，MENTION 下普通背景消息也会唤醒，违背 spec.md:263–265 与 design.md:71。current ALWAYS/MENTION 判断明确在 inbound_pipeline.py:353–362。**不改：worker 可分别实现所有条目唤醒或仅 attention 唤醒，使闲聊触发全局运行，或丢掉本应唤醒的信号。** 明确 entry seq 与 effective wake signal 的关系，以及非 attention、sync-only/history catchup、自身回声的推进条件；不需新增优先级机制。

### Recommendations

- [R1-R1] 旧 canonical 只增加必要模式限定并链接全局 area；全局正文集中维护，避免在多个 area 复制新设计。
- [R1-R2] 关闭 R1-C2 后，优先用真实 loop 的 serializer 成功/回退/持久失败三个分支验证同一 receipt 消费结果；不需为各存储字段写镜像测试。

### Coverage

本轮 inventory：design 现状表全部 10 项、trace 现有链/缺口及统计来源；D1–D13；Q1–Q16、7 段用户场景、11 个 Requirement 下全部 31 个 Scenario、全部范围/非目标；7 份 delta 的 17 个 Requirement、67 个 Scenario；唯一 M1；P1–P8 和 J1–J9。下列“成立/覆盖”指设计和前提，绝不表示功能已实现。

路径简写：PA=src/personal_assistant/，K=src/agent/，IM=src/IM/；runtime=runtime-contract.md，trace=work-trace-contract.md。行号来自本轮实际读取。

### 核实台账：现状断言与生产路径

| ID / 断言 | 独立动作与证据 | 结论 |
|---|---|---|
| F1 聊天绑定/入站 gating | 从 PA/gateway/process_lifecycle.py:1010–1012 进入 composition.py:686–734，实际注入 SessionRunCoordinator/InboundPipeline；inbound_pipeline.py:122–178 解析身份/控制并缓冲，:181–245 调控制或 dispatch；session_binder.py:263–287 按 key 复用并更新 ReplyContext | 成立；全局分支落在真实入口 |
| F2 完整配置链 | composition.py:247–254,286–304 装配 kernel/binder/shim；IM/api/routes/agents.py:523,588 调 coordinator；IM/application/agent_config_operations.py:29–34,301–425 处理 allowlist/workspace/profile；PA/config/local_store.py:394,617 持久/加载 | 成立；mode 不能只加 UI |
| F3 durable 后 observe | K/core/agent/loop.py:618–633 yield 后 observe，runtime.py:727–732 对 tool durable append | 顺序成立；内容证明缺失 R1-C2 |
| F4 steer 两步/active 漏 queued | K/sdk/kernel.py:1777–1798 先 try_steer 后 submit；K/core/runs/registry.py:258–300 创建 QUEUED，:595–606 维护 active；executor.py:220–227,283–294 已有 lifecycle/accepted 管理 | 成立；新准入复用真实载体 |
| F5 send 协议/ACK/屏障可复用 | composition.py:871–889 装配 handler；PA/tools/send_message.py:155–187 带真实 ctx/revision；internal_dispatch.py:150–215 验来源并同步 enqueue，:216–247 返回 held/inactive/ACK | 成立；global 扩目标/来源分支 |
| F6 普通 child 无 run_id 被跳过 | K/platform/background_tasks/runtime_runner.py:173 辅助入口；realtime_stream.py:60–62,96–98,115–117,206–208 过滤无 run_id | 成立；只订阅无法补未发布事件 |
| F7 内存流非历史库 | K/core/events/hub.py:54–59,82–108 为 2000 项历史/溢出队列；K/sdk/kernel.py:1936–1954 flatten 不保留外层 event_id/created_at | 成立；同步持久记录是新增 |
| F8 子身份/后台回流 | K/sdk/kernel.py:177–233 验 parent/create child；K/core/background_tasks/notifications.py:19–57,169–191 仅投影 subagent/Workflow；platform/background_tasks/wiring.py:172–224 active 注入/idle submit | 主 parent 路径成立，Bash sidecar 确缺；wiring:187–206 的既有子 parent 限制不应被描述成此次已修复 |
| F9 过程依附 message_id | IM/app.py:340–379 装配 Execution/Relay/EventBridge；IM/ws/gateway/execution.py:249–303 turn_start 返回 message_id，:308 后依赖它；PA/gateway/runtime_delivery/observer.py:717–730 投影 presentation | 成立；独立工作归属有必要 |
| F10 Heartbeat/Cron | composition.py:760–787 实际 scheduler/runner；heartbeat_scheduler.py:320–348 canonical/busy gate；cron_runner.py:126–161 每次隔离 create+origin=cron；cron_execution_service.py:583–674 执行/投递 | 成立；两种来源不能合成同一 Session |
| F11 前端复用点 | IM/frontend/src/app/router.tsx:5,12,31 导入 Chat/Agent detail；chat-workspace-page.tsx:630–670,839 历史页/导航；tool-calls-panel.tsx:434,510、tool-detail-renderers.tsx:696、token-chip.tsx:20、permission-card.tsx:78 | 成立；定位历史需新增真实加载 |
| F12 Presenter 两阶段 | realtime_stream.py:101–109,127–144 生成 arguments/duration/reason/approval/detail，observer.py:717–730 映射 | 成立；无需前端猜结果 |
| F13 transcript 不含完整 UI 元数据 | K/core/session/transcript.py:883–924 白名单无 duration/approval/完整 turn usage | 成立；不能当工作历史库 |
| F14 usage 口径 | K/core/agent/loop.py:1375–1392 最新 prompt/累计 completion；realtime_stream.py:216–222 上送 usage/window；对照 trace:258–270 | 一致，主子不加总/未知不当零 |
| F15 外部普通群消息可到 pipeline | PA/channels/feishu/adapter.py:249–268,466–483 都调用 handler；:306 history catchup 标 sync_only；composition.py:268–275,734–744 接同一 dispatcher | 成立；signal 规则另见 R1-W1 |
| F16 relay/watchdog 真实存在 | IM/ws/gateway/relay.py:52–89 持久 receipt，IM/app.py:390–404 起 watchdog，current im/gateway-relay.md:116–147 规定后台气泡 | 成立；模式契约归并见 R1-C1 |

### 核实台账：D1–D13

每行均核是否拍死、是否和其他决策兼容、是否有 spec 驱动及是否遵守实际分层。

| 决策 | 核实动作与证据 | 结论 |
|---|---|---|
| D1 通知/正文分离 | runtime:61–66,70–80 check/read 页；spec:215,252–261 | 完整，无强制批量摄取 |
| D2 注意力/配置 | spec Q3:64–72、runtime:49–50,68,110、_should_process | 方向对齐，signal 歧义 R1-W1 |
| D3 精确消费 | runtime:38–39,74–80 与实际 durable/hook/serializer 三个边界 | 分段/稳定 ID 合理；R1-C2 |
| D4 新工具/既有工具边界 | runtime:13–15,55–78,139–145、trace:218–245；K/sdk/__init__.py:23 提供 HookAPI/Tool | schema/预算/错误/权限已选，不混外部派工权限 |
| D5 主上下文/事件唤醒 | runtime:90–116 收据/水位/准入，spec:215–217 | 架构成立；canonical/signal 待修 |
| D6 目标复核 | spec Q11:159–165、runtime:127–135、internal_dispatch.py:193–228 | target→publication、enqueue 界限/锁外 ACK 已选，无远端强一致 |
| D7 /new | spec:167–173,339–348、runtime:120 | 明确拒绝且保留上下文；旧 delta R1-C1 |
| D8 /stop | spec:175–183、runtime:121、registry.py:329,522 | 停主、不新增子级联，保留旧通知 |
| D9 /compact | spec:185–191,370–374、runtime:122、executor.py:220–227 | 串行主 Session/focus/幂等，不遍历子 |
| D10 工作归属 | spec:219–223,289–303、trace:48–64,202–210，真实 Chat 组件 | 独立存储/权限/导航闭合；旧展示范围 R1-C1 |
| D11 固定基础工具 | Q15:193–201、runtime:25–27、current agent-capabilities:221–239 | 需求和选择明确；旧真白名单未修改 R1-C1 |
| D12 持久观察/IM 投影 | F6/F7/F9/F13、trace:10–64 callback/ACK/REST/WS | 必要持久链，无无限 stream 假设；正文证明 R1-C2 |
| D13 自动来源 | F8/F10、runtime:149–153、trace:145–171、K/core/runs/origin.py:8–17 | Heartbeat 主线/Cron 独立，active 不改触发标题 |

### 核实台账：澄清、用户场景与非目标

| 澄清 | 实际意图与落点 | 结论 |
|---|---|---|
| Q1 | spec:48 连续认知 → D5/runtime 主 binding | 覆盖 |
| Q2 | spec:60 忙时自主/空闲唤醒 → D1/D5 | 覆盖 |
| Q3 | spec:72 普通更新按配置 → D2 | R1-W1 |
| Q4 | spec:82 单上下文/按需 subagent → D5/prompt:174–184 | 覆盖 |
| Q5 | spec:92 可以自己做 → prompt:174–178 | 无强制委派 |
| Q6 | spec:96,104 成员身份提议未确认 → 无独立群成员 | 未越界 |
| Q7 | spec:115–119 群进展工具主动发，工作另看 → D10 | 无自动播报 |
| Q8 | spec:127–129 主子关联 → trace:18–24,108–113 | 覆盖 |
| Q9 | spec:137–139 不做独立 Task → runtime:43 | 未越界 |
| Q10 | spec:147–157 创建后模式固定 → runtime:9,23–25 | 覆盖，旧 Agent 默认 single_thread |
| Q11 | spec:163–165 内置目标群已接收范围 → D6/runtime §4 | 覆盖 |
| Q12 | spec:171–173 拒绝全局 /new → D7 | 覆盖 |
| Q13 | spec:181–183 触达 Agent 停主，子沿旧规则 → D8 | 覆盖 |
| Q14 | spec:189–191 compact 主上下文 → D9 | 覆盖 |
| Q15 | spec:199–201 四项加默认工具 → D11/P1 | 覆盖目标，R1-C1 |
| Q16 | spec:205–209 具体工具/token/来源 → trace 字段表/P2/P3/P5 | 有逐字段来源，消费证明 R1-C2 |

| 用户场景段 | 核实落点 | 结论 |
|---|---|---|
| spec:213 创建/实验模式 | runtime §1、P1/J1 | 覆盖 |
| spec:215 连续认知/读取/触发 | D1/D2/D5、J2/J3 | 目标覆盖；R1-W1 |
| spec:217 A/B 补充、委派跟进/并行 | design:169–184、J2、prototype:121–144 | 无派出即完成 |
| spec:219 交流/内部过程分离 | runtime:135、D10 | 覆盖 |
| spec:221 反复复核/排除边界 | runtime §4、J4/J9 | 覆盖 |
| spec:223 员工整体/子执行 | trace REST/归属/来源表、P2/P3 | 覆盖 |
| spec:225 不建 Task | runtime:43、design:11 | 未越界 |

| 范围/非目标原子 | 核实证据 | 结论 |
|---|---|---|
| 新建模式/全局/Inbox/配置 | spec:409 → D1/D2/D5/D11 | 目标覆盖，signal 待修 |
| 自行执行/委派、原聊天显式回复 | spec:409 → design:174–190 | 覆盖 |
| 主子轨迹/目标草稿 | spec:409 → trace:194–200,244 | 覆盖 |
| 不迁移已有 Agent/不切模式 | spec:411 → runtime:9,25 | 未越界 |
| 不合并旧历史 | spec:411 → runtime:25，历史工具按需读 | 未越界 |
| 不用聊天或替代入口重置全局 | spec:411 → D7 | 未越界 |
| 不建 Task/看板/认领/指派/完成凭据 | spec:411 → runtime:43 | 技术 receipt 只证明摄取/提示 |
| 不引入 Joint Channel/App 平台 | spec:411 → 模块和工具清单 | 未越界 |
| 不仲裁 Gateway 未接收远端消息 | spec:413 → runtime:131 | 未越界 |
| 不扩 DM/外部/shadow、不强发/要求重新触发 | spec:413 → runtime:129–133，J4/J9 | 未越界 |
| 实验不容许串线/丢轨迹/不交付 | spec:415 → trace 持久链/prompt/J2/J7 | 目标保留；R1-C2 是落地缺口 |

### 核实台账：首文档全部 Requirement / Scenario

| Requirement（首文档起始行） | Scenario（原标题） | 具体设计/验证落点 |
|---|---|---|
| 模式选择 229 | 新建全局 Agent | runtime:9,23–25；J1/P1 |
| 同上 | 保留单 Thread 方式 | mode 缺省 single_thread/旧 coordinator；J1 |
| 同上 | 不提供模式切换 | 服务端拒绝改模式，prototype:68–69 只读 |
| 连续认知 243 | 使用另一个聊天中已读取的相关条件 | 单 binding，J2，prompt:145–147；canonical R1-C1 |
| 接收/读取 250 | 忙碌期间有其他聊天的新请求 | runtime:90,110–114 忙时零注入，正文保留 |
| 同上 | 空闲时收到符合触发条件的输入 | runtime signal/drain/receipt；R1-W1 |
| 同上 | 普通群聊更新遵循各 Agent 配置 | requires_attention/_should_process；R1-W1 |
| 统筹委派 267 | 委派实质工作并跟进交付 | prompt:169–184、J2、prototype S1 返回/发言 |
| 同上 | 保留主 Agent 自行处理的能力 | prompt:174–176/D11 默认工具 |
| 同上 | 多项工作独立推进 | prototype:132–144 的 S1/S2、trace 独立 Session |
| 同上 | 外部通信能力不等于派工权限 | prompt:149–152、J5，内部 child/外部 IM Agent 分开 |
| 交流/工作分离 289 | Agent 向聊天报告进展或结果 | runtime:127–135 显式 send+ACK；J2/J6 |
| 同上 | 查看员工整体工作 | trace:54,68–70；P2 |
| 同上 | 深入查看 subagent 工作 | trace:55–56,108–110；P3/J6 |
| 目标群复核 305 | 没有新消息时正常发言 | runtime:131 target 检查后 enqueue |
| 同上 | 目标群的新更正被考虑 | runtime:129 withheld、prompt:192–194 |
| 同上 | 复核期间又收到适用的新消息 | 每次 send 都取 target 接收锁；J4 |
| 同上 | 其他群及仅作背景的更新不阻塞发送 | runtime:133，不用全局未读总数 |
| 同上 | 草稿和复核归属员工工作视图 | trace:244、prototype:115–118，草稿不进群 |
| 同上 | 单聊和外部聊天不新增复核 | runtime:133/J9 |
| /new 337 | 全局 Agent 收到重置命令 | runtime:120；J1/J5；旧规则需 R1-C1 |
| 同上 | 单 Thread 模式继续使用重置命令 | 原 coordinator 保留；J1 |
| /stop 350 | 从一个聊天停止跨聊天工作的 Agent | runtime:121 主 Session interrupt/来源反馈 |
| 同上 | 停止范围由既有路由决定 | 保留入站 gating/agent resolution；J5 |
| 同上 | subagent 停止规则不因全局模式改变 | D8/runtime:121 不遍历 task_stop |
| compact 368 | 从聊天压缩全局主上下文 | runtime:122、executor lifecycle |
| 固定工具 376 | 新建全局 Agent 时保留正常执行能力 | runtime:27 并集、prototype:242–243 默认说明 |
| 同上 | 固定基础工具与可配置工具区分 | 四项不可关，其他沿原选择；R1-C1 |
| 执行明细 389 | 查看主 Agent 与关联子 Agent 的具体执行 | trace:175–200,218–247；J6 |
| 同上 | 查看轮次统计及未完成状态 | trace:258–287、prototype usage null/权限/失败/离线 |
| 同上 | 刷新后回看同一执行过程 | trace:26–64 journal→ACK→projection；J7 |

acceptance-map 的 31 个 Scenario 与首文档标题一一对应，均落 M1；J8/J9 补充自动来源/外部边界。没有缺 Scenario、偷加第二个 milestone，也没有以静态原型当通过证据。

### 核实台账：delta-spec 全部条目

逐条核 canonical target、ADDED/MODIFIED、原 Scenario 和 THEN 消费者视角。无 REMOVED。对两条 MODIFIED 提取标题并读正文比较：Heartbeat/Cron 原 15 个 Scenario、后台通知原 8 个 Scenario 均保留。

| delta / Requirement | 独立核实与结论 |
|---|---|
| gateway/agent-capabilities / 全局主 Agent 保留默认工具并具备固定基础能力（2 Scenario） | area 合适、THEN 可观察；ADDED 无法改掉 current:221–239 真白名单 → R1-C1 |
| gateway/global-agent / 全局 Agent 跨聊天保持连续的工作认知（1） | 新 area 合适；current routing 隔离/并行需 MODIFIED → R1-C1 |
| 同文件 / 依据配置接收信号，并自主安排读取（3） | 对应 spec:250–265；不能与旧 steer 无条件并存 → R1-C1；signal R1-W1 |
| 同文件 / 主 Agent 统筹工作，并偏向按需委派执行（4） | 平行新增，保留内部/外部派工责任；THEN 面向结果，合格 |
| 同文件 / 全局模式向目标群发言前复核应处理的新消息（6） | global 目标群增量，不删除旧当前群规则；THEN 发言/草稿可观察，范围合格 |
| 同文件 / 全局模式不通过聊天命令重置工作上下文（2） | 对应 Q12，须限定旧 /new → R1-C1 |
| 同文件 / 停止命令强制停止实际触达的 Agent（3） | 主执行/路由/子规则保留；与原控制规则模式对账见 R1-C1 |
| 同文件 / 全局模式的压缩命令作用于主工作上下文（1） | 主 Session 新语义明确，不改 focus/FIFO/幂等，作用域随 R1-C1 收口 |
| 同文件 / Inbox 读取与聊天历史读取具有不同的消费语义（3） | 真新增：摘要/历史不推进、分段失败不丢、越权拒绝；证明接口 R1-C2 |
| gateway/heartbeat-cron / Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停（17） | 精确锚 current:14，原 15 场景完整；两个 global 场景与 D13 一致 |
| im/agent-work / 聊天沟通与全局工作轨迹分开呈现（3） | 新 area 合适、THEN 为用户结果；旧气泡模式限定 R1-C1 |
| im/agent-work / 工作轨迹保留可检查的执行明细（3） | 真新增持久视图，工具/统计/刷新均可观察，未断言私有符号调用 |
| im/agents-nodes / 新建时选择工作模式，已有 Agent 保持原行为（3） | 新字段可 ADDED，默认/不可改完整，未删除既有配置 Scenario |
| kernel/background-tasks / 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠（9） | 精确 MODIFIED 同标题，8 个旧场景保留；新增 Bash sidecar 属 SDK 可观察行为，XML/工具协议不变 |
| kernel/runs / 消费者可原子地只在 Session 空闲时提交输入（3） | 真新增 SDK 行为，queued/lifecycle/竞争/重启收据均消费者视角 |
| kernel/runs / SDK 消费者可同步观察 Session 级执行事实（3） | child/补充/关闭/异常边界完整，无 core 类型外泄 |
| kernel/runs / 持久输入边界可被观察而不冒充消息消费（1） | 初始输入 committed 的消费者语义正确；仍未定义正文证明 → R1-C2 |

CLI no spec delta 已在 design:327 明示，SDK 加法仍做 CLI/架构回归。新增 area 索引在 design:329 指定实施后归并时更新，不提前覆盖 current。

### 核实台账：milestone、原型和整体闭合

| 项目 | 实际核实 | 结论 |
|---|---|---|
| 唯一 M1 | design:333–339 范围包含 PA/Kernel/IM，J1–J9 reviewer 轨与接口/测试/边界 worker 轨齐；目录实际仅 .gitkeep | 完整垂直切片，无横切/并行冲突；空骨架符合阶段 |
| P1 | prototype:68–69,242–243 模式创建/只读/固定四项加默认 | 覆盖；真实配置链须 J1 |
| P2 | prototype:86–90,111–144,220 主轮次/usage/正文/工具，trace 来源表 | 覆盖，无前端猜因果 |
| P3 | prototype:132–150,222,227–228 同 child/独立执行/返回位置 | 覆盖；run_id null fixture 不造顶层 run |
| P4 | prototype:115–118,184–189,229–239 草稿/发送归同工具，Chat 往返；trace:208–210 实际定位 | 覆盖；静态跳转不冒充真实接入 |
| P5 | prototype:34–36,150,217,226 加载/空/错误/离线、权限/拒绝/中断、usage null | 状态设计覆盖，JavaScript 经 node --check 通过；不声称完成真实浏览器验收 |
| P6 | CSS container/media 和 tokenMarkup 通栏/三列明细 | may-adapt 边界清楚，无布局口味 issue |
| P7 | prototype:146–149,221–222 Cron 其他执行/独立 Session/usage | 覆盖 |
| P8 | prototype:31–40 明示演示，design:214 排除审阅开关 | 合格 |
| J1–J9 | design:293–303 分别模式/跨聊/摄取/复核/控制/轨迹/恢复权限/自动/Feishu；acceptance-map 全映射 | 可验目标清楚，不是已执行结果 |
| 人类可审上层 | design:9–13,38–64,68–107 有摘要/图/决策结论，接口下沉两份组成契约 | 方向直观，无实现细节墙 |
| 数据流 | 入站→Inbox→准入→tool 正文→消费→send→work；trace:40–64 REST/WS 共 projection，owner/root/session 校验 | 总体闭合，正文证明 R1-C2、signal R1-W1 |
| 元信息/命名 | Unit branch、对齐、空 Changelog、M1 名称、链接及决策编号存在 | 合格，不索要实现步骤 |
| 风险/回退 | design:222–230 明确持久失败/并发/发言/模型交付/断连/回归/global 回退禁旧代码误跑 | 具体可行动，无任意副作用透明恢复承诺 |
| 常驻服务 Runbook | design:242–285 隔离启停；独立查 scripts/e2e-up.sh:233–243 确实重建 DB，所以另用原数据重启正确；:370–376 导出端口/JWT；IM/app.py:262–263 默认 DB 路径对应 worktree cwd | 下游可照做；本轮未运行，不操作生产/proxy |

### 架构进攻

| 角度 | 主动检查与删除/替代试验 | 结论及长期代价 |
|---|---|---|
| 1 归属与组合依赖 | 若把 Inbox 策略放 Kernel，会令 core 识别聊天/配置；busy 判定只留 PA 会漏 queued/cleanup。runtime:11–17,90–94 将前者放 PA、后者收口内核；SQLite recorder 在 PA，IM 经 WS，不 import PA/agent。核 AGENTS 红线及 current kernel/sdk-boundary.md:14–29 | 归属成立。R1-C2 必须沿合法 SDK/HookAPI 补，若 PA 私读 core transcript，将让产品长期依赖内核存储细节 |
| 2 该不该存在 | 逐个删除：GlobalInboxService/Store 删掉会将去重/receipt/part 消费/目标判断散入工具和 dispatcher；GlobalRunCoordinator 删掉会分散 durable signal/retry/stop；Recorder 删掉只剩 2000 项内存；Relay 删掉 recorder 将同时做网络 ACK；AgentWorkRepository 删掉 IM 只能访问 Gateway 磁盘；专用两种卡片删掉则 Inbox/历史语义被通用 JSON 混淆。单份 work 日志兼待 ACK，不另造 outbox | 每个对象都有必要隐藏的责任；无只为未来多态的工厂/策略，无独立 Task 业务模型 |
| 3 深浅/复用 | 独立搜索找到 try_commit_output、executor lifecycle、send ACK、Presenter、ToolDetailBody、permission broker，设计均复用。新 idle 接口隐藏 compare/reserve 和 queued/cleanup，不外露内核锁。projection 合并 start/end 稳定 item，不要求客户端重建因果 | 无可删浅透传模块。R1-C2 若让产品猜序列化，serializer/多模态每次改动都会传播到 Inbox，形成维护税 |
| 4 治本/补丁 | 主上下文无唯一 ReplyContext，设计独立工作归属并过滤旧 observer 出口，没有隐藏私聊/假 run_id/强发/计数即完成/房间版本服务；stable ingress/submission/ACK 与 unknown 状态都对应实际边界 | 核心方向治本。R1-C1 若不修，新模式会长期叠在相反 current 上，每次回归付歧义成本；R1-W1 若不修，入站/调度会各自解释注意力策略 |

未将空 milestone、缺代码/步骤、布局口味或假想分布式强一致要求升级为问题。author 追加 Resolutions 并修订三项 issue 后，由同一 reviewer 选择下一轮实际所需深度。


### Author Resolutions

- **R1-C1 — accepted.** 回查 current `gateway/routing-delivery.md` 的聊天隔离、自动入站/后台回复、插话、控制、配置边界与失败展示，以及 `agent-capabilities.md` 的真白名单和 fallback 聊天呈现，确认与 global 的共享主上下文/显式发送存在无条件冲突。新增 `specs/gateway/routing-delivery.md`，扩展 `specs/gateway/agent-capabilities.md` 的 MODIFIED；并新增 `specs/im/gateway-relay.md`、`specs/im/tool-timeline.md` 限定旧聊天气泡/后台/配置边界。下游仍使用原工具与真实投递链。现有 runtime 已写明全局模式在 IM 离线时接受/读取本地 Inbox、显式投递不可用则明确失败，因此 IM 可选中心条目也限定其原 single_thread 完整离线回复承诺，未新增离线发送路径。Heartbeat/Cron 恢复原 Scenario 原文，在 Requirement 内解释 canonical 直聊场景作用域。主文档加入归并规则，runtime/trace 明确主配置与模型切换事实归工作轮次。对 24 条 MODIFIED 的 131 个原有 Scenario 做逐段文本比对，全部原文保留；global 的详细行为仍集中在专属 area。
- **R1-C2 — accepted.** 核实 `loop.py:935–971` 只给 raw result、`:1012–1066` 存在异常 fallback 及两次独立序列化；`runtime.py:727–732` 才是实际 durable append。运行契约 §2 现明确唯一采用 SDK `tool_result_committed`，由 composition 安装的 `GlobalWorkRecorder` 转给 Inbox 服务，按 session/call、正常序列化、无工具错误与实际最终内容 digest 校验服务端 receipt。工作轨迹 SDK 段定义实际 message identity、serialization_status、digest 格式、持久发布位置和 live LLM 复用相同 content；无需 PA 读取内核私有文件。fallback 仍保留原工具模型行为但不确认 Inbox；持久失败无证明，事件/确认故障保留待读供稳定 ID 重读。同步修改 design 图/grounding/风险、acceptance-map、kernel/runs delta，新增三条消费者场景；无现有工具 schema、返回或 Presenter 修改要求。
- **R1-W1 — accepted.** 核实 `inbound_pipeline.py:148–150,353–362` 分开持有 should_process 与 sync_only，Feishu history catchup 也显式 sync_only。运行契约 §2 接收步骤 3–4 现在定义 requires_attention = normal_live_input && should_process；背景、sync_only/history catchup 不推进 signal，自身回声不建 Inbox entry，重复 ingress 不新增触发。entry seq 全量递增，latest_signal_seq 仅保存最后有效触发的 entry seq；§3 pending 只能使用有效水位，禁止用最大 entry seq 或全部待读计数唤醒。目标复核使用同一有效 attention 定义。
- **R1-R1 — accepted.** 使用原 Requirement 开头的最窄模式限定，保留原 Scenario 并链接 global area；没有在各 area 重复整份 global 设计。
- **R1-R2 — accepted.** design 最窄测试段、runtime §7 与 acceptance-map 明确真实 loop 的 serializer 成功、fallback、tool error、durable 失败和精确消费路径，留给 M1 worker 验证；设计阶段未伪称运行过尚未实现的接口。

自检：首文档 31 条 Scenario 全部仍映射 M1；spec、prototype、M1 骨架相对首轮 hash 未改变。核过 proof 来源→唯一 SDK observer→Inbox 事务、signal→idle admission→持久水位和目标锁→Kernel publication 的接口链；PA/Kernel/IM 归属与调用方向不变。原型 JS 语法检查通过，Markdown/本地链接检查通过。将本 unit 文件纳入 `docs_check.run_checks` 后，只剩已有 `docs/research/studies/README.md` 两条指向本任务外未跟踪研究目录的链接；没有本 unit 结构错误。上述为设计自检，不是产品实现验收。


## Round 2

### Metadata

- reviewer: `/root/feat_546_design_reviewer`
- review_mode: delta
- mode_reason: 本轮为三项历史问题的有界语义修订：补齐旧 canonical 的模式作用域；在已计划的 SDK 观察接口内补实际持久正文证明；区分接收 seq 与有效 signal。需求、非目标、主上下文/Inbox/工作存储的归属、公开工具协议和唯一 M1 未变。新增 proof 细化原方案既有消费边界，未引入另一条产品调用链；影响可枚举，故不采用仅措辞 closure，也不重新冷启动 full。
- started_at: 2026-09-09T18:50:48+08:00
- completed_at: 2026-09-09T10:55:29Z
- duration: 281 seconds

### Verdict

Approved — 0 CRITICAL / 0 WARNING

三项历史 Issue 均关闭，两个 Recommendation 已落实。可以进入 change-orchestrator；本结论是设计文档门禁通过，不代表尚未实施的 SDK/产品行为已经测试通过。

### Coverage

- retained_from: Round 1 — 完整台账仍是本轮 inventory。首文档、原型与 M1 未变；权限、工作日志/WS ACK、查询/projection、子执行归属、Cron 隔离、回退与运行手册的核心设计未变，原证据继续有效。本轮仅重核下述 changed atoms 及其直接上下游。
- 逐条检查新增/修订的 23 条模式限定 Requirement：Gateway routing 14、能力 2、Heartbeat 1、IM relay 4、IM timeline 2；另保留 kernel/background-tasks 的原 1 条 MODIFIED。独立脚本按 canonical 同标题提取并逐段比较全部 24 条 MODIFIED 的 131 个原 Scenario，全部原文保留；并人工逐条读新作用域说明，未只依赖作者的比对结论。
- 重核 runtime §2/3/4、trace SDK/PA 事件段、kernel/runs 新证明 Requirement 及 3 个消费者场景，以及 design 的 grounding/总图/D3/风险/最窄测试/归并说明与 acceptance-map。新证明不替代初始输入收据；注意力修订同时核接收、唤醒与发送目标复核。
- 受影响四个架构角度均重跑，见末表。未运行服务、模型旅程或尚未存在的实现测试；只改本报告。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮独立核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted；补最窄 MODIFIED 和模式边界 | 逐条核下表 23 项；24 条 MODIFIED/131 个旧 Scenario 对比无缺失或静默改写。routing 明示 global 不绑定当前聊天、不自动回发；能力真白名单有主 Agent 固定并集例外；IM 气泡/配置边界/后台/离线作用域同步，design:327–329 写清实际归并，不再依赖 ADDED 隐式覆盖 | closed |
| R1-C2 | accepted；唯一 SDK tool_result_committed，实际 digest/serializer 状态 | 独立回查 loop.py:1012–1038 的 serializer fallback 与预算、:1040–1066 两次独立序列化、runtime.py:727–732 durable append；新 runtime:78–82 与 trace:21–27 逐一覆盖这些真实缺口。Kernel 保存实际最终 content 并供 live/transcript 共用，持久后发布；PA 经 SDK 收证明校验 session/call/name/error/status/digest 后同事务消费，无 raw hook/Presenter 旁路 | closed |
| R1-W1 | accepted；有效 attention 水位 | inbound_pipeline.py:140–148 分开 sync_only 与 should_process，:355–361 保留 ALWAYS/MENTION 条件。runtime:49–50 仅 normal_live_input && should_process 推进 signal；:112 只按该水位 pending；:131–135 用同一 requires_attention 判断目标未读。背景/history catchup 不唤醒或拦发送，self echo 不建条目，重复 ingress 不重新触发 | closed |
| R1-R1 | accepted；短作用域摘要+专属 area | routing 各项与 IM 两份新 delta 都将详细 global 行为链接到专属 area，保留原 Scenario；能力和 Heartbeat 只展开必要差异，没有平行复制完整设计 | closed |
| R1-R2 | accepted；验证真实 durable seam | runtime:159、design:309、acceptance-map:41 包括真实 loop → durable → SDK → PA → SQLite，覆盖成功/fallback/tool error/持久失败；明确留给 M1 worker 实施验证，没有把文档静态检查写成产品成功 | closed |

### 本轮核实台账：模式限定及归并

以下行号均相对本 unit 的 specs；各行同时比对 docs/specs 下同名 canonical Requirement，括号为原 Scenario 数。

| changed atom | 实际核实与上下游结论 |
|---|---|
| gateway/routing-delivery:7 四步路由（8） | :9 将旧聊天处理与自动回复限定 single_thread，Agent 身份/未知拒绝两模式通用；对 runtime:47–51 的 Inbox 接受和取消占位一致 |
| :54 恢复交付（3） | :56 限定旧原聊天恢复 batch；global 恢复持久 Inbox/signal，与 runtime:114–118 不重放已执行副作用一致 |
| :78 群触发（7） | :80 保留 MENTION/ALWAYS/控制触达；仅旧 buffer 自动摄取等限定模式，与 requires_attention 判据一致 |
| :122 /new（4） | :124 保留命令路由/幂等，global 明确拒绝；runtime:122 不重置主 Session |
| :154 /compact（5） | :156 保留 focus/幂等/FIFO/失败不改/来源反馈，global 改主 Session；Inbox 接收不阻塞但摄取不越预留，对 runtime:96,124 |
| :193 /stop（3） | :195 当前目标按模式解释，旧语法/触达/反馈保留；不清 Inbox/不级联 task_stop，对 runtime:123 |
| :213 忙时插话（5） | :215 明示 global 收至 Inbox 后自主读取，不再强制正文 steer，对 runtime:47,88 |
| :245 插话回复定位（1） | :247 global 工作轮次与显式消息分开，不再要求自动挂到插话下方 |
| :255 配置边界（5） | :257 主 Session/turn 工作事实与纯展示/保存失败例外清楚；对 runtime:125 与 trace:43，不需要伪造首条聊天输入 |
| :286 映射/配置持久（5） | :288 主 Session 允许关联已读跨聊内容，旧聊天绑定不迁移；消除旧“仅自己的聊天历史”冲突 |
| :316 显式发送（4） | :318 目标/权限/结果两模式共用，global 无隐含当前群；仍保留 :320 实际 live IM 投递限制，对 runtime:53,129–135 |
| :342 后台回复（6） | :344 global 原始返回与综合正文归工作，不按最后聊天自动回传或复制 Inbox；对 runtime:116 与 trace PA 事件 |
| :382 失败反馈（2） | :384 global 对应工作轮次显示失败/中断/离线，不造聊天失败泡；不撤销真实可见失败的要求 |
| :399 当前群复核（6） | :401 旧当前群插话分段限定 single_thread；global 走明确目标复核，对 runtime:131–135 |
| gateway/agent-capabilities:22 真白名单（5） | :24 固定四项并集只作用 global 主 Agent，其他工具仍配置限制；子继承/角色/数据权限不扩大，对 D11/runtime 工具身份检查 |
| :54 备用模型（9） | :56 保留候选链/重试/持久粘性/配置重置；global 粘主 Session、失败切换归工作、/new 不重置，对 runtime:125/trace:43 |
| gateway/heartbeat-cron:7 两套机制（15） | :11–18 区分主上下文/canonical 直聊并保留共同开关/节律/错过周期/幂等/历史；原场景逐段相同，新增 :92–100 仍是主 Heartbeat 和独立 Cron，不新扩调度需求 |
| im/gateway-relay:7 配置 ACK（3） | :9 旧聊天锚点限定 single_thread，global 归工作持久同步；不降低真实身份校验/ACK，见 trace:43 与既有工作事件同步契约 |
| :28 中继/回执（3） | :30 明确 global completed 是 durable Inbox 接受，不是已读或工作完成；:32 原幂等/回执继续适用，对 runtime:50–51 |
| :48 IM 可选中心（2） | :50 保留两模式本地执行边界；global 离线本地接受/读取，但显式发送依赖既有链，失败不能成功；这是 R1 runtime:53 已有选择的 canonical 补齐，不是新造离线发送途径 |
| :64 后台通知（6） | :66 仅旧自动气泡/message sidecar 限定 single_thread，global 返回归工作、显式消息仍实时；不把 Kernel 终态广播业务搬入 IM |
| im/tool-timeline:7 过程（9） | :9 仅气泡内归属限定模式，global 共用真实过程/工具详情/usage/权限/外部不展示原则，与工作视图专属 area 一致 |
| :50 草稿/复核（7） | :52 global 草稿归发送工具详情；正式消息边界与来源不可用不误定位继续通用，不改旧 Presenter |
| kernel/background-tasks 原 MODIFIED（8） | 本轮正文设计未改；重新纳入 canonical 原 Scenario 保留比对，8 条完整，SDK Bash sidecar 加法结论继承 R1 |

### 本轮核实台账：持久证明与有效 signal

| changed atom / 波及链 | 直接证据与结论 |
|---|---|
| D3/grounding：实际正文从哪里来 | design:23,75 对原始 hook 能力的描述已纠正。独立实际路径 loop:583–592,618–632 先 yield tool message，再 observe；runtime:727–732 是 durable append。修改点就在真实生产执行路径；未发明测试专用证明来源 |
| 实际序列化与 live/transcript 同一内容 | runtime:78–82/trace:25 规定一次实际最终序列化、预算后 digest、succeeded/fallback 和 live 复用；对 loop:1012–1066 的真实双序列化/fallback 缺口逐一回应，不要求既有工具改 schema/Presenter |
| 事件身份/调用方/确认事务 | trace:21 给 session/turn/message/call/name/error/status/digest，run 可空；:27 唯一 composition observer 转交 Inbox；runtime:80 服务器 receipt 比对再同 SQLite 事务 parts/consumed_at/work event。Kernel 不携带 owner/Inbox 业务，PA 不读内核私有 Message |
| 失败及重启边界 | runtime:82：tool error/fallback/mismatch 不消费；durable 失败不发证明；观察失败/崩溃保留待重读。不是先 ack 再等落盘，也不从旧 raw output 补猜；继续符合 spec 的完整摄取而非任务完成语义 |
| SDK 消费者契约 | kernel/runs:52–68 新 Requirement/3 Scenario 覆盖实际持久正文、回退辨识、失败无证明；THEN 为消费者取得的事实，不断言内部函数调用。:44–50 初始通知收据保留，不能提前代表正文消费 |
| 入站→signal→pending→target | runtime:49–50 明确背景可读但不触发、self 不入箱、重放不新增；:112 的 pending 与 :131 的发送阻塞均依赖同一有效 attention。有效 seq 可带空隙但只比较单调水位，不依赖连续 entry 序号 |
| 对整体/退出标准的影响 | design 总图:43–63 的 SDK→observer 仍容纳证明，D3/风险:224/最窄测试:309/归并:329 和 acceptance-map:41 一致；原 M1 已涵盖 core agent/session/events 与 PA 接点，既有 worker 两契约闭合退出包含此次修订，无需横切增 M |

### 架构进攻：本轮受影响范围

| 角度 | 主动攻击/替代检验 | 结论 |
|---|---|---|
| 1 归属 | 试将 digest/持久判断放 PA：PA 需依赖 serializer/fallback/压缩和私有 transcript，且无法知道 live 是否同一内容。当前将实际证明留 Kernel、业务 receipt/消费留 PA，经 SDK 输出普通字段 | 补在真实责任边界，没有 core→PA/IM 或 PA→core 反向依赖；避免产品随每次内核序列化变更承担维护税 |
| 2 是否需要 | 试删除 committed 事件、改用已有 tool_end/raw hook：独立代码证据显示二者缺实际正文和 serializer 状态，无法证明消费。试增加第二个产品 hook：会重复观察/持久责任 | 新事件是必要事实出口，复用既有计划 observer/recorder；没有再加只为转发的服务或消费旁路 |
| 3 深浅/复用 | 试让调用者拿原 output 自算 digest：既有 fallback/预算/双序列化会令产品猜内部状态。修订将该复杂性收口一个稳定 proof；signal 也复用现有 should_process 而非再造优先级分类器 | 接口隐藏真实复杂度，未重造路由/模型白名单/发送/Presenter；一次 final content 消除双序列化的根源 |
| 4 治本/补丁 | 试只补 ADDED 注释、每处各自解释 global；或以未读数代 signal 兜底：前者仍会在 canonical 合并后冲突，后者会把背景误作新工作。当前最窄 MODIFIED + 单一 attention + durable proof 三处各自回到真实边界 | 无私有存储旁路、隐形聊天锚点、猜测确认或背景忙唤醒补丁；配置/失败工作归属同步解决同一模式边界问题 |

### Issues

无。本轮没有新增 CRITICAL 或 WARNING，R1 Issue 无未关闭项。

### Recommendations

无新增建议。R1-R1/R1-R2 已落实，实施期按既定 M1 的真实 durable seam 与产品旅程验证即可。

### Author Resolutions

Round 2 无新 Issue 或 Recommendation。作者逐条核过历史闭环、模式限定台账、持久证明的真实来源及四角度结论，确认无实质问题。随后仅删除 `specs/gateway/global-agent.md`、`specs/gateway/heartbeat-cron.md`、`specs/kernel/background-tasks.md` 各一处 EOF 多余空行；内容去除尾部空白后与 Round 2 完全相同，无契约/原型/M1 变化。临时隔离副本以同一基线纳入本 unit 后完整 docs-check 已通过；清理后的 staged diff 格式检查通过。此格式修订交同一 reviewer 确认，受审其余文件保持不变。


## Round 3

### Metadata

- reviewer: `/root/feat_546_design_reviewer`
- review_mode: closure
- mode_reason: 独立核对 Round 2 文件清单后，确认只有三份 delta 各删除一个 EOF 换行字节；其他 18 份受审产物 SHA-256 完全相同，文件集合没有新增或缺失。无语义变化，历史问题的直接证据没有失效，采用 closure。
- started_at: 2026-09-09T10:56:35Z
- completed_at: 2026-09-09T10:57:17Z
- duration: 42 seconds

### Verdict

Approved — 0 CRITICAL / 0 WARNING

保持 Round 2 的设计门禁通过结论，可进入 change-orchestrator。

### 历史问题闭环与直接证据

| 历史项 / 本次修改 | 本轮独立核实 | 状态 |
|---|---|---|
| R1-C1、R1-C2、R1-W1 | 已读 Round 2 Author Resolutions；Round 2 已逐条闭环，本轮运行契约、工作轨迹契约、design、SDK runs 和模式限定相关正文未改变，原证据继续有效 | closed |
| R1-R1、R1-R2 | 无新增建议；canonical 模式作用域和真实 durable seam 验证要求未变化 | closed |
| specs/gateway/global-agent.md EOF | 读取当前字节，在末尾补回一个 LF 后的 SHA-256 与 Round 2 清单值一致；当前保留正常单个结尾 LF，确认仅删多余空行 | verified |
| specs/gateway/heartbeat-cron.md EOF | 同样以当前字节加一个 LF 精确恢复 Round 2 SHA-256；全部正文及 Scenario 不变 | verified |
| specs/kernel/background-tasks.md EOF | 同样以当前字节加一个 LF 精确恢复 Round 2 SHA-256；全部正文及 Scenario 不变 | verified |
| 其他受审产物 | 对清单全部 21 个路径计算实际 SHA-256：18 个完全一致，仅上述 3 个 EOF 差异；独立遍历 unit（排除本报告）与清单比较，无新增或缺失文件 | verified |

以上为 reviewer 实际执行的文件完整性核验。作者报告的隔离 docs-check/staged diff 检查不冒充本轮执行结果；没有新契约语义，不重抄 Round 1/2 台账或重跑架构进攻。

### Issues

无。

### Recommendations

无。

### Author Resolutions

Round 3 无 Issue 或 Recommendation。作者确认三处差异仅为 EOF 空行清理，其他受审产物未变；认可本轮闭环及零遗留结论。最终正文保持冻结，门禁 2 完成。
