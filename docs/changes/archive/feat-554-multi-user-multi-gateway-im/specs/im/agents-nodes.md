# feat-554 — im/agents-nodes

> 目标: docs/specs/im/agents-nodes.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## MODIFIED Requirements

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

新建/编辑 Agent 页需要的 runtime 候选项（skills / tools / models / features）由 IM **当场**经 gateway WS 向在线节点解析后返回，IM 不在本地持久化该能力目录，也不据 IM 部署机文件系统推断。节点级 `GET /im/v1/nodes/{id}/capabilities`（agent 尚不存在时用）与 agent 级 `GET /im/v1/agents/{id}/capabilities` 都把网关返回的 `features` 和每模型安全的 reasoning descriptor 透传给前端；节点级响应另透传可选的 `default_workspace_template`，供创建页展示该 Gateway 的默认路径，IM 不自行推导。Skill 候选的 `location` 和可选 `source_group` 亦由 Gateway 解析；IM 只透传，不直读 Gateway Workspace。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...], platform_default_model, default_workspace_template?, features:[...]}`；网关 payload 无 features 时 IM 返回空 `features` 列表（优雅降级）

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}`（可含 `requires_tool`）,由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider（例：`codex_oauth:gpt-5.5` → `openai_compat`，`kimiCoding:K2.6` → `anthropic`）,供 agent 配置页模型下拉展示格式

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

## REMOVED Requirements

### Requirement: 浏览器经用户维 WebSocket 收事件流,鉴权后只回放本租事件


## ADDED Requirements

### Requirement: 浏览器经用户维 WebSocket 接收和重放当前成员事件

浏览器经 `/im/ws/user` 建用户维事件流;身份取自 JWT(`?token=<jwt>` 查询串或 `Sec-WebSocket-Protocol:
bearer.<jwt>` 子协议),无 token / 非法 token 立即关闭;身份只认 JWT,单凭 `?user_id=` 不构成信任锚。
握手后发 `{op:"resume", after_event_id:N}` 即回放该用户当前参与聊天范围内、`event_id > N` 的事件帧
(`op:"event"`),非成员聊天事件不投递；个人节点／配置事件仍只向 owner 发送。`GET /im/v1/sync` 给出会话列表快照 + 全局 `max_event_id`,供前端在
`resync_required` 后对齐游标。浏览器短暂断网或登录凭证自动更新后,使用当前登录身份恢复连接和游标;
账号切换后不再接收前一账号事件。

#### Scenario: 无 token / 非法 token / 仅 user_id 的连接被拒
- **WHEN** 浏览器 `websocket_connect("/im/ws/user")`(无 token,或 `?token=not-a-jwt`,或仅 `?user_id=`)
- **THEN** 连接被服务端关闭(policy violation),收不到事件帧

#### Scenario: 合法 token 连接并 resume 回放成员事件
- **GIVEN** 已授权用户在自己会话里发过消息
- **WHEN** 浏览器以 `?token=<合法 jwt>` 连上后发 `{op:"resume", after_event_id:0}`
- **THEN** 收到 `op:"event"` 帧,含 `message.sent`、`message.delivered` 等 `event_type`;仅包含当前身份可访问的事件

#### Scenario: sync 返回快照与全局游标
- **WHEN** 前端 `GET /im/v1/sync`
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(>0);前端据其对齐用户流游标

#### Scenario: 长时间登录后短暂断网自动恢复
- **GIVEN** 用户已在 Web IM 持续登录一段时间
- **WHEN** 浏览器网络短暂中断后恢复
- **THEN** 浏览器以当前登录身份恢复用户流,继续收到本账号的新事件,无需退出后重新登录

#### Scenario: 切换账号后只接收新账号事件
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** 浏览器停止接收 A 的事件,后续用户流只交付 B 当前成员范围内的聊天事件及其个人事件

### Requirement: 登录用户可发现人和 Agent，管理配置保持个人归属

#### Scenario: 从目录直接发起聊天
- **WHEN** 登录用户按名字或稳定 ID 搜索联系人
- **THEN** 可辨认真人与 Agent 并直接私聊，不要求已有 Gateway、好友申请或管理者逐人授权；无匹配时显示空结果。

#### Scenario: 公开 Agent 资料与配置分开
- **GIVEN** Agent 由另一人管理
- **WHEN** 用户浏览该 Agent 资料
- **THEN** 能看到名字、管理者、设备名、在线状态及工作模式，能发消息，全局 Agent 可进入 Work；不能读取完整配置、凭据或保存管理修改。

#### Scenario: 一个人多 Gateway，单台离线
- **WHEN** 用户绑定多台 Gateway，其中一台离线
- **THEN** 可辨认各 Agent 所属设备与在线状态，其余设备和人际沟通正常；设备及其 Agent 仍只有原管理者管理。
