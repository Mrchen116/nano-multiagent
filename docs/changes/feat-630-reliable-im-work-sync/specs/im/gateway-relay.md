# IM gateway-relay Specification (delta for feat-630)

## MODIFIED Requirements

### Requirement: Gateway 经 /im/ws/gateway 持久双向连接，协议帧契约稳定

Node Gateway 主动向 IM 建立 `/im/ws/gateway` 持久连接，用于实时消息、回执、必要控制与小体积权威元数据。工作记录批量补传使用独立、按节点授权的同步入口；补传失败不阻断实时沟通。既有上行 `agent.config.boundary` 仍仅在配置边界 durable insert 成功后返回 success ACK。非法、不支持或持久化失败的帧返回稳定错误信封，不静默丢弃或崩连接。

#### Scenario: 非 JSON 帧返回 invalid_message 错误信封
- **WHEN** Gateway 经 `/im/ws/gateway` 发非 JSON 文本
- **THEN** 收到稳定 `invalid_message` 错误信封。

#### Scenario: 不支持的消息类型返回 unsupported_message_type
- **WHEN** Gateway 发 `{type:"unknown.type", payload:{}}`
- **THEN** 收到稳定 `unsupported_message_type` 错误信封。

#### Scenario: 配置边界保留 durable ACK 与必要顺序
- **WHEN** Gateway 上行 `agent.config.boundary`
- **THEN** ACK 表示 IM 已完成 durable insert 或幂等命中；同一配置边界及相关操作的因果顺序保持，不因历史工作记录补传而等待。

#### Scenario: 工作记录同步失败不拆实时连接
- **GIVEN** 实时通路仍可用
- **WHEN** 节点工作记录同步请求失败或超时
- **THEN** 消息、回执、停止与权限响应仍可通过实时连接，历史记录可以稍后恢复。

### Requirement: Gateway HTTP 数据操作使用当前注册连接的运行凭据

已授权 Gateway 成功注册后取得绑定当前有效设备身份与 node 的不透明运行凭据，用于消息镜像和附件等机器数据操作。它与真人 access JWT 不互相替代，不授予人的聊天或配置管理权限。仅工作记录专用同步入口允许使用当前有效绑定、账号与设备 epoch 的持久机器身份，不要求实时 WS 在线；该例外不扩展到消息镜像、附件或其他机器数据及真人入口。

#### Scenario: 机器为非管理者的聊天交付图片
- **GIVEN** B 与 A 管理的 Agent 私聊，A 本人不是成员
- **WHEN** A 的 Gateway 用当前运行凭据及所属 Agent 上传或读取该聊天附件
- **THEN** 操作按 node／Agent／聊天关系成功，B 能看到图文交付；A 的普通真人 JWT 仍无法读取 B 的原聊天和附件。

#### Scenario: 运行凭据过期或节点身份不匹配
- **GIVEN** 设备被交接、管理者被停用、连接临时凭据已失效，或请求 Agent 不属于该 node
- **WHEN** 客户端使用旧运行凭据或伪造 node／Agent 关系执行机器操作
- **THEN** 请求被拒，不通过降级为 owner 读取或加入真人成员恢复；除受限 Work 同步入口外，绑定/恢复后的设备凭据只用于同一节点重新注册，其他 HTTP 数据操作仍要求该设备当前注册在线；Work 专用凭据也不能绕过当前 binding、账号和 epoch 撤销。

#### Scenario: shadow 代记不冒充真人
- **GIVEN** Gateway 正在镜像其已有外部来源聊天
- **WHEN** 用运行凭据提交外部真人消息或 Agent 富消息
- **THEN** 沿用原来源身份、幂等及调和语义；普通真人 JWT 不能用同一机器入口冒充 Agent、system 或外部真人。

#### Scenario: 外部镜像核实当前机器管理者
- **WHEN** Gateway 准备或恢复外部消息镜像
- **THEN** 通过当前机器运行凭据查询 `GET /im/v1/gateway/identity`，只取得当前 node_id 与 owner_id，校验节点一致后沿用已有 owner 调和与写入路径。
- **AND** 不使用真人 `/me` 或节点管理列表、不信任本地旧 owner 作为授权证据；真人凭据或失效机器身份不能使用此查询。

#### Scenario: 机器凭据仅限机器数据入口
- **WHEN** 用 Gateway 运行凭据请求账号、策略、设备绑定、完整配置管理或真人用户流
- **THEN** 请求被拒；正常 owner JWT 的管理能力保持不变。

#### Scenario: 自演化创建技能后继续启用自己的技能
- **WHEN** 当前已注册且管理者 active 的 Gateway 为自身节点 Agent 调用 `POST /im/v1/agents/{agent_id}/skills/enable`
- **THEN** 仅接受 profile_version 和要启用的技能 ID，按现有 optimistic locking / Gateway apply 协议合并到已有技能列表，保留工作模式、工具、模型及其他完整配置。
- **AND** 真人凭据、其他节点 Agent、过期版本、停用或已交接机器被拒绝；该入口不授予完整配置、公司策略或他人设备管理权限。

#### Scenario: 实时连接断开时独立补传 Work
- **GIVEN** 节点的当前绑定、账号与设备 epoch 仍有效，实时 WS 暂时断开
- **WHEN** Gateway 使用其持久机器身份调用仅属于本节点的 Work 同步入口
- **THEN** 可以补传和核对本节点工作记录，不因缺少活动 WS 临时凭据而拒绝。

#### Scenario: Work 同步设备被撤销或交接
- **WHEN** 绑定或账号已失效，或设备已交接且旧 epoch 不再有效
- **THEN** 旧机器身份的 Work 上传、查询和未完成分块提交被拒绝，不能恢复旧权限。

#### Scenario: 持久机器身份不能跨用其他入口
- **WHEN** 使用 Work 同步采用的持久机器身份请求消息镜像、附件、账号、完整配置或真人用户流
- **THEN** 请求被拒，其他入口仍执行原本的认证和授权规则。


### Requirement: 已授权更新的切换阶段持久等待新消息

#### Scenario: 切换期间发送和刷新
- **WHEN** 用户向正在切换版本的电脑发送消息并刷新页面
- **THEN** 消息保留并显示等待电脑更新完成，不被普通离线报错要求重发；该电脑恢复后继续处理且不重复回复。

#### Scenario: 多电脑与访问变更
- **WHEN** 消息接收方包含更新中的电脑与其他电脑，或等待期间权限发生变化
- **THEN** 其他电脑继续正常接收；恢复后仍按当前成员资格和设备归属投递，不能借等待绕过权限。

#### Scenario: 普通离线
- **WHEN** 目标电脑未处于有效更新切换过程而离线
- **THEN** 消息成功保存后保留待投递并在同身份节点恢复时自动交付，不以普通离线误报消息未保存，也不冒充正在更新或已可处理。

#### Scenario: 取消与恢复失败
- **WHEN** 更新取消且原节点恢复接入
- **THEN** 主动重放暂存消息，不依赖断线重连。
- **WHEN** 更新进程中断且电脑尚未恢复
- **THEN** 已暂存消息显示电脑恢复后继续处理、无需重发；聊天入口提供恢复提示，不无限显示正常更新；同身份节点恢复后继续投递。

## ADDED Requirements

### Requirement: 已持久保存的消息在节点暂不可达时保留并自动投递

#### Scenario: 中心已保存而节点离线
- **WHEN** 用户发送消息，IM 已持久保存消息和目标投递任务，但目标节点暂不可达
- **THEN** 返回已保存的同一消息，保留待投递状态，不把暂时离线误报为消息未保存
- **AND** 节点恢复后自动投递，重试不产生第二条消息。

#### Scenario: 一个目标暂不可达
- **WHEN** 群聊消息的部分 Agent 不可达，其他目标仍可用
- **THEN** 各目标独立接收和恢复，晚到或重复确认不使已有终态回退，不阻断其他目标。

### Requirement: 实时请求确认与工作同步具有独立恢复边界

#### Scenario: 业务请求确认迟到
- **WHEN** 某请求超时后收到迟到确认，或同类其他请求正在进行
- **THEN** 确认只归属原请求，不误完成其他请求；结果未知的有副作用操作按原身份核对，不盲目重新执行。

#### Scenario: 历史积压与多节点恢复
- **WHEN** 大量历史记录积压或节点同时重连
- **THEN** 节点的正常消息与必要控制仍有处理机会，单节点补传不使其他用户的通信等待其清空历史。
