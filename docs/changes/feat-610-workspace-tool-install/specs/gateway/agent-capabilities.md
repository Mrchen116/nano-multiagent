## MODIFIED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

本条的静态工具选择规则适用于 `single_thread`。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大静态默认工具、显式空集或子任务限制。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

任务图特性被显式关闭时，`task_graph` 从该 Agent 的有效工具集排除；这一有限例外及预览、下一轮生效规则见 [任务图规范](../../../../specs/gateway/task-graphs.md)。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述 workspace 自建工具的有限增量外，非空时 Agent 静态工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单的 Agent 会话拒绝一切工具调用
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用工具
- **THEN** 工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态工具只启用该白名单列出的工具；仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="schedule_create"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `schedule_create`；其他原生 `schedule_*` 工具仍需在有效白名单内。停用 Cron 能力后，其调度工具不再可调用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true


## ADDED Requirements

### Requirement: Agent 可在 workspace 自助安装原生工具

Agent 启用 `plugin_manager` 后，可以在可信配置确定的 workspace 创建标准 DSH bundle，安装、启用、停用和移除。新增且不与既有工具名冲突的 workspace 工具自动并入该 Agent 的有效集合，不要求人工修改白名单。静态工具选择和禁用保持；关闭管理能力或显式空工具集不自动获得这些工具。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

#### Scenario: 安装后既有聊天立即使用
- **WHEN** Agent 成功安装并启用 workspace 工具
- **THEN** 同 workspace 既有及新聊天可使用它，不需重启；其他 workspace 不可发现或执行

#### Scenario: 失败不声称已启用
- **WHEN** 包安装或实际加载失败
- **THEN** Agent 收到失败状态和真实诊断；包管理成功不代替执行可用证据

#### Scenario: 重启和撤销
- **WHEN** 节点重启或 Agent 停用/移除已安装 bundle
- **THEN** 重启保留持久选择，停用/移除后后续调用不可执行对应工具

#### Scenario: 保留其他工具选择
- **GIVEN** 已有禁用工具或显式空集
- **WHEN** 该 workspace 安装新增工具
- **THEN** 既有禁用选择不改变，空集不自动扩宽
