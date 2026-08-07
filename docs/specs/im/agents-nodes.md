# IM - Agents and Nodes Specification

> 对齐: refactor-513
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

Agent 配置中心、外部 channel 控制面、节点绑定、节点状态、runtime 能力解析、用户维事件流和配置 RPC 的 IM 契约。

## Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、其可空 `reasoning_effort`、可见的 Custom Instructions (`custom_prompt`)、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一轮新回复开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live 快照合并时仍以持久值为准。公开 Agent profile 和能力目录都不提供 `system_prompt` 或上游请求参数。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段、可空 `reasoning_effort` 及 profile version
- **AND** 专属人设只以可见的 `custom_prompt` 返回，不含 profile `system_prompt`

#### Scenario: PATCH 经 Gateway 可恢复 apply 后持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** IM 先持久化候选 configuration operation，并取得 owning Gateway 对完整候选配置的成功 apply operation 结果，再持久化 profile
- **AND** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一轮新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一轮新回复使用更新后的模型和推理强度，并延续原聊天历史

#### Scenario: 保存的推理强度必须属于 Gateway apply 时的有效模型目录
- **GIVEN** Agent 明确选择模型 M，或继承 Gateway 的平台默认模型 M
- **WHEN** 前端保存 M 的推理强度
- **THEN** Gateway 在 apply 时以 M 的当前能力验证该选择并确认其本地配置已落地后，IM 才持久化
- **AND** 当目录已更新而该强度失效时返回冲突、不写新 profile，也不表示保存成功

#### Scenario: Gateway 成功 apply 后 IM 乐观锁失败会恢复 Gateway 原配置
- **GIVEN** Gateway 已成功 apply 一个候选 Agent 配置
- **WHEN** IM 以该请求的 profile version 持久化时发现并发配置已先保存
- **THEN** IM 在返回冲突前请求 Gateway 恢复之前已确认的完整配置，前端不显示候选配置已保存

#### Scenario: 已落盘但 ACK 丢失的配置操作可恢复而不伪装旧值成功
- **GIVEN** IM 已保存一个 Agent 配置 operation，Gateway 已落盘候选配置和 applied receipt
- **WHEN** ACK frame 丢失、连接重连或 IM 在 profile 持久化前重启
- **THEN** IM 使用同一 operation id 重试或查询 Gateway operation status
- **AND** 结果仍不可确认时 API 返回 `503 config_apply_pending`，页面显示正在确认且禁止重复编辑，不把旧 profile 显示为已经保存的当前配置

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

### Requirement: Agent 专属说明只有可见的 Custom Instructions，预览覆盖全部稳定公开配置

Agent owner 通过 Custom Instructions 管理该 Agent 的专属职责或约束；它是公开 profile 唯一会改变专属人设的文本。提示词预览使用已保存或当前草稿的同一 `custom_prompt`、features、tools 与 skills 组装稳定提示词，并明确排除群聊、记忆等仅在运行时才确定的上下文。

#### Scenario: 留空的 Custom Instructions 没有隐藏专属人设
- **WHEN** owner 打开或保存 Agent 配置，Custom Instructions 为空
- **THEN** Agent 不带任何由公开 Agent profile 注入的专属说明

#### Scenario: 预览可检查当前稳定专属说明
- **WHEN** owner 展开提示词预览，或编辑 Custom Instructions 后再次查看预览
- **THEN** 预览包含该 Agent 已保存或待保存的专属说明和已选能力配置
- **AND** 页面明确说明群聊、记忆等运行时内容不在预览内

#### Scenario: 退休字段不能影响升级后的新回复
- **GIVEN** 某旧 profile、conversation snapshot 或 Gateway YAML 仍带 `system_prompt`
- **WHEN** 新版本读取 Agent 配置、同步 profile 或开始下一轮新回复
- **THEN** 该字段不被读取、展示、迁入 Custom Instructions 或传入运行时
- **AND** 已知生产存量的删除由发布操作完成，不属于 IM/Gateway 的自动迁移

### Requirement: Agent 配置保存与聊天实际采用状态分离

IM 持久化 Agent 配置并用 `profile_version` 做乐观锁；保存成功表示新的期望配置可供 Gateway 同步，不表示所有既有聊天已经采用。名称、头像、描述等展示字段不会被解释为模型上下文缓存边界。运行配置真正应用到某个聊天时，由 Gateway 单独上报实际采用事实。

#### Scenario: 运行配置成功保存后由各聊天惰性采用
- **GIVEN** 同一 Agent 有多个既有聊天
- **WHEN** 用户成功保存会改变后续模型请求的配置
- **THEN** IM 持久化新配置并通知 Gateway
- **AND** 不在保存时向所有休眠聊天批量插入配置边界

#### Scenario: 纯展示字段保存不产生运行边界
- **WHEN** 用户只修改 Agent 名称、头像或描述并保存
- **THEN** 配置读取反映新展示信息，但既有聊天不出现上下文缓存边界

#### Scenario: 保存失败不产生实际采用事实
- **WHEN** Agent 配置因版本冲突、校验或网络错误未保存
- **THEN** IM 不产生配置已采用的聊天边界，既有配置保持权威

### Requirement: Agent 配置页可管理 skill_view 工具

前端在 Agent 配置页把 `skill_view` 作为普通可选工具呈现;未显式配置工具白名单的 Agent 默认启用它, 显式白名单仍精确表达用户选择。

#### Scenario: 新建 agent 时默认选中 skill_view
- **WHEN** 用户在 IM 新建 PA agent 并进入工具选择区域
- **THEN** `skill_view` 出现在可选工具列表中
- **AND** 默认处于选中状态

#### Scenario: 用户取消 skill_view 后保存配置
- **WHEN** 用户在 agent 配置页取消选择 `skill_view` 并保存
- **THEN** IM 持久化该 agent 的显式工具白名单
- **AND** 白名单不包含 `skill_view`

#### Scenario: 已显式配置工具白名单的 agent 不自动选回 skill_view
- **GIVEN** agent 已持久化显式工具白名单,且其中不包含 `skill_view`
- **WHEN** 用户再次打开该 agent 配置页
- **THEN** `skill_view` 显示为未选中

### Requirement: PA 产品说明书 skill 可默认启用和关闭

Gateway 当前版本提供产品说明书 skill 时，IM 把它作为普通全局 skill 呈现在 Agent 配置中。新建 Agent 采用 Gateway 声明的默认选择；已有 Agent 的显式 skills 列表保持权威，资源刷新不改写选择。

#### Scenario: 新建 Agent 默认选中产品说明书

- **WHEN** 用户在在线节点下新建 PA Agent 并查看 skill 选择
- **THEN** 产品说明书出现在全局 skill 列表中并默认选中

#### Scenario: 已有显式选择不因升级改变

- **GIVEN** 某 Agent 已保存不含产品说明书的显式 skills 列表
- **WHEN** Gateway 升级、刷新内置资源并重新连接 IM
- **THEN** 该 Agent 原有选择保持不变，产品说明书显示为未选中

#### Scenario: 用户关闭或重新开启产品说明书

- **WHEN** 用户在 Agent 配置中取消或重新选中产品说明书并成功保存
- **THEN** 该 Agent 后续新回复分别不再使用或恢复使用产品说明书

### Requirement: Skill 使用统计 API

浏览器前端可按 agent 查询 skill 使用统计;IM 通过在线 Gateway 读取对应 agent workspace 的运行态使用数据, 离线时以前端可处理的方式降级。

#### Scenario: 查询 agent 的 skill 使用统计
- **WHEN** 浏览器前端请求 `GET /im/v1/agents/:agentId/skills/usage`
- **THEN** 返回该 agent 的所有 skill 使用数据,包含 name、source、state、use_count、last_used_at、session_refs
- **AND** source 至少支持用户创建、历史会话蒸馏、自动创建、自动批量优化与 unknown

#### Scenario: agent 离线时查询 skill 统计
- **WHEN** agent 不在线或 Gateway 无法到达
- **THEN** API 返回离线/空数据语义,前端显示离线提示而非崩溃

### Requirement: HEARTBEAT.md 只读预览与 cron 任务管理经 WS RPC 代理到 gateway（feat-394-M13 决策 G）

IM 进程**绝不**直读 gateway 侧 workspace 文件（IM 与 gateway 可跨机）。相关 endpoint 均经 WS RPC 将请求委托给目标节点 gateway，由 gateway 读写其本地 workspace 后回包，IM 做路由转发与离线降级。

#### Scenario: 获取 HEARTBEAT.md 预览内容
- **WHEN** 前端 `GET /im/v1/agents/{id}/heartbeat-md`
- **THEN** 200 返回 `{content: string, node_online: bool}`；节点在线时 content 为 `HEARTBEAT.md` 内容 （文件不存在则空串）；节点离线或 RPC 超时时 `{content:"", node_online:false}`

#### Scenario: 列 cron 任务经 RPC 代理
- **WHEN** 前端 `GET /im/v1/agents/{id}/cron-jobs`
- **THEN** 200 返回 jobs 数组；节点离线或超时时返回空列表（不报错），不直读 gateway 侧文件

#### Scenario: 删 cron 任务经 RPC 代理
- **WHEN** 前端 `DELETE /im/v1/agents/{id}/cron-jobs/{job_id}`
- **THEN** 204 表示删除成功；节点离线或 RPC 超时或 job_id 不存在均返回 404

### Requirement: Agent 创建必须挂在已绑定且在线的节点下,workspace_root 由节点分配

前端在节点下创建 Agent(`POST /im/v1/nodes/{node_id}/agents`):IM 校验该节点已绑定、归属当前 owner; 经网关 `agent.create` 由节点分配并回传 `workspace_root`,IM 持久化为 `AgentProfile`。未知节点在 owner 门禁处 404,重复 `agent_id` 409。

#### Scenario: 在已知节点创建返回带 node_id+workspace_root 的配置
- **GIVEN** 当前 owner 名下一个已知节点 `node-1`
- **WHEN** 前端 `POST /im/v1/nodes/node-1/agents {agent_id, display_name, skills, tool_allowlist, ...}`
- **THEN** 201 返回与 `GET .../config` 同形的配置体,`node_id == "node-1"`、`workspace_root` 为节点回传值、`workspace_is_default` 反映是否默认路径、`profile_version == 1`

#### Scenario: 重复 agent_id 与未知节点被拒
- **WHEN** 前端以已存在的 `agent_id` 再次创建
- **THEN** 409 `{detail:"agent_id already exists"}`
- **WHEN** 前端向不存在的 `node_id` 创建
- **THEN** 404 `{detail:"node_id not found"}`(owner-scope 门禁先于网关派发拦下)

### Requirement: 桌面 Agent 页面提供连续导航，并保护新建草稿

桌面端从 Agent 列表或节点入口进入新建页，以及打开或切换既有 Agent 详情时，保持 Agent 导航栏。详情请求处于 loading 或 initial error 时，导航栏仍可用，内容区显示局部 loading/error 状态与可重试操作；移动端保持单栏流程。用户一旦编辑新建表单，任何站内离开操作都必须先确认，避免草稿因误触丢失。

#### Scenario: 桌面端两个新建入口保持 Agent 导航
- **WHEN** 用户在桌面端打开 `/settings/agents/new` 或 `/settings/nodes/{node_id}/agents/new`
- **THEN** 新建页显示已有 Agent 的导航栏，并可在未编辑表单时直接切换
- **AND** 移动端仍只显示单栏创建流程

#### Scenario: 桌面端详情切换期间保持 Agent 导航
- **WHEN** 用户在桌面端打开或从一个 Agent 切换到另一个 Agent，详情请求处于 loading 或返回 initial error
- **THEN** Agent 导航栏保持可见且可切换，内容区仅显示该 Agent 的局部 loading/error 状态
- **AND** error 状态提供重试操作，移动端仍只显示单栏内容

#### Scenario: 有草稿时确认站内离开
- **GIVEN** 用户已编辑新建 Agent 表单但尚未提交
- **WHEN** 用户通过 Agent 导航、取消、应用导航、用户菜单或浏览器后退离开页面
- **THEN** 页面要求确认退出，取消确认后保留当前草稿
- **AND** 用户确认后才进入原目标

### Requirement: node.register 首见 agent 时以上报种子值落库（bugfix-404-M2 / bugfix-467）

IM 处理 `node.register` 时,对帧中**首次出现**(无既有 profile)的 agent,以帧内种子值落库: workspace_root 取 `agent_workspaces` 上报值(缺失时回落 managed default),skills / tool_allowlist 取 `agent_skills` / `agent_tool_allowlist` 上报值(帧未携带或单 agent 值非法时按空落库,兼容旧帧; 单 agent 值内混入非法项时仅丢弃非法项)。已存在 profile 的 agent,其各字段保持既有值不被注册改写(重连重发幂等),以保护用户经配置更新(含特意清空)后的收敛。

#### Scenario: 首见 agent 用上报值落库
- **GIVEN** IM 中无 agent X 的 profile
- **WHEN** 收到 `node.register`,`agent_workspaces["X"]` 为非默认绝对路径 P, `agent_skills["X"]` 为技能列表 S,`agent_tool_allowlist["X"]` 为工具列表 T
- **THEN** agent X 的 profile 落库 workspace_root=P、skills=S、tool_allowlist=T, `GET /im/v1/agents` 广播 P 且 `workspace_is_default=false`

#### Scenario: 已存在 profile 不被重注册改写
- **GIVEN** agent X 的 profile 已存在(含用户特意清空的 skills / tool_allowlist)
- **WHEN** 再次收到 `node.register`(无论帧内上报何值)
- **THEN** profile 的 workspace_root / skills / tool_allowlist 均保持既有值

#### Scenario: 帧未带种子字段退回默认与空(旧帧兼容)
- **GIVEN** IM 中无 agent Y 的 profile
- **WHEN** 收到不含 `agent_workspaces` / `agent_skills` / `agent_tool_allowlist` 字段的 `node.register`
- **THEN** agent Y 的 workspace_root 按 managed default 落库,skills / tool_allowlist 落库为空

### Requirement: agent workspace_root 创建后不可经配置更新修改（bugfix-404-M2）

agent 的 workspace_root 在创建时确定(`agent.create` 由节点分配 / `node.register` 种子),update config 接口不含该字段(请求中出现也被忽略),且任何配置更新都不改变已存的 workspace_root。

#### Scenario: 配置更新不重置 workspace_root
- **GIVEN** agent X 的 profile workspace_root 为非默认路径 P
- **WHEN** 调用 update config 接口修改其他字段(如 custom_prompt),payload 不含 workspace_root
- **THEN** 返回成功,workspace_root 仍为 P

#### Scenario: update config 携带 workspace_root 被忽略
- **GIVEN** agent X 的 profile workspace_root 为 P
- **WHEN** 调用 update config 接口,payload 含 `workspace_root: Q`(Q ≠ P),其余字段合法
- **THEN** 返回成功,其余字段按 payload 更新,workspace_root 仍为 P

### Requirement: 每个 AgentProfile 一一对应一个 IM users 行,响应恒带非空 user_id

每个 `AgentProfile` 有且只有一个 `users.username = "agent:" + agent_id` 的行(创建时同事务建,历史缺失者读路径 lazy bootstrap)。因此前端只要看到一个 agent 行,就能拿到稳定非空的 `user_id`,据此把 Agent 作为会话 participant 加入,不会被会话创建端点以"未知 user"400 拒绝。

#### Scenario: 列 agent 恒带可作 participant 的 user_id
- **WHEN** 前端 `GET /im/v1/agents`
- **THEN** 每个 agent 行带非空 `user_id`;以该 `user_id` 作 `participant_ids` 创建 direct 会话被接受

### Requirement: 浏览器经用户维 WebSocket 收事件流,鉴权后只回放本租事件

浏览器经 `/im/ws/user` 建用户维事件流;身份取自 JWT(`?token=<jwt>` 查询串或 `Sec-WebSocket-Protocol:
bearer.<jwt>` 子协议),无 token / 非法 token 立即关闭;身份只认 JWT,单凭 `?user_id=` 不构成信任锚。
握手后发 `{op:"resume", after_event_id:N}` 即回放该用户 owner 范围内、`event_id > N` 的事件帧
(`op:"event"`),跨租事件不投递。`GET /im/v1/sync` 给出会话列表快照 + 全局 `max_event_id`,供前端在
`resync_required` 后对齐游标。浏览器短暂断网或登录凭证自动更新后,使用当前登录身份恢复连接和游标;
账号切换后不再接收前一账号事件。

#### Scenario: 无 token / 非法 token / 仅 user_id 的连接被拒
- **WHEN** 浏览器 `websocket_connect("/im/ws/user")`(无 token,或 `?token=not-a-jwt`,或仅 `?user_id=`)
- **THEN** 连接被服务端关闭(policy violation),收不到事件帧

#### Scenario: 合法 token 连接并 resume 回放本租事件
- **GIVEN** 已授权用户在自己会话里发过消息
- **WHEN** 浏览器以 `?token=<合法 jwt>` 连上后发 `{op:"resume", after_event_id:0}`
- **THEN** 收到 `op:"event"` 帧,含 `message.sent`、`message.delivered` 等 `event_type`;只含本 owner 事件

#### Scenario: sync 返回快照与全局游标
- **WHEN** 前端 `GET /im/v1/sync`
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(>0);前端据其对齐用户流游标

#### Scenario: 长时间登录后短暂断网自动恢复
- **GIVEN** 用户已在 Web IM 持续登录一段时间
- **WHEN** 浏览器网络短暂中断后恢复
- **THEN** 浏览器以当前登录身份恢复用户流,继续收到本账号的新事件,无需退出后重新登录

#### Scenario: 切换账号后只接收新账号事件
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** 浏览器停止接收 A 的事件,后续用户流只交付 B 的 owner 范围事件

### Requirement: 设备绑定把节点归属到当前用户

终端用户在本机发起绑定:`POST /im/v1/bind {action:"start", node_id}` 取得绑定链接,浏览器登录后 `{action:"confirm", bind_id|bind_token}` 确认,确认后该节点及其上 Agent 自动归属当前用户。缺必填字段大声失败(400),不静默。

#### Scenario: start 返回绑定结构
- **GIVEN** 已授权用户、一个已知节点
- **WHEN** 用户 `POST /im/v1/bind {action:"start", node_id}`
- **THEN** 201 返回 `{bind_id, node_id, user_id, status, bind_url, created_at, confirmed_at}`

#### Scenario: 缺动作必填字段返回稳定 400
- **WHEN** `start` 缺 `node_id`
- **THEN** 400 `{detail:"node_id is required for start"}`
- **WHEN** `confirm` 缺 `bind_id` 且缺 `bind_token`
- **THEN** 400 `{detail:"bind_id or bind_token is required for confirm"}`

#### Scenario: 同 owner 重复确认幂等，跨 owner 改绑被拒
- **GIVEN** 节点已绑定 owner A，并保存或运行其外部 channel
- **WHEN** owner A 再次确认该节点
- **THEN** 保持原 owner、Agent 与 channel 数据不变，并可安全重试 channel initialization
- **WHEN** owner B 尝试确认同一节点
- **THEN** 返回 `node_owner_transfer_not_supported`，不迁移 node、Agent、channel、manifest、removal 或 credential key
- **AND** owner B 不能读取或控制 owner A 的 channel

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

新建/编辑 Agent 页需要的 runtime 候选项(skills / tools / models / features)由 IM
**当场**经 gateway WS 向在线节点解析后返回,IM 不在本地持久化该能力目录,也不据 IM 部署机文件系统推断。
节点级 `GET /im/v1/nodes/{id}/capabilities`(agent 尚不存在时用)与 agent 级 `GET /im/v1/agents/{id}/
capabilities` 都把网关返回的 `features` 和每模型安全的 reasoning descriptor 透传给前端。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...],
  platform_default_model, features:[...]}`;网关 payload 无 features 时 IM 返回
  空 `features` 列表(优雅降级)

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}` (可含 `requires_tool`),由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider(例:`codex_oauth:gpt-5.5` → `openai_compat`, `kimiCoding:K2.6` → `anthropic`),供 agent 配置页模型下拉展示格式

#### Scenario: 用户按有效模型能力选择推理设置
- **GIVEN** 创建或编辑页已取得在线节点能力
- **WHEN** 用户选择一个可调推理模型，或当前继承的 platform default 是可调推理模型
- **THEN** 页面只提供该 model descriptor 声明的 levels，并初始选择其 default
- **AND** 继承 default 时保存的 `default_model` 仍为空，只持久化用户明确选择的强度
- **WHEN** 有效模型是 fixed、平台默认不可解析，或目录未声明推理能力
- **THEN** 页面分别显示固定思考、无法确定模型或不可配置说明，不提交不属于有效模型的强度

#### Scenario: 可选模型列表每项携带安全的推理能力
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 若节点将模型声明为可调推理模型，model 含 `{kind:"selectable", default, levels}`；固定思考模型含 `{kind:"fixed"}`；未声明的模型不含 reasoning 字段
- **AND** 响应不含模型静态请求参数或上游密钥

#### Scenario: agent 能力的 skills 项携带 location
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `skills` 列表中每项携带 `location`(SKILL.md 路径,可空;网关 payload 无此字段时降级为空),前端据此对同名不同路径的 skill 分开展示

### Requirement: 节点上线/心跳/超时实时反映到 owner 的浏览器看板

Gateway 上行 `node.register` / `node.heartbeat` 驱动 IM 向**该节点 owner**的浏览器用户流广播 `node.status_changed` 事件(online);心跳超时由 IM 后台扫描翻为 offline 并广播 (`status:"offline", last_error:"heartbeat_timeout"`)。广播严格按 owner 隔离,不泄漏给他租浏览器。

#### Scenario: 节点注册广播 online 给本租浏览器
- **GIVEN** 节点已绑定某 owner,该 owner 一条浏览器用户流在线
- **WHEN** Gateway 上行 `node.register {node_id, agents, capabilities}`
- **THEN** 该 owner 浏览器收到 `op:"event"`、`event_type:"node.status_changed"`、`status:"online"` 帧; 他租浏览器收不到

#### Scenario: 心跳超时翻 offline 并广播
- **GIVEN** 一个 online 节点最近心跳已过期
- **WHEN** IM 后台扫描运行
- **THEN** 节点态翻 `offline`,向本租浏览器广播一帧 `node.status_changed status:"offline"
  last_error:"heartbeat_timeout"`;对已 offline 节点重复扫描是无副作用的幂等(不重复广播)

### Requirement: Agent 通道页统一管理外部 channel 与安全凭据

Agent 详情页的“通道”页只管理可配置的外部 channel，不把内置 Web IM 列为 channel。页面和 REST 资源按 provider 通用建模；本期 provider catalog 只有飞书，且同一 Agent 每种 provider 最多一个实例。飞书向导只给简短准备说明和开放平台入口。App Secret 只在新增或显式替换时提交，服务端立即封装为目标节点公钥可解的密文；list/get/edit 不返回明文或 envelope，Gateway 的普通 `config.yaml` 也不是该凭据的持久化位置。

#### Scenario: 空态与添加入口不展示 Web IM
- **GIVEN** 当前 Agent 没有外部 channel
- **WHEN** 用户打开“通道”页
- **THEN** 页面显示通用空态和“添加通道”，provider picker 当前包含飞书
- **AND** 页面不展示 Web IM；已有飞书时 picker 标记已添加并禁止第二个实例

#### Scenario: 飞书向导提供轻量开放平台入口
- **WHEN** 用户选择添加飞书
- **THEN** 页面简要提示准备应用、Bot 与长连接，并提供 `https://open.feishu.cn/page/launcher?from=backend_oneclick`
- **AND** App ID/App Secret 缺失时在字段处提示，不提交连接请求

#### Scenario: channel 列表读取失败不伪装成空态
- **WHEN** IM 无法读取当前 Agent 的 channel resources
- **THEN** 页面显示失败原因和重试入口，不显示“尚未配置”的空态

#### Scenario: 已保存密钥不可读取且 App ID 换绑必须换密钥
- **GIVEN** 飞书 channel 已保存 App Secret
- **WHEN** 用户再次读取或编辑该 channel
- **THEN** 响应只表明 `secret_configured=true`，不返回明文或 envelope；用户可显式 keep 或 replace
- **AND** App ID 改变时 keep 被拒，必须同时 replace App Secret；通过 IM 新建/更新不会把 secret 写入 Gateway `config.yaml`

#### Scenario: 节点尚未登记 credential public key
- **GIVEN** IM 从未取得目标节点的 credential public key
- **WHEN** 用户新增 channel 或 replace secret
- **THEN** IM 拒绝凭据写入，并说明需让节点至少上线一次以建立安全存储
- **AND** 不把该错误误报成飞书凭据无效

### Requirement: 外部 channel desired state 与 runtime state 分离并自动收敛

IM 持久化用户期望的 channel 配置，Gateway 上报实际连接和诊断状态。保存成功只代表 desired state 已提交；节点离线或 Gateway 尚未应用时显示“配置已保存，等待节点应用”，不能伪造已连接。节点重连后 IM 下发完整 manifest 自动收敛。启用、停用、编辑、重连和删除均经同一资源生命周期；内部 revision 只用于并发/CAS，不作为用户可见版本。删除先保留无凭据 removal receipt，实际停止失败可重试；影子会话和历史不随 channel 删除。

#### Scenario: 节点离线仍可保存并在重连后自动应用
- **GIVEN** Agent 所属节点离线
- **WHEN** 用户新增、编辑、启用、停用或删除 channel
- **THEN** IM 保存期望状态并显示等待节点应用，不显示已连接
- **AND** 节点恢复后无需再次保存或重启，页面自动收敛到 connected、limited、failed 或 disabled

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
- **GIVEN** 用户离线时点击 removal retry，页面显示等待节点
- **WHEN** 节点恢复后用户再次在线 retry，或后台成功令 receipt 消失
- **THEN** 旧离线等待提示立即清除；receipt 消失时相关临时错误也清除，页面进入通用空态

### Requirement: 外部 channel 状态提供可操作的 provider 诊断

连接状态和权限诊断分层展示。基础收发可用但权限不完整时 channel 保持降级可用并标为“连接受限”；页面逐项展示缺失权限、受影响能力和修复方向。只有完整、可信的 provider probe 才能断言某权限缺失；probe 失败或返回信息不完整时显示“权限状态暂时无法确认”，不能猜测缺失。凭据、Bot、长连接或 runtime 失败显示具体可操作原因，节点离线时已观测状态明确标成 last-known。

#### Scenario: 部分权限缺失时降级使用并解释影响
- **GIVEN** 飞书基础消息可收发，但某项租户权限未授权
- **WHEN** 用户查看 channel 状态
- **THEN** 页面显示“连接受限”而不是连接失败，并列出 raw scope、受影响能力和修复方向
- **AND** 缺普通群消息权限时明确说明群聊背景上下文不完整

#### Scenario: probe 不完整时不伪造缺失权限
- **GIVEN** 基础连接可用，但权限接口失败、字段缺失或只得到用户级授权
- **WHEN** 页面展示诊断
- **THEN** 显示“权限状态暂时无法确认”和重试建议，不把任何 scope 断言为确定缺失

#### Scenario: 连接失败与节点离线快照可区分
- **WHEN** App 凭据无效、Bot 未启用、长连接不可用或 runtime 启动失败
- **THEN** 页面显示具体失败原因和下一步，不要求用户查终端日志
- **AND** 节点离线时 connected/limited/failed 只显示为最后已知状态，不冒充当前结论

#### Scenario: 旧 runtime 状态不能逆序覆盖当前状态
- **GIVEN** IM 已接收某 channel 当前配置和 runtime incarnation 的较新状态
- **WHEN** 旧 revision、旧 incarnation 或较小 status sequence 的状态迟到
- **THEN** IM 拒绝旧状态，页面不从已恢复/失败的当前事实回退到旧 connecting 或 connected

### Requirement: 设置 detail 页工具勾选态按存储真值渲染

agent 设置 detail 页的工具面板按存储的 `tool_allowlist` 渲染勾选态:存储为空时全部不亮,不再按 capabilities `default_on` 显示为默认全开;用户勾选/取消直接写显式名单,空名单作为合法配置可表达、可保存、刷新后保持。

#### Scenario: 存储为空全不亮
- **GIVEN** agent 的存储 `tool_allowlist` 为空
- **WHEN** 打开该 agent 的设置 detail 页
- **THEN** 工具面板全部不亮

#### Scenario: 显式清空保存后保持
- **GIVEN** agent 当前启用若干工具
- **WHEN** 用户取消全部勾选、保存、刷新页面
- **THEN** 工具面板保持全部不亮

### Requirement: IM 独立判定 PA 托管默认 workspace

IM 自己维护 PA 托管默认 workspace 的路径规则，不 import `personal_assistant` 或 `agent`：未显式 workspace 的 Agent 为 `~/.nanoassistant/workspaces/<agent-id>/`，并以该路径判定 `workspace_is_default`。IM 只保存和转发这一路径；实际 workspace 文件仍由 Gateway 读写。显式外部 workspace 保持非默认。

#### Scenario: 新建未指定 workspace 的 Agent 使用新托管默认路径
- **WHEN** IM 为在线节点创建一个未显式 workspace_root 的 Agent
- **THEN** 下发、保存并在响应中标记 `~/.nanoassistant/workspaces/<agent-id>/` 为该 Agent 的默认 workspace

#### Scenario: 外部 workspace 不被判为默认
- **GIVEN** Agent profile 保存的是任意显式外部代码仓路径
- **WHEN** IM 返回该 Agent 的配置
- **THEN** `workspace_is_default` 为 false，且原路径不被改写
