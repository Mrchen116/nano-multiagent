# kernel (agent) - SDK Boundary Specification (delta for refactor-477)

## MODIFIED Requirements

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
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact` /
  `discard_run_messages`,异步 USER/事件生命周期方法 `admit_user_input` /
  `wait_run_settlement` / `open_event_subscription`,非阻塞方法 `submit` / `try_steer` / `stream` /
  `interrupt` / `interrupt_user` / `cancel` / `get_run` / `current_event_sequence` / `list_session_tools` /
  `get_llm_config`,中立能力查询 `list_models` / `list_tools` / `list_features` /
  `list_skills`,以及 prompt 预览 `assemble_prompt_preview`;并同时暴露供异步消费者使用的 `aclose()`
  与同步兼容的 `close()`

### Requirement: Kernel 出入参为 SDK-owned 类型

`create_session` / `fork_session` 返回 `SessionInfo`;`submit` / `get_run` / `cancel` 返回 `RunInfo`;
`admit_user_input` 返回 `UserInputAdmission`;`wait_run_settlement` 返回 `RunSettlement`;
`open_event_subscription` 返回 `SessionEventSubscription`。`SessionInfo` / `RunInfo` / `LLMConfig` /
`UserInputAdmission` / `RunSettlement` / `RunContinuationInfo` / `SessionEventSubscription` /
`EventReplayGapError` / `RunSettlementNotFoundError` / `UserAdmissionConflictError` 为真 SDK-owned
纯边界类型或 typed error(内核边界处映射,core 不回引);内核内部 `Session` / `RunRecord` /
`LLMFactoryConfig`、Registry admission/settlement 对象与 replay journal 内部错误不出边界。
`RunOrigin` / `TERMINAL_RUN_STATUSES` / `PermissionDecision` / `ToolPresenter` /
`ToolPresentationEvent` 因 core/platform 引用,保持其拥有、sdk re-export(闸 2 豁免)。

#### Scenario: 会话、运行、USER lifecycle 与 replay gap 不暴露内核内部对象
- **WHEN** 消费者调用上述方法,或 strict subscription open 检测到不可重放缺口
- **THEN** 返回值、subscription 或错误为 SDK-owned 类型,`session_id` / `run_id` / `status` /
  `action` / `continuations` / `origin` / `published_through_sequence_num` /
  `requested_after_sequence` 等约定属性名与语义稳定
- **AND** 内核内部对象与内部 replay error 不出 `agent.sdk` 边界
