# refactor-564: Gateway 统一消息交付设计

## Changelog

- 实施核对：完整轮事件附带已有 `context_revision` 事实；普通群候选由 Gateway 记录待消费输入身份，并以既有 `injection_consumed.pending_ids` 收据解除门禁。权限等待期间单独消费同 run 的审批事件，避免正文消费者等待权限时阻塞审批卡。

## 决策与基线

用户已确认交付是产品业务，错误可作为后续消息驱动修正，并授权自主重构/验证。本设计取代未合并 feat-563 的 OutputCandidate/OutputControl/OutputResult 方案，保留其 Runtime、权限和用户体验要求。源码调查基线 `6ee4c71ab`；main 基线 `0014ee0b0`。不重写 Agent 内核、不新增调度平台/消息中间件。

实际可复用能力：SDK `try_steer` / `try_submit_idle` 提供原子运行准入；`InputPart.metadata.context_origin=system` 由 `input_context_metadata` 保存并影响来源投影，已有能力无需新增 SYSTEM 枚举。`append_message` 仅写历史且仅接受 user/assistant，不将其误用成运行触发。已有 SessionRunCoordinator 拥有入口队列、停止/reset代次和模型选择。已有源消息 revision/try_commit_output 继续用于输入过时检查，其本身不含渠道交付状态。

## 所有权

| 模块 | 唯一负责 | 不能再做 |
|---|---|---|
| Kernel/SDK | 模型/工具执行、输入来源、通用权限与运行准入 | 图片上传、渠道送达状态、根据业务交付结果续跑 |
| SessionRunCoordinator / 对应 global/background coordinator | 消费模型事件、完整候选边界、调用投递、安排内部反馈 | 读取图片、直接写渠道、独立判断送达 |
| Gateway 的 MessageDelivery | 一条逻辑输出的准备、提交、渠道回执与恢复；唯一业务入口 | 决定模型如何生成或启动新模型运行 |
| ReplyImages | 解析、受限文件读取、不可变图片快照、资源投影 | 决定消息是否送达或触发重试 |
| IM 消息写入组件（delivery 内部） | provisional气泡、正文提交、process与完成写入的同一身份 | 在完成事件重新读源文件、另行准备/上传 |
| IM/Feishu 适配器 | 目标协议的上传/发送及原始回执 | 业务重新生成、选择其他目标、自己的消息重试循环 |
| Shadow sync | 外部会话/用户输入的影子映射、已有锚点恢复 | 独立准备并发送 Agent 正文 |
| composition | 构造和依赖连接 | 内嵌 prepare/publish 状态机 |

MessageDelivery 是模块而非一个容纳所有代码的巨类。保持现有 IM connection、Feishu adapter、task tracker 和 shadow ingress 能力，仅迁移重叠的 Agent 正文交付决策。普通消息和显式消息的协议可以不同，但上层准备/回执流程相同。权限卡片和控制命令的独立业务规则不扩张为此次重构对象。

## 窄接口和调用

Gateway 私有接口草案（不是 SDK API）：

```python
result = await delivery.deliver(intent, admission)
await delivery.observe_process(run_context, event)
await delivery.recover_pending()
```

- `intent` 是 Gateway 构造的不可变完整输出：稳定 source id、session/agent/workspace 来源、目标 ReplyContext、完整正文及需要的气泡身份。普通来源为真实 session/run/message 或 group id，显式来源为真实 tool call/provenance。不得接受模型/HTTP自报的“已授权”布尔值。
- `admission` 来自当前产品 coordinator/Inbox，封装目标访问、会话代次、输入 revision 与取消门禁；准备前可快速拒绝，提交前原子复核。不得在短提交锁内执行文件/网络 I/O或等待授权。
- `result` 仅在 Gateway 内表达未发布错误、已确认、部分/不确定和过时/撤销。具体图片错误是数据；不进入 Kernel 枚举。普通与显式入口只转换返回形式，不能重做准备/发送。
- `observe_process` 只呈现运行/工具/思考及终结事实，使用同一 IM 写入组件，不能自行取得正文、读图或重新发送。运行开始与正文先到都解析到同一气泡，按已有稳定身份幂等。
- `recover_pending` 使用同一内部提交函数与原 intent/快照，仅补未确认目标；没有另一条“恢复发送实现”。连接恢复定时器只调用该方法。

普通群候选在准备前与公开 I/O 准入前检查待消费输入：coordinator 收到新输入即登记，成功 steer 后绑定真实 pending_id，只有实际 injection_consumed.pending_ids 才解除对应门禁；排队到下一 run 的输入不会解除旧候选门禁。这样后续同 run 的有效回复可以继续发送，无需依赖已终结 Kernel run 的提交回调。

普通入口：收齐一次模型回复 → 构造 intent → await deliver → 若全未发布且可修正，向产品 coordinator 登记反馈。显式入口：现有工具权限先通过 → handler验证真实 provenance/目标 → 调同一 deliver → 简短结果直接回工具。显式错误不额外排内部反馈，避免两次修正。

## 完整候选与运行状态

正常模型事件只从现有事件流进入 Gateway，移除 feat-563 直接从内核回调 Gateway observer 的第二入口。新增产品无关的 `model_round_end` 观察事件：携带真实 session_id/run_id/turn_id/group_id 和 `completed`，不携带渠道或交付状态；每次 LLM 调用结束并完成该轮已启动工具结果收集、既有group输出复核之后发出一次，位置在准备下一次LLM调用之前。该事件只报告事实，不等待产品处理，不影响内核是否续跑。空正文/纯工具轮也发事实但不形成正文候选；流异常或取消走异常终结，Gateway丢弃该轮未完成缓存，不提交残缺图片。现有终态事件依然结束整个run。

Gateway按group_id收集assistant_message，只在匹配的 `model_round_end(completed=True)` 冲刷。message_end是chunk结束，tool_start可与stream交错，均不能触发正文提交。启用既有group revalidation时，内核只发通过复核的聚合assistant_message，Gateway收集这一条并等相同round_end；被withheld的轮没有公开正文事件，不能再次拼回失败草稿。普通路径使用各chunk的共同group_id。重复事实按稳定run/group候选身份幂等；异常round和无正文round不增加delivery。

正文在准备/授权失败时不公开；思考和工具过程可以继续显示。模型完成与交付完成是不同事实：内核照常记录真实执行结果，Gateway 在当前逻辑请求的交付完成后再完成用户气泡/请求；失败反馈后续运行复用逻辑请求关联，不伪造一次新真人输入，不把“模型run结束”等同于“消息已送达”。工具不会因图片失败重放已经执行的调用。

## 权限复用

显式 send_message 保持原工具权限链，无二次审批。普通候选通过通用 SDK 权限检查复用同一 tool policy/Auto/hook/user approval；这个窄能力只接收 tool name/arguments、真实session来源与操作身份，返回 allow/deny，不执行工具，也不依赖输出回调。

沿用 feat-563 对 registry 权限逻辑的提取，移除 BoundOutputControl 和输出状态类型。SDK 权限检查必须从真实 session/runtime 构造 HookContext，继承权限来源、人工批准通路、取消、模型配置；不接受伪造授权上下文，不越过包边界。权限检查可发生在模型执行已结束但产品逻辑请求仍有效的阶段，提交资格最终仍由 Gateway 的 admission负责。显式调用依据真实执行路径判断已审批，不暴露可由HTTP控制的跳过标志。

Gateway 在等待通用权限调用时，从当前事件序号订阅同 run 的 permission_request/permission_resolved，只呈现审批过程并按事件身份去重；不消费或提交正文。停止/reset 撤销此等待并取消底层审批。

先取得不跟随符号链接的受限文件描述符，再决定权限，批准后读取形成快照，所有分支关闭。后续恢复使用批准的快照，不重新读取路径或重新审批同一次交付。

## 失败反馈回到模型

Feedback 调度属于产品 coordinator：

1. 只有可以确定整条候选未公开的准备/权限错误形成内部反馈。沿用既定 reminder内容，明确这条未送达、此前成功消息仍可见；具体路径/远端错误转义并限制长度。
2. 当前 Kernel run 未结束时可以先登记反馈，不强制打断模型/工具；利用既有 pending input/idle admission能力在安全入口消费。优先在该run收口后以稳定 submission identity 调度同session修正，避免提前消费反馈导致完成顺序交叉。反馈 part 标明 `context_origin=system`，不伪装真人消息、无真人channel/time前缀。
3. 遵循同一产品请求的停止/reset代次与现有用户输入队列。用户停止后丢弃未准入反馈；新输入优先，过时草稿不自动复活；反馈去重并遵循下述明确的请求级修正上限，不能无限新建run绕过限制。
4. 已部分公开或回执不确定，交付owner继续原身份对账，不能让模型重生成副本。最终无法确认时只反馈真实渠道状态，不能套用“从未发送”的模板。

请求级上限：当前产品逻辑请求至多准入两次交付反馈运行，由coordinator持有计数并记入该请求的交付恢复记录，稳定submission id与计数一同保存。首次允许修正图文；若仍未成功，第二次只要求Agent用文字解释无法交付，不再尝试图文。计数在实际成功准入时消耗，busy排队不消耗；同一submission重试不重复计数。若第二次仍输出不可交付内容，扣住候选、停止自动反馈并将逻辑请求如实标为未完成，不强行发布错误正文或假装成功。已有成功气泡保持成功；仅待完成气泡按既有失败/取消终结协议处理。stop/reset撤销排队反馈且不释放额度让同一请求复活；下一条真人请求有独立预算。不是新的通用重试调度器。

这里不承诺同一个 run id；用户仍在同一个聊天中得到完整结果。反馈运行仍必须由原 coordinator建立路由、workspace、模型和生命周期，禁止在 observer 回调中直接裸调用 SDK后丢失上下文。

## 快照、回执与恢复

复用既有图片SQLite及shadow持久状态，不引入新数据库平台。消息回执写入职责从 ReplyImages/各入口移至 delivery模块，可保留现有表与稳定键以减少迁移。一个 logical output固定一个 identity；同一来源重放只读原快照和目标回执。图片资源准备与消息提交分开，完成通知只引用已保存的发布内容。

IM离线时，飞书是主交付，shadow目标未有anchor也不能阻塞它；owner保存外部已确认回执以及待镜像事实，shadow恢复取得锚点后调用同一owner补IM。Shadow ingress仍可独立恢复用户映射，不再回读Agent源文件。显式双目标部分成功沿用原要求与真实回执。provider稳定UUID及有效重试窗口保留，不宣称跨服务exactly-once。

## 删除与迁移清单

- 删除 SDK/core OutputCandidate、OutputResult、BoundOutputControl和loop业务回调分支；保留原group新输入复核与准确的旧reminder。
- 删除 PaReplyDelivery 的kernel回调角色；其权限/准备能力并入 MessageDelivery普通入口。
- composition 内 _prepare_candidate/_publish_candidate/_prepare_outbound 的业务移入owner。
- internal_dispatch 保留来源/路由/工具结果适配，移除独立上传、渠道提交、回执重试流程。
- ImageReplyConnection 不再自动 prepare/读取/重投；由统一IM写入组件呈现已准备内容；observer不再拥有另外一套正文发送入口。
- ReplyDeliveryRecovery 合并为owner的恢复执行，不独立选择通道或发送；shadow的Agent输出恢复交给owner。
- 保留现有窄渠道实现、运行task tracker、资源快照和合法权限策略。不在旧路径外简单新增facade并让调用方继续操作底层。

## 规格处理

原 feat-563 尚未合并，最终PR继续包含原设备上下文/图片产品行为增量。撤回它的 kernel/runs“产品候选交付回调与状态”目标，改为必要的产品无关权限能力说明；Gateway内部反馈使用现有输入来源，不新增业务kernel状态。此重构单元不新增用户功能；受审 delta 位于 `specs/kernel/runs.md`、`specs/gateway/routing-delivery.md`，以合入旧候选源码后的集成树为替换基线。旧 feat-563 的 gateway/relay-protocol、im/web-chat-ux 及 routing-delivery 中 Runtime/统一图片交付要求全部保留，只替换恢复反馈要求的同run隐含假设。最终只合并实际仍成立的current契约。

## 验证与 Gate

采用单 M1，不按模块横切；在专属worktree做完整重构。以旧候选真实产品验收为回归基线，不以旧内部测试结构为约束。

| Milestone | 文件范围 | 退出标准 |
|---|---|---|
| M1-delivery-owner | PA gateway/coordinators/channels，SDK通用权限，撤回core输出回调，相关测试/规格 | [worker] 两入口/恢复只经过一个owner；SDK无业务交付状态；普通失败反馈是系统来源输入且停止/新输入安全；两种bubble竞争确定性回归、重复/缺图/删源/离线/ACK丢失/权限/多轮工具回归通过；[reviewer] Runtime、普通/群/global图文、拒绝、失败修正、完成状态和专用飞书离线后补真实验收通过。 |

关键测试落在 MessageDelivery公开入口和真实coordinator链：假的网络传输控制ACK/故障，真实本地SQLite与文件快照，不绕过权限或调度来伪造成功。保留已发现竞争/生命周期回归，删除只镜像已撤接口的测试。独立设计审查、实现verifier、代码review及产品review；最终全量Python、frontend、docs/Ruff和远端CI。无布局变化，不新增prototype。

## 验收环境与交付

已有仓库E2E脚本、可用LLM代理和专用飞书测试授权（本会话）继续适用；隔离端口、配置、workspace/node/data；不接生产Bot、不部署。最终待审PR取代已转draft的#306，旧提交保留供审查追溯。前期已用户体验的临时栈已停，不把本次重构直接覆盖其运行目录。
