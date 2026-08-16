# kernel (agent) - Runs Specification

> 对齐: bugfix-536
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

会话创建、run 调度、steering、工具许可、中断、liveness 和 Kernel 关闭的对外契约。

## Requirements

### Requirement: 创建会话必须绑定 workspace_root

消费者创建会话时绑定一个 `workspace_root`;该路径绑定到会话生命周期,后续该会话内工具执行的 `cwd` / 安全沙箱边界、以及工具/hook/skill 的工作区层扫描均以此为根。

#### Scenario: 创建会话返回绑定工作区的 Session
- **WHEN** 消费者 `await kernel.create_session(workspace_root=<path>)`
- **THEN** 返回一个 `Session`,其工作区根固定为该 `workspace_root`,会话内后续工具执行均在此根下进行

### Requirement: submit 非阻塞调度一轮运行,事件经 stream 异步消费

`submit()` 把一轮(turn)调度到内核后台事件循环并立即返回一个 `RunRecord`(初始状态 QUEUED);消费者经 `stream()` 异步迭代该会话的事件,跨自己的事件循环也能收到。

#### Scenario: 提交后从 stream 收到运行状态事件
- **GIVEN** 一个已创建的会话
- **WHEN** 消费者 `kernel.submit(session_id, parts=[{type:text,...}], workspace_root=...)` 后 `async for ev in kernel.stream(session_id, after_sequence=0)`
- **THEN** 收到扁平化事件 dict(含 `event` / `session_id` / `sequence_num` + payload 字段), 其中出现 `run_status` 事件,运行完成时其 `status` 为 `completed`(或失败时 `failed`)

#### Scenario: 同步提交完成后运行记录可查
- **WHEN** 提交一轮并轮询 `kernel.get_run(run_id)`
- **THEN** 运行到达终态后记录 `status == "completed"` 且 `turn_id` 非空

### Requirement: 经 submit 投递的消息可 steer 进活跃 run 的下一轮

消费者经 `Kernel.submit(steer=True)` 投递消息时，内核按会话当前是否有活跃 run 决定注入或新建，结果由返回的 `RunInfo.injected` 标识；`steer=False`（默认）保持"总是新建 run"的既有语义。消息的 origin 由消费者随原始注入来源提供，注入、异常转交或新建 fallback 都不改变它。

#### Scenario: 有活跃 run 时注入其下一轮
- **GIVEN** 某会话有一个正在执行的 run
- **WHEN** 消费者对该会话 `submit(steer=True)`
- **THEN** 消息进入该活跃 run 的待注入队列，于其下一次模型调用前被带入上下文
- **AND** 返回 `RunInfo.injected=True` 且 `run_id` 等于该活跃 run 的 id（不新建 run）

#### Scenario: 无活跃 run 时退化为新建 run
- **GIVEN** 某会话当前没有活跃 run
- **WHEN** 消费者对该会话 `submit(steer=True)`
- **THEN** 照常新建一个 run，返回 `RunInfo.injected=False`

#### Scenario: 默认 steer=False 维持新建语义
- **WHEN** 消费者 `submit()` 不传 steer（或 steer=False）
- **THEN** 无论是否有活跃 run，都新建 run、`injected=False`（与既有调用方行为一致）

#### Scenario: 注入消息携带多模态 parts
- **GIVEN** 某会话有活跃 run
- **WHEN** 消费者 `submit(steer=True)` 投递含文本与图片附件的 parts
- **THEN** 注入上下文的消息完整保留文本与图片，与一次普通 turn 的用户消息无差别

#### Scenario: 多条 steer 消息按序全部注入
- **GIVEN** 某会话有活跃 run
- **WHEN** 消费者在该 run 结束前连续多次 `submit(steer=True)`
- **THEN** 这些消息按提交顺序全部进入上下文，无丢失、无乱序

#### Scenario: 活跃 run 异常终止时注入的消息不丢
- **GIVEN** 一条 steer 消息注入了一个活跃 run，而该 run 随后因非用户原因异常终止（消息尚未被消费）
- **WHEN** 内核处理这次终止
- **THEN** 该消息不丢失，由一个后续 run 接着消费；可信人工消息保持 HUMAN，普通 SDK 用户消息保持 USER，自动来源保持原 automation origin
- **AND** 内容（含图片）完整保留
### Requirement: 消费者可只尝试向预期活跃 run 注入且不创建 fallback

已拥有 normal-run admission 的消费者可调用 `Kernel.try_steer()`；该调用只尝试注入，不负责创建 fallback run。消费者可携带自己观察到的 active run id，避免在 run 切换窗口把消息注入同 session 的替代 run。

#### Scenario: 预期 run 仍活跃时原子注入
- **GIVEN** 消费者持有某会话当前活跃 run 的 id
- **WHEN** 消费者调用 `try_steer(session_id, parts, expected_run_id=<该 id>)`
- **THEN** 返回 `RunInfo.injected=True`，返回的 `run_id` 与预期 id 相同，且消息只进入该 run

#### Scenario: 会话空闲或预期 run 已过期时零副作用拒绝
- **GIVEN** 会话没有活跃 run，或同 session 的活跃 run 已替换为另一个 id
- **WHEN** 消费者调用 `try_steer(..., expected_run_id=<旧 id>)`
- **THEN** 返回 `None`，不注入替代 run，也不创建新 run；normal fallback 是否提交仍由消费者决定

#### Scenario: inject-only steer 保留多模态内容
- **GIVEN** 预期 run 仍活跃
- **WHEN** 消费者经 `try_steer()` 投递文本与图片 parts
- **THEN** 下一轮模型上下文完整保留文本与图片；若消息因 `/stop` 或非用户终态转交后续 run，内容仍不降级

### Requirement: 自动恢复向 SDK 消费者提供可结算的 pending 交接

消费者经 `try_steer()` 成功注入一条消息时，返回的 `RunInfo` 带一个 Kernel-owned opaque `pending_id`。若该消息在消费前因非用户终态转交后续 run，消费者可从后续 run 的 queued `run_status` event 读取完整 continuation descriptor（含 `recovery_id`、直接 `predecessor_run_id`、batch index、origin 和该 batch 的 `pending_ids`）；内核随后在同一 session stream 恰好发布一次 recovery settlement，明确所有 batch 已 scheduled、没有 batch，或无法恢复。

#### Scenario: 消费者按 pending identity 关联恢复 batch
- **GIVEN** 消费者已成功 steer 多条消息到活跃 run，并保留各自 `pending_id`
- **WHEN** 该 run 因非用户原因在消费前终止，内核将未消费消息分成一个或多个后续 batch
- **THEN** 每个后续 batch 的 queued status 都携带直接前序 run、batch identity 和该 batch 的完整 `pending_ids`
- **AND** 消费者可不依赖时间相邻、session 当前 active id 或 origin 猜测，将每条已接受消息关联到唯一 batch

#### Scenario: recovery settlement 可靠收口
- **GIVEN** 一个非用户终态有尚未消费的 pending 消息
- **WHEN** 内核完成该批消息的恢复调度判定
- **THEN** stream 恰好产生一次带相同 `recovery_id` 的 settlement，声明 `scheduled`、`none` 或 `unavailable`，并在 `scheduled` 时列出全部 successor run id
- **AND** 用户主动 interrupt 的 held pending、正常同-run steer 和无 pending 的终态不产生 recovery descriptor 或 settlement

### Requirement: 消费者可按 terminal run 身份选择性清理其持久化消息

需要隐藏内部静默轮次的消费者可调用 `await Kernel.discard_run_messages(run_id)`。清理以 run 的持久化 turn 身份为边界，不把文件位置或行数暴露给消费者，也不得删除更晚到达的消息。

#### Scenario: terminal run 的消息被删除且后继历史保持可达
- **GIVEN** 一个 terminal run 已持久化消息，之后同会话又完成了用户 turn
- **WHEN** 消费者调用 `await discard_run_messages(<terminal run id>)`
- **THEN** 只删除该 run 的消息并返回 `True`，更晚的用户消息与回复、父链和下一轮模型上下文保持完整

#### Scenario: 无可清理消息时无副作用
- **GIVEN** run 不存在、尚未 terminal、尚未形成持久化 turn，或已经清理过
- **WHEN** 消费者调用 `discard_run_messages(run_id)`
- **THEN** 返回 `False`，会话历史不变

### Requirement: steer 进活跃 run 的消息，其后续事件始终归属同一个 run

消费者经 `submit(steer=True)` 注入活跃 run 的消息，由该 run 接着消费、`injected=True` 且 `run_id` 不变；该消息触发的后续事件（工具调用、回复直到完成）始终出现在**这同一个 run** 的事件流上，事件归属不会静默转移到另一个 run——无论注入时该 run 离结束有多近。只有当该 run 在消费前已确实结束、无法再接续时，才退化为新建 run。

#### Scenario: steer 的后续事件都出现在该 run 的事件流上
- **GIVEN** 某会话有一个正在执行的 run，消费者已按其 `run_id` 订阅事件流
- **WHEN** 消费者对该会话 `submit(steer=True)`，返回 `injected=True`、`run_id` 为该 run
- **THEN** 该消息触发的后续事件（工具调用、回复、完成）都出现在这同一个 `run_id` 的事件流上
- **AND** 按该 `run_id` 订阅即可完整收到这条 steer 引发的全部事件直到该 run 结束

#### Scenario: 活跃 run 已结束无法接续时退化为新建
- **GIVEN** 某会话的活跃 run 在 steer 到达时已经结束
- **WHEN** 消费者 `submit(steer=True)`
- **THEN** 退化为新建 run、`RunInfo.injected=False`（消息不丢，作为新 run 处理）

#### Scenario: 事件流标出 steer 消息进入上下文的位置
- **GIVEN** 某会话有活跃 run、有 steer 消息待注入
- **WHEN** 该消息被带入模型上下文
- **THEN** 该 run 的事件流上出现一个可观察标记，携带该 `run_id`，使消费者能把"对这条 steer 的回应"与此前的输出区分开

### Requirement: 工具使用权限经注入的 can_use_tool 回调裁决

内核不内置权限策略;消费者在 `build_kernel` 时注入 `can_use_tool` 异步回调。当某轮需要工具使用许可时,内核调该回调并据其 `PermissionDecision` 放行或拒绝。

#### Scenario: 需要许可时 can_use_tool 被调用并采纳其决定
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel
- **WHEN** 运行中触发一次工具许可请求
- **THEN** `can_use_tool(tool_name, tool_input, ...)` 被调用;它返回 `allow` 则该次工具被放行, 返回 `deny` 则被拒绝

#### Scenario: 等待许可期间 interrupt 解除挂起
- **GIVEN** 一次许可请求正阻塞在 `can_use_tool`(模拟用户迟迟未决)
- **WHEN** 消费者对该会话调 `kernel.interrupt(session_id)`
- **THEN** 挂起的许可请求被解除为拒绝(deny),等待者立即返回而不会无限挂起

### Requirement: 自动工具权限判定必须基于稳定的工具动作描述

当消费者启用自动工具权限判定时,内核在判定一次非安全工具调用前必须提供当前工具动作的可解释描述; 找不到当前工具、当前工具无法提供动作描述、或动作描述为空时,该次工具调用必须 fail closed 到显式权限决策,不得用空当前动作继续自动判定。历史 transcript 中的工具调用必须按当时记录的工具名与输入稳定描述, 不得被当前注册表中同名工具的替换实现改写或丢弃。

#### Scenario: 当前非安全工具缺少动作描述时不进入自动判定
- **GIVEN** 消费者启用自动工具权限判定,且某会话尝试执行一个非安全工具
- **WHEN** 内核无法解析该工具的当前动作描述
- **THEN** 该工具调用不会被自动允许或按空当前动作交给分类器
- **AND** 消费者收到显式权限决策路径(ask / deny 等 fail-closed 结果)

#### Scenario: 动态工具有稳定的通用动作描述
- **GIVEN** 消费者或工作区注册了一个未提供专用动作描述的动态工具
- **WHEN** 该动态工具进入自动权限判定
- **THEN** 当前动作描述包含该工具名及其原始输入的结构化表示
- **AND** 该工具不会因为缺少专用描述而被视为安全或以空动作判定

#### Scenario: 历史工具调用不会被当前注册表改写
- **GIVEN** 会话历史中已有一个动态工具调用记录
- **WHEN** 后续该工具被卸载、改名,或同名工具被替换后,消费者继续推进同一会话
- **THEN** 自动权限判定中的历史 transcript 仍保留那条历史工具调用的工具名与输入
- **AND** 不会用当前同名工具的新描述重写那条历史记录

#### Scenario: 只读 skill 管理查询不触发自动分类器
- **GIVEN** 会话可用 `skill_manage` 工具
- **WHEN** 消费者触发 `list` 或 `view` 这类只读 skill 查询动作
- **THEN** 该动作由工具级权限检查直接放行,不进入自动分类器
- **AND** `create` / `edit` / `patch` / `write_file` / `remove_file` 等变更动作仍需带当前动作描述进入权限判定

### Requirement: 自动工具权限分类可使用消费者指定模型且不静默降级

消费者可在装配 Kernel 时选择一个已注册模型,专用于自动工具权限分类;未选择时,分类复用
当前 run 的模型。该选择不改变 run 的正常模型,也不改变分类失败后的既有权限处理。

#### Scenario: 显式模型只用于自动分类
- **GIVEN** 消费者以已注册模型 C 装配 Kernel,并以模型 A 提交一个 run
- **WHEN** 该 run 触发自动工具权限分类、执行工具并继续运行
- **THEN** 自动分类使用 C
- **AND** 分类前后的正常 run 请求继续使用 A

#### Scenario: 未显式选择时复用当前 run 模型
- **GIVEN** 消费者未在装配 Kernel 时选择自动工具权限分类模型
- **WHEN** 一个以模型 A 提交的 run 触发自动分类
- **THEN** 分类使用 A

#### Scenario: 显式模型必须属于已注册 catalog
- **GIVEN** 消费者提供的自动工具权限分类模型不在 Kernel 的 LLM catalog 中
- **WHEN** 消费者经 `agent.sdk` 装配 Kernel
- **THEN** 装配失败并明确指出无效模型

#### Scenario: 显式模型调用失败时不改用 run 模型
- **GIVEN** 消费者选择模型 C 用于自动工具权限分类,当前 run 使用模型 A
- **WHEN** C 的分类调用超时、失败或返回不可解析结果
- **THEN** 内核不改用 A 或其他模型重新分类
- **AND** 该次工具调用进入既有的显式审批或 unattended fallback

### Requirement: 运行可被中断与取消

消费者可中断某会话当前活动运行(`interrupt`),或按 `run_id` 取消排队/运行中的运行(`cancel`);两者对不存在的目标安全无害。`cancel` 必须**强制终止**承载该 run 的执行(不依赖被取消代码合作式自查),使该 run 即使 parked 在工具执行、LLM 等待或权限决策上也能终止;终止后该 run 占用的 session 串行锁必须释放, 同一 session 后续 `submit` 不被此前 run 永久阻塞。取消同时取消该 run 仍在等待的权限请求(resolve 为拒绝)。

#### Scenario: 取消运行中的运行,二次取消幂等
- **GIVEN** 一个运行中的运行
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 返回的记录 `status == "cancelled"`;再次 `cancel(同一 run_id)` 仍返回 `cancelled`(幂等)

#### Scenario: 取消未知运行返回 None 而非抛错
- **WHEN** 消费者 `kernel.cancel("<不存在的 run_id>")`
- **THEN** 返回 `None`(不抛异常)

#### Scenario: interrupt 无活动运行的会话不抛错
- **WHEN** 消费者对一个无活动运行的会话调 `kernel.interrupt(session_id)`
- **THEN** 返回 `None` 或被中断的 run_id,均不抛异常

#### Scenario: 取消一条 parked 的 run 后同 session 可继续
- **GIVEN** 某 session 有一条 run 卡在工具执行 / LLM 等待 / 等待权限决策且不再前进
- **WHEN** 消费者对该 run 调 `kernel.cancel(run_id)`,随后对同一 session `submit` 一条新 run
- **THEN** 被取消的 run 到达取消终态(`get_run` 可见 `status == "cancelled"`)
- **AND** 新 run 正常开始执行并能到达终态,无需重建内核(此前的 parked run 不会永久阻塞同 session)

#### Scenario: 取消会连带取消该 run 待决的权限请求
- **GIVEN** 某 run parked 在等待用户权限决策(broker 有该 run 的待决请求)
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 该 run 的待决权限请求被取消(resolve 为拒绝),不残留 pending 请求

### Requirement: alive-but-quiet 窗口经 stream 持续发出 liveness 事件

当一条 run 处于“活着但暂无业务输出”的窗口（执行静默长工具、等待主模型或自动压缩摘要模型返回、parked 等待用户权限决策）时，内核必须经 `kernel.stream` 周期性发出 liveness 事件（携带 run_id），间隔显著小于消费者侧的存活判定窗口。该事件仅表征“该 run 仍存活”，消费者可据其判定存活而不误判为卡死。四类窗口走同一事件通路，消费者无需按窗口类型分别豁免。

#### Scenario: 执行静默长工具期间 stream 仍有事件
- **GIVEN** 某 run 正在执行一个长时间无标准输出的工具(如长命令)
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 在工具执行全程内,stream 周期性产出携带该 run_id 的 liveness 事件(不必等工具结束才出现)

#### Scenario: 等待 LLM 返回期间 stream 仍有事件
- **GIVEN** 某 run 正在等待 LLM 返回且长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件

#### Scenario: 自动压缩等待期间 stream 仍有事件
- **GIVEN** 某 run 正在自动整理过长上下文，内部摘要尚未产生用户可见业务输出
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 摘要等待期间 stream 周期性产出携带该父 run id 的 liveness 事件
- **AND** 摘要的内部内容、工具和权限过程不作为父 run 的业务事件泄漏

#### Scenario: parked 等待权限决策期间 stream 仍有事件
- **GIVEN** 某 run parked 在等待用户权限决策、长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件（与工具/主模型/自动压缩等待同一事件通路），消费者据此判存活，无需 permission 专用豁免

### Requirement: Kernel 关闭会收拢所有 owned runs

`Kernel.aclose()` 与同步兼容接口 `Kernel.close()` 必须共享幂等关闭状态,停止接受新运行, 解除权限等待,中断或取消仍在执行/排队的 run,等待 RunsRegistry 自己创建的 Task 在所属 event loop 与 Context 中进入终态,再停止并关闭 loop。关闭开始后不得创建新的 queued run; 异步消费者使用 `aclose()` 时不得阻塞其 event loop。

#### Scenario: 有活动运行时关闭
- **GIVEN** Kernel 存在 running run 或权限等待
- **WHEN** 异步消费者 await `kernel.aclose()` 或同步消费者调用 `kernel.close()`
- **THEN** 相关 run 在有限 grace period 内进入 completed/failed/cancelled 之一,Registry 不遗留 Task,tracing scope 在原 Task Context 中退出

#### Scenario: 异步关闭不阻塞消费者 loop
- **GIVEN** 消费者的 event loop 还有 heartbeat、IM 或 UI 状态任务
- **WHEN** 消费者 await `kernel.aclose()`
- **THEN** Registry 在自己的 loop/thread 中 drain,消费者 loop 在等待期间仍可调度其他任务

#### Scenario: 关闭期间拒绝新提交
- **GIVEN** Kernel 已进入 draining 或 closed 状态
- **WHEN** 消费者调用 `submit`
- **THEN** 返回稳定的 closed error,不创建 queued run 或后台 Task

#### Scenario: 重复关闭
- **WHEN** 消费者多次调用或混用 `kernel.aclose()` 与 `kernel.close()`
- **THEN** 后续调用安全返回,不重复停止 loop、不抛 secondary exception

### Requirement: 消费者可保留运行来源并把可信人工输入与自动输入区分

#### Scenario: 交互产品提交可信人工输入
- **GIVEN** 消费者已验证本次内容来自当前交互用户
- **WHEN** 消费者以 human origin 提交该内容
- **THEN** 内核在该轮 provider input 和事件中保留可信人工来源
- **AND** 依赖人工来源的 turn attachment 可据此生效

#### Scenario: 自动来源保持非人工
- **WHEN** 消费者提交 heartbeat、cron、后台通知、webhook、bot 转发或普通非交互 SDK 内容
- **THEN** 对应 origin 保持自动或普通 user 来源，不被提升为可信人工输入
- **AND** 内容中出现与人工触发相同的关键词也不能改变来源

#### Scenario: Workflow 子运行有独立来源
- **WHEN** Workflow 派发子 Agent
- **THEN** 子运行的 origin 可被消费者识别为 workflow
- **AND** 该来源不能冒充新的人工 opt-in

### Requirement: self-evolution side-chain 只向 session stream 暴露明确业务结果

消费者经 `agent.sdk` 运行启用了 self-evolution 的会话时，后台 review 继承主会话能力并完成真实 memory/skill 更新，但其内部 assistant、tool 与 turn 过程不成为父 session 的普通 realtime events。需要驱动产品状态的业务事件继续可观察；只有返回结果中至少一条 mutating memory/skill tool call 被确认成功时才发布最终 structured `self_evolution_review` 更新事件，并携带非空真实更新对象与 originating run trace，供消费者选择正确投递路径。no-save、只有读取/列举或写操作失败时不发布该更新事件；若 fork 整体 `completed=False` 但此前已有确认成功的写入，仍发布对应真实更新对象。

#### Scenario: memory review 不产生第二条 assistant 输出

- **GIVEN** 消费者提交的一轮触发后台 memory review
- **WHEN** 消费者从该轮 start sequence 持续读取 session stream 直到后台 review 结束
- **THEN** stream 只含该前台轮次的 assistant/tool/turn realtime events，不含 review fork 的 prompt、tool 过程或完成确认
- **AND** 若 memory 持久更新成功，消费者收到携带 memory 更新对象与 originating run trace 的最终 `self_evolution_review`

#### Scenario: skill review 暴露可归属的创建事件

- **GIVEN** 消费者提交的一轮触发后台 skill review，且 review 成功创建 Skill
- **WHEN** 消费者持续读取同一 session stream
- **THEN** stream 不含 review fork 的普通 assistant/tool/turn realtime events
- **AND** 消费者收到一条保留创建结果并标明 self-evolution 来源的 `skill_created` 业务事件
- **AND** 消费者随后收到携带 skills 更新对象与 originating run trace 的最终 `self_evolution_review`

#### Scenario: no-save 或写操作失败不产生更新事件

- **GIVEN** self-evolution review 未执行 mutating tool、只执行读取/列举，或所有 mutating tool result 均失败
- **WHEN** 后台 review 结束
- **THEN** consumer 不收到 `self_evolution_review` 更新事件
- **AND** review fork 的 raw assistant/tool/turn 过程仍保持私有

#### Scenario: incomplete fork 已有成功写入时仍报告真实更新

- **GIVEN** self-evolution fork 返回 `completed=False`
- **AND** 返回结果中存在至少一个已确认成功的 mutating memory/skill tool result
- **WHEN** hook 汇总真实更新对象
- **THEN** consumer 收到只包含这些成功更新对象的 `self_evolution_review`
- **AND** 不把未成功或只被 review 的对象标记为已更新
