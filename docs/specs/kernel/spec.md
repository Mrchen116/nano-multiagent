# kernel (agent) Specification

> 对齐: bugfix-402
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本契约层只收
> **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 +
> 归档 design)。每条 Scenario 的主语 = 经 `agent.sdk` 调用内核的产品(`coding_cli` /
> `personal_assistant`)或 `tests/contract/` 契约测试。

## Purpose

`agent`(内核)是整个系统唯一的 Agent 执行内核,是一个**库**:单 Agent 运行时 + 工具执行 + 技能发现
+ 事件扩展 + 会话持久化 + 上下文压缩 + 多 LLM provider 适配。

它对外**只暴露 `agent.sdk`**——`build_kernel()` 装配出一个进程内 `Kernel`,消费者持有它并 `await` /
调用其方法。内核**不内置任何 HTTP / 网络 API**;呈现为终端软件、常驻 gateway 还是云 API,是产品层
决策,内核不持形态偏好(refactor-387)。

**显式不负责**:不知道什么是 coding / assistant(产品语义);不做 IM 接入 / channel 路由 / heartbeat
调度;不做 CLI 交互;不做对外网络服务。这些由消费它的产品承担。

## Requirements

### Requirement: 内核对外只经 agent.sdk 暴露,产品不得依赖内核内部

`agent.sdk` 是内核唯一对外面。消费者只能 import `agent.sdk`;内核内部层(`agent.core` /
`agent.platform` / `agent.products`)不得被产品直接 import,`agent.sdk` 也不得反向依赖任何产品包。

#### Scenario: 产品越界 import 内核内部被拦
- **GIVEN** `coding_cli` 或 `personal_assistant` 的某文件
- **WHEN** 它写下 `import agent.core...` / `import agent.platform...` / `import agent.products...`
- **THEN** 契约测试(`tests/contract/test_agent_sdk_boundary_contract.py`)失败,挡住越界

#### Scenario: agent.sdk 不上行依赖产品
- **WHEN** 审阅 `agent.sdk` 下任一模块的 import
- **THEN** 其中没有对 `coding_cli` / `personal_assistant` / `IM` 的 import(否则形成循环依赖)

#### Scenario: core 不依赖 platform / products
- **WHEN** 审阅 `agent.core` 下任一模块的 import
- **THEN** 其中没有对 `agent.platform` / `agent.products` 及 web 框架(fastapi / starlette)的
  import——provider 与存储细节不反向污染纯逻辑运行时

### Requirement: build_kernel 装配出可用的进程内 Kernel

消费者调
`agent.sdk.build_kernel(product_profile, llm_config, can_use_tool, repo_root, host_capabilities)`
得到一个装配完成、可直接使用的 `Kernel`;无需起任何子进程或 HTTP 服务。可选的
`host_capabilities` 是通用 dispatcher:SDK/core 只定义按 namespaced capability、结构化 payload
和可信 context 调用宿主的机制,不声明 cron 或其他具体产品命令;dispatcher 不进入 session
metadata、持久化记录或 prompt。可信 context 携带 session、workspace、product 与 agent 身份;
agent 身份取自消费者在创建会话时提供的元数据,未提供时为空——按 agent 身份路由的宿主能力在
空身份下返回稳定的 capability unavailable 错误,而非误路由。

#### Scenario: 用产品 profile + LLM 配置装配 Kernel
- **GIVEN** 一个 `ProductProfile`(如 `LOCAL_CODING_PROFILE` / `PERSONAL_ASSISTANT_PROFILE`)、一份
  `LLMFactoryConfig`(provider + model + base_url)、一个 `can_use_tool` 回调,以及可选的
  host capability dispatcher
- **WHEN** 消费者调 `build_kernel(...)`
- **THEN** 返回一个 `Kernel` 实例,其后所有会话/运行均在进程内执行(无子进程、无 loopback HTTP)

#### Scenario: Kernel 暴露稳定的对外方法集
- **GIVEN** 一个已装配的 `Kernel`
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact`,以及非阻塞方法
  `submit` / `stream` / `interrupt` / `cancel` / `get_run` / `list_session_tools` /
  `get_llm_config` / `reconfigure_llm`,并同时暴露供异步消费者使用的 `aclose()` 与同步兼容的
  `close()`

#### Scenario: 宿主注入能力
- **WHEN** 消费者构建 Kernel 并提供 host capability dispatcher
- **THEN** 工具可通过通用 dispatcher 调用已注册能力,SDK 不需要理解该能力的产品语义

#### Scenario: 宿主未提供能力
- **WHEN** 工具请求未注册的 host capability
- **THEN** 返回稳定的 capability unavailable 错误,不访问 loopback HTTP 或持久化 callback

### Requirement: 创建会话必须绑定 workspace_root

消费者创建会话时绑定一个 `workspace_root`;该路径绑定到会话生命周期,后续该会话内工具执行的
`cwd` / 安全沙箱边界、以及工具/hook/skill 的工作区层扫描均以此为根。

#### Scenario: 创建会话返回绑定工作区的 Session
- **WHEN** 消费者 `await kernel.create_session(workspace_root=<path>)`
- **THEN** 返回一个 `Session`,其工作区根固定为该 `workspace_root`,会话内后续工具执行均在此根下进行

### Requirement: submit 非阻塞调度一轮运行,事件经 stream 异步消费

`submit()` 把一轮(turn)调度到内核后台事件循环并立即返回一个 `RunRecord`(初始状态 QUEUED);消费者
经 `stream()` 异步迭代该会话的事件,跨自己的事件循环也能收到。

#### Scenario: 提交后从 stream 收到运行状态事件
- **GIVEN** 一个已创建的会话
- **WHEN** 消费者 `kernel.submit(session_id, parts=[{type:text,...}], workspace_root=...)` 后
  `async for ev in kernel.stream(session_id, after_sequence=0)`
- **THEN** 收到扁平化事件 dict(含 `event` / `session_id` / `sequence_num` + payload 字段),
  其中出现 `run_status` 事件,运行完成时其 `status` 为 `completed`(或失败时 `failed`)

#### Scenario: 同步提交完成后运行记录可查
- **WHEN** 提交一轮并轮询 `kernel.get_run(run_id)`
- **THEN** 运行到达终态后记录 `status == "completed"` 且 `turn_id` 非空

### Requirement: 工具使用权限经注入的 can_use_tool 回调裁决

内核不内置权限策略;消费者在 `build_kernel` 时注入 `can_use_tool` 异步回调。当某轮需要工具使用许可
时,内核调该回调并据其 `PermissionDecision` 放行或拒绝。

#### Scenario: 需要许可时 can_use_tool 被调用并采纳其决定
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel
- **WHEN** 运行中触发一次工具许可请求
- **THEN** `can_use_tool(tool_name, tool_input, ...)` 被调用;它返回 `allow` 则该次工具被放行,
  返回 `deny` 则被拒绝

#### Scenario: 等待许可期间 interrupt 解除挂起
- **GIVEN** 一次许可请求正阻塞在 `can_use_tool`(模拟用户迟迟未决)
- **WHEN** 消费者对该会话调 `kernel.interrupt(session_id)`
- **THEN** 挂起的许可请求被解除为拒绝(deny),等待者立即返回而不会无限挂起

### Requirement: 运行可被中断与取消

消费者可中断某会话当前活动运行(`interrupt`),或按 `run_id` 取消排队/运行中的运行(`cancel`);两者对
不存在的目标安全无害。

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

### Requirement: LLM 配置可查询、可纯配置切换

消费者可读当前 LLM 配置,也可在不重建 runtime 的前提下打补丁切换 provider / model;provider 切换是
纯配置动作,不需改 runtime / tool / session 代码。

#### Scenario: 读取当前 LLM 配置
- **WHEN** 消费者 `kernel.get_llm_config()`
- **THEN** 返回的配置含 `provider` / `model` / `base_url` 字段

#### Scenario: 切换 provider / model 后查询反映新值
- **WHEN** 消费者 `kernel.reconfigure_llm(provider=..., model=...)`
- **THEN** 返回更新后的配置;随后 `get_llm_config()` 也反映该 provider / model

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限,必要时把旧轮次摘要化并落盘为压缩记录,保留首个保留
事件 id 以保证可重建与可审计;overflow 后可恢复重试。消费者也可手动触发压缩。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果(或在无需压缩时返回 None),压缩落盘后会话仍可由事件重放重建

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `task` 等基础工具,默认启用工作区安全约束;所有工具执行经
工具注册表分发。产品可经产品 profile + 工作区配置目录追加/筛选工具。

#### Scenario: bash 工具输出超限被截断且暴露完整输出路径
- **WHEN** 经内核运行的一次 `bash` 工具产生超过上限的输出
- **THEN** 工具结果标记 `truncated` 为真,并提供可取完整输出的路径

#### Scenario: bash 工具超时/被信号中断转为明确错误
- **WHEN** 一次 `bash` 执行超时或被信号中断
- **THEN** 工具结果暴露稳定的超时/信号细节(而非静默挂起或丢失)

#### Scenario: 会话可用工具集可查询
- **WHEN** 消费者 `kernel.list_session_tools(session_id, workspace_root=...)`
- **THEN** 返回该会话可用工具的描述信息

### Requirement: Hook 体系对外契约稳定(事件集 + intercept/observe 语义)

内核暴露稳定的 hook 事件集与拦截/观察语义,供产品与工作区注入扩展行为。intercept 事件可改变行为,
observe 事件只观察;单个 hook 异常/超时不中断主流程(fail-open)。

#### Scenario: intercept 事件集与默认 priority/timeout 稳定
- **WHEN** 产品或工作区注册 hook 处理器
- **THEN** intercept 事件恰为 `{input, before_agent_start, tool_call, tool_result}`;observe 事件
  含 `turn_start` / `run_error` 等;默认 priority 为 100、默认 timeout 为 1500ms

#### Scenario: 单个 hook 失败不中断主流程
- **GIVEN** 一个注册的 hook 在执行中抛错或超时
- **WHEN** 对应事件触发
- **THEN** 主运行流程继续(fail-open),其它 hook 仍按 priority 顺序执行

### Requirement: Skill 自动发现走 prompt 列表,显式调用改写为自然语言

存在可见 skill 时,内核在 system prompt 注入 `<available_skills>` 列表(名称 + 描述 + 路径),模型按需
用 `read` 工具读取 SKILL.md,而非注入全文;消费者输入的 `/skill:<name>` 被改写为自然语言指令。

#### Scenario: 显式 skill 命令被改写
- **WHEN** 消费者输入 `/skill:doc`(或带参数 `/skill:doc fix heading spacing`)
- **THEN** 内核将其改写为 `Use the "doc" skill for this request.`(带参数时追加 `User input:` 段),
  然后走常规推理,不展开 SKILL.md 原文

### Requirement: 会话事件溯源持久化,进程重启后可恢复

每次状态变更产生事件并经会话存储持久化;会话可由事件重放重建,进程重启后可恢复。运行时不直接写 SQL,
只经会话存储接口。

#### Scenario: 重启后恢复会话
- **GIVEN** 一个已持久化的会话
- **WHEN** 进程重启后消费者按 session_id 取该会话
- **THEN** 会话历史与状态可由持久化事件重放重建

### Requirement: 经 append_message 带外写入的消息对后续轮次可见

消费者(如 Gateway)可在不触发模型运行的前提下,经 `append_message` 把一条消息持久化进会话;该消息进入会话
线性历史,对该会话此后任意一轮运行可见——既不被丢弃,也不被运行时的内存历史缓存遮蔽。内核另提供
`invalidate_session_cache`,供消费者在带外改动会话持久化后显式失效内存缓存。

#### Scenario: 带外追加的消息进入下一轮上下文
- **GIVEN** 一个已运行过至少一轮的会话
- **WHEN** 消费者经 `append_message` 向该会话追加一条消息,随后再提交一轮运行
- **THEN** 该追加消息出现在这一轮的模型上下文里(不被陈旧缓存或历史链断裂遮蔽)

### Requirement: 持久化 transcript 在进入模型前保持 tool call 闭合

消费者中断、取消或关闭包含工具调用的运行后,内核必须使已持久化的每个 assistant tool call
具有对应的 tool result。进程异常退出留下的历史悬空调用在下次提交运行前自动恢复为取消终态;
恢复保持 append-only、按 tool call id 幂等,并向 provider 物化为合法消息顺序。只读加载、
列表和预览不得因检查完整性而改写会话。

#### Scenario: 中断权限等待后继续同一会话
- **GIVEN** 一个运行已经持久化 assistant tool call,正在等待权限决定
- **WHEN** 消费者调用 `kernel.interrupt(session_id)`,随后向同一会话再次 `submit`
- **THEN** 原 tool call 以取消结果闭合,新一轮模型请求收到合法 transcript 并可继续运行

#### Scenario: 重启后恢复悬空 tool call
- **GIVEN** JSONL 历史中存在没有对应 tool result 的 assistant tool call
- **WHEN** 新 Kernel 实例加载该 session 并提交下一轮
- **THEN** 内核自动追加一次引用原 call id 的恢复记录,并把取消结果物化到合法位置

#### Scenario: 重复准备恢复保持幂等
- **GIVEN** 某个 call id 已有恢复记录
- **WHEN** session 被并发或重复准备、fork 或继续运行
- **THEN** 不为该 call id 产生第二条恢复结果,transcript 仍保持闭合

#### Scenario: 只读加载没有修复副作用
- **GIVEN** session 含有悬空 tool call
- **WHEN** 消费者只执行列表、预览或其他只读加载
- **THEN** 会话文件不发生变化;下一次实际提交运行时才原子地写入恢复结果

### Requirement: 模型错误按统一可恢复语义重试并保留原始原因

内核对所有 LLM provider 使用同一 provider-neutral 错误事实与重试策略。网络、超时、限流、
额度/余额及无法明确判定为永久的错误默认可重试;明确参数/格式错误、无效凭证、权限拒绝、
资源或能力不存在/不支持不可重试。HTTP 状态码本身不单独决定 4xx 是否可重试。重试策略含
退避,连续失败可能引入额外冷却等待——消费者观察到的恢复延迟可能超过单次重试间隔。重试不得
造成重复输出:一次请求已向消费者产出部分内容后,中途故障按最终失败处理,不原位重放该请求。

#### Scenario: 语义不明或可能恢复的 4xx 继续重试
- **WHEN** provider 返回限流、额度/余额或没有明确永久语义的 4xx
- **THEN** 内核在既定预算内重试同一请求

#### Scenario: 明确永久错误快速失败
- **WHEN** provider 或本地 mapper 明确报告参数/格式、凭证、权限、not-found 或 unsupported 错误
- **THEN** 内核不重复发送相同请求,并把实际错误交给消费者

#### Scenario: 已产出内容后的中途故障不重复输出
- **GIVEN** 一次模型响应已向消费者产出部分内容
- **WHEN** 流在到达终态前故障
- **THEN** 内核不重放该请求、不产生重复内容,本轮以真实上游错误失败

#### Scenario: 重试耗尽返回最后真实错误
- **WHEN** 可重试错误耗尽重试预算
- **THEN** 最终 `ModelError` 保留最后一次上游 message/code/type/status,重试次数仅作为附加诊断,
  不用通用 exhaustion 或 stream-ended 文案替换真实原因

### Requirement: Kernel 关闭会收拢所有 owned runs

`Kernel.aclose()` 与同步兼容接口 `Kernel.close()` 必须共享幂等关闭状态,停止接受新运行,
解除权限等待,中断或取消仍在执行/排队的 run,等待 RunsRegistry 自己创建的 Task 在所属
event loop 与 Context 中进入终态,再停止并关闭 loop。关闭开始后不得创建新的 queued run;
异步消费者使用 `aclose()` 时不得阻塞其 event loop。

#### Scenario: 有活动运行时关闭
- **GIVEN** Kernel 存在 running run 或权限等待
- **WHEN** 异步消费者 await `kernel.aclose()` 或同步消费者调用 `kernel.close()`
- **THEN** 相关 run 在有限 grace period 内进入 completed/failed/cancelled 之一,Registry 不遗留
  Task,tracing scope 在原 Task Context 中退出

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
