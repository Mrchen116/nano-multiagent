# refactor-460-M2 — Progress

## 启动记录

- 2026-07-13：已完整读取 motivation/design、项目 AGENTS/SPEC/注释与测试规范、worker 模板及 M1/current code/test 结构。
- 基线：worktree 初始缺少 `node_modules`，`npm run test` 在 Vitest 启动前报 `vitest: command not found`；确认 `package-lock.json` 完整且主仓存在同版本依赖后执行 `npm ci`，未改源码，随后全量 Vitest 基线通过。
- 范围确认：只改 design M2 范围与路径移动牵连的 frontend imports/tests、README、M2 tasks/progress/evidence；不修改 motivation/design/delta-spec，不返工 M1。

## R1 — canonical Chat 提升与 legacy cluster 删除

- Status: DONE
- Context: 生产路由使用的 current Chat 仍位于 `v2/`，根目录同时保留 4200+ 行 legacy client/mock/types/旧组件；大规模移动必须保持 UI 与数据行为不变。
- Decision: 先用 architecture guard 锁定无版本目录、legacy 文件零残留与 canonical query key，再删除同名 legacy 表面并以 `git mv` 提升 current 文件；同步迁移 router/shell/toast/notifier/Settings imports、`chat-v2` keys、窄 bind 请求、Agent config envelope normalization 与 Agent 详情 canonical createConversation。
- Rationale: 删除根目录同名 legacy 文件后再移动，Git 保留 30+ 个 current 文件的 rename history；迁移全部最后 import 才能真实删除 cluster，不保留 shim。批量 query-key 替换后主动复查并移除了 Agent 详情重复 invalidation，避免两个旧 key 机械收敛成同一调用。
- Evidence:
  - Tests: `npm run test -- --reporter=dot`，61 files / 569 tests passed；`npm run build` passed；`pytest -q tests/contract/test_im_frontend_user_stream_ownership.py`，2 passed。
  - Entry: 真实 IM + Gateway 栈登录 `/chat`，desktop/mobile canonical Chat 均正常加载；路由、shell、workspace、toast、notifier 与 Agent detail 集成回归通过。
  - Frontend State Matrix: desktop/mobile/default/empty 已真浏览器覆盖；loading/error/permission/long-content 保留并通过 current Chat Vitest；无 UI 设计变化。
  - Browser QA: `evidence/r1-browser-report.md`；1440×900 与 390×844，console 0 error/0 warning，登录/nodes/conversations/agents network 均 200。
  - E2E/Regression: `canonical-chat-architecture.test.ts` 锁定无 `v2/`、无 legacy cluster、无 `VITE_CHAT_API_MODE`/`chat-v2`；全量 569 tests 回归 current Chat 行为。
  - Visual/Interaction: `evidence/r1-canonical-chat-desktop.png`、`evidence/r1-canonical-chat-mobile.png`；与现有真实 Web IM 基线一致。
  - Prototype Comparison: N/A（design 明确无 prototype/视觉变化）。
- Rollback: 回退 C2 `86b07fee` 恢复 legacy/v2 双表面；C1 保留最终 architecture 缺口。
- Commits: C1=`14d132d7`, C2=`86b07fee`, C3=本提交。
- Next: R2 实现不可重复 confirm 与可重试 reconciliation 的严格绑定收敛。

## R2 — 绑定确认 session/cache 收敛

- Status: DONE
- Context: 旧绑定页把 confirm 成功与后续 cache 刷新放在一次普通 mutation 中；`/me` 失败或 owner cache 失败后的重试会再次消费同一 token，并且只 invalidate 不等待 active/inactive hot cache refetch 完成就导航。
- Decision: auth store 增加只允许当前同 user、且不改 token 的 `replaceUser`；绑定页以 ref 保存首次成功的 confirm 结果，随后独立执行 `/me`、snapshot replace、六组 owner-derived prefix 的 `refetchType: 'all'`，并等待 `Promise.allSettled` 全部成功后才导航。reconciliation 失败保留成功结果，用户重试从 `/me` 开始，不再 POST bind。
- Rationale: bind token 是一次性资源，不能把已成功的不可逆步骤重放；`invalidateQueries` 返回值只有在明确包含 inactive hot cache 且被 await 时，才能形成“下一页第一次 render 已一致”的可验证边界。`replaceUser` 额外校验当前 session user，防止延迟 `/me` 覆盖已经切换的账号。
- Evidence:
  - Tests: `auth-store.test.ts`、`im-settings-api.test.ts`、`bind-confirm-page.test.tsx` 定向 13 tests passed；全量 `npm run test -- --reporter=dot`，62 files / 574 tests passed；`npm run build` passed。
  - Entry: 真栈先在同一 SPA document 依次访问 Agents、Nodes、Account、Chat 预热六组 query，再进入外部 bind confirm 路由；单击一次后成功进入 Chat。
  - Frontend State Matrix: default/submitting/disabled 由集成测试覆盖；`/me` 首次失败后 retry 由测试证明不会再次 confirm；真实成功态在 Agents/Account/Nodes 三页立即一致。
  - Browser QA: `evidence/r2-bind-report.md`；POST bind 一次为 201，随后 `/me` 与六组 owner refetch 均 200；console 0 error/0 warning。
  - E2E/Regression: 绑定后 auth snapshot 当场出现 default/owned node；Agents 立即出现 4 个 online agent，Account 立即显示默认入口与 Owned nodes=1，Nodes 立即显示 1 online/4 agents。
  - Visual/Interaction: `evidence/r2-bind-agents-immediate.png`、`evidence/r2-bind-account-immediate.png`、`evidence/r2-bind-nodes-immediate.png`。
  - Prototype Comparison: N/A（design 明确无 prototype/视觉变化）。
- Rollback: 回退 C2 `57632320` 恢复旧绑定编排；C1 保留不可重复 confirm 与 settled-cache 契约红测。
- Commits: C1=`725ac203`, C2=`57632320`, C3=本提交。
- Next: R3 清理 README/测试版本叙事与 repository-wide 残留，并完成全量 Python/e2e-critical/真栈 Chat 回归。

## R3 — 零残留收尾与全量真栈验收

- Status: DONE
- Context: 实现删除后，README 仍宣称 Chat 可通过 env 切换 legacy/mock client，production 注释与部分 Agent/Chat 测试仍保留 `im-chat-api`、版本路径与 `createDirectConversation` 假 mock；这些残留会继续误导维护者，也让删除缺少 repository-wide 门禁。
- Decision: 扩展 Python architecture contract，锁定 legacy 路径、生产叙事与 README 零残留；把 README 改为 canonical `authFetch` + shared user-stream 真实数据面，清除测试的旧直聊 mock 与版本命名。随后在真浏览器回归 Agent 详情单聊、实时消息、toast、status/recovery、真实签名过期 JWT refresh 与桌面/移动布局。
- Rationale: TypeScript 同目录 guard 证明 Chat 局部结构，Python contract 覆盖 production tree 与 README，二者共同阻止 compatibility surface 回流；真栈验证则覆盖静态 guard 无法证明的 transport/session/cache 首屏一致性。
- Evidence:
  - Tests: `npm run test -- --reporter=dot`，62 files / 574 tests passed；`npm run build` passed；`pytest -q tests/contract/test_im_frontend_user_stream_ownership.py`，3 passed；`pytest -m "not e2e"`，3499 passed / 1 skipped / 23 deselected。
  - Entry: Agent 详情 `Open chat` 真实发出 canonical `POST /im/v1/conversations` 201，并进入新 direct conversation；两次消息发送均 201，桌面与移动实时收到完整 agent reply、thinking 与 token usage。
  - Frontend State Matrix: desktop/mobile/default/empty/online/offline/reconnected/notification 已真浏览器覆盖；loading/error/disabled/submitting/permission/long-content/missing data 由全量 Vitest 覆盖。
  - Browser QA: `evidence/r3-browser-report.md`；普通旅程 console 0 error/0 warning、请求均 2xx；过期 JWT 专项观察到预期首轮 401、单次 refresh 200 与所有 replay 200。
  - E2E/Regression: `scripts/e2e-critical.sh -m "not slow" -q` 为 15 passed / 2 deselected；`scripts/e2e-critical.sh -m slow --timeout=240 -q` 为 1 passed / 1 xfailed（仓库已声明 #126 heartbeat xfail）/ 15 deselected。默认 90 秒 timeout 会在该测试自身 180 秒等待前中断，故提高 timeout 让预期 xfail 正常收口。
  - Visual/Interaction: `evidence/r3-agent-detail-direct-chat.png`、`evidence/r3-realtime-desktop.png`、`evidence/r3-realtime-mobile.png`、`evidence/r3-agents-offline.png`、`evidence/r3-agents-reconnected.png` 已人工复核，未见路径迁移造成的布局/交互 drift。
  - Prototype Comparison: N/A（design 明确无 prototype/视觉变化，以当前真实 Web IM 为基线）。
- Rollback: 回退 C2 `c8aaed90` 恢复旧 README/测试叙事；C1 保留 repository-wide 零残留契约红测。R1/R2 可按各自 progress 独立回退。
- Commits: C1=`b47441cc`, C2=`c8aaed90`, C3=本提交。
- Next: rebase 最新 unit branch，复跑合并前门禁，合入并清理 milestone worktree/branch。
