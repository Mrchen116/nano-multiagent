# M322 Fix stale node status and chat availability mismatch

## Context
- Milestone: `M322`
- Goal: 修复节点状态与聊天可用性在心跳陈旧/连接断开时的产品可见不一致。
- Scope: `src/IM/infra/repositories.py`、`src/IM/application/node_service.py`、`src/IM/api/deps.py`、`tests/im_service/integration/`、`src/IM/frontend/src/features/chat/`、`src/IM/frontend/src/features/settings/nodes/`。

## Roadpoints

### R1.1 Node status freshness + live connectivity alignment
- Status: TODO
- Acceptance:
  - `/im/v1/nodes` 不再把超出心跳有效窗口的节点继续展示为 `online`。
  - 节点断开 WebSocket 连接后，节点状态读取结果可反映实际连接态（不是仅依赖持久化旧状态）。
  - 聊天发送可用性更贴近 live relay 连接状态，避免“UI 可发但 relay 已断”的明显错配。
  - 覆盖 stale-heartbeat mismatch 回归场景（后端 API + 前端可用性门禁）。
- Tests Plan:
  - 在 `tests/im_service/integration/test_nodes_metrics_api.py` 补充 stale heartbeat 与 live connectivity 覆盖。
  - 在 `tests/im_service/integration/test_messages_api.py` 补充 direct-chat availability mismatch 路径回归。
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 与 `src/IM/frontend/src/features/settings/nodes/nodes-page.test.tsx` 补充对应 UI 回归断言。
- DoD:
  - C1/C2/C3 三提交完成。
  - 里程碑指定 test command（按仓库当前测试文件实际存在情况）通过。
  - TASKS/PROGRESS 记录完整并包含入口证据。
