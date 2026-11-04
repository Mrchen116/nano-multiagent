# Delta — docs/specs/im/auth-tenancy.md

MODIFIED 账号注册/登录走 JWT,刷新令牌轮换且可吊销
- 程序接口继续 JWT refresh 一次性轮换。
- 浏览器登录使用稳定 HttpOnly Cookie，后台续期延长服务器有效期与 Cookie Max-Age 至 30 天；access 保持 15 分钟。
- 同一稳定 Cookie 的并发与重试均可成功，不消费该凭据。退出、撤销、epoch、过期继续拒绝。
- 当前有效旧 JWT Cookie 可重复升级为相同稳定 Cookie，已消费或失效旧 JWT 不复活。
- 保留既有 Origin、Cookie-only、存储、权限与登录成功记录场景。

ADDED 浏览器续期响应丢失恢复
- WHEN 稳定 Cookie 续期响应丢失，随后刷新页面或其他标签页重试
- THEN 使用原 Cookie 恢复，无需输入密码。

MODIFIED refresh 并发、登出与重启
- 程序 refresh 并发至多一次成功，浏览器稳定 Cookie 重试与并发可成功；退出撤销持久保持，正常重启可恢复有效会话。
