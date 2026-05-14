# M4: fix-permission-auth-and-banner-scope

## 目标

修复 reviewer round 2 三项问题：
1. **Issue 4 (blocking)**: IM 权限卡片决策提交 401 — permission-card.tsx 缺 Authorization header
2. **Issue 5 (minor)**: REPL 横幅未读 workspace 级 config — `_load_auto_mode_config_for_repl()` 只读 global
3. **polish**: 权限卡片按钮无视觉间距

## 退出标准

- `npm run test`（cd src/IM/frontend）不新增失败（baseline: 2 failed pre-existing）
- `pytest -m "not e2e" --continue-on-collection-errors` 不新增失败（baseline: 203 failed @ ba56e6fa）
- IM 权限卡片点击决策按钮成功提交（不再 401），证据记录在 progress.md
- REPL 在 workspace 含 dangerously_skip_permissions=true 的 .nanocode/config.yaml 下启动显示危险横幅

## 测试策略

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| auth header 缺失 → 401 | 现有 fetchFn seam 测试 + 浏览器验收证据 | 是（单测补充 auth mock 路径） |
| workspace banner 读取 | pytest 补单测 + CLI 本地验证 | 是 |
| 按钮间距 | 浏览器截图验证 | 否（视觉 polish） |

## UI 状态矩阵（permission-card.tsx）

| 状态 | 覆盖 |
|---|---|
| pending（default） | 已有测试 |
| submitting（disabled buttons） | 已有测试 |
| resolved（allow） | 已有测试 |
| resolved（deny） | 已有测试 |
| error（POST failed） | 已有测试 |
| auth 正常提交 | 需补充 mock auth 路径 |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 测试+验收基线（C1 verify） | DONE |
| R2 | Issue 4: permission-card 使用 authFetch | DONE |
| R3 | Issue 5: _load_auto_mode_config_for_repl 读 workspace | DONE |
| R4 | polish: 按钮间距 + 构建 + 浏览器验收 | DONE |
