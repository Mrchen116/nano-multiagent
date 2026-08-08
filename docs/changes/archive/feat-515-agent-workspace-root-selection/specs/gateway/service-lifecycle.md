## MODIFIED Requirements

### Requirement: IM 推送 agent.create 时由节点创建并固定唯一 workspace root

Gateway 处理 IM 下行的 `agent.create` 时，在**本节点**决定 workspace root。未指定 root 的请求
使用节点默认目录；指定 root 的请求在本节点将路径 canonicalize 后校验。新 root 的父目录必须
已存在且可用，Gateway 不创建缺失父目录；已有 target 必须为目录且须由用户在请求中明确确认后
才可采用。Gateway 在初始化前以本地已持久化 agent config 检查 canonical root，确保一个 root
只归属本节点的一个 Agent。成功后，Gateway 建立/补齐工作区、注册 live 路由、持久化本地配置，
并回传非空 canonical absolute `workspace_root` 和 `workspace_is_default`（默认 factory 为 true，
自定义为 false）；已有文件不覆盖。该来源信息随本地 Agent 配置持久化，并在 node register 时
供 IM 镜像，不能由 IM 根据路径字符串重新推导。

#### Scenario: 默认 root 沿用节点分配
- **WHEN** IM 下发的 `agent.create` 未指定 `workspace_root`
- **THEN** Gateway 使用节点默认 workspace factory 创建 Agent、注册 live 路由并回传非空绝对
  `workspace_root` 与 `workspace_is_default == true`

#### Scenario: 节点能力提供默认路径模板供创建页展示
- **WHEN** IM 请求 `node.capabilities`
- **THEN** Gateway 复用默认 workspace resolver 返回 canonical `default_workspace_template`，只把
  Agent ID 位置保留为 `{agent_id}` 占位符
- **AND** 该模板只供页面展示；默认创建仍由 Gateway 在收到 `agent.create` 时重新解析最终路径

#### Scenario: 新自定义 root 只在已有 parent 下创建
- **GIVEN** 下发的自定义 target P 不存在，P 的 canonical parent 已存在、为目录且可用
- **WHEN** Gateway 处理 `agent.create`
- **THEN** Gateway 创建 P 及需要的初始 workspace 内容，持久化 Agent config 并回传 P 的
  canonical absolute path 与 `workspace_is_default == false`

#### Scenario: 不创建缺失或不可用 parent
- **WHEN** 自定义 target 的 canonical parent 不存在、不是目录或无法用于创建
- **THEN** Gateway 不创建 target、不创建缺失 parent、不持久化 Agent config，并在 `agent.created`
  回包中携带对应的结构化 workspace error

#### Scenario: 已有目录先返回确认要求
- **GIVEN** 自定义 target P 已存在且为目录
- **WHEN** `agent.create` 未携带明确的已有目录确认
- **THEN** Gateway 不初始化 P、不写 config、不注册 Agent，回 `agent.created` 的
  `workspace_confirmation_required` error
- **WHEN** 后续请求明确确认 P
- **THEN** Gateway 才初始化缺失的 workspace 默认内容、保留 P 中已有文件，并成功创建 Agent

#### Scenario: 同节点 canonical root 不可重复归属
- **GIVEN** Gateway 本地 config 中 Agent A 已拥有 canonical root P
- **WHEN** 下发为 Agent B 指定 P（包括解析后同 P 的别名路径）
- **THEN** Gateway 不创建或注册 Agent B，回 `workspace_already_assigned` error 并标识 Agent A

#### Scenario: workspace root 创建后不被 IM 镜像改写
- **GIVEN** Gateway 为 Agent X 成功创建并持久化 root P
- **WHEN** 后续 IM 配置同步携带不同的镜像 root Q
- **THEN** Gateway runtime 继续以本地 config 的 P 读写 workspace；不迁移或覆盖 P

### Requirement: 创建 operation 仅用于同一丢失响应的重连恢复

下行 `agent.create` 可带 opaque `create_operation_id`。Gateway 成功创建时把它与 workspace root/provenance
一起持久化，`agent.created` 回包和以后 `node.register.agent_create_operations` 映射均回传同一 id。对于
已经存在的 Agent，Gateway 只接受同一 operation id 的恢复请求；缺失或不同 id 仍为 duplicate create，
不得借常规注册广告产生、替换或刷新 operation。

#### Scenario: Gateway 回显已持久化的 operation
- **GIVEN** IM 下发带 operation X 的 `agent.create`
- **WHEN** Gateway 已写入本地 Agent config
- **THEN** `agent.created` 及随后的 `node.register` 都为该 Agent 回传 X
- **AND** 不同 X 的恢复请求不能改写已持久化 Agent

### Requirement: 会话 JSONL 地址从 durable binding 投影且不阻塞 Gateway 接收循环

Gateway 收到 `session.log.resolve` 时，只从 durable conversation binding 投影
`<workspace>/.nanoassistant/sessions/<kernel-session-id>.jsonl`。Gateway 在 IM receive loop 启动前将
committed binding hydrate 为 copy-on-write 的进程内投影，并在每次 durable binding 更新后发布新 entry；
receive task 只读该投影，不获取 binder threading lock、不查询 SQLite，也不调用 `Path.is_file()`、
`Path.resolve()` 或扫描 workspace。请求在可取消且按 `(agent_id, conversation_id)` coalesce 的任务中执行，
连接关闭只取消其 task，不等待被其他业务持有的 persistence lookup。

缺少 durable binding 时回 `status="missing"`；存在 binding 时回投影地址和 `status="ready"`，即使该
路径的文件状态无法被探测。provider 缺失或 binding/projection 出错时回
`status="unavailable"`，不得伪装为 `missing`。

#### Scenario: 慢或不可用 workspace 不阻塞 control frame
- **GIVEN** Gateway 已开始一个 `session.log.resolve`，其 binding provider 随后不可用
- **WHEN** IM 在该解析完成前下发 heartbeat 或其他 control frame
- **THEN** Gateway 继续处理 control frame，并最终为该解析回 `status="unavailable"`

#### Scenario: 持久化 binding lookup 被占用时 receive 与关闭仍前进
- **GIVEN** 另一 Gateway 业务正持有 `GatewaySessionBinder` 的 binding lookup 和对应 SQLite read
- **WHEN** IM 下发 `session.log.resolve`，随后下发 heartbeat 或 Gateway 开始关闭连接
- **THEN** receive task 只读取已发布的 binding projection，heartbeat 或关闭在该 lookup 释放前完成
- **AND** 已 durable 的 binding 仍返回其 exact JSONL 地址与 `status="ready"`
