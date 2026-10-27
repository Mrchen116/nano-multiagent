# Kernel SDK boundary delta — refactor-476

> 本 delta 完整替换 `docs/specs/kernel/sdk-boundary.md` 的两条 MODIFIED Requirement。
> canonical 原正文与全部 Scenario 均保留，只增加 SDK-owned permission interaction
> 类型、build-time 参数与 per-Kernel permission/run 资源关闭隔离，并保留 model registry
> 的进程级共享边界。unit 收尾时按最终实现归并。

## MODIFIED Requirements

### Requirement: 内核对外只经 agent.sdk 暴露,产品不得依赖内核内部

`agent.sdk` 是内核唯一对外面。消费者只能 import `agent.sdk`;内核内部层(`agent.core` /
`agent.platform`)不得被产品直接 import,`agent.sdk` 也不得反向依赖任何产品包。`agent.sdk` 的公开
符号是一份**精确允许名单**(逐字钉死,见归档 design 接口总表),由表面守卫 contract 测试守卫:多导出
或少导出都失败。除显式豁免外,每个导出对象的类型须由 `agent.sdk` 自身拥有(SDK-owned),不得是
内核内部模块拥有的对象直接外泄。

本 unit 在既有允许名单上新增两个 SDK-owned 类型：
`PermissionInteraction` 与 `PermissionInteractionPort`。platform 内部的 transaction record、
terminal signal、local handle、broker response、supervisor 与 task registry 均不导出。

既有 `CanUseToolFn` 仍是 SDK-owned 三参数 callable alias：

```python
CanUseToolFn = Callable[
    [str, Any, Any],
    Awaitable[PermissionDecision],
]
```

第三个参数继续是未经替换或包裹的原始 permission request。

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

#### Scenario: 新 interaction 类型由 SDK 拥有
- **WHEN** 检查 `PermissionInteraction` 与 `PermissionInteractionPort`
- **THEN** 两者的 owner module 属于 `agent.sdk`
- **AND** 产品无需 import core/platform 才能实现 port

#### Scenario: 新 permission 导出同样受精确名单守卫
- **WHEN** `agent.sdk.__all__` 缺少 `PermissionInteraction` /
  `PermissionInteractionPort`，或额外暴露任一 internal permission transaction 类型
- **THEN** 表面或所有权守卫 contract 测试失败

#### Scenario: 既有 callback 签名和 request identity 保持
- **GIVEN** 外部应用已有三参数 `CanUseToolFn`
- **WHEN** 它以原有 `build_kernel(can_use_tool=callback)` 装配
- **THEN** callback 仍收到 `(tool_name, tool_input, raw_request)`
- **AND** `raw_request` identity 与权限事务收到的原始 request 相同

### Requirement: 装配与会话分两层,内核产品中立

`agent.sdk` 不提供"产品"对象(无 `ProductProfile` / `ProductDefinition` / 内置产品常量)。装配分两层,
内核对三类应用(coding_cli / personal_assistant / 任意外部应用)无差别对待,无任何"一方产品"分支:

- `build_kernel(llm, tools, hooks, can_use_tool=None, permission_interaction_port=None,
  workspace_config_dirname=…, repo_root=None, skill_search_roots=(), tool_search_roots=(),
  hook_search_roots=())` —— 建一次进程级**共享基座**:
  `llm` 为 SDK-owned `LLMConfig`(providers/models 目录 + 连接 + 默认);`tools` 为原生工具对象**目录**;
  `hooks` 为 `setup(hooks: HookAPI)` 形态 callable;`skill_search_roots` / `tool_search_roots` /
  `hook_search_roots` 为部署级用户插件目录(消费者显式传入的根,非 ConfigResolver),内核在工作区
  `<repo_root>/.nano/{tools,hooks,skills}` 运行时发现之外额外发现这些目录,空 → 仅工作区。模型注册表
  初始化在内部,消费者无前置时序义务;装配完成后所有会话/运行均在进程内执行(无子进程、无 loopback HTTP)。
  `permission_interaction_port` 是可选的 SDK-owned 本地权限交互扩展，与既有
  `can_use_tool` 互斥；两者均为空时保持 Gateway/IM remote-only 权限流程。
  每次调用产生的 Kernel 分别拥有自己的 run、permission、local-task、executor 与 finalizer
  资源图；关闭其中一个不得 seal/cancel/drain 另一个的这些 owned resources。模型目录仍是进程级
  共享基座；本 Requirement 不承诺不同 `LLMConfig` / model catalog 的多个 Kernel 可独立并行提交。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)` —— 每 agent
  带齐配置:`enabled_tools` 从工具目录选子集;`features` 开关内核通用 feature;`prompt` 为 SDK-owned
  `PromptSlots`。不收 `model`——model 是 per-run 的,消费者每轮经 `submit(model=...)` 提供。

本地扩展的消费者表面为：

```python
class PermissionInteraction:
    request_id: str

    @property
    def cancelled(self) -> bool: ...

    async def wait_cancelled(self) -> None: ...


class PermissionInteractionPort(Protocol):
    async def decide(
        self,
        tool_name: str,
        tool_input: Any,
        request: Any,
        interaction: PermissionInteraction,
    ) -> PermissionDecision: ...
```

`wait_cancelled()` 可从任意 asyncio loop 等待同一 loop-neutral cancellation signal。
port 的 `decide()` 返回、抛错或完成取消清理时，由 SDK adapter 自动确认本地 interaction
已退出；consumer 没有额外 ack API。

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
  `discard_run_messages`,非阻塞方法 `submit` / `try_steer` / `stream` / `interrupt` / `cancel` /
  `get_run` / `list_session_tools` /
  `get_llm_config`,中立能力查询 `list_models` / `list_tools` / `list_features` /
  `list_skills`,以及 prompt 预览 `assemble_prompt_preview`;并同时暴露供异步消费者使用的 `aclose()`
  与同步兼容的 `close()`

#### Scenario: 旧 callback 无迁移成本
- **GIVEN** 任意外部应用只提供既有 `CanUseToolFn`
- **WHEN** 本地决定、外部决定或 run cancel 任一先发生
- **THEN** callback 的参数和决定语义不变
- **AND** callback 不需要实现 `PermissionInteractionPort` 或退出 ack

#### Scenario: 新 port 跨 loop 接收取消
- **GIVEN** port coroutine 与触发 cancel 的 caller 位于不同 event loop/thread
- **WHEN** broker settlement 取消本地 interaction
- **THEN** `interaction.cancelled` 变为 true
- **AND** `await interaction.wait_cancelled()` 在 port 使用的当前 loop 正常完成
- **AND** 不共享 loop-bound asyncio primitive

#### Scenario: 两个本地 owner 被拒绝
- **WHEN** 同时传入 `can_use_tool` 与 `permission_interaction_port`
- **THEN** `build_kernel` 在启动任何 runtime/task 前抛出 `ValueError`

#### Scenario: remote-only 装配保持
- **WHEN** 两个本地 permission 参数均为空
- **THEN** request 仍经既有 session events 交给 Gateway/IM
- **AND** `submit_permission_decision()` 仍以 first-wins bool 结果解决请求

#### Scenario: 多个 Kernel 的 owned 关闭资源相互隔离
- **GIVEN** 消费者以兼容的进程级 model catalog 分别调用两次 `build_kernel()` 得到 K1 与 K2，
  且两者各有待决权限请求
- **WHEN** K1 进入权限等待并被关闭
- **THEN** K2 的 run、permission、local task、executor 与 finalizer 不被 K1 的关闭取消或停止
- **AND** K2 的待决权限可继续解决，且 K2 只在消费者关闭 K2 时才进入关闭状态
