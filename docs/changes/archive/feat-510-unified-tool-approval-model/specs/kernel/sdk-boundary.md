# kernel (agent) SDK Boundary Specification (delta for feat-510)

## MODIFIED Requirements

### Requirement: 装配与会话分两层,内核产品中立

`agent.sdk` 不提供“产品”对象(无 `ProductProfile` / `ProductDefinition` / 内置产品常量)。
装配分两层，内核对三类应用(coding_cli / personal_assistant / 任意外部应用)无差别对待，
无任何“一方产品”分支：

- `build_kernel(llm, tools, hooks, can_use_tool=None, tool_approval_model=None,
  workspace_config_dirname=…, repo_root=None, skill_search_roots=(), tool_search_roots=(),
  hook_search_roots=())` —— 建一次进程级**共享基座**：`llm` 为 SDK-owned `LLMConfig`
  (providers/models 目录 + 连接 + 默认)；`tools` 为原生工具对象**目录**；`hooks` 为
  `setup(hooks: HookAPI)` 形态 callable；`tool_approval_model` 是可选的 build-scoped 自动
  工具权限分类模型，非空时必须属于 `llm` catalog，空时分类复用当前 run 模型；
  `skill_search_roots` / `tool_search_roots` / `hook_search_roots` 为部署级用户插件目录
  (消费者显式传入的根，非 ConfigResolver)，内核在工作区
  `<repo_root>/.nano/{tools,hooks,skills}` 运行时发现之外额外发现这些目录，空 → 仅工作区。
  模型注册表初始化在内部，消费者无前置时序义务；装配完成后所有会话/运行均在进程内执行
  (无子进程、无 loopback HTTP)。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)` ——
  每 agent 带齐配置：`enabled_tools` 从工具目录选子集；`features` 开关内核通用 feature；
  `prompt` 为 SDK-owned `PromptSlots`。不收 `model`——model 是 per-run 的，消费者每轮经
  `submit(model=...)` 提供。

#### Scenario: 应用零前置调用直接装配
- **GIVEN** 应用构造了 `LLMConfig`(含 `from_env()`)、工具目录、hooks
- **WHEN** 未调用任何注册表初始化函数，直接 `build_kernel(...)`
- **THEN** Kernel 正常装配，模型解析、默认 provider 推导可用；无子进程、无 loopback HTTP

#### Scenario: 三类应用对内核同构
- **GIVEN** coding_cli、personal_assistant、任意外部应用
- **WHEN** 各自 `build_kernel(基座)` + `create_session(per-agent)`
- **THEN** 内核对三者无差别对待，无“一方产品”分支；各自的品牌/默认在自己包的工厂里，内核不感知

#### Scenario: 工具目录共享、会话选子集
- **WHEN** `build_kernel(tools=[A,B,C])` 后 `create_session(enabled_tools=[A,B])`
- **THEN** 该会话只暴露 A、B；工具实现实例在基座注册一次、不因会话重建

#### Scenario: Kernel 暴露稳定的对外方法集
- **GIVEN** 一个已装配的 `Kernel`
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact` / `discard_run_messages`，非阻塞方法 `submit` / `try_steer` / `stream` / `interrupt` / `cancel` / `get_run` / `list_session_tools` / `get_llm_config`，中立能力查询 `list_models` / `list_tools` / `list_features` / `list_skills`，以及 prompt 预览 `assemble_prompt_preview`；并同时暴露供异步消费者使用的 `aclose()` 与同步兼容的 `close()`

#### Scenario: 消费者选择已注册的自动分类模型
- **GIVEN** `LLMConfig` catalog 含模型 C
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=C)`
- **THEN** Kernel 正常装配并对该消费者保持产品中立

#### Scenario: 消费者省略自动分类模型
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=None)` 或省略该参数
- **THEN** Kernel 正常装配，不建立独立的自动分类模型选择

#### Scenario: 消费者选择未注册的自动分类模型
- **GIVEN** 模型 X 不在 `LLMConfig` catalog 中
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=X)`
- **THEN** Kernel 在启动 runtime 或后台任务前以明确配置错误拒绝装配
