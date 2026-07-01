# feat-451-M1: impl — Tasks

> 对齐: ../design.md

## 目标

完成聊天页历史消息向上滚动分页、阅读位置保持、智能滚底、移动端 Enter 发送、composer 自动增高，以及消息复制/长按菜单/移动端 fork 入口。

## 退出标准

- [ ] 在消息数 > 50 的会话中，用户滚动进入已加载内容上方 1/3 时，自动按 50 条加载更早消息并插入顶部。
- [ ] 加载更早消息后，用户原阅读位置保持稳定；已无更早消息时不再重复请求，并显示无更多提示。
- [ ] 新消息到达时，用户在底部则自动滚底；用户正在看历史则不打扰。
- [ ] 移动端 composer 按 Enter 发送并清空；桌面端 Enter 发送、Shift+Enter 换行保持可用。
- [ ] composer 随多行内容自动增高，达到最大行数后内部滚动。
- [ ] 长按/右键消息气泡出现复制菜单；移动端单聊里长按可 fork 的 agent 完成回复出现 fork；桌面端 hover fork 保持。
- [ ] `npm run test` 在 `src/IM/frontend` 通过。
- [ ] `npx tsc -b` 在 `src/IM/frontend` 通过。

## 测试策略

- 被测行为（来自退出标准）：分页请求参数与 cursor；prepend 合并/去重/排序；滚动阈值 `(scrollHeight - clientHeight) / 3`；加载态/无更多态；阅读位置保持；智能滚底；移动端 Enter；桌面 Shift+Enter；composer 自动增高；复制菜单；移动端 fork 菜单。
- 已有测试在：`src/IM/frontend/src/features/chat/v2/chat-api.test.ts`（扩展分页参数）；`src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展分页集成与 reducer 合并）；`src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`（扩展滚动、composer、菜单）；`src/IM/frontend/src/features/chat/v2/components/message-pane-fork.test.tsx`（已有桌面 fork 回归，保留不重复）。
- 落层/目录/marker：前端 vitest 现有 `src/IM/frontend/src/**` 组件/集成测试；marker：无。
- 可选依赖 importorskip：无。真实浏览器验收使用已有 dev server + Playwright 一次性自测，不落库。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：Playwright 浏览器截图/console/network 结论，记录在 `progress.md`；不提交临时脚本。

## 前端 UI 计划

用户路径分类：`critical-path`（聊天历史分页、发送、实时消息滚底）+ `bug-regression`（移动端 Enter、移动端 fork 不可达）+ `normal-ui`（菜单、loading/no-more 状态、composer auto-grow）。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 已有消息列表 + 新分页 props 默认值组件测试；浏览器入口自测 |
| loading | `isLoadingHistory` 顶部提示组件测试；浏览器入口自测 |
| empty | 保留现有空态测试；分页提示不覆盖空态 |
| error | 本 milestone 不新增历史加载错误 UI；请求失败按 React Query/控制台暴露，progress 记录 N/A |
| disabled | 无更多历史时不再请求；发送按钮禁用保留 |
| submitting | 现有发送 mutation 测试保留；非本 milestone 新行为 |
| permission denied | N/A，消息审批卡不在本 milestone 范围 |
| long content | composer 多行 auto-grow 测试；浏览器输入多行自测 |
| missing/nullable data | fork 资格继续依赖 `kernel_message_id`/agent online；已有 fork 测试保留，新增菜单条件测试 |
| mobile viewport | 浏览器移动 viewport 自测 Enter/长按菜单/fork；组件用 `isMobile` 覆盖 |
| desktop viewport | 浏览器桌面 viewport 自测滚动/右键/Shift+Enter；组件覆盖 hover fork不移除 |
| dark mode（如项目支持） | N/A，当前 chat v2 无主题切换验收要求 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| API cursor/limit/markAsRead 参数错误 | `chat-api.test.ts` | 是 |
| prepend 破坏消息排序或 WS 缓存字段 | `chat-workspace.integration.test.tsx` | 是 |
| 滚动阈值、加载守卫、位置保持 | `message-pane.test.tsx` + 浏览器自测 | 是 + 临时证据 |
| 新消息错误滚底打断看历史 | `message-pane.test.tsx` + 浏览器自测 | 是 + 临时证据 |
| 移动端 Enter/桌面 Shift+Enter 回归 | `message-pane.test.tsx` + 浏览器自测 | 是 + 临时证据 |
| composer 多行高度 | `message-pane.test.tsx` + 浏览器截图 | 是 + 临时证据 |
| 复制/长按菜单/fork 可达性 | `message-pane.test.tsx` + 浏览器自测 | 是 + 临时证据 |

## Roadpoints

### R1 — 历史分页与阅读位置保持

- 状态: DOING
- 步骤: 扩展 API/集成/组件测试；在 workspace 管理 cursor/loading/hasMore；在 MessagePane 按上方 1/3 触发加载并恢复 anchor。
- 验证: 相关 vitest 文件 + `npm run test`。

### R2 — 智能滚底与 composer 输入行为

- 状态: TODO
- 步骤: 扩展组件测试；修正自动滚底条件；移动端 Enter 发送；Shift+Enter 换行；textarea 根据内容 auto-grow。
- 验证: `message-pane.test.tsx` + `npm run test`。

### R3 — 消息菜单、移动端 fork 与真实浏览器验收

- 状态: TODO
- 步骤: 扩展组件测试；新增复制/右键/长按菜单；移动端 fork 放入菜单；补 CSS/i18n；跑真实浏览器入口自测。
- 验证: `message-pane.test.tsx` + `npm run test` + `npx tsc -b` + 浏览器证据。
