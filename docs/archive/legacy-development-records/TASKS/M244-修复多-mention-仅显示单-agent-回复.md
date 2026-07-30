# M244 修复多 mention 仅显示单 agent 回复

## Milestone context
- Goal: 修复一次消息同时 @ 两个 agent 时，虽然产生两个大模型请求，但前端只看到一个 agent 回复的问题；先完成 communication context 修复后的多 mention 群聊根因修复，再补齐 relay/SSE/frontend 合成链路，确保两个 agent 的回复都稳定显示。
- Execution mode: serial
- use_worktree: false（按要求直接在主仓执行，不创建/进入 worktree）
- Branch: `main`
- Test gate (派发包原文): `pytest tests/im_service/integration/test_m136_group_chat_flow.py tests/IM/frontend/src/features/chat/chat-workspace-page.test.tsx && if command -v uv >/dev/null 2>&1; then uv run pytest tests/im_service/integration/test_m136_group_chat_flow.py; fi`
- Allowed scope:
  - `src/IM/frontend/src/features/chat/**`
  - `src/IM/application/**`
  - `src/personal_assistant/gateway/**`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `TASKS/**`
  - `PROGRESS/**`
- Forbidden scope:
  - unrelated product config files
  - `data/dev-tasks.json` manual editing
- Startup notes:
  - 遵守 `COMMENTING_GUIDE.md`：public API 用 Google 风格 docstring；注释只写意图/边界，不复述代码。
  - 复用 `LOGBOOK.md` 规则：hook/事件相关测试不要写死总数；优先验证真实入口与真实事件身份。
  - prevention_rules 已应用：必须端到端排查 relay task identity、SSE event fan-out、synthetic message IDs、frontend dedupe/merge，不接受只修前端表象。

## Baseline
- 派发包中的前端测试路径 `tests/IM/frontend/src/features/chat/chat-workspace-page.test.tsx` 在当前仓库不存在；基线命令因此先失败，属于本 milestone 的测试门禁定义漂移，而非代码行为失败。
- 当前代码审计已发现高风险根因候选：前端 synthetic agent message 固定使用 `${message_id}:agent` 作为 key；同一条用户消息 fan-out 给多个 agent 时，这会把多个 agent 回复折叠成同一条 UI 消息。
- 当前上游链路还存在身份漂移：Gateway `node.report` → IM `relay.processing/relay.report` 持久化时未稳定保留 `relay_task_id` / `agent_id` / sender identity，导致前端难以对齐同一 agent 的 processing/report/completed 序列。

## Roadpoints

### R1. 固化多 mention 回归红测并定位身份冲突
- Status: DONE
- Acceptance:
  - 自动化先证明“同一条群聊消息 @ 两个 agent 时，当前前端只显示一条 synthetic agent reply”。
  - 自动化先证明“同一条消息的两条 relay 链路在 IM/SSE 层缺少稳定的 per-agent identity”。
  - 红测覆盖 processing/completed 两类可见事件，不只覆盖单一 happy path。
  - 结论能明确指出是 message identity collision，而不是模型/路由未执行。
- Tests Plan:
  - unit: 否；本 milestone 优先用页面级与集成链路测试覆盖真实去重问题。
  - contract: 否；暂无独立 schema 文件，身份字段通过 integration/page tests 固化。
  - integration: 是；扩展 `tests/im_service/integration/test_m136_group_chat_flow.py`，断言 group 多 mention 产生的 relay/receipt/SSE 具备区分两位 agent 的身份字段。
  - e2e: 是（页面级）；扩展 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`，断言同一用户消息的两位 agent 回复不会互相覆盖。
- Expected Tests:
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 红测先失败。
  - 记录根因：identity collision 发生在哪些 payload / merge key。
  - 后续修复可直接复用这些测试作为回归门禁。

### R2. 修复 relay/Gateway/SSE 身份链路并保持同 agent 事件可归并
- Status: DONE
- Acceptance:
  - 同一条 group 消息 fan-out 给两个 agent 时，每条 relay 链路都带稳定 `relay_task_id` / `agent_id` 身份，不再只共享原始 `message_id`。
  - 同一 agent 的 running/report/completed/message.delivered 事件能归并到同一 synthetic agent message。
  - 不同 agent 的事件不会互相覆盖。
  - 现有 NO_REPLY、失败态、背景 context relay 语义不回退。
- Tests Plan:
  - unit: 否；通过 integration + page-level tests 覆盖端到端身份传递。
  - contract: 否；事件字段直接在现有 SSE payload 测试中断言。
  - integration: 是；验证 IM persisted events / relay payload identity。
  - e2e: 是（页面级）；验证 processing → completed 合并到各自 agent 气泡。
- Expected Tests:
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 最小实现后，上述测试转绿。
  - 代码改动仅限允许范围。
  - PROGRESS 写清 identity 设计与兼容边界。

### R3. 真实回归验证多 mention 群聊可稳定看到两个 agent 回复
- Status: DONE
- Acceptance:
  - 回归验证一次消息同时 `@agent:Q @agent:A` 时，前端稳定可见两位 agent 各自回复。
  - 若使用 relay.processing / relay.completed 混合时序，最终 UI 仍稳定保留两条消息。
  - TASKS / PROGRESS 记录最终证据、边界和回滚点。
  - 在派发包原测试命令路径错误的前提下，补充实际执行的等价门禁命令并记录结果。
- Tests Plan:
  - unit: 否。
  - contract: 否。
  - integration: 是；重跑 `tests/im_service/integration/test_m136_group_chat_flow.py`。
  - e2e: 是（页面级）；重跑 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 中 M244 相关用例。
- Expected Tests:
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 相关回归全绿。
  - 真实验证口径与限制写入 PROGRESS。
  - 不修改其他 milestone 文档。
