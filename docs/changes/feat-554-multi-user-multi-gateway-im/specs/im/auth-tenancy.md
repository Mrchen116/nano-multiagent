# feat-554 — im/auth-tenancy

> 目标: docs/specs/im/auth-tenancy.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## REMOVED Requirements

### Requirement: 数据面 HTTP 路由强制 Bearer 鉴权且按 owner 隔离


## ADDED Requirements

### Requirement: 数据面按登录身份、聊天成员与资源管理归属确定访问

普通真人请求中，除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes / metrics 等)要求合法 Bearer access token;缺失或非法 token 返回 401。聊天列表、消息、历史和受保护附件按当前用户成员关系访问，非成员返回 404；Agent／Gateway 配置与 metrics 保持 owner 管理归属。联系人目录向登录用户开放；全局 Agent Work 的完整读取以 [agent-work](agent-work.md) 为准，不放开原聊天或管理操作。Gateway 机器数据入口另接受绑定当前已注册连接的运行凭据，范围见 [gateway-relay](gateway-relay.md)，不能用于真人账号／配置管理。请求主体身份取自服务端验证的 token,不接受 `?user_id=` 之类的查询参数作为信任锚。

#### Scenario: 无 token 的数据面请求返回 401
- **WHEN** 浏览器前端未带 Bearer 调 `GET /im/v1/me` / `/im/v1/conversations` / `/im/v1/agents` / `/im/v1/nodes` / `/im/v1/metrics/usage`
- **THEN** 全部 401(无 `?user_id=` 捷径)

#### Scenario: 身份取自 token 而非查询参数
- **GIVEN** 已授权用户 alice
- **WHEN** alice `GET /im/v1/me`(或 `PATCH /im/v1/me`,即使带 `?user_id=` 也忽略)
- **THEN** 返回/更新的恒是 token 主体 alice 自己

#### Scenario: 聊天列表按成员关系过滤,非成员读写 404
- **GIVEN** alice 与 bob 各自注册、各建一个会话
- **WHEN** alice `GET /im/v1/conversations`
- **THEN** 只见 alice 参与的会话；若 bob 不在 alice 的会话中，bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404, 向其发消息也 404

#### Scenario: metrics 仅返回调用方 owner 的行
- **WHEN** 已授权用户 `GET /im/v1/metrics/usage`
- **THEN** 返回行的 `owner_id` 全归属该调用方(空列表亦可),不含他租数据

#### Scenario: 跨账号成员可以读取同一个群
- **GIVEN** alice 与 bob 是同一群的成员
- **WHEN** 两人分别用自己的 token 打开群
- **THEN** 都能读取同一群并发言，未入群用户不能访问。
