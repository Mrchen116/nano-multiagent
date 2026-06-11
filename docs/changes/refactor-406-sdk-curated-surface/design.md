# refactor-406: 收敛 agent.sdk 公共表面 — 技术方案

> Unit branch: `unit/refactor-406` (will be created by orchestrator)
>
> 对齐: motivation.md v1

## Changelog

## 现状分析

### 涉及范围

- `src/agent/sdk/` 当前既是内核装配入口，也是 `core` / `platform` /
  `products` 内部对象的转发出口。本 unit 需要收敛其顶层公开符号、Kernel
  方法签名和装配配置。
- `src/agent/platform/bootstrap.py` 已负责把产品 profile 解析为 tool、hook、skill、
  config 和 session 等运行时对象。本 unit 应复用这条装配链，而不是另建一套 capability
  扫描链。当前完整的多产品定义能力已经存在，但其 `ProductProfile` 类型位于内部
  `agent.products`，尚未形成可供任意产品安全依赖的 SDK 契约。
- `src/personal_assistant/reporter/upstream_reporter.py` 当前直接消费 SDK 转发出的
  registry、resolver、profile 和 feature registry，再组合成 IM 所需的 node / agent
  capability payload。本 unit 需要把内部发现逻辑移回内核边界内，同时保留 Gateway
  对 IM payload 的所有权。
- `src/personal_assistant/main.py`、`src/personal_assistant/gateway/inbound_pipeline.py`
  和 `src/coding_cli/commands.py` 直接使用当前 SDK 的 profile、模型 registry 和内部配置类型，
  是公共表面迁移的主要调用方。
- `tests/contract/` 已有产品只能 import `agent.sdk` 的依赖方向守卫和 Kernel 行为契约，
  但没有精确约束 SDK 允许公开哪些符号、公开对象由哪一层拥有。

### 既有约束

- `coding_cli` 与 `personal_assistant` 只能 import `agent.sdk`，不得通过迁移改为直接依赖
  `agent.core`、`agent.platform` 或 `agent.products`。
- `agent.sdk` 可以向下装配 `core` / `platform` / `products`，但不能反向依赖
  `coding_cli`、`personal_assistant` 或 `IM`。
- SDK 只能提供产品中立的内核能力；IM 字段、展示文案、feature 可用性投影和 Gateway
  协议 payload 仍由 Gateway 负责。
- SDK 必须保持开放装配：新增产品在自身包内提交完整产品定义即可运行，不得要求修改
  `agent` 内部源码、向 SDK 增加产品 ID 分支，或把产品专属实现并入 SDK。
- capability payload 的 models、skills、tools、features、默认值、顺序和 workspace
  差异均为迁移不变量。
- 本 unit 不为错误公开的内部实现符号提供兼容层，也不顺带重构与 SDK 边界无直接关系的
  core/platform 内部问题。
- public API 必须有 Google 风格 docstring；测试先落最窄的 SDK / Gateway / CLI
  契约层，再跑跨包 contract 与产品回归。

### 契约层 Grounding

- `docs/specs/kernel/spec.md` 与当前代码在“产品只经 `agent.sdk` 进程内调用内核”这一行为上
  一致，但它当前仍以旧装配参数和内部类型描述公共接口，也没有定义“精确公开面”“禁止内部
  passthrough”以及稳定能力查询契约。本 unit 的 kernel delta-spec 不是局部补丁，而是对
  SDK 公共契约相关章节的系统重写；会话、运行、流式事件和权限等既有行为语义保持不变。
- `docs/specs/gateway/spec.md`、`docs/specs/im/spec.md` 与 capability 查询、工作区 skill
  差异和配置同步的当前代码一致。本 unit 保持这些行为，不产生 Gateway/IM 行为增量。
- `docs/specs/cli/spec.md` 与 CLI 进程内创建 Kernel、流式执行和权限交互的当前代码一致。
  本 unit 只更换内部调用契约，不产生 CLI 行为增量。
- 发现的实现层张力是 `FEATURE_REGISTRY` 同时包含内核 feature 元数据与 IM 展示键，但该
  ownership 问题不改变当前外部契约；本 unit 只阻止它作为可变内部 registry 穿透 SDK。

### 可复用能力

- `bootstrap_product()` 已一次性得到有效 tool registry、skill registry、config resolver、
  默认工具和 prompt sections；保留其“完整产品定义一次解析”的模式，并在 SDK 边界前后做
  稳定定义到内部 profile 的转换，避免 Gateway 重复了解产品目录布局。
- `Kernel.stream()` 已把内部 `StreamEvent` 转换为稳定字典。这是本 unit 应沿用的 facade
  模式：SDK 在边界处转换，调用方不持有内部 dataclass 或 registry。
- `HostCapabilityDispatcher` / `HostCapabilityContext` 已形成产品中立的 host 扩展协议；
  其能力边界应保留，但公开类型的 ownership 需要纳入统一审计。
- Gateway 的 `ReporterCapabilities` 及 node / agent payload builder 已承担 IM 协议投影，
  应继续作为产品 adapter 使用，只替换底层数据来源。

### 相关历史

- `refactor-387` 把独立 HTTP Kernel 改为进程内库，并建立产品只 import `agent.sdk` 的方向约束；
  本 unit 完成其尚未完成的“稳定公共契约”部分。
- `feat-379` 与 `feat-394` 建立了当前 models / skills / tools / features capability
  语义和 per-agent workspace 差异；这些结果是本次迁移的回归基线。
- `bugfix-402` 引入产品中立的 host capability dispatcher，证明 SDK 可以暴露窄协议而不暴露
  cron 等产品实现类型。

## 架构总览

### Before

```text
coding_cli ----------------------+
                                 |
personal_assistant --------------+--> agent.sdk
  |                                    |
  | capability reporter                +--> Kernel / build_kernel
  |                                    +--> core registries and DTOs
  +--> SDK re-exported internals -------+--> platform ConfigResolver
       (skills/models/features/profile) +--> product profiles
                                            |
                                            v
                                  core / platform / products
```

产品虽然没有直接 import 内核内部包，但可以经 `agent.sdk` 持有内部 registry、resolver、
profile 和可变 metadata，导致 SDK 边界只在语法上成立。

### After

```text
 coding_cli        personal_assistant       any new agent product
     |                     |                         |
     | SDK-owned Product Definition + extensions    |
     +---------------------+-------------------------+
                           |
                           v
                 agent.sdk curated facade
               +----------------------------+
               | stable product definition  |
               | Kernel lifecycle/actions   |
               | neutral capability view    |
               +-------------+--------------+
                             |
                   boundary conversion
                             |
                             v
                internal composition/bootstrap
                core registries / platform IO

 personal_assistant only:

 neutral capability view --> Gateway capability adapter --> IM payload
                              (owns projection semantics)
```

核心思路是把 SDK 变成真正的 anti-corruption layer：内部可以继续用 registry、resolver、
profile 和内部 dataclass，但越过 `agent.sdk` 时必须转换成 SDK 自己拥有的窄契约。Gateway
读取中立能力描述后继续负责 IM payload 的字段组织、默认值和可用性计算；CLI 只消费稳定的
Kernel 装配与运行接口。SDK 同时把现有完整多产品定义能力公开化：产品定义由产品自身持有，
SDK 负责解析和装配，不通过内置产品枚举或产品 ID 映射限制可接入的产品集合。

## 关键决策

### 决策 1: 公开产品定义形态 — SDK-owned 不可变 ProductDefinition

- **选择**: SDK 拥有一个不可变的公共 `ProductDefinition` 类型。产品（内置或外部）在
  自己的包里构造它，直接传给 `build_kernel()`；SDK 在边界内将其转换为内部
  `ProductProfile` 并驱动 `bootstrap_product()`。它覆盖现有 profile 的全部语义
  （identity、prompt、tool/hook 默认集、路径策略、layouts），并新增现状缺失的
  **产品自有能力来源**字段（具体形态由决策 2 定为对象直传 + skill 目录），替代
  `bootstrap._product_root()` 写死的 `agent/products/<product_id>/` 包内目录推导。
  两个内置产品同路径迁移，加载结果与现状一致。
- **理由**: 现状的产品扩展机制是"agent 包内目录约定"——外部产品的工具物理上放不进
  `agent/products/`，所以开放扩展必然要求公共定义携带能力来源；定义由产品持有、
  作为参数直传则天然无全局状态与初始化顺序问题。
- **拒绝**: 公开内部 `ProductProfile` —— 它没有能力来源字段（目录是推导的），公开了
  也接不进外部工具，且其 `prompt_sections_builder` 要求持有内部 `PromptSection`
  类型，等于把内部组织方式抬成公共契约。全局 `register_product()` 注册表 —— 重蹈
  `init_model_registry` 必须先于 `LLMFactoryConfig.from_env()` 调用的顺序 footgun。
  内置产品枚举 / product-id 分派表 —— 与开放扩展方向（澄清 Q7/Q8）直接冲突。
- **风险**: `ProductProfile` 字段语义必须完整映射，遗漏任何一项都会迫使内置产品迁移
  时绕回内部类型；prompt sections 的公共形态是已知难点，在决策 3 单独对齐。

### 决策 2: 产品能力扩展契约 — 对象直传，类型由 SDK 拥有

- **选择**: `ProductDefinition` 以对象形式接收产品能力：
  - `tools=(...)` —— 工具实例元组。契约为 SDK 拥有的 `Tool` 结构化 Protocol
    （`name` / `description` / `input_schema` / `run(args, ctx)`，与现有
    `loader._is_tool()` 鸭子检查一致），另提供可选便利基类供外部产品继承。
    内置产品现有工具类（如 `SendMessageTool`）天然满足 Protocol，一行不改。
  - `hooks=(...)` —— `setup(hooks)` 形态的可调用对象元组，`HookAPI` 稳定面由 SDK 拥有。
  - `skill_dirs=(...)` —— skill 是 SKILL.md 目录数据资产而非代码对象，保持目录传递。
  - `bootstrap._product_root()` 的 `agent/products/<id>/` 包内目录扫描随之退役：
    内置产品改为在自己的 profile 模块里显式列出工具实例与 hook callable。
    工作区用户工具的 `.nano/tools` 运行时发现机制不变（另一机制，非本契约）。
- **理由**: 程序化 SDK 入口的常规形态是对象直传——类型安全、IDE 可补全、可单测、
  不依赖文件系统布局；`registry.register(tool)` 本就接收实例，直传零转换成本。
  目录约定本质上为"用户向工作区投放 .py 文件"的运行时插件发现服务，不适合做
  程序化装配入口。
- **拒绝**: `tool_dirs/hook_dirs` 目录传递 —— 把内部加载实现（文件命名、模块导出
  约定）抬成公共契约，且对象不可单测、不可静态检查。要求继承内部
  `agent.core.tools.base` 基类 —— 泄漏内部类型；SDK 拥有的契约类不在此列。
- **风险**: `run(args, ctx)` 中 `ctx` 的稳定字段子集、hook 事件名集合随之成为公共
  契约，需在接口与数据流段逐项定义承诺范围。

### 决策 3: prompt 与 feature 的公共形态 — 统一 Feature 模型 + 内核装配模板填槽

- **选择**: 三部分构成，PA 与任何外部产品完全对等，无内部逃生舱：
  1. **统一 Feature 模型，两个户籍**。`FeatureDefinition(key, guidance 文本,
     default_on, requires_tool, requires_features, label_i18n/help_i18n)` 为 SDK-owned
     值对象。内核内置 feature 住 `FEATURE_REGISTRY`（`memory_curation` /
     `skill_creation`，其工具是平台内置）；产品自带 feature 在
     `ProductDefinition.custom_features` 声明（PA 的 `heartbeat` / `cron_scheduling` /
     `cron_routing`——其机制代码本在 PA/Gateway 侧，指引文本逐字搬进声明）。内核合并
     两者为一张 feature 表，统一驱动 per-agent 配置开关、prompt 段门控
     （flag 开 + requires_tool 在场 + requires_features 全开）与 capability 投影。
     现有 `layer: "core" | "product"` 硬编码区分由"按产品显式选择/声明"替代，
     capability payload 结果不变。**孵化→晋升路径**：feature 先在产品包内声明迭代，
     成熟后把 `FeatureDefinition` 搬进内核注册表、产品改为 `features=` 选用同名
     key——key 不变，用户 per-agent 配置与 IM toggle 无感。
  2. **产品静态文本填槽**。内核拥有装配模板（顺序固定：prompt_head → core 行为规则 →
     feature 指引 → prompt_body → core 自进化指引 → 后台任务/runtime footer →
     用户自定义指令 → 易变尾部），产品经 `prompt_head` / `prompt_body` 传入
     `PromptText(name, text)` 静态文本元组。两槽位置提炼自 PA/LC builder 的现有
     交错顺序（身份在 core 规则前、行为守则在 core 规则后），逐字节可复现现状
     （黄金等价测试守卫）。排序、缓存前缀分界、机制段位置是内核的提示词工程知识，
     不对产品开放。
  3. **机制段移入内核**。`pa.user_custom`（custom_prompt vars 门控）与
     `pa.communication_context`（群聊 scenario 门控）不是 feature（无开关），是由
     会话元数据驱动的内核机制段，从 PA 包迁入内核模板；LC 等不带相应元数据的产品
     永不渲染，逐字节不变。
  - `ProductProfile.prompt_sections / prompt_sections_builder` 字段随之退役；
    `PromptSection` / `PromptContext` / `RenderMode` 全家保持内核内部。
- **理由**: 段落盘点显示 24 个段落恰好三分：通用机制指引（feature/机制段）、产品
  静态文本、core 段——与"feature 内核管、个性化产品传"的拆分完全吻合；统一 Feature
  模型直接支撑真实演进史（heartbeat/cron 即在 PA 孵化）的孵化→晋升路径。
- **拒绝**: 公开 `PromptSection` 协议 —— `PromptContext` / flags / RenderMode 全家
  成为公共 ABI，与收敛方向相反。内置产品包内构造挂内部 sections builder（早期方案）
  —— PA 获得外部产品没有的特权通道，违背对等原则。仅公开单一 `system_prompt` 字符串
  —— 表达不了现有交错排序，PA/LC 无法迁移。
- **风险**: heartbeat/cron 指引段、user_custom、communication_context 的文本搬迁
  必须逐字（黄金等价测试 + bugfix-358 mention 格式测试钉死措辞）；`label_i18n` 等
  IM 展示键随 custom_features 声明回产品侧，内置 feature 的展示键仍在内核注册表
  （ownership 张力部分缓解，剩余维持现状）。

### 决策 4: 能力查询 — Kernel 提供单项中立查询，Gateway 自己拼装

- **选择**: Kernel 新增四个正交的单项查询方法，各返回 SDK-owned 不可变 DTO
  （沿用 `stream()` 边界转换先例，不返回 registry / resolver 对象）：
  - `kernel.list_models()` —— 可用模型 + 默认模型（CLI 模型选择器同样可用）。
  - `kernel.list_tools()` —— 工具事实：name / description / default_on
    （来自产品定义的 default + optional 集）。
  - `kernel.list_features()` —— 决策 3 统一 feature 表：key / default_on /
    requires_tool / 展示键（与 `assemble_prompt_preview` 的 features 同源）。
  - `kernel.list_skills(workspace_root)` —— 该工作区解析出的 skills：
    name / description（per-agent 工作区差异由内核已有发现链解析）。
  Gateway 的 `ReporterCapabilities` / payload builder 调这四个查询完成产品层拼装：
  IM 协议字段组织、按 tool_allowlist 计算 `available`、组帧——投影语义全部留在
  Gateway（澄清 Q3）。SDK 随之撤出 reporter 专用导出：`SkillRegistry`、
  `ConfigResolver`、`default_skill_search_roots`、`FEATURE_REGISTRY`、model registry
  列表函数（model 函数全套去留并入决策 5）。
- **理由**: 消除 Gateway 手工重建内核包磁盘布局（`upstream_reporter._product_root()`）
  这一最深越界；查询来自已 bootstrap 的 Kernel，与运行时实际能力天然一致——现状
  reporter 自建链与 bootstrap 链是两套，已出现 advertise 阶段看不到 memory /
  skill_manage 的分叉（靠注释解释）。单项查询是内核本来就有的中立事实，各有独立
  价值；"打包快照"的形状本身就是被 Gateway 上报需求塑出来的，不该进内核。
- **拒绝**: `kernel.capabilities()` 聚合大快照 —— 打包结构由产品需求反向定义内核
  接口。SDK 模块级 capability 查询函数（不经 Kernel 实例）—— 重新引入初始化顺序
  问题与第二条解析链。快照内直接算好 `available` —— 把 Gateway 投影语义吸进内核，
  违背 Q3。
- **风险**: 四个查询的字段并集必须覆盖 reporter 现用的每一项事实（models 顺序、
  tools 的 default_on 区分、features 的全部投影输入）；milestone 内先做
  "查询字段 ↔ payload 字段"映射表再迁移，漏一项 Gateway 就被迫绕回内部。

### 决策 5: LLM 配置 — 单一 `llm` 入参，注册表初始化收进 build_kernel

- **选择**: `build_kernel(product=..., llm=...)` 只接收一个 SDK-owned 的
  `LLMConfig`：providers/models 目录 + 默认模型 + 可选激活连接覆盖
  （provider / model / base_url / api_key / timeout），即现状 `LLMConfigPayload`
  与 `LLMFactoryConfig` 两份信息合一。模型注册表初始化发生在 `build_kernel()`
  内部——产品侧不再存在"先 init 再 from_env"的时序，footgun 按构造消失。
  SDK 提供 `LLMConfig.from_env()` 便利构造（只读 env，不查注册表，无顺序依赖）。
  SDK 撤出：`init_model_registry`、`get_default_model` / `get_default_provider` /
  `list_provider_models` / `list_supported_providers`（查询由决策 4 的
  `kernel.list_models()` 承接）、`LLMFactoryConfig` / `LLMConfigPayload` /
  `LLMModelPayload` / `LLMProviderPayload` 全家。`kernel.get_llm_config()` /
  `reconfigure_llm()` 改为返回 SDK-owned DTO。
- **理由**: LLM 配置是部署期事实，与产品身份正交（故不进 `ProductDefinition`，
  保持 `build_kernel` 独立参数）；"两份配置 + 全局 init + 顺序靠注释"
  （coding_cli/commands.py 现有警告注释）是 HTTP 时代两步装配的遗迹，进程内库
  没有理由保留。
- **拒绝**: 保留 `init_model_registry` 仅补文档 —— footgun 还在，只是写了说明书。
  LLM 目录并入 `ProductDefinition` —— 部署配置与产品定义耦死，换模型要改产品定义。
- **风险**: `reconfigure_llm` 是 CLI `/model` 运行中换模型的热路径
  （coding_cli/commands.py:535，行为不变量），DTO 转换须保字段语义逐项一致；
  内部全局注册表消费点多，worker 评估改 kernel 实例持有若波及面超出本 unit 边界，
  允许退守"全局保留但仅由 build_kernel 写入"，公共契约不变。

### 决策 6: Kernel 方法出入参 — 全部换成 SDK-owned 类型

- **选择**: 沿用 `stream()` / `get_session()` 的边界转换先例，Kernel 方法签名上
  不再出现内核内部类型：
  - `create_session` / `fork_session` → SDK-owned 冻结 `SessionInfo`
    （session_id / title / workspace_root / metadata）；
  - `submit` / `get_run` / `cancel` → 冻结 `RunInfo`（run_id / session_id / status）；
  - 现为 `-> Any` 的 `compact` / `append_message` / `list_session_tools` 一并定型为
    稳定 DTO 或 dict 形状；
  - `RunOrigin` 枚举本体归 SDK（产品代码不改，边界映射内部值）；
    `TERMINAL_RUN_STATUSES` 保留 frozenset 字符串常量、所有权挪到 SDK
    （Gateway 拿它比对 stream 事件 status 字符串，inbound_pipeline.py:811）；
  - `PermissionDecision` / `CanUseToolFn` 纳入同一 ownership 审计：类型归 SDK。
  DTO 字段以"产品实际消费 + 合理稳定面"为限，不镜像内部 dataclass。grounding：
  产品实际只消费 `session.session_id`、`run_record.run_id / .session_id`、
  status 字符串与 RunOrigin 枚举值。
- **理由**: 现状 Kernel 把整个内部 `Session` / `RunRecord` 端给产品，内部重构任一
  字段都是对产品的隐式契约变更；DTO 字段即承诺，方法返回值是有限结构，typed DTO
  比裸 dict 多给产品 IDE 补全与类型检查。
- **拒绝**: 全部返回裸 dict —— dict 适合 stream 事件这种开放结构，方法返回值
  应当 typed。继续 re-export 内部 dataclass —— 本 unit 要消除的正是这个。
- **风险**: 属性名与现状保持一致（session_id / run_id / status），CLI / Gateway
  迁移基本无感；需逐一核对 Gateway `_KernelClientShim`（旧 kernel_client 协议
  垫片）实际触碰的 RunRecord 字段。

### 决策 7: 公共表面守卫 — 精确允许名单 + 所有权来源检查（contract 测试）

- **选择**: 新增 contract 测试两道闸（成熟 SDK 的通行做法——NumPy
  test_public_api / pandas test_api 维护显式名单，.NET PublicApiAnalyzers /
  api-extractor 把 API 变更钉进可 review 的文件 diff）：
  1. **精确名单**：`set(agent.sdk.__all__) == EXPECTED_SURFACE` 逐字相等，
     增删任何导出都必须同步修改 contract 测试中的名单——"扩公共契约"被迫成为
     PR 里显式可 review 的动作。
  2. **所有权来源**：每个导出对象的 `__module__`（实例按 `type(obj).__module__`）
     必须以 `agent.sdk` 开头——内部对象即使被加进名单也过不了这道闸，唯一出路
     是在 SDK 建 SDK 拥有的窄类型。`LOCAL_CODING` / `PERSONAL_ASSISTANT` 是
     `ProductDefinition` 实例、在 agent.products 包内构造，按类型所有权判定不违规
     （构造位置不设限，类型所有权才是闸）。
  现有 import 方向 contract 测试（test_agent_sdk_boundary_contract 等）保留不动。
- **理由**: 现状只有方向守卫、没有表面守卫，正是"产品每要一个内部对象就加一行
  re-export"能反复发生的原因（motivation 痛点）；contract 测试是本仓既有的
  架构守卫惯例，Python 无编译器级私有性，测试是实现 Go `internal/` / Rust
  `pub(crate)` 同等约束的常规替代。
- **拒绝**: 纯文档约定 —— 已被现状证伪。自定义 lint 规则 —— 表达不了所有权来源
  语义，且偏离本仓 contract 测试惯例。
- **风险**: 名单成为高频 review 焦点（设计目的，非缺陷）；闸 2 对函数 / 常量
  （frozenset 无 `__module__`）的判定细节 worker 逐类处理，必要时对常量做
  显式豁免注记。

### 决策 8: 迁移顺序 — 扩张→迁移→收缩三段式，新旧表面共存过渡

- **选择**:
  - **阶段一（扩张）**: 新表面（ProductDefinition / LLMConfig / DTO / kernel 查询
    方法）在 SDK 长出来，旧导出一个不动；全部既有测试零改动保持绿，每个 commit
    可独立回退。
  - **阶段二（迁移）**: 消费方逐个切，各一个独立 commit：① 内置产品定义改走
    ProductDefinition（黄金 prompt 等价测试钉逐字节）；② CLI 切新表面（消费面小）；
    ③ Gateway 切新表面（reporter 重建链 → `kernel.list_*()`；动 reporter **之前**
    先录 capability payload 回归基线 fixture，切完逐字段比对）。新旧表面共存，
    任一步出问题 revert 单个 commit 即回到旧表面，互不阻塞。
  - **阶段三（收缩）**: 删全部旧导出；决策 7 的精确名单守卫测试随同一 commit 落闸
    （名单即最终表面——早进会红，晚进有空窗）。
  - 硬规则：删除任何旧导出前其替代必须已被全部调用方使用（motivation 迁移不变量）；
    capability payload 基线先录后动。
- **理由**: `agent.sdk` 是两个在线产品的唯一入口，原地改签名意味着 CLI / Gateway /
  测试同 commit 全改、回退粒度归零——正是 motivation 禁止的大爆炸迁移。
- **拒绝**: 一步到位改 `build_kernel` 签名 —— 无回退粒度。先删后迁 —— 问题只能
  向前修不能向后退。
- **风险**: 共存期 SDK 表面临时变大，靠阶段三收口；共存期跨多个 milestone，
  期间其他 unit 并行改 SDK 文件会冲突——orchestrator 派发时本 unit 对 SDK 文件
  的改动应独占。

## 接口与数据流

### 最终公共表面（决策 7 守卫名单的内容来源）

| 类别 | 导出 | 形态 | 替代的旧导出 |
|---|---|---|---|
| 装配 | `build_kernel(product, llm, can_use_tool=None, repo_root=None, host_capabilities=None)` | 函数 | 同名（签名收紧：`product_profile`→`product`，`llm_config`→`llm`） |
| 装配 | `Kernel` | 类 | 同名 |
| 产品定义 | `ProductDefinition` | 冻结 dataclass | `LOCAL_CODING_PROFILE` / `PERSONAL_ASSISTANT_PROFILE`（类型层面） |
| 产品定义 | `FeatureDefinition` | 冻结 dataclass | `FEATURE_REGISTRY`（产品声明侧） |
| 产品定义 | `PromptText` | 冻结值对象 (name, text) | profile.prompt_sections* 字段 |
| 产品定义 | `Tool` | 结构化 Protocol（name/description/input_schema/run）+ 可选便利基类 | （新增；现状为目录约定） |
| 产品定义 | `ToolContext` | 类型 façade（承诺字段子集） | `agent.core.tools.base.ToolContext` 直 import |
| 产品定义 | `HookAPI` | 类型 façade（`setup(hooks)` 入参面） | （新增） |
| 内置产品 | `LOCAL_CODING` / `PERSONAL_ASSISTANT` | `ProductDefinition` 实例 | `LOCAL_CODING_PROFILE` / `PERSONAL_ASSISTANT_PROFILE` |
| LLM | `LLMConfig`（含 `.from_env()`） | 冻结 dataclass | `LLMFactoryConfig` + `LLMConfigPayload` 全家 + `init_model_registry` |
| 结果 | `SessionInfo` / `RunInfo` | 冻结 dataclass | 内部 `Session` / `RunRecord` |
| 枚举/常量 | `RunOrigin` / `TERMINAL_RUN_STATUSES` | SDK-owned 枚举 / frozenset | 同名 re-export |
| 权限 | `PermissionDecision` / `CanUseToolFn` | SDK-owned 类型 | 同名 re-export |
| Host 能力 | `HostCapabilityDispatcher` / `HostCapabilityContext` | 抽象基类（ownership 审计后归 SDK） | 同名 re-export |

**整体撤出、无替代**（消费方改问 Kernel）：`SkillRegistry`、`ConfigResolver`、
`default_skill_search_roots`、`FEATURE_REGISTRY`、`init_model_registry`、
`get_default_model`、`get_default_provider`、`list_provider_models`、
`list_supported_providers`。

### Kernel 方法面（变更点）

| 方法 | 现返回 | 改后 | 备注 |
|---|---|---|---|
| `create_session` / `fork_session` | 内部 `Session` | `SessionInfo` | 决策 6 |
| `submit` / `get_run` / `cancel` | 内部 `RunRecord` | `RunInfo` | 决策 6 |
| `compact` / `append_message` / `list_session_tools` | `Any` | 定型 DTO / dict | 决策 6 |
| `get_llm_config` / `reconfigure_llm` | 内部 `LLMFactoryConfig` | `LLMConfig` DTO | 决策 5 |
| `list_models()` | （新增） | 模型名元组 + 默认模型 | 决策 4 |
| `list_tools()` | （新增） | (name, description, default_on) 元组 | 决策 4 |
| `list_features()` | （新增） | 统一 feature 表投影（key/default_on/requires_tool/展示键） | 决策 3/4 |
| `list_skills(workspace_root)` | （新增） | (name, description) 元组 | 决策 4 |
| `stream` / `get_session` / `interrupt` / `submit_permission_decision` / `current_event_sequence` / `aclose` / `assemble_prompt_preview` | 不变 | 不变 | 已是稳定形态 |

### 数据流 1: 产品装配（任意产品同一条路）

```text
产品包: ProductDefinition(tools=…, hooks=…, features=…, custom_features=…,
                          prompt_head/body=…, 路径与策略…)
            |
            v  build_kernel(product, llm)
agent.sdk 边界转换: definition -> 内部 ProductProfile + 直传对象
            |
            v
bootstrap_product(): 注册 tools 实例（替代 _product_root 目录扫描）
                     注册 hooks callable / skill_dirs
                     合并 内置features(选中) + custom_features -> 统一 feature 表
                     模板装配 prompt: head -> core规则 -> feature指引 ->
                       body -> core指引 -> footer -> 机制段 -> 易变尾部
            |
            v
LLMConfig -> 内核内部初始化模型注册表（无产品侧时序）
            |
            v
Kernel（持有统一 feature 表、tool/skill registry、resolver —— 全部不出边界）
```

### 数据流 2: Gateway 能力上报（决策 4 之后）

```text
Gateway reporter:
  kernel.list_models() ──┐
  kernel.list_tools()  ──┤   (SDK-owned 不可变 DTO)
  kernel.list_features()─┤
  kernel.list_skills(workspace_root) ─┘
            |
            v
  ReporterCapabilities / payload builder（Gateway 拥有）:
    字段组织、available=requires_tool∈allowlist 计算、默认值呈现、IM 帧组装
            |
            v
  node.register / node.capabilities / agent.capabilities.resolve （payload 逐字段与现状一致）
```

### 产品扩展作者契约（决策 2 的承诺面）

- Tool: 对象满足 `name: str` / `description: str` / `input_schema: dict` /
  `run(args: Mapping, ctx: ToolContext) -> Mapping`；`ToolContext` 承诺字段子集
  在 delta-spec 中逐项列（基线：`session_metadata`、`repo_root`、工作区路径族），
  其余字段不承诺。
- Hook: callable `setup(hooks: HookAPI) -> None`；`HookAPI.on(event, handler, …)`
  的事件名集合为公共契约，稳定性分级在 delta-spec 标注。
- Skill: `skill_dirs` 下每个子目录一个 skill，含 SKILL.md（name/description 元数据），
  与现状工作区 skill 格式一致。

## 契约层增量 (delta-spec)

- kernel: `specs/kernel/spec.md`（重写 SDK 公共契约相关章节）
- im: no spec delta
- gateway: no spec delta
- cli: no spec delta

## 风险与回退

### 已知风险

1. **prompt 字节漂移**（决策 3）：feature/机制段文本从 PA 包迁声明、模板装配替代
   builder，任何措辞/顺序漂移都破坏 K2.6 心跳反射规避（memory:
   project-k26-heartbeat-ok-reflex）与 provider 前缀缓存命中。对策：黄金等价测试
   （现有 test_pa_golden_* + 新增 LC/PA 全 prompt 逐字节对照）先行落地，红了即停。
2. **capability payload 漂移**（决策 4）：reporter 数据源整体替换。对策：动 reporter
   前先把现网 node/agent capability payload 录成 fixture，切换后逐字段比对
   （models 顺序、tools default_on、features 投影、per-workspace skills 差异）。
3. **模型注册表改造波及面**（决策 5）：内部消费点多。对策：已在决策 5 内置退守
   路径——"全局保留但仅由 build_kernel 写入"，公共契约不变。
4. **`_KernelClientShim` 隐式字段依赖**（决策 6）：垫片可能触碰 RunRecord 未盘点
   字段。对策：迁移前 grep 垫片全部属性访问，逐一映射到 RunInfo 或 dict 返回。
5. **共存期并行冲突**（决策 8）：本 unit 跨 milestone 持续改 `agent/sdk/`、
   `agent/products/`、bootstrap。对策：实施期内本 unit 独占这些路径，orchestrator
   不并行派发触碰相同文件的其他 unit。

### 回退

- 三段式每个 commit 独立可 revert（决策 8）；阶段二任一消费方迁移失败，revert 该
  commit 即回旧表面，不影响已完成的其他迁移。
- 阶段三收缩 commit revert 即恢复全部旧导出 + 撤守卫，系统回到共存态。
- 无数据迁移、无配置文件格式变更（`~/.nano-assistant/config.yaml` 与 CLI 启动参数
  语义不变），回退不涉及用户侧操作。
- 回退不得恢复"产品直接 import 内核内部"（motivation 红线）——所有回退点都落在
  仍经 SDK 的状态上。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid` | `IM_JWT_SECRET=<unit随机串> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port $IM_PORT > .im.log 2>&1 & echo $! > .im.pid` | `curl -sf http://127.0.0.1:$IM_PORT/ >/dev/null` |
| Gateway | `stop_pidfile .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config $WT_CFG --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 node.register 成功 + IM 节点列表显示 online |
| Coding CLI | 非常驻，随用随起 | `PYTHONPATH=src python3 -m coding_cli.main` | REPL 可交互、`/model` 可切换 |

推荐直接 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh` 一键起停（自动分配端口、
worktree config 隔离、auto-bind）。reviewer 重点旅程：① CLI 带工具调用任务 +
`/model` 热切换；② IM 创建/编辑 Agent 时 models/skills/tools/features 与重构前
一致（含不同 workspace 的 skill 差异）；③ 既有会话收发消息 + 权限卡片。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-406-M1 | expand-and-cli | — | A | `src/agent/sdk/`（新增类型与 Kernel 方法，不删旧导出）、`src/agent/products/`（base/两产品 profile/prompt_sections/toolsets）、`src/agent/platform/bootstrap.py`、`src/agent/core/agent/prompt_sections/`（机制段迁入与统一 feature 表）、`src/coding_cli/`、相关单测 | `[reviewer]` CLI 全旅程行为不变：带工具调用任务、模型选择启动、`/model` 热切换、权限询问/中断（覆盖 Req-CLI 两 Scenario）；`[worker]` 决策 1-6 全部公共类型与 `kernel.list_*` 可用且有单测；`[worker]` 外部产品扩展路径有最小证明：测试内构造一个 agent 包外的产品定义（自带 tool / hook / custom_feature / prompt 槽），仅经 `agent.sdk` 装配 Kernel 并跑通一轮带工具调用的会话（覆盖 Req-新产品 两 Scenario）；`[worker]` PA/LC 经 ProductDefinition 装配的 system prompt 与现状黄金等价逐字节绿；`[worker]` coding_cli 仅 import 新表面符号；`[worker]` 旧导出原样保留，全测试树（`pytest -m "not e2e"` 全收集）绿 |
| refactor-406-M2 | gateway-and-contract | refactor-406-M1 | B | `src/personal_assistant/`（reporter/upstream_reporter.py、main.py、gateway/inbound_pipeline.py）、`src/agent/sdk/`（删除旧导出）、`tests/contract/`（新增表面守卫、更新既有契约测试）、capability payload 基线 fixture | `[reviewer]` IM 创建/编辑 Agent 时 models/skills/tools/features、默认模型与默认选中状态与重构前一致，含跨 workspace skill 差异（覆盖 Req-IM配置 三 Scenario）；`[reviewer]` 既有会话消息收发、权限卡、Gateway 启停与离线自治不变（覆盖 Req-PA/Req-Gateway 四 Scenario）；`[worker]` capability payload fixture 逐字段比对绿；`[worker]` 旧导出清零，决策 7 两道闸（精确名单 + 所有权来源）绿；`[worker]` Gateway 仅 import 新表面符号；`[worker]` 全测试树绿 |

```mermaid
graph LR
  M1[expand-and-cli] --> M2[gateway-and-contract]
```

拆分举证（§4.2 触发条件）：① 工作量——新类型体系 + feature 模型 + 模板装配 +
bootstrap 改造 + 两产品迁移 + 守卫，粗估 >1500 行、>20 文件，超单 worker 窗口；
② 分阶段验证——M2 录制 capability payload 基线要求 M1 产物已合入 unit 分支跑真。
两 milestone 均触碰 `agent/sdk/`，范围有交集，串行不并行。不拆三段的原因：纯
"扩张"milestone 的产物是无人消费的新表面，不满足退出标准试金石；收缩仅百行级，
并入 M2 收口。
