# feat-795 M1 真栈走查与保留测试现场记录

## 1. 构建与测试验收证据

- **服务端单元与集成/E2E 测试**：
  - 命令：`pnpm exec vitest run apps/im-server/tests`
  - 结果：`76 passed (76)` 文件，`512 passed (512)` 用例全通过（含新增真人 `username` 返回/`@username` 搜索、`owner_user_id`/`owner_display_name` 跨主键对齐与 `/people` SPA 入口回退测试）。
- **前端全量单元与集成测试**：
  - 命令：`npm --prefix src/IM/frontend run test`
  - 结果：`134 passed (134)` 文件，`1,301 passed (1,301)` 用例全通过（含 `i18n.test.ts` 中英文词条对齐、`app-shell.test.tsx`、`conversation-sidebar.test.tsx`、`new-group-modal.test.tsx`、`group-settings.test.tsx`、`agent-profile-page.test.tsx`、`first-use-entry.test.tsx`、`people-directory-page.test.tsx`、`person-popover.test.tsx`）。
- **生产构建与契约检查**：
  - `npm --prefix src/IM/frontend run build` & `pnpm build`：通过（0 TypeScript / Rollup 错误）
  - `pytest tests/contract/test_runtime_dependency_contract.py`：`14 passed`
  - `./scripts/docs-check`：通过

## 2. 桌面与移动端真栈走查摘要

说明：执行期间 T3 Preview 桌面窗口处于遮挡状态（连续两次返回 `"Preview snapshot failed: Preview automation snapshot failed: The browser is not producing screenshot frames. For a desktop tab, show or restore the T3 Code window and try again."`），已关闭临时 Preview Tab 并切换至本仓内置 Playwright Chromium，连接真实隔离栈 `http://127.0.0.1:56708` 完成桌面（`1280×820 @ 2x`）与移动端（`390×844 @ 2x`）全链路走查（`0` 个 `pageerror`）：

1. **一级「同事（`/people`）」目录（桌面 & 移动端）**：
   - 左栏主导航（`聊天 | 同事 | 任务 | 智能体`）与移动端 5 项底栏（`聊天 | 同事 | 任务 | 智能体 | 我`，未读角标锚定图标右上角）对齐清晰；
   - 展示全部获批团队成员（陈明 `@chenming`、林夏 `@linxia`、苏晴 `@suqing`、周予 `@zhouyu`、陈泽 `@nano`「你」标识），同事关联的公开个人助手（点击发起 1:1 协作）与负责的数字员工（点击跳转 `/settings/agents/:id`）主次分明；
   - 初次渲染发现 `.im-settings-search` 默认 `240px` 在英文占位符下略微截断，已收口调整 `.im-people-toolbar .im-settings-search` 宽度至 `276px`，中英文占位符均完整显示。
2. **聊天侧栏「同事」筛选 Tab 与 `⌘K` 搜索直达**：
   - 切到「同事」Tab 时，上方显示已有私聊（`苏晴`），下方「可直接联系的同事」直接列出尚未私聊的团队成员（`陈明`、`林夏`、`周予` 及各自公开 PA 提示），彻底消除“暂无会话”死胡同；
   - 按 `⌘K` 唤起搜索框并输入 `@linxia`，在「联系人」分组即时召回尚未建立私聊的 `林夏 (@linxia)`。
3. **群聊上下文 `PersonPopover`、选人弹窗与公开 Agent 资料互链**：
   - 在群聊「产品研发日常」点击 `林夏` 消息头像弹出 `PersonPopover`（展示 `@linxia`、公开 PA、负责的数字员工「体验走查助手」及「发消息 / `@` 提及」），引用回复预览不嵌套按钮；
   - 「新聊天」弹窗提供「全部 / 同事 / 助手」筛选并将同事置顶；「群聊信息」顶部头像簇包含真人与 Agent，加人候选将未入群同事（`@zhouyu`、`@suqing`）置顶；
   - 他人公开数字员工资料页 `/settings/agents/design-critic` 的「管理员」字段展示 `林夏 (@linxia)` 与一键「给 林夏 发消息」入口。

## 3. 保留资源台账（供用户亲自测试）

按用户明确要求（“测试服务别关，我要亲自测测”），本轮隔离测试栈在交付后**保持运行**：

- **保留原因与责任方**：用户亲自登录体验找人、通讯录与上下文名片全套交互（Owner: User Trial）。
- **隔离运行目录 (`WT_ROOT`)**：`/tmp/nano-e2e-feat-795`
- **访问地址 (`IM_URL` / `UI_URL`)**：`http://127.0.0.1:56708`（健康检查：`curl -fsS http://127.0.0.1:56708/health`）
- **守护进程 PID**：
  - IM Server PID：`66944`（`/tmp/nano-e2e-feat-795/.im.pid`）
  - Gateway Node PID：`66974`（`/tmp/nano-e2e-feat-795/.gateway.pid`）
- **预置测试账号**：
  - 主测管理员账号：`nano` / `nano1234`（显示名：`陈泽`，绑定在线个人助手与 P/E/Q 数字员工）
  - 团队同事账号（密码均为 `colleague1234`）：`linxia`（林夏，尚未与 `nano` 建立 1:1 私聊）、`chenming`（陈明，尚未与 `nano` 建立 1:1 私聊）、`zhouyu`（周予，尚未私聊且尚未进群）、`suqing`（苏晴，已有 1:1 私聊）
- **体验完毕后的回收命令**：
  ```bash
  /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-795-people-discovery/scripts/e2e-down.sh --wt /tmp/nano-e2e-feat-795
  ```
