# feat-340-M5: frontend-agents-rewrite — Tasks

> 对齐: ../design.md v1

## 目标

Agents 列表 / 详情 / 新建三屏按 Agent-native IM 原型重写;桌面 + 移动响应式对等;
四组卡片(Identity / Behavior / Access & Model / Workspace & Runtime)字段全部接通后端真存盘;
dirty 检测正确驱动 Save/Discard;详情顶部 Open chat ↗ 跳直聊。

## 退出标准

- [ ] Agents 列表桌面侧栏 240px 暗色背景 + 头像 + display_name + agent_id + 在线状态点;移动占满 + tap 进详情
- [ ] 新建入口:列表顶部 `+ New` + UserMenu `New agent`(后者复用现有 Nodes 入口)
- [ ] 详情四组卡片各自渲染原型布局,Identity/Behavior/Access&Model 可编辑,Workspace&Runtime 只读;Workspace 卡片仅详情显示,新建页不显示
- [ ] dirty 检测:任一字段改动后 Save 按钮 enable + accent;Discard 回滚;Save 调 PATCH 返回新 profile_version 后 dirty 清除并显示 "✓ Saved"
- [ ] 详情顶栏 Open chat ↗ 调 createDirectConversation 后路由跳 `/chat/:id`
- [ ] 新建页只显示三组(Identity 含 Owning Node、Behavior、Access & Model);Save 后跳详情;Cancel 回列表
- [ ] 全部网络调用走 authFetch(Authorization: Bearer 自动注入)
- [ ] 文案全部 i18n,英文 + 中文两套 key 增量追加
- [ ] 桌面 + 移动两套布局均通过自动化测试断言
- [ ] 既有 174 个测试全部继续通过,新增测试也全绿

## 测试策略

入口是浏览器 `/settings/agents` `/settings/agents/:id` `/settings/nodes/:nodeId/agents/new`。
所有测试通过 `renderRouter({ routes: appRoutes, initialEntries: [...] })` 真实驱动路由 + Query Client + Auth store,
并 mock 全局 `fetch`(authFetch 调用真 fetch,只是加 Authorization 头) — 这是项目既有约定。

- **R1 测试**:列表页桌面 / 移动两布局可见 + 选中态 + 进入详情链接
- **R2 测试**:详情页四卡渲染 + dirty Save/Discard 真存盘 + Open chat 跳直聊;失败态(409 冲突)正确显示
- **R3 测试**:新建页三卡渲染 + 必填校验 + Save 真创建并跳转
- **R4 测试**:i18n key 切到 zh 后关键文本变成中文

不依赖快照测试(视觉细节由 design-review 流程兜底,本期只做行为测试)。

## Roadpoints

### R1 — list page rewrite (desktop sidebar + mobile)

- 步骤:
  1. 改 `im-agent-config-api.ts` 全部 fetch 调用切到 authFetch(透明加 Authorization 头)
  2. 重写 `agents-list-page.tsx` 为原型布局(240px 暗色侧栏 + agent 行;移动占满)
  3. 顶部 `+ New` 按钮:导航到 `/settings/nodes`(让用户选节点) — 与现有 Nodes 入口一致
  4. 列表展示在线状态点(需结合 nodes 列表)
- 验证:列表展示桌面 / 移动两布局,点击进入详情链接生效

### R2 — detail page four-card rewrite

- 步骤:
  1. 重写 `agent-detail-page.tsx`:四卡(Identity / Behavior / Access&Model / Workspace&Runtime)
  2. 顶栏头像 + display_name + agent_id + node 状态 chip + Open chat ↗ + Save
  3. dirty 检测 + Discard + Save → PATCH;Save 后显示 "✓ Saved" 2s
  4. 沿用 `AllowlistSelector` 但 wrap 进新 Section 样式
- 验证:打开详情、改字段触发 dirty、Save PATCH、Discard 回滚、Open chat 跳转

### R3 — create page three-card rewrite

- 步骤:
  1. 重写 `agent-create-page.tsx`:三卡(Identity 含 Owning Node 下拉、Behavior、Access&Model)
  2. 必填校验 + Save 后跳详情
- 验证:Save 成功跳 `/settings/agents/:newId`,失败显示错误

### R4 — i18n: zh translations + UI 切换断言

- 步骤:
  1. 在 `en.json` / `zh.json` 增量追加 `agents.*` namespace 全部 key
  2. 所有页面用 `useTranslation()` 包裹文案
  3. 用 setLanguage("zh") 后断言中文关键字
- 验证:测试切语言后关键字显示中文
