# bugfix-576: 公网认证可用性与浏览器会话加固 — 技术方案

> 对齐：[incident.md](incident.md)，基线 `15a0d0f2d`。沿用用户已确认的低复杂性方案。

## Changelog

## 现状分析

### 涉及范围

- `api/public_boundary.py`：所有普通 `/im/v1/` 请求持有 company_gate 至响应头，认证限流在锁内；上传已有短提交保护。
- `application/auth_service.py`、`api/routes/auth.py`、`infra/auth_limits.py`：bcrypt 和 session 创建未拆分；账号失败桶跨来源封禁；计数保存在同一 SQLite。
- `ws/gateway/control.py`、`ws/gateway/work.py`：发送命令后通过 Future 等待结果。`application/agent_config_operations.py` 持有每 Agent 锁跨 RPC，`web_im_service.py` 的 fork 失败清理会写库。
- `frontend/src/features/auth/`：JSON refresh token 和 access 一起保存 localStorage；同标签通过 refresh token 合并续期。账号页更新也直接重建 token pair。
- `app.py`：一个 IM worker/连接注册表；浏览器 WS 校验精确 Origin。前端构建不含内联脚本，样式使用内联 style 和 Google Fonts。

### 既有约束

IM 不 import Agent；保持一个 worker 的 shared SQLite / live registry 契约。保留正在工作的程序客户端 JSON token pair，机器运行凭据独立，不迁移公司数据。撤销必须覆盖后续提交与受保护响应；已提交到远端的动作不能被声称撤回。

### 可复用能力

- 用：AuthSessions 持久 CAS 轮换、整会话撤销、真人 epoch、单次 WS ticket。
- 改：AuthLimits 继续使用原表和固定窗口；增加单桶清理，不建新风控组件。
- 改：公司锁只对真实慢等待让出；不让路由各自发明事务边界。
- 用：现有认证表单、冷却提示、深链、成员状态和缓存清理；不重做 UI。
- 不用：Redis、分布式锁、验证码、MFA、设备指纹、新的第三方依赖或安全配置中心。

### 相关历史

feat-572 建立公司撤销、公网来源边界和设备身份；本次保留其有效安全语义。feat-561 建立原子配置 operation/pending/recovery；本次只调整等待期间的锁持有，不重写配置协议。PR #321 的 HTTPS 跳转与生产拓扑已合并，本次不操作边缘控制台。

## 架构总览

```text
来源限流 → company gate 内的输入/身份快照与准备
                     │
          让出 gate：bcrypt / 已发出 RPC 的结果等待
                     │
          重新取 gate → 复核身份 → 提交/响应

浏览器：内存 access → Bearer 业务请求
        HttpOnly refresh cookie → 带标记及 Origin 的续期 → 原会话 CAS 轮换
程序客户端：显式 JSON refresh → 原会话 CAS 轮换（不读取 cookie）
```

## 关键决策

### 1. 保留默认提交边界，只显式让出慢等待

新增 IM 内部 `infra/company_gate.py`，提供请求级 lease、`await_outside_gate` 和 gate-aware 的局部锁上下文。CompanyBoundary 创建 lease，注入当前数据 principal 的重验证回调；ContextVar 避免把 HTTP Request 传入全部 RPC 层，但 lease 只可由创建它的当前 asyncio task 使用，继承 context 的后台 task 不得释放其锁。

lease 统一持锁状态，响应头释放和 finally 使用它。成功、超时、异常和取消都先重取 gate，再允许调用者继续或处理异常；撤销复核失败则拒绝，不进入受保护提交。异常清理可能写库（fork 删除空分支），不能在 gate 外把异常直接抛给路由。撤销后唯一允许的服务内部清理，是在 gate 内删除本请求刚预建、尚未绑定且仍无消息的空 fork 分支；不复制历史、不删除已有分支或用户消息、不发送新的远端命令。此有限清理不是继续执行用户操作；其他受保护提交仍拒绝。若半成品已非空则保留，不引入补偿或后台清理框架。取消中的重取要完成，不泄露 gate 或让已取消请求继续正常提交。

GatewayControl 所有结果 Future 等待及 GatewayWork permission 等待调用同一 helper。保留 waiter 注册和命令发送在 gate 内；只放开等待结果的部分，既有发送超时仍有界。本次不承诺慢 socket write 完全无影响。返回后的复核拒绝旧 session、suspended owner 和失效机器连接。

配置 operation 等待每 Agent 锁时也让出 gate，避免“请求 A 持 Agent 锁等 gate，请求 B 持 gate 等 Agent 锁”的实际 AB/BA 死锁。局部锁获得后先重取 gate/复核，再访问数据库；失败或取消仍释放已获得的局部锁。等待期间的 pending operation 保留，由既有授权 recovery 处理，不在撤销后自动补偿或提交。

### 2. 密码计算与数据库操作分离，认证不排长队

AuthService 拆出准备和完成接口：gate 内校验字段/读取用户快照；gate 外仅执行 bcrypt；gate 内重新读取用户后建立 session。保留原 `register/login` 服务接口供既有直接调用者，复用相同校验与签发逻辑，不保留两份业务规则。

应用级两个密码计算名额；满额立即 429，Retry-After=1，不等待无界 semaphore 队列。用工作线程执行 bcrypt，名额直到线程真正结束才归还，HTTP 取消不能提前释放计算预算。未知用户也走固定的无效密码 hash 验证，保持有限计算与相同错误语义。登录完成重新核验用户身份、密码 hash 与 epoch；不为校验期间已失效的用户快照签发有效会话。

来源限流先于 company gate 等待。AuthLimits 使用独立连接访问现有 SQLite 文件，避免 gate 外的限流 commit 干扰受保护路由的共享连接事务；计数仍原子、持久、有期限，生命周期在 app 内关闭，无新数据库/服务。

### 3. 限制猜测速率，不用跨来源的长封禁

- 保留来源登录 30 次/300 秒、注册来源 5 次/900 秒和注册总量 100 次/小时。
- 登录失败冷却改为规范化 `source + account`，10 次错误/900 秒；正确登录清除此组合的失败状态。
- 全来源的目标账号最多每秒进入一次密码校验，窗口为 1 秒且拒绝不续期；结合两个全局计算名额限制分散猜测。该桶不按连续失败封禁 15 分钟。
- 同一来源/账号冷却仍可能拒绝该来源的正确密码；另一来源最多遇到短暂目标或服务忙碌，不继承长封禁。高强度分布式攻击仍可能占用机会，本 unit 不宣称完全消除 DDoS。
- 全部 429 复用现有 Retry-After 与用户可见冷却反馈，不显示账号是否存在。无需新挑战、管理员解锁界面或独立调度器。

### 4. 通过明确的浏览器模式复用认证端点

沿用 `/im/v1/auth/{register,login,refresh,logout}`；浏览器统一加 `X-IM-Session: browser`，后端在任何浏览器会话操作前校验 Origin 等于配置的 IM public origin 或显式 `IM_BROWSER_ORIGINS`。缺少/非法 Origin 拒绝，不能从 Host/任意代理头推导可信来源。

- 浏览器 login/register/refresh 响应只有 `{access_token,user}`，refresh 从不返回给页面 JS。
- `im_refresh` 为 host-only、Path=/、HttpOnly、SameSite=Strict；配置 public URL 为 HTTPS 时必须 Secure，max-age 与服务端 refresh TTL 一致。loopback HTTP 开发允许非 Secure Cookie，不放宽生产。
- 浏览器 refresh/logout 提交空 JSON，由后端只读取 Cookie；不接受此模式通过 body 提供 refresh。无 Cookie 的 refresh 为 401；logout 清 cookie 并幂等结束，不恢复会话。
- 程序模式无该标记，继续要求 JSON refresh，返回原 token pair，完全忽略 Cookie且不设置/清除 Cookie。
- 仅浏览器模式允许使用 cookie；CSRF 使用精确 Origin、非简单请求标记和 SameSite，数据面继续 Bearer，不自动改用 Cookie。
- CORS 从任意 loopback 正则改成精确配置 origins，允许凭据以支持显式开发 origin；默认生产同源、开发优先 Vite `/im` proxy。不添加通配符可信来源。
- 浏览器认证响应 `Cache-Control: no-store`，日志不记录 Cookie 或令牌。

### 5. 保留交互，用浏览器内置协调解决 Cookie 轮换

auth-store 只保留内存 access/user、hydration 状态和本标签会话版本；删除 refresh 字段及持久化写入。初始化删除旧 `im_auth_v1`，不读取/兑换历史 refresh：现有用户升级后一次重新登录，后续刷新页面用 Cookie 恢复。数据库和签名密钥不变，原生客户端无迁移。

auth-session 保留同标签 single-flight 与失败分类，通过会话版本防止旧响应覆盖退出或新登录。登录页/成员页/账号页沿用现有样式与路由；恢复网络失败沿用现有可重试错误反馈，不能把未知恢复状态当成永久登出。

使用标准 Web Locks API 在同源标签间串行化会写 Cookie 的登录、注册、刷新和登出。每个刷新在取得锁之后才发请求，因此使用最新 Cookie，保留严格一次性 refresh；不增加重放宽限或服务端兼容分支。现代生产浏览器和 localhost 安全上下文支持该 API；验收使用真实 Chromium，不为旧浏览器引入 polyfill。

使用不携带凭据的 BroadcastChannel 通知显式登录/登出事件，其他标签清理旧内存身份与公司缓存，再按需要恢复；普通刷新不广播，避免循环。请求结果需与发起时的会话版本匹配。服务器 401 不发清 Cookie，避免失败响应覆盖另一个已完成的成功轮换；只有明确登出清除 Cookie。

## 浏览器响应策略

在一个 IM HTTP middleware 中集中输出安全头：

- CSP：`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self' <配置的 ws/wss origin>; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`。
- 不允许 inline script 或 eval；内联 style 是既有组件定位/样式的需要，不当作脚本豁免。
- `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: strict-origin-when-cross-origin`。
- HTTPS public origin 时输出 `Strict-Transport-Security: max-age=86400`，首版不加 includeSubDomains/preload。依据配置而非 Tunnel 到源站的 HTTP scheme。
- CSP 约束生产前端 HTML；API文档保留其原开发/文档脚本行为，不用 CSP 变相停用 Swagger。API 与资源仍有防嵌入、nosniff 和适用 HSTS。Vite 自己提供开发 HTML，无需为 HMR 放宽生产 script-src。

## 前端呈现边界

无新的页面、布局、表单或视觉设计；会话运输和恢复机制改变，既有登录、冷却、成员状态、错误重试与深链语义保持。本次无需独立 prototype.html，不把验收说明做成新的产品界面。grounding 为当前 login-page/require-auth/membership-page/auth-page-frame 和既有设计样式。真实产品 reviewer 必须从浏览器操作登录、刷新、多标签、退出、待批准状态，检查桌面和窄屏不受会话恢复影响。

## 契约层增量

- [specs/im/auth-tenancy.md](specs/im/auth-tenancy.md)：浏览器 Cookie 会话、来源/目标短节流、等待期间撤销与不阻塞、响应头。
- 无 agent / Gateway 协议或公司数据结构 delta；机器身份与 RPC 消息不变。

## 风险与回退

确定性回归须挂起 fork 结果、撤销身份，再分别释放成功结果、错误或取消；断言旧请求拒绝、受 gate 保护的本请求空半成品被清除、已有分支与用户内容不变，且 gate 不泄漏。正常授权下失败/取消沿用原清理。

取消期间必须保持名额与 gate 生命周期完整；Agent 锁和公司锁的顺序纳入确定性回归。旧 Cookie 轮换的并发用浏览器锁解决，不削弱持久 CAS。CSP 允许现有字体/图片/样式，实际浏览器检查无功能阻断。

回退需成套回退浏览器与服务端认证运输；旧版没有 Cookie 恢复能力，浏览器需重新登录，不导出 Cookie 进 localStorage。生产 HSTS 有一天有效期，回退不能把官网切回 HTTP。本 unit 不部署，生产启用另外授权。

## Runbook for Reviewer

只启动本 unit 的 IM 与内置前端；不需要真实 LLM、外部平台或生产 Gateway。使用独立临时库/上传目录、随机测试 secret、独立 loopback 端口；测试用户与公司管理员由隔离库 CLI 初始化。慢 RPC 用注册到该隔离 IM 的协议测试节点发送真实 WS 帧，明确不是生产容量测试。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM | 对本次终端 session 发送 Ctrl-C；只停止已记录本进程 | unit cwd 下设置 `IM_DB_PATH=<临时目录>/im.sqlite3 IM_UPLOAD_DIR=<临时目录>/uploads IM_PUBLIC_URL=http://127.0.0.1:<独立端口> IM_JWT_SECRET=<测试随机值> PYTHONPATH=src`，用主仓 `.venv/bin/python -m uvicorn IM.app:app --host 127.0.0.1 --port <独立端口>` | GET `/openapi.json` 与首页 200 |
| 前端静态产物 | 无常驻进程 | `cd src/IM/frontend && npm ci && npm run build` | 首页引用本次 dist，真实浏览器请求成功 |

**Review 驱动方式**：端到端真栈，必须用隔离 Playwright 浏览器真实驱动 UI；不启动用户的 Chrome profile。Cookie Secure/HSTS/CSP 的 HTTPS 部分通过 HTTPS 配置的 HTTP 集成测试加本地可信测试 TLS 浏览器入口验证，不能把 HTTP localhost 非 Secure 当作生产验收。

**验收前置**：主仓 `.venv`、Node/npm 与已安装的 Playwright Chromium；全部测试账号和数据库由此 unit 创建。临时 TLS 证书仅用于隔离浏览器上下文信任，不改系统钥匙串。WS 协议测试节点只作用于隔离库；无生产凭据、无需外部 LLM。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-hardening | 公网认证与浏览器会话完整加固 | 无 | 串行 | IM boundary/auth/headers、RPC 等待接线、frontend auth、对应既有回归、canonical delta | [reviewer] 真实浏览器注册/登录/刷新/两标签/退出与 pending/深链可用，页面持久存储无 token，跨源请求不改变 Cookie 会话，HTTPS 头与正常页面/WS/附件可用；[worker] 慢密码与 RPC 不阻塞无关请求，等待期间撤销、取消清理与同 Agent 并发无死锁，来源与短目标预算有效，程序 API 兼容、轮换/撤销仍持久；窄回归、全量本地 CI 与独立门禁通过，保留脱敏证据。 |
