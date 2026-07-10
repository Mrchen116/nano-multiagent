# feat-340-M6 — Progress

## R1 — i18n + status pill + last_error 警示色 + 空态

- Context: 既有 nodes 页所有字面量为英文硬编码;status 仅作为纯文字渲染,缺颜色点 / pill 视觉;last_error 与正常 placeholder 同色不易看见;rows 为空也只渲染标题。spec §"Nodes 页" + 场景 C 要求颜色点、红字 last_error、empty 文案 + i18n。
- Decision: 在 `i18n/{en,zh}.json` 新增 `settings.nodes.*` 命名空间;改写 `nodes-page.tsx`:status pill 走查表(online=emerald / offline=red / degraded=amber)同时渲染圆点 + 文案;last_error 非空时以 `text-red-600` 单独渲染;rows 数组为空时单独走 empty 分支。
- Rationale: 颜色点用查表而不写枚举常量(在 i18n 文件外暴露视觉 tokens 会污染调色板单点 §决策 6);empty 分支独立返回让 layout/标题保持但不渲染列表代码,避免 useMemo 触发空数组迭代。
- Evidence:
  - Tests: `vitest run features/settings/nodes/nodes-page-status` → 2/2 pass;legacy nodes-page.test 仍 pass。
  - Entry: 加载 /settings/nodes 渲染节点列表,可见绿/红状态点 + 文案;空数据切到 empty 文案。
- Rollback: revert `b8051d7b` (C2 R1) + `14daed82` (C1 R1)。
- Commits: C1=`14daed82`, C2=`b8051d7b`, C3=本提交。
- Next: R2 — 节点视角列 agents。

## R2 — 节点视角 agent 列表

- Context: spec §Nodes 页 "能从节点视角列出本节点 agents";原页面只显 agent_count 数字,跳转无入口。
- Decision: 在 NodesPage 内并行查询 `/im/v1/agents`(沿用 `listAgentSummaries`),按 `node_id` 分组,渲染在每个节点 section 内部为可点击列表(`Link to=/settings/agents/<id>`);offline 节点也展示历史 agents(只是没有 "Create agent on" 入口)。
- Rationale: 复用已有 settings/agents API,不引入新端点;每条 agent 跳详情页符合 spec §"会话头部 ⚙ 跳对应 agent 配置页"的导航预期。
- Evidence:
  - Tests: `vitest run nodes-page-agents` → 1/1 pass;mock 多个 agent,断言每个 node 内出现 link 且 href 正确。
  - Entry: /settings/nodes 渲染时每节点出现 "Agents on this node" 区块。
- Rollback: revert `85ed4f89` (C2 R2) + `15355825` (C1 R2)。
- Commits: C1=`15355825`, C2=`85ed4f89`, C3=本提交。
- Next: R3 — WS 实时驱动 status pill。

## R3 — node.status_changed WS 订阅 → 实时 status pill

- Context: M10 (4aff4987) 已实装 owner-scoped 推送 `node.status_changed`,M6 退出标准要求 "status 由 WS 实时反映"。
- Decision: NodesPage `useEffect` 调用 `attachUserConversationStream({selfUserId, onEvent})` 订阅用户级 WS(沿用 M3 / M4 已存在的共享单连接 + 自动重连);收到 `event.eventType === "node.status_changed"` 时,`queryClient.setQueryData(["settings","nodes"], …)` 仅 patch 命中 node 的 `status / last_heartbeat_at / last_error` 三字段;同步更新已有 drafts(只覆盖 status/heartbeat/last_error,保留用户未存盘的 alias/relay/reporting 编辑)。
- Rationale: 复用 chat 已有的全局 WS hub(`attachUserConversationStream`)而不开新连接,符合"复杂度最低"原则(决策原则,见 design 决策 2);cache patch 比 invalidate 节省一次 round trip;同时保留本地 draft 避免 WS 事件冲掉用户正在敲的别名。
- Evidence:
  - Tests: `vitest run nodes-page-ws` → 1/1 pass;test 用 FakeWebSocket emit `node.status_changed` 后断言 pill 从 online 翻成 offline 且 last_error 渲染。
  - Entry: 完整套件 185/185 pass;tsc 无新错误(account-page.test.tsx 的 default_entry_node_id null 不兼容为 pre-existing,与本 milestone 无关)。
- Rollback: revert `a3ef5285` (C2 R3) + `0c8346dd` (C1 R3)。
- Commits: C1=`0c8346dd`, C2=`a3ef5285`, C3=本提交。
- Next: 本 milestone 完成,准备 rebase + merge 到 unit 分支。

## Notes

- M10 端 producer 已存在 `build_node_status_changed_payload` + `_handle_register / _handle_heartbeat / disconnect / offline timeout` 四触发点,本 milestone 仅消费,不动后端。
- 跨租户隔离由 M1 owner-scoped 路由 + M10 owner-scoped 广播保证,M6 不重复测试。
- agent.status_changed 事件 producer 同样已合(M10),M6 暂不消费(本 milestone 范围限定 Nodes 页;agent 状态消费属于 M5 agents-rewrite 范围)。
