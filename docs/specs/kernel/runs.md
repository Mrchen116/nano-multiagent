# kernel (agent) - Runs Specification

> 对齐: feat-552
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

消费者在 `build_kernel` 时可注入 `can_use_tool` 异步回调；启用 Auto 时由 SDK 装配共享自动权限判定。需要人工许可的交互入口调用该回调并采纳其决定；选择 `return_to_agent` 的普通运行将未获准原因返回 Agent，不进入人工等待。实际 Heartbeat/Cron 运行保持本文件规定的无人值守分流。

#### Scenario: 需要许可时 can_use_tool 被调用并采纳其决定
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel
- **WHEN** 运行中触发一次工具许可请求
- **THEN** `can_use_tool(tool_name, tool_input, ...)` 被调用;它返回 `allow` 则该次工具被放行, 返回 `deny` 则被拒绝

#### Scenario: 等待许可期间 interrupt 解除挂起
- **GIVEN** 一次许可请求正阻塞在 `can_use_tool`(模拟用户迟迟未决)
- **WHEN** 消费者对该会话调 `kernel.interrupt(session_id)`
- **THEN** 挂起的许可请求被解除为拒绝(deny),等待者立即返回而不会无限挂起

#### Scenario: 全局入口返回未获准结果
- **WHEN** 当前运行按入口优先级选择 return_to_agent，Auto 未允许当前动作
- **THEN** 返回明确原因，动作不执行，不创建权限 Future；该设置由应用元数据传入并由普通 child 继承。

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

#### Scenario: 消费者显式提供用户消息工具的审批上下文
- **GIVEN** 消费者消息工具显式声明结果审批投影，且真实成功结果与调用匹配
- **WHEN** 后续动作进行自动权限判定
- **THEN** 保留工具动作与附加上下文，实时宿主内容以 host_context_live 呈现，恢复内容以 host_context 呈现
- **AND** 来源由应用和 runtime 提供；明确真人原话可表达意图，Agent/系统/引用不因此成为真人；结果本身不直接允许动作。

#### Scenario: 普通或失败工具结果不成为授权依据
- **WHEN** 工具未声明投影、结果失败、或无法配对真实调用
- **THEN** 不产生实时宿主授权上下文；历史工具状态仍可作为执行事实
- **AND** 显式投影异常保留可区分的失败结果，不隐式改成人类输入或 classifier allow。


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
- **GIVEN** 分类选模型 C，主 run 使用 A
- **WHEN** C 超时、不可用、输出无法解析或请求上下文超限
- **THEN** 不换 A 或其他模型、不隐式裁剪重判，保留 no_verdict 原因且不计有效拒绝
- **AND** interactive 进入原人工入口；global wake 与普通 child 返回原因；Heartbeat（包括复用 global 主 session 的运行）及 Cron 按 unattended_fallback（默认 deny，可显式 allow）处理，配置放行不标成模型 allow。

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

### Requirement: 消费者可在模型失败后复用上一条用户消息换模型再跑

消费者在某 run 以模型可用性失败终态结束后，可为同一 session 换成另一个 runtime 模型，再发起不携带新 user parts 的下一 run。内核复用 transcript 里最近一条用户消息；不向消费者再投一条 user 消息。若该失败 run 已向消费者产出过非 provider-error 的 assistant 正文或工具事件，内核拒绝此次 replay，不原位重放。该入口不读取产品层备用列表，也不在一次 run 内切换模型。产品层以 `run_status.error.kind` 决定是否调用本入口，不以 assistant 正文是否为空或失败气泡文案为准。

#### Scenario: replay 不复制用户消息
- **GIVEN** 某 session 最近一轮因模型可用性失败结束，transcript 含用户消息与 provider-error assistant
- **WHEN** 消费者将该 session runtime 换成模型 B 并发起 replay-last-user
- **THEN** 新 run 以模型 B 请求 LLM，上下文含那条用户消息（失败 assistant 仍按既有规则过滤）
- **AND** 消费者不再收到一条新的 user 消息

#### Scenario: 仅 provider-error 气泡不阻止 replay
- **GIVEN** 某 run 只向消费者产出了 provider-error 失败 assistant，没有其它正文或工具事件
- **WHEN** 消费者将该 session runtime 换成模型 B 并发起 replay-last-user
- **THEN** 内核接受此次 replay

#### Scenario: 已有真实输出则不可 replay 原位重放
- **GIVEN** 某 run 已向消费者产出非 provider-error 的 assistant 正文或工具事件
- **WHEN** 该 run 随后失败
- **THEN** 消费者不能用 replay-last-user 原位重放该请求

### Requirement: 消费者可为运行启用输出前输入复核

SDK 消费者可在提交时启用输出复核，默认关闭。启用后，已接受但尚未被本轮模型采纳的输入会阻止旧正文提交；原运行在既有预算内带着未发送状态与新输入继续。消费者可使用相同提交边界保护产品工具的对外输出。

#### Scenario: 已接受新输入阻止旧正文
- **GIVEN** 消费者启用输出复核，模型正在生成一轮正文
- **WHEN** 消费者成功向该运行注入新输入，随后旧正文尝试提交
- **THEN** stream 不把旧正文报告为已公开助手消息，而提供完整未发送草稿记录；运行在预算允许时采纳新输入继续生成
- **AND** 输入中的多模态内容与 origin 保留，实际已执行工具结果继续有效

#### Scenario: 没有未采纳输入时提交
- **WHEN** 本轮已采纳全部在提交之前被接受的输入，且运行仍活动
- **THEN** 正文正常提交；提交之后才接受的输入在后续处理，不撤销已经提交的输出

#### Scenario: 产品工具提交绑定预期运行和上下文
- **GIVEN** 消费者持有工具执行时的运行身份与上下文代次
- **WHEN** 消费者尝试提交该工具输出
- **THEN** 只在身份匹配、运行活动且无更新输入时执行同步入队回调；过时或无效身份分别得到未提交结果，无 fallback 运行与发送副作用

#### Scenario: 预算与中断保持原语义
- **WHEN** 复核遇到运行上限或用户中断
- **THEN** 运行按原有终态结束，不强制发送旧稿，不把尚未进入下一次模型调用的输入报告为已采纳；未消费输入仍按既有恢复或 held 交接处理

#### Scenario: 默认消费者不改变行为
- **WHEN** 消费者未启用输出复核
- **THEN** 原有正文交付、steer 与工具行为保持不变

#### Scenario: 候选状态精确持久化
- **WHEN** 同一运行先提交一份正文，随后产生另一份未发送候选，即使两份文本相同
- **THEN** 模型历史按候选身份分别保留本地已提交与未发送状态；持久化重载后仍可区分，不把本地提交描述为远端确认

### Requirement: 消费者可原子地只在 Session 空闲时提交输入

消费者可以提交带稳定 submission identity 的空闲运行请求。Session 有已经受理、运行或尚未完成清理的执行，以及串行生命周期操作时，该请求不注入消息、不创建排队运行。正常 submit 与后台通知的默认行为保持兼容。

#### Scenario: 忙碌时零副作用拒绝
- **GIVEN** Session 已经有受理中的执行或压缩操作
- **WHEN** 消费者调用空闲提交
- **THEN** 得到未受理结果，Session 不增加输入或运行

#### Scenario: 同时到达的请求
- **WHEN** 两个空闲提交或空闲提交与后台通知竞争同一 Session
- **THEN** 每个被受理的输入都有准确的执行身份，Session 不并行运行
- **AND** 已受理且仍在运行或已持久写入输入时，同一 submission identity 的重试复用原收据；输入持久前已终止的受理可以重试

#### Scenario: 进程重启后查提交收据
- **WHEN** 消费者按原 Session 与 submission identity 查询收据
- **THEN** 可以判断输入是否已经持久写入，以及其实际 turn identity
- **AND** 未持久写入的受理不被报告为已进入上下文

### Requirement: SDK 消费者可同步观察 Session 级执行事实

SDK 消费者可注册和关闭进程内事件观察器，按发布顺序取得稳定 event identity、时间与实际 Session／Turn identity。普通子执行没有顶层 run identity 不影响其消息、工具、usage 和终态的可观察性；子归属与后台 task 类型来自真实执行记录。

#### Scenario: 普通子执行无顶层 run identity
- **WHEN** 子 Session 执行工具并完成
- **THEN** 观察器收到同一真实 child 的工具开始／结束、轮次统计和终态
- **AND** 不需要为它伪造顶层 run identity

#### Scenario: 子创建与补充关联
- **WHEN** 消费者的主 Session 创建子执行或给已有 child 补充输入
- **THEN** 可以观察真实 parent/child 关联与实际接收的补充，不从描述文字推断身份

#### Scenario: 关闭或异常观察器
- **WHEN** 消费者关闭自己的观察器，或该观察器处理事件发生异常
- **THEN** 不改写工具的模型可见结果，不重放工具副作用
- **AND** 正常关闭等待已经进入的回调结束，后续不再向该观察器投递

### Requirement: 持久输入边界可被观察而不冒充消息消费

消费者可观察实际输入持久写入的边界，带该提交的身份。初始唤醒输入持久化与之后工具返回正文的持久化是不同事件，不能将前者解释为已经读完后者。

#### Scenario: 工具读取之前收到唤醒收据
- **WHEN** 一个仅含通知提示的初始输入被持久写入
- **THEN** 观察器只能据此确认该提示已进入 Session，不能得出其引用正文已被读取的结论

### Requirement: 消费者可核对实际持久写入的工具正文

SDK 观察器可获得某个工具结果实际持久写入后的证明，含真实 Session、Turn、工具调用及消息身份、最终内容摘要和序列化状态。证明描述实际保存并用于模型上下文的内容，而不是原始工具对象或 UI 展示；序列化回退仍可维持原模型行为，但必须与正常序列化区分。

#### Scenario: 正常序列化正文可核对
- **WHEN** 工具结果正常序列化并成功持久写入
- **THEN** 消费者收到同一工具调用的持久证明，内容摘要对应实际模型内容
- **AND** 当前轮模型使用的工具内容与持久内容一致，消费者不需要读取内核私有存储

#### Scenario: 序列化回退不会冒充正常结果
- **WHEN** 工具序列化失败并以既有回退内容成功持久写入
- **THEN** 消费者可辨认回退状态和实际回退内容摘要，不能误认为原目标正文已正常持久化
- **AND** 不因此改变既有工具的参数或回退结果

#### Scenario: 持久失败不产生成功证明
- **WHEN** 工具消息未能完成持久写入
- **THEN** 消费者不会收到该消息的成功持久证明，不能提前确认其引用内容已摄取

### Requirement: Auto 来源语义独立于消息承载角色

#### Scenario: 真人回复前保留 assistant 文本
- **WHEN** 主会话中的真人回复跟在 assistant 文本之后
- **THEN** 按固定 CC 的启用分支保留最近文本末尾 2000 UTF-16 单位用于解释回复；尚无真人回复的当前旁白不加入。

#### Scenario: 自动触发与 Agent 输入
- **WHEN** user-role 内容实际来自 Cron、heartbeat、后台通知或 Agent
- **THEN** 审批保留对应非真人来源及 CC 说明，不能把该内容当作新的人工确认或触发真人回复配对。

#### Scenario: 同会话跨轮与恢复
- **WHEN** 实时宿主上下文经历普通跨 turn、compact 或进程恢复
- **THEN** 普通跨 turn 保留实时来源；compact 只使用新窗口；恢复的宿主内容降为 host_context，不通过查询历史提升为实时授权。

### Requirement: Auto 有效拒绝按会话计数并保留产品分流

#### Scenario: 主会话与普通 child
- **WHEN** 多个 run 或工具产生有效自动拒绝
- **THEN** 同一主 session 跨 run 累计 consecutive/total；普通 child 各自计数；默认 3/20，成功清连续数，总阈值处理清总数，不新增永久暂停锁。

#### Scenario: 达阈值与服务故障
- **WHEN** 达到拒绝阈值，或分类服务未给有效结论
- **THEN** interactive 使用既有人工入口，global wake/普通 child 返回原因，Heartbeat/Cron 等原无人值守运行使用其 fallback；global Heartbeat 的自动入口不被同 session 的全局交互设置覆盖，child 的 BACKGROUND_TASK/USER 调度值不改写其继承的全局交互；故障不计为用户未授权。

### Requirement: 子任务保留更新后的 Auto 约束与原始来源

#### Scenario: 新派发与 follow-up
- **WHEN** 父 Agent 创建或继续 child
- **THEN** agent 调用保持免审；工具/skills 不扩大，继承有效审批设置和带原始来源的父已读上下文；child 的实际动作继续过 gate。

#### Scenario: 委派或结果声称用户批准
- **WHEN** Agent 文本声称获得了用户同意
- **THEN** 不把该主张本身提升为人工授权，普通 child 自身的非真人消息也不形成确认配对。
