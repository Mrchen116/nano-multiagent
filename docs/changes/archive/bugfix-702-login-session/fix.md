# bugfix-702 浏览器登录恢复与持久会话

## Relations

- Current contract: docs/specs/im/auth-tenancy.md
- 生命周期为 Bugfix lite，唯一 milestone 为 M1-fix。

## 原始报告

用户原话：
- “但是现在我发现经常要重新登录啊，能找到原因吗”
- “90天有点长，30天吧。”
- “打开或刷新 /login 时，如果凭据有效，直接回/chat，对吧。”
- “是不是记录下最近几次登录时间和登录设备就ok”
- “好，开始做吧”

## 现象 / 复现

打开或刷新 /login，即使浏览器仍有有效 HttpOnly refresh Cookie，也直接显示密码表单。本机 Chrome 历史存在一天多次访问登录页的记录。线上 IM 重启时间早于两次登录页访问，因此重启不能解释全部症状。部署期间存在续期接口不可达记录，但无证据证明这些临时失败导致首次跳转。

目标为有效会话进入 /chat，临时故障可重试，主动退出与无效凭据继续显示登录表单。浏览器会话每次续期延长为 30 天。每账号保留最近 10 次密码登录成功时间与请求客户端信息，自动续期与失败登录不计入。记录存于 IM 数据库供排障查询，不增加账号页面。

## 根因

Cookie 会话设计通过 RequireAuth、MembershipPage 调用 hydrate，独立 LoginPage 不触发恢复，也未根据有效会话跳转。登录入口与受保护入口恢复行为不一致。当前登录页最近改动见 59650f196（onboarding），此处以现有实现确认缺口，不断言该提交首次引入。原鉴权意图见 current spec 的“浏览器令牌保存与页面恢复”，必须保留 Cookie-only、一次性轮换、退出撤销及临时故障重试语义。

服务端 refresh TTL 固定 7 天，登录与自动续期共用 issuePair，auth_sessions 仅保存滚动过期时间，不能还原密码登录时间和设备。不会把此次发现解释为所有历史掉登录事件的已证实根因。

## 修复

M1-fix，源码提交 e58eed055：
- 登录页调用现有 Cookie 会话恢复，自动恢复成功进入 /chat（需准入处理进入 /membership）；临时故障显示重试入口，主动退出保留登录表单。
- 登录提交过程继续由既有成功回调处理原路径，避免与自动恢复跳转竞争。
- 共用 refresh 有效期从 7 天延长至 30 天，Cookie Max-Age 同步延长。原有 access 15 分钟、轮换与撤销语义保留。
- 增加 auth_login_events 表，成功密码校验后在同一事务创建会话、记录时间/客户端 User-Agent 并保留该账号最近 10 条。初始化现有数据库自动建表。注册、失败登录、续期均不写记录。
- 更新 canonical auth-tenancy.md。无独立 delta；无 Agent Context 影响；无人工一次性迁移。
- 独立 code review 见 M1-fix/code-review.md，结果 []。



## 验证

- 修前前端回归新增的“登录页恢复有效 Cookie”和“临时失败重试”两个场景失败，修后通过。
- 最终登录相关前端套件 7 files / 57 tests passed，涵盖直接打开登录页、重试、失效会话、主动退出、原路径返回。
- 前端全量 111 files / 1056 tests passed；该次全量后只增加主动退出、401 恢复拒绝两个用例，已包含于最终 57 tests 中。
- 后端 identity 套件 11 tests passed，验证轮换撤销、30 天 Cookie/JWT、真实登录路由的 User-Agent 传递、最近 10 条记录持久化和失败登录/续期不新增记录。历史数据 fixture 直接预置，以避免重复 bcrypt 导致负载相关超时。
- pnpm build、pnpm typecheck、pnpm check:ios-runtime、前端 npm run build 通过。
- Python 非 E2E 129 passed / 28 deselected；ruff check / format、docs-check 通过。
- Playwright 驱动独立 Chrome，使用 127.0.0.1:18172、独立临时 SQLite 与固定测试密钥。真实 HTTP 注册后 /login 自动进入 /chat，重复打开同样恢复，HttpOnly Cookie 剩余有效期为 30 天。停止并重启 IM 后再次从 /login 恢复 /chat；真实登出后回到密码表单；通过页面输入密码登录后数据库恰好保存 1 条 Chrome 客户端登录记录。服务与浏览器已停止，无生产变更。
- 首次后端全量误用系统 Node 25.8.2 并与前端全量并发，多个 DSH 用例失败；停止该次运行后，使用指定 Node 24.22.1 与 maxWorkers=2 重新验证，209 files / 1113 tests 全部通过（431.39 秒）。
