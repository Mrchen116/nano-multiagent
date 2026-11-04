# Stable browser sessions

## 整体思路

浏览器使用稳定的 host-only HttpOnly Cookie，内容为现有随机 session_id 与随机 secret，数据库只保存 secret 的 SHA-256。复用 auth_sessions、expires_at、revoked、epoch 和现有 access JWT 校验。新增 browser_session 标记，默认 0，用于阻止稳定浏览器会话再走程序 refresh 接口。程序客户端继续现有 JWT 一次性轮换。

稳定 Cookie 不自带固定 JWT 到期时间，服务器 expires_at 与 Cookie Max-Age 每次续期滚动 30 天。短期 access 仍为 15 分钟。响应丢失仅使浏览器 Cookie 的本地剩余期限较短，原 secret 仍有效，可继续重试。

## 数据与接口

auth_sessions 新增 browser_session INTEGER NOT NULL DEFAULT 0。schema.sql 定义新表状态，db.ts 按既有加列机制升级现有数据库，重复启动幂等，无人工一次性迁移。

Identity 增加浏览器凭据验证、refreshBrowser 和 logoutBrowser。旧三段 JWT 用现有签名、过期、epoch、当前 refresh_hash 全部验证；仅浏览器升级入口允许会话已标记 browser_session。升级保持原 jti 与 hash，返回 session_id.jti，随后重复升级返回同一值。因此首次升级响应丢失也不会再次消费旧凭据。过期、已消费和已撤销的旧 JWT 继续被拒绝，不恢复历史失步会话。

新稳定 Cookie 为两段，仅接受 browser_session=1 的有效会话和相同 secret hash。续期只更新 expires_at 与 browser_session，不改变 secret/hash。新浏览器登录和注册完成现有会话创建后转换成稳定 Cookie，返回原有 {access_token,user} 结构。程序接口仍返回 JWT pair，不接受稳定 Cookie；已升级会话的旧 JWT 不可再通过程序 refresh 接口消费。

logoutBrowser 与原 logout 复用同一撤销事务，删除会话 ticket。成员停用、epoch、WebSocket ticket 与请求权限门禁沿用既有有效会话校验。Cookie 的 Origin、SameSite=Strict、Secure、HttpOnly 和 Cache-Control 继续执行现有边界。

## 验证与交付

无前端视觉变化，无 prototype，无 Agent Context 影响。单 M1-session，依赖无，并行组无。

| Milestone | 文件范围 | 退出标准 |
|---|---|---|
| M1-session | identity.ts、identity-routes.ts、db.ts、schema.sql、identity.test.ts、auth-tenancy.md | [worker] 浏览器响应丢失重试/并发、有效旧 JWT 重复升级、过期/篡改/epoch/撤销和原生轮换测试通过；现有数据库加列重启幂等。[reviewer] 隔离 Chrome 真实登录后续期响应丢失仍能刷新 /login 恢复 /chat；重启恢复；主动退出返回密码表单。 |

隔离 IM 与专用测试账号足以验证本次身份协议，不启动 Agent/模型服务。原生语义由真实 HTTP JSON 接口验证，不变更 iOS UI。独立 code-review/verifier 核对协议及 delta；独立产品 reviewer 验证浏览器旅程。成功日志不作为所有历史掉线触发条件已确认的证据。

## 关键决策

稳定凭据在浏览器自动续期时不轮换。程序客户端维持一次性轮换。完整 delta 见 specs/im/auth-tenancy.md。

## Changelog

- 8ece8ad0e 实现稳定浏览器凭据、现有数据库加列、重复升级与验证；无设计偏离。
