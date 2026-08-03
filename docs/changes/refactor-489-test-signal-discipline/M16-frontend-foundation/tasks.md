# refactor-489-M16: frontend-foundation — Tasks

> 对齐: ../design.md 的 refactor-489-M16 行与决策 1--2

## 目标

让 frontend foundation Vitest 只保护 app/auth/realtime/notification/i18n 的用户可观察状态、公开 adapter 与测试运行配置；删除 `.gitignore`、HTML、prototype/CSS class、退役 alias 等低信号断言，并将同一 seam 的重复状态收敛为最低必要保护。

## 退出标准

- [ ] 19 个 M16 测试文件与 scoped test/config support 均有 keep / rewrite-merge / delete 处置结论。
- [ ] 保留测试直接驱动路由、组件、store、transport runtime、browser API adapter 或 Vite config，并从 DOM、请求、持久状态、事件 fan-out 或公开配置观察结果。
- [ ] 删除的源码文本、HTML/`.gitignore` 布局与重复断言不留下 app/auth/realtime/notification 保护缺口。
- [ ] M16 Vitest、frontend build、`git diff --check` 与 changed-path scope 全绿。

## 测试策略

- 被测行为（来自退出标准）：root/绑定/设置路由可达；同账号 refresh 保留 cache、退出/切账号隔离 cache；鉴权注入、token rotation、401/retry 与账号切换竞态；桌面/移动 shell、Me 导航/语言/退出；Agent completion、系统通知资格/点击、local unread；用户流 single socket、cursor/resume/resync/recovery/session generation；Vite `/im` WebSocket proxy 与 Vitest/jsdom 配置。
- 已有测试在：`src/IM/frontend/src/{app,features/{auth,me,notifications},i18n,realtime}/**/*.test.{ts,tsx}` 与 `src/IM/frontend/tests/vite-proxy-config.test.ts`；本 milestone 只删改现有测试，不新建测试域或产品 helper。
- 落层/目录/marker：frontend Vitest/jsdom component、pure state/runtime 与 node config tests，marker：无；真浏览器 E2E 不属本 milestone。
- 可选依赖 importorskip：无（Node/Vitest workspace 依赖）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；测试资产改造前后数量、命令与结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| App 只协调一份全局通知流；同用户 token refresh 不清 cache，退出/切账号清 cache | `src/IM/frontend/src/app/App.test.tsx` | rewrite-merge | 保留 coordinator owner 与 identity-scoped QueryClient 结果；删除与 AppShell 重复的 nav/banner/main DOM 断言，合并退出/切账号 cache 隔离 | App tests |
| `.gitignore` 中 dist 条目与构建分发终态 | `src/IM/frontend/src/app/distribution-contract.test.ts` | delete | 只读取 `.gitignore` 文本，既不执行 build 也不证明 IM hosted entry；production build 与 AGENTS 禁止提交 dist 的门禁负责真实风险 | frontend build + changed-path audit |
| `index.html` favicon 源码文本 | `src/IM/frontend/src/app/index-html.test.ts` | delete | 只扫描 HTML 字符串且无 current 产品契约；不能证明浏览器无 404，不保留伪入口保护 | frontend build |
| root redirect、bind、settings 与 node-scoped creation 路由可达 | `src/IM/frontend/src/app/router.test.tsx` | rewrite-merge | root 由实际 MemoryRouter 导航结果证明，不再反射 `RouteObject/Navigate` 内部形状；其余路由保留跨 router→page 接线，并隔离不属于用例的全局 stream side effect | router tests |
| desktop/mobile shell 导航、退出与 unread feedback | `src/IM/frontend/src/app/shell/app-shell.test.tsx` | rewrite-merge | 保留真实 viewport、链接、退出、unread sum；删除 prototype milestone 注释、internal badge/chevron/emoji 和零 unread 的重复 visual/absence 断言 | AppShell tests |
| Bearer 注入、401 refresh/replay、refresh 失败/缺失 | `src/IM/frontend/src/features/auth/auth-fetch.test.ts` | keep | 直接经过公开 HTTP wrapper，从请求 header、重放与 auth state 观察；是 API client 最低 seam | auth-fetch tests |
| 未登录 redirect、已登录进入、登录成功/401 反馈 | `src/IM/frontend/src/features/auth/auth-gate.test.tsx` | keep | 真实 route/form 用户交互，直接保护 auth gate 与 login 入口，不与 store 纯状态重复 | auth-gate tests |
| token freshness、single-flight、HTTP/WS 共用 refresh、瞬态失败与账号切换竞态 | `src/IM/frontend/src/features/auth/auth-session.test.ts` | rewrite-merge | 保留 session readiness 的公开状态；去掉 30 秒精确边界和 500/503 同义组合，只留代表性即将过期与服务端失败 | auth-session tests |
| session 持久化/清理/hydrate 与 delayed snapshot identity 隔离 | `src/IM/frontend/src/features/auth/auth-store.test.ts` | rewrite-merge | 合并 set/clear lifecycle，删除 Zustand getter 的初始值复述；保留 localStorage 和跨用户写入结果 | auth-store tests |
| Me 的身份、入口、语言与退出 | `src/IM/frontend/src/features/me/me-page.test.tsx` | rewrite-merge | 保留可见身份、真实链接、语言持久化和退出导航；删除 prototype 流水号、CSS class、圆角/红色/monospace/chevron/emoji 等 jsdom 伪视觉断言 | MePage tests |
| canonical Agent completion、reload pending identity 与 discard | `src/IM/frontend/src/features/notifications/agent-completion-accumulator.test.ts` | rewrite-merge | 保留消息 lifecycle 和持久 pending seam；删除退役 `message_created` alias 缺席测试 | accumulator tests |
| hidden + preference + permission 下通知及点击；不符合资格/重复 candidate 不通知 | `src/IM/frontend/src/features/notifications/agent-completion-notifier.test.tsx` | keep | 顶层 notifier 的用户可见副作用与幂等边界；leaf API 测构造，本层只守资格连接和导航 | notifier tests |
| document visibility 读取、订阅与解除订阅 | `src/IM/frontend/src/features/notifications/document-visibility.test.ts` | rewrite-merge | 三个公开结果可在一个 listener lifecycle 中证明，无需拆成 getter 与 callback 两例 | visibility tests |
| 本 tab unread 不被 stale server 0 清除，也不降低 authoritative count | `src/IM/frontend/src/features/notifications/local-unread-feedback.test.tsx` | keep | 直接保护公开 hook 的两个不同合并规则，是 shell/chat 共用最低 seam | unread feedback tests |
| Notification 支持、权限与构造/click/no-op | `src/IM/frontend/src/features/notifications/notification-api.test.ts` | rewrite-merge | 每个公开 adapter 保留成功与不可用边界；合并 granted/denied terminal permission、denied/absent 构造等同 seam 重复 | notification API tests |
| 本地通知 preference 默认值、持久化与 hook fan-out | `src/IM/frontend/src/features/notifications/notification-preference.test.tsx` | keep | 直接保护用户偏好持久化和订阅结果，无更低层替代 | preference tests |
| 默认语言与中英文切换/持久化 | `src/IM/frontend/src/i18n/i18n.test.ts` | rewrite-merge | 保留默认 locale 与用户切换后的代表性可见翻译；删除 `as any` 非法 locale、防伪 hydrate 和同一 shell namespace 的逐 key 文案重复 | i18n tests |
| user stream socket ownership、session generation、cursor/resume/resync/recovery 与 malformed isolation | `src/IM/frontend/src/realtime/user-stream/user-stream.test.ts` | rewrite-merge | 保留 runtime 的公开 transport/state seam；删除与完整 continuity 重复的 storage 调用次数和 lower-cursor 单点 case，避免锁定 timer/内部 storage fuse 步骤 | user-stream tests |
| `/im` development proxy 同时转发 HTTP/WS | `src/IM/frontend/tests/vite-proxy-config.test.ts` | keep | 直接读取公开 Vite config 对象，保护本地 WebSocket 用户流入口的运行配置 | proxy config test |
| Vitest/jsdom setup、render helper、scripts 与 TypeScript/Vite 配置可运行 | `src/IM/frontend/{package.json,vite.config.ts,tsconfig*.json}`、`src/IM/frontend/src/test/**` | keep | 这些是 19 个测试与 build 的当前运行 seam，不以源码文本快照另测；用实际 collection/build 验证 | M16 Vitest + frontend build |

### 前端覆盖矩阵（本 milestone 无 UI delta）

用户路径分类：N/A（测试资产重构；不修改产品源码、样式或交互）。

| 状态 | 覆盖计划 |
|---|---|
| default | 保留 authenticated App/Shell、Me、notification preference 与 user-stream 正常路径 |
| loading | auth gate hydration 由 redirect/authenticated route 结果覆盖；无新增 loading UI |
| empty | 保留无 session、无 candidate、无 Notification API、无 unread 的最低状态 owner |
| error | 保留 login 401、refresh 401/503/network、resync/storage/subscriber failure |
| disabled | 保留 notification preference off 与 browser permission denied |
| submitting | 保留 login form POST 成功/失败；无新增提交 UI |
| permission denied | 保留 Notification permission denied 不弹系统通知 |
| long content | N/A；本 unit 不改通知内容或样式，现有处置不新增假想视觉场景 |
| missing/nullable data | 保留无 session/token/API/candidate 与 malformed canonical event |
| mobile viewport | 保留 mobile shell 三入口与 unread badge |
| desktop viewport | 保留 desktop shell Chat/Agents/UserMenu 与退出 |
| dark mode（如项目支持） | N/A；本 unit 无样式 delta，不用 class 正则伪造视觉保护 |

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| app/auth/notification 用户状态 | 保留/收敛后的 Vitest DOM interaction + state regression | 是 |
| user-stream 与 Vite proxy | runtime/config Vitest | 是 |
| 真实浏览器视觉与网络 | N/A；零 UI/product delta，不把测试清理升级为产品验收 | 否 |

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 删除静态扫描与 app/me 伪视觉重复

- 状态: TODO
- 步骤: 删除 `.gitignore`/HTML 源码测试；收敛 App/router/AppShell/Me 的重复路由、prototype 与 CSS/DOM 形状断言。
- 验证: app/me 定向 Vitest 与 M16 全量通过；保留 root/route、identity cache、桌面/移动导航、语言与退出路径。

### R2 — 收敛 auth 与 notification 状态保护

- 状态: TODO
- 步骤: 合并 auth freshness/status、store lifecycle、completion/visibility/Notification API/i18n 的同 seam 重复，保留错误、账号竞态和用户副作用。
- 验证: auth/notification/i18n 定向 Vitest 与 M16 全量通过。

### R3 — 收敛 realtime 并完成配置门禁

- 状态: TODO
- 步骤: 删除 user-stream 中被完整 continuity/resync case 覆盖的内部调用次数与单点重复；复核 test setup/package/Vite/tsconfig owner，并在最新 unit 上完成门禁。
- 验证: M16、frontend build、docs/diff/scope 全绿；changed paths 仅 M16 tests 与本 milestone 文档。
