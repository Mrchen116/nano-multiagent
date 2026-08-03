# refactor-489-M16 — Progress

## Baseline

- Claim: 清理前 M16 foundation Vitest 可稳定运行，后续删除/合并能与同一范围直接对照。
- Baseline: `milestone/refactor-489-M16` from `origin/unit/refactor-489@90415c3d1`。
- Method: 在 `src/IM/frontend/` 对不属于 M14/M15 的 19 个 tracked `*.test.{ts,tsx}` 运行 Vitest；worktree 的临时未跟踪 `node_modules` 链接到主仓已安装的同版本 frontend dependencies，收尾时删除。
- Result: PASS；`19 test files / 105 tests passed in 2.91s`。
- Locator: `src/IM/frontend/src/` foundation tests、`src/IM/frontend/tests/vite-proxy-config.test.ts` 与本 milestone `tasks.md` 处置表。
- Limit: Vitest/jsdom + fake WebSocket/Notification/fetch；不证明真实浏览器视觉、真实 IM 服务或外部网络。既存输出含 router 测试未隔离全局 stream 导致的 `/im/v1/sync` invalid-URL console error，以及 Node `--localstorage-file` warnings；基线仍绿，前者在 R1 从测试 harness 隔离，后者记录但不扩张产品范围。

## R1 — 删除静态扫描与 app/me 伪视觉重复

- 状态: DONE
- Context: foundation 基线含 `.gitignore`/`index.html` raw-text 扫描，App 与 AppShell 对 nav/banner 的重复，以及 Me/AppShell 对 prototype 流水号、CSS class、emoji、chevron、圆角和颜色的 jsdom 断言；router 还反射 `RouteObject/Navigate` 内部形状并因未隔离全局 user stream 在绿测中输出真实 fetch URL error。
- Decision: 删除两份 raw-text 测试；App 只保留全局 notification coordinator 和 identity-scoped cache；AppShell 保留 desktop/mobile 导航、退出与 unread sum；Me 保留身份/入口、语言与退出；root route 改为实际 MemoryRouter 从 `/` 进入 chat workspace，并把 router fixture 更新为 current `Conversation` shape、隔离与路由无关的全局 stream。
- Rationale: 构建与用户操作才是分发/路由/导航的有效 seam；HTML/`.gitignore` 字符串、React element 类型和 Tailwind class 不能证明真实视觉。路由测试仍应直接证明页面可达，但不应附带真实网络副作用或旧 API fixture。
- Evidence:
  - Tests: App/router/AppShell/Me 定向 `4 files / 13 tests passed in 1.63s`；current fixture 修正后 router `4 passed` 且不再输出 `/im/v1/sync` invalid-URL error；完整 M16 从 `19 files / 105 tests` 收敛为 `17 files / 88 tests passed in 2.95s`。
  - Entry: Testing Library 仍从 authenticated root 打开 chat workspace，执行 desktop/mobile nav、UserMenu/Me 退出、语言切换并观察 localStorage/router/auth state；零产品源修改。
  - Frontend State Matrix: default、empty unauthenticated、mobile、desktop 与 unread 代表性状态仍由保留的 App/router/shell/Me tests 覆盖。
  - Browser QA: N/A（测试资产重构，无 UI/product delta）。
  - E2E/Regression: 永久 regression 为收敛后的 DOM interaction/state Vitest；本 R 不新增浏览器 E2E。
  - Visual/Interaction: N/A；删除的 class/text scan 不能作为真实视觉证据，且无样式改动。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复 raw-text 与 prototype/CSS 断言，不影响产品源码或数据。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 收敛 auth freshness/store lifecycle 与 notification/i18n 同 seam 重复。

## R2 — 收敛 auth 与 notification 状态保护

- 状态: DONE
- Context: auth-session 把同一 refresh readiness 分支按 30 秒/过期和 500/503 拆成边界枚举，auth-store 又把一次 session lifecycle 拆成初值/set/clear；notification leaf tests 分别枚举 browser API 缺失、granted/denied/default、visibility getter/callback，i18n 对同一中文 namespace 逐 key 重复精确文案。
- Decision: auth 保留 fresh/near-expiry、single-flight、HTTP+WS 共用、401/503/network 与账号切换竞态，只删精确 TTL/同类状态重复；store 合并 persist→clear lifecycle，保留 hydrate/malformed 和 delayed identity；completion 删除退役 alias，visibility 合并订阅生命周期，Notification API 按 support/permission/show 三个公开 adapter 各保留成功和 suppression seam，i18n 只保留默认与切换持久化的代表性可见翻译。
- Rationale: 当前真实风险是 token rotation、身份隔离、通知资格/副作用和 locale state，而不是某个内部 freshness 常量、每个 5xx 数值或曾存在的 alias/翻译 key 列表。同一公开 adapter 一例可覆盖同类 terminal 状态，账号/网络/权限的独立失败语义仍分别保留。
- Evidence:
  - Tests: auth + notifications + i18n 定向 `11 files / 44 tests passed in 1.82s`；完整 M16 `17 files / 75 tests passed in 3.37s`。
  - Entry: Login form/RequireAuth、authFetch、session readiness、Zustand+localStorage、Notification click→chat route、preference/visibility/unread hooks 均从公开入口观察请求、DOM、副作用或 state；零产品源修改。
  - Frontend State Matrix: authenticated/unauthenticated、error/retry/signed-out、preference disabled、permission denied、visible/hidden、missing API/candidate 与账号切换均有代表性保护。
  - Browser QA: N/A（测试资产重构，无 UI/product delta）。
  - E2E/Regression: 永久 regression 为保留的 auth/notification/i18n Vitest；真实浏览器 Notification permission flow 不属本 unit。
  - Visual/Interaction: N/A；无 UI 或样式修改。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复被合并的状态枚举与退役 alias/逐 key 文案测试，不改变产品代码或持久数据。
- Commits: 本 R2 提交（SHA 以 Git history 为准）。
- Next: R3 收敛 user-stream 内部重复，复核 proxy/setup/config 并完成最新 unit 门禁。

## R3 — 收敛 realtime 并完成配置门禁

- 状态: DONE
- Context: user-stream 已直接保护 single socket、session generation、cursor/resume、resync/recovery 与 malformed isolation，但又用单独 case 锁定 sessionStorage read/write 恰好一次、lower cursor 的内部 setter 分支，并在多例中精确等待 1 秒/25 秒/60 秒 timer 常量。
- Decision: 保留 storage 被阻挡时完整的 resume→dispatch→ping→reconnect memory continuity，以及 resync 失败→重连→lower authoritative cursor→新事件的端到端 runtime case；删除两份内部调用次数/单点重复，将 timer 驱动改为推进下一已安排任务。Vite WS proxy test 与 package/vite/tsconfig/setup/render helper 原样保留，由实际 collection 和 build 验证。
- Rationale: 产品风险是断线后仍能恢复、cursor 不漏/不倒退/可被新 epoch 校正、账号切换不串流和坏事件不污染 fan-out；storage helper 调用次数和退避常量不是公开契约。完整状态机 case 已覆盖被删分支，而且更接近消费者可观察结果。
- Evidence:
  - Tests: user-stream + proxy 定向 `2 files / 16 tests passed in 0.72s`；最新 unit 上完整 M16 `17 files / 73 tests passed in 3.49s`，相对基线从 `19 files / 105 tests` 净减 2 个 raw-text 文件与 32 个低信号/重复 case；完整 frontend `66 files / 608 tests passed in 13.71s`。
  - Build: `tsc -b --pretty false` 与 Vite production build PASS；构建输出定向 `/tmp/refactor-489-M16-build.*`，仓内不产生 `src/IM/frontend/dist/`。
  - Docs/Scope: `scripts/docs_check.py` PASS（218 maintained Markdown sources / 65 required routes）；`git diff --check` 与 changed-path audit PASS，改动仅 M16 foundation tests 和本 milestone 文档。
  - Entry: runtime tests 继续执行 socket open/message/close、session change、cursor storage、sync/recovery、subscriber fan-out；node-environment proxy test 继续证明 `/im` WebSocket 转发配置。
  - Frontend State Matrix: default/empty/error/disabled/permission denied/missing data/mobile/desktop 的适用 foundation 状态均由保留的 73 个 case 代表性覆盖。
  - Browser QA: N/A（测试资产重构，无 UI/product delta）。
  - E2E/Regression: 永久 regression 为收敛后的 M16 Vitest；真实浏览器/real IM service 不属本 milestone。
  - Visual/Interaction: N/A；无产品样式或交互修改。
  - Prototype Comparison: N/A。
- Rollback: 回退 M16 三个 roadpoint commit 可恢复被删除/合并的测试资产，不改变生产代码或用户数据。
- Commits: 本 R3 提交与最终 merge commit（SHA 以 Git history 为准）。
- Next: 无；M16 已达到退出标准，等待合入 unit 分支。

## Promotion Candidates

None.
