# PROGRESS — M244 修复多 mention 仅显示单 agent 回复

## Startup
- Milestone: M244 / 修复多 mention 仅显示单 agent 回复
- Execution mode: serial
- Worktree: none（按要求直接在主仓执行）
- Branch: `main`
- Commenting commitment:
  - 遵守 `COMMENTING_GUIDE.md`：public API 使用 Google 风格 docstring；注释只解释意图、边界、代价。
- Prevention rules applied:
  - 直接在主仓执行，不创建/进入 worktree。
  - 端到端排查 relay task identity、SSE event fan-out、synthetic message IDs、frontend dedupe/merge，不停留在前端表象。
  - 不修改 M244 之外的 milestone 文档；不手改 `data/dev-tasks.json`。
- Relevant reusable notes from `LOGBOOK.md`:
  - hook/event 相关测试断言关键字段，不写死模块/事件总数。
  - 真实入口问题优先核对事件身份与链路契约，而不是只看单点 happy path。

## Baseline
- 派发包原始 `test_command` 中的 `tests/IM/frontend/src/features/chat/chat-workspace-page.test.tsx` 路径不存在，导致基线命令先在文件路径阶段失败；这属于测试命令漂移，仍在本 milestone 记录并改用仓库中实际存在的 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 作为等价前端门禁。
- 代码静态排查初步结论：
  - 前端 `toRelayAgentMessage()` 目前固定生成 `message_id = ${message_id}:agent`，`upsertMessage()` 又按 `message_id` 去重；同一用户消息 fan-out 给两个 agent 时，两条 agent 回复天然冲突。
  - Gateway `node.report` → IM `relay.processing/relay.report` 持久化路径当前未稳定保留 `relay_task_id` / `agent_id` / sender identity，导致前端缺少可与 receipt 对齐的 per-agent 合成 key。
  - `relay.completed` / `message.delivered` 虽包含 `agent_id` 与 `relay_task_id`，但前端仍只按原始 `message_id` 合成，因此最后只会剩一条 agent 消息。

---

### R1 固化多 mention 回归红测并定位身份冲突
- Context:
  - 真实问题不是“只跑了一个 agent”，而是同一条群聊消息 fan-out 给两个 agent 后，UI 合成层若只用 `${message_id}:agent` 或只看原始 `message_id`，两条回复会在页面去重时互相覆盖。
  - 需要同时覆盖两类回归：一类是前端 `toRelayAgentMessage()` / 页面流式更新；另一类是 IM 事件回放时 `relay.processing` / `relay.report` 是否还能带回稳定 per-agent identity。
- Decision:
  - 在 `tests/im_service/integration/test_m136_group_chat_flow.py` 新增 dual-mention 回归，固定 `relay.processing`/`relay.report` 与 `relay.completed`/`message.delivered` 都能区分 `agent_id` 和 `relay_task_id`。
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 新增页面级双 mention 用例，分别覆盖“先靠 relay.accepted+run_id 回填身份”和“事件直接携带 per-agent identity”两条路径。
- Rationale:
  - 只测 completed receipt 不够，因为真实 UI 先看到 processing，再被 report/completed 覆盖；回归必须把整条可见链路一起锁住。
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_m136_group_chat_flow.py`；`npm --prefix src/IM/frontend test -- src/features/chat/chat-workspace-page.test.ts`
  - Entry: 前端页面测试稳定断言同一条 `@agent:Q @agent:A` 消息会留下两条 agent 气泡，而不是只剩一条。
- Rollback: 回到引入 M244 前的上一稳定点，删除 dual-mention 回归用例即可恢复旧行为基线。
- Commits: C1=未创建（按本次要求直接在主仓续跑且未单独提交）, C2=未创建, C3=未创建
- Next: 进入实现修复，确保 relay/Gateway/SSE/frontend 都使用稳定 per-agent identity。

### R2 修复 relay/Gateway/SSE 身份链路并保持同 agent 事件可归并
- Context:
  - Gateway `relay.processing` / `relay.report` 上报天然先带 `run_id`，但并不总是直接携带 `agent_id` / `relay_task_id`；而前端同一 agent 的 processing → report → completed 又必须归并成同一个 synthetic message。
  - 若只用 `relay_task_id` 做前端 key，同一 agent 的不同阶段事件可能分裂；若只用 `message_id`，不同 agent 会碰撞。
- Decision:
  - 前端 `chat-workspace-page.tsx` 改为优先用 `agent_id`、其次 `relay_task_id`、再回退 hint 生成 synthetic message id，即 `${message_id}:agent:${identity}`；同时用 `relay.accepted` 建立 `run_id -> {identity, sender}` 映射，给后续 processing/report 补身份。
  - IM `EventService` 在 SSE replay/polling 时回查历史 `relay.accepted` 事件，把 `agent_id` / `relay_task_id` / `sender_display_name` 回填到缺失的 `relay.processing` / `relay.report` 载荷，保证页面刷新或晚订阅仍能拿到稳定身份。
  - Relay fan-out 保持“一位参与 agent 一条 relay”，Gateway 群聊路由优先尊重 payload 里的 `message.agent_id`，避免 fan-out 后又被 mention 列表重新折回第一位 agent。
- Rationale:
  - 稳定身份必须同时满足“不同 agent 不冲突”和“同一 agent 多阶段可归并”，因此 key 选 `agent_id` 最合适，而 `relay_task_id` / `run_id` 仅作为补洞路径。
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_m136_group_chat_flow.py` → 4 passed；`uv run pytest tests/im_service/integration/test_m136_group_chat_flow.py` → 4 passed；`npm --prefix src/IM/frontend test -- src/features/chat/chat-workspace-page.test.ts` → 34 passed。
  - Entry: 同一 turn 的 `relay.processing` / `relay.report` / `relay.completed` / `message.delivered` 均保留两位 agent 的独立身份，且每位 agent 自己的阶段事件仍归并到同一个气泡。
- Rollback: 回退到移除 per-agent synthetic key 与 EventService enrichment 之前的稳定点；若要重做，优先保留 R1 回归测试再重调实现。
- Commits: C1=未创建（按本次要求直接在主仓续跑且未单独提交）, C2=未创建, C3=未创建
- Next: 做真实浏览器验证，并据此决定是否更新 dev-tasks 为 DONE。

### R3 真实回归验证多 mention 群聊可稳定看到两个 agent 回复
- Context:
  - M244 的验收口径不接受“只有测试绿”；必须走真实 IM-hosted 浏览器、真实 gateway、真实 runtime，证明一条 dual-mention 消息在人眼可见的线程里真的留下两条回复。
  - 派发包原始 `test_command` 中前端路径漂移为 `tests/IM/frontend/src/features/chat/chat-workspace-page.test.tsx`，因此需要记录等价实际门禁命令。
- Decision:
  - 复用 canonical `ACCEPTANCE/m170-runtime` 已在线运行时，临时把 `agent-m170-alpha` / `agent-m170-beta` system prompt 改为唯一 nonce 回复，使用 Playwright 打开真实 `http://127.0.0.1:18031/chat`，创建群聊后发送一条同时 `@agent-m170-alpha @agent-m170-beta` 的消息，并等待页面消息区同时出现两条唯一回复；验证后再恢复 agent 配置。
  - 同步核对运行时 SQLite：同一人类消息下存在两条 completed relay receipt 和两条 `message.delivered` agent identity。
- Rationale:
  - 唯一 nonce 回复可以排除历史消息/预览串扰；同时查 UI 与 DB，能证明不是“页面偶然显示”或“后端已完成但 UI 丢了一条”。
- Evidence:
  - Tests: 原始派发门禁因路径漂移失败；实际执行门禁为 `pytest tests/im_service/integration/test_m136_group_chat_flow.py`、`uv run pytest tests/im_service/integration/test_m136_group_chat_flow.py`、`npm --prefix src/IM/frontend test -- src/features/chat/chat-workspace-page.test.ts`，均全绿。
  - Entry: 真实浏览器对 `http://127.0.0.1:18031/chat` 发送 `@agent-m170-alpha @agent-m170-beta please both answer exactly as configured for M244 f098143e.` 后，页面消息区同时出现 `M244_ALPHA_f098143e` 与 `M244_BETA_f098143e`；运行时 DB 同一 `message_id=4274d00aa13146769882bb4e2aa76ade` 下记录两条 completed relay（agents=`agent-m170-alpha`,`agent-m170-beta`）和两条 `message.delivered`。
- Rollback: 若后续回归失败，可先回到 R2 完成时的稳定点，再复用本节的真实验证步骤重测。
- Commits: C1=未创建（按本次要求直接在主仓续跑且未单独提交）, C2=未创建, C3=未创建
- Next: 使用脚本把 M244 更新为 DONE，并在结果里写入测试与真实验证摘要。
