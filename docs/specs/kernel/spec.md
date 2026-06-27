# kernel (agent) Specification

> 对齐: feat-440-tool-rejection-feedback
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
`agent.platform`)不得被产品直接 import,`agent.sdk` 也不得反向依赖任何产品包。`agent.sdk` 的公开
符号是一份**精确允许名单**(逐字钉死,见归档 design 接口总表),由表面守卫 contract 测试守卫:多导出
或少导出都失败。除显式豁免外,每个导出对象的类型须由 `agent.sdk` 自身拥有(SDK-owned),不得是
内核内部模块拥有的对象直接外泄。

#### Scenario: 产品越界 import 内核内部被拦
- **GIVEN** `coding_cli` 或 `personal_assistant` 的某文件
- **WHEN** 它写下 `import agent.core...` / `import agent.platform...` / `import agent.products...`
- **THEN** 契约测试(`tests/contract/test_agent_sdk_boundary_contract.py`)失败,挡住越界
  (`agent.products` 包已退役,但其前缀仍在禁止名单内,防止以旧概念重建)

#### Scenario: agent.sdk 不上行依赖产品
- **WHEN** 审阅 `agent.sdk` 下任一模块的 import
- **THEN** 其中没有对 `coding_cli` / `personal_assistant` / `IM` 的 import(否则形成循环依赖)

#### Scenario: core 不依赖 platform / products
- **WHEN** 审阅 `agent.core` 下任一模块的 import
- **THEN** 其中没有对 `agent.platform` 及 web 框架(fastapi / starlette)的
  import——provider 与存储细节不反向污染纯逻辑运行时

#### Scenario: 新增导出未进允许名单
- **WHEN** `agent.sdk.__all__` 含允许名单之外的名字(或缺名单内的名字)
- **THEN** 表面守卫 contract 测试失败

#### Scenario: 导出对象由内核内部模块拥有
- **WHEN** `agent.sdk` 的某导出(不在显式豁免名单内),其类型定义在 `agent.core` / `agent.platform`
  内部模块
- **THEN** 所有权守卫 contract 测试失败

#### Scenario: 豁免名单容纳内核必拥有的边界类型
- **WHEN** 导出属于显式豁免名单(`RunOrigin` / `PermissionDecision` / `TERMINAL_RUN_STATUSES` /
  `ToolPresenter` / `ToolPresentationEvent`——core/platform 引用、物理上无法 sdk-owned,由 sdk re-export)
- **THEN** 所有权守卫放行;但豁免名单本身逐字钉死,增删名单成员同样使测试失败

#### Scenario: sdk-owned typing 别名不计入豁免
- **WHEN** 导出为 `CanUseToolFn`(sdk-owned 的 `Callable` 类型别名,定义在 `agent/sdk/kernel.py`,
  无 class `__module__`、非 core/platform re-export)
- **THEN** 闸 2 对 typing 别名特殊处理放行,且它**不在**豁免名单之列

### Requirement: 装配与会话分两层,内核产品中立

`agent.sdk` 不提供"产品"对象(无 `ProductProfile` / `ProductDefinition` / 内置产品常量)。装配分两层,
内核对三类应用(coding_cli / personal_assistant / 任意外部应用)无差别对待,无任何"一方产品"分支:

- `build_kernel(llm, tools, hooks, can_use_tool=None, workspace_config_dirname=…, repo_root=None,
  skill_search_roots=(), tool_search_roots=(), hook_search_roots=())` —— 建一次进程级**共享基座**:
  `llm` 为 SDK-owned `LLMConfig`(providers/models 目录 + 连接 + 默认);`tools` 为原生工具对象**目录**;
  `hooks` 为 `setup(hooks: HookAPI)` 形态 callable;`skill_search_roots` / `tool_search_roots` /
  `hook_search_roots` 为部署级用户插件目录(消费者显式传入的根,非 ConfigResolver),内核在工作区
  `<repo_root>/.nano/{tools,hooks,skills}` 运行时发现之外额外发现这些目录,空 → 仅工作区。模型注册表
  初始化在内部,消费者无前置时序义务;装配完成后所有会话/运行均在进程内执行(无子进程、无 loopback HTTP)。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)` —— 每 agent
  带齐配置:`enabled_tools` 从工具目录选子集;`features` 开关内核通用 feature;`prompt` 为 SDK-owned
  `PromptSlots`。不收 `model`——model 是 per-run 的,消费者每轮经 `submit(model=...)` 提供。

#### Scenario: 应用零前置调用直接装配
- **GIVEN** 应用构造了 `LLMConfig`(含 `from_env()`)、工具目录、hooks
- **WHEN** 未调用任何注册表初始化函数,直接 `build_kernel(...)`
- **THEN** Kernel 正常装配,模型解析、默认 provider 推导可用;无子进程、无 loopback HTTP

#### Scenario: 三类应用对内核同构
- **GIVEN** coding_cli、personal_assistant、任意外部应用
- **WHEN** 各自 `build_kernel(基座)` + `create_session(per-agent)`
- **THEN** 内核对三者无差别对待,无"一方产品"分支;各自的品牌/默认在自己包的工厂里,内核不感知

#### Scenario: 工具目录共享、会话选子集
- **WHEN** `build_kernel(tools=[A,B,C])` 后 `create_session(enabled_tools=[A,B])`
- **THEN** 该会话只暴露 A、B;工具实现实例在基座注册一次、不因会话重建

#### Scenario: Kernel 暴露稳定的对外方法集
- **GIVEN** 一个已装配的 `Kernel`
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact`,非阻塞方法
  `submit` / `stream` / `interrupt` / `cancel` / `get_run` / `list_session_tools` /
  `get_llm_config`,中立能力查询 `list_models` / `list_tools` / `list_features` /
  `list_skills`,以及 prompt 预览 `assemble_prompt_preview`;并同时暴露供异步消费者使用的 `aclose()`
  与同步兼容的 `close()`

### Requirement: 应用以原生 Tool/Hook 对象扩展,契约为 SDK-owned Protocol

应用经 `build_kernel(tools=…, hooks=…)` 传入原生对象扩展内核,无须修改 `agent` 内部源码、无须进任何
产品目录。`Tool` / `ToolContext` / `HookAPI` 是 SDK-owned 结构化 Protocol(鸭子结构,内核真造对象天然
满足、无 core→sdk 倒挂)。副作用工具可在应用包内闭包持有应用子系统句柄,经 `build_kernel(tools=…)`
传入后副作用直达应用子系统;内核不提供也不需要 `host_capabilities` 回调通道。

#### Scenario: 对象满足 Tool 契约即可装配
- **GIVEN** 一个对象具备 `name: str`、`description: str`、`input_schema: dict`、可调用 `run(args, ctx)`
  (无须继承内核基类)
- **WHEN** 它出现在 `build_kernel(tools=…)` 且某会话 `enabled_tools` 选了它
- **THEN** 被注册并可执行,`ctx`(结构化 Protocol)提供承诺字段子集(session_metadata、repo_root、
  工作区路径族);非承诺字段不进 Protocol、不承诺

#### Scenario: 副作用工具闭包直连自己的服务、无内核回桥
- **GIVEN** 一个在应用包内定义、闭包持有应用子系统句柄(如 Gateway 调度器)的工具,经
  `build_kernel(tools=…)` 传入
- **WHEN** 会话中调用它
- **THEN** 副作用直达应用子系统;内核不提供 `host_capabilities` 通道(`HostCapabilityDispatcher`
  不在公共表面)

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

### Requirement: 经 submit 投递的消息可 steer 进活跃 run 的下一轮

消费者经 `Kernel.submit(steer=True)` 投递用户消息时，内核按会话当前是否有活跃 run 决定注入或新建，结果由返回的 `RunInfo.injected` 标识；`steer=False`（默认）保持"总是新建 run"的既有语义。

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
- **THEN** 该消息不丢失，由一个后续 run 接着消费，其 origin 跟随注入来源（用户消息为 USER）、内容（含图片）完整保留

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
不存在的目标安全无害。`cancel` 必须**强制终止**承载该 run 的执行(不依赖被取消代码合作式自查),使该
run 即使 parked 在工具执行、LLM 等待或权限决策上也能终止;终止后该 run 占用的 session 串行锁必须释放,
同一 session 后续 `submit` 不被此前 run 永久阻塞。取消同时取消该 run 仍在等待的权限请求(resolve 为拒绝)。

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

当一条 run 处于"活着但暂无业务输出"的窗口(执行静默长工具、等待 LLM 返回、parked 等待用户权限决策)时,
内核必须经 `kernel.stream` 周期性发出 liveness 事件(携带 run_id),间隔显著小于消费者侧的存活判定窗口。
该事件仅表征"该 run 仍存活",消费者可据其判定存活而不误判为卡死。三类窗口走同一事件通路,消费者无需按
窗口类型分别豁免。

#### Scenario: 执行静默长工具期间 stream 仍有事件
- **GIVEN** 某 run 正在执行一个长时间无标准输出的工具(如长命令)
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 在工具执行全程内,stream 周期性产出携带该 run_id 的 liveness 事件(不必等工具结束才出现)

#### Scenario: 等待 LLM 返回期间 stream 仍有事件
- **GIVEN** 某 run 正在等待 LLM 返回且长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件

#### Scenario: parked 等待权限决策期间 stream 仍有事件
- **GIVEN** 某 run parked 在等待用户权限决策、长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件(与工具/LLM 等待同一事件通路),消费者据此判存活,无需 permission 专用豁免

### Requirement: LLM 配置可查询,每轮对话的模型由消费者随 run 提供

消费者可读当前 LLM 配置(provider/base_url/默认目录,供选择器/能力上报用);模型不再是 kernel 级固化的
全局属性,改为消费者在发起每个 run 时随 `submit` 提供,内核不持有对话默认 model。`get_llm_config()` 返回
SDK-owned `LLMConfig` DTO(内核内部 `LLMFactoryConfig` 不出边界),仍报告 build-time 的 active 连接供
选择器使用;`create_session` 不收 model。`reconfigure_llm`/`bind_llm_client` 失去调用方而退役,内核不再
有"当前全局 active model"的概念。

#### Scenario: 读取当前 LLM 配置
- **WHEN** 消费者 `kernel.get_llm_config()`
- **THEN** 返回 SDK-owned `LLMConfig`,含 `provider` / `model` / `base_url` 等字段

#### Scenario: submit 携带 model 并在该 run 生效
- **WHEN** 消费者 `kernel.submit(session_id=..., parts=..., model=M)`
- **THEN** 该 run 的 LLM 请求以 `model=M` 发出(session JSONL 该 turn 记录可见)

#### Scenario: 同一 run 的内核续跑复用本 run 的 model
- **GIVEN** 一个以 `model=M` 提交的 run 在处理中产生了需续跑的消息
- **WHEN** 内核自身发起续跑
- **THEN** 续跑仍以 `model=M` 发出,不要求消费者再次提供,也不回退到任何内核默认

#### Scenario: 模型按其注册的 provider 路由请求格式
- **GIVEN** model `M` 在 config 注册于 provider `P`
- **WHEN** 以 `model=M` 提交 run
- **THEN** 内核用 `P` 声明的 client / 请求格式发出(不跨 provider 借用其它格式)

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限,必要时把旧轮次摘要化并落盘为压缩记录,保留首个保留
事件 id 以保证可重建与可审计;overflow 后可恢复重试。消费者也可手动触发压缩。压缩判定所用的**上下文上限按当前轮所用模型取**：消费者经 `build_kernel(llm=…)` 为某模型声明的上下文窗口生效于该模型的运行;未声明窗口的模型回退到内核默认上限。判定上限时保留的安全余量是全局策略量,不随模型变化。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果(或在无需压缩时返回 None),压缩落盘后会话仍可由事件重放重建

#### Scenario: 按当前轮模型的窗口判定压缩
- **GIVEN** 消费者为某模型声明了与内核默认不同的上下文窗口
- **WHEN** 用该模型推进一个持续增长的会话直到接近"该模型窗口 − 全局安全余量"
- **THEN** 内核在该模型窗口对应的边界触发压缩,而非内核默认上限对应的边界

#### Scenario: 未声明窗口的模型回退默认上限
- **GIVEN** 某模型未声明上下文窗口(或声明值非正整数)
- **WHEN** 用该模型推进会话
- **THEN** 内核按默认上限判定压缩,运行不因缺少该声明而报错

#### Scenario: 工作区绑定的会话压缩落盘后运行透明继续
- **GIVEN** 一个绑定了 `workspace_root` 的会话(消费者经 `create_session(workspace_root=…)` 创建),其上下文已增长到触发压缩(自动阈值或 overflow 恢复)
- **WHEN** 消费者继续推进该会话一轮
- **THEN** 内核完成压缩并落盘,该轮以成功终态正常完成,**不因无法定位会话存储位置而失败**;压缩后会话仍可由事件重放重建,且先前轮次内容不被清空

### Requirement: 内核内置基础工具集,执行受工作区安全约束

内核内置 `read` / `write` / `edit` / `bash` / `agent` 等基础工具,默认启用工作区安全约束;所有工具执行经
工具注册表分发。应用经 `build_kernel(tools=…)` 追加原生工具、`create_session(enabled_tools=…)` 选子集;
工作区 `<repo_root>/.nano/tools` 下的同名工具可 override 内置(replace 语义,不致装配崩溃)。

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

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示(`tool_start`/`tool_end` 携带的 presentation:`visible`/`label`/`summary`/
`detail`/`emoji`)由该工具自身的 `presenter`(SDK-owned `ToolPresenter`,缺省即无)决定;未带 presenter 的
工具走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具,其 presenter 随对象一起生效,无须额外注册步骤。
`ToolPresenter` / `ToolPresentationEvent` 在公共表面。`emoji` 随工具/presenter 走(feat-425):presenter
可在 `ToolPresentationEvent.emoji` 声明工具的折叠行图标,经事件透传给消费者;未声明则为空串,由消费者自行
兜底。内置工具 `read` / `write` / `edit` / `bash` / `web_fetch` / `agent` / `memory` / `skill_manage` /
`task_stop` 均自带 presenter,其 `tool_end` 事件携带结构化 `detail`(而非默认的截断参数);`detail` 中的大
字段(stdout/stderr/diff/content)受硬上限尾截断,截断时 `detail.truncated` 为真。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具,消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的
  `visible`/`label`/`summary`/`detail`/`emoji`

#### Scenario: presenter 声明的 emoji 随事件透传
- **GIVEN** 一个 presenter 在 `ToolPresentationEvent.emoji` 声明了图标的工具(如 `web_fetch` 自带 🌐)
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 携带该 `emoji`;presenter 未声明 emoji 的
  工具,事件的 `emoji` 为空串(消费者据此兜底)

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具(如 MCP / 工作区运行时发现的工具)
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation(可见 + 名称 + 截断后的参数),
  不因缺 presenter 而丢失事件或报错

#### Scenario: 工作区 DIY 工具自带 presenter 被认
- **GIVEN** 用户在 `<repo_root>/.nano/tools` 放置一个工具类,并在其对象上声明了 `presenter`
- **WHEN** 该工具被运行时发现并调用
- **THEN** 其 `tool_start`/`tool_end` 事件的 presentation 为该 DIY presenter 产出的
  `summary`/`detail`(不被剥离、不退回默认渲染),与内置工具同等透传

#### Scenario: agent 工具的 detail 含完整派发 prompt
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `agent` 工具被调用派发子 agent
- **THEN** 其 `tool_end` 事件的 `detail` 含完整(不截断)的派发 `prompt`,以及子 agent 的执行结果
  (前台完成时为结果文本、后台/续传时为产物文件位置)与状态

#### Scenario: memory / skill_manage / task_stop 产结构化 detail
- **WHEN** `memory` / `skill_manage` / `task_stop` 任一被调用
- **THEN** 其 `tool_end` 事件的 `detail` 为该工具的结构化结果(写入的记忆 / 操作的 skill /
  停止的任务),而非默认的截断参数串

#### Scenario: 内置工具 summary 为人话而非裸状态码
- **GIVEN** 消费者订阅会话事件流
- **WHEN** `bash` 工具被调用且其参数含 `description`
- **THEN** 该工具的 `tool_start` 与 `tool_end` 事件的 `summary` 均为 `description` 文案
  (`description` 为空时降级为命令首段),而非仅 `exit=… elapsed=…ms` 这类裸状态串或开始态显示原始命令

### Requirement: feature 内核只留通用项,产品专属条件 prompt 全 per-session 经 PromptSlots

内核 feature 目录只含配内核内置工具的通用项:`memory_curation`(`memory` 工具)、`skill_creation`
(`skill_manage` 工具),其开关在 `create_session(features=…)`,gate 内核统一模板对应段(flag 开 +
requires_tool 在场)。内核不含任何产品专属 feature。产品专属条件 prompt(cron 指引 / heartbeat 指引 /
群聊上下文)**全是 per-session**(由 agent 配置在 create_session 时定、整会话不变),经
`create_session(prompt=PromptSlots)` 注入;产品**不向系统提示做 per-turn 注入**。

#### Scenario: 通用 feature 由会话开关 + 工具在场门控
- **GIVEN** 会话 `features={"memory_curation": true}` 且 `memory` 工具在 `enabled_tools` 中
- **WHEN** 装配该会话 system prompt
- **THEN** memory guidance 段出现;flag 未开或工具不在场则不渲染

#### Scenario: 能力查询返回内核 feature、产品对外 feature 由应用投影
- **GIVEN** Gateway 拿 `kernel.list_features()`(内核通用项)组装 IM payload
- **WHEN** 产品需对外呈现自己的"feature"概念(含 heartbeat/cron 等纯产品开关)
- **THEN** 该呈现是应用层投影,可叠加无内核 feature 对应的纯产品开关,不要求与内核目录一一对应

### Requirement: 系统提示由内核模板 + PromptSlots(四槽) 组装,产品内容纯 per-session

内核拥有模板骨架(顺序固定:head → core 行为规则 → body → 通用 feature 指引 → 后台任务/runtime footer →
custom → **内核自有工作区 AGENTS.md 段** → 内核易变尾部(memory/时间) → tail)。`create_session(prompt=PromptSlots(head/body/custom/tail))`
填产品文案槽。系统提示的**产品内容全是 per-session**:建会话时由模板 + PromptSlots 组装一次、整会话
稳定;内核易变尾部由内核自管,产品不碰。**工作区 AGENTS.md 段也由内核自管**(源自 `workspace_root/AGENTS.md`,
首轮冻结、压缩边界刷新,见「会话上下文自带工作区 AGENTS.md」Requirement)。产品无任何向系统提示做
per-turn 注入的通道(hook 不注入系统提示)。`PromptSection` / `PromptContext` / `RenderMode` 不在公共表面。

#### Scenario: 系统提示产品内容在会话内稳定
- **GIVEN** 一个已创建会话
- **WHEN** 同一会话多回合运行
- **THEN** 系统提示的产品内容(PromptSlots 四槽)逐回合不变(仅内核自管的易变尾部随 memory/时间变、
  以及内核自管的工作区 AGENTS.md 段随上下文压缩边界刷新);产品无机制在回合间改写系统提示

#### Scenario: prompt preview 与真实装配同源
- **GIVEN** `kernel.assemble_prompt_preview(*, prompt=PromptSlots, features, enabled_tools,
  workspace_root, scenario)`,消费者用与真实会话同一工厂构造的 `PromptSlots`
- **WHEN** 以某 agent 配置请求预览
- **THEN** 预览输出与该配置真实会话装配的 system prompt 一致(**易变尾部 + 工作区 AGENTS.md 段**以
  `<runtime-injected:…>` 占位,不读盘);内核侧 product-neutral(产品段全在传入的 PromptSlots)

### Requirement: Kernel 提供单项中立能力查询

`kernel.list_models()` / `list_tools()` / `list_features()` / `list_skills(workspace_root)` 返回
SDK-owned 不可变数据,与已装配 Kernel 实际能力一致;内核不做产品语义聚合(payload 拼装 / available
计算归应用)。`list_skills(workspace_root)` 的搜索根 = 每会话
`<workspace_root>/<workspace_config_dirname>/skills` **叠加** `build_kernel(skill_search_roots=…)` 传入
的部署级共享 skill 根,按「workspace 优先 → 部署根按传入顺序」去重保序;缺省为空 → 仅 workspace skill。

#### Scenario: 能力查询与运行时事实一致
- **GIVEN** 已装配的 Kernel
- **WHEN** 调四个 list_* 查询
- **THEN** models 含目录模型 + 默认、tools 含工具目录事实、features 为内核通用项投影、
  skills 为指定 workspace 解析结果

#### Scenario: 部署级共享 skill 根叠加在每 workspace 根之上
- **GIVEN** `build_kernel(skill_search_roots=(R1, R2))` 装配的 Kernel,某 workspace 自有 skill
- **WHEN** `list_skills(workspace_root)`
- **THEN** 返回 workspace skill + R1/R2 中的 skill,顺序为「workspace → R1 → R2」去重;
  跨 workspace 调用时部署级根一致、workspace 部分各异

### Requirement: 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致

`assemble_prompt_preview` 预览展示的技能、`list_skills(workspace_root)` 查询返回的技能、以及一次真实
session turn 注入 system prompt `<available_skills>` 的技能,对同一 `(workspace_root, skills)` 配置解析
出**同一集合**——搜索根均为 `<workspace_root>/<workspace_config_dirname>/skills` 叠加
`build_kernel(skill_search_roots=…)`,不存在「预览看得到、运行时看不到」的分歧。

#### Scenario: 预览与运行时技能一致
- **GIVEN** `build_kernel(skill_search_roots=…, workspace_config_dirname=…)` 装配的 Kernel,某 session
  的 `skills` 含若干在 workspace 配置目录或 `skill_search_roots` 下暴露的技能名
- **WHEN** 取 `assemble_prompt_preview(skill_ids=…, workspace_root=…)` 展示的技能,与该 session 真实
  执行一轮后 LLM 请求中 `<available_skills>` 列出的技能
- **THEN** 两者为同一集合(同名 + 同路径),不会出现预览齐全而运行时缩水成单个共享根技能的情形

#### Scenario: 子 agent 的 load_skills 校验与 list_skills 同口径
- **GIVEN** 某 session 的 agent 经 `agent` 工具创建子 agent 并传入 `load_skills`
- **WHEN** 工具校验 `load_skills`
- **THEN** 在该 workspace 配置目录或 `skill_search_roots` 下暴露的技能名通过校验,不存在的技能名报错;
  通过的集合与 `list_skills(workspace_root)` 对同一名集合的结果一致

#### Scenario: 未提供 workspace_config_dirname 时技能集合为空
- **GIVEN** 经 `build_kernel()` 未传入 `workspace_config_dirname`
- **WHEN** 取 preview / `list_skills` / 运行时注入的技能
- **THEN** 三者均为空,不隐式回退到 `~/.codex/skills` 等 legacy 默认路径

### Requirement: Kernel 出入参为 SDK-owned 类型

`create_session` / `fork_session` 返回 `SessionInfo`;`submit` / `get_run` / `cancel` 返回 `RunInfo`。
`SessionInfo` / `RunInfo` / `LLMConfig` 为真 SDK-owned 纯边界 DTO(内核边界处映射,core 不回引);内核
内部 `Session` / `RunRecord` / `LLMFactoryConfig` 不出边界。`RunOrigin` / `TERMINAL_RUN_STATUSES` /
`PermissionDecision` / `ToolPresenter` / `ToolPresentationEvent` 因 core/platform 引用,保持其拥有、
sdk re-export(闸 2 豁免)。

#### Scenario: 会话与运行结果不暴露内核内部对象
- **WHEN** 消费者调上述方法
- **THEN** 返回 SDK-owned 冻结类型,`session_id` / `run_id` / `status` 等既有属性名与语义不变;
  内核内部对象不出边界

### Requirement: 会话档案为无状态 per-workspace JSONL

会话档案是每会话一个 append-only JSONL,落
`{workspace_root}/{workspace_config_dirname}/sessions/{session_id}.jsonl`。存储组件无状态(不持
session→位置映射,按调用方传的 `workspace_root` 当场定位);位置由 `create_session(workspace_root)`
决定,无中心 session db 路径配置。

#### Scenario: 不同 agent 会话落各自 workspace
- **GIVEN** 两个会话以不同 `workspace_root` 创建
- **WHEN** 各自产生 turn
- **THEN** 档案分别落各自 `workspace_root` 下,互不混写

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

### Requirement: 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠

后台 bash / subagent 任务自然终态（成功或失败）后，发起它的 session 在下一轮输入中收到一条
`<task-notification>` 消息，内含任务结果——消费者无需轮询即可感知。该通知在任意 workspace_root 下均
可靠送达，不因 session 绑定非默认工作区而丢失。（经 `task_stop` 主动终止后的通知去重 / 携带部分结果行为，
见下方「经 task_stop 停止后台任务」要求。）反之，同步前台工具（前台 bash 或前台 subagent 在预算内
完成 / 失败 / 超时 / 被中断）的结果只经该工具的 tool result 同步返回，绝不再额外发 `<task-notification>`——
一次执行只走一条结果通路。仅当前台调用超出前台预算、真正转为后台任务（auto-background）后，其后续完成才
发一次 `<task-notification>`（此后它就是后台任务）。

#### Scenario: 非默认 workspace 下后台任务完成通知送达
- **GIVEN** 一个绑定非默认 workspace_root 的 session 启动了后台任务
- **WHEN** 任务完成
- **THEN** 该 session 下一轮输入含一条带任务结果的 `<task-notification>` 消息

#### Scenario: 前台命令完成只走 tool result，不发通知
- **GIVEN** 某 session 执行一条前台 bash 命令（未声明 `run_in_background`），且在前台预算内完成、失败或自身超时
- **WHEN** 消费者消费该 run 的结果
- **THEN** 该命令的结果只经其 tool result 同步返回（含成功输出 / 失败 / 超时归因）
- **AND** 该 session 后续输入中**不含**针对该命令的 `<task-notification>`（不出现"既返回结果又异步通知"的双通道）

#### Scenario: 前台命令超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 执行一条前台 bash 命令，运行时长超出前台预算被 auto-background（其 tool result 返回 `async_launched` + task_id）
- **WHEN** 该命令稍后在后台完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）

#### Scenario: 前台 subagent 在预算内完成只走 tool result，不发通知
- **GIVEN** 某 session 经 `agent` 工具派发一个前台子 agent（未声明 `run_in_background`），且在前台预算内完成
- **WHEN** 子 agent 跑完一轮返回
- **THEN** 父 session 经该 `agent` 工具的 tool result 同步拿到子 agent 的结果文本
- **AND** 该 session 后续输入中**不含**针对该子 agent 的 `<task-notification>`（不出现"既返回结果又异步通知"的双通道）

#### Scenario: 前台 subagent 超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 派发的前台子 agent 运行时长超出前台预算被 auto-background（其 tool result 返回 `async_launched` + agent_id）
- **WHEN** 该子 agent 稍后完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）

### Requirement: 经 task_stop 停止后台任务，model-facing 通知不与 tool_result 重复

消费者经 `task_stop` 停止一个后台任务后，发起 session **不应**收到一条与 `task_stop` tool result 内容
重复、且不带任何新增 payload 的 `<task-notification>`。按任务类型分两支：停后台 bash 抑制 model-facing
通知；停后台 subagent 保留通知但携带子 agent 被停前的部分产出。无论哪支，被停任务最终都进入 killed 终态，
且仍可经 `agent` 工具从 transcript 续跑。

#### Scenario: 停后台 bash 不再发重复通知
- **GIVEN** 消费者派了一个后台 bash 任务且它仍在运行
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 只收到 `task_stop` 的 tool result 一条停止信号
- **AND** 后续输入中不再注入与该 tool result 重复的 `<task-notification>`

#### Scenario: 停后台 subagent 通知携带部分结果
- **GIVEN** 消费者派了一个后台 subagent，它在被停前已产出至少一段 assistant 文字
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 收到一条 `<task-notification>`，其 `<status>` 为 `killed`
- **AND** 该通知带 `<result>`，内容为子 agent 被停前最后一段 assistant 文字

#### Scenario: 子 agent 无产出时通知省略 result
- **GIVEN** 消费者派了一个后台 subagent，它在产出任何 assistant 文字前就被停
- **WHEN** 消费者调 `task_stop` 停掉它
- **THEN** 发起 session 收到的 `killed` 通知省略 `<result>`（不出现空 `<result>`）

#### Scenario: 停止后任务进 killed 终态且可续跑
- **WHEN** 消费者对任意后台任务（bash / subagent，含前台超预算自动转后台的 subagent）调 `task_stop`
- **THEN** 该任务最终进入 killed 终态
- **AND** 对该 subagent 再发 follow-up 时，它从 transcript 续跑（与停止前的 resume 行为一致）

### Requirement: 派生子 agent 的前台执行与内核 run 隔离

经 `agent` 工具派发的前台子 agent，复用内核同一事件循环执行，不在独立的瞬时事件循环上运行共享内核
组件；因此前台子 agent 能正常完成并返回结果。任意工具调用（含子 agent）的失败被收敛在该工具的 tool
result 边界内，不破坏内核的 run、不影响同一内核上的其它 run，也不中断该消费者进程的其它常驻活动。

#### Scenario: 前台子 agent 正常返回结果
- **WHEN** 消费者经 `agent` 工具派发一个前台子 agent（传齐 description + subagent_type / category）
- **THEN** 该工具调用返回子 agent 的执行结果（status=completed 含结果文本），而非因跨事件循环绑定而失败

#### Scenario: 单次工具 / 子 agent 失败被隔离，不拖垮内核与常驻进程
- **GIVEN** 某消费者进程常驻运行内核（持续有心跳 / 中继等常驻活动）
- **WHEN** 一次 `agent` 工具派发的子 agent 调用失败
- **THEN** 该失败仅作为该工具调用的失败结果（status=failed + error）返回
- **AND** 内核的其它 run 与该消费者进程的常驻活动不受影响、继续正常运行（进程不失联、不需重启）

### Requirement: 会话上下文自带工作区 AGENTS.md（机制 A，默认恒开）

创建会话时，若 `workspace_root` 根目录存在 `AGENTS.md`，内核自动将其内容（含 `@import` 展开）纳入该会话的系统提示，无需消费者额外传入、无需 agent 主动读取。无该文件则不注入，会话照常工作。此行为不可经任何 per-session / per-agent 开关关闭。注入内容在一个上下文压缩窗口内**冻结**（与 MEMORY/USER 快照同生命周期，保前缀缓存稳定）；发生上下文压缩或开启新会话时**刷新**为磁盘最新内容。

#### Scenario: workspace 根有 AGENTS.md
- **WHEN** 消费者以一个根目录含 `AGENTS.md` 的 `workspace_root` 创建会话并提交一轮运行
- **THEN** 该 agent 的系统提示包含该 `AGENTS.md` 内容，agent 可据其中约定行动

#### Scenario: workspace 根无 AGENTS.md
- **WHEN** 消费者以一个根目录无 `AGENTS.md` 的 `workspace_root` 创建会话
- **THEN** 不注入项目指令，会话正常运行、无错误

#### Scenario: AGENTS.md 含 @import
- **GIVEN** 工作区根 `AGENTS.md` 内有 `@./sub.md` 形式的 import
- **WHEN** 会话启动注入
- **THEN** 被 import 文件的内容一并纳入（递归最深 5 层、环引用不重复、不存在的 import 静默忽略）

#### Scenario: 压缩窗口内冻结、压缩边界刷新
- **GIVEN** 会话已注入工作区根 `AGENTS.md`（快照 X），其后磁盘上被改为 Y
- **WHEN** 在同一压缩窗口内继续提交运行
- **THEN** 系统提示仍含 X（不随磁盘变动而变，保前缀缓存）
- **AND** 发生上下文压缩（或新会话）后的下一轮，系统提示刷新为 Y

### Requirement: read 工具触发就近项目指令加载（机制 B，可选，默认开）

当 `nested_memory` 内核特性开启（默认 `default_on=True`，不投影为产品/用户 toggle）时，agent 经 `read` 工具读取文件，内核在该 read 的工具结果中追加项目指令上下文：被读文件在 `workspace_root` 内 → 追加其目录链（至 workspace 根）上各级 `AGENTS.md` 的正文（`@import` 展开、`<project-instructions>` 标签包裹）；在 `workspace_root` 外 → 追加英文路径提示（`<project-instructions-hint>`），范围为该文件目录至最外层 git 仓根逐级、不含正文。同一份 AGENTS.md（按绝对路径）在一个上下文压缩窗口内只追加一次（含机制 A 已注入的工作区根那份）；发生上下文压缩后去重记录清空，使压缩后的 read 可重新追加（取磁盘最新内容）——与机制 A 的压缩边界刷新一致。

#### Scenario: 读工作区内子目录文件，链上有 AGENTS.md
- **GIVEN** `nested_memory` 开启，workspace 内某子目录有 `AGENTS.md`
- **WHEN** agent read 该子目录（或更深）下的文件
- **THEN** 该 read 的工具结果含该 `AGENTS.md` 正文（`<project-instructions>` 包裹）

#### Scenario: 读工作区外 git 仓内文件
- **GIVEN** `nested_memory` 开启，被读文件在 workspace 外、属于某 git 仓，文件目录至最外层仓根之间有 `AGENTS.md`
- **WHEN** agent read 该文件
- **THEN** 工具结果含英文路径提示（列出各级 AGENTS.md 路径，不含正文）

#### Scenario: 读不属于任何 git 仓的工作区外文件
- **WHEN** agent read 的文件在 workspace 外且不属于任何 git 仓
- **THEN** 工具结果不含任何项目指令提示

#### Scenario: 同一 AGENTS.md 多次命中只追加一次（压缩窗口内）
- **WHEN** 同一压缩窗口内多次 read 命中同一份 `AGENTS.md`（含机制 A 已注入的工作区根那份）
- **THEN** 仅首次追加，后续不重复

#### Scenario: 压缩后 read 重新追加（去重记录随压缩清空）
- **GIVEN** 某 `AGENTS.md` 已在本压缩窗口内因一次 read 被追加过
- **WHEN** 发生上下文压缩后，再次 read 命中该文件
- **THEN** 重新追加该文件当前磁盘内容（压缩已把旧追加内容摘要掉，去重记录已随压缩清空）

#### Scenario: 关闭 nested_memory 后 read 不再追加
- **GIVEN** `nested_memory` 特性关闭
- **WHEN** agent read 工作区内/外文件
- **THEN** 工具结果不含项目指令内容/提示
- **AND** 机制 A 的工作区根 AGENTS.md 仍照常注入系统提示（不随之关闭）

### Requirement: 消息携带图片块时图片送达模型并随会话历史保留

消费者经 `agent.sdk` 提交（`submit`）或追加（`append_message`）一条携带图片部件（image part）的消息时，图片须送达底层模型，且随会话历史持久化——同一会话后续轮次重建历史时，该图片仍作为图片内容呈现给模型，而非被降级为纯文本占位符。两条入口（`submit` / `append_message`）在「能携带并保留图片」这一点上行为一致。

#### Scenario: 提交含图片的消息，当轮模型即可见
- **WHEN** 消费者 `submit` 一条 parts 含 image part 的用户消息
- **THEN** 该图片送达模型并被模型理解（模型据其内容作答），而非被降级为 `[image:placeholder]` 纯文本占位

#### Scenario: 单条消息含多张图片时全部送达
- **WHEN** 消费者 `submit` 一条 parts 含多个 image part 的用户消息
- **THEN** 所有图片都送达模型（不因多部件内部展开而丢失其中任一张）

#### Scenario: 含图片的消息跨轮重建后图片仍在
- **GIVEN** 某会话已持久化过一条含图片的用户消息
- **WHEN** 消费者在同一会话发起新的一轮、内核重建该会话历史
- **THEN** 重建出的历史里那条消息仍带有图片内容，发往模型的请求中图片可见

#### Scenario: append_message 追加的图片同样被保留
- **WHEN** 消费者用 `append_message` 追加一条 parts 含 image part 的消息
- **THEN** 该图片随会话历史持久化，后续轮重建历史时仍可见（与 `submit` 行为一致）

#### Scenario: 纯文本消息的持久化与回放不受影响
- **WHEN** 消费者提交一条不含图片的纯文本消息并在后续轮重建历史
- **THEN** 其持久化与回放结果与本变更前一致，无可观察差异

#### Scenario: 含图消息触发模型错误后，后续轮不再因该图重复失败
- **GIVEN** 某含图片的消息触发了一次模型调用错误
- **WHEN** 消费者在同一会话提交后续消息、内核重建历史
- **THEN** 历史中那张图不再发往模型，后续消息不会因它重复触发同一错误（该消息的文本保留；纯文本消息的既有错误处理不受影响）

> 失败契约（图片无法获取 / 超大 / 损坏）属 gateway 入站职责（见 gateway 契约「用户经 IM 发送的图片被 Agent 看到」下的异常图片 Scenario），不在内核重复——图片校验在 gateway 入站完成，到达内核的 image part 已是校验过的 data URL，内核不产出图片失败信号。

### Requirement: 工具执行事件携带用户授权决策标识

内核经 `agent.sdk` 向消费者发出的工具执行事件，在原有「非成功终态分类」（denied / 超时 / 中断）之外，
新增一个**授权决策标识**：当某次工具调用是经用户在权限确认中显式决策放行或拒绝时，事件携带该决策；
自动放行的调用不携带。该标识独立于既有的终态原因维度。

#### Scenario: 用户显式允许的工具调用
- **GIVEN** 一次工具调用进入权限确认（用户需显式决策）
- **WHEN** 用户显式允许后该工具执行
- **THEN** 消费者从该工具调用的执行事件可观察到「经用户授权允许」的标识

#### Scenario: 用户显式拒绝的工具调用
- **GIVEN** 一次工具调用进入权限确认
- **WHEN** 用户显式拒绝该工具调用
- **THEN** 消费者可观察到「经用户拒绝」的标识

#### Scenario: 自动放行的工具调用
- **WHEN** 一次工具调用未触发用户确认、被自动放行
- **THEN** 该工具调用的执行事件不携带授权决策标识

### Requirement: 缓存使用量随 token 用量一并对外

#### Scenario: 一轮含多次模型调用
- **WHEN** 一次助手回复完成
- **THEN** 对外的 token 用量里，命中缓存的输入量、与可用于计算命中率的总输入量，都是这一轮所有模型调用的累计值
- **AND** 跨 provider 口径已归一，命中率 = 命中输入量 ÷ 总输入量，取值落在 0%–100%

#### Scenario: provider 不返回缓存信息
- **WHEN** 上游 provider 的用量里没有缓存字段
- **THEN** 对外的缓存输入量为 0（消费者据此得到 0% 命中率），不报错

### Requirement: 每次模型调用的思考内容随其回合对外

#### Scenario: 一轮含多次模型调用、各自有思考
- **WHEN** 一轮助手回复完成、其中多次模型调用各自产生了思考
- **THEN** 对外可观察到这一轮的多段思考，各段保留其相对于工具调用的先后次序

#### Scenario: 某次模型调用无思考
- **WHEN** 某次模型调用没有产生思考内容
- **THEN** 对外不为该次调用产出思考段
### Requirement: 工具被拒回传给模型的结果按拒绝来源给出语义化文本

当一次工具使用被拒，内核投递回模型的 tool-role 结果内容不再是单一通用字面量，而是按「谁拒的、循环里有无用户可等」给出区分性的语义文本：主会话由用户拒绝 → 指示模型停下并等待用户进一步指示；用户拒绝并附理由 → 在停下指示后附上该理由；策略/分类器自动拒绝 → 指示模型可换工具/换做法或如实上报、但不得恶意绕过；subagent（无人值守的派生运行）内被拒 → 指示其换方法或向上报告限制，而非停下等用户。该文本对 `agent.sdk` 消费者经会话事件流 / 持久化 transcript 的 tool-role 消息内容可见。

#### Scenario: 主会话用户拒绝、未附理由
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel，某轮触发工具许可请求
- **WHEN** 该请求以用户拒绝（无理由）解决
- **THEN** 投递回模型的该工具结果内容表达「用户不愿继续此工具使用、应停下并等待用户指示」，而非通用的 `tool blocked by hook`

#### Scenario: 主会话用户拒绝并附理由
- **WHEN** 该许可请求以用户拒绝且携带一段理由文本解决
- **THEN** 投递回模型的该工具结果内容在「停下等待」指示之后包含该用户理由原文

#### Scenario: 策略/分类器自动拒绝
- **GIVEN** 一次工具使用被内核权限裁决自动拒绝（无逐次用户决定）
- **WHEN** 该次工具使用被拒
- **THEN** 投递回模型的结果内容表达「权限被拒，可用其他正当方式达成或向用户说明，但不得以恶意方式绕过」

#### Scenario: subagent 派生运行内工具被拒
- **GIVEN** 一个受工具执行白名单约束的派生运行（subagent）发起被拒的工具使用（白名单外工具或运行内裁决拒绝）
- **WHEN** 该工具使用被拒
- **THEN** 投递回模型的结果内容指示「换一种方法或向上层报告此限制以完成任务」，而非「停下等待用户」
