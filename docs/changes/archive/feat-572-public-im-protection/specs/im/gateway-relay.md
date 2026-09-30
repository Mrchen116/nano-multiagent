# IM gateway-relay Specification (delta for feat-572)

## MODIFIED Requirements

### Requirement: Gateway HTTP 数据操作使用当前注册连接的运行凭据

已授权 Gateway 成功注册后取得绑定当前有效设备身份与 node 的不透明运行凭据，用于消息镜像和附件等机器数据操作。它与真人 access JWT 不互相替代，不授予人的聊天或配置管理权限。

#### Scenario: 机器为非管理者的聊天交付图片
- **GIVEN** B 与 A 管理的 Agent 私聊，A 本人不是成员
- **WHEN** A 的 Gateway 用当前运行凭据及所属 Agent 上传或读取该聊天附件
- **THEN** 操作按 node／Agent／聊天关系成功，B 能看到图文交付；A 的普通真人 JWT 仍无法读取 B 的原聊天和附件。

#### Scenario: 运行凭据过期或节点身份不匹配
- **GIVEN** 设备被交接、管理者被停用、连接临时凭据已失效，或请求 Agent 不属于该 node
- **WHEN** 客户端使用旧运行凭据或伪造 node／Agent 关系执行机器操作
- **THEN** 请求被拒，不通过降级为 owner 读取或加入真人成员恢复；绑定/恢复后的设备凭据只用于同一节点重新注册，HTTP 数据操作仍要求该设备当前注册在线。

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
