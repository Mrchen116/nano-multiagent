# im/auth-tenancy.md (delta for feat-796)

## MODIFIED Requirements

### Requirement: 数据面按登录身份、聊天成员与资源管理归属确定访问

普通真人请求中，除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes 等)要求合法 Bearer access token 和有效账号（个人空间可用或公司 active），再核对资源空间;缺失或非法 token 返回 401。默认聊天列表按成员关系及双方 Agent owner 的只读观察资格；详情、消息、历史与受保护附件同时核对资源空间及会话可见范围：有公司资格的用户可读公司空间公开群，私密群和普通私聊仅成员可读；恰含两个可协作 Agent 的私聊允许双方有效真人 owner 只读观察；一个 PA 与一个真人的私聊允许该 PA 主人按 [personal-agent](personal-agent.md) 只读观察，无资格返回 404；写入还须未解散会话的成员资格，且一对一对象为他人「私有」Agent 时禁止写入；Agent／Gateway 配置保持 owner 管理归属。联系人目录返回本人及本人名下全部可用助手，获准加入公司的有效成员还可发现其他有效公司成员及其设为「团队公开」的普通 Agent 与已激活 PA（隐藏他人设为「私有」的助手）；全局 Agent Work 的完整读取以 [agent-work](agent-work.md) 为准，不因此放开原聊天或管理操作。Gateway 机器数据入口另接受绑定当前已注册连接的运行凭据，不能用于真人账号／配置管理。请求主体身份取自服务端验证的 token,不接受 `?user_id=` 之类的查询参数作为信任锚。

#### Scenario: 无 token 的数据面请求返回 401
- **WHEN** 浏览器前端未带 Bearer 调 `GET /im/v1/me` / `/im/v1/conversations` / `/im/v1/agents` / `/im/v1/nodes`
- **THEN** 全部 401(无 `?user_id=` 捷径)

#### Scenario: 身份取自 token 而非查询参数
- **GIVEN** 已授权用户 alice
- **WHEN** alice `GET /im/v1/me`(或 `PATCH /im/v1/me`,即使带 `?user_id=` 也忽略)
- **THEN** 返回/更新的恒是 token 主体 alice 自己

#### Scenario: 聊天列表按成员关系过滤，读取区分可见范围
- **GIVEN** alice 与 bob 各自注册并获准加入公司、各建一个私聊或私密群
- **WHEN** alice `GET /im/v1/conversations`
- **THEN** 可见 alice 参与或有 Agent owner 观察资格的会话；若 bob 既不在 alice 的会话中也无观察资格，bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404, 向其发消息也 404

#### Scenario: 跨账号成员可以读取同一个群
- **GIVEN** alice 与 bob 是同一群的成员
- **WHEN** 两人分别用自己的 token 打开群
- **THEN** 都能读取同一群并发言，未入群用户只有在公开群中可读，仍不能发言。

#### Scenario: 公司资格不扩大对象权限
- **WHEN** 已登录但 pending 或 suspended 的真人访问公司数据，或失去资格的 owner 名下机器继续请求
- **THEN** 被拒绝；批准成为 active 后仍按会话可见范围、成员写入资格、Agent 公开/私有档位及配置 owner 判断，管理员也不自动取得他人私聊与设备管理权。

### Requirement: 资源空间固定且叠加原有对象权限

会话、Agent 和任务图创建时取得私人或公司范围，附件继承会话。团队批准不迁移私人聊天历史、受保护附件、私有任务图或 PA Work；有效团队成员名下设为「团队公开」的普通 Agent 与 PA 可在公司空间被其他有效成员发现并参与公司会话（普通全局 Agent 在「团队公开」下可由有效团队成员查看 Work），设为「私有」的 Agent 与 PA 则对其他成员隐藏且仅允许在同一 owner 内部会话通信；成员被停用公司资格后，其个人空间的 Agent 立即收回团队可见与联系权，但本人在个人空间内仍可继续使用。显式整机交接仍是改变绑定归属的唯一路径，见 [设备绑定](agents-nodes.md)。

#### Scenario: 两个私人账号
- **WHEN** 一个用户查找、读取、修改或订阅另一私人空间的资源
- **THEN** 拒绝或不返回，不泄露内容；自己的资源正常可用。已有 owner、聊天成员和媒体权限继续叠加。

#### Scenario: 旧库升级与团队批准
- **WHEN** 既有库升级，或一个个人用户获批进入团队
- **THEN** 旧资源保留原空间范围、身份与成员状态；新用户的私人聊天历史与私有任务图仍私有，其设为「团队公开」的助手对团队成员开放协作，设为「私有」的助手保持仅本人及本人名下助手可访问。旧 pending/suspended 用户不因升级自动恢复。
