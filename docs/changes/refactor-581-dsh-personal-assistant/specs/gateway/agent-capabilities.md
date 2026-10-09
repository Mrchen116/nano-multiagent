# gateway/agent-capabilities Specification (delta for refactor-581)

## ADDED Requirements

### Requirement: 可替代能力采用原生工具名称与用法并允许受控升级

#### Scenario: 使用通用工具
- **WHEN** 助手使用已由DSH提供的等价工具或Skill调用入口
- **THEN** 使用其原生名称、参数及命令方式；迁移后的既有Skill仍能完成工作，不依赖旧名字或旧schema兼容层。

#### Scenario: 截断读取与后台输出
- **WHEN** 文件超过单次读取范围，或后台工具完成
- **THEN** 截断明确可继续读取；助手通过原生输出工具读取后台结果后正常向用户交付，不要求用户手动操作内部工具。

#### Scenario: 升级上游工具
- **WHEN** 维护者升级受支持的DSH版本并完成产品接入验证
- **THEN** 可使用更新后的原生工具能力；身份、权限、Skill引用及结果交付仍有效，不被复制的旧实现固定住。

### Requirement: 自建工具支持节点全局与workspace两层

#### Scenario: 共享、局部及同名覆盖
- **GIVEN** 本节点owner共享工具和workspace A的同名工具，另有workspace B
- **WHEN** A或B的主会话及被允许的子任务使用工具
- **THEN** A优先使用局部版本，B使用共享版本；A的私有工具不出现在B，工具名单继续限制可用能力。

#### Scenario: 重启和同workspace多会话
- **WHEN** 同一workspace建立多个会话或服务重启
- **THEN** 按该workspace的同一份持久扩展声明装配，局部工具不因为包已安装而自动全局启用。

### Requirement: Auto默认沿用Nano规则且可配置为DSH规则

#### Scenario: 默认审核规则
- **WHEN** 用户未选择其他Auto规则
- **THEN** 工具权限审核沿用Nano当前判定规则，保留可信来源、短确认、拒绝计数、人工审批和无人值守分流。

#### Scenario: 配置切换规则
- **WHEN** 运维者选择DSH默认规则并重启节点完成生效
- **THEN** 后续工具权限判定使用DSH规则；独立审核模型选择仍按既有契约，不能改用另一条并行审批链或绕开产品来源规则。
- **AND** 配置生效前已发出的审批仍对应原请求，迟答不复活取消调用。

#### Scenario: 规则切换不改变审核模型失败处理
- **GIVEN** 节点配置了独立审核模型
- **WHEN** 该模型在已有重试后仍失败或无有效判定
- **THEN** 不自动换回执行Agent模型复审；有人值守/无人值守分别走既有分流。

### Requirement: Feature可独立启停并撤销其后续影响

#### Scenario: 关闭和重新开启单项能力
- **WHEN** 用户对某Agent关闭再开启Task Graphs、Memory Curation、Skill Creation、Cron或Heartbeat
- **THEN** 该Feature的工具、提示、命令和未来触发按有效配置撤销或恢复，其他Feature及其他Agent不受影响；重新开启不累积重复监听或任务。
- **AND** 已有任务/记忆/Skill保留，Skill Creation关闭不等于禁用已有Skill加载。

#### Scenario: 关闭期间重启与在途工作
- **WHEN** 关闭的Feature经历节点重启，或关闭时已有工作被接收
- **THEN** 重启不擅自重新启用；在途工作依原产品契约收口；未完成卸载显示pending，不伪报effective或回滚已发生副作用。

## MODIFIED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

本条以下恰等于配置白名单、显式空集和不自动扩宽的规则及 Scenario 适用于 `single_thread`。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

任务图特性被显式关闭时，`task_graph` 从该 Agent 的有效工具集排除；这一有限例外及预览、下一轮生效规则见 [任务图规范](../../../../../docs/specs/gateway/task-graphs.md)。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时 Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

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
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="schedule_create"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `schedule_create`；其他原生 `schedule_*` 工具仍需在有效白名单内。停用 Cron 能力后，其调度工具不再可调用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true

### Requirement: PA 产品说明书按需回答产品问题

PA 随当前安装版本提供可选的产品说明书 skill，覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、外部渠道、启动和常见故障处理。入口经 `skill` 按需加载，再由默认启用的 `read` 只读取当前问题所需的随包专题资料；普通任务不因其启用而加载。用户显式关闭 `read` 后，产品不保证详细手册可读。退役 Coding CLI、DSH 内部和开发流程不属于该手册。

#### Scenario: 在 PA 对话入口询问产品问题

- **GIVEN** 当前 Agent 已启用产品说明书、`skill` 与 `read`
- **WHEN** 用户从 Web IM、飞书或其他 PA 对话入口询问 PA 能力、使用、配置或故障处理
- **THEN** Agent 按需读取产品说明书，并基于当前安装版本直接回答

#### Scenario: 普通任务不加载产品说明书

- **WHEN** 用户提出与 PA 产品自身无关的普通任务
- **THEN** Agent 不因为产品说明书处于启用状态而读取它

#### Scenario: 基础问答离线可用

- **WHEN** 用户询问当前安装版本的 PA 产品能力或使用方法
- **THEN** Agent 可只依据随包手册回答，不要求远端文档服务

#### Scenario: 最新版与本机版本分开回答

- **WHEN** 用户明确询问最新版、升级变化或远端当前行为
- **THEN** Agent 区分查到的官方远端信息与本机安装版本，不把远端行为表述为本机已经具备
- **AND** 远端信息不可用时明确限定为本机手册事实

#### Scenario: 现场状态以实际核实为准

- **WHEN** 用户询问自己的 Agent、节点、渠道或任务当前状态
- **THEN** Agent 在能力允许时核实现场后回答，并区分产品规则与观察结果
- **AND** 无法核实或手册未覆盖时明确不确定，不编造能力、配置或处理步骤

### Requirement: PA Agent 从有序的工作区与用户级兼容根发现 Skill

PA 为某 Agent 解析可选 Skill、prompt preview、下一轮新回复和 `skill` 时，按该 Agent 的真实 Workspace 依次搜索 `<workspace>/.nanoassistant/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`，再依次搜索 `~/.nanoassistant/skills/`、`~/.agents/skills/`、`~/.claude/skills/`、`~/.codex/skills/`。`~/.agents/skills/` 是用户级兼容来源，不新增 `<workspace>/.agents/skills/`。同名 Skill 只采用最先命中的版本；缺失或空的可选兼容目录不影响其他来源。

#### Scenario: 工作区 Claude/Codex Skill 出现在 Agent capability 中
- **GIVEN** 某 Agent 的真实 Workspace 下 `.claude/skills/` 或 `.codex/skills/` 含有效 Skill
- **WHEN** IM 通过在线 Gateway 解析该 Agent 的 capabilities
- **THEN** 该 Skill 成为候选并携带实际命中的 location
- **AND** 同名的较低优先级副本不作为第二个候选返回

#### Scenario: PA 新回复与 capability 使用同一同名覆盖结果
- **GIVEN** 同名 Skill 同时存在于 PA 的多个受支持工作区或全局 roots，且用户在 Agent 配置中选择该 name
- **WHEN** 用户保存配置后在既有聊天开始下一轮新回复
- **THEN** 该轮使用与 capability 中同一优先级、同一 location 的 Skill 内容

#### Scenario: 缺失兼容目录不阻断 PA Agent
- **GIVEN** Agent Workspace 未创建 `.claude/skills/` 或 `.codex/skills/`，或用户主目录未创建 `.claude/skills/`
- **WHEN** Gateway 解析 capabilities、开始新回复或处理 `skill`
- **THEN** 操作正常完成
- **AND** 其他有效 roots 中的 Skill 仍可使用

#### Scenario: 新建页只取得全局 Skill candidates
- **GIVEN** IM 正在为尚无 canonical Workspace 的新 Agent 查询 node capabilities，且 Gateway repo root 中存在工作区 Skill
- **WHEN** Gateway 返回该 node 的创建页 Skill candidates
- **THEN** 返回的候选只来自 PA 的共享全局 roots
- **AND** repo root 或其他未绑定 Workspace 中的 Skill 不作为新 Agent 可选择项
