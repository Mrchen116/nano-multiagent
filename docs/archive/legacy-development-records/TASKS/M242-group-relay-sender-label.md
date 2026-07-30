# M242 群聊 sender 显示修复：SSE/relay 优先显示 agent 身份

## Milestone context
- Goal: 修复群聊 relay/SSE 合成消息错误显示 node_id 的问题，优先展示 agent display name，其次 agent_id，并让刷新后的历史路径尽量一致。
- Test gate: `cd src/IM/frontend && npm run build 2>&1 | tail -10 && npx vitest run 2>&1 | grep "FAIL\|×"`
- Scope: `src/IM/frontend/src/features/chat/**` 及前端源码/产物、`TASKS/**`、`PROGRESS/**`
- Out of scope: `src/personal_assistant/`、`src/agent/`、`src/IM/application/`、`src/IM/api/`、`docs/`

## R1 修正 relay synthetic message 的 sender 身份映射
- Status: DONE
- Acceptance:
  - group relay/SSE synthetic agent message 不再显示 node_id 作为 sender label
  - 若 payload 提供 display name，则优先用于群聊 sender label
  - 若 display name 缺失，至少回退到 agent_id，而不是 node_id
  - 现有 NO_REPLY / failure / running 行为保持不变
- Tests Plan:
  - unit: 是。直接覆盖 `toRelayAgentMessage` 的字段优先级，定位最小根因
  - contract: 否。当前无独立 schema 契约，字段优先级属于前端映射逻辑
  - integration: 是。复用 `chat-workspace-page.test.ts` 中页面级事件链路，确保 SSE 合成消息进入 UI 后 sender 正确
  - e2e: 否。Milestone 门禁以 build + vitest 为准，且当前目标集中在前端映射回归
- Expected Tests:
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - 用例：relay.processing 优先 display name；缺 display name 时回退 agent_id
- DoD:
  - 最小红测先失败
  - C1/C2/C3 完整
  - `test_command` 全绿
  - PROGRESS 记录决策、证据、提交 hash、回滚点
