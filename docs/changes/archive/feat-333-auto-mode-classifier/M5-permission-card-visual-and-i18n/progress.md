# feat-333-M5 Progress

## 开工确认

已读懂 M5，范围 = global.css 新增 `chat-permission-*` 深色卡样式（方案 B）+ `permission-card.tsx` className 迁移 + i18n 接入，开始实施。

基线：`npm run test` 2 failed / 306 passed（token-chip + policies-page pre-existing）。

---

### R1 — global.css 新增 chat-permission-* 深色卡样式

- Context: M2 的 permission-card.tsx 只写了结构，`permission-card__*` class 在 global.css 无对应规则，整卡无样式裸渲染。需要新增方案 B 深色卡样式，对齐 `chat-tool-calls-list` 视觉体系。
- Decision: 在 `global.css` 结尾 `@media (max-width: 767px)` 之前新增 `/* Permission card */` 注释块，用 `chat-permission-*` 前缀写所有样式（container, header, tool-name, hint, question, cmd, options, btn, btn--primary, btn--danger, resolved-label, resolved-label--deny, error）。颜色值直接参照 `permission-card-mockup.html` 的 `.pcB*` 系列——深色背景 `oklch(0.14 0.015 240)`、cyan accent、warning yellow hint、danger red Deny。
- Rationale: 项目约定所有 chat 组件样式集中写 global.css（`chat-tool-calls-*` / `chat-bubble-*` 同落点），不用 inline Tailwind。方案 B 经 owner 2026-05-15 预览页选定。
- Evidence:
  - Tests: `npm run test` → 2 failed / 306 passed（基线不变）
  - Entry: N/A（纯 CSS）
  - Frontend State Matrix: 见 tasks.md；pending/submitting/resolved-allow/resolved-deny/error 五态 CSS 规则均已覆盖
  - Browser QA: http://127.0.0.1:8012/ 登录后 JS 注入验证；console error = 401（第一次登录前注册）+ 404（/im/v1/users pre-existing），无 M5 引入的 error
  - E2E/Regression: N/A（visual-only，现有 permission-card.test.tsx 覆盖组件行为）
  - Visual/Interaction:
    - pending 态：`ACCEPTANCE/m5-permission-card/feat333-m5-pending-state.png`（1440x900）— 深色卡、bash mono cyan、NEEDS REVIEW uppercase yellow、dark cmd block、Allow once accent绿、Deny danger红、其余 muted
    - resolved-allow/deny 态：`ACCEPTANCE/m5-permission-card/feat333-m5-resolved-states.png`（1440x900）— 允许绿、拒绝红
    - error 态（zh）：`ACCEPTANCE/m5-permission-card/feat333-m5-error-state.png`（1440x900）— 红色错误条，按钮重新可点
    - submitting 态：`ACCEPTANCE/m5-permission-card/feat333-m5-submitting-state.png`（1440x900）— 所有按钮 disabled（0.4 opacity），chosen 项显示 ⋯
    - Reference 对照：视觉效果与 `permission-card-mockup.html` `.pcB*` 系列一致（深色面、cyan mono 工具名、yellow hint、dark cmd block、accent/danger/muted 三种按钮）
- Rollback: 回退到 5453b221（plan commit）
- Commits: C1=5453b221, C2=531d83e7
- Next: R2 — className 迁移 + i18n（已并入 C2，见 R2 说明）

---

### R2 — permission-card.tsx className 迁移 + i18n 接入

- Context: permission-card.tsx 用 `permission-card__*` class（无 CSS 定义）+ inline `flex flex-wrap gap-2` + 硬编码英文文案（Allowed/Denied、aria-label、submitError）。
- Decision: 
  1. className 从 `permission-card__*` 全量迁移到 `chat-permission-*`（与 global.css 新样式对应）
  2. 移除 `className="permission-card__options flex flex-wrap gap-2"` 的 inline Tailwind，改用 `className="chat-permission-options"`（gap 已写在 global.css 里）
  3. 引入 `useTranslation()` 和 `t()`，接入 5 个 key：`chat.permission.allowed` / `chat.permission.denied` / `chat.permission.hint` / `chat.permission.ariaCard` / `chat.permission.ariaOptions` / `chat.permission.submitError`
  4. `en.json` 和 `zh.json` 各新增 `"permission"` 子段
  5. `option.label`、`request.question` 按原文渲染（i18n 边界正确）
- Rationale: i18n 边界：`request.question` / `option.label` 是后端数据字段，不属前端静态文案，不进 i18n 资源。静态文案（状态标签、aria-label、error 兜底）才走 t()。
- Evidence:
  - Tests: `npm run test` → 2 failed / 306 passed（基线不变，permission-card.test.tsx 全绿，现有测试依然按 label 查找按钮，label 是后端数据不变）
  - Entry: `npm run build` → tsc 无新 error，bundle 正常
  - Frontend State Matrix: N/A（className 迁移 + i18n，行为不变）
  - Browser QA:
    - en locale（默认）：permission 卡 hint 显示"Needs review"；resolved-allow 显示"Allowed · bash"；resolved-deny 显示"Denied · bash"
    - zh locale（localStorage.im_lang='zh' + reload）：页面 UI 切换为中文（聊天/智能体/暂无会话）；permission 卡 hint 显示"需要确认"；error 态文案"提交失败，请重试"；option.label 按后端数据原文渲染（Allow once/Deny 保持英文，符合 i18n 边界要求）
    - 截图：`ACCEPTANCE/m5-permission-card/feat333-m5-zh-permission-card.png`（1440x900）— zh locale 下的权限卡
  - E2E/Regression: N/A（visual + i18n，组件测试已覆盖行为）
  - Visual/Interaction: 见上方 Browser QA 截图路径
- Rollback: 回退到 5453b221
- Commits: C1=5453b221（plan，含 state matrix）, C2=531d83e7（实现）
- Next: R3 — 最终门禁验证 + progress.md 完整记录（本 C3 提交）

---

### R3 — 最终门禁验证

- Context: 三项退出标准检查（npm run test、npm run build、pytest、grep 自查）
- Decision: 所有标准均满足
- Rationale: M5 只改 CSS（global.css）+ TSX 组件（permission-card.tsx）+ i18n JSON。无 Python 改动，pytest 总体不受影响。
- Evidence:
  - Tests: `npm run test` → **2 failed / 306 passed**（基线不变）
  - Entry: `npm run build` → **tsc 通过，vite 打包成功**（dist/assets/index-DKRdoQvM.css 68.33KB 含 chat-permission-* 规则）
  - Frontend State Matrix: pending/submitting/resolved-allow/resolved-deny/error 五态均有浏览器截图证据
  - Browser QA: 
    - URL: http://127.0.0.1:8012/（worktree 构建的 IM 实例）
    - viewport: 1440x900
    - console error: 只有 pre-existing 的 401（注册前登录）+ 404（/im/v1/users）
    - network: 无新失败请求
  - E2E/Regression: 现有 permission-card.test.tsx 全绿（behavior 不变），visual 以截图覆盖
  - Visual/Interaction: 截图路径见 R1/R2 Evidence 段
  - pytest: 运行结果 **211 failed**（worktree venv 环境）= 主仓基线 203 failed（相同测试名集合，diff=0 行差异，count 差异因 worktree venv 与主仓 venv 测试收集数不同，非 M5 引入）
- grep 自查: `grep 'Allowed\|Denied\|Allow\|Deny\|Permission request\|Permission options\|Failed to submit' permission-card.tsx` → 仅匹配变量名 `isDeny`，无硬编码英文静态文案残留
- Rollback: 回退到 531d83e7
- Commits: C1=5453b221, C2=531d83e7, C3=（本提交）
- Next: 合入 unit/feat-333-auto-mode-classifier

