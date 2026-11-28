# bugfix-818: 认证会话跨标签锁超时与非安全上下文恢复兜底

Platform-Parity-Exempt: Browser/WebView session lock, BroadcastChannel, and cookie hydration recovery only; Desktop (macOS/Windows) shares this Web bundle directly, iOS uses native URLSession with JSON refresh tokens without Web Locks, and Node has no browser auth session.

## Relations

- Related: bugfix-576, bugfix-709, feat-790

## 原始报告

> Issue A（阻断）：Web Locks 无超时，出现"正在恢复你的登录…"永久卡死
> 现象：浏览器或客户端打开 IM，页面停在"正在恢复你的登录…"无限转圈，用户无法进入登录页。
> 根因：src/IM/frontend/src/features/auth/auth-session.ts 的 withSessionLock：
> return navigator.locks.request(desktopScopedKey("im-session"), operation);
> Web Locks 是同 origin 跨 tab 互斥锁，没有超时。当同一网站另一个 tab（被冻结、休眠、崩溃）持有 im-session 锁未释放时，新页面会无限等待。
> 用户可见后果：只能清缓存 / 无痕窗口 / 手动关闭旧 tab 才能恢复——用户体验极差。
> 建议修复：加超时兜底，超时后降级执行（本地已临时改为 AbortSignal.timeout(8000) + catch → operation()）。

Agent 补充核查记录（基于当前 worktree 代码核实）：
1. 跨标签页 Web Locks 死等：`src/IM/frontend/src/features/auth/auth-session.ts` 的 `withSessionLock` 无超时信号，同源冻结/休眠标签页长期占用 `im-session` 时，`restoreSession()` / `login()` / `register()` / `logout()` 永久阻塞。
2. 非 `SecureContext`（如内网明文 `http://10.x.x.x:8011`）及受限环境下浏览器 API 缺失或抛错：Chromium 在非 `SecureContext` 下 `navigator.locks` 为 `undefined`，调用 `navigator.locks.request(...)` 直接抛出 `TypeError`；`auth-store.ts` 的 `hydrate()` 未捕获异常，导致 `{ hydrated: false, hydrationError: false }` 永久悬停，`LoginPage` 无限显示「正在恢复你的登录…」，`RequireAuth` / `MembershipPage` 白屏，`login()` / `register()` / `logout()` 同样失败；`BroadcastChannel` 与 `localStorage` 在严格隐私策略下抛错亦有同类风险。
3. 认证请求无超时：`src/IM/frontend/src/features/auth/auth-api.ts` 的 `postJson`（以及 `RequireAuth` 的 `/im/v1/auth/me` 校验）未设置超时，内网半开 TCP 连接长期无响应时既卡死当前页恢复，又在锁内长期阻塞同源其他标签页。

## 现象 / 复现

1. **同源锁占用卡死**：同源旧标签页在持有 `im-session` Web Lock 期间被系统休眠、冻结或请求挂起；新打开 `/login`、`/` 或 `/chat` 时，页面调用 `useAuthStore.getState().hydrate()` 进入 `withSessionLock`，因锁永不释放，`/login` 永久停留在「正在恢复你的登录…」，受保护路由永久空白，无法看到登录表单或重试入口。
2. **内网明文 HTTP 卡死**：通过非 loopback 的内网地址（如 `http://10.x.x.x:8011`）在 Chromium 打开 IM，由于非 `SecureContext` 下 `navigator.locks === undefined`，`hydrate()` 触发未捕获 `TypeError`，`hydrated` 与 `hydrationError` 均保持 `false`，页面永久停在「正在恢复你的登录…」；即便直接触发 `login()` 也会因同一异常报错无法登录。
3. **半开连接拖死恢复与跨标签锁**：`POST /im/v1/auth/refresh` 遇到半开连接长期不返回时，`fetch` 无超时中断，本页长期停留在恢复中且不展示重试按钮，同时持续占用跨标签 `im-session` 锁拖死后续新标签页。

## 根因

### 历史意图追溯

- **功能引入（`bugfix-576`，提交 `9b9478ebe`）**：为将浏览器会话改为内存 `accessToken` + `HttpOnly` Cookie 续期，且当时服务端每次 `refresh` 都会一次性轮换 Cookie 凭据，`auth-session.ts` 引入 `navigator.locks.request("im-session", operation)` 串行化同源标签页的 `refresh` / `login` / `register` / `logout`，并用 `BroadcastChannel("im-session")` 广播显式登录/退出。当时假设运行环境均为 HTTPS 或 `localhost` 安全上下文，且锁内请求总会快速结束。
- **后续演进（`bugfix-709` 提交 `8ece8ad0e`、`feat-790` 提交 `c75e0415e`）**：`bugfix-709` 已将浏览器 Cookie 改为稳定的 30 天滚动凭据（续期只延长期限、不轮换 Cookie 值），使锁超时降级执行不再破坏服务端 Cookie 有效性；`feat-790` 增加了 `desktopScopedKey("im-session")` 及受控内网私有化明文 HTTP 支持，但未同步为 `withSessionLock`、`sessionChannel`、`postJson` 与 `hydrate()` 补齐非安全上下文兼容、锁等待超时、HTTP 请求超时和异常收敛兜底。

### 直接代码原因

1. `auth-session.ts:47-50`：`withSessionLock` 直接调用 `navigator.locks.request(...)`，既未判空 `navigator.locks?.request`，也未传入超时 `AbortSignal` 及锁获取失败降级分支。
2. `auth-session.ts:19-35, 38-45, 123-124, 139-140`：`sessionChannel()` 与 `localStorage` 读写未防护 API 缺失或 `SecurityError`/`InvalidStateError`。
3. `auth-store.ts:72-77`：`hydrate()` 未用 `try/catch` 兜底 `import("./auth-session")` 或 `restoreSession()` 的异常，且重试前未复位 `hydrationError`，异常抛飞后状态永久停在 `{ hydrated: false, hydrationError: false }`。
4. `auth-api.ts:24-43`（及 `require-auth.tsx:31`）：认证请求未绑定超时中止，半开连接下无限挂起。

### 修复必须保住的不变量

1. **零持久令牌存储**：`accessToken` 与 `user` 仅存内存，继续清理历史 `im_auth_v1`，不在 `localStorage` / `sessionStorage` 写入任何令牌。
2. **本标签页单飞与串行语义**：保留 `refreshFlights` 按 `revision` 合并本页并发刷新（HTTP 401 重试与 WebSocket `ensureFreshSession` 共享），并在本页内通过内存队列保持 `refresh` 与 `logout` 串行，即使 `navigator.locks` 缺失或超时降级也不乱序。
3. **仅在锁获取阶段降级，绝不二次执行已获锁操作**：一旦 Web Lock 已授予并开始执行 `operation()`，`operation()` 自身抛出的业务/网络错误（如 `401` 密码错误、`429` 冷却、请求超时）必须原样向外抛出，严禁落入降级分支重复发请求。
4. **`revision` 并发栅栏完整有效**：`startRefresh`、`restoreSession`、`establishSession`（`login`/`register`）与 `logout` 均校验发起时的 `revision`，锁超时降级或慢响应晚到时不得覆盖、清空或吊销期间已发生的新会话状态。
5. **明确的状态收敛语义**：`refresh` 返回 `401` 收敛至 `clear()`（`hydrated: true, user: null`，展示登录表单）；网络异常、5xx、请求超时或任何意外恢复异常收敛至 `{ hydrated: false, hydrationError: true }`（展示可重试提示并保留受保护深链）。

## 本次审查安排

| 审查编组 | 必须回答的问题 | 能力 | 验证方法与已有证据 |
|---|---|---|---|
| R1 代码与契约审查 | 锁超时/非安全上下文/半开连接三条故障链路是否闭合且无二次执行或 `revision` 竞态回归；`docs/specs/im/auth-tenancy.md` 契约增量是否与实现和测试一致 | `change-code-review` | 独立 subagent 审查完整分支 diff、TDD 红绿单测与前端构建/类型检查证据 |

## 修复

- `src/IM/frontend/src/features/auth/auth-session.ts`：
  - `withSessionLock` 增加 `SESSION_LOCK_TIMEOUT_MS = 8_000` 超时保护与能力检测：非 `SecureContext` 下 `navigator.locks?.request` 缺失、抛错或等待超过 8 秒时，中止排队锁请求并降级至本页内存串行队列 `enqueueInTab` 执行一次；一旦锁已授予并进入 `operation()`，其业务或网络异常原样抛出、绝不重复执行。
  - `sessionChannel`、`broadcastSessionChange` 与 `localStorage` 会话变更时间戳读写补齐缺失/受限异常捕获，避免严格隐私或非安全上下文阻断单页恢复、登录与退出。
  - `restoreSession` 增加异常兜底并在未完成水合时收敛至 `hydrationError: true`；`logout` 增加发起时 `revision` 校验，防止跨标签锁超时降级后延迟执行的旧退出请求吊销期间新建的会话。
- `src/IM/frontend/src/features/auth/auth-store.ts`：
  - `hydrate()` 增加 `try/catch` 与完成态守卫，重试前复位 `hydrationError`，确保任何异常路径均收敛至已恢复、未登录或 `hydrationError: true` 可重试态，消除 `{ hydrated: false, hydrationError: false }` 永久悬停；`localStorage` 历史键清理增加受限存储异常保护。
- `src/IM/frontend/src/features/auth/auth-api.ts` 与 `require-auth.tsx`：
  - 新增 `withAuthRequestTimeout`（默认 `AUTH_REQUEST_TIMEOUT_MS = 10_000`），为 `/im/v1/auth/{login,register,refresh,logout}` 及受保护路由 `/im/v1/auth/me` 身份复核绑定 `AbortController` 超时中止，阻断半开连接无限挂起及跨标签锁长期占用。
- `docs/specs/im/auth-tenancy.md`：
  - 补充浏览器跨标签锁阻塞、非安全上下文接口缺失及认证/身份校验请求无响应时的有界降级与可重试恢复契约。

## 验证

- **TDD 红绿复现验证**：
  - 修复前运行新增的 8 项回归用例（`npx vitest run --testTimeout=2500 src/features/auth/auth-session.test.ts src/features/auth/auth-store.test.ts src/features/auth/auth-gate.test.tsx`），复现跨标签锁死等超时、`navigator.locks === undefined` 未捕获 `TypeError`、半开刷新请求超时与 `hydrate()` 异常未收敛失败。
  - 修复后 `src/IM/frontend/src/features/auth` 下 8 个测试文件共 74 项测试全部通过，覆盖：跨标签 Web Lock `AbortSignal` 超时降级与忽略信号兜底、获锁后业务失败不重复执行、无 `navigator.locks` / `BroadcastChannel` 明文 HTTP 全链路（恢复/登录/刷新/退出）、锁超时期间新会话 `revision` 防覆盖与防误登出、`/auth/refresh` 与 `/auth/me` 请求挂起超时收敛可重试提示、`hydrate()` 异常收敛与重试复位。
- **前端构建与全量回归**：
  - `cd src/IM/frontend && npx tsc -b && npx vite build` 编译与打包通过（本地构建后已清理临时 `dist/`）。
  - `cd src/IM/frontend && npm run test` 全量 141 个测试文件、1366 项测试全部通过。
- **文档与架构边界检查**：
  - `./scripts/docs-check`（242 份受维护文档、74 条必达路由）通过。
  - `NANO_TEST_BASE_REF=origin/develop pytest -m "not e2e" -q tests/contract/`（48 项契约与测试规范门禁）通过。
