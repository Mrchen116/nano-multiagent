# feat-517: Python Dynamic Workflows

## Relations

- Related: feat-474

## 原始需求

> 假如我想变成python版的workflow，而不是js，能做不

> 好，现在我们落地这个工具到我们的系统中吧，Python版本

## 澄清记录

- Q1: Python Workflow v1 只在 `nanocode/coding_cli` 开放，还是同时开放到个人助手的 Web IM、飞书等入口？
  A(原话): 都支持
  Agent 解读: `coding_cli` 与个人助手的 Web IM、飞书等对话入口都应提供 Python Workflow 能力。
- Q2: 是否照 Claude Code 的来源识别、提示词约束与权限行为落地，同时为 PA 额外增加一道 Workflow 执行期资格校验？
  A(原话): 你不要做额外多余的一些你觉得有价值的设计，你就抄claude code就行了。
  Agent 解读: 除把脚本语言替换为 Python 外，按已取证的 Claude Code 行为复刻；不增加 Claude Code 没有的产品规则或防御机制。
- Q3: 完成口径是否包含 Claude Code 当前完整 Workflow 能力——生成与后台执行、`agent`/`parallel`/`pipeline`、保存与按名运行、进度查看、暂停/停止/恢复、权限继承、成本和规模提示？
  A(原话): 对。但是有一个考虑是，能不能在开这个工具的时候，包含对应的一些系统提示，但是不开这个工具的时候不包含。因为我的IM界面上是可以给agent选择工具的，这样我就可以有这个工具没这个工具做对比。
  Agent 解读: 完整能力都在范围内；Workflow 工具是否启用必须同时控制工具定义、Workflow 专属提示与相关入口，使 IM 中选择或取消该工具形成干净的有/无能力对照。
- Q4: IM 中取消 `Workflow` 工具时，是否将 Workflow tool schema/description、opt-in/ultracode reminder、专属运行指导、保存的 Workflow 命令和管理入口全部移除，并在重新勾选后的下一轮全部恢复？
  A(原话): 对

## 用户场景

一名开发者在 `coding_cli`，或在 Web IM / 飞书中使用自己的个人助手 Agent。对于普通任务，Agent 仍按原有单会话和 `agent` 工具能力工作；用户明确说“用 workflow”、输入 `ultracode`，或为当前会话开启 ultracode 模式后，Agent 才把大规模、多阶段工作组织成一个 Python Workflow。

Agent 先生成可检查的 Python 编排脚本。脚本负责循环、分支、并行、流水线、阶段和结果组合，实际读写文件、执行命令或访问外部工具仍由 Workflow 派生的子 Agent 完成。用户批准后，Workflow 在后台运行，当前会话保持可交互；中间结果留在 Workflow 内，用户通过进度视图看到阶段、Agent、用量和耗时，完成后只收到最终结果与诊断。

用户可以暂停、停止、恢复或重新运行 Workflow；已经完成且仍位于相同调用前缀中的 Agent 结果会被复用。一次满意的运行可以保存为项目或个人 Workflow，之后通过名称和参数再次运行。相同能力在 `coding_cli`、Web IM 和外部 IM 中都可到达，呈现形式可以适配各入口，但运行语义一致。

个人助手的 Agent 配置继续以现有工具选择为准。勾选 `Workflow` 后，下一轮同时获得 Workflow 工具及其专属 model-facing 指令和入口；取消后，下一轮不再看到该工具、提示、关键词触发、保存命令或管理入口。用户因此可以用同一个 Agent、同一个任务对比启用与禁用 Workflow 的行为，而不会让隐藏提示继续影响“无 Workflow”一侧。

本功能以本机已取证的 Claude Code 2.1.226 Dynamic Workflows 及实现期当前官方契约为行为基线。唯一主动改变是把 Workflow 脚本语言由 JavaScript 换成 Python；不因移植而额外发明激活、安全、调度、权限或产品规则。

## 验收标准

### Requirement: Workflow 在所有 Agent 产品入口可用且由工具选择完整开关

#### Scenario: coding CLI 启用 Workflow
- **GIVEN** `coding_cli` 当前会话启用了 Workflow 工具
- **WHEN** 用户明确要求以 Workflow 完成一个适合多 Agent 编排的任务
- **THEN** Agent 可以生成并发起 Python Workflow，并向用户展示其后台运行状态

#### Scenario: 个人助手勾选 Workflow
- **GIVEN** 用户在 IM 的 Agent 工具选择中勾选 `Workflow`
- **WHEN** 该 Agent 开始下一轮新回复
- **THEN** Web IM、飞书等该 Agent 可用的对话入口都能按相同语义发起和管理 Python Workflow

#### Scenario: 个人助手取消 Workflow
- **GIVEN** 用户在 IM 的 Agent 工具选择中取消 `Workflow`
- **WHEN** 该 Agent 开始下一轮新回复
- **THEN** Agent 不再提供 Workflow 工具、Workflow 专属提示、保存或管理入口，`ultracode` 也不再触发 Workflow
- **AND** 用户明确要求使用 Workflow 时，Agent 不会发起 Workflow 调用

#### Scenario: 运行中修改工具选择
- **GIVEN** 某轮已经按启动时配置开始执行
- **WHEN** 用户在 IM 中勾选或取消 `Workflow`
- **THEN** 正在执行的整轮保持其启动时能力，更新后的完整有/无 Workflow 配置从下一轮新回复生效

### Requirement: 默认模式只响应明确 opt-in，ultracode 模式允许 Agent 自主编排

#### Scenario: 人类输入使用 ultracode 关键词
- **WHEN** 用户在交互式终端、Web IM 或外部 IM 的亲自输入中写入 `ultracode`
- **THEN** 当前请求被视为一次 Workflow opt-in，Agent 使用 Workflow 组织该任务

#### Scenario: 人类用自然语言明确要求 Workflow
- **WHEN** 用户不用固定关键词、但用自己的话明确要求“使用 workflow”“并行编排多个 Agent”或运行指定 Workflow
- **THEN** Agent 把该请求视为显式 opt-in

#### Scenario: 普通任务不自动扩张
- **GIVEN** 当前会话未开启 ultracode 模式
- **WHEN** 用户提出一个可能受益于并行、但没有明确要求 Workflow 的任务
- **THEN** Agent 不调用 Workflow；可以继续使用普通能力，或先向用户说明规模和成本并征求同意

#### Scenario: 会话开启 ultracode 模式
- **GIVEN** 用户为当前会话开启 ultracode 模式
- **WHEN** 用户提出一个实质任务
- **THEN** Agent 自主判断并优先为任务编排一个或多个 Workflow，无需用户逐次重复 opt-in
- **AND** 用户关闭该模式或开始新会话后，恢复默认的逐次 opt-in 规则

#### Scenario: 非人工来源不因关键词自动激活
- **WHEN** `ultracode` 来自 heartbeat、cron、后台任务通知、webhook、非人工 SDK 输入或其他无人值守来源
- **THEN** 该关键词本身不构成 Workflow opt-in，也不会仅凭该文本自动启动 Workflow

### Requirement: Agent 生成和运行可检查、可编辑、可复用的 Python 编排脚本

#### Scenario: 从自然语言生成 Python Workflow
- **WHEN** 用户明确要求为任务创建 Workflow
- **THEN** Agent 生成的是 Python 编排脚本，而非 JavaScript/TypeScript，并在启动前向用户展示名称、说明和阶段计划

#### Scenario: 查看并修改生成脚本后重跑
- **GIVEN** 一次 Workflow 已生成脚本 artifact
- **WHEN** 用户查看、编辑该 Python 脚本并要求重新运行
- **THEN** 系统从编辑后的脚本启动新的运行，用户无需重新描述整套编排

#### Scenario: Python 脚本使用 Workflow primitives
- **WHEN** 用户运行一个使用 Agent 调用、并行、流水线、阶段、日志、参数、预算或嵌套 Workflow 的合法 Python 脚本
- **THEN** 这些能力按 Claude Code 对应 Workflow primitive 的语义执行，子 Agent 的最终文本或结构化结果成为脚本可组合的值

#### Scenario: 脚本试图直接取得系统能力
- **WHEN** Workflow 脚本尝试直接加载模块、访问文件系统、执行 shell 或取得未提供的系统能力
- **THEN** 运行在产生这些副作用前以可理解错误拒绝；用户被告知应把实际操作交给子 Agent

#### Scenario: 参数化运行
- **GIVEN** 一个保存的 Python Workflow 接受输入参数
- **WHEN** 用户按名称运行并提供列表、对象或文本参数
- **THEN** 脚本收到对应结构化值并据此执行，无需用户编辑脚本

### Requirement: Workflow 提供与 Claude Code 一致的确定性多 Agent 编排语义

#### Scenario: 并行汇合
- **WHEN** Python Workflow 用并行 primitive 同时派发多个独立 Agent
- **THEN** 用户在进度中看到它们并发推进，并在全部结束后得到保持输入位置对应关系的结果集合

#### Scenario: 按 item 流水执行
- **WHEN** Python Workflow 对多个 item 使用多阶段 pipeline
- **THEN** 每个 item 完成前一阶段后即可进入后一阶段，不必等待其他 item 的前一阶段全部结束

#### Scenario: 运行时分支和循环
- **WHEN** 一个 Workflow 根据前序 Agent 结果决定后续分支、循环次数或新任务集合
- **THEN** 后续 Agent 按 Python 脚本实际控制流被派发，用户得到该运行计算出的最终结果

#### Scenario: 单个 Agent 被停止或发生不可恢复错误
- **WHEN** Workflow 中一个 Agent 被用户停止或遇到重试后仍不可恢复的 API 错误
- **THEN** 该 Agent 产生与 Claude Code 一致的空结果语义，parallel/pipeline 的其他 item 可以继续完成

#### Scenario: 中间结果不淹没主会话
- **WHEN** Workflow 运行大量子 Agent 并产生中间结果
- **THEN** 主会话不逐条接收全部中间 transcript，只接收启动反馈、可按需查看的进度和最终结果通知

### Requirement: Workflow 后台运行且各入口均可查看和控制进度

#### Scenario: 启动后主会话保持可用
- **WHEN** 用户批准并启动 Workflow
- **THEN** 工具立即返回可识别的 task/run 信息，Workflow 在后台执行，用户可以继续使用当前会话

#### Scenario: 查看运行进度
- **GIVEN** 一个 Workflow 正在运行或已经结束
- **WHEN** 用户从 `coding_cli`、Web IM 或外部 IM 打开或请求 Workflow 状态
- **THEN** 用户能看到运行状态、阶段、Agent 数量及状态、token 用量和耗时，并能下钻查看 Agent 的任务与结果

#### Scenario: 暂停与继续
- **GIVEN** 一个 Workflow 正在运行
- **WHEN** 用户暂停后再继续
- **THEN** 运行停止派发新工作并可从可恢复边界继续，界面清楚显示状态变化

#### Scenario: 停止 Agent 或整个 Workflow
- **GIVEN** 一个 Workflow 正在运行
- **WHEN** 用户停止选中的 Agent 或整个 Workflow
- **THEN** 对应执行进入明确停止状态，其余是否继续遵循 Claude Code 的相同控制语义，用户不会看到任务仍被错误标为运行中

#### Scenario: Workflow 完成
- **WHEN** 后台 Workflow 成功、失败或被停止
- **THEN** 发起会话收到一次包含最终结果或错误、诊断、用量和恢复提示的完成通知

### Requirement: 暂停或修改后的 Workflow 按最长相同 Agent 调用前缀恢复

#### Scenario: 恢复未完成的运行
- **GIVEN** 一个 Workflow 在若干 Agent 已完成、后续 Agent 尚未完成时被暂停或停止
- **WHEN** 用户在同一会话恢复该运行
- **THEN** 最长连续已完成调用前缀的结果被直接复用，第一个未完成调用及其后的调用重新执行

#### Scenario: 修改后续 Agent 调用再恢复
- **GIVEN** 一个已运行 Workflow 的前若干 Agent 调用保持不变，之后的 prompt 或行为选项被修改
- **WHEN** 用户从原运行恢复编辑后的脚本
- **THEN** 修改点之前的最长相同调用前缀被复用，修改点及后续调用实时重跑

#### Scenario: 完全相同的脚本与参数重跑
- **GIVEN** 一个 Workflow 已完整结束
- **WHEN** 用户在同一会话以相同脚本和相同参数恢复
- **THEN** 所有仍符合前缀规则的 Agent 结果命中复用，并返回与原运行一致的 Workflow 结果

#### Scenario: 退出会话后重新启动
- **GIVEN** 用户退出了 Workflow 所属会话
- **WHEN** 在另一个新会话运行同一 Workflow
- **THEN** 新运行从头开始，不把跨会话复用冒充为同会话恢复

### Requirement: Workflow 可保存、发现、分发并按名称运行

#### Scenario: 保存为项目 Workflow
- **GIVEN** 用户完成了一次满意的 Workflow 运行
- **WHEN** 用户选择保存到项目范围
- **THEN** Python 脚本成为可随项目共享的命名 Workflow，并在后续会话的命令发现中出现

#### Scenario: 保存为个人 Workflow
- **WHEN** 用户把 Workflow 保存到个人范围
- **THEN** 它可在该用户的其他项目中按名称发现和运行，且不会自动成为项目共享文件

#### Scenario: 同名 Workflow 的发现优先级
- **GIVEN** 当前目录适用的项目 Workflow 与个人 Workflow 同名
- **WHEN** 用户按该名称运行
- **THEN** 使用距离当前工作目录最近的项目定义；没有项目定义时才使用个人定义

#### Scenario: 运行内置或插件 Workflow
- **GIVEN** 产品或已启用插件提供命名 Workflow
- **WHEN** 用户从命令入口显式调用并传入参数
- **THEN** 对应 Python Workflow 按其命名空间运行，并使用相同的审批、进度、权限和恢复能力

#### Scenario: Workflow 工具关闭时命名入口消失
- **GIVEN** 当前 Agent 未启用 `Workflow`
- **WHEN** 用户查看命令发现或尝试运行保存、内置、插件 Workflow
- **THEN** 相关命令不出现在可用入口中，也不会绕过工具选择启动运行

### Requirement: Workflow 启动与子 Agent 工具调用遵循 Claude Code 权限语义

#### Scenario: 默认交互权限下审批计划
- **GIVEN** 当前入口有人可交互确认，且未永久允许该 Workflow
- **WHEN** Agent 准备启动 Workflow
- **THEN** 用户先看到名称、阶段和用量提醒，并可选择本次允许、在适用范围内持续允许、查看原始 Python 脚本或拒绝

#### Scenario: ultracode 与非交互权限模式
- **WHEN** 会话已开启 ultracode，或入口处于 bypass、非交互 SDK 等 Claude Code 不展示 Workflow 启动确认的模式
- **THEN** Workflow 按该模式直接启动，不额外制造一个无法响应的确认步骤

#### Scenario: 子 Agent 继承工具范围
- **GIVEN** 发起会话具有一组允许工具
- **WHEN** Workflow 派生子 Agent
- **THEN** 子 Agent 继承该会话的工具 allowlist 和沙箱边界；Workflow 本身不能替子 Agent 扩大权限

#### Scenario: 子 Agent 使用未预先允许的能力
- **WHEN** Workflow 子 Agent 尝试使用未在 allowlist 中、且按当前权限模式需要确认的 shell、网络或外部工具
- **THEN** 调用遵循现有权限规则被询问、拒绝或按无人值守策略处理，不因来自 Workflow 而绕过

#### Scenario: 运行中不接受普通阶段签字
- **WHEN** 用户试图在同一个 Workflow 运行中插入普通对话作为阶段间输入
- **THEN** 运行不会把该消息当成脚本中途输入；需要人工签字的阶段通过拆分为多个 Workflow 完成

### Requirement: Workflow 对规模、成本和模型路由提供与 Claude Code 一致的反馈与限制

#### Scenario: 查看实时成本
- **WHEN** Workflow 正在运行
- **THEN** 用户可以按运行、阶段和 Agent 查看 token 用量与耗时，并可据此停止运行

#### Scenario: 大型 Workflow 警告
- **WHEN** Workflow 计划超过 Claude Code 对应的大型运行阈值
- **THEN** 用户看到 `Large workflow` 级别的规模/预计 token 警告和停止入口；警告本身不擅自暂停已获准运行

#### Scenario: 调整规模 guideline
- **WHEN** 用户选择 `small`、`medium`、`large` 或 `unrestricted` 规模 guideline
- **THEN** Agent 生成 Workflow 时按 Claude Code 对应目标规模规划，并在运行反馈中显示当前 guideline

#### Scenario: 达到运行时上限
- **WHEN** Workflow 触及 Claude Code 对应的并发 Agent、总 Agent 数或单次组合 item 上限
- **THEN** 超出并发槽位的工作排队，超出硬上限的请求以明确错误停止扩张，不静默丢弃 item

#### Scenario: 模型与 effort 路由
- **GIVEN** Workflow 脚本没有指定子 Agent 模型或 effort
- **WHEN** 它派生 Agent
- **THEN** 子 Agent 继承当前运行的模型和 effort；脚本或现有环境配置的显式覆盖按 Claude Code 相同优先级生效，并在发生模型替换时向用户告警

### Requirement: Workflow 错误可定位且不破坏主会话

#### Scenario: Python 脚本不合法
- **WHEN** 生成、保存或编辑后的 Python Workflow 存在语法、metadata 或受限能力错误
- **THEN** 用户在后台运行启动前收到可定位的错误，主会话继续可用

#### Scenario: 后台运行失败
- **WHEN** Workflow runtime 或其子 Agent 出现不可恢复失败
- **THEN** 运行进入明确失败状态，完成通知和进度详情保留错误位置、已有结果与诊断入口

#### Scenario: 用户查看历史运行诊断
- **GIVEN** 一个 Workflow 返回空结果、意外结果或曾被停止
- **WHEN** 用户打开运行详情或要求 Agent 诊断
- **THEN** 用户可以定位到已持久化的脚本、运行状态、Agent 调用记录和实际返回值，而不必依赖主会话记住全部中间输出

## 范围与非目标

- 在范围：`coding_cli`、Web IM 与外部 IM 的 Python Dynamic Workflows；与 Claude Code 2.1.226/当前官方契约一致的激活、生成、运行、编排、后台状态、通知、权限、保存、命名调用、暂停/停止/恢复、诊断、规模、成本与模型路由行为；IM 工具选择对全部 Workflow model-facing 内容和入口的完整开关。
- 非目标：兼容或执行 JavaScript/TypeScript Workflow；把 Workflow 扩展成 Claude Code 没有的自动激活、额外资格校验或权限体系；复刻未被公开或取证、且不影响上述用户行为的 vendor 内部实现细节；把 Claude Code cloud routines、通用 hooks 或 agent teams 当作 Dynamic Workflows 一并实现。
