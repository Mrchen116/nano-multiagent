# M4 Progress

## Baseline

- frontend npm test: 2 failed (pre-existing token-chip + policies-page), 305 passed @ unit/feat-333-auto-mode-classifier head 825334c9
- pytest -m "not e2e": baseline 203 failed / 1418 passed @ merge-base ba56e6fa

---

### R1 — 测试基线确认 + tasks.md 建立

- Context: M4 是 reviewer round 2 三项遗留问题修复。在动手前需要确认 baseline 和创建 milestone 骨架。
- Decision: 在 worktree (.worktrees/feat-333-M4) 安装 node_modules 并运行 npm test（从 worktree frontend 目录，非主仓库），确保 baseline 是对 M4 分支代码的正确度量。
- Rationale: 主仓库 frontend 的 npm test 指向主仓库 src，不会反映 worktree 的修改；需要在 worktree 的 frontend 目录单独 npm install。
- Evidence:
  - Tests: worktree npm test: 3 failed (2 pre-existing + 1 new R2 Red test), 305 passed — Red 状态确认
  - Entry: N/A（计划阶段）
  - Frontend State Matrix: N/A（计划阶段）
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 537333b9（plan commit）
- Commits: C1=537333b9（plan files）
- Next: R2 Issue 4 auth header fix

---

### R2 — Issue 4: permission-card.tsx 使用 authFetch 作为默认 fetchFn

- Context: IM 权限卡片 `permission-card.tsx` L61 使用裸 `fetch`，缺少 Authorization header，导致 `POST /im/v1/conversations/{cid}/permissions/{request_id}` 返回 401。项目已有 `authFetch` 工具（`src/features/auth/auth-fetch.ts`），自动注入 Bearer token 并处理 refresh。组件有 `fetchFn` prop 作为测试 seam，需要保留。
- Decision: 将 `permission-card.tsx` 的 `fetchFn` 默认值从 `fetch` 改为导入的 `authFetch`。更新 prop 类型为 `(url: string, init?: RequestInit) => Promise<Response>` 以匹配 `authFetch` 签名。补 `vi.mock("auth-fetch")` 测试验证默认 fetchFn 路径调用 `authFetch` 而非裸 `fetch`。
- Rationale: `authFetch` 已是项目标准的带 auth 的 fetch 工具，与其他所有 API 调用保持一致。保留 `fetchFn` prop 确保单测无需触碰 auth store 仍可注入 mock。
- Evidence:
  - Tests: worktree npm test: 2 failed (pre-existing only), 306 passed (+1 new M4 test Green) ✓
  - Entry: `POST .../permissions/test-perm-req-m4-v2-001 → 200`（浏览器验收，见 R4 Browser QA）
  - Frontend State Matrix: pending/submitting/resolved/error 均有测试覆盖；M4 新增 authFetch 默认路径测试
  - Browser QA: N/A（见 R4 综合浏览器验收）
  - E2E/Regression: permission-card.test.tsx 9 tests passed（含新增 M4 auth mock test）
  - Visual/Interaction: N/A（见 R4）
- Rollback: 7d46eb2d（C1 Red test）
- Commits: C1=7d46eb2d, C2=33630673
- Next: R3 Issue 5 workspace banner

---

### R3 — Issue 5: _load_auto_mode_config_for_repl 读取 workspace 级 config

- Context: `commands.py` 的 `_load_auto_mode_config_for_repl()` 只读 `~/.nanocode/config.yaml`（global），忽略 workspace 级 `.nanocode/config.yaml`。spec A9 要求 workspace 覆盖 global。用户在 workspace 开 `dangerously_skip_permissions=true` 后，REPL 横幅不显示危险警告，与 agent 侧 `load_auto_mode_config()` 的行为不一致。
- Decision: 在 `_load_auto_mode_config_for_repl()` 内新增 `_read_section()` helper，先读 `Path.home() / ".nanocode" / "config.yaml"`（global），再读 `Path.cwd() / ".nanocode" / "config.yaml"`（workspace），workspace 值 field-by-field 覆盖 global，最后解析 `enabled` 和 `dangerously_skip_permissions`。不能 import agent 包（跨包禁止），在本文件内复刻相同的两级合并逻辑。
- Rationale: 对齐 `agent.platform.config.auto_mode.load_auto_mode_config()` 的优先级语义（workspace > global），但不允许 import 该模块。本地复刻比依赖跨包 import 更安全。`Path.cwd()` 反映用户 REPL 启动目录，与 agent 侧 workspace_root 语义一致。
- Evidence:
  - Tests: pytest tests/unit/test_repl_auto_mode_banner.py: 6 passed（含 3 个新增 workspace 优先级测试）
  - pytest -m "not e2e": 203 failed / 1418 passed（与 baseline 完全一致，无新增失败）
  - Entry: CLI 本地验证 — 在 `/tmp/test-workspace-m4/` 写 `dangerously_skip_permissions: true`，`cd` 进去后运行 `_load_auto_mode_config_for_repl()` 返回 `dangerously_skip_permissions=True`，横幅输出 `⚠ WARNING: dangerously_skip_permissions is enabled — all permission checks are bypassed.` ✓
  - Frontend State Matrix: N/A（后端 Python 改动）
  - Browser QA: N/A
  - E2E/Regression: 补 3 个单测：workspace 覆盖 global True/False + 无 workspace config 时 fallback global
  - Visual/Interaction: N/A
- Rollback: 63ed1107（C1 Red test）
- Commits: C1=63ed1107, C2=a2088b63
- Next: R4 polish 按钮间距 + 构建 + 浏览器验收

---

### R4 — 按钮间距 + 前端构建 + 浏览器综合验收

- Context: 权限卡片按钮紧贴（`Allow onceDenyAllow for session...`），需要视觉间距。同时需要构建前端产物、重启 IM、完成浏览器端对端验收（Issue 4 是 blocking，必须看到卡片点击后 HTTP 200）。
- Decision: 在 `permission-card__options` div 上追加 Tailwind 类 `flex flex-wrap gap-2`（0.5rem 间距，与项目 button-group 约定一致）。R2 的 authFetch fix 已一同在 C2 提交。构建在 worktree frontend 目录执行，dist 复制到主仓库（IM 进程从主仓库解析 dist 路径）。IM 进程从 `.worktrees/main` 启动但代码版本过旧（无 permissions 路由），需杀旧进程用 worktree M4 源码重启。
- Rationale: `gap-2` 是项目已有的 Tailwind gap 间距（参考 `agent-detail-page.tsx` `gap-3` 等），`flex-wrap` 确保窄屏按钮换行。
- Evidence:
  - Tests: worktree npm test: 2 failed (pre-existing), 306 passed ✓ (与 R2 后一致)
  - pytest -m "not e2e": 203 failed / 1418 passed ✓（与 baseline 完全一致）
  - Entry: 
    - 浏览器通过 gateway WS 注入 `turn_start` + `permission_request` 事件 → 权限卡片在聊天流中出现 ✓
    - 点击 "Allow once" → `POST /im/v1/conversations/3b974a0a.../permissions/test-perm-req-m4-v2-001 → HTTP 200` ✓（之前 M3 bug 是 401，现已修复）
    - 卡片转为 `Allowed · bash` resolved 状态 ✓
    - Console: 无 JS error ✓
  - Frontend State Matrix:
    - pending: ✓ 权限卡片 4 按钮可见，间距正常
    - submitting: ✓ 单测覆盖
    - resolved(allow): ✓ 浏览器截图 `/tmp/feat333-m4-perm-card-resolved.png` 显示 "Allowed · bash"
    - resolved(deny): ✓ 单测覆盖
    - error: ✓ 单测覆盖
    - mobile: N/A（未测试，不在 M4 范围）
  - Browser QA: 
    - URL: `http://127.0.0.1:8011/chat/3b974a0a433347c59c5ab002c77bf88d`
    - Bundle: `index-daYQ-UWP.js`（M4 build，已验证）
    - 用户路径: 登录 → 打开 Test Permission Card M4 对话 → 卡片显示 → 点击 Allow once → HTTP 200 → 卡片 resolved
    - Console errors: 无
    - Network failures: 无（permission POST 返回 200）
    - Viewport: 1280x720（桌面）
  - Visual/Interaction: 
    - 截图 `/tmp/feat333-m4-perm-card-visible.png`：4 按钮可见，有 gap-2 间距（"Allow once  Deny  Allow for session  Always allow"）
    - 截图 `/tmp/feat333-m4-perm-card-resolved.png`：点击 Allow once 后显示 "Allowed · bash"
    - REPL workspace banner：`/tmp/test-workspace-m4/.nanocode/config.yaml` 写 `dangerously_skip_permissions: true`，`cd` 进目录后运行 `_load_auto_mode_config_for_repl()` 返回危险横幅 ✓
- Rollback: a2088b63（C2 Issue 5 fix）
- Commits: C1=7d46eb2d（测试，与 R2 共用）, C2=33630673（按钮间距+authFetch，与 R2 共用）, C3=TBD
- Next: M4 所有 roadpoint DONE → 集成到 unit branch

---

## Final Test Results

- `npm run test` (worktree frontend): 2 failed (pre-existing token-chip + policies-page) / 306 passed
  - Baseline: 2 failed / 305 passed (+1 new M4 test)
  - No new failures introduced ✓
- `pytest -m "not e2e"` (baseline @ ba56e6fa): 203 failed / 1418 passed
  - Current: 203 failed / 1418 passed — exact match ✓
  - No new failures introduced ✓
