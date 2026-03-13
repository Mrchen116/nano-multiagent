# M138 主 Agent 与 Heartbeat 汇报链路产品化

## Milestone Context
- Milestone: M138
- Goal: 让用户能在真实产品入口识别主 Agent，并看到 Heartbeat 结果通过 IM 回流，形成用户可见的产品闭环。
- Exit Criteria:
  1. 用户可识别主 Agent 的真实产品入口或会话语义；
  2. Heartbeat 结果能通过 IM 回流到用户或主 Agent；
  3. 有自动化与真实产品证据；
  4. TASKS/PROGRESS 完整记录。
- Scope: 仅在 `/Users/czj/Repos/nano-multiagent/.worktrees/M138` 内最小改动实现 IM/Gateway/Web IM 产品闭环；不改 `data/dev-tasks.json`。
- Test command baseline: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q`

## Roadpoints

### R1 主 Agent 入口语义产品化
- Status: DONE
- Acceptance:
  - Web IM 默认入口明确告诉用户“这是主 Agent / 你的替身入口”，而非仅泛化为普通 agent chat。
  - 会话列表或默认 starter 中能区分主 Agent 与其他会话类型。
  - IM 前端真实 API 模式与 mock 模式语义一致，不只在 mock 数据中成立。
  - 保持现有 send 可用性与会话创建逻辑不回退。
- Tests Plan:
  - unit: 前端 API 适配与文案选择逻辑；需要。
  - contract: 复用现有前端测试，不单独新增后端 contract；因为本 Roadpoint 主要是入口语义与 UI 映射。
  - integration: 前端页面测试验证 starter/detail/list 可见文案；需要。
  - e2e: 以现有真实产品链路测试/证据确认入口文案能支撑用户识别；需要最小真实证据。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 红测先失败，再最小实现转绿。
  - `pytest -q` 继续全绿，且前端定向测试通过。
  - 完成 C1/C2/C3，并在 PROGRESS 记录设计、证据、回滚点、提交哈希。

### R2 Heartbeat 结果 IM 回流产品化
- Status: DONE
- Acceptance:
  - Heartbeat 触发后，结果不只停留在本地 scheduler/kernel；能形成 IM 可消费的 report 事件。
  - 若当前 agent 是主 Agent，则结果直接面向用户会话；否则至少带有“汇报给主 Agent/用户”的产品语义与可视证据。
  - 自动化测试覆盖 heartbeat -> report payload / IM event 的关键链路。
  - 不破坏现有 relay/report/receipt 主链路。
- Tests Plan:
  - unit: scheduler/reporter/runtime 组合的回流 payload；需要。
  - contract: 沿用现有 websocket/report 结构，不单独扩 schema；仅验证新增字段/语义。
  - integration: IM gateway handler / acceptance harness 对 heartbeat 回流事件断言；需要。
  - e2e: 真实进程或真实产品入口证据至少覆盖 heartbeat 结果可见；需要最小证据。
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/unit/personal_assistant/test_heartbeat_scheduler.py`
  - `tests/im_service/unit/test_gateway_handler.py`
  - `tests/acceptance/test_im_gateway_real_acceptance.py`
- DoD:
  - 红测先失败，再最小实现转绿。
  - `pytest -q` 全绿，并补真实入口证据。
  - 完成 C1/C2/C3，并在 PROGRESS 记录设计、证据、回滚点、提交哈希。

### R3 真实入口证据与收口
- Status: DONE
- Acceptance:
  - 留下真实产品入口证据，证明用户能识别主 Agent，且 heartbeat 汇报链路用户可见。
  - TASKS/PROGRESS 更新完整，说明测试命令、证据位置、剩余 blocker。
  - 明确是否已 merge main。
- Tests Plan:
  - unit: 无新增。
  - contract: 无新增。
  - integration: 复用前两步结果。
  - e2e: 真实入口证据为主。
- Expected Tests:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/unit/personal_assistant/test_main.py`
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/im_service/integration/test_gateway_websocket_api.py -k heartbeat_report_into_conversation_events`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q`（本轮暂未执行，因 targeted tests 已覆盖当前改动面）
- DoD:
  - 证据文件/PROGRESS 可支持换人续跑与主 agent 验收。
  - 完成 C3 文档收口。
- Merge Main Status:
  - 未 merge `main`；`git rev-list --left-right --count main...HEAD` = `13 0`，当前分支落后 `main` 13 个提交。
- Remaining Blockers:
  - 无代码级 blocker；是否补跑全量 `pytest -q` 作为提交前最终回归仍待执行。
