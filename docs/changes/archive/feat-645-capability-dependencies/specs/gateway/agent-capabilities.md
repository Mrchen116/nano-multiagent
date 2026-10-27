# gateway/agent-capabilities.md (delta for feat-645)

## MODIFIED Requirements

### Requirement: Intelligent UI Feature 可配置

#### Scenario: 默认启用和显式关闭
- Agent 配置页 Features 提供 `intelligent_ui`，默认勾选，缺失值按开启解释。
- 合法取消勾选并保存后，运行时移除交互生成指导，按共享依赖规则默认取消关联工具/Skill；有效 send_message 的显式合法 interactive 参数仍能发布新卡片，文字交付保留。重新勾选恢复完整依赖及指导。
- 关闭不删除已发布卡片、个人草稿或选择，历史卡片继续按原消息权限读取与提交。

#### Scenario: Feature 关闭但工具独立可用
- **GIVEN** Intelligent UI Feature 关闭，send_message 仍为固定或独立启用
- **WHEN** 普通、Global 或 Personal Agent 使用显式合法 interactive 参数发布
- **THEN** 不因 Feature 关闭而拒绝新卡片，仍执行既有 schema、身份权限、审批和交付检查；不反向恢复额外交互生成指导
- **AND** 不支持交互的渠道保留文字摘要降级，历史卡片权限与提交行为不变

### Requirement: Feature可独立启停并撤销其后续影响

#### Scenario: 关闭和重新开启单项能力
- **WHEN** 用户对无开启 Feature 依赖、有效业务责任或相关在途工作需要的某 Agent 合法关闭再开启Task Graphs、Memory Curation、Skill Creation、Cron或Heartbeat
- **THEN** 该 Feature 的额外提示与未来主动触发按配置撤销或恢复，工具及必要服务按最终工具选择和有效安排提供，其他Feature及其他Agent不受影响；重新开启不累积重复监听或任务。
- **AND** 已有任务/记忆/Skill保留，Skill Creation关闭不等于禁用已有Skill加载。

#### Scenario: 关闭期间重启与在途工作
- **WHEN** 关闭的 Feature 经历节点重启，或用户在相关工作已接受后尝试关闭
- **THEN** 重启不擅自重新启用；存在相关已接受工作时关闭被拒，配置、订阅与工作保持，不以取消工作来完成关闭。合法配置操作在持久化后因断联尚未确认时仍显示 pending，不伪报 effective 或回滚已发生副作用。

### Requirement: Memory 与 Skill 同时到期时使用一次联合复盘

后台维护 SHALL 保留 Memory、Skill 单项及 combined 三种复盘。两项已启用、工具可用且同时到期时，使用一个联合复盘处理两类知识。仅一项满足条件时运行单项复盘。开关、计数和知识归属保持独立。普通及 Global 模式均适用；F4 不并入联合复盘。

#### Scenario: 两类维护同时到期
- **WHEN** 同一前台轮次结束时两项均满足维护条件
- **THEN** 只启动一次联合复盘，两类知识均可按合法范围维护，不再为同一批条件重复启动单项复盘
- **AND** 只按实际写入报告更新，不要求两类知识都产生修改。

#### Scenario: 一项不可用或尚未到期
- **WHEN** 只有一项满足本次维护条件
- **THEN** 该项运行单项复盘，不等待另一项，也不重置未参与类别的计数。

#### Scenario: 联合复盘取消或部分成功
- **WHEN** 联合复盘失败、被显式取消，或因进程停止而中断
- **THEN** 已成功的修改和真实通知保留，未完成复盘不推进后台维护周期
- **AND** 取消或停止后的工作不再接受后续写入；仍启用能力可在后续正常触发时继续维护，不重放已成功修改。

#### Scenario: 在途联合复盘期间尝试关闭单项能力
- **GIVEN** 联合复盘已被接受且尚未终结
- **WHEN** 用户通过配置入口关闭其中一项参与维护的 Feature
- **THEN** 本次关闭被拒，原配置与联合工作保持，不触发取消，不因关闭尝试改变已成功事实或维护计数
- **AND** 复盘结束后可重新尝试合法关闭；不取消未完成工作来消除关闭阻碍

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。公开 Agent profile 提供的提示词文本仅为可见的 Custom Instructions：它作为产品规则后的 `PromptSlots` 追加段出现，不能覆盖公共 PA 提示词，也不走 Kernel 内部完整 override。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。可调用工具的取消选择先立即收缩，后续 dispatch 不再允许该工具，但不中断已开始的调用；新增工具等待当前执行空闲后的完整配置应用。收缩从当前有效选择计算，未配置白名单时默认未选的工具不会因候选名单包含而提前启用。

本次取消选择若会撤销仍被开启 Feature、有效业务责任或正在执行的工具调用需要的能力，保存先被拒绝；只有通过依赖与占用校验的变更才进入上述生效流程。普通运行中不因此阻止无关配置更新。

#### Scenario: 增加工具后继续既有聊天
- **GIVEN** Agent 因未配置某工具而无法完成既有聊天中的任务
- **WHEN** 用户增加该工具后在同一聊天继续
- **THEN** 新回复可使用该工具并理解此前的问题与回复

#### Scenario: 删除工具后保留既成工具历史
- **GIVEN** 既有聊天历史中已有某工具调用及结果
- **WHEN** 用户删除该工具后继续聊天
- **THEN** 新回复不能再执行该工具，但能理解历史调用与结果

#### Scenario: 修改 Custom Instructions、skills 或 features 后继续历史
- **GIVEN** 某聊天已形成历史
- **WHEN** 用户修改会影响后续模型请求的 Custom Instructions、skills 或 features 后发起新交流
- **THEN** 新回复体现完整的新运行配置，并仍能引用修改前历史

#### Scenario: 连续保存多次只采用最终运行配置
- **GIVEN** 某聊天空闲或消息仍在等待处理
- **WHEN** 用户连续成功保存多份 Agent 运行配置
- **THEN** 下一轮新回复使用真正开始时最新的完整配置，不依次重演中间版本

#### Scenario: 配置替换失败不使用混合配置回复
- **WHEN** Gateway 无法把最新完整运行配置持久应用到既有会话
- **THEN** 当前消息以真实失败结束，不以新 model 搭配旧 prompt 或 tools 的混合配置运行

### Requirement: 全局主 Agent 保留默认工具并具备固定基础能力

#### Scenario: 新建全局 Agent 时保留正常执行能力
- **WHEN** 用户新建全局 Agent
- **THEN** 除读取收件箱、查阅聊天、显式发言及委派的固定基础工具外，仍默认拥有现有创建流程提供的工具
- **AND** 不因选择全局模式变成只能统筹、不能正常查询或执行的空工具 Agent

#### Scenario: 固定基础工具与可配置工具区分
- **GIVEN** 用户创建或编辑全局 Agent
- **WHEN** 查看和调整工具配置
- **THEN** `inbox`、`conversations`、`send_message`、`subagent` 作为固定基础工具，不可关闭
- **AND** Personal Global 另外固定 personal_sources；其他工具继续按默认选择及依赖规则配置，single_thread 和子 Agent 不继承 Global 根会话固定项

### Requirement: Workspace 和全局 Skill 使用禁用名单

Agent 使用 `skills_selection_mode=explicit_denylist`，`skills` 保存禁用名称。配置界面仍以勾选表示启用；保存的是取消项，暂时缺失的禁用名称保留。工具白名单不受影响。

#### Scenario: 新建或复制导入的技能默认可用
- **WHEN** 在 Agent 可发现的 Workspace 或共享全局 roots 新增有效 Skill
- **THEN** 后续模型步骤可发现并按名加载，无需修改启用名单或重启；共享全局新增技能对可访问该目录的 Agent 默认可用
- **AND** 其他 Workspace 的私有 Skill 不泄漏；同名覆盖仍按已有 roots 优先级

#### Scenario: 明确禁用在所有消费者一致生效
- **WHEN** 用户合法取消勾选不再被开启 Feature 需要的 Skill 并保存
- **THEN** 后续回复的目录、按名加载、显式命令、preview、distillation readiness 和 SlashPicker 一致排除该名称
- **AND** 重启、重新扫描或同名技能重新创建不会自动启用；旧回复沿配置安全边界收口

#### Scenario: 旧配置升级保留已有选择
- **WHEN** 节点连接 IM 后迁移旧 default-discovery 或 explicit-allowlist 配置
- **THEN** default 转为空禁用名单；allowlist 以该 Agent 迁移时的完整候选集合减去旧已选名称形成禁用名单，包括旧显式空名单
- **AND** 经已有版本化配置操作同时提交 Node YAML、runtime 与 IM profile；离线不猜候选，已经迁移的配置不重复转换
- **AND** 迁移后新增名称默认可用；旧配置没有记录候选历史，迁移只保证迁移当时已有候选的选择状态

#### Scenario: 创建事实不覆盖用户禁用
- **WHEN** 前台或后台成功创建 Skill 并产生知识更新事实
- **THEN** 继续记录真实来源与通知，但不追加任何 Agent 的启用配置；是否可用由发现及禁用名单共同决定

#### Scenario: 禁用蒸馏技能时明确不可用
- **GIVEN** Agent 禁用了会话蒸馏 Skill，或离线旧模式的显式 allowlist 不包含它
- **WHEN** 用户请求生成或蒸馏 Skill
- **THEN** 返回明确的 distiller unavailable 结果，不因文件存在而放行

#### Scenario: 离线历史配置保持原模式
- **GIVEN** 节点尚未完成认证迁移
- **WHEN** 节点离线工作或旧模式会话继续执行
- **THEN** 历史 default discovery 保持发现行为，显式 allowlist 包括空名单仍按原选择限制；不凭缺失候选推断禁用名单

## ADDED Requirements

### Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖

本条的静态工具选择规则适用于 `single_thread`。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用机制即撤销其注册。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述四个上下文内部工具和 workspace 自建工具的有限增量外，非空时 Agent 静态业务工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按机制启停，预览、下发和实际执行保持一致。

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

### Requirement: Feature SHALL 保证完整依赖并与独立工具行为分离

#### Scenario: 开启 Feature 展开完整依赖
- **WHEN** 用户开启 Feature 或创建采用默认 Feature 的 Agent
- **THEN** 交互式回复需要 send_message、skill 和 nano-interactive-ui；Task 需要 task_graph 与 Cron Feature；Memory 需要 memory、read；Skill 创建需要 skill_manage、skill、read；Cron 需要 schedule_create/list/update/delete/run/history；Heartbeat 需要 read
- **AND** 默认开启 Task 的初始配置同时开启 Cron；依赖资源缺失时整个动作失败，已关闭的 Skill 不能冒充可加载

#### Scenario: 合法关闭与共享依赖
- **WHEN** 用户关闭没有需要者的 Feature
- **THEN** 默认取消其直接关联工具与 Skill，仍被其他开启 Feature 需要或属于基础固定的能力保持开启
- **AND** 不级联关闭依赖 Feature，关闭 Task 后 Cron 保持开启；随后单独打开工具或 Skill 不反向打开 Feature

#### Scenario: 独立工具不恢复 Feature 行为
- **GIVEN** 对应 Feature 关闭且工具已单独选中
- **WHEN** Agent 调用 task_graph、memory、skill_manage 或某个 schedule 工具
- **THEN** 合法调用实际可用；不附加该 Feature 的额外提示词、后台复盘、主动注入或自动续跑，操作仍受原授权及业务前置条件约束

### Requirement: 能力配置 SHALL 在保存边界保护真实需要者

#### Scenario: 静态依赖不能被任意配置入口绕过
- **WHEN** 完整候选配置缺少开启 Feature 的必需依赖，或移除基础固定能力
- **THEN** 配置 API、预览与运行入口明确拒绝，不静默猜测点击顺序、不写入半套能力配置
- **AND** Feature 关闭而工具单独开启的完整配置合法

#### Scenario: 在途工作保护最小能力范围
- **GIVEN** 本 Agent 已接受相应 Memory/Skills 维护或 Heartbeat 工作，或待撤销工具正在调用
- **WHEN** 用户尝试关闭仍被该工作需要的能力
- **THEN** 关闭被拒，原配置和业务工作不被本次操作改变；其他无关配置可修改
- **AND** 普通 Agent running、已完成记录和未来未接收的维护机会不构成此类阻碍

#### Scenario: 检查后出现的新责任不能绕过关闭保护
- **WHEN** 配置关闭与新 Task 责任或新定时安排并发到达
- **THEN** 先建立的有效责任使关闭被拒；先被接受的关闭使冲突的新责任或安排被拒，不出现双方都成功而能力缺失
- **AND** 使用状态不可确认时明确失败，不把读取失败当作空闲；重试和断联恢复沿既有配置 operation 保持一致

## REMOVED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具
