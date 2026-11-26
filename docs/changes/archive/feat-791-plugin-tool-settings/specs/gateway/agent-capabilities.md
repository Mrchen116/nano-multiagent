# gateway/agent-capabilities.md (delta for feat-791)

## MODIFIED Requirements

### Requirement: Agent 可在 workspace 自助安装原生工具

Agent 启用 `plugin_manager`（含通过默认开启的 `plugin_management`「插件开发与管理」运行特性启用，或独立勾选该工具）后，可以在可信配置确定的 workspace 创建标准 DSH bundle（包括工具、提示词和其他适用 workspace scope 的插件贡献），安装、启用、停用和移除。宿主只读运行时检查工具（`cordis_inspect_list`、`cordis_inspect_query`）作为默认开启的标准可选工具随 `plugin_management` 特性联动启用，也可在特性关闭后按静态工具选择单独启用或停用，用于查询宿主已注册的服务、事件、配置 Schema 与当前可见工具声明。新增且不与既有工具名冲突的已启用 workspace 插件工具自动并入该 Agent 的有效集合，并在能力目录中携带 `source_group="workspace"` 及所属插件包的标识与显示标题，不要求人工修改静态白名单。静态工具选择和禁用保持；关闭 `plugin_manager` 或显式空工具集不自动获得自装 workspace 业务工具；升级前已保存配置按既有 `plugin_manager` 权限平滑承接特性与只读检查工具状态。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

#### Scenario: 安装后既有聊天立即使用
- **WHEN** Agent 成功安装并启用 workspace 工具
- **THEN** 同 workspace 既有及新聊天可使用它，不需重启；其他 workspace 不可发现或执行

#### Scenario: 失败不声称已启用
- **WHEN** 包安装或实际加载失败
- **THEN** Agent 收到失败状态和真实诊断；包管理成功不代替执行可用证据

#### Scenario: 重启和撤销
- **WHEN** 节点重启或 Agent 停用/移除已安装 bundle
- **THEN** 重启保留持久选择，停用/移除后后续调用不可执行对应工具，且已停用或移除插件的工具从当前运行时能力目录中移除

#### Scenario: 保留其他工具选择
- **GIVEN** 已有禁用工具或显式空集
- **WHEN** 该 workspace 安装新增工具
- **THEN** 既有禁用选择不改变，空集不自动扩宽

#### Scenario: 非工具插件及整体停用
- **WHEN** Agent 安装不注册工具的提示词插件，随后用户停用或重新启用
- **THEN** 当前 workspace 的提示词贡献生效、撤销或恢复，其他 workspace 不受影响；DSH 生命周期管理的资源一并回收

#### Scenario: 网页与聊天管理同一原生插件状态
- **WHEN** 已认证的所属用户从 Agent 设置管理插件
- **THEN** Node 从可信 Agent 配置解析 workspace，网页与聊天操作同一份持久安装和启用状态，不修改宿主全局 profile
- **AND** 忙碌时网页操作等待 workspace 执行空闲，状态查询仍可用，并发管理明确返回忙碌而不死锁；未完成操作不报成功

#### Scenario: 停用状态在更新时保留
- **GIVEN** 已安装包处于停用
- **WHEN** Agent 更新同名包且没有显式要求开启
- **THEN** 包仍停用，重启保持已完成的选择

#### Scenario: 第三方插件的宿主依赖与 workspace 配置
- **WHEN** Agent 安装声明兼容当前 DSH 的第三方 bundle，并通过 workspace 原生 user overlay 配置其服务作用域
- **THEN** 插件可复用宿主公开依赖，配置在该 workspace 热应用；不要求复制运行时、修改宿主 profile 或静态工具白名单
- **AND** 该 preset 提供压缩引擎时，自动与人工压缩由该引擎负责；停用后恢复默认引擎，其他 workspace 保持原有行为

#### Scenario: 只读运行时检查与插件开发管理特性联动并支持独立选择
- **WHEN** Agent 开启 `plugin_management` 运行特性，或在关闭该特性后单独在工具选择中启用 `cordis_inspect_list` 或 `cordis_inspect_query`，且当前会话属于拥有可信 workspace 的根会话或显式 `subagent_fork`
- **THEN** 模型可调用被选中的只读运行时检查工具读取宿主服务、事件、插件配置 Schema 与可见工具契约，不因此开放动态代码定义或运行能力，单独启用检查工具也不反向开启 `plugin_management` 或 `plugin_manager`
- **WHEN** Agent 未选中对应检查工具（含在线撤回后），或当前会话属于无 workspace、普通子 Agent 或 Global 一级执行者
- **THEN** 模型下发工具集不含对应检查工具，直接调用被拒绝

#### Scenario: 存量配置平滑承接插件管理权限
- **GIVEN** 升级前已保存且未显式记录 `plugin_management` 特性的存量 Agent 配置
- **WHEN** 节点启动校验、上报能力或创建会话
- **THEN** 原先允许使用 `plugin_manager` 的配置自动具备 `cordis_inspect_list` 与 `cordis_inspect_query` 有效权限（`nano-plugin-development` 仍处于有效选择且所需能力可用时 `plugin_management` 特性按开启解释），不因新增伴随工具触发依赖缺失阻断；原先显式工具白名单不含 `plugin_manager` 的受限配置保持 `plugin_management` 关闭且不扩宽可用工具集

### Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖

本条的静态工具选择规则适用于 `single_thread` 及 Global／PA 主会话的可配置工具；Global／PA 普通内部执行者遵循本 area 的分层工作能力条目，不套用主会话的普通工具名单。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的已启用 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制（`dsh-agent-context` 插件）启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用该插件即从运行时撤销其注册并从 `fixed_tools` 与能力目录移除。global 主 Agent 的有效集为配置集合与固定基础项的并集；其他工具（含 `cordis_inspect_list` 与 `cordis_inspect_query`）仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，插件开发与管理、任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为上述主会话构建可配置工具集时，以该 Agent 配置的 `tool_allowlist` 为静态白名单单一来源（升级前未显式记录 `plugin_management` 且包含 `plugin_manager` 的存量配置按承接规则隐式包含 `cordis_inspect_list` 与 `cordis_inspect_query`）：除已启用上下文插件的四个内部工具以及启用 `plugin_manager` 时的已启用 workspace 自建工具增量外，非空时 Agent 静态业务工具集**恰为**有效选中的这些（列表外的默认工具不提供，即默认文件/web/只读自省工具均可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按插件启停状态挂载或卸载，预览、下发和实际执行保持一致。

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
- **GIVEN** single_thread PA agent 已持久化显式记录了 `features.plugin_management` 的合法非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除已启用上下文插件的四个内部工具外，仅在启用 `plugin_manager` 时按当前已启用 workspace 插件集合增加不冲突的自建工具名
- **AND** 若白名单不含 `skill`、`apply_patch` 或 `cordis_inspect_list`，session 不启用未列出的对应工具

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 Cron Feature 并已将其全部依赖工具保存到 `tool_allowlist`
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 schedule_create/list/update/delete/run/history 六项；合法关闭 Cron 后按最终工具选择提供，用户单独重新启用的工具不因 Feature 关闭而拒用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`、`cordis_inspect_list` 与 `cordis_inspect_query`
- **AND** 上述工具的 `default_on` 均为 true

#### Scenario: Auto 关闭不阻断会话内部上下文管理
- **GIVEN** 当前 Agent 启用了默认上下文机制，自动审批关闭
- **WHEN** 普通、Global、Personal 或子 Agent 保存笔记、恢复历史、查询预算或请求换窗
- **THEN** 仅作用当前执行会话的四工具无需额外审批即可执行，明确的底层拒绝仍保留
- **AND** 其他业务工具继续遵守原审批、选择与发送重验规则；恢复内容不生成新的授权

### Requirement: Feature SHALL 保证完整依赖并与独立工具行为分离

#### Scenario: 开启 Feature 展开完整依赖
- **WHEN** 用户开启 Feature 或创建采用默认 Feature 的 Agent
- **THEN** 交互式回复需要 send_message、skill 和 nano-interactive-ui；插件开发与管理（`plugin_management`，默认开启）需要 `plugin_manager`、`cordis_inspect_list`、`cordis_inspect_query` 和 `nano-plugin-development`；Task 需要 task_graph 与 Cron Feature；skill-creator 是固定内置指导，不再属于可选 Feature 或 Skill 名单，其实际操作遵守工具权限；Cron 需要 schedule_create/list/update/delete/run/history；Heartbeat 需要 read。
- **AND** 内置 document 消费不依赖旧 memory 条目工具；主 Agent/普通 child 对正式记忆只读，文件工具不能直接修改正式库。Dreaming 使用自己的受限维护工具集，不暗中开启父业务工具；缺少可运行所需资源须显示不可用，不能假报运行。
- **AND** 默认开启 Task 的初始配置同时开启 Cron；依赖缺失时显式启用动作失败，已关闭 Skill 不冒充可加载。

#### Scenario: 合法关闭与共享依赖
- **WHEN** 用户关闭没有需要者的 Feature
- **THEN** 取消其直接关联资源，仍被其他 Feature 需要或属于基础固定的能力保留；Dreaming 停用不撤销普通文件工具/内置记忆。
- **AND** 不级联关闭依赖 Feature，关闭 Task 后 Cron 保持开启；随后单独打开工具或 Skill 不反向打开 Feature。

#### Scenario: 独立工具不恢复 Feature 行为
- **GIVEN** Feature 关闭而工具仍被合法独立选中
- **WHEN** Agent 调用 `plugin_manager`、`cordis_inspect_list`、`cordis_inspect_query`、task_graph、skill_manage、schedule 工具，或 legacy 模式下可用的 memory
- **THEN** 操作按原授权与业务前置条件执行，不恢复 Feature 额外行为或已关闭的依赖 Skill；document 不提供旧 memory 条目工具，Skill 工具不恢复自动 fork。
