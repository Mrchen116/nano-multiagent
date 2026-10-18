# IM auth-tenancy Specification (delta for feat-616)

## MODIFIED Requirements

### Requirement: 资源空间固定且叠加原有对象权限

PA 的 Work/配置及所有执行域轨迹始终仅 owner 可读，即使其 profile 在公司资源空间；普通 Agent 的 Work 空间规则不变。

会话、Agent 和任务图创建时取得私人或公司范围，Work/轨迹继承 Agent，附件继承会话。团队批准不迁移私人历史；普通个人 Agent 的执行范围不随 owner 获批扩大。PA 的资源空间同样不被迁移；经 owner 启用的观察是本人当前权限的有界只读投影，合法外部联系是指定会话参与资格，两者均不扩大该 PA 私人资产受众或其他 Agent 的空间权限。无 PA 私密资产驻留的普通节点显式整机交接是普通 Agent 范围变化的唯一例外；PA 驻留节点本期拒绝跨 owner 交接，见 [设备绑定](agents-nodes.md)。

#### Scenario: 两个私人账号
- **WHEN** 一个用户查找、读取、修改或订阅另一私人空间的资源
- **THEN** 拒绝或不返回，不泄露内容；自己的资源正常可用。已有 owner、聊天成员和媒体权限继续叠加。

#### Scenario: 旧库升级与团队批准
- **WHEN** 既有库升级，或一个个人用户获批进入团队
- **THEN** 旧资源保留公司范围、身份与成员状态；新用户的私人历史仍私有。旧 pending/suspended 用户不因升级自动恢复。

### Requirement: 数据面按登录身份、聊天成员与资源管理归属确定访问

PA 受限观察与本人明确授权的任务协助使用独立、可撤销的委托边界，每次仍核本人当前源对象资格。它不更改真人/普通 Agent 的原有 ACL，不冒充真人 actor，不将 owner 权限交给外部聊天或一般 child。

普通真人请求中，除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes / metrics 等)要求合法 Bearer access token 和有效账号（个人空间可用或公司 active），再核对资源空间;缺失或非法 token 返回 401。默认聊天列表按成员关系；详情、消息、历史与受保护附件同时核对资源空间及会话可见范围：有公司资格的用户可读公司空间公开群，私密群与私聊仅成员可读，无资格返回 404；写入还须未解散会话的成员资格；Agent／Gateway 配置与 metrics 保持 owner 管理归属。联系人目录返回自己及私人助手，以及获准加入公司的成员、公司助手和符合 PA 联系策略的同公司个人助手；可联系个人助手不授予其私密资料/Work 资格；全局 Agent Work 的完整读取以 [agent-work](agent-work.md) 为准，不放开原聊天或管理操作。Gateway 机器数据入口另接受绑定当前已注册连接的运行凭据，范围见 [gateway-relay](../../../../specs/im/gateway-relay.md)，不能用于真人账号／配置管理。请求主体身份取自服务端验证的 token,不接受 `?user_id=` 之类的查询参数作为信任锚。

#### Scenario: 无 token 的数据面请求返回 401
- **WHEN** 浏览器前端未带 Bearer 调 `GET /im/v1/me` / `/im/v1/conversations` / `/im/v1/agents` / `/im/v1/nodes` / `/im/v1/metrics/usage`
- **THEN** 全部 401(无 `?user_id=` 捷径)

#### Scenario: 身份取自 token 而非查询参数
- **GIVEN** 已授权用户 alice
- **WHEN** alice `GET /im/v1/me`(或 `PATCH /im/v1/me`,即使带 `?user_id=` 也忽略)
- **THEN** 返回/更新的恒是 token 主体 alice 自己

#### Scenario: 聊天列表按成员关系过滤，读取区分可见范围
- **GIVEN** alice 与 bob 各自注册并获准加入公司、各建一个私聊或私密群
- **WHEN** alice `GET /im/v1/conversations`
- **THEN** 只见 alice 参与的会话；若 bob 不在 alice 的会话中，bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404, 向其发消息也 404

#### Scenario: metrics 仅返回调用方 owner 的行
- **WHEN** 已授权用户 `GET /im/v1/metrics/usage`
- **THEN** 返回行的 `owner_id` 全归属该调用方(空列表亦可),不含他租数据

#### Scenario: 跨账号成员可以读取同一个群
- **GIVEN** alice 与 bob 是同一群的成员
- **WHEN** 两人分别用自己的 token 打开群
- **THEN** 都能读取同一群并发言，未入群用户只有在公开群中可读，仍不能发言。

#### Scenario: 公司资格不扩大对象权限
- **WHEN** 已登录但 pending 或 suspended 的真人访问公司数据，或失去资格的 owner 名下机器继续请求
- **THEN** 被拒绝；批准成为 active 后仍按会话可见范围、成员写入资格及配置 owner 判断，管理员也不自动取得他人私聊与设备管理权。
