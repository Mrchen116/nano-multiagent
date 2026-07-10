# feat-340-M6: frontend-nodes-rewrite — Tasks

> 对齐: ../design.md (M6 行 + 决策 11)

## 目标

Nodes 设置页与原型/规范对齐:列表 + alias + status pill(颜色点)+ relay/reporting toggle + last_error 红字 + 节点视角列 agents + 节点视角"新建 agent"入口 + i18n + 空态;并消费 M10 的 `node.status_changed` WS 事件实时刷新 status pill。

## 退出标准

- [x] 旧 EN 字面量改走 i18n,提供 en/zh 文案
- [x] status 用带颜色点 pill 渲染(online green / offline red / degraded amber)
- [x] last_error 非空时以警示色(red-600)渲染
- [x] toggle relay_enabled / reporting_enabled 真存盘(沿用既有 PATCH /im/v1/nodes/:id/config)
- [x] 节点视角列出本节点 agents(node_id 匹配的 agent),offline 节点也显示历史 agents 列表
- [x] 节点视角"Create agent on <node>"入口仅 online 节点显示(沿用既有路由 /settings/nodes/:id/agents/new)
- [x] 空态:nodes 数组为空时显示 empty 文案
- [x] WS `node.status_changed` 到达时,对应 row 的 status pill / last_heartbeat / last_error 实时更新(React Query cache patch)
- [x] 跨租户隔离不在本 milestone 范围(M1 已保证),但消费的事件已是 owner-scoped
- [x] 现有 nodes-page 测试继续通过,新增测试覆盖 status pill / empty / agent list / WS patch

## 测试策略

- 单元/集成:vitest + RTL
  - 现有 `nodes-page.test.tsx` 必须继续过(保持向后兼容:link、alias edit、PATCH 参数)
  - 新增 `nodes-page-status-pill.test.tsx` — status pill 渲染 + last_error 红字 + 空态
  - 新增 `nodes-page-agent-list.test.tsx` — 节点视角列 agents(fetch /im/v1/agents + 按 node_id 分组)
  - 新增 `nodes-page-ws.test.tsx` — 注入 fake WS,emit `node.status_changed`,断言 UI 实时变
- 真实入口已由 e2e/手测覆盖:M10 producer 已合并;本 milestone 不重测后端

## Roadpoints

### R1 — i18n + status pill(颜色点)+ last_error 警示色 + 空态 — DONE

- 步骤:在 en/zh.json 加 `settings.nodes.*` 命名空间;改 NodesPage 走 t();增加 status dot 视觉 + last_error 红字;rows 为空时 empty 文案。
- 验证:新 vitest 用例 status-pill + empty;原 nodes-page.test.tsx 仍过(label 可走 i18n key 默认 EN)。

### R2 — 节点视角列 agents + 仅 online 显示新建入口(已存在,加 list) — DONE

- 步骤:在 NodesPage 内 listAgents(/im/v1/agents),按 node_id 分组,每个节点 section 下渲染本节点 agents 子列表(name + status);保留已有 Create agent on link(仅 online)。
- 验证:新 vitest 用例:mock /im/v1/agents 返回多 agent,断言每个 node 下出现对应 agent 链接 /settings/agents/<id>。

### R3 — WS node.status_changed → 实时 status pill — DONE

- 步骤:在 NodesPage 用 `attachUserConversationStream` 订阅;event_type === `node.status_changed` 时 setQueryData 更新对应 node 的 status / last_heartbeat_at / last_error;cleanup on unmount。
- 验证:新 vitest 用例:渲染后用 fake WebSocket 推送 `node.status_changed` frame,UI status pill 从 online → offline。
