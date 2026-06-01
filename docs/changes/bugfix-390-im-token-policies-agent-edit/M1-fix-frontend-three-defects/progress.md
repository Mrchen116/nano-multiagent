# bugfix-390-M1: fix-frontend-three-defects — Progress

## R1 — token 牌主数字改 total + 后端 REST total 兜底

- Context: token-chip.tsx 第 29 行取 `usage.output` 而非 `usage.total`；REST messages.py total 字段原样透传可能为 None；TypeScript 类型 `total?:number` 需处理。
- Decision: 前端改 `const displayed = usage.total!`（非空断言，注释说明后端契约保证）；后端 messages.py 对齐 event_types.py:67 的 `total or ctx+output` 兜底；测试 fixture 补 total 字段（契约收紧）。
- Rationale: 恢复 R4（f1cc8881）原意图。用非空断言而非 `?? output` 是遵 incident decision 1"坚决否决 output 退让"；fixture 补 total 是因为"total 由后端契约保证"这个约束同样应体现在测试中。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/components/token-chip.test.tsx` → 5 passed (5)
  - Entry: `pytest tests/im_service/ -m "not e2e"` → 263 passed, 0 failed
  - Frontend State Matrix: default(有 total): R8-3 用例覆盖；usage=null: 已有测试覆盖；无 total(旧 fixture): 补 total 后覆盖
  - Browser QA: N/A（本 roadpoint 无独立浏览器验收，合并到 R4 整体验收）
  - E2E/Regression: 既有 token-chip.test.tsx R8-3 用例由红转绿作为 regression 保护
  - Visual/Interaction: N/A（无视觉变化，主数字取值口径变更）
- Rollback: C1=973ef0be, C2=0d1111b4
- Next: R2

## R2 — 全局策略页接回路由 + 用户菜单加「策略」入口

- Context: `/settings/policies` 路由缺失；用户菜单无「策略」入口；EN/ZH i18n 缺 policies key。PoliciesPage + 后端 endpoint 全现成。
- Decision: router.tsx 补 `{ path: "policies", element: <PoliciesPage /> }`；user-menu.tsx 在 nodes Link 后插入 policies Link（图标 ⚙️，沿用 nodes 样式）；EN/ZH 各加 `shell.userMenu.policies`。
- Rationale: 纯接线，不改页面逻辑。用户明确决定入口位置在「节点」下方。
- Evidence:
  - Tests: `npx vitest run src/features/settings/policies/policies-page.test.tsx` → 1 passed (1)
  - Entry: 浏览器访问 http://127.0.0.1:59780/settings/policies 路由可达，页面正常渲染
  - Frontend State Matrix: default(加载策略成功): 浏览器验收覆盖；loading/error: 既有 policies-page 组件内处理
  - Browser QA: URL=http://127.0.0.1:59780/settings/policies；用户菜单点击「Policies」正常跳转；Policies 页显示 Default Model/Audit Level/Max Turn Per Run/Rate Limit/Retention Days 字段；console error 无新增（WebSocket 失败是无 Gateway 节点的环境问题，非本 unit）；截图: /tmp/bugfix390-policies-page.png, /tmp/bugfix390-user-menu.png
  - E2E/Regression: 既有 policies-page.test.tsx 由红转绿作为 regression 保护
  - Visual/Interaction: 用户菜单菜单项：Account → Nodes → Policies（新增）→ Language → Sign out；顺序和样式符合 design.md 决策 2
- Rollback: C2=38865b08
- Next: R3

## R3 — agent-edit 测试断言对齐 features:{}

- Context: agent-edit.test.tsx 第一用例精确 JSON 断言不含 features，但 im-agent-config-api.ts 在 `features !== undefined` 时发送 features；组件 normalizedDraft 包含 `features:{}`（Behavior card feat-379-M3 引入），导致实际 body 含 `features:{}` 而测试期望不含，断言不符。保存功能正常，纯测试陈旧。
- Decision: 在期望 body 中 `system_prompt` 之后补入 `features: {}`，匹配组件当前正确行为。不动产品代码。
- Rationale: 测试维护，无用户侧影响（incident Q4 已核实）。
- Evidence:
  - Tests: `npx vitest run src/features/settings/agents/agent-edit.test.tsx` → 4 passed (4)
  - Entry: N/A（产品行为正常，无用户侧缺陷）
  - Frontend State Matrix: N/A（测试维护）
  - Browser QA: N/A（保存功能正常，无需额外浏览器验收）
  - E2E/Regression: 既有 agent-edit.test.tsx 全 4 用例由 1 failed → 0 failed
  - Visual/Interaction: N/A
- Rollback: C2=69681571
- Next: R4

## R4 — 全量门禁 + 浏览器验收

- Context: 三个 roadpoint 全部完成，跑全量门禁确认无回归，浏览器验收确认用户可观察缺陷已修复。
- Decision: 全量 vitest + npm run build + 后端 pytest + 浏览器验收（登录→用户菜单→Policies 入口→策略页）。
- Rationale: 退出标准全覆盖。
- Evidence:
  - Tests: `npx vitest run` → 54 test files, 345 tests, 0 failed（baseline 3 failed → 0 failed）
  - Entry: `npm run build` → tsc -b 通过，vite build 成功（544kB bundle，既有 chunk size warning 非本 unit 引入）
  - Frontend State Matrix: 全量 vitest 覆盖所有组件的多状态；浏览器覆盖 desktop viewport(1280x720)
  - Browser QA:
    - URL: http://127.0.0.1:59780 登录成功，跳转 /chat
    - 用户菜单展开：Account → Nodes → Policies（新增，⚙️ 图标）→ Language → Sign out
    - 点击「Policies」→ 跳转 /settings/policies，页面渲染完整（6 字段 + Save Policies 按钮）
    - Console errors: 无新增错误（WS/404 是无 Gateway 的环境问题）
    - Network: /im/v1/policies GET 返回 JSON，策略页加载成功
    - 截图: /tmp/bugfix390-user-menu.png, /tmp/bugfix390-policies-page.png, /tmp/bugfix390-chat-view.png
  - E2E/Regression: 3 个失败测试全部转绿；其余 342 个既有测试零回归
  - Visual/Interaction: 用户菜单布局符合 design.md 决策 2；策略页显示正常
- Commits: C2=全量门禁通过（无新 commit，门禁在各 R 已跑），浏览器验收截图已记录
- Next: 集成到 unit 分支
