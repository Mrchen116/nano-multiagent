# Verification Report: bugfix-576-public-auth-hardening

## Round 1

> Validation snapshot: `d357729af19d5860db79ae5617eaee5b44ada0d7 → 9b9478ebe0c1075ccc9b166afae80f3190a604fb`

- reviewer: `/root/static_review_576`，独立于实现者。
- verification_mode: full；review_round: 1。
- requires_full_verification: false；已执行 full，后续可针对本轮问题与最终 delta 校正 closure。
- verdict: **Issues Found — 1 CRITICAL / 1 WARNING / 0 SUGGESTION**。
- product_evidence_status: received；独立产品 full `regression.md`（report commit `4f008a8bd`，源实现未变）的唯一 R1-01 major 与本轮 W1 同一根因。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 四项目标 requirement 均有实现；产品 evidence 已交付，M1 未退出，两个实质问题仍待修复闭环 |
| Correctness | 认证运输、来源预算、慢等待与身份复核有实现和回归；非空 fork 清理、注册字节反馈未符合契约 |
| Coherence | 默认 gate 与局部让出、既有会话 CAS 和单 worker 架构符合设计；有限 fork 清理漏掉两条路径 |

## Completeness

- 全部 incident Requirement、canonical auth delta Scenario、design 五项决定和 M1 worker/reviewer 退出标准均已检查。
- 注册/登录、原生令牌对、保留用户名、pending、refresh 持久轮换/撤销沿用现有服务和回归；浏览器运输不返回 refresh，旧持久 token 删除。
- 慢密码、线程取消容量、来源隔离、短目标预算、同 Agent 竞争、控制结果期间 logout 和 fork 撤销三种 outcome 已有长期回归。
- 当前 fork 新测试只保护空 scaffold 的撤销成功/错误/取消，没有保护正常拒绝/timeout 或成功后复制失败时已非空分支；直接公开 seam 证实其仍可丢内容。
- 未新增 prototype / reference：N/A。必须保留既有页面体验；独立 reviewer 的 regression.md 已提供桌面/窄屏、TLS/真实多标签、WS 与附件直接证据，本轮核对证据链，不代替其体验判断。

## Correctness

| Requirement / Scenario | 实现位置 | 测试 / 直接证据 | 状态 |
|---|---|---|---|
| 原生注册/登录及未知账号错误语义 | `application/auth_service.py:103-186`；`api/routes/auth.py:148-205` | 既有 auth service/routes；dummy bcrypt 路径 | covered，新增字节规则见 W1 |
| reserved 身份、pending 与公司准入 | `auth_service.py:118-158`；既有 current_user/company service | 既有保留身份和 company admission 覆盖，完整 Python 通过 | covered |
| 持久 refresh CAS、重放、logout/重启 | 原有 AuthSessions；`api/routes/auth.py:208-256` | 既有 auth session 回归、`test_browser_auth.py` 的原生重放及 Cookie logout | covered |
| 浏览器令牌保存、Cookie 页面恢复 | `api/routes/auth.py:114-145`；`frontend/.../auth-store.ts`、`auth-session.ts` | browser auth HTTP；auth-store/session/gate 测试；regression.md UI 注册/刷新与可读存储为空 | covered |
| 浏览器 Origin/标记与原生 JSON 边界 | `public_boundary.py:157-176`；`auth.py:134-145` | `test_untrusted_browser_origin_cannot_mutate_session`、原生空 body 422 且不改 Cookie | covered |
| 同源多标签续期、版本、登出与临时失败 | `auth-session.ts:12-29,50-121` | session delayed 200/401、single-flight、logout 排序、无凭据广播；真实两标签 reload/signout、深链、发送前网络失败恢复 | covered |
| 来源、source/account、目标短预算不续期 | `public_boundary.py:145-156`；`auth.py:190-204`；`infra/auth_limits.py` | `test_auth_concurrency.py` 来源隔离及短窗口；固定 expires_at SQL | covered |
| 密码计算不阻塞读取、取消不提前放名额 | `infra/password_work.py:16-30`；`company_gate.py:27-51`；`auth_service.py:169-183` | 受控 worker/实际 HTTP、取消后第三请求 429、最终连接无事务且 gate 无泄漏 | covered |
| 已派发控制等待撤销及同资源不互锁 | `ws/gateway/control.py` 全部结果等待；`ws/gateway/work.py:130`；`agent_config_operations.py:100,136,178` | 真实 HTTP+WS 同 Agent 双请求/读取/logout；401/409/profile_version 直接断言 | covered，fork 例外见 C1 |
| 有限 fork 清理不删用户内容 | `web_im_service.py:445-456,588` | 空 scaffold 撤销回归通过；非空正常失败公开 HTTP+WS 复现删除内容 | **CRITICAL C1** |
| 集中安全头及 loopback/显式开发 origin | `api/security_headers.py`；`app.py:518-530` | served HTML/HSTS/docs exception、显式 CORS、完整前端 build；真实 TLS/CSP inline 与 iframe 拦截、图片解码和 wss | covered |
| 当前可修正输入与 Unicode 字段反馈 | `auth_service.py:132`；`auth-form-feedback.ts:37,44-70`；`register-page.tsx:83-88` | 73 字节 HTTP 注册直接返回新 422；frontend 映射缺失 | **WARNING W1** |

## Coherence

| design 决策 | 遵守? | 代码 / 验证证据 |
|---|---|---|
| 默认提交 boundary；仅慢操作让出；当前 task 拥有 lease | 是 | `company_gate.py:54-72`，response lease release，三种异常/取消重新取 gate |
| 每 Agent 锁等待不持 company gate；状态与 CAS/pending 保留 | 是 | `outside_gate_lock` acquired/finally；create 再查 profile；同 Agent 200/409 或撤销401 回归 |
| 撤销后只允许本请求空 fork 半成品清理 | 部分 | 异常入口已限空；normal failed result 和 copy-error 删除缺非空内容保护，见 C1 |
| 两个实际密码线程名额、用户快照复核、独立限流连接 | 是 | shield executor Future 的 done_callback 释放预算；hash/epoch 重读；app 开启/关闭 limits_connection |
| 组合失败桶和一秒目标预算 | 是 | `auth.py:190-204`；成功只 clear source/account；拒绝不延长原窗口 |
| 浏览器 Cookie 和程序 JSON 明确分离 | 是 | host-only、HttpOnly、Strict、HTTPS Secure、no-store；browser body token 拒绝；native 不读/改 Cookie |
| Web Locks + revision + credential-free BroadcastChannel | 是 | refresh、login/register、logout 经统一 lock；刷新不广播；旧 200/401 受 revision 约束；Providers 原有 cache clear 仍连接 |
| 策略集中，字体/图片/WS 可用、文档保留 | 是 | HTML CSP 及精确 ws origin；Swagger/Redoc 例外；HSTS 不依赖内部 scheme；regression.md 真实 HTTPS 图片/WS 与页面证据 |
| 低复杂性及仓库依赖红线 | 是 | 所有产品修改局限 IM；无新第三方依赖、Redis、分布式或补偿平台；未跨产品 import |

## Issues

### CRITICAL

- **C1 — 等待期间用户内容会被 fork 失败回滚删除。** 契约：design §关键决策 1/R3 的“非空保留”及不删用户内容。实际 `web_im_service.py:455-456` 的 None/ok:false 分支无条件 cascade；`:588` 成功后 copy-error 同样如此。公开 HTTP+真实 WS 复现：挂起 fork → 列表200可见 branch → 正常真人发消息201 → Gateway ok:false → fork502/branch404/消息数0。应同步所有受影响清理路径，仅删除可观察为本请求空半成品；copy 前记录已有内容，避免失败删除并发写入。增加最低合适 HTTP/WS 公开 seam 回归和必要复制失败保护，不用改 spec 适配丢内容。独立复现临时目录已清理。

### WARNING

- **W1 — 72 UTF-8 字节注册拒绝的字段反馈与 delta 遗漏。** 当前 `docs/specs/im/auth-tenancy.md:57-75` 要求本地可判定输入和服务可修正拒绝字段化；新 `auth_service.py:132-133` 的明确拒绝没有对应 `auth-form-feedback.ts:44-70` byte 判断/422 mapping，register-page:88 将其报告为服务异常。73 字节 ASCII 实际 HTTP=422；25 个三字节中文同样超限而低于 256 codepoints。应保留 bcrypt 上限，在注册字段提供一致的本地化 byte 反馈并补回归；由 root 校正 canonical delta 为明确的注册密码规则，不能仅悄悄更改 current。无需扩展哈希算法或兼容框架。

### SUGGESTION

无。

## Delta Reconciliation

- 浏览器 transport、存储、CSRF、限流维度、慢等待撤销与集中安全头均与 auth delta 对齐。
- **implementation-mismatch**：fork 的非空保留未覆盖所有失败路径，详见 C1。
- **delta-mismatch / uncovered observable behavior**：明确新增的 72 UTF-8 字节注册 422 边界尚未进入 canonical delta，详见 W1。修正后应同步核对 current Unicode/input 反馈 Scenario 的最终投影。
- fork 非空保留是 design 既定边界；修复时应核对 `docs/specs/im/conversations-messages.md:300-310` 的既有“任一步失败原子回滚”文字与该有限例外，必要时由 owner 补对应 canonical delta，避免交付后长青 spec 漂移。
- 本轮组合 outcome: **implementation-mismatch**。不修改任何 spec；交 root 做最终校正。

## Validation Evidence and Limits

- 冻结版本主 Agent 全量 Python：`pytest -m 'not e2e' -n4 --dist worksteal` → 4112 passed / 27 warnings / 85.35s。独立只读 `/tmp/bugfix-576-full-tests.log` 末尾确认摘要。
- 冻结版本完整前端 → 85 files / 799 tests passed / 17.42s；独立只读 `/tmp/bugfix-576-frontend-tests.log` 末尾确认，含新增 stale401 参数案例。
- narrow auth/cookie/control/fork、build、Ruff check/format、docs-check 及 npm audit critical gate 复用 progress/主 Agent 的同版本证据；未重复全量，未把现有非critical依赖结果纳入本 unit。
- 独立直接证据：临时隔离 HTTP 注册字节拒绝，以及真实 ASGI HTTP+GatewaySocket 的 fork 数据丢失；仅用于本轮 finding，未提交一次性脚本或 runtime 文件。
- 独立产品 `regression.md` full 同源码版本的真实 HTTPS、桌面/窄屏、两标签、pending/深链、附件/WS 与 CSP 证据已收到并核对。该 reviewer 另外执行 auth_concurrency/company_control_waits 4 passed；真实并发 HTTPS 登录为 2x401/3x429（Retry-After=1），同期间 auth/me 200 / 3ms。仅作为单次可用性证据，不是容量承诺。唯一产品 R1-01 与 W1 同根因；CAS 已提交而响应丢失可能需重新登录是 design 已承认边界，本轮不要求 replay grace。
- 无生产、系统钥匙串或用户 Chrome 操作；无自建常驻服务。仅 stage/commit本报告和对应 code-review 记录。

1 critical issue, 1 warning found. Fix before PR; then close final delta and product evidence.
