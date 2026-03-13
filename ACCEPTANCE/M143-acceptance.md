# M143 Acceptance

## Scope
- Milestone: M143 — Usage 指标正确性与群聊按 Agent 可视化
- Review target: `/Users/czj/Repos/nano-multiagent/.worktrees/M143`
- Review date: 2026-03-13
- Review focus:
  - completed relay usage 是否从真实 run usage 落到 IM metrics；
  - `This chat` / `Workspace total` / `completion tokens` 是否在真实路径上正确；
  - group chat 是否提供按 Agent usage 的产品级可视化；
  - IM-hosted frontend dist 是否与源码保持可发布一致。

## User Journeys Exercised
1. Relay-backed direct chat: user message -> gateway completed report -> owner/conversation/agent metrics 持久化。
2. Active chat usage refresh: page load -> send / relay lifecycle -> `This chat` 与 `Workspace total` 立即反映真实 totals。
3. Group chat usage comparison: group conversation 打开后展示按 Agent tabs，并能切换查看不同 agent 的 prompt/completion totals。
4. IM-hosted entry delivery: frontend build 产物通过 IM host `/chat` 提供，避免 `dist/index.html` 指向未跟踪 hash 资源。

## Passes
1. **真实 completion usage 已成为 metrics 的唯一真源。**
   - Gateway completed lifecycle 现在会携带真实 `usage`。
   - IM `GatewayHandler` 只在 completed `node.report` 上把 usage 同时写入 owner / conversation / agent 三种 scope。
   - relay-backed create path 不再提前写 fake usage，因此 completion tokens 不会再被固定为 0。

2. **前端 workspace total 已改为真实 owner 聚合，并避免 double count。**
   - bootstrap 暴露 `ownerId`，workspace query 不再误用 `selfUserId`。
   - `buildUsageView(...)` 只把 `conversation` scope 用于 `This chat`，只把 `owner` scope 用于 `Workspace total`，agent scope 只进入 tabs。

3. **群聊按 Agent 的 usage 可视化已经可用。**
   - `MessagePane` 新增 per-agent tabs，可切换查看 `turns / total / prompt / completion`。
   - `im-chat-api.ts` 基于真实 `conversation.type` 显示 `Group chat` 语义，不再把群聊误标成 direct chat。

4. **最小相关门禁为绿色。**
   - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_nodes_metrics_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_gateway_handler.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_main.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_gateway_pipeline.py -q` -> `41 passed in 0.36s`
   - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py -q` -> green
   - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx` -> `3 passed, 26 passed`
   - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend run build` -> green

5. **真实入口证据显示页面文案与 metrics API 一致。**
   - 本轮 real-entry 证据中，浏览器 `body_text` 关键片段为：
     - `Group chat`
     - `Target: Multiple participants`
     - `This chat 2 turns 32 tokens Prompt 16 Completion 16`
     - `Workspace total 2 turns 32 tokens Prompt 16 Completion 16`
     - `By agent`
     - `Agent · agent-beta 1 turns 14 tokens Prompt 5 Completion 9`
   - 同一轮证据中的 metrics 对照为：
     - conversation scope: `turns=2`, `prompt_tokens=16`, `completion_tokens=16`, `total_tokens=32`
     - agent scope `agent-alpha`: `total_tokens=18`
     - agent scope `agent-beta`: `total_tokens=14`
     - owner scope: `turns=2`, `prompt_tokens=16`, `completion_tokens=16`, `total_tokens=32`
   - 该对照证明浏览器主卡片、workspace totals 与 per-agent tabs 使用的是同一组真实 metrics rows。

6. **IM-hosted dist 交付一致性已补齐。**
   - root `.gitignore` 现在显式放行 `src/IM/frontend/dist/**`，避免 `dist/index.html` 更新后引用新的 hash 资源但 git 忽略这些文件。
   - 这保证仓内 IM host 提供的壳文件与最新 frontend build 保持同步。

## Issues
### Minor 1: real-entry 证据仍是会话内人工驱动脚本，不是已入仓的长期 acceptance 自动化
- Severity: Minor
- 本轮已经拿到浏览器可见文本与 metrics API 对照证据，但该 real-entry 采集仍主要依赖会话内的 operator-style run。
- 这不阻塞 M143，因为 milestone 目标是修正 usage correctness 与群聊可视化，不是新增一整套长期 browser acceptance harness。

## Retest Focus
1. 下一轮主 agent 总验收时，直接用完整 IM + Gateway 实进程再次跑一遍 group conversation path，确认 real browser 证据可重复生成。
2. 继续抽检 mixed direct/group conversation 场景下 owner totals 是否保持正确，避免后续新增 scope 时再次把 agent rows 计入主卡片。
3. 若前端继续演进，build 后必须复查 IM-hosted `src/IM/frontend/dist/index.html` 与 `assets/*` 是否同步入库。

## Final Verdict
- Final verdict: Acceptable
- Blocking issues: 0
- Major issues: 0
- Minor issues: 1

M143 在 milestone 目标范围内已达到可验收状态：真实 completion usage、owner/workspace totals、group per-agent usage UI 与 IM-hosted dist 交付一致性均已闭环。

## Commits
- C1=d32b76e19e11a21d51110ee4d029e7cb804d4182
- C2=856f3fcb363756ebbf2d694ee6a24ef16d5a6b52
- C3=this acceptance/docs commit
