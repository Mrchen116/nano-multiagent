# feat-333-M5: permission-card 视觉规范 + i18n

## 目标

补齐 M2 遗漏的 `PermissionCard` 样式实现与 i18n 接入：
1. 在 `global.css` 新增 `chat-permission-*` 深色卡样式（方案 B），覆盖 pending/submitting/resolved/error 四态
2. `permission-card.tsx` className 从无定义的 `permission-card__*` 迁移到 `chat-permission-*`，移除 inline `flex flex-wrap gap-2`
3. 硬编码英文文案（resolved 标签、aria-label、错误兜底）接入 `t()`，`i18n/{en,zh}.json` 新增 key

## 退出标准

- `cd src/IM/frontend && npm run test` 不新增失败（baseline: 2 failed / 306 passed）
- `cd src/IM/frontend && npm run build` 通过（tsc 无新 error）
- `pytest -m "not e2e" --continue-on-collection-errors` 不比 baseline 新增失败（baseline 203 failed）
- `permission-card.tsx` 源码无残留硬编码英文静态文案（grep 自查）
- 真实 IM 服务 + 浏览器验收：pending/submitting/resolved/error 四态截图，en/zh 文案切换证据

## 测试策略

- 类型：`visual-only` + i18n（前端样式细节 + i18n 静态文案接入）
- 核心 regression（已存在）：`permission-card.test.tsx` 覆盖四态状态机，无需新增 E2E
- i18n 新增：验证 `i18n.test.ts` 中两种语言 key 均有覆盖
- 真实浏览器验收：四态截图 + 语言切换截图

## UI 状态矩阵

| 状态 | 适用 | 说明 |
|---|---|---|
| pending | ✓ | 卡片可点，按钮正常 |
| submitting | ✓ | 按钮 disabled，选中项显示 busy |
| resolved (allow) | ✓ | success 色标签，按钮消失 |
| resolved (deny) | ✓ | danger 色标签，按钮消失 |
| error | ✓ | 红色错误条，按钮重新可点 |
| mobile | ✓ | flex-wrap 按钮换行，设计已支持 |
| desktop | ✓ | 主要 viewport |
| dark mode | N/A | 项目不支持 dark mode toggle（已是深色卡） |
| empty | N/A | 权限卡始终有内容 |
| loading | N/A | 不存在加载态 |

## 用户路径分类

- `visual-only`：样式迁移（`permission-card__*` → `chat-permission-*`）
- `visual-only`：i18n 文案接入（静态文案，非业务逻辑）

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| pending 四态样式（深色卡） | 浏览器截图验证 | 否（视觉） |
| i18n key 完整性 | i18n.test.ts 自动校验 | 是（已有体系） |
| 无硬编码残留 | grep 自查 | 否 |
| 按钮 disabled/busy 状态 | 现有 permission-card.test.tsx | 是（已有） |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | global.css 新增 chat-permission-* 深色卡样式 | DONE |
| R2 | permission-card.tsx className 迁移 + i18n 接入 | DONE |
| R3 | 构建验收 + 浏览器验收 + 文档 | DONE |
