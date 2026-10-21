# gateway Agent Capabilities Specification (delta for feat-627)

## ADDED Requirements

### Requirement: 所有 Agent 默认使用无摘要换窗并支持显式回退

#### Scenario: 新建与既有 Agent 默认生效
- **WHEN** 新建或升级前已存在的普通、Global、Personal 或子 Agent 开始工作，用户未显式停用该能力
- **THEN** 默认使用无摘要换窗及配套恢复工具，无需逐 workspace 安装或修改业务工具 allowlist
- **AND** 不扩大业务操作权限

#### Scenario: 用户显式停用后重启
- **GIVEN** 用户通过现有 workspace 插件入口停用了该能力
- **WHEN** 节点重启或该 workspace 创建新 Agent
- **THEN** 保持停用并使用原摘要压缩，直至用户重新启用；其他 workspace 的选择不改变

### Requirement: 无摘要换窗的 workspace 支持持续任务与按需恢复

#### Scenario: 多次换窗后继续任务
- **GIVEN** 用户在已启用该能力的 workspace 提供了目标、限制并在后续纠正过要求
- **WHEN** 同一个未完成任务经历多次上下文换窗
- **THEN** Agent 能利用已保存记录与原始历史继续工作，按最新有效要求交付，不要求用户重复提供仍可恢复的信息
- **AND** 不因换窗重复已经完成的外部副作用，不把未完成事项报告为完成

#### Scenario: 恢复原始细节或说明缺口
- **WHEN** 换窗后的任务需要早先消息或较长工具结果中的细节
- **THEN** Agent 可以按需恢复已离开活动上下文的原始记录及来源，并据此继续工作
- **AND** 缺失记录时如实说明具体缺口，不编造已经恢复的信息

### Requirement: 换窗记录在同一会话重启后保留且不扩大访问授权

#### Scenario: 正常重启与重新启用
- **GIVEN** 当前会话已保存工作记录
- **WHEN** 节点正常重启，或能力停用后重新启用
- **THEN** 同一会话可继续访问其已保存记录；停用不删除记录，停用期间的未来工作恢复原摘要压缩行为，重新启用后使用该换窗能力

#### Scenario: 请求其他归属的记录
- **WHEN** 当前任务尝试读取既有权限之外的其他 Agent 或 workspace 记录
- **THEN** 不获得记录，恢复出的内容也不形成新的外部操作授权

## MODIFIED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

本条的静态工具选择规则适用于 `single_thread`。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用机制即撤销其注册。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

任务图特性被显式关闭时，`task_graph` 从该 Agent 的有效工具集排除；这一有限例外及预览、下一轮生效规则见 [任务图规范](../../../../specs/gateway/task-graphs.md)。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述四个上下文内部工具和 workspace 自建工具的有限增量外，非空时 Agent 静态业务工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按机制启停，预览、下发和实际执行保持一致。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单拒绝业务工具但保留上下文内部操作
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用业务工具
- **THEN** 业务工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈
- **AND** 已启用的上下文机制仍可调用四个内部工具；停用后它们也不可调用

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除四个上下文内部工具外，仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="schedule_create"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `schedule_create`；其他原生 `schedule_*` 工具仍需在有效白名单内。停用 Cron 能力后，其调度工具不再可调用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true


#### Scenario: Auto 关闭不阻断会话内部上下文管理
- **GIVEN** 当前 Agent 启用了默认上下文机制，自动审批关闭
- **WHEN** 普通、Global、Personal 或子 Agent 保存笔记、恢复历史、查询预算或请求换窗
- **THEN** 仅作用当前执行会话的四工具无需额外审批即可执行，明确的底层拒绝仍保留
- **AND** 其他业务工具继续遵守原审批、选择与发送重验规则；恢复内容不生成新的授权
