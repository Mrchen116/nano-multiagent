# Kernel SDK boundary delta — refactor-479

> 本 delta 对 `docs/specs/kernel/sdk-boundary.md` 的 build-time extension contract 做修改。
> unit 收尾时按最终实现更新精确 allowlist 并归并 canonical。

## MODIFIED Requirements

### Requirement: 内核对外只经 agent.sdk 暴露，产品不得依赖内核内部

`agent.sdk` 是内核唯一对外面。消费者只能 import `agent.sdk`；内核内部层
(`agent.core` / `agent.platform`)不得被产品直接 import，`agent.sdk` 也不得反向依赖任何
产品包。公开符号是由 contract test 逐字守卫的精确允许名单；除显式豁免外，每个导出对象
由 `agent.sdk` 自身拥有。

本 unit 在既有允许名单上新增四个 SDK-owned 类型：
`SkillReviewEvidence`、`SkillReviewRequest`、`SkillReviewSelection`、
`SkillReviewPolicy`。前三者是 policy 接收/返回的 frozen DTO，后者是产品实现的 Protocol；
除此之外，本 unit 不扩大 SDK 公开类型表面。

#### Scenario: 产品越界 import 内核内部被拦
- **GIVEN** coding_cli 或 personal_assistant 的某文件
- **WHEN** 它 import `agent.core` / `agent.platform` / `agent.products`
- **THEN** SDK boundary contract 失败

#### Scenario: agent.sdk 不上行依赖产品
- **WHEN** 审阅 `agent.sdk` 下任一 import
- **THEN** 不存在对 coding_cli / personal_assistant / IM 的 import

#### Scenario: core 不依赖 platform 或产品
- **WHEN** 审阅 `agent.core`
- **THEN** 不存在对 `agent.platform`、产品包或 web framework 的 import

#### Scenario: Skill review policy 类型由 SDK 拥有
- **WHEN** 产品实现 `SkillReviewPolicy` 并处理 request/selection
- **THEN** 四个边界类型的 `__module__` 属于 `agent.sdk`
- **AND** 产品只需依赖这四个 SDK 类型即可实现 policy

#### Scenario: 新增或缺失导出被精确 allowlist 拦截
- **WHEN** `agent.sdk.__all__` 多出未批准名字，或缺少既有名字/本 unit 四个新增名字之一
- **THEN** 表面守卫 contract 失败

#### Scenario: 内核拥有的既有豁免仍逐字受控
- **WHEN** 导出属于既有显式豁免
  (`RunOrigin` / `PermissionDecision` / `TERMINAL_RUN_STATUSES` /
  `ToolPresenter` / `ToolPresentationEvent`)
- **THEN** ownership 守卫放行，且豁免名单本身增删仍失败

#### Scenario: sdk-owned typing alias 不计入豁免
- **WHEN** 导出为 `CanUseToolFn` 或本 unit 的 SDK-owned Protocol
- **THEN** 由 SDK ownership 规则放行，不加入 core/platform 豁免名单

### Requirement: 装配与会话分两层，内核产品中立

`agent.sdk` 不提供产品对象或产品路径常量。装配仍分两层：

- `build_kernel(llm, tools, hooks, can_use_tool=None,
  workspace_config_dirname=…, repo_root=None, skill_search_roots=(),
  global_skill_root=None, tool_search_roots=(), hook_search_roots=(),
  skill_review_policy=None)` 建一次进程级共享基座。`skill_review_policy` 为可选的
  SDK-owned build-time extension：`None` 表示该 Kernel 不产生自动 skill batch review
  副作用；提供 policy 时，返回的 Kernel 已可在达到既有阈值后发起自动复盘，产品不再在
  Kernel 返回后安装 review scheduler/drain。
- `create_session(workspace_root, enabled_tools, features, prompt, title=…, metadata=…)`
  仍负责 per-agent 会话配置；skill review policy 不是 per-session metadata，也不能被
  caller metadata 替换。

policy 的消费者表面为：

- `SkillReviewEvidence(session_id, transcript_path)`；
- `SkillReviewRequest(skill_name, skill_root, skill_location, evidence)`；
- `SkillReviewSelection(analysis_workspace_root, target_skill_root, writable, reason=None)`；
- `SkillReviewPolicy.resolve(request) -> SkillReviewSelection | None`。

policy 只提供产品 workspace/root 事实，不负责运行复盘。`target_skill_root` 必须与 request 的
`skill_root` 完全相等；`writable=False` / `None` / root mismatch 都表示本轮不修改并且不得
回退到其他同名 root。`resolve` 是同步调用，消费者实现必须快速、线程安全，且不能依赖调用方
event loop。该扩展不新增 product-facing `Kernel.configure_*` / `run_queued_*` 方法。

#### Scenario: 应用零前置调用直接装配
- **GIVEN** 应用构造 LLMConfig、工具、hooks，以及可选 SkillReviewPolicy
- **WHEN** 直接调用 `build_kernel`
- **THEN** 模型目录正常装配，返回的 Kernel 可立即创建会话
- **AND** 不需要后置注册表、review scheduler 或 drain 调用

#### Scenario: 三类应用对内核同构
- **GIVEN** coding_cli、personal_assistant、任意外部应用
- **WHEN** 各自用同一 build/create-session 表面装配
- **THEN** 内核不含产品分支；产品差异只存在于传入对象与 policy 实现

#### Scenario: 工具目录共享、会话选择子集
- **WHEN** build catalog 含 A/B/C，而会话 enabled_tools 只选 A/B
- **THEN** 会话只暴露 A/B，工具实例仍只在共享基座注册一次

#### Scenario: 首次越过阈值无需后置配置
- **GIVEN** build_kernel 传入 SkillReviewPolicy
- **WHEN** Kernel 返回后第一条会话立即由 skill_view 越过 threshold
- **THEN** 本次 skill_view 正常返回且不等待复盘结果
- **AND** policy 收到对应 SkillReviewRequest，应用无需先调用 configure/scheduler/drain

#### Scenario: product policy 不能把 target 重定向到同名 root
- **GIVEN** request owning root 为 R1，policy 错误返回 target R2
- **WHEN** 该 selection 对应的自动复盘被处理
- **THEN** 本轮复盘跳过，R1/R2 的目标 skill 内容与 reviewed 标记均不因本轮改变
- **AND** 不回退到 R1 或其他同名 root 执行修改

#### Scenario: read-only selection 不回退到可写同名 root
- **GIVEN** policy 对 compat root 返回 `writable=False`
- **WHEN** 对应 skill 越过自动复盘阈值
- **THEN** 该 root 的 skill 内容与 reviewed 标记不变
- **AND** workspace/global 中的同名 skill 也不被读取、修改或标记

#### Scenario: 未提供 policy 时无自动复盘副作用
- **WHEN** 外部应用以 `skill_review_policy=None` 构造 Kernel
- **THEN** 普通会话、skill_view 返回与使用统计仍可用，但达到阈值不产生自动复盘修改或
  reviewed 标记

#### Scenario: Kernel 稳定方法集不因本 unit扩张
- **GIVEN** 已装配 Kernel
- **THEN** 既有会话、run、能力查询、prompt preview 与 close 方法集保持
- **AND** 不新增 product-facing configure/drain/scheduler 方法
