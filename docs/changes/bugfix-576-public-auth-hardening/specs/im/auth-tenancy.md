# IM Auth and Tenancy (delta for bugfix-576)

## MODIFIED Requirements

### Requirement: 账号注册/登录走 JWT,刷新令牌轮换且可吊销

程序客户端经 `/im/v1/auth/*` 注册/登录获得一对令牌(短期 access + 长期 refresh);浏览器通过明确的浏览器会话模式取得内存 access 与 HttpOnly refresh Cookie;refresh 一次性轮换,旧 refresh 轮换或登出后立即失效。错误凭证大声失败(401/拒绝),不静默成功,也不泄漏用户是否存在。

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

#### Scenario: 注册不等于取得公司资格
- **WHEN** 新真人账号注册成功
- **THEN** 返回令牌和 pending 状态，只可查看本人状态；系统、Agent 和 shadow 身份不经真人公开注册取得公司资格。

#### Scenario: refresh 并发、登出与重启
- **WHEN** 同一 refresh 并发消费、登出后使用或服务正常重启后重试已消费令牌
- **THEN** 至多一次轮换成功，已消费或吊销状态持久保持；登出后的对应会话不能继续读公司数据。

#### Scenario: 浏览器令牌保存与页面恢复
- **WHEN** 浏览器以 `X-IM-Session: browser` 和许可 Origin 调用注册、登录或刷新
- **THEN** 响应仅含 access_token 与 user，refresh 通过 host-only、HttpOnly、SameSite=Strict Cookie 传送；HTTPS 部署带 Secure，页面可读持久存储不保存任何会话令牌。
- **AND** 刷新页面及同源多标签续期通过 Cookie 恢复有效会话，保留一次性 refresh、退出、成员停用和临时故障重试语义。

#### Scenario: 浏览器 Cookie 的跨站与原生接口边界
- **WHEN** 非许可或缺少 Origin 的浏览器模式请求试图登录、注册、刷新或登出
- **THEN** 拒绝且不更改 Cookie 会话；无浏览器标记的程序接口只接受显式提供的 refresh，不读取 Cookie、不设置 Cookie，继续使用 JSON token pair。

### Requirement: 公网认证限制来源与目标账号滥用

#### Scenario: 分散尝试与共享网络
- **WHEN** 同一来源大量注册/认证，或多个来源持续猜测同一账号
- **THEN** 来源、来源与账号组合以及短时目标账号预算均可触发有界冷却，不因伪造代理头绕过；拒绝不会无限续期，反馈包含重试时间。

#### Scenario: 不跨来源继承长时间失败封禁
- **WHEN** 一个来源对账号连续输错密码后，另一来源尝试正确凭据
- **THEN** 后者不继承该来源约 15 分钟的失败冷却，只受短时目标节流与服务计算容量约束；已登录合法会话不因匿名失败被注销。

## ADDED Requirements

### Requirement: 慢认证和已派发控制等待不串行阻塞无关用户

#### Scenario: 密码计算与无关读取
- **WHEN** 并发密码校验尚未完成，另一已登录用户读取本人或有权访问的公司数据
- **THEN** 读取不必等待校验完成，超出计算容量的认证请求被有界拒绝。

#### Scenario: 等待结果期间撤销
- **WHEN** Gateway 控制命令已发出但结果未返回，管理员停用发起者
- **THEN** 停用和无关读取不必等待控制结果；停用后旧请求不能继续提交新的受保护 IM 副作用或返回受保护结果，已发出的远端动作可能完成；同资源并发不形成互锁。服务内部可在 gate 内清除本请求预建、仍无消息且尚未完成历史复制的空 fork 半成品；此例外不允许删除已有分支或用户内容，不允许复制历史或派发新命令。

### Requirement: 生产浏览器入口提供集中安全响应策略

#### Scenario: HTTPS 页面与资源正常工作
- **WHEN** 用户访问生产 HTTPS Web IM
- **THEN** 前端 HTML 限制脚本、连接与嵌入来源，不允许第三方框架嵌入；响应提供 nosniff、防嵌入和仅当前主机的 HSTS，同时保留正常字体、图片、附件和实时连接。
- **AND** loopback HTTP 开发仍可使用，不通过放宽生产脚本执行或信任任意 Origin 支持开发。
