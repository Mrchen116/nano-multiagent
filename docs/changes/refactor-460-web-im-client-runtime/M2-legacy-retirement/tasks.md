# refactor-460-M2: legacy-retirement — Tasks

> 对齐: ../design.md（2026-07-13）

## 目标

Web IM 只保留无版本后缀的 canonical Chat；绑定确认与 Agent 详情单聊等最后入口不再依赖 legacy client，且绑定后的 auth snapshot 与六组 owner-derived hot cache 在导航前完成收敛。

## 退出标准

- [ ] 原 `features/chat/v2/` current 文件经 `git mv` 提升到 `features/chat/`，所有生产与测试 import/query key 使用 canonical 命名。
- [ ] legacy `im-chat-api.ts`、`chat-api.ts`、`mock-chat-api.ts`、`types.ts`、旧 ConversationList/MessagePane 及只服务旧路径的测试删除，不保留 shim。
- [ ] 绑定确认只消费 token 一次；随后 `/me` 替换同 user auth snapshot，并等待六组 owner-derived prefix 以 `refetchType:'all'` 收敛后导航；reconciliation 失败重试不再 confirm。
- [ ] Agent 详情单聊使用 canonical `createConversation`，Agent config 自己归一化 items envelope。
- [ ] 生产源码无 `VITE_CHAT_API_MODE`、`chat-v2` query key、legacy import 或第二个 user-stream socket；README 与真实入口一致。
- [ ] `npm run test`、`npm run build`、相关 Python contract、`pytest -m "not e2e"`、`scripts/e2e-critical.sh` 全绿。
- [ ] 真栈预热 Chat/Settings cache 后，绑定 Node/Agent/默认入口立即可见；M1 实时旅程及桌面/移动 Chat 回归证据持久化在 `evidence/`。

## 测试策略

- 被测行为（来自退出标准）：canonical Chat 路径与单一 query key；legacy cluster 零残留；bind confirm/reconciliation 严格顺序与可重试边界；同 user auth snapshot 持久替换；Agent 详情 canonical 单聊；Agent envelope normalization；真栈绑定与 M1/桌面/移动回归。
- 已有测试在：`src/IM/frontend/src/features/chat/v2/legacy-isolation.test.ts`（迁移为 canonical architecture guard）、`src/IM/frontend/src/features/auth/auth-store.test.ts`、`src/IM/frontend/src/features/settings/im-settings-api.test.ts`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`、`src/IM/frontend/src/features/settings/agents/im-agent-config-api.test.ts`、`src/IM/frontend/src/app/router.test.tsx`；绑定页无合适行为测试，新建 `src/IM/frontend/src/features/chat/bind-confirm-page.test.tsx`，因为它是跨 auth/query/navigation 的页面编排入口。
- 落层/目录/marker：frontend Vitest 与现有源码同目录，marker：无；architecture contract 在 `tests/contract/`，marker：无；真进程/真浏览器证据为 milestone 一次性验收，不新增常规测试套件。
- 可选依赖 importorskip：无；浏览器验收复用仓库已有 Playwright 依赖与 e2e 脚本。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真栈浏览器截图、console/network 与关键旅程报告，持久落在 `M2-legacy-retirement/evidence/`；临时驱动脚本不入库。

## 前端实施计划

- 用户路径分类：`critical-path`（Chat、绑定、Agent 详情单聊、M1 实时恢复回归）；无视觉重设计，现有真实 Web IM 是交互/视觉基线。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 绑定成功进入 Chat；Agent 详情打开单聊；桌面 Chat |
| loading | bind reconciliation 期间按钮维持 pending；现有 Chat loading 回归 |
| empty | Chat 空会话/未选择会话沿现有集成测试与真栈抽检 |
| error | bind confirm 错误与 reconciliation 错误明确显示；单聊创建失败保留 banner |
| disabled | 缺 bind token、pending 时按钮禁用 |
| submitting | confirm/reconciliation 全阶段阻止重复点击 |
| permission denied | 无新增权限状态；现有 Chat permission card 测试回归 |
| long content | 无视觉改动；现有 Chat 长内容/工具卡测试回归 |
| missing/nullable data | bind token 缺失；Agent 无 user_id 的既有错误反馈回归 |
| mobile viewport | 真栈移动 Chat 核心交互截图与发送/实时回复 |
| desktop viewport | 真栈桌面 Chat、绑定、Agent 详情单聊 |
| dark mode（如项目支持） | N/A：项目未声明 dark mode 为本 milestone 契约 |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 大规模路径移动误改行为 | canonical architecture guard + 全量 Vitest + build + router/Chat integration | 是 |
| bind token 被二次消费或 cache 未 settled 就导航 | BindConfirmPage 集成测试，预填六组 hot cache 并驱动失败后重试 | 是 |
| auth `/me` 延迟响应覆盖切换账号 | auth-store observable behavior test | 是 |
| Agent 详情仍调用 legacy 单聊或双 cache | 现有 agent-detail-page 行为测试迁移 | 是 |
| 真栈绑定后 owner-derived 数据仍旧 | 预热 Chat/Settings 后真实绑定并截图/报告 | 否，一次性交付证据 |
| M1 实时/桌面移动 Chat 回归 | `scripts/e2e-critical.sh` + 真浏览器桌面/移动关键路径、console/network 检查 | 脚本既有；截图/报告一次性 |

### Prototype / Reference Contract

N/A：design 明确不改变 UI/交互/视觉，不产 prototype；以当前真实 Web IM 为基线。

## Roadpoints

### R1 — canonical Chat 提升与 legacy cluster 删除（DONE）

- 步骤：先把 architecture/isolation guard 改为最终 canonical/零残留契约并验红；删除同名 legacy 表面，使用 `git mv` 提升 current Chat；迁移所有 imports 与 `chat-v2` query key，删除失效旧测试。
- 验证：canonical Chat 相关 Vitest、router/shell/notification/toast 测试、Python user-stream ownership/前端架构 contract、production build。

### R2 — 绑定确认 session/cache 收敛（DOING）

- 步骤：先补 auth replaceUser 与 BindConfirmPage 集成红测；在 settings client 增加窄 bind 请求，页面持有不可重复 confirm result 与可重试 reconciliation，严格执行 `/me`、同用户 snapshot replace、六组 cache refetch settled、导航。
- 验证：auth-store、settings API、bind 页面集成测试；失败重试断言 confirm 只调用一次且导航在全部 refetch settled 后发生。

### R3 — 零残留收尾与全量真栈验收（TODO）

- 步骤：以 repository-wide guard 验红 README/测试残留，清理过期 mock 与版本叙事；完成全量门禁及持久化真栈证据，并复验已迁移的 Agent 详情 canonical 单聊与 Agent envelope normalization。
- 验证：Agent detail/config 测试、全量 Vitest/build/Python contract/non-e2e/e2e-critical；预热 cache 后真实绑定、Agent 单聊、M1 实时旅程、桌面/移动 Chat 与 console/network 检查。
