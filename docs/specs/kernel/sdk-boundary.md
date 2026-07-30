# kernel (agent) - SDK Boundary Specification

> 对齐: refactor-463
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

`agent.sdk` 的公开边界、装配模型、扩展协议、能力查询和 SDK-owned 类型契约。

## Requirements

### Requirement: 内核对外只经 agent.sdk 暴露,产品不得依赖内核内部

`agent.sdk` 是内核唯一对外面。消费者只能 import `agent.sdk`;内核内部层(`agent.core` / `agent.platform`)不得被产品直接 import,`agent.sdk` 也不得反向依赖任何产品包。`agent.sdk` 的公开符号是一份**精确允许名单**(逐字钉死,见归档 design 接口总表),由表面守卫 contract 测试守卫:多导出或少导出都失败。除显式豁免外,每个导出对象的类型须由 `agent.sdk` 自身拥有(SDK-owned),不得是内核内部模块拥有的对象直接外泄。

#### Scenario: 产品越界 import 内核内部被拦
- **GIVEN** `coding_cli` 或 `personal_assistant` 的某文件
- **WHEN** 它写下 `import agent.core...` / `import agent.platform...` / `import agent.products...`
- **THEN** 契约测试(`tests/contract/test_agent_sdk_boundary_contract.py`)失败,挡住越界 (`agent.products` 包已退役,但其前缀仍在禁止名单内,防止以旧概念重建)

#### Scenario: agent.sdk 不上行依赖产品
- **WHEN** 审阅 `agent.sdk` 下任一模块的 import
- **THEN** 其中没有对 `coding_cli` / `personal_assistant` / `IM` 的 import(否则形成循环依赖)

#### Scenario: core 不依赖 platform / products
- **WHEN** 审阅 `agent.core` 下任一模块的 import
- **THEN** 其中没有对 `agent.platform` 及 web 框架(fastapi / starlette)的 import——provider 与存储细节不反向污染纯逻辑运行时

#### Scenario: 新增导出未进允许名单
- **WHEN** `agent.sdk.__all__` 含允许名单之外的名字(或缺名单内的名字)
- **THEN** 表面守卫 contract 测试失败

#### Scenario: 导出对象由内核内部模块拥有
- **WHEN** `agent.sdk` 的某导出(不在显式豁免名单内),其类型定义在 `agent.core` / `agent.platform`内部模块
- **THEN** 所有权守卫 contract 测试失败

#### Scenario: 豁免名单容纳内核必拥有的边界类型
- **WHEN** 导出属于显式豁免名单(`RunOrigin` / `PermissionDecision` / `TERMINAL_RUN_STATUSES` / `ToolPresenter` / `ToolPresentationEvent`——core/platform 引用、物理上无法 sdk-owned,由 sdk re-export)
- **THEN** 所有权守卫放行;但豁免名单本身逐字钉死,增删名单成员同样使测试失败

#### Scenario: sdk-owned typing 别名不计入豁免
- **WHEN** 导出为 `CanUseToolFn`(sdk-owned 的 `Callable` 类型别名,定义在 `agent/sdk/kernel.py`, 无 class `__module__`、非 core/platform re-export)
- **THEN** 闸 2 对 typing 别名特殊处理放行,且它**不在**豁免名单之列

### Requirement: 装配与会话分两层,内核产品中立

`agent.sdk` 不提供"产品"对象(无 `ProductProfile` / `ProductDefinition` / 内置产品常量)。装配分两层, 内核对三类应用(coding_cli / personal_assistant / 任意外部应用)无差别对待,无任何"一方产品"分支:

- `build_kernel(llm, tools, hooks, can_use_tool=None, workspace_config_dirname=…, repo_root=None,
  skill_search_roots=(), tool_search_roots=(), hook_search_roots=())` —— 建一次进程级**共享基座**:
  `llm` 为 SDK-owned `LLMConfig`(providers/models 目录 + 连接 + 默认);`tools` 为原生工具对象**目录**;
  `hooks` 为 `setup(hooks: HookAPI)` 形态 callable;`skill_search_roots` / `tool_search_roots` /
  `hook_search_roots` 为部署级用户插件目录(消费者显式传入的根,非 ConfigResolver),内核在工作区
  `<repo_root>/.nano/{tools,hooks,skills}` 运行时发现之外额外发现这些目录,空 → 仅工作区。模型注册表
  初始化在内部,消费者无前置时序义务;装配完成后所有会话/运行均在进程内执行(无子进程、无 loopback HTTP)。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)` —— 每 agent 带齐配置:`enabled_tools` 从工具目录选子集;`features` 开关内核通用 feature;`prompt` 为 SDK-owned `PromptSlots`。不收 `model`——model 是 per-run 的,消费者每轮经 `submit(model=...)` 提供。

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
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact` / `discard_run_messages`,非阻塞方法 `submit` / `try_steer` / `stream` / `interrupt` / `cancel` / `get_run` / `list_session_tools` / `get_llm_config`,中立能力查询 `list_models` / `list_tools` / `list_features` / `list_skills`,以及 prompt 预览 `assemble_prompt_preview`;并同时暴露供异步消费者使用的 `aclose()`与同步兼容的 `close()`

### Requirement: 应用以原生 Tool/Hook 对象扩展,契约为 SDK-owned Protocol

应用经 `build_kernel(tools=…, hooks=…)` 传入原生对象扩展内核,无须修改 `agent` 内部源码、无须进任何产品目录。`Tool` / `ToolContext` / `HookAPI` 是 SDK-owned 结构化 Protocol(鸭子结构,内核真造对象天然满足、无 core→sdk 倒挂)。副作用工具可在应用包内闭包持有应用子系统句柄,经 `build_kernel(tools=…)`传入后副作用直达应用子系统;内核不提供也不需要 `host_capabilities` 回调通道。

#### Scenario: 对象满足 Tool 契约即可装配
- **GIVEN** 一个对象具备 `name: str`、`description: str`、`input_schema: dict`、可调用 `run(args, ctx)` (无须继承内核基类)
- **WHEN** 它出现在 `build_kernel(tools=…)` 且某会话 `enabled_tools` 选了它
- **THEN** 被注册并可执行,`ctx`(结构化 Protocol)提供承诺字段子集(session_metadata、repo_root、工作区路径族);非承诺字段不进 Protocol、不承诺

#### Scenario: 副作用工具闭包直连自己的服务、无内核回桥
- **GIVEN** 一个在应用包内定义、闭包持有应用子系统句柄(如 Gateway 调度器)的工具,经 `build_kernel(tools=…)` 传入
- **WHEN** 会话中调用它
- **THEN** 副作用直达应用子系统;内核不提供 `host_capabilities` 通道(`HostCapabilityDispatcher`不在公共表面)

### Requirement: Kernel 提供单项中立能力查询

`kernel.list_models()` / `list_tools()` / `list_features()` / `list_skills(workspace_root)` 返回 SDK-owned 不可变数据,与已装配 Kernel 实际能力一致;内核不做产品语义聚合(payload 拼装 / available 计算归应用)。`list_skills(workspace_root)` 的搜索根 = 每会话 `<workspace_root>/<workspace_config_dirname>/skills` **叠加** `build_kernel(skill_search_roots=…)` 传入的部署级共享 skill 根,按「workspace 优先 → 部署根按传入顺序」去重保序;缺省为空 → 仅 workspace skill。

#### Scenario: 能力查询与运行时事实一致
- **GIVEN** 已装配的 Kernel
- **WHEN** 调四个 list_* 查询
- **THEN** models 含目录模型 + 默认、tools 含工具目录事实、features 为内核通用项投影、skills 为指定 workspace 解析结果

#### Scenario: 消费者可在工具目录中启用 skill_view
- **WHEN** 消费者通过 `Kernel.list_tools()` 或 `Kernel.list_session_tools(...)` 查看包含默认自进化工具的工具目录
- **THEN** 返回的工具目录中包含真实工具名 `skill_view`

#### Scenario: 部署级共享 skill 根叠加在每 workspace 根之上
- **GIVEN** `build_kernel(skill_search_roots=(R1, R2))` 装配的 Kernel,某 workspace 自有 skill
- **WHEN** `list_skills(workspace_root)`
- **THEN** 返回 workspace skill + R1/R2 中的 skill,顺序为「workspace → R1 → R2」去重; 跨 workspace 调用时部署级根一致、workspace 部分各异

### Requirement: Kernel 出入参为 SDK-owned 类型

`create_session` / `fork_session` 返回 `SessionInfo`;`submit` / `get_run` / `cancel` 返回 `RunInfo`。`SessionInfo` / `RunInfo` / `LLMConfig` 为真 SDK-owned 纯边界 DTO(内核边界处映射,core 不回引);内核内部 `Session` / `RunRecord` / `LLMFactoryConfig` 不出边界。`RunOrigin` / `TERMINAL_RUN_STATUSES` / `PermissionDecision` / `ToolPresenter` / `ToolPresentationEvent` 因 core/platform 引用,保持其拥有、sdk re-export(闸 2 豁免)。

#### Scenario: 会话与运行结果不暴露内核内部对象
- **WHEN** 消费者调上述方法
- **THEN** 返回 SDK-owned 冻结类型,`session_id` / `run_id` / `status` 等既有属性名与语义不变; 内核内部对象不出边界
