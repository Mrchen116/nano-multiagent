# M136 Web IM 群聊真实创建与多 Agent 行为收口

## Milestone Goal
补齐 Web IM 真实群聊创建/进入入口，并用自动化与真实产品证据证明群聊会话可以创建和进入、多个 Agent 群聊行为成立，同时核对 @提及门控与 NO_REPLY/群聊行为说明是否满足需求与现状边界。

## Context
- Canonical worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M136`
- Branch: `milestone/M136`
- Execution mode: parallel
- use_worktree: true（已存在 worktree，必须直接复用）
- Test gate (working set for this milestone):
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/acceptance/test_im_gateway_real_acceptance.py`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/app/router.test.tsx`
- Allowed scope:
  - `src/IM/**`
  - `src/personal_assistant/**`（仅限群聊 relay / mention gate / metadata 相关）
  - `tests/im_service/**`
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - `tests/acceptance/**`
  - `src/IM/frontend/**`
  - `TASKS/M136-*.md`
  - `PROGRESS/M136-*.md`
  - `ACCEPTANCE/M136-*`
- Forbidden scope:
  - `data/dev-tasks.json`
  - 新建 git worktree
  - 与 M136 无关的 CLI / core / board 变更

## Roadpoints

### R1. 群聊创建/进入真实入口收口
- Status: TODO
- Acceptance:
  - Web IM 有真实产品入口可创建群聊，或在可靠入口下进入既有群聊。
  - 前后端都能表达群聊参与者与会话类型，不再只依赖 seeded demo 文案。
  - 至少一条 red test 先证明当前入口缺失或语义不足。
  - 完成后可用自动化证明创建后会话列表/详情可见并可进入。
- Tests Plan:
  - unit: 前端 API helper/映射逻辑，快速验证群聊 summary/detail 语义。
  - contract: 不单独新增；复用现有 HTTP shape，避免重复。
  - integration: IM API 创建会话与列表/详情读取。
  - e2e: 前端页面级测试覆盖真实入口按钮/流程；若需要浏览器证据，另在 acceptance 记录。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`（新）
- DoD:
  - 上述测试先红后绿。
  - working set test gate 全绿。
  - C1/C2/C3 完整。
  - PROGRESS 写清入口、证据、回滚点、提交哈希。

### R2. 多 Agent 群聊 relay / metadata / 行为证据收口
- Status: TODO
- Acceptance:
  - 群聊 relay payload 能携带并稳定表达多 Agent 场景所需 metadata。
  - 自动化证明群聊中多个 Agent 的真实行为可被验证，至少包括显式提及与被忽略两类结果。
  - 若现有 relay / repository 缺 metadata，则以最小改动补齐。
  - 证据能说明“多个 Agent 群聊行为成立”，而非只是一条单 Agent reply。
- Tests Plan:
  - unit: Gateway inbound mention gate focused 回归。
  - contract: 不新增独立 contract，避免重复约束。
  - integration: IM ↔ Gateway 群聊 roundtrip、多 Agent routing/metadata。
  - e2e: acceptance harness 级联调覆盖真实消息路径。
- Expected Tests:
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`（新）
  - `tests/acceptance/test_im_gateway_real_acceptance.py`
- DoD:
  - red test 先证明 metadata/多 Agent 证据缺口。
  - 最小实现后 working set test gate 全绿。
  - PROGRESS 记录关键 metadata 与行为边界。

### R3. @提及门控、NO_REPLY/群聊行为说明与真实证据收口
- Status: TODO
- Acceptance:
  - 自动化或真实入口证据证明未 @提及时不会误触发 Agent。
  - 自动化或文档核对说明当前 NO_REPLY/群聊行为说明的真实产品状态：已满足、部分满足、或仍缺实现。
  - 若产品未真正落地 NO_REPLY 固定字符串协议，必须在证据中明确记账，不伪称完成。
  - TASKS/PROGRESS/ACCEPTANCE 形成可复用交接材料。
- Tests Plan:
  - unit: mention gate focused regression。
  - contract: 不新增。
  - integration: 群聊消息/relay 行为结果验证。
  - e2e: acceptance 文档或浏览器/真实入口证据。
- Expected Tests:
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`（新）
  - `ACCEPTANCE/M136-*.md`
- DoD:
  - working set test gate 全绿。
  - 文档证据明确区分“已实现”和“仍缺口”。
  - C1/C2/C3 完整。
