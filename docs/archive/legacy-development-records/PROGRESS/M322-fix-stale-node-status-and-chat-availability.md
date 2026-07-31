# M322 Fix stale node status and chat availability mismatch

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M322`。
- 已将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 派发 baseline 命令首段失败：`tests/im_service/integration/test_nodes_api.py` 在当前仓库不存在（已被 `test_nodes_metrics_api.py` 替代）；后续执行将按现有测试文件覆盖同一节点状态能力。

### R1.1 Node status freshness + live connectivity alignment
- Context: 节点状态读取路径只依赖持久化 `status/last_heartbeat_at`，导致“历史在线快照 + 当前 relay 已断连”时，`/im/v1/nodes` 仍可能返回 `online`；前端 availability 依据该快照会与实际 relay 连通性不一致。
- Decision:
  - 在 `NodeService` 引入 read-time 状态投影：仅对 persisted `online` 节点额外执行两道门禁（心跳新鲜度窗口 + live 连接存在性）。
  - 把 `/im/v1/nodes` 改为异步路由，读取 `GatewayHandler` 当前连接集合并传入 `NodeService`，使节点板与实际 websocket 连接一致。
  - 新增/补强集成回归：覆盖 stale heartbeat 与“fresh 但未连接”节点必须离线，以及 direct-chat 下节点板离线与 relay 503 行为对齐。
- Rationale: 把“在线”定义收敛为“心跳在窗口内 + 当前有 live relay 连接”可直接消除假绿状态；同时不改持久化 schema/运行配置，仅修复读路径判定逻辑，符合里程碑约束。
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_nodes_metrics_api.py tests/im_service/integration/test_messages_api.py -k "stale_and_disconnected or relay_not_live_connected"`（2 passed）。
  - Tests: `pytest tests/im_service/integration/test_nodes_metrics_api.py tests/im_service/integration/test_messages_api.py -k "node or mark_as_read or availability"`（7 passed）。
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts src/features/settings/nodes/nodes-page.test.tsx`（`nodes-page` 通过；`chat-workspace-page` 存在 2 个既有失败，与本里程碑改动无关）。
  - Entry: `test_direct_chat_reports_node_offline_when_relay_not_live_connected` 验证同一路径下 `/im/v1/nodes` 返回 `offline` 且消息 relay 仍明确返回 `503 target_node_id is not connected`，状态与连通性不再冲突。
- Rollback: 回退到 `269aeaa` 可撤销实现层变更，仅保留红测提交。
- Commits: C1=`269aeaa`, C2=`5cedb70`, C3=`(this commit)`
- Next: 更新 `data/dev-tasks.json` 的 M322 为 DONE 并附结果摘要；等待上层集成。
