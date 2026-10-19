# im/auth-tenancy Specification delta

## ADDED Requirements

### Requirement: 双方 Agent owner 对协作私聊有只读观察权

#### Scenario: 有效 owner 读取
- **WHEN** 两个 Agent 的有效 owner 查看其私聊
- **THEN** 双方均可读取，不需要加入成员；管理员和无关账号不因此可读。

#### Scenario: 观察不授权写入
- **WHEN** owner 尝试发送、上传或修改协作聊天
- **THEN** 请求被拒绝，参与者和消息不改变。

#### Scenario: 观察资格失效
- **WHEN** 账号、空间资格或实际 owner 关系失效
- **THEN** 后续读取及实时交付不继续放行。


## MODIFIED Requirements

### Requirement: 数据面按登录身份、聊天成员与资源管理归属确定访问

普通真人请求中，除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes / metrics 等)要求合法 Bearer access token 和有效账号（个人空间可用或公司 active），再核对资源空间;缺失或非法 token 返回 401。默认聊天列表按成员关系及双方 Agent owner 的只读观察资格；详情、消息、历史与受保护附件同时核对资源空间及会话可见范围：有公司资格的用户可读公司空间公开群，私密群和普通私聊仅成员可读；恰含两个同空间 Agent 的私聊还允许双方有效真人 owner 只读观察，无资格返回 404；写入还须未解散会话的成员资格；Agent／Gateway 配置与 metrics 保持 owner 管理归属。联系人目录只返回自己及私人助手，以及获准加入公司的成员和公司助手；全局 Agent Work 的完整读取以 [agent-work](agent-work.md) 为准，不因此放开原聊天或管理操作。Gateway 机器数据入口另接受绑定当前已注册连接的运行凭据，范围见 [gateway-relay](gateway-relay.md)，不能用于真人账号／配置管理。请求主体身份取自服务端验证的 token,不接受 `?user_id=` 之类的查询参数作为信任锚。

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
- **THEN** 可见 alice 参与或有 Agent owner 观察资格的会话；若 bob 既不在 alice 的会话中也无观察资格，bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404, 向其发消息也 404

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

