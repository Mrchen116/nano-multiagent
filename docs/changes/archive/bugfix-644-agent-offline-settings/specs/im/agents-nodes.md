# IM agents-nodes Specification (delta for bugfix-644)

## ADDED Requirements

### Requirement: Agent 设置与外部渠道离线时保持可读并统一只读，恢复后刷新再解锁

#### Scenario: 离线首次打开或跨浏览器查看
- **GIVEN** 当前用户有权查看该 Agent，但节点不可达
- **WHEN** 用户打开整个 Agent 配置页及相关分区
- **THEN** 页面显示已保存配置和最后成功同步的展示信息、来源与时间，没有取得的信息明确暂时无法获取
- **AND** 模型与推理强度成对保留；插件、统计、任务和渠道的未知状态不伪装为空、关闭或失败，已同步工作历史仍可阅读
- **AND** 所有配置写入和节点操作禁用，阅读、展开、取消、放弃草稿及检查连接仍可用

#### Scenario: 编辑中掉线并恢复
- **GIVEN** 用户已有未保存草稿或已打开的渠道编辑弹窗
- **WHEN** 节点失联并随后重新连接
- **THEN** 页面保留本页草稿并立即禁用修改和提交；重连先刷新当前配置、能力、相关资源版本和未确认结果，完成后才恢复相应操作
- **AND** 刷新或历史数据均不自动提交草稿、不清空选择、不替用户补默认值；迟到的旧请求不能解锁页面
- **AND** 若版本或真实能力变化造成冲突，用户核对、调整或放弃后再主动保存，不能自动用新版本覆盖服务端内容

#### Scenario: 在线某一区域读取失败
- **GIVEN** 节点在线但某一设置分区的当前信息未取得
- **WHEN** 用户查看该分区
- **THEN** 页面保留最近确认内容、说明读取失败并允许重试；该分区未刷新成功前不可操作
- **AND** 独立分区不因统计等无关读取失败被禁用，历史信息不充当当前能力

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、有序 `model_fallbacks`、其可空 `reasoning_effort`、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。完整配置不在已进行的整轮中切换；可调用工具的取消选择例外地立即收缩，新增工具仍等待当前执行空闲后的完整配置应用，不中断已开始的工具调用。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。缺省或空的 `model_fallbacks` 与从未配置等价。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段、可空 `reasoning_effort`、有序 `model_fallbacks` 及 profile version
- **AND** 专属人设只以可见的 `custom_prompt` 返回，不含 profile `system_prompt`

#### Scenario: 新离线请求不产生配置操作
- **GIVEN** Agent 所属节点当前不可达
- **WHEN** 用户或客户端提交新的配置修改
- **THEN** 页面禁用提交，服务端拒绝该请求且不创建新候选操作或修改已提交配置
- **AND** 先前已经接受的操作继续使用原操作标识确认结果，不因断线被删除或标成功

#### Scenario: PATCH 经 Gateway 可恢复 apply 后持久化运行配置并保持乐观锁
- **GIVEN** 节点当前可达，且没有阻止本次修改的未确认操作
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** IM 先持久化候选 configuration operation，并取得 owning Gateway 对完整候选配置的成功 apply operation 结果，再持久化 profile
- **AND** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新后的模型、备用列表和推理强度，并延续原聊天历史

#### Scenario: 保存的推理强度必须属于 Gateway apply 时的有效模型目录
- **GIVEN** Agent 明确选择模型 M，或继承 Gateway 的平台默认模型 M
- **WHEN** 前端保存 M 的推理强度
- **THEN** Gateway 在 apply 时以 M 的当前能力验证该选择并确认其本地配置已落地后，IM 才持久化
- **AND** 当目录已更新而该强度失效时返回冲突、不写新 profile，也不表示保存成功

#### Scenario: 保存的备用模型必须属于 Gateway apply 时的有效模型目录
- **GIVEN** 该节点当前可用模型目录
- **WHEN** 前端保存 `model_fallbacks`
- **THEN** Gateway 在 apply 时确认每一项都在目录中、与当时有效主模型不同，并去重保序
- **AND** 目录外的项返回冲突、不写新 profile

#### Scenario: Gateway 成功 apply 后 IM 乐观锁失败会恢复 Gateway 原配置
- **GIVEN** Gateway 已成功 apply 一个候选 Agent 配置
- **WHEN** IM 以该请求的 profile version 持久化时发现并发配置已先保存
- **THEN** IM 在返回冲突前请求 Gateway 恢复之前已确认的完整配置，前端不显示候选配置已保存

#### Scenario: 已落盘但 ACK 丢失的配置操作可恢复而不伪装旧值成功
- **GIVEN** IM 已保存一个 Agent 配置 operation，Gateway 已落盘候选配置和 applied receipt
- **WHEN** ACK frame 丢失、连接重连或 IM 在 profile 持久化前重启
- **THEN** IM 使用同一 operation id 重试或查询 Gateway operation status
- **AND** 结果仍不可确认时 API 返回 `503 config_apply_pending`，页面显示正在确认且禁止重复编辑，不把旧 profile 显示为已经保存的当前配置
- **AND** 完整请求已收到后，HTTP 连接允许等待既有节点确认流程返回；不因短于该流程的 socket 空闲超时提前断开。请求体接收时限与大小限制继续生效。

#### Scenario: 配置接口遇到代理错误页面
- **WHEN** 加载或保存 Agent 配置时，代理返回 HTML 或其他非业务 JSON 错误
- **THEN** 页面显示当前语言的简短服务器响应提示和 HTTP 状态，保留正在编辑的内容，不展示代理页面源码，也不自动重发修改请求
- **AND** 业务 JSON 中的待确认状态、冲突原因与操作标识继续用于原有恢复流程

#### Scenario: 创建 Agent 的已应用结果丢失后可恢复
- **GIVEN** Gateway 已创建并为某 create operation 持久化 applied receipt
- **WHEN** IM 未收到 create ACK 或在写入 profile 前重启
- **THEN** IM 通过该 operation status 得到 canonical Agent payload 后创建 profile
- **AND** 同一 operation 重试不会在 Gateway 创建第二个 workspace 或第二次发布配置

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久 profile 含 IM 自有运行字段
- **WHEN** IM 拉取并合并 Gateway live snapshot
- **THEN** live payload 省略这些字段时不把持久值清空

#### Scenario: heartbeat cadence 返回真实配置值
- **WHEN** 前端读取某 Agent 的 heartbeat cadence
- **THEN** 返回该 Agent 的真实 `heartbeat.every` 配置值；未配置时体现为默认 `30m`

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

工具候选合并 Gateway 的 PA 内置声明与对应上下文中已注册的工具：内置声明保持既有顺序及 default_on，其他注册工具去重追加、default_on=false；已有注册项携带真实描述，缺失 runtime 实例的内置声明仍保留。节点创建页使用共享目录，Agent 编辑页还包含其工作区工具并采用该工作区的同名覆盖。候选可见不代表已启用；选中状态和保存值仍由用户配置决定，不因新增候选而扩大已有白名单（含显式空集），global 固定基础工具规则不变。

新建/编辑 Agent 页需要的 runtime 候选项（skills / tools / models / features）由 IM **当场**经 gateway WS 向在线节点解析后返回，IM 不在本地持久化该能力目录，也不据 IM 部署机文件系统推断。Agent 设置页可保留已成功取得的有限展示信息，供离线只读；这些信息带取得时间，不作为当前候选目录、保存校验或操作许可。节点级 `GET /im/v1/nodes/{id}/capabilities`（agent 尚不存在时用）与 agent 级 `GET /im/v1/agents/{id}/capabilities` 都把网关返回的 `features` 和每模型安全的 reasoning descriptor 透传给前端；节点级响应另透传可选的 `default_workspace_template`，供创建页展示该 Gateway 的默认路径，IM 不自行推导。Skill 候选的 `location` 和可选 `source_group` 亦由 Gateway 解析；IM 只透传，不直读 Gateway Workspace。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...], platform_default_model, default_workspace_template?, features:[...]}`；网关 payload 无 features 时 IM 返回空 `features` 列表（优雅降级）

#### Scenario: 用户发现并启用新安装的共享工具
- **GIVEN** 在线 Gateway 已成功注册共享用户工具 T
- **WHEN** 用户打开该节点的新建页或其 Agent 的编辑页
- **THEN** 工具候选包含 T 及其注册描述，新建默认不选中 T；已有 Agent 未启用 T 时仍保持未选中
- **WHEN** 用户主动勾选 T 并保存
- **THEN** T 加入该 Agent 工具白名单，重新打开页面仍为选中，并按既有配置下一轮生效契约可用
- **WHEN** 用户取消 T 并保存
- **THEN** T 仍是候选但不在保存的白名单，后续会话按既有执行层权限契约拒绝未授权调用

#### Scenario: 工作区候选不跨 Agent 混入
- **GIVEN** Agent A 与 B 使用不同工作区，各有各自的用户工具
- **WHEN** 用户分别编辑 A 与 B，或打开其节点的新建页
- **THEN** 各编辑页只包含共享目录及自身工作区工具；节点新建页不借用 A/B 的工作区目录
- **AND** 同名工具只显示一次，其描述与该 Agent 的实际工作区覆盖一致

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}`（可含 `requires_tool`）,由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider（例：`codex_oauth:gpt-5.5` → `openai_compat`，`kimiCoding:K2.6` → `anthropic`）,供 agent 配置页模型下拉展示格式

#### Scenario: 用户按有效模型能力选择推理设置
- **GIVEN** 创建或编辑页已取得在线节点能力
- **WHEN** 用户选择一个可调推理模型，或当前继承的 platform default 是可调推理模型
- **THEN** 页面只提供该 model descriptor 声明的 levels，新建或用户主动切换模型时可初始选择其 default；读取已有配置时保留已存强度及继承语义，不因刷新自动补值
- **AND** 继承 default 时保存的 `default_model` 仍为空，只持久化用户明确选择的强度
- **WHEN** 有效模型是 fixed、平台默认不可解析，或目录未声明推理能力
- **THEN** 页面分别显示固定思考、无法确定模型或不可配置说明，不提交不属于有效模型的强度

#### Scenario: 可选模型列表每项携带安全的推理能力
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 若节点将模型声明为可调推理模型，model 含 `{kind:"selectable", default, levels}`；固定思考模型含 `{kind:"fixed"}`；未声明的模型不含 reasoning 字段
- **AND** 响应不含模型静态请求参数或上游密钥

#### Scenario: agent 能力的 skills 项携带 location 与来源分组
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `skills` 列表中每项携带实际命中的 `location`（SKILL.md 路径，可空）
- **AND** Gateway 能确定来源时，该 Skill 同时携带 `source_group: "workspace" | "global" | "compatibility"`，供配置页分组
- **AND** 同一 Agent 的同名 Skill 只返回有序 roots 中最先命中的版本；多 Agent 聊天的 SlashPicker 使用会话成员 commands 投影的 opaque `skill_key` 区分不同节点／位置的同名 Skill，保留独立说明与来源 Agent；上述管理能力接口仍保留 `location`／`source_group`，成员候选不暴露本机路径

#### Scenario: 旧节点未提供来源分组时安全降级
- **GIVEN** 在线 Gateway 返回的旧 capability payload 不含 `source_group`
- **WHEN** 前端打开 Agent 配置页
- **THEN** Skill 候选仍可显示和逐项选择
- **AND** 页面不因缺少该可选字段崩溃或误报能力请求失败

#### Scenario: 技能禁用名单显示为灰色
- **GIVEN** Agent 配置使用 `explicit_denylist`，其中名称表示禁用的 Skill
- **WHEN** 用户打开配置页、保存后重新打开或刷新
- **THEN** 禁用名单中的候选 Skill 显示为灰色未选中，名单外显示为绿色选中，分组计数表示启用数量
- **AND** 编辑并保存后仍持久化禁用名称，保留暂时不可见的禁用名称。

#### Scenario: 无实时能力不误判已保存配置
- **GIVEN** 节点失联或本次能力读取失败
- **WHEN** 用户查看已保存的模型、推理强度、Features、工具和 Skills
- **THEN** 页面保留显式配置和最近确认的名称、来源与派生状态；未取得的信息明确未知
- **AND** 不因缺少目录显示强度不受支持、移除配置项或填入默认值，历史展示信息不能用于开启编辑

### Requirement: HEARTBEAT.md 只读预览与 cron 任务管理经 WS RPC 代理到 gateway（feat-394-M13 决策 G）

IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）。相关 endpoint 均经 WS RPC 将请求委托给目标节点 gateway，由 gateway 读写其本地 workspace 后回包，IM 做路由转发与离线降级。

#### Scenario: 获取 HEARTBEAT.md 预览内容
- **WHEN** 前端 `GET /im/v1/agents/{id}/heartbeat-md`
- **THEN** 200 返回 `{content: string, node_online: bool}`；节点在线时 content 为 `HEARTBEAT.md` 内容 （文件不存在则空串）；节点离线或 RPC 超时时 `{content:"", node_online:false}`

#### Scenario: 列 cron 任务经 RPC 代理
- **WHEN** 前端 `GET /im/v1/agents/{id}/cron/jobs`
- **THEN** 在线成功时 200 返回 jobs 数组；节点离线或超时时返回明确不可用错误，不以空数组冒充无任务，也不直读 gateway 侧文件

#### Scenario: 删 cron 任务经 RPC 代理
- **WHEN** 前端 `DELETE /im/v1/agents/{id}/cron/jobs/{job_id}`
- **THEN** 204 表示删除成功；节点离线或 RPC 超时返回明确不可用错误，只有已确认 job_id 不存在才返回 404

#### Scenario: 离线查看已取得内容
- **GIVEN** 页面已成功取得 HEARTBEAT.md 或提示词预览，或 IM 曾成功取得该 Agent 的任务列表
- **WHEN** 节点失联或再次读取失败
- **THEN** 页面保留已取得的文件预览或最后同步任务列表并标明时间，禁止重新生成预览与删除任务
- **AND** 新页面没有取得文件预览时显示暂时无法获取，不能把离线响应中的空内容当作空文件；真实成功空结果仍可显示为空

### Requirement: 外部 channel desired state 与 runtime state 分离并自动收敛

IM 持久化用户期望的 channel 配置，Gateway 上报实际连接和诊断状态。保存成功只代表 desired state 已提交；请求在线被接受后节点断线或 Gateway 尚未应用时显示“配置已保存，等待节点应用”，不能伪造已连接。节点重连后 IM 下发完整 manifest 自动收敛。启用、停用、编辑、重连和删除均经同一资源生命周期；内部 revision 只用于并发/CAS，不作为用户可见版本。删除先保留无凭据 removal receipt，实际停止失败可重试；影子会话和历史不随 channel 删除。

#### Scenario: 新离线渠道操作被拒绝
- **GIVEN** Agent 所属节点当前离线
- **WHEN** 用户新增、编辑、启用、停用、重连、删除 channel 或重试删除
- **THEN** 页面禁用入口和已打开弹窗中的提交，服务端拒绝新操作，不改变 desired 配置、凭据、revision 或删除回执
- **AND** 用户仍能阅读已有配置、最后状态及诊断，取消弹窗；不承诺节点本地渠道已停止

#### Scenario: 已接受的渠道变更在重连后继续收敛
- **GIVEN** 渠道变更已被接受，随后节点断线或结果尚未确认
- **WHEN** 节点恢复连接
- **THEN** 原 manifest 和删除回执继续确认实际结果，无需再次提交
- **AND** 页面在确认前保留待应用或待确认状态，不把旧连接状态当作本次操作成功

#### Scenario: 删除等待实际停止且保留历史
- **GIVEN** channel 已产生外部影子会话
- **WHEN** 用户确认删除
- **THEN** desired 配置和凭据被删除，但 removal receipt 在 Gateway 确认停止前保持可见
- **AND** stop 失败显示具体原因与重试入口；成功后 channel 从列表移除，既有影子会话和聊天历史保留

#### Scenario: 停用、重新启用和手动重连
- **GIVEN** 一个已连接 channel
- **WHEN** 用户确认停用
- **THEN** 页面等待 Gateway 实际停止后显示 disabled，配置和凭据继续保留
- **WHEN** 用户重新启用或在节点在线时手动重连
- **THEN** 无需重填未变化的 secret，页面显示连接进度和真实终态；手动重连不改变 desired 配置

#### Scenario: transient removal feedback 随 receipt 生命周期收敛
- **GIVEN** 已有 removal receipt 未确认且节点离线，页面显示等待节点并禁用 retry
- **WHEN** 节点恢复后用户再次在线 retry，或后台成功令 receipt 消失
- **THEN** 旧离线等待提示立即清除；receipt 消失时相关临时错误也清除，页面进入通用空态
