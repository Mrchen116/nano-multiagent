# IM auth delta

## MODIFIED Requirements

### Requirement: 账号注册/登录走 JWT,程序刷新令牌轮换且浏览器会话稳定可吊销

程序客户端经 `/im/v1/auth/*` 注册/登录获得一对令牌(短期 access + 长期 refresh);浏览器通过明确的浏览器会话模式取得内存 access 与稳定的 HttpOnly 会话 Cookie；程序 refresh 一次性轮换，浏览器续期只延长会话期限；退出后对应会话立即失效。错误凭证大声失败(401/拒绝),不静默成功,也不泄漏用户是否存在。

#### Scenario: 注册返回令牌对且密码经哈希,弱口令/重名被拒
- **WHEN** 终端用户 `POST /im/v1/auth/register {username,password,display_name,locale?}`
- **THEN** 201 返回 `{access_token, refresh_token, user}`,`user` 含 `id/username/display_name/owner_id`且不泄漏密码哈希;注册密码至少 8 个字符且最多 72 UTF-8 字节，超出边界或用户名重复时注册失败(不创建用户)；浏览器在本地阻止可判定的无效输入，服务端相同拒绝映射为密码字段的本地化修正提示，不误报服务故障

#### Scenario: 登录凭证错误返回 401 且不区分"用户不存在"与"密码错"
- **WHEN** 终端用户以错误密码或未知用户名 `POST /im/v1/auth/login`
- **THEN** 401(同一种失败语义,避免存在性预言机);凭证正确时返回新令牌对

#### Scenario: 程序 refresh 轮换令牌,旧 refresh 失效;登出吊销 refresh
- **WHEN** 程序客户端 `POST /im/v1/auth/refresh` 用合法 JSON refresh
- **THEN** 返回新 access+refresh,且原 refresh 再次使用被拒;`POST /im/v1/auth/logout` 后该 refresh 也被拒

#### Scenario: 保留运行身份不可用于真人注册
- **WHEN** 用户注册时，用户名去除首尾空白后等于 `system`，或以 `agent:`、`shadow:` 开头
- **THEN** 注册被拒且不创建账号，不能通过注册取得系统、Agent 或外部影子发送者身份；普通用户名继续按原注册规则处理。

#### Scenario: 注册不等于取得公司资格
- **WHEN** 新真人账号注册成功
- **THEN** 返回令牌、可用的个人空间和公司 none 状态；个人数据与绑定立即可用，公司资源在主动申请并获批前不可见；系统、Agent 和 shadow 身份不经真人公开注册取得公司资格。

#### Scenario: refresh 并发、登出与重启
- **WHEN** 程序客户端同一 refresh 并发消费、登出后使用或服务正常重启后重试已消费令牌
- **THEN** 至多一次轮换成功，已消费或吊销状态持久保持；登出后的对应会话不能继续读公司数据。

#### Scenario: 浏览器令牌保存与页面恢复
- **WHEN** 浏览器以 `X-IM-Session: browser` 和许可 Origin 调用注册、登录或刷新
- **THEN** 响应仅含 access_token 与 user，refresh 通过 host-only、HttpOnly、SameSite=Strict Cookie 传送；HTTPS 部署带 Secure，页面可读持久存储不保存任何会话令牌。
- **AND** 刷新页面及同源多标签续期通过 Cookie 恢复有效会话，保留稳定 Cookie、退出、成员停用和临时故障重试语义。

#### Scenario: 登录页恢复已有会话
- **WHEN** 用户打开或刷新 /login，未主动退出且浏览器保留有效会话
- **THEN** 自动恢复并进入 /chat；账号需准入处理时进入 /membership。没有有效会话才显示登录表单，临时服务故障显示重试入口，主动退出显示登录表单。

#### Scenario: 三十天滚动续期与成功登录记录
- **WHEN** 用户登录或成功续期
- **THEN** refresh 有效期与浏览器 Cookie 有效期从本次成功起为 30 天，短期 access 保持原有效期，已有有效会话在下次续期时取得新期限。
- **AND** IM 持久保存每账号最近 10 次密码登录成功的时间及客户端 User-Agent（最长 512 字符）。注册、失败登录和自动续期不产生成功登录记录；设备信息缺失时保存空字符串，不阻断登录。

#### Scenario: 浏览器 Cookie 的跨站与原生接口边界
- **WHEN** 非许可或缺少 Origin 的浏览器模式请求试图登录、注册、刷新或登出
- **THEN** 拒绝且不更改 Cookie 会话；无浏览器标记的程序接口只接受显式提供的 refresh，不读取 Cookie、不设置 Cookie，继续使用 JSON token pair。

#### Scenario: 浏览器续期响应丢失后恢复
- **WHEN** 有效稳定 Cookie 发起续期，响应丢失或页面关闭，随后刷新页面或其他标签页用原 Cookie 重试
- **THEN** 继续恢复会话，无需输入密码；每次成功续期保持凭据不变，并将服务端及浏览器期限延长为 30 天。

#### Scenario: 稳定会话重启与失效
- **WHEN** 沿用同一数据库和配置重启 IM，浏览器再次打开 /login
- **THEN** 有效 Cookie 自动恢复 /chat；主动退出、撤销、认证 epoch 变化、过期或篡改的 Cookie 被拒绝。

#### Scenario: 已有浏览器 JWT Cookie 升级
- **WHEN** 当前仍有效的旧 JWT Cookie 首次续期，或升级响应丢失后重试
- **THEN** 返回相同稳定 Cookie；已被消费、过期或撤销的旧凭据保持拒绝，此类浏览器需要重新登录一次。
- **AND** 稳定 Cookie 及已升级会话的旧 JWT 均不能通过程序 JSON refresh 接口消费。

