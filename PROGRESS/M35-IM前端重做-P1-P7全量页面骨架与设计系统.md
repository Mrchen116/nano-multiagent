# PROGRESS (Milestone: M35)

- Title: IM前端重做：P1-P7全量页面骨架与设计系统
- Goal: 按 IM前端蓝图在 `src/IM/frontend` 用 React+TS+Vite+Tailwind+Radix+Zustand+TanStack Query 重做前端，完成 P1-P7 页面骨架、响应式切换与 mock settings 可编辑。
- Exit Criteria:
  - P1-P7 路由全落地。
  - 桌面两栏 + 手机单栏切换可用。
  - Chat/Settings 工作区可切换。
  - settings 各页 mock 数据可读可编辑。
  - 前端测试与构建通过。
  - 不依赖 Agent 后端接口。
- Test command: `cd src/IM/frontend && npm run test && npm run build`
- Branch: `milestone/M35`

### Baseline
- Context:
  - execution_mode=`parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M35`，branch=`milestone/M35`。
  - 已在 worktree 建立共享链接：`data/dev-tasks.json` 与 `data/locks/`。
  - 已读取 `COMMENTING_GUIDE.md`、`LOGBOOK.md`、`IM前端蓝图.md`、`IM服务蓝图.md`、`Agent 助手（基于 SDK 的上层应用）蓝图.md`。
- Decision:
  - 采用四段 Roadpoint：先建工程与设计系统，再落地 Chat、Settings、最后做 Playwright 与门禁收口。
- Rationale:
  - 当前仓库不存在 `src/IM/frontend`，需先完成可运行底座，再逐步补齐页面与交互。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（baseline 失败：`no such file or directory: src/IM/frontend`）。
  - Entry: 当前主干未包含 IM 前端目录，失败属于 M35 scope 内缺失能力。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R35.1 Red：先为路由与壳体写测试，确认先红。

### R35.1 前端工程初始化与设计系统底座
- Context:
  - 基线 `test_command` 在 `cd src/IM/frontend` 阶段失败，仓库无前端目录。
  - 需先建立可运行前端工程，并用明确视觉方向的 token 防止模板感。
- Decision:
  - 新建 `src/IM/frontend`（React+TS+Vite+Tailwind v4+Radix+Zustand+TanStack Query）。
  - 先提交壳体测试（App 工作区切换、路由可达）做 Red，再实现 AppShell/Router/主题样式。
- Rationale:
  - 先让门禁链路可执行，再进入页面与交互细化，可降低后续 Roadpoint 的排障成本。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（通过）
  - Entry: 可启动 Vite 应用，`/chat` 与 `/settings/*` 路由骨架已可渲染，主题样式已生效。
- Rollback:
  - `c9ac187`（R35.1 C1，仅测试先红）
- Commits: C1=`c9ac187`, C2=`e43b438`, C3=`fcbb033`
- Next:
  - R35.2 Red：补写 chat 响应式与路由行为测试，覆盖桌面两栏+手机单栏。

### R35.2 Chat 工作区（P1/P2）与桌面/手机响应式
- Context:
  - 需要在 `/chat` 与 `/chat/:conversationId` 同时满足桌面两栏和手机单栏切换。
  - 现有壳体仅占位页，缺少会话列表、消息区、输入区与 mock 数据链路。
- Decision:
  - 新增 mock chat API + React Query 查询/发送 mutation，数据完全本地内存化。
  - 将 `/chat` 与 `/chat/:conversationId` 统一为 `ChatWorkspacePage`：桌面显示会话+详情双栏；手机在详情路由仅显示消息页并提供 Back。
  - 新增 `useIsMobile` 宽度判断和会话/消息组件拆分，保证后续设置页可独立演进。
- Rationale:
  - 单页面控制布局分支可减少路由重复逻辑，同时保留 URL 语义，便于 Playwright 验收覆盖。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（通过）
  - Entry: `/chat` 可浏览会话列表与未选中占位；`/chat/conv-kernel-ops` 可展示消息与输入框；手机宽度下 `/chat` 仅列表，`/chat/:id` 为单栏详情。
- Rollback:
  - `06e4f3e`（R35.2 C1，仅测试先红）
- Commits: C1=`06e4f3e`, C2=`a394561`, C3=`cdf23c9`
- Next:
  - R35.3 Red：补写 settings mock contract 与编辑联动测试，覆盖 P3-P7。

### R35.3 Settings 工作区（P3-P7）+ mock 可读可编辑
- Context:
  - 先前 settings 仍为占位页面，无法编辑 Agent/Nodes/Policies/Account 配置。
  - 目标要求所有设置数据走 mock 且可写回，不接 Agent 后端。
- Decision:
  - 新增 `mock-settings-api` 作为单一 mock 数据源，覆盖 agents/nodes/policies/account 全字段。
  - 用 React Query 管理读写：列表/详情查询 + mutation 更新 + query 失效刷新。
  - 落地五页真实表单：`/settings/agents`、`/settings/agents/:id`、`/settings/nodes`、`/settings/policies`、`/settings/account`。
- Rationale:
  - 通过统一 mock API 可以在不依赖后端的情况下稳定复用数据逻辑，且便于后续替换真实接口。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（通过）
  - Entry: Agent 名称可编辑保存并反馈 `Saved`；Nodes 节点别名与开关可保存；Policies/Account 表单可读写并回显。
- Rollback:
  - `bc30711`（R35.3 C1，仅测试先红）
- Commits: C1=`bc30711`, C2=`0f08257`, C3=`<pending>`
- Next:
  - R35.4：补最终验收测试与 Playwright 桌面/手机真实浏览器检查，收口到 main。
