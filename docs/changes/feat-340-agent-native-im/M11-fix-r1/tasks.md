# M11-fix-r1: Post-Acceptance Fix Round 1

## 目标

修复验收 round 1 发现的 8 个 issue（4 blocking + 3 major + 1 minor），让 Chat workspace 核心数据通路可用，WS 实时事件通，SPA 路由全覆盖，i18n 全覆盖，tsc 无错。

## 退出标准

- `npx tsc -b` 无错 ✅
- `npm test -- --run` 全绿（52 文件 / 236 测试）✅
- `pytest tests/im_service/ --ignore=...baseline...` 不引入新 regression ✅（199 passed，较基线 +1）

## 测试策略

- R1(CSS): 补 CSS 规则后 vitest 全绿（组件 snapshot / className 断言通过）
- R2(im-chat-api Bearer): 修 requestJson → 调 authFetch；im-chat-api.test.ts 补 Bearer 断言
- R3(WS token query): 修 chat-stream.ts access_token → token；chat-stream.test.ts 改断言
- R4(SPA fallback): 修 app.py 加 /login /register /me 路由；pytest 补 HTTP 404→200 断言
- R5(i18n): 修 settings-page-shell.tsx 改用 t()；补 settings.nav.* i18n keys
- R6(tsc): 修 account-page.test.tsx fixture 类型
- R7(Policies 链接): 删除 Policies navItem；更新 settings-scroll-layout.test.tsx

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | 补 Chat CSS 规则（chat-* 类名） | DONE |
| R2 | im-chat-api requestJson → authFetch | DONE |
| R3 | WS query param: access_token → token | DONE |
| R4 | SPA fallback: /login /register /me | DONE |
| R5 | i18n: Settings 侧栏 + 顶栏硬编码字符串 | DONE |
| R6 | tsc fix: account-page.test.tsx fixture 类型 | DONE |
| R7 | 删除 Settings 侧栏 Policies 链接 | DONE |
