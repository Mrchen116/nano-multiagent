# progress — bugfix-390-M2: restyle-policies-page

### R1 — i18n keys（EN/ZH 补 settings.policies.*）

- Context: 原 policies-page.tsx 全部硬编码英文字符串，无 i18n。重写后需要 EN/ZH 双份 key。
- Decision: 在 `en.json` 和 `zh.json` 的 `settings` 段下新增 `policies` 对象，包含 `title`、`subtitle`、`loading`、`fields.*`（6 个字段标签）、`actions.*`（save/saving/discard/unsavedChanges/saveFailed）共 17 个 key。
- Rationale: 测试环境默认 en locale，`fields.defaultModel = "Default Model"` 等与现有测试 `getByLabelText("Default Model")` 匹配；ZH 同步补齐。
- Evidence:
  - Tests: N/A（纯 i18n 配置，R2 测试验证）
  - Entry: N/A（配合 R2 实现后测试验证）
  - Frontend State Matrix: N/A（配置层，不产生 UI）
  - Browser QA: N/A（配合 R2 验证）
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 plan commit（8b631da2）
- Commits: C1+C2 合并=fc2bfc9d, C3=见 R3 docs commit
- Next: R2 呈现层重写

### R2 — policies-page.tsx 呈现层重写

- Context: 原页面是裸 form（无外壳、硬编码英文、无 mobile、无 loading/error 态），对照 account-page.tsx house style 完全重写呈现层。字段集、API 调用、保存语义全部保持不变。
- Decision: 结构对齐 account-page：外层 `flex flex-1 flex-col overflow-y-auto bg-[oklch(0.95)]`；移动端 sticky 顶栏（`‹ Policies` + 返回键）；桌面端 `<header>` 大标题+subtitle；字段分组进两张白色圆角卡；底部保存区（dirty 检测 + Discard/Save 按钮）；save error 样式化 alert；所有文案走 i18n key。
- Rationale: account-page 是同级页里最完整的 house-style 范本，直接对标复用，避免引入第三种风格。isDirty 检查使按钮在 clean state 保持 disabled，与 account-page 行为一致。label 不嵌套 hint span（保证 aria-label 精确匹配让测试通过）。
- Evidence:
  - Tests: `npx vitest run` — 54 passed (54), 345 passed (345)（含 policies-page.test.tsx 1 test pass）
  - Entry: 真实浏览器 http://localhost:56527/settings/policies — 页面加载正常，字段可编辑，保存功能正常（Default Model 改为 "claude-sonnet-4" 后 PATCH 成功，页面刷新显示新值，按钮回 disabled 状态）
  - Frontend State Matrix: default=已验证卡片布局; loading=样式化"Loading policies…"文本; submitting=按钮 isPending disabled; save error=oklch 红色 alert 渲染; mobile=移动视口 sticky 顶栏+单列已验证; desktop=居中卡 max-w-[620px]已验证
  - Browser QA: URL http://localhost:56527/settings/policies; 执行字段编辑+保存流程; console error 无业务错误（WebSocket warning 是 Vite 代理缺 ws 路由，已知开发环境问题，非本次引入）; network: GET /im/v1/policies 200, PATCH 发出后数据持久化
  - E2E/Regression: 现有 policies-page.test.tsx 通过，不新增测试（visual-only 分类）
  - Visual/Interaction: 见 screenshots/ 目录（桌面+移动+account 对照）
- Rollback: 回退到 fc2bfc9d（R1 i18n keys）
- Commits: C1=fc2bfc9d(与R1合并), C2=b2076774, C3=本 docs commit
- Next: R3 浏览器验收截图 + progress 补齐

### R3 — 浏览器验收截图 + progress.md 补齐

- Context: design.md M2 退出标准要求 worker 留下桌面+移动两视口截图，与 account-page 对照结论。
- Decision: 起 worktree 专属 Vite dev server（端口 56527，VITE_IM_PROXY_TARGET=http://127.0.0.1:8011），用 gstack-browse 登录后验收策略页。
- Rationale: 真实浏览器验收是视觉 milestone 的硬门槛，不能只跑组件测试了事。
- Evidence:
  - Tests: `npm run build` tsc 通过（无 TypeScript 错误）
  - Entry: http://localhost:56527/settings/policies — 已通过完整保存流程
  - Frontend State Matrix: 全状态覆盖（见 R2 Evidence）
  - Browser QA:
    - 桌面 1280×720：大标题 "Policies" + subtitle + 两张白色卡片（模型/审计 + 运行时限制）+ 底部 Discard/Save 区
    - 移动 375×812：sticky 顶栏（‹ + "Policies" 标题）+ 单列卡片 + 底部保存区，无溢出无错位
    - 保存功能：修改 Default Model → PATCH /im/v1/policies 成功 → 页面刷新回显新值 → 按钮回 disabled
    - console errors：无业务错误
  - E2E/Regression: 全量 vitest 345 passed
  - Visual/Interaction:
    - `screenshots/policies-desktop-1280.png` — 桌面视口（1280×720）
    - `screenshots/policies-mobile-375.png` — 移动视口（375×812）
    - `screenshots/account-desktop-1280.png` — account-page 桌面对照
    - `screenshots/account-mobile-375.png` — account-page 移动对照
    - **对照结论**：布局结构完全一致（大标题+subtitle → 白色圆角卡 → 底部保存区）；配色一致（`oklch(0.95)` 灰色背景、白色卡、深色标签）；移动版一致（sticky 顶栏 + 返回键 + 单列布局）。策略页不再格格不入。
- Rollback: 回退到 b2076774（R2 实现）
- Commits: C1=b2076774, C2=b2076774(与R2合并), C3=本 commit
- Next: milestone DONE → 集成到 unit/bugfix-390
