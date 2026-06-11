# kernel delta-spec — refactor-406 收敛 agent.sdk 公共表面

> 对 `docs/specs/kernel/spec.md` 的增量声明。主语 = `agent.sdk` 的消费者（产品包）。
> 本 unit 不改变会话、运行、流式事件、权限、压缩、持久化等既有行为语义；
> 变更集中在"产品如何定义自己、如何装配内核、经什么类型与内核交互"。

## MODIFIED Requirements

### Requirement: 内核对外只经 agent.sdk 暴露,产品不得依赖内核内部

（在既有内容上追加精确表面约束）

`agent.sdk` 的公开符号是一份精确允许名单（见 design.md §接口与数据流总表），由
contract 测试守卫两重不变量：

#### Scenario: 新增导出未进允许名单
- **WHEN** `agent.sdk.__all__` 含有允许名单之外的名字（或缺失名单内的名字）
- **THEN** 表面守卫 contract 测试失败

#### Scenario: 导出对象由内核内部模块拥有
- **WHEN** `agent.sdk` 的某个导出，其类型定义在 `agent.core` / `agent.platform` /
  `agent.products` 内部模块（而非 `agent.sdk` 自有模块）
- **THEN** 所有权守卫 contract 测试失败；内部对象不得通过加名单的方式成为公共契约

### Requirement: build_kernel 装配出可用的进程内 Kernel

（装配入参从内部 `ProductProfile` + `LLMFactoryConfig` 改为 SDK-owned 类型）

`build_kernel(product, llm, can_use_tool=None, repo_root=None, host_capabilities=None)`：
`product` 为 SDK-owned 不可变 `ProductDefinition`；`llm` 为 SDK-owned `LLMConfig`
（providers/models 目录 + 默认模型 + 可选激活连接覆盖）。模型注册表初始化发生在
`build_kernel` 内部，消费者无任何前置初始化时序义务。

#### Scenario: 产品零前置调用直接装配
- **GIVEN** 消费者构造了 `ProductDefinition` 与 `LLMConfig`（含 `LLMConfig.from_env()` 路径）
- **WHEN** 消费者未调用任何注册表初始化函数，直接 `build_kernel(product=..., llm=...)`
- **THEN** Kernel 正常装配，模型解析、默认 provider 推导均可用

#### Scenario: 内置产品经同一公共构造装配
- **WHEN** 消费者传入 SDK 导出的 `LOCAL_CODING` / `PERSONAL_ASSISTANT` 定义常量
- **THEN** 装配结果（工具集、hook 集、skill 发现、system prompt 逐字节）与
  refactor-406 之前经内部 profile 装配一致

### Requirement: LLM 配置可查询、可纯配置切换

（返回类型从内部 `LLMFactoryConfig` 改为 SDK-owned `LLMConfig` DTO）

#### Scenario: 查询与热切换返回 SDK-owned DTO
- **WHEN** 消费者调用 `kernel.get_llm_config()` 或 `kernel.reconfigure_llm(**patch)`
- **THEN** 返回 SDK-owned `LLMConfig`，字段语义（provider/model/base_url/timeout/api_key）
  与切换即时生效行为不变

## ADDED Requirements

### Requirement: 产品以 SDK-owned ProductDefinition 完整定义自身

新产品仅依赖 `agent.sdk` 即可声明完整产品定义并装配可运行 Kernel，不修改 `agent`
包内部源码。`ProductDefinition` 覆盖：identity（product_id/display_name/
config_namespace）、prompt（`prompt_head`/`prompt_body` 静态文本槽）、feature
（`features` 选用内置 + `custom_features` 自带声明）、能力对象（`tools`/`hooks`/
`skill_dirs`）、工具默认集（default/optional tool ids）、路径与策略
（global_config_home/workspace_config_dirname/session_db_filename 等）。

#### Scenario: 外部产品零内核改动接入
- **GIVEN** 一个 `agent` 包之外的产品包，自带工具实例与 hook callable
- **WHEN** 它构造 `ProductDefinition` 并 `build_kernel`
- **THEN** 其工具/hook/skill/prompt/路径全部生效，无需向 `agent.products` 添加目录
  或修改内核源码

#### Scenario: 产品工具满足结构化 Tool 契约即可被装配
- **GIVEN** 一个对象具备 `name: str`、`description: str`、`input_schema: dict`、
  可调用 `run(args, ctx)`（无须继承内核内部基类）
- **WHEN** 它出现在 `ProductDefinition.tools` 中
- **THEN** 该工具被注册并可在会话中执行，`ctx` 提供 delta 承诺的稳定字段子集
  （session_metadata、repo_root、工作区路径族）

### Requirement: feature 统一模型支持内置选用与产品自带声明

内核合并"产品 `features` 选中的内置 feature"与"`custom_features` 自带声明"为统一
feature 表，统一驱动 prompt 指引段门控（flag 开 + requires_tool 在场 +
requires_features 全开）、per-agent 配置开关与能力查询投影。

#### Scenario: 产品自带 feature 与内置 feature 行为同构
- **GIVEN** 产品在 `custom_features` 声明了一个带 guidance 文本与 requires_tool 的 feature
- **WHEN** 某会话开启该 feature 且所需工具在活动工具集中
- **THEN** 其指引段出现在 system prompt 中、`kernel.list_features()` 含该条目，
  语义与内置 feature 完全一致

#### Scenario: feature 由产品声明晋升为内核内置后消费者无感
- **GIVEN** 某 feature 定义从产品 `custom_features` 迁入内核注册表，key 不变，
  产品改为在 `features` 中选用
- **WHEN** 既有 per-agent 配置以同一 key 开关该 feature
- **THEN** 配置语义、prompt 门控与能力投影结果不变

### Requirement: prompt 由内核装配模板与产品静态文本槽组装

内核拥有装配模板（顺序固定：prompt_head → core 行为规则 → feature 指引 →
prompt_body → core 自进化指引 → 后台任务/runtime footer → 用户自定义指令机制段 →
易变尾部）；产品经 `PromptText(name, text)` 填充两个静态文本槽。内部段落机器
（PromptSection/PromptContext/RenderMode）不在公共表面。

#### Scenario: 内置产品模板装配与既有 prompt 逐字节等价
- **WHEN** PA / LC 经 ProductDefinition 模板路径装配 system prompt
- **THEN** 在相同会话条件（features、tools、scenario、vars）下与 refactor-406 之前
  逐字节一致

#### Scenario: 机制段由会话元数据驱动、产品中立
- **GIVEN** 任意产品的会话携带 custom_prompt vars（或群聊 scenario 与参与者元数据）
- **WHEN** 装配该会话的 system prompt
- **THEN** 用户自定义指令段（或群聊通信上下文段）按既有措辞渲染；不携带相应
  元数据的会话不渲染

### Requirement: Kernel 提供单项中立能力查询

`kernel.list_models()` / `list_tools()` / `list_features()` /
`list_skills(workspace_root)` 返回 SDK-owned 不可变数据，与已装配 Kernel 的实际
运行时能力一致。内核不提供产品语义聚合（payload 拼装、available 计算归产品）。

#### Scenario: 能力查询与运行时事实一致
- **GIVEN** 一个已装配的 Kernel
- **WHEN** 消费者调用四个 list_* 查询
- **THEN** models 含目录全部模型与默认模型、tools 含产品声明的 default+optional 集
  及 default_on 区分、features 为统一 feature 表投影（key/default_on/requires_tool/
  展示键）、skills 为指定 workspace 解析结果（name/description）

#### Scenario: 跨 workspace 的 skill 查询互不混用
- **GIVEN** 两个 workspace_root 各有不同的可发现 skills
- **WHEN** 分别调用 `kernel.list_skills(workspace_root)`
- **THEN** 各自返回对应工作区可见的 skill 集，无混用或丢失

### Requirement: Kernel 方法出入参为 SDK-owned 类型

`create_session`/`fork_session` 返回 `SessionInfo`（session_id/title/workspace_root/
metadata）；`submit`/`get_run`/`cancel` 返回 `RunInfo`（run_id/session_id/status）；
`compact`/`append_message`/`list_session_tools` 返回定型的稳定形状；`RunOrigin`、
`TERMINAL_RUN_STATUSES`、`PermissionDecision`、`CanUseToolFn` 为 SDK-owned。

#### Scenario: 会话与运行结果不暴露内核内部对象
- **WHEN** 消费者调用上述方法
- **THEN** 返回对象为 SDK-owned 冻结类型，`session_id`/`run_id`/`status` 等
  既有属性名与语义不变；内核内部 dataclass 不出边界

## REMOVED Requirements

- 无独立删除的 Requirement。被移除的是公共表面符号（`SkillRegistry`、
  `ConfigResolver`、`default_skill_search_roots`、`FEATURE_REGISTRY`、
  `init_model_registry` 与 model registry 查询函数、`LLMFactoryConfig`/
  `LLMConfigPayload` 全家、`LOCAL_CODING_PROFILE`/`PERSONAL_ASSISTANT_PROFILE`），
  canonical 中若有按旧符号表述的接口描写，归并时按本 delta 的 MODIFIED 条目改写。
