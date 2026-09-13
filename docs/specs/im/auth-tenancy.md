# IM - Auth and Tenancy Specification

> 对齐: feat-447 / feat-554
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

账号鉴权、聊天成员可见性、资源管理归属和系统策略的 IM 契约。

## Requirements

### Requirement: 账号注册/登录走 JWT,刷新令牌轮换且可吊销

终端用户经 `/im/v1/auth/*` 注册/登录获得一对令牌(短期 access + 长期 refresh);refresh 一次性轮换,旧 refresh 轮换或登出后立即失效。错误凭证大声失败(401/拒绝),不静默成功,也不泄漏用户是否存在。

#### Scenario: 注册返回令牌对且密码经哈希,弱口令/重名被拒
- **WHEN** 终端用户 `POST /im/v1/auth/register {username,password,display_name,locale?}`
- **THEN** 201 返回 `{access_token, refresh_token, user}`,`user` 含 `id/username/display_name/owner_id`且不泄漏密码哈希;口令短于下限或用户名重复时注册失败(不创建用户)

#### Scenario: 登录凭证错误返回 401 且不区分"用户不存在"与"密码错"
- **WHEN** 终端用户以错误密码或未知用户名 `POST /im/v1/auth/login`
- **THEN** 401(同一种失败语义,避免存在性预言机);凭证正确时返回新令牌对

#### Scenario: refresh 轮换令牌,旧 refresh 失效;登出吊销 refresh
- **WHEN** 用户 `POST /im/v1/auth/refresh` 用合法 refresh
- **THEN** 返回新 access+refresh,且原 refresh 再次使用被拒;`POST /im/v1/auth/logout` 后该 refresh 也被拒

#### Scenario: 保留运行身份不可用于真人注册
- **WHEN** 用户注册时，用户名去除首尾空白后等于 `system`，或以 `agent:`、`shadow:` 开头
- **THEN** 注册被拒且不创建账号，不能通过注册取得系统、Agent 或外部影子发送者身份；普通用户名继续按原注册规则处理。

### Requirement: 系统级策略(policies)可读可改,字段集稳定

前端设置页经 `/im/v1/policies` 读写系统级策略(默认模型 / 每 run 最大轮数 / 附件大小上限 / 留存天数 / 审计级别 / 限流);PATCH 整体回写并回显。

#### Scenario: 读写 policies 字段集稳定
- **WHEN** 前端 `GET /im/v1/policies`
- **THEN** 200 响应键恰为 `{default_model, max_turn_per_run, max_attachment_size_mb, retention_days,
  audit_level, rate_limit_per_min}`;`PATCH` 同结构写入并原样回显

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
