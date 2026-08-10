# kernel (agent) - SDK Boundary Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 装配与会话分两层,内核产品中立

`agent.sdk` 不提供"产品"对象(无 `ProductProfile` / `ProductDefinition` / 内置产品常量)。装配分两层, 内核对三类应用(coding_cli / personal_assistant / 任意外部应用)无差别对待,无任何"一方产品"分支:

- `build_kernel(llm, tools, hooks, can_use_tool=None, tool_approval_model=None,
  workflow_subagent_model=None, workspace_config_dirname=…, global_config_root=None,
  repo_root=None, skill_search_roots=(), tool_search_roots=(), hook_search_roots=(),
  workflow_search_roots=())` —— 建一次进程级**共享基座**:
  `llm` 为 SDK-owned `LLMConfig`(providers/models 目录 + 连接 + 默认);`tools` 为原生工具对象**目录**;
  `hooks` 为 `setup(hooks: HookAPI)` 形态 callable;`tool_approval_model` 是可选的 build-scoped
  自动工具权限分类模型,非空时必须属于 `llm` catalog,空时分类复用当前 run 模型;
  `workflow_subagent_model` 是可选的 build-scoped Workflow child 最终模型覆盖;
  `skill_search_roots` / `tool_search_roots` / `hook_search_roots` 为部署级用户插件目录
  (消费者显式传入的根,非 ConfigResolver),内核在每个 session 选定的
  `<workspace_root>/<workspace_config_dirname>/{tools,hooks,skills}` 运行时发现之外额外发现这些目录,
  空 → 仅工作区。`workflow_search_roots` 是消费者显式传入的命名 Workflow 根,
  叠加到工作区与 personal Workflow discovery。`global_config_root` 是可选的、消费者拥有的
  global auto-mode configuration root；省略时不加载 global auto-mode config，仍从 session 选定的
  workspace config root 加载。模型注册表初始化在内部,消费者无前置时序义务;
  `workspace_config_dirname` 必须是单层 dot-prefixed directory name（两端空白会归一化；
  `.`、`..` 与 path separator 拒绝），并在创建任何 session 文件前验证。装配完成后
  所有会话/运行均在进程内执行(无子进程、无 loopback HTTP)。
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
- **THEN** 它暴露异步会话生命周期方法 `create_session` / `fork_session` / `compact` / `discard_run_messages`,非阻塞方法 `submit` / `try_steer` / `stream` / `interrupt` / `cancel` / `get_run` / `list_session_tools` / `get_llm_config`,中立能力查询 `list_models` / `list_tools` / `list_features` / `list_skills`,Workflow 查询与控制 `list_workflow_runs` / `get_workflow_run` / `control_workflow` / `save_workflow` / `list_named_workflows`,以及 prompt 预览 `assemble_prompt_preview`;并同时暴露供异步消费者使用的 `aclose()`与同步兼容的 `close()`

#### Scenario: 消费者选择已注册的自动分类模型
- **GIVEN** `LLMConfig` catalog 含模型 C
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=C)`
- **THEN** Kernel 正常装配并对该消费者保持产品中立

#### Scenario: 消费者省略自动分类模型
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=None)` 或省略该参数
- **THEN** Kernel 正常装配,不建立独立的自动分类模型选择

#### Scenario: 消费者选择未注册的自动分类模型
- **GIVEN** 模型 X 不在 `LLMConfig` catalog 中
- **WHEN** 任一消费者调用 `build_kernel(tool_approval_model=X)`
- **THEN** Kernel 在启动 runtime 或后台任务前以明确配置错误拒绝装配

#### Scenario: 消费者提供 global auto-mode config root
- **GIVEN** 应用拥有部署级 auto-mode 配置目录 G，session workspace 有自身选定配置目录 W
- **WHEN** 应用调用 `build_kernel(global_config_root=G)` 并在该 session 触发 auto-mode 工具决策
- **THEN** 决策按 G 与 W 的既有合并规则读取配置，且不会把任一产品目录名硬编码到 SDK

#### Scenario: 消费者省略 global auto-mode config root
- **WHEN** 任一消费者省略 `global_config_root`
- **THEN** Kernel 正常装配，auto-mode 决策不读取任意部署级 global 配置，仍只读取该 session 的选定 workspace config directory

#### Scenario: 消费者配置 Workflow child 模型覆盖
- **GIVEN** 消费者为 `build_kernel(workflow_subagent_model=X)` 提供了模型 X
- **WHEN** Workflow 派发子 Agent
- **THEN** X 的优先级高于脚本 call model 与父轮模型
- **AND** X 不在当前 catalog 时子 Agent 改用父轮已解析模型，运行只产生一次包含 requested/resolved 的可见替换告警

## ADDED Requirements

### Requirement: 应用只经 agent.sdk 查询、控制和保存 Workflow

#### Scenario: 查询 Workflow 运行
- **WHEN** 应用经 `agent.sdk` 列出或读取指定 session 的 Workflow runs
- **THEN** 返回 SDK-owned immutable snapshots，不暴露 platform manager、store 或 child session 对象

#### Scenario: 控制 Workflow 运行
- **WHEN** 应用经 SDK 对 run 发起 pause、resume、stop 或 restart-agent
- **THEN** 返回更新后的 SDK-owned snapshot 或稳定错误
- **AND** 应用不需要 import `agent.core` 或 `agent.platform`

#### Scenario: 保存和发现命名 Workflow
- **WHEN** 应用经 SDK 保存某 run script 或列出 workspace 适用的命名 Workflow
- **THEN** 返回 SDK-owned saved-workflow records
- **AND** project/personal/plugin 路径解析留在内核实现边界内
