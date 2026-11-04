# gateway agent-capabilities Specification (delta for feat-705)

> 目标：`docs/specs/gateway/agent-capabilities.md`。

## ADDED Requirements

### Requirement: Global 的一级执行者获得独立工作能力，二级沿用原生子 agent

#### Scenario: 主会话工具选择不缩减完整事项执行能力
- **GIVEN** Global／PA 主会话的工具选择满足其日常和协调需要
- **WHEN** 主会话把完整事项交给一级 subagent
- **THEN** 一级以 DSH 默认工作能力为基础执行，可使用原生 fork、子 agent 及内部通信，不因主会话未勾选普通工作工具而失去这些能力。
- **AND** 主会话自身仍按其有效选择执行；一级工作能力不反向开启主会话未选择的工具，也不恢复运行时未装载的能力。

#### Scenario: 二级无额外产品身份
- **WHEN** 一级创建普通二级 subagent
- **THEN** 二级使用 DSH 原生子 agent 上下文与父级交办的子目标，不额外注入 Nano 身份或完整事项负责者职责，不自动复制父级历史。
- **AND** fork 继续使用原生父上下文继承，不因该规则裁改其前缀；各级来源、审批、深度、workspace 与宿主产品权限限制仍有效，用户沟通逐级经过 Global。

#### Scenario: 更新与恢复保持角色边界
- **WHEN** 修改主会话工具选择，或恢复已有一级／二级会话
- **THEN** 按该层职责恢复实际工作能力与上下文，原执行者身份和已有工作保留；主会话 fork 开关不撤销一级的原生 fork 能力。
- **AND** 共享 Feature、Skill 与扩展的选择、撤回和权限继续生效；不将其他特定范围的子任务自动升级为完整工作执行者。

#### Scenario: 按消费者角色加载指导
- **WHEN** 装配普通 Global、PA 及其内部执行者的模型请求
- **THEN** 主人身份、participant／observer 和代表主人等 PA 专属说明只给 PA 根或适用的 PA 一级；普通 Global 及其一级不携带它们，普通二级继续不注入 Nano 指导。
- **AND** 普通 Global 的 Inbox 只声明 check／read；review 和 message_id 仅声明给主 PA，实际权限检查仍由宿主执行。通用 pa_agent_id 来源归属仍适用于与 PA 的平等协作。
- **AND** 一级只获得委派来源的最小授权边界和准备交互产物后回传父级的说明，不复制主会话的 Inbox／聊天交互操作流程；详细 UI 用法按需加载。Heartbeat 协议仅由已启用 Feature 向主会话提供，不进入内部执行者。 历史恢复不产生新授权的通用提醒由上下文组件在换窗时提供，主会话和一级不重复常驻注入。 Cron 也不追加通用的定时授权／交付常驻段，沿用原生提醒与各 Schedule 工具的操作说明。 Skill 常驻仅提示修正已验证错漏、提议保存可靠可复用方法及不固化一次性细节／临时故障／未验证变通方案；编写细则按需加载 skill-creator。

### Requirement: 主会话 fork 默认关闭，可按现有工具规则开启

#### Scenario: 新建和无显式工具选择
- **WHEN** 新建 Global、PA 或 SingleThread 主 Agent，或主会话配置没有显式工具名单
- **THEN** subagent_fork 默认不启用，仍可在现有工具目录发现并选择；普通 subagent 和 Global 固定基础能力不因此关闭。
- **AND** 此主会话默认值不套用到 Global／PA 一级执行者的 DSH 工作工具。

#### Scenario: 显式选择与撤回
- **WHEN** 用户选中或取消主会话 fork 并保存
- **THEN** 采用现有工具配置及生效规则，模型可调用能力和预览与有效设置一致；开启只增加原生工具，不增加专门身份提示、清理流程或新开关。
- **AND** Goal 三工具仍各自选择、默认关闭，不因启用 fork 而启用 Goal 或注入 Goal 专属指导。

#### Scenario: 保留已有选择
- **WHEN** 已保存工具名单的 Agent 升级或恢复
- **THEN** 名单保持，显式启用的 fork 仍可用，不按新默认值覆盖已有选择；原生返回和继承语义保持。


### Requirement: exit_plan_mode 默认关闭并保留显式选择

#### Scenario: 新建、未配置与手动选择
- **WHEN** 新建 Global、PA 或 SingleThread 主 Agent，或配置没有显式工具名单
- **THEN** `exit_plan_mode` 默认不启用，仍在现有工具目录可手动选择；默认值、能力预览、实际下发和执行限制一致。
- **AND** 手动开启或关闭沿用现有工具规则，不增加 Plan 模式入口、额外提示词或委派职责；内部执行者原有用户交互工具限制不变。

#### Scenario: 已有显式选择不改写
- **WHEN** 加载、更新或恢复已有显式工具名单
- **THEN** 保留其 `exit_plan_mode` 选择；新默认值不覆盖已保存的开启或关闭，不迁移历史配置。

## MODIFIED Requirements

### Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖

本条的静态工具选择规则适用于 `single_thread` 及 Global／PA 主会话的可配置工具；Global／PA 普通内部执行者遵循本 area 的分层工作能力条目，不套用主会话的普通工具名单。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用机制即撤销其注册。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为上述主会话构建可配置工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述四个上下文内部工具和 workspace 自建工具的有限增量外，非空时 Agent 静态业务工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按机制启停，预览、下发和实际执行保持一致。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的合法 `tool_allowlist` 被设为不含某默认工具的非空显式集，且没有开启的 Feature 需要该工具
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单拒绝业务工具但保留上下文内部操作
- **GIVEN** single_thread Agent 的 `tool_allowlist` 显式为空，所有依赖业务工具的 Feature 均关闭
- **WHEN** 用户与该 Agent 会话，模型尝试调用业务工具
- **THEN** 业务工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈
- **AND** 已启用的上下文机制仍可调用四个内部工具；停用后它们也不可调用

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** single_thread PA agent 已持久化合法非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除四个上下文内部工具外，仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 Cron Feature 并已将其全部依赖工具保存到 `tool_allowlist`
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 schedule_create/list/update/delete/run/history 六项；合法关闭 Cron 后按最终工具选择提供，用户单独重新启用的工具不因 Feature 关闭而拒用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true


#### Scenario: Auto 关闭不阻断会话内部上下文管理
- **GIVEN** 当前 Agent 启用了默认上下文机制，自动审批关闭
- **WHEN** 普通、Global、Personal 或子 Agent 保存笔记、恢复历史、查询预算或请求换窗
- **THEN** 仅作用当前执行会话的四工具无需额外审批即可执行，明确的底层拒绝仍保留
- **AND** 其他业务工具继续遵守原审批、选择与发送重验规则；恢复内容不生成新的授权

### Requirement: 子执行上下文服从原生执行方式

#### Scenario: 普通子 Agent
- **WHEN** Global、PA 或 SingleThread 的普通内部子执行接到委派
- **THEN** Global／PA 一级采用 DSH 工作基础上下文与完整事项职责；其普通二级只采用 DSH 原生子 agent 上下文和父级子任务，不注入额外 Nano 身份或一级职责。
- **AND** SingleThread 普通子执行保留明确内部身份与可调用工具；普通子会话均不复制父 Persona 的公开交付职责，产品权限按真实身份在宿主执行。

#### Scenario: fork 子 Agent
- **WHEN** fork 子执行开始或恢复
- **THEN** 系统提示与工具定义保持实际父级的有效工作配置一致，在历史后追加任务/回传边界，继承前缀保持可复用；父级可以是主会话或一级执行者，不能把一级 fork 重新解释为根职责。
- **AND** 宿主权限验证不因工具可见而放宽，原生深度与返回语义保持。
