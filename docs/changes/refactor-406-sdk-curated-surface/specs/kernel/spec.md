# kernel delta-spec — refactor-406 收敛 agent.sdk 公共表面

> 对 `docs/specs/kernel/spec.md` 的增量声明。主语 = `agent.sdk` 的消费者（应用包）。
> 本 unit 不改变会话、运行、流式事件、权限、压缩、持久化等既有**行为**语义；变更集中在
> "应用如何装配内核、如何开会话、经什么类型与内核交互"——即取消"产品层"、收敛为
> **共享基座(build_kernel) + per-agent 会话(create_session)** 两层。

## MODIFIED Requirements

### Requirement: 内核对外只经 agent.sdk 暴露，产品不得依赖内核内部

（追加精确表面约束）`agent.sdk` 的公开符号是一份精确允许名单（见 design.md §接口与数据流总表），
由 contract 测试守卫。

#### Scenario: 新增导出未进允许名单
- **WHEN** `agent.sdk.__all__` 含允许名单之外的名字（或缺名单内的名字）
- **THEN** 表面守卫 contract 测试失败

#### Scenario: 导出对象由内核内部模块拥有
- **WHEN** `agent.sdk` 的某导出（不在显式豁免名单内），其类型定义在 `agent.core` / `agent.platform` /
  `agent.products` 内部模块
- **THEN** 所有权守卫 contract 测试失败

#### Scenario: 豁免名单容纳内核必拥有的边界类型
- **WHEN** 导出属于显式豁免名单（`RunOrigin` / `PermissionDecision` /
  `TERMINAL_RUN_STATUSES`——core/platform 引用、物理上无法 sdk-owned，由 sdk re-export）
- **THEN** 所有权守卫放行；但豁免名单本身逐字钉死，增删名单成员同样使测试失败

#### Scenario: sdk-owned typing 别名不计入豁免
- **WHEN** 导出为 `CanUseToolFn`（sdk-owned 的 `Callable` 类型别名，定义在 `agent/sdk/kernel.py`，
  无 class `__module__`、非 core/platform re-export）
- **THEN** 闸 2 对 typing 别名特殊处理放行，且它**不在** C1 豁免名单之列

### Requirement: 装配与会话分两层，内核产品中立

`agent.sdk` 不提供"产品"对象（无 `ProductDefinition` / 内置产品常量）。装配分两层：
- `build_kernel(llm, tools, hooks, can_use_tool=None, workspace_config_dirname=…, repo_root=None, skill_search_roots=(), tool_search_roots=(), hook_search_roots=())`
  —— 建一次进程级**共享基座**：`llm` 为 SDK-owned `LLMConfig`（providers/models 目录 + 连接 + 默认）；
  `tools` 为原生工具对象**目录**；`hooks` 为 `setup(hooks: HookAPI)` 形态 callable；`skill_search_roots`
  为部署级共享 skill 根（叠加在每 workspace 根之上，见「Kernel 提供单项中立能力查询」Requirement）。
  `tool_search_roots` / `hook_search_roots` 为部署级用户工具/hook 插件目录（与 `skill_search_roots`
  同模式：消费者显式传入的根，非 ConfigResolver）；内核在工作区 `<repo_root>/.nano/{tools,hooks}` 运行时
  发现之外，额外发现这些目录下的插件。空 → 仅工作区。模型注册表初始化在
  内部，消费者无前置时序义务。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)`
  —— 每 agent 带齐配置：`enabled_tools` 从目录选子集；`features` 开关内核通用 feature；`prompt` 为
  SDK-owned `PromptSlots`。（不收 `model`；model 维持 kernel 级，CLI `/model` 经 `reconfigure_llm`。）

#### Scenario: 应用零前置调用直接装配
- **GIVEN** 应用构造了 `LLMConfig`（含 `from_env()`）、工具目录、hooks
- **WHEN** 未调用任何注册表初始化函数，直接 `build_kernel(...)`
- **THEN** Kernel 正常装配，模型解析、默认 provider 推导可用

#### Scenario: 三类应用对内核同构
- **GIVEN** coding_cli、personal_assistant、任意外部应用
- **WHEN** 各自 `build_kernel(基座)` + `create_session(per-agent)`
- **THEN** 内核对三者无差别对待，无任何"一方产品"分支；各自的品牌/默认在自己包的工厂里，内核不感知

#### Scenario: 工具目录共享、会话选子集
- **WHEN** `build_kernel(tools=[A,B,C])` 后 `create_session(enabled_tools=[A,B])`
- **THEN** 该会话只暴露 A、B；工具实现实例在基座注册一次、不因会话重建

### Requirement: LLM 配置经单一 LLMConfig 装配，model 维持 kernel 级

`build_kernel(llm=LLMConfig)` 装 provider/model 目录与连接；模型注册表初始化在 `build_kernel` 内部，
消费者无前置时序义务。`get_llm_config()` / `reconfigure_llm()` 返回 SDK-owned `LLMConfig` DTO。model
维持 kernel 级（`create_session` 不收 model）；CLI `/model` 经 `reconfigure_llm` 即时切换。（per-agent
model 生效为行为新增，不在本 unit 范围。）

#### Scenario: 零前置直接装配
- **GIVEN** 消费者构造 `LLMConfig`（含 `from_env()`）
- **WHEN** 未调任何注册表初始化函数直接 `build_kernel`
- **THEN** 模型解析、默认 provider 推导可用

#### Scenario: get_llm_config / reconfigure_llm 返回 SDK-owned DTO
- **WHEN** 消费者调 `kernel.get_llm_config()` 或 `kernel.reconfigure_llm(...)`
- **THEN** 返回 SDK-owned `LLMConfig`，字段语义（provider/model/base_url/timeout/api_key）与切换即时
  生效行为不变

## ADDED Requirements

### Requirement: 应用以原生 Tool/Hook 对象扩展，契约为 SDK-owned Protocol

应用经 `build_kernel(tools=…, hooks=…)` 传入原生对象，无须修改 `agent` 内部源码、无须进
`agent/products/` 目录。`Tool` / `ToolContext` / `HookAPI` 是 SDK-owned 结构化 Protocol（鸭子结构，
内核真造对象天然满足、无 core→sdk 倒挂）。

#### Scenario: 对象满足 Tool 契约即可装配
- **GIVEN** 一个对象具备 `name: str`、`description: str`、`input_schema: dict`、可调用 `run(args, ctx)`
  （无须继承内核基类）
- **WHEN** 它出现在 `build_kernel(tools=…)` 且某会话 `enabled_tools` 选了它
- **THEN** 被注册并可执行，`ctx`（结构化 Protocol）提供承诺字段子集（session_metadata、repo_root、
  工作区路径族）；非承诺字段不进 Protocol、不承诺

#### Scenario: 副作用工具闭包直连自己的服务、无内核回桥
- **GIVEN** 一个在应用包内定义、闭包持有应用子系统句柄（如 Gateway 调度器）的工具，经
  `build_kernel(tools=…)` 传入
- **WHEN** 会话中调用它
- **THEN** 副作用直达应用子系统；内核不提供也不需要 `host_capabilities` 回调通道
  （`HostCapabilityDispatcher` 不在公共表面）

### Requirement: 工具展示由工具自带的 presenter 决定

工具在流式事件上的展示（`tool_start`/`tool_end` 携带的 presentation：`visible`/`label`/`summary`/
`detail`）由该工具自身的 `presenter`（SDK-owned `ToolPresenter`，缺省即无）决定；未带 presenter 的
工具走默认渲染。应用经 `build_kernel(tools=…)` 传入的工具，其 presenter 随对象一起生效，无须任何
额外注册步骤。`ToolPresenter` / `ToolPresentationEvent` 在公共表面，应用可为自带工具实现自定义展示。

#### Scenario: 自带 presenter 的工具产出自定义展示
- **GIVEN** 应用经 `build_kernel(tools=…)` 传入一个带 `presenter` 的工具，消费者订阅会话事件流
- **WHEN** 该工具被调用
- **THEN** 对应 `tool_start`/`tool_end` 事件的 presentation 字段为该工具 presenter 产出的
  `visible`/`label`/`summary`/`detail`

#### Scenario: 无 presenter 的工具走默认展示
- **GIVEN** 一个未带 presenter 的工具（如 MCP / 工作区运行时发现的工具）
- **WHEN** 它被调用
- **THEN** 其 `tool_start`/`tool_end` 事件携带默认 presentation（可见 + 名称 + 截断后的参数），
  不因缺 presenter 而丢失事件或报错

### Requirement: feature 内核只留通用项，产品专属条件 prompt 全 per-session 经 PromptSlots

内核 feature 目录只含配内核内置工具的通用项：`memory_curation`（`memory` 工具）、`skill_creation`
（`skill_manage` 工具）。其开关在 `create_session(features=…)`，gate 内核统一模板对应 core 段
（`flag 开 + requires_tool 在场`）。内核不含任何产品专属 feature。产品专属条件 prompt（cron 指引 /
heartbeat 指引 / 群聊上下文）**全是 per-session**（由 agent 配置在 create_session 时定、整会话不变），
经 `create_session(prompt=PromptSlots)` 注入（cron/heartbeat → body，群聊 → tail）；产品**不向系统提示
做 per-turn 注入**。

#### Scenario: 通用 feature 由会话开关 + 工具在场门控
- **GIVEN** 会话 `features={"memory_curation": true}` 且 `memory` 工具在 `enabled_tools` 中
- **WHEN** 装配该会话 system prompt
- **THEN** memory guidance 段出现；flag 未开或工具不在场则不渲染

#### Scenario: 产品条件 prompt 经 PromptSlots 在 create_session 注入
- **GIVEN** 应用工厂对开了 cron/heartbeat 的 agent 把对应指引拼进 `PromptSlots.body`、对群聊会话把群聊
  上下文拼进 `PromptSlots.tail`
- **WHEN** 该会话运行
- **THEN** 这些段按 PromptSlots 指定位置出现在系统提示中、整会话稳定；内核模板不含任何产品专属段；
  内核不提供产品向系统提示做 per-turn 注入的通道

#### Scenario: 能力查询返回内核 feature、产品对外 feature 由应用投影
- **GIVEN** Gateway 拿 `kernel.list_features()`（内核通用项）组装 IM payload
- **WHEN** 产品需对外呈现自己的"feature"概念（含 heartbeat/cron 等纯产品开关）
- **THEN** 该呈现是应用层投影，可叠加无内核 feature 对应的纯产品开关，不要求与内核目录一一对应

### Requirement: 系统提示由内核模板 + PromptSlots(四槽) 组装，产品内容纯 per-session

内核拥有模板骨架（顺序固定：head → core 行为规则 → body → 通用 feature 指引(memory/skill) →
后台任务/runtime footer → custom → 内核易变尾部(memory/时间) → tail）。
`create_session(prompt=PromptSlots(head/body/custom/tail))`
填产品文案槽。系统提示的**产品内容全是 per-session**：建会话时由模板 + PromptSlots 组装一次、整会话
稳定；内核易变尾部（memory 快照 / 当前时间）由内核自管，产品不碰。产品无任何向系统提示做 per-turn
注入的通道（hook 不注入系统提示）。`PromptSection`/`PromptContext`/`RenderMode` 不在公共表面。

#### Scenario: 系统提示产品内容在会话内稳定
- **GIVEN** 一个已创建会话
- **WHEN** 同一会话多回合运行
- **THEN** 系统提示的产品内容（PromptSlots 四槽）逐回合不变（仅内核自管的易变尾部随 memory/时间变）；
  产品无机制在回合间改写系统提示

#### Scenario: 相同会话条件下 prompt 逐字节等价
- **WHEN** 在相同 features/enabled_tools/PromptSlots 下装配 system prompt
- **THEN** 完整 system prompt 与 refactor-406 之前**逐字节一致**（基线 = 重构前快照；cron/heartbeat/群聊
  三段经 PromptSlots 四槽复现，位置与措辞不漂）

#### Scenario: prompt preview 与真实装配同源
- **GIVEN** `kernel.assemble_prompt_preview(*, prompt=PromptSlots, features, enabled_tools, workspace_root,
  scenario)`，消费者用与真实会话同一工厂构造的 `PromptSlots`
- **WHEN** 以某 agent 配置请求预览
- **THEN** 预览输出与该配置真实会话装配的 system prompt 一致（仅易变尾部以 `<runtime-injected:…>` 占位）；
  内核侧 product-neutral（PA 段全在传入的 PromptSlots）

### Requirement: Kernel 提供单项中立能力查询

`kernel.list_models()` / `list_tools()` / `list_features()` / `list_skills(workspace_root)` 返回
SDK-owned 不可变数据，与已装配 Kernel 实际能力一致；内核不做产品语义聚合（payload 拼装/available
计算归应用）。

`list_skills(workspace_root)` 的搜索根 = 每会话 `<workspace_root>/<workspace_config_dirname>/skills`
（由 workspace_config_dirname 约定派生）**叠加** `build_kernel(skill_search_roots=…)` 传入的部署级
共享 skill 根，按「workspace 优先 → 部署根按传入顺序」去重保序。`skill_search_roots` 是部署路径约定
（与 `workspace_config_dirname` 同层，应用经 `build_kernel` 传入；内核只搜被交给它的根，保持产品中立）；
缺省为空 → 仅 workspace skill。

#### Scenario: 能力查询与运行时事实一致
- **GIVEN** 已装配的 Kernel
- **WHEN** 调四个 list_* 查询
- **THEN** models 含目录模型 + 默认、tools 含工具目录事实、features 为内核通用项投影、
  skills 为指定 workspace 解析结果

#### Scenario: 跨 workspace 的 skill 查询互不混用
- **GIVEN** 两个 workspace_root 各有不同可发现 skills
- **WHEN** 分别 `list_skills(workspace_root)`
- **THEN** 各返回对应工作区 skill，无混用或丢失

#### Scenario: 部署级共享 skill 根叠加在每 workspace 根之上
- **GIVEN** `build_kernel(skill_search_roots=(R1, R2))` 装配的 Kernel，某 workspace 自有 skill
- **WHEN** `list_skills(workspace_root)`
- **THEN** 返回 workspace skill + R1/R2 中的 skill，顺序为「workspace → R1 → R2」去重，
  跨 workspace 调用时部署级根一致、workspace 部分各异（应用据此复刻其多层 skill 分发约定）

### Requirement: Kernel 出入参为 SDK-owned 类型

`create_session`/`fork_session` 返回 `SessionInfo`；`submit`/`get_run`/`cancel` 返回 `RunInfo`；
`compact`/`append_message`/`list_session_tools` 返回定型稳定形状。`SessionInfo`/`RunInfo`/`LLMConfig`
为真 SDK-owned 纯边界 DTO（内核边界处映射，core 不回引）。`RunOrigin`/`TERMINAL_RUN_STATUSES`/
`PermissionDecision` 因 core/platform 引用，保持其拥有、sdk re-export（闸 2 豁免）；`CanUseToolFn`
是 sdk-owned 的 `Callable` 别名（非 re-export），闸 2 对 typing 别名特殊处理，不在豁免名单之列。

#### Scenario: 会话与运行结果不暴露内核内部对象
- **WHEN** 消费者调上述方法
- **THEN** 返回 SDK-owned 冻结类型，`session_id`/`run_id`/`status` 等既有属性名与语义不变；
  内核内部 `Session`/`RunRecord`/`LLMFactoryConfig` 不出边界

### Requirement: 会话档案为无状态 per-workspace JSONL

会话档案是每会话一个 append-only JSONL，落 `{workspace_root}/{workspace_config_dirname}/sessions/
{session_id}.jsonl`。存储组件无状态（不持 session→位置 映射，按调用方传的 `workspace_root` 当场定位）。
位置由 `create_session(workspace_root)` 决定，无中心 session db 路径配置。

#### Scenario: 不同 agent 会话落各自 workspace
- **GIVEN** 两个会话以不同 `workspace_root` 创建
- **WHEN** 各自产生 turn
- **THEN** 档案分别落各自 `workspace_root` 下，互不混写

## REMOVED Requirements

- 无独立删除的 Requirement。被移除的是公共表面符号与"产品层"概念：`ProductDefinition` 及
  `LOCAL_CODING_PROFILE` / `PERSONAL_ASSISTANT_PROFILE`、`SkillRegistry`、`ConfigResolver`、
  `default_skill_search_roots`、`FEATURE_REGISTRY`、`init_model_registry` 与 model registry 查询函数、
  `LLMFactoryConfig` / `LLMConfigPayload` 全家、`HostCapabilityDispatcher` / `HostCapabilityContext`
  与 `build_kernel` 的 `host_capabilities=` 参数。（`reconfigure_llm` 保留作 CLI `/model`，仅返回类型
  改为 SDK-owned `LLMConfig` DTO，非删除。）canonical 中若有按旧符号表述的接口描写，归并时按本 delta
  的 MODIFIED/ADDED 条目改写。
