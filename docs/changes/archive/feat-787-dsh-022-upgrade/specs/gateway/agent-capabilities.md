# gateway agent-capabilities Specification (delta for feat-787)

## MODIFIED Requirements

### Requirement: Agent 可在 workspace 自助安装原生工具

Agent 启用 `plugin_manager` 后，可以在可信配置确定的 workspace 创建标准 DSH bundle（包括工具、提示词和其他适用 workspace scope 的插件贡献），安装、启用、停用和移除，并同时获得只读运行时检查工具（`cordis_inspect_list`、`cordis_inspect_query`）以查询宿主已注册的服务、事件、配置 Schema 与当前可见工具声明。新增且不与既有工具名冲突的 workspace 工具自动并入该 Agent 的有效集合，不要求人工修改白名单。静态工具选择和禁用保持；关闭管理能力或显式空工具集不自动获得这些工具或只读运行时检查工具。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

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

#### Scenario: 只读运行时检查随插件管理权限联动开放
- **WHEN** Agent 已启用 `plugin_manager` 并处于允许使用该入口的会话角色
- **THEN** 可调用只读运行时检查工具 `cordis_inspect_list` 与 `cordis_inspect_query` 读取宿主服务、事件、插件配置 Schema 与可见工具契约，不因此开放动态代码定义或运行能力
- **WHEN** Agent 未启用 `plugin_manager`（含在线撤回 `plugin_manager` 后），或当前会话属于禁用用户管理入口的子执行者
- **THEN** 模型下发工具集不含 `cordis_inspect_list` 与 `cordis_inspect_query`，直接调用被拒绝；节点可选工具目录不将其拆分为独立勾选项

### Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖

本条的静态工具选择规则适用于 `single_thread` 及 Global／PA 主会话的可配置工具；Global／PA 普通内部执行者遵循本 area 的分层工作能力条目，不套用主会话的普通工具名单。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具及只读宿主检查工具（`cordis_inspect_list`、`cordis_inspect_query`）按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用机制即撤销其注册。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为上述主会话构建可配置工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述四个上下文内部工具以及启用 `plugin_manager` 时的 workspace 自建工具与只读宿主检查工具（`cordis_inspect_list`、`cordis_inspect_query`）有限增量外，非空时 Agent 静态业务工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按机制启停，预览、下发和实际执行保持一致。

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
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除四个上下文内部工具外，仅在启用 `plugin_manager` 时按已安装 workspace 工具集合及只读宿主检查工具（`cordis_inspect_list`、`cordis_inspect_query`）增加受控伴随工具名
- **AND** 若白名单不含 `skill` 或 `apply_patch`，session 不启用未列出的 `skill` 或 `apply_patch`

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

## ADDED Requirements

### Requirement: apply_patch 作为默认文件修改能力提供且保持工作区与白名单边界

宿主默认启用原生 `apply_patch` 文件补丁能力，与 `write`、`edit` 一同组成标准文件修改工具集，同时不开放模型侧切换会话目录的 `working_directory` 工具、原生 `AgentTeam` 共享任务板工具及单次实验性 `subagent_oar`。

#### Scenario: 新建与未固定白名单的助手及一级原生执行者默认可用
- **WHEN** IM 查询节点可选工具，或新建 Agent、运行未显式配置 `tool_allowlist` 的 Agent 及 Global/PA 一级原生工作 subagent
- **THEN** `apply_patch` 出现在可选工具目录中且 `default_on` 为 `true`，上述执行会话默认可调用 `apply_patch` 在单次补丁中完成多文件新增、更新、删除或移动
- **AND** 任意会话均不暴露 `working_directory`、原生团队任务板工具与 `subagent_oar`，会话工作区身份保持创建时绑定的目录且不吸入工作区外指令文件

#### Scenario: 既有显式工具白名单不被静默扩宽
- **GIVEN** 存量 Agent 已持久化非空或空的显式 `tool_allowlist` 且未包含 `apply_patch`
- **WHEN** 节点升级运行时后创建或恢复该 Agent 的主会话
- **THEN** 主会话仍严格按已保存的 `tool_allowlist` 提供静态业务工具，用户可在设置页按需勾选或取消 `apply_patch`

### Requirement: 网页搜索在缺少独立搜索源时脱敏复用官方 DeepSeek 凭据

#### Scenario: 显式搜索源优先级保持不变
- **GIVEN** 节点已配置 `DSH_WEB_SEARCH_PROVIDER`、`SEARXNG_URL` 或 `BRAVE_API_KEY`
- **WHEN** Agent 调用 `web_search`
- **THEN** 按显式指定提供方、`searxng`、`brave` 的既有优先级执行搜索

#### Scenario: 未配独立搜索源时安全复用官方 DeepSeek 凭据且不外发对话原文
- **GIVEN** 节点未设置 `DSH_WEB_SEARCH_PROVIDER`、`SEARXNG_URL` 与 `BRAVE_API_KEY`，但存在可用的官方 DeepSeek 凭据（含原生 DeepSeek 凭据或指向官方 DeepSeek API 域名的节点模型服务密钥）
- **WHEN** Agent 调用 `web_search`
- **THEN** 通过原生 DeepSeek 搜索返回带来源链接的结果摘要，发往搜索端点的请求仅携带查询参数而不附带用户原始对话消息文本
- **AND** 指向非官方第三方代理的模型密钥不被转发至官方 DeepSeek 搜索端点

#### Scenario: 无专用搜索与官方凭据时回退公共搜索
- **GIVEN** 节点未配置上述独立搜索源，也无可用的官方 DeepSeek 凭据
- **WHEN** Agent 调用 `web_search`
- **THEN** 回退使用 `duckduckgo`，遇到网络失败或人机验证拦截时返回明确可读的原因说明

### Requirement: 长对话与模型切换具备工具输出修剪、超限图片卸载及小窗预压缩保护

#### Scenario: 超大工具输出与超限历史图片自动收敛后继续对话
- **GIVEN** 会话中累计了超过单条阈值的历史工具输出，或历史图片数量触发当前模型的图片预算上限
- **WHEN** 用户继续发起新请求，并在后续要求核对早先轮次的完整输出
- **THEN** 运行时在不额外消耗摘要模型调用的情况下裁剪过长旧工具输出，或在超限时将最早历史图片替换为带附件标识的只读占位后重试完成回复
- **AND** 已被换窗归档的早期完整记录仍可通过当前会话的 `history` 工具分页回查

#### Scenario: 切换至较小上下文窗口模型时平稳过渡
- **GIVEN** 既有会话已积累多轮历史，用户将模型切换为上下文窗口更小的目标模型
- **WHEN** 用户在该会话发送下一条消息
- **THEN** 运行时在请求发出前按目标模型窗口完成必要的上下文换窗或预压缩，不因沿用旧模型窗口估算而直接超限失败，既有备用模型链与粘性规则保持不变
