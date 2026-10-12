## MODIFIED Requirements

### Requirement: 账号注册/登录走 JWT,刷新令牌轮换且可吊销

程序客户端经 `/im/v1/auth/*` 注册/登录获得一对令牌(短期 access + 长期 refresh);浏览器通过明确的浏览器会话模式取得内存 access 与 HttpOnly refresh Cookie;refresh 一次性轮换,旧 refresh 轮换或登出后立即失效。错误凭证大声失败(401/拒绝),不静默成功,也不泄漏用户是否存在。

#### Scenario: 注册返回令牌对且密码经哈希,弱口令/重名被拒
- **WHEN** 终端用户 `POST /im/v1/auth/register {username,password,display_name,locale?}`
- **THEN** 201 返回 `{access_token, refresh_token, user}`,`user` 含 `id/username/display_name/owner_id`且不泄漏密码哈希;注册密码至少 8 个字符且最多 72 UTF-8 字节，超出边界或用户名重复时注册失败(不创建用户)；浏览器在本地阻止可判定的无效输入，服务端相同拒绝映射为密码字段的本地化修正提示，不误报服务故障

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
- **THEN** 返回令牌、可用的个人空间和公司 none 状态；个人数据与绑定立即可用，公司资源在主动申请并获批前不可见；系统、Agent 和 shadow 身份不经真人公开注册取得公司资格。

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

### Requirement: Web 认证入口在提交前说清规则并给出可行动反馈

注册与登录页在未登录状态下提供一致、可本地化的表单反馈；能在当前字段修正的问题不伪装成笼统服务失败，服务异常也不伪装成输入错误。

#### Scenario: 认证入口延续当前 Web IM 设计语言
- **WHEN** 用户在桌面或手机打开注册或登录页
- **THEN** 页面以当前 nano IM 的品牌、色彩、字体、图标、表面层级和交互状态呈现主要认证任务
- **AND** 手机窄屏重排为自然单列，不将桌面布局等比缩小或产生水平滚动
- **AND** 较矮视口下内容变高时可纵向滚动到主操作与页脚

#### Scenario: 注册规则在输入前可见
- **WHEN** 未登录用户打开注册页
- **THEN** 页面明确区分必填项和可选显示名，并在密码附近告知至少 8 位
- **AND** 用户可主动显示或隐藏密码，而不改变已输入内容

#### Scenario: 可本地判定的输入问题原位反馈
- **WHEN** 用户提交必填项为空的认证表单，或提交包含短密码的注册表单
- **THEN** 页面在对应字段原位告知修正方式，将焦点放到第一个问题，且不发出必然失败的认证请求
- **AND** 用户编辑有误字段后，与旧值相关的反馈消失

#### Scenario: Unicode 输入按服务端字符限制处理
- **WHEN** 用户在认证字段输入包含 Unicode 字符的内容
- **THEN** 页面按与服务端一致的字符语义判断长度，限制内的输入不会被浏览器提前截断
- **AND** 超过服务端字符上限时才在对应字段原位反馈，并阻止必然失败的认证请求

#### Scenario: 认证拒绝与服务异常可区分
- **WHEN** 注册用户名重复、登录凭据错误，或认证服务无法完成请求
- **THEN** 重名在用户名原位反馈，错误凭据不区分用户名与密码，服务异常则显示不同的可重试提示
- **AND** 失败不清空其他已输入内容

#### Scenario: 服务端拒绝可修正的输入
- **WHEN** 认证服务拒绝一项可由用户修正的输入
- **THEN** 页面使用当前语言在受影响字段告知修正方式
- **AND** 不向用户直接暴露服务端内部错误原文

#### Scenario: 未登录用户切换语言
- **WHEN** 用户在注册或登录页切换中文与英文
- **THEN** 规则、反馈和提交状态立即改用新语言，已输入内容保留
- **AND** 新语言在后续打开认证页时继续生效

#### Scenario: 辅助技术定位认证输入错误
- **WHEN** 键盘或辅助技术用户提交无效认证表单
- **THEN** 字段状态、可见文案和焦点变化使用户能定位第一个问题
- **AND** 密码显隐与提交状态有明确的可读名称

#### Scenario: 认证请求处理中
- **WHEN** 一份有效认证表单正在提交
- **THEN** 页面清晰告知处理状态，并阻止重复提交
- **AND** 用户仍可切换语言，处理状态立即使用新语言

#### Scenario: 注册成功进入个人首次设置
- **WHEN** 服务成功创建账号
- **THEN** 页面保存新会话并进入首次设置，无需再次输入凭据；因设备绑定而注册时保留绑定深链，确认后可继续设置

#### Scenario: 登录成功返回原始深链
- **GIVEN** 用户因访问带查询条件或页内锚点的受保护位置而进入登录页
- **WHEN** 用户成功登录
- **THEN** 个人空间可用或有效公司成员返回完整的安全站内原始位置，路径、查询条件与页内锚点都保留；无个人空间的旧待批准或停用账号先显示本人状态，不提前显示公司缓存

#### Scenario: 暂时冷却可以恢复
- **WHEN** 认证请求被限流
- **THEN** 当前语言告知等待时间和重试方法，保留已填写的非敏感表单状态，不伪装成密码错误或永久禁用。

### Requirement: 数据面按登录身份、聊天成员与资源管理归属确定访问

普通真人请求中，除 `/im/v1/auth/*` 外,所有数据面路由(`me` / conversations / messages / agents / nodes / metrics 等)要求合法 Bearer access token 和有效账号（个人空间可用或公司 active），再核对资源空间;缺失或非法 token 返回 401。聊天列表、消息、历史和受保护附件按资源空间及当前用户成员关系访问，非成员返回 404；Agent／Gateway 配置与 metrics 保持 owner 管理归属。联系人目录只返回自己及私人助手，以及获准加入公司的成员和公司助手；全局 Agent Work 的完整读取以 [agent-work](agent-work.md) 为准，不放开原聊天或管理操作。Gateway 机器数据入口另接受绑定当前已注册连接的运行凭据，范围见 [gateway-relay](../../../../../specs/im/gateway-relay.md)，不能用于真人账号／配置管理。请求主体身份取自服务端验证的 token,不接受 `?user_id=` 之类的查询参数作为信任锚。

#### Scenario: 无 token 的数据面请求返回 401
- **WHEN** 浏览器前端未带 Bearer 调 `GET /im/v1/me` / `/im/v1/conversations` / `/im/v1/agents` / `/im/v1/nodes` / `/im/v1/metrics/usage`
- **THEN** 全部 401(无 `?user_id=` 捷径)

#### Scenario: 身份取自 token 而非查询参数
- **GIVEN** 已授权用户 alice
- **WHEN** alice `GET /im/v1/me`(或 `PATCH /im/v1/me`,即使带 `?user_id=` 也忽略)
- **THEN** 返回/更新的恒是 token 主体 alice 自己

#### Scenario: 聊天列表按成员关系过滤,非成员读写 404
- **GIVEN** alice 与 bob 各自注册并获准加入公司、各建一个会话
- **WHEN** alice `GET /im/v1/conversations`
- **THEN** 只见 alice 参与的会话；若 bob 不在 alice 的会话中，bob `GET /im/v1/conversations/{alice 的会话 id}` 返回 404, 向其发消息也 404

#### Scenario: metrics 仅返回调用方 owner 的行
- **WHEN** 已授权用户 `GET /im/v1/metrics/usage`
- **THEN** 返回行的 `owner_id` 全归属该调用方(空列表亦可),不含他租数据

#### Scenario: 跨账号成员可以读取同一个群
- **GIVEN** alice 与 bob 是同一群的成员
- **WHEN** 两人分别用自己的 token 打开群
- **THEN** 都能读取同一群并发言，未入群用户不能访问。

#### Scenario: 公司资格不扩大对象权限
- **WHEN** 已登录但 pending 或 suspended 的真人访问公司数据，或失去资格的 owner 名下机器继续请求
- **THEN** 被拒绝；个人空间可用不授予公司访问；批准成为 active 后仍按资源空间、原聊天成员及配置 owner 判断，管理员也不自动取得他人私聊与设备管理权。

### Requirement: 公司成员资格由管理员批准和停用

#### Scenario: 准入与管理边界
- **WHEN** 真人完成普通公开注册
- **THEN** 立即使用个人空间并绑定自己的设备；从账号/团队入口主动申请后才等待公司管理员批准，批准前不能读取公司联系人、Work、任务；不要求邀请或 Cloudflare 登录。
- **WHEN** active 管理员批准 pending 成员
- **THEN** 成员取得公司资格；普通成员不能批准或停用他人。

#### Scenario: 停用立即覆盖真人与机器
- **WHEN** 管理员停用成员
- **THEN** 撤销其后续公司请求及现有浏览器会话、公司实时访问；旧令牌不能恢复访问。个人空间用户重新登录后可继续个人资源；机器资格按所在资源空间判定，原公司 Agent 不因 owner 还有私人空间而继续公司接入。
- **AND** 保留历史记录和配置，不关机、不自动接管资源；公司空间的 Agent 暂不可用，个人空间的 Agent 保持私人边界，已授权的其他公司成员可继续查看历史共享记录。

## ADDED Requirements

### Requirement: 资源空间固定且叠加原有对象权限

会话、Agent 和任务图创建时取得私人或公司范围，Work/轨迹继承 Agent，附件继承会话。团队批准不迁移私人历史；个人 Agent 的执行范围不随 owner 获批扩大。显式整机交接是 Agent 范围变化的唯一例外，见 [设备绑定](agents-nodes.md)。

#### Scenario: 两个私人账号
- **WHEN** 一个用户查找、读取、修改或订阅另一私人空间的资源
- **THEN** 拒绝或不返回，不泄露内容；自己的资源正常可用。已有 owner、聊天成员和媒体权限继续叠加。

#### Scenario: 旧库升级与团队批准
- **WHEN** 既有库升级，或一个个人用户获批进入团队
- **THEN** 旧资源保留公司范围、身份与成员状态；新用户的私人历史仍私有。旧 pending/suspended 用户不因升级自动恢复。

### Requirement: 已有原生客户端兼容个人账号准入

原生 iOS 使用个人空间或公司 active 判断账号可用，个人账号可以继续聊天和管理自己的账号/设备；公司菜单仍只向 active 公司成员展示。Web 首次设置向导不因此复制到原生客户端。

#### Scenario: 个人账号与旧账号登录原生端
- **WHEN** 个人空间启用的用户在公司 none、pending 或 suspended 状态登录 iOS
- **THEN** 可以进入个人聊天与设备功能；公司未 active 时不展示公司管理入口。
- **AND** 不带个人空间字段的旧账号仍按原公司成员状态判断准入。
