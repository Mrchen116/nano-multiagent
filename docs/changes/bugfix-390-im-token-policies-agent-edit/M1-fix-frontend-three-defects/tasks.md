# bugfix-390-M1: fix-frontend-three-defects — Tasks

> 对齐: ../design.md v1

## 目标

三处前端缺陷全部修复：token 牌主数字取 total（后端 REST 对齐 WS total 兜底）；全局策略页接回路由 + 用户菜单加「策略」入口；agent-edit 测试断言对齐当前正确保存行为（含 `features:{}`）。

## 退出标准

- [ ] `npm test` 全绿（token-chip / policies-page / agent-edit 三处由失败转绿，不新增失败）
- [ ] `npm run build` 类型检查通过
- [ ] 后端 `pytest -m "not e2e"` 全绿
- [ ] token 牌主数字取 `usage.total`，无 `?? output` 回退
- [ ] REST(`messages.py`) total 兜底 = WS(`event_types.py`) 口径
- [ ] i18n EN/ZH 均补 `shell.userMenu.policies`
- [ ] 用户菜单「节点」下方有「策略」Link 指向 `/settings/policies`
- [ ] `/settings/policies` 路由已接回，PoliciesPage 可达

## 测试策略

- 被测行为（来自退出标准）：
  1. token 牌主数字显示 total（既有测试 R8-3 覆盖）
  2. 全局策略页路由可达（既有测试 policies-page.test.tsx 覆盖）
  3. agent-edit 保存断言匹配含 `features:{}` 的 body（既有测试覆盖）
- 已有测试在：
  - `src/features/chat/v2/components/token-chip.test.tsx`（扩展/回归确认）
  - `src/features/settings/policies/policies-page.test.tsx`（路由接回后自动转绿）
  - `src/features/settings/agents/agent-edit.test.tsx`（更新断言）
- 落层/目录/marker：前端 vitest，无 e2e marker
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：浏览器验收截图记录（policy 入口点击 + token 牌展示），收尾不进套件

**用户路径分类**：
- token 牌：`bug-regression`（历史 bug，已有 regression test）
- 策略页入口：`normal-ui`（功能恢复，vitest 覆盖 + 浏览器临时验收）
- agent-edit 测试：`bug-regression`（测试维护，已有 test 文件更新即可）

**UI 状态矩阵**：
| 状态 | 覆盖计划 |
|---|---|
| default | token 牌 default 有 total → R1 vitest 覆盖 |
| loading | N/A（token 牌无 loading 态） |
| empty | N/A |
| error | N/A |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | N/A |
| missing/nullable data | usage=null → token 牌不渲染（已有测试） |
| mobile viewport | N/A（token 牌与策略页无响应式特殊要求） |
| desktop viewport | 浏览器验收覆盖 |
| dark mode | N/A（项目无 dark mode 体系） |

**测试与验收映射**：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| token 牌主数字取 total | vitest R8-3 用例由红转绿 + 浏览器验收截图 | 是（既有套件） |
| 策略页路由可达 + 用户菜单入口 | policies-page.test.tsx 转绿 + 浏览器点击「策略」入口验收 | 是（既有套件） |
| agent-edit 保存 body 含 features | agent-edit.test.tsx 第一用例断言更新后转绿 | 是（既有套件） |
| i18n EN/ZH 双份 key 对齐 | 浏览器两种语言下查看菜单 | 否（视觉临时验收） |

## Roadpoints

### R1 — token 牌主数字改 total + 后端 REST total 兜底

- 步骤:
  1. `token-chip.tsx` 第 29 行：`const displayed = usage.output` → `const displayed = usage.total`（更新注释为"显示这一轮总消耗 total，由后端契约保证恒有值"）
  2. `messages.py` REST 序列化 total 字段改用 WS 同一兜底：`total=message.token_usage.total` → `total=message.token_usage.total or (message.token_usage.context_used + message.token_usage.output)`
  3. 后端跑 `pytest -m "not e2e"` 验证无回归
  4. 前端跑 `npx vitest run src/features/chat/v2/components/token-chip.test.tsx` 验证 R8-3 转绿
- 验证: `token-chip.test.tsx` 全绿；`pytest -m "not e2e"` 全绿
- Status: TODO

### R2 — 全局策略页：接回路由 + 用户菜单加「策略」入口

- 步骤:
  1. `en.json` / `zh.json` 各加 `shell.userMenu.policies`（EN "Policies" / ZH "策略"）
  2. `router.tsx` 在 `account` 路由前加 `{ path: "policies", element: <PoliciesPage /> }`，import PoliciesPage
  3. `user-menu.tsx` 在「节点」Link 之后、语言组之前加「策略」Link（沿用 nodes Link 样式）
  4. 前端跑 `npx vitest run src/features/settings/policies/policies-page.test.tsx` 验证转绿
- 验证: `policies-page.test.tsx` 全绿；用户菜单可见「策略」入口
- Status: TODO

### R3 — agent-edit 测试断言对齐 features:{}

- 步骤:
  1. `agent-edit.test.tsx` 第一用例第 193-209 行：期望 body 补入 `features: {}`（在 `custom_prompt` 后，对齐组件现状）
  2. 前端跑 `npx vitest run src/features/settings/agents/agent-edit.test.tsx` 验证转绿
- 验证: `agent-edit.test.tsx` 全绿
- Status: TODO

### R4 — 全量门禁 + 浏览器验收

- 步骤:
  1. `npm test` 全量运行，确认 3 failed → 0 failed
  2. `npm run build` tsc 通过
  3. 后端 `pytest -m "not e2e"` 全绿
  4. 浏览器验收：起服务，点用户菜单查看「策略」入口，点击进入，查看 token 牌显示
- 验证: 全量测试绿；build 无 type error；浏览器验收截图记录
- Status: TODO
