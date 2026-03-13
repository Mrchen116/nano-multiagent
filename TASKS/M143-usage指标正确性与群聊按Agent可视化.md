# M143 Tasks - Usage 指标正确性与群聊按 Agent 可视化

- Milestone: M143
- Title: Usage 指标正确性与群聊按 Agent 可视化
- Goal: 修正真实路径中的 this chat/workspace total/completion tokens 统计，并补齐群聊按 Agent 视角的使用量展示。
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M143`
- branch: `milestone/M143`
- test_command: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_nodes_metrics_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_gateway_handler.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_main.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_gateway_pipeline.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py -q && npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx && npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend run build`
- allowed_scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/src/personal_assistant/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/TASKS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/PROGRESS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/ACCEPTANCE/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/.gitignore`
- forbidden_scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/data/dev-tasks.json`
  - 新建额外 worktree
  - 与 M143 无关的 CLI / kernel / docs 大范围改动
- prevention_rules:
  - 先红后绿，最小改动。
  - relay 真链路的 usage 只能以真实 run usage 为准，不能继续把“用户输入词数”冒充 completion。
  - workspace 聚合必须按 owner_id 取数，不能把 self user id 当 owner id。
  - 群聊按 Agent 展示必须来自真实 usage row，而不是前端硬编码推导。
  - IM-hosted 前端壳文件必须与源码同步，不能让 `dist/index.html` 指向未跟踪的 hash 资源。
  - 浏览器/入口证据需结合真实链路事件，不接受仅 unit mock 结论。
- dev_tasks_path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`

## R1 锁定 owner/workspace 与真实 completion usage 缺口
- Status: DONE
- Acceptance:
  - relay-backed 用户发言不再预先写入伪 usage。
  - gateway 完成真实 run 后，IM 能按 owner/conversation/agent 写入 usage。
  - real completion 发生时 completion tokens 大于 0 不再卡死。
  - workspace owner 聚合与 conversation 聚合可同时读到正确值。
- Tests Plan:
  - unit: 已覆盖 usage repository / gateway handler / relay callback / gateway pipeline。
  - integration: 已覆盖 metrics API 在 relay 真链路后的 owner/conversation/agent 聚合结果。
  - e2e: 由 ACCEPTANCE 中的真实入口证据补充收口。
- Evidence:
  - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_nodes_metrics_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_gateway_handler.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_main.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_gateway_pipeline.py -q` -> `41 passed in 0.36s`
  - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py -q` -> green
- DoD:
  - 真实 completed `node.report` 带 usage。
  - owner/conversation/agent metrics rows 同时持久化。
  - 真实提交哈希记录在 `PROGRESS` / `ACCEPTANCE`。

## R2 前端修正 This chat / Workspace total 实时值
- Status: DONE
- Acceptance:
  - workspace total 改按 owner_id 聚合，不再错误使用 self user id。
  - 当前会话 usage 与 workspace total 在发送/完成后会刷新。
  - completion tokens 在真实 completion 后可见非 0 值。
  - conversation/workspace cards 不再把 agent rows double-count。
- Tests Plan:
  - component: `chat-workspace-page.test.ts` 与 `message-pane.test.tsx` 覆盖 owner 聚合、刷新 helper、错误反馈与 usage 展示。
  - e2e: 由 ACCEPTANCE 中 IM-hosted 页面可见文本与 metrics API 对照收口。
- Evidence:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx` -> `3 passed, 26 passed`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend run build` -> green
- DoD:
  - bootstrap 暴露真实 `ownerId`。
  - usage 刷新事件覆盖 send / relay report / delivered / turn_end / message_status。
  - IM-hosted dist 与源码同步可发布。

## Commit Plan / Result
- C1: `d32b76e19e11a21d51110ee4d029e7cb804d4182` `test(M143): lock usage metrics and group chat visibility regressions`
- C2: `856f3fcb363756ebbf2d694ee6a24ef16d5a6b52` `fix(M143): ship real usage aggregation and group chat usage views`
- C3: docs capture commit created after TASKS/PROGRESS/ACCEPTANCE finalization

## R3 群聊按 Agent usage 展示与验收收口
- Status: DONE
- Acceptance:
  - 群聊页面能看到按 Agent 维度 usage tabs。
  - Agent usage 来自真实 usage row，展示 turn / total / prompt / completion。
  - Group chat 语义不再误显示成 direct chat。
  - 留下 `ACCEPTANCE/M143-acceptance.md` 作为复验证据。
- Tests Plan:
  - component: 群聊 usage tabs、agent 切换与语义文案。
  - integration: 真实 group conversation creation / mention routing / metrics 聚合。
  - e2e: 真实浏览器 + IM-hosted frontend + gateway websocket report evidence。
- Evidence:
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 覆盖 `buildUsageView`、`shouldRefreshUsageForEvent`、agent tabs 与 workspace totals。
  - `tests/im_service/integration/test_m136_group_chat_flow.py` 持续验证 group path。
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M143/ACCEPTANCE/M143-acceptance.md` 记录浏览器与 metrics 对照证据。
- DoD:
  - 群聊按 Agent 使用量可见。
  - 验收文档落地。
  - 真实提交哈希记录在 `PROGRESS` / `ACCEPTANCE`。
