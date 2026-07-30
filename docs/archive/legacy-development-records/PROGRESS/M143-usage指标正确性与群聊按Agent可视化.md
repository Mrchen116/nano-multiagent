# M143 Progress - Usage 指标正确性与群聊按 Agent 可视化

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M143`
- 已确认 branch：`milestone/M143`
- 已确认约束：不修改 `data/dev-tasks.json`；不创建额外 worktree；只在 canonical repo / 指定 milestone worktree 内工作。
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`docs/需求.md`（token/turn 部分）、`docs/IM-SPEC.md`、既有 acceptance / progress 记录。
- 当前结论：M143 已完成 owner/workspace usage 修正、真实 relay completion usage 持久化、群聊按 Agent usage 展示、IM-hosted dist 同步交付。

## 执行策略
1. 先用红测锁定 relay 真 usage、owner 聚合、群聊按 Agent 展示三个缺口。
2. 最小实现只收敛到 IM metrics 写入、前端 usage 读取/刷新、群聊 usage 展示，不扩散到无关协议层。
3. 用最小相关测试集、前端 build、真实入口证据与 acceptance 文档收口。

### R1 owner/workspace 与真实 completion usage
- Context:
  - relay-backed message create path 会在真实 completion 之前写入伪 usage，导致 completion tokens 长期为 0。
  - IM 侧缺少 completed `node.report` -> owner/conversation/agent metrics 的真实落库路径。
- Decision:
  - Gateway inbound pipeline 在 completed lifecycle 上携带真实 run usage。
  - `UpstreamReporter.send_report(...)` 与 relay lifecycle callback 把 usage 写进 completed `node.report`。
  - IM `GatewayHandler` 只在 completed report 上把真实 usage 落到 owner/conversation/agent 三种 scope。
  - `WebImService` 对 relay-backed path 停止预写伪 usage，只保留 auto-complete/local path 的最小本地统计。
- Rationale:
  - 真实 usage 的唯一可信来源是 completed run state；在 create path 以词数冒充 completion 会永久污染 metrics。
  - owner/workspace、conversation、per-agent 三层视图必须共享同一 completed usage 真源，才能避免 totals 漂移。
- Evidence:
  - Tests:
    - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_nodes_metrics_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/unit/test_gateway_handler.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_main.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/unit/personal_assistant/test_gateway_pipeline.py -q` -> `41 passed in 0.36s`
    - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py -q` -> green
  - Entry:
    - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_inbound_pipeline_emits_real_usage_in_completed_relay_update`
    - `tests/unit/personal_assistant/test_main.py::test_relay_lifecycle_callback_sends_receipts_and_reports_with_real_usage_to_im`
    - `tests/im_service/unit/test_gateway_handler.py::test_completed_report_persists_real_usage_metrics`
    - `tests/im_service/integration/test_nodes_metrics_api.py::test_usage_metrics_follow_real_relay_usage_by_owner_conversation_and_agent`
- Rollback:
  - 若 completed report 写入策略出现回归，可先回滚 `GatewayHandler` 的 usage 持久化与 `WebImService` 的 relay fake-usage 删除，再恢复旧的 create-path 统计；该回滚会重新暴露 completion=0 与 owner totals 漏数。
- Commits: C1=d32b76e19e11a21d51110ee4d029e7cb804d4182, C2=856f3fcb363756ebbf2d694ee6a24ef16d5a6b52, C3=this docs commit
- Next: 已完成，进入前端 owner/workspace 刷新与 per-agent UI 收口。

### R2 This chat / Workspace total 实时值
- Context:
  - 前端 bootstrap 只拿 `selfUserId`，workspace query 误用 user id 查询 owner metrics。
  - usage cards 把 conversation rows 与 agent rows 混算，出现 double count 风险。
  - 发送与 relay lifecycle 后未统一刷新 usage 查询。
- Decision:
  - bootstrap 暴露真实 `ownerId`，workspace query 改按 owner metrics 读取。
  - `buildUsageView(...)` 只聚合 conversation scope 到 `This chat`、owner scope 到 `Workspace total`、agent scope 到 per-agent tabs。
  - `shouldRefreshUsageForEvent(...)` 在 send success、`relay.report`、`message.delivered`、`turn_end`、`message_status` 上触发 refresh。
- Rationale:
  - workspace total 的 owner 维度不能由 self user id 推导，否则 shared owner workspace 一定漏数。
  - usage cards 必须只消费对应 scope，否则 per-agent rows 会污染 conversation / workspace 主卡片。
- Evidence:
  - Tests:
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx` -> `3 passed, 26 passed`
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend run build` -> green
  - Entry:
    - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 中的 `builds conversation, workspace, and per-agent usage without double counting`
    - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 中的 `shows real conversation and workspace token-turn usage for the active chat`
- Rollback:
  - 若 owner query 或 refresh 触发点造成噪音，可先回滚至 conversation-only usage 视图；代价是 workspace total 重新失真且完成后页面不再及时刷新。
- Commits: C1=d32b76e19e11a21d51110ee4d029e7cb804d4182, C2=856f3fcb363756ebbf2d694ee6a24ef16d5a6b52, C3=this docs commit
- Next: 已完成，进入 group semantics 与 acceptance 收口。

### R3 群聊按 Agent usage 与验收收口
- Context:
  - 群聊真实 conversation type 之前会被误渲染成 direct chat。
  - 群聊缺少按 Agent usage 的可见入口，用户无法比较 agent-specific completion/prompt totals。
  - IM-hosted dist 重新 build 后，root `.gitignore` 的 `dist/` 规则会把新 hash 资源忽略掉，导致 `dist/index.html` 可能引用未跟踪文件。
- Decision:
  - `im-chat-api.ts` 基于真实 `conversation.type` 区分 direct / group / main-agent / agent-network 语义。
  - `MessagePane` 增加 per-agent tabs，并从真实 usage rows 渲染 `turns / total / prompt / completion`。
  - root `.gitignore` 显式放行 `src/IM/frontend/dist/**`，让 IM-hosted 构建产物可随源码一起提交。
  - 新增 `ACCEPTANCE/M143-acceptance.md` 记录 real-entry 浏览器与 metrics 对照证据。
- Rationale:
  - group semantics 若继续误标成 direct chat，会直接误导用户对群聊产品模型的理解。
  - IM-hosted 入口依赖仓内 `dist`，忽略新 hash 文件会让构建结果与已提交壳文件失配，形成真实入口故障。
- Evidence:
  - Tests:
    - `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_nodes_metrics_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M143/tests/im_service/integration/test_m136_group_chat_flow.py -q` -> green
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx` -> `3 passed, 26 passed`
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M143/src/IM/frontend run build` -> green
  - Entry:
    - 浏览器可见文本证据见 `/Users/czj/Repos/nano-multiagent/.worktrees/M143/ACCEPTANCE/M143-acceptance.md`
- Rollback:
  - 若 per-agent UI 或 dist 交付策略需要快速回退，可先撤掉 tabs 与 `.gitignore` 例外；代价是群聊回到不可比较的 usage 视图，且 IM-hosted build 重新暴露未跟踪资源风险。
- Commits: C1=d32b76e19e11a21d51110ee4d029e7cb804d4182, C2=856f3fcb363756ebbf2d694ee6a24ef16d5a6b52, C3=this docs commit
- Next: 已完成，等待记录真实提交哈希并继续主 agent 验收。
